"""EventLog service - independent event logging SQLite database."""

import json
import sqlite3
import threading


class EventLog:
    """Records execution events to a SQLite database.
    
    Supports logging events for multi-agent workflow executions,
    aggregating them into execution views, and providing statistics.
    """

    def __init__(self, db_path: str = "./checkpoints/events.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._create_table()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._create_table_for_conn(conn)
        return self._local.conn

    def _create_table(self) -> None:
        """Create the execution_events table if it doesn't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                node_name TEXT,
                timestamp REAL NOT NULL,
                data TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_thread ON execution_events(thread_id);
        """)
        conn.commit()

    @staticmethod
    def _create_table_for_conn(conn: sqlite3.Connection) -> None:
        """Create the execution_events table on a specific connection."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                node_name TEXT,
                timestamp REAL NOT NULL,
                data TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_thread ON execution_events(thread_id);
        """)
        conn.commit()

    def log(
        self,
        thread_id: str,
        event_type: str,
        timestamp: float,
        node_name: str | None = None,
        data: dict | None = None,
    ) -> int:
        """Record an event.
        
        Args:
            thread_id: Execution thread identifier.
            event_type: One of execution_started, node_started, node_completed,
                        node_failed, execution_completed, interrupted.
            timestamp: Unix timestamp of the event.
            node_name: Node name (for node_* events).
            data: Arbitrary data to store as JSON.
            
        Returns:
            The row id of the inserted event.
        """
        data_json = json.dumps(data) if data is not None else None
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO execution_events (thread_id, event_type, node_name, timestamp, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (thread_id, event_type, node_name, timestamp, data_json),
            )
            conn.commit()
            return cursor.lastrowid

    def get_execution(self, thread_id: str) -> dict | None:
        """Aggregate all events for a thread into a complete execution view.
        
        Args:
            thread_id: Execution thread identifier.
            
        Returns:
            Dict with thread_id, events (list), status, or None if no events found.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM execution_events WHERE thread_id = ? ORDER BY timestamp ASC",
            (thread_id,),
        ).fetchall()

        if not rows:
            return None

        events = [self._row_to_event(row) for row in rows]
        status = self._infer_status(events)

        return {
            "thread_id": thread_id,
            "events": events,
            "status": status,
        }

    def get_total_count(self, status: str | None = None) -> int:
        """Get total execution count across all threads (unaffected by pagination).

        Args:
            status: If provided, only count executions with this status.
        """
        conn = self._get_conn()
        if status is None:
            row = conn.execute(
                "SELECT COUNT(DISTINCT thread_id) as cnt FROM execution_events"
            ).fetchone()
            return row["cnt"]

        # When filtering by status, we need to count threads whose inferred status matches
        rows = conn.execute("""
            SELECT
                thread_id,
                (SELECT event_type FROM execution_events e2
                 WHERE e2.thread_id = execution_events.thread_id
                 ORDER BY timestamp DESC LIMIT 1) as latest_event_type,
                (SELECT COUNT(*) > 0 FROM execution_events e3
                 WHERE e3.thread_id = execution_events.thread_id
                 AND e3.event_type = 'node_failed') as has_failed
            FROM execution_events
            GROUP BY thread_id
        """).fetchall()

        count = 0
        for row in rows:
            inferred = self._infer_status_from_summary(row["latest_event_type"], row["has_failed"])
            if inferred == status:
                count += 1
        return count

    def list_executions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """List executions sorted by latest event time descending.
        
        Args:
            limit: Maximum number of executions to return.
            offset: Number of executions to skip.
            
        Returns:
            List of execution summaries with thread_id, event_count, status, latest_event_time.
        """
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT
                thread_id,
                COUNT(*) as event_count,
                MAX(timestamp) as latest_event_time,
                (SELECT event_type FROM execution_events e2
                 WHERE e2.thread_id = execution_events.thread_id
                 ORDER BY timestamp DESC LIMIT 1) as latest_event_type,
                (SELECT COUNT(*) > 0 FROM execution_events e3
                 WHERE e3.thread_id = execution_events.thread_id
                 AND e3.event_type = 'node_failed') as has_failed
            FROM execution_events
            GROUP BY thread_id
            ORDER BY latest_event_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        result = []
        for row in rows:
            result.append({
                "thread_id": row["thread_id"],
                "event_count": row["event_count"],
                "status": self._infer_status_from_summary(
                    row["latest_event_type"], row["has_failed"]
                ),
                "latest_event_time": row["latest_event_time"],
            })

        return result

    def get_overview(self) -> dict:
        """Get overview statistics.
        
        Returns:
            Dict with total_executions, total_events, status_breakdown.
        """
        conn = self._get_conn()
        # Single query: get per-thread summary (latest event type, has_failed flag)
        rows = conn.execute("""
            SELECT
                thread_id,
                (SELECT event_type FROM execution_events e2
                 WHERE e2.thread_id = execution_events.thread_id
                 ORDER BY timestamp DESC LIMIT 1) as latest_event_type,
                (SELECT COUNT(*) > 0 FROM execution_events e3
                 WHERE e3.thread_id = execution_events.thread_id
                 AND e3.event_type = 'node_failed') as has_failed
            FROM execution_events
            GROUP BY thread_id
        """).fetchall()

        # Compute status breakdown in Python using the same inference logic
        status_breakdown: dict[str, int] = {}
        for row in rows:
            status = self._infer_status_from_summary(
                row["latest_event_type"], row["has_failed"]
            )
            status_breakdown[status] = status_breakdown.get(status, 0) + 1

        total_executions = len(rows)

        total_events_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM execution_events"
        ).fetchone()
        total_events = total_events_row["cnt"]

        return {
            "total_executions": total_executions,
            "total_events": total_events,
            "status_breakdown": status_breakdown,
        }

    def _infer_status_from_summary(self, latest_event_type: str, has_failed: bool) -> str:
        """Infer execution status from summary data (optimized for list/overview queries).
        
        Args:
            latest_event_type: The most recent event type for this thread.
            has_failed: Whether any node_failed event exists for this thread.
        """
        if latest_event_type == "interrupted":
            return "interrupted"
        if latest_event_type == "execution_completed":
            return "failed" if has_failed else "success"
        if latest_event_type == "node_failed":
            return "failed"
        return "running"

    def _infer_status(self, events: list[dict]) -> str:
        """Infer execution status from event sequence.
        
        Rules:
        - If last event is 'interrupted' -> "interrupted"
        - If last event is 'execution_completed' and no failed nodes -> "success"
        - If any node_failed event -> "failed"
        - If there are node_started without corresponding completed -> "running"
        """
        if not events:
            return "unknown"

        last_event_type = events[-1]["event_type"]

        # Check for interrupted
        if last_event_type == "interrupted":
            return "interrupted"

        # Check if execution completed
        if last_event_type == "execution_completed":
            has_failed = any(e["event_type"] == "node_failed" for e in events)
            return "failed" if has_failed else "success"

        # Check for failed nodes
        if any(e["event_type"] == "node_failed" for e in events):
            return "failed"

        # Check if running (nodes started but not all completed)
        started_nodes = set()
        completed_nodes = set()
        for e in events:
            if e["event_type"] == "node_started" and e.get("node_name"):
                started_nodes.add(e["node_name"])
            elif e["event_type"] in ("node_completed", "node_failed") and e.get("node_name"):
                completed_nodes.add(e["node_name"])

        if started_nodes and started_nodes != completed_nodes:
            return "running"

        # execution_started but no nodes yet
        if last_event_type == "execution_started":
            return "running"

        return "running"

    @staticmethod
    def _row_to_event(row) -> dict:
        """Convert a database row to an event dict."""
        data = json.loads(row["data"]) if row["data"] else None
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "node_name": row["node_name"],
            "timestamp": row["timestamp"],
            "data": data,
        }

    def close(self) -> None:
        """Close the database connection for the current thread."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

