"""Observability service — aggregation queries and alerts management."""

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AlertItem:
    id: str
    rule_id: str
    rule_name: str
    triggered_at: float
    severity: str
    message: str
    acknowledged: bool


class ObservabilityStore:
    """SQLite-backed observability: aggregation queries + alerts."""

    def __init__(self, events_db_path: str, alerts_db_path: str = "./checkpoints/observability.db"):
        self._events_db_path = events_db_path
        self._alerts_db_path = alerts_db_path
        self._local = threading.local()
        self._alerts_local = threading.local()
        self._write_lock = threading.Lock()
        self._ensure_alerts_db()

    def _get_events_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._events_db_path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _get_alerts_conn(self) -> sqlite3.Connection:
        if not hasattr(self._alerts_local, "conn") or self._alerts_local.conn is None:
            conn = sqlite3.connect(self._alerts_db_path)
            conn.row_factory = sqlite3.Row
            self._alerts_local.conn = conn
            self._ensure_alerts_table(conn)
        return self._alerts_local.conn

    def _ensure_alerts_db(self) -> None:
        Path(self._alerts_db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_alerts_conn()
        self._ensure_alerts_table(conn)

    def _ensure_alerts_table(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL DEFAULT '',
                triggered_at REAL NOT NULL,
                severity TEXT NOT NULL DEFAULT 'medium',
                message TEXT NOT NULL DEFAULT '',
                acknowledged INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(triggered_at);
        """)
        conn.commit()

    # ── Period helpers ──

    def _period_seconds(self, period: str) -> float:
        periods = {"24h": 86400, "7d": 604800, "30d": 2592000}
        return periods.get(period, 86400)

    # ── Overview ──

    def get_overview(self, period: str = "24h") -> dict:
        conn = self._get_events_conn()
        cutoff = time.time() - self._period_seconds(period)

        # Thread-level summaries using subqueries (same as EventLog.get_overview)
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

        total = 0
        success = 0
        failed = 0
        for r in rows:
            latest = r["latest_event_type"]
            has_failed = bool(r["has_failed"])
            total += 1
            if latest == "execution_completed" and not has_failed:
                success += 1
            elif has_failed or latest == "node_failed":
                failed += 1

        # Total cost from execution_completed events
        total_cost = 0.0
        cost_rows = conn.execute("""
            SELECT data FROM execution_events
            WHERE event_type = 'execution_completed' AND timestamp > ? AND data IS NOT NULL
        """, (cutoff,)).fetchall()
        for cr in cost_rows:
            try:
                d = json.loads(cr[0]) if isinstance(cr[0], str) else cr[0]
                if d and isinstance(d, dict):
                    total_cost += d.get("total_cost", 0) or 0
            except (json.JSONDecodeError, TypeError):
                pass

        # Total tokens from node_completed events
        total_tokens = 0
        token_rows = conn.execute("""
            SELECT data FROM execution_events
            WHERE event_type = 'node_completed' AND timestamp > ? AND data IS NOT NULL
        """, (cutoff,)).fetchall()
        for tr in token_rows:
            try:
                d = json.loads(tr[0]) if isinstance(tr[0], str) else tr[0]
                if d and isinstance(d, dict):
                    tu = d.get("token_usage")
                    if tu and isinstance(tu, dict):
                        total_tokens += tu.get("input", 0) + tu.get("output", 0)
            except (json.JSONDecodeError, TypeError):
                pass

        success_rate = success / total if total > 0 else 0.0

        # Alert count (unacknowledged)
        alerts_conn = self._get_alerts_conn()
        alert_row = alerts_conn.execute(
            "SELECT COUNT(*) as cnt FROM alerts WHERE acknowledged = 0"
        ).fetchone()
        alert_count = alert_row["cnt"] if alert_row else 0

        return {
            "period": period,
            "total_executions": total,
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "success_rate": round(success_rate, 4),
            "avg_duration_ms": 0,
            "alert_count": alert_count,
        }

    # ── Cost Trend ──

    def get_cost_trend(self, days: int = 7) -> list[dict]:
        conn = self._get_events_conn()
        cutoff = time.time() - days * 86400

        # Get all execution_completed events in range
        rows = conn.execute("""
            SELECT timestamp, data FROM execution_events
            WHERE event_type = 'execution_completed' AND timestamp > ? AND data IS NOT NULL
            ORDER BY timestamp
        """, (cutoff,)).fetchall()

        # Aggregate by date
        daily: dict[str, dict] = {}
        for r in rows:
            ts = r["timestamp"]
            day_key = time.strftime("%Y-%m-%d", time.gmtime(ts))
            if day_key not in daily:
                daily[day_key] = {"date": day_key, "total_cost": 0.0, "total_tokens": 0, "execution_count": 0}
            daily[day_key]["execution_count"] += 1
            try:
                d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                if d and isinstance(d, dict):
                    daily[day_key]["total_cost"] += d.get("total_cost", 0) or 0
            except (json.JSONDecodeError, TypeError):
                pass

        # Get tokens per day
        token_rows = conn.execute("""
            SELECT timestamp, data FROM execution_events
            WHERE event_type = 'node_completed' AND timestamp > ? AND data IS NOT NULL
        """, (cutoff,)).fetchall()
        for r in token_rows:
            ts = r["timestamp"]
            day_key = time.strftime("%Y-%m-%d", time.gmtime(ts))
            try:
                d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                if d and isinstance(d, dict):
                    tu = d.get("token_usage")
                    if tu and isinstance(tu, dict):
                        if day_key in daily:
                            daily[day_key]["total_tokens"] += tu.get("input", 0) + tu.get("output", 0)
            except (json.JSONDecodeError, TypeError):
                pass

        return sorted(daily.values(), key=lambda x: x["date"])

    # ── Success Rate ──

    def get_success_rate(self, days: int = 7) -> list[dict]:
        conn = self._get_events_conn()
        cutoff = time.time() - days * 86400

        rows = conn.execute("""
            SELECT
                thread_id,
                (SELECT MAX(timestamp) FROM execution_events e2
                 WHERE e2.thread_id = execution_events.thread_id) as latest_time,
                (SELECT event_type FROM execution_events e2
                 WHERE e2.thread_id = execution_events.thread_id
                 ORDER BY timestamp DESC LIMIT 1) as latest_event_type,
                (SELECT COUNT(*) > 0 FROM execution_events e3
                 WHERE e3.thread_id = execution_events.thread_id
                 AND e3.event_type = 'node_failed') as has_failed
            FROM execution_events
            GROUP BY thread_id
        """).fetchall()

        daily: dict[str, dict] = {}
        for r in rows:
            ts = r["latest_time"]
            day_key = time.strftime("%Y-%m-%d", time.gmtime(ts))
            if day_key not in daily:
                daily[day_key] = {"date": day_key, "total": 0, "success": 0, "failed": 0, "rate": 0.0}
            daily[day_key]["total"] += 1
            if r["has_failed"]:
                daily[day_key]["failed"] += 1
            elif r["latest_event_type"] == "execution_completed":
                daily[day_key]["success"] += 1

        for d in daily.values():
            if d["total"] > 0:
                d["rate"] = round(d["success"] / d["total"], 4)

        return sorted(daily.values(), key=lambda x: x["date"])

    # ── Node Performance ──

    def get_node_performance(self) -> list[dict]:
        conn = self._get_events_conn()

        # Build start time map per thread
        thread_starts: dict[str, dict[str, float]] = {}
        started_all = conn.execute("""
            SELECT thread_id, node_name, timestamp FROM execution_events
            WHERE event_type = 'node_started' AND node_name IS NOT NULL
        """).fetchall()
        for r in started_all:
            tid = r["thread_id"]
            if tid not in thread_starts:
                thread_starts[tid] = {}
            thread_starts[tid][r["node_name"]] = r["timestamp"]

        # Build durations from completed nodes
        completed_all = conn.execute("""
            SELECT thread_id, node_name, timestamp FROM execution_events
            WHERE event_type = 'node_completed' AND node_name IS NOT NULL
        """).fetchall()

        node_durations: dict[str, list[float]] = {}
        for r in completed_all:
            tid = r["thread_id"]
            name = r["node_name"]
            if tid in thread_starts and name in thread_starts[tid]:
                duration_ms = (r["timestamp"] - thread_starts[tid][name]) * 1000
                if name not in node_durations:
                    node_durations[name] = []
                node_durations[name].append(duration_ms)

        result = []
        for name, durations in sorted(node_durations.items()):
            durations.sort()
            n = len(durations)
            avg = sum(durations) / n if n > 0 else 0
            p50 = durations[int(n * 0.5)] if n > 0 else 0
            p95 = durations[min(int(n * 0.95), n - 1)] if n > 0 else 0
            p99 = durations[min(int(n * 0.99), n - 1)] if n > 0 else 0
            result.append({
                "node": name,
                "count": n,
                "avg_ms": round(avg, 1),
                "p50_ms": round(p50, 1),
                "p95_ms": round(p95, 1),
                "p99_ms": round(p99, 1),
            })

        return result

    # ── Failure Reasons ──

    def get_failure_reasons(self) -> list[dict]:
        conn = self._get_events_conn()
        rows = conn.execute("""
            SELECT data FROM execution_events
            WHERE event_type = 'node_failed' AND data IS NOT NULL
        """).fetchall()

        reasons: dict[str, int] = {}
        total = 0
        for r in rows:
            try:
                d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                error = (d.get("error") or "unknown") if isinstance(d, dict) else "unknown"
                total += 1

                # Categorize
                error_lower = error.lower()
                if "timeout" in error_lower:
                    category = "Timeout"
                elif "oom" in error_lower or "memory" in error_lower:
                    category = "OOM"
                elif "api" in error_lower or "http" in error_lower or "connection" in error_lower:
                    category = "API Error"
                elif "network" in error_lower:
                    category = "Network Error"
                elif "syntax" in error_lower or "parse" in error_lower:
                    category = "Syntax Error"
                else:
                    category = "Other"

                reasons[category] = reasons.get(category, 0) + 1
            except (json.JSONDecodeError, TypeError):
                total += 1
                reasons["Parse Error"] = reasons.get("Parse Error", 0) + 1

        result = []
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            result.append({
                "reason": reason,
                "count": count,
                "percentage": round(count / total * 100, 1) if total > 0 else 0,
            })

        return result

    # ── Alerts ──

    def list_alerts(self) -> list[AlertItem]:
        conn = self._get_alerts_conn()
        rows = conn.execute("SELECT * FROM alerts ORDER BY triggered_at DESC").fetchall()
        return [AlertItem(
            id=r["id"], rule_id=r["rule_id"], rule_name=r["rule_name"],
            triggered_at=r["triggered_at"], severity=r["severity"],
            message=r["message"], acknowledged=bool(r["acknowledged"]),
        ) for r in rows]

    def create_alert(
        self, rule_id: str, rule_name: str, severity: str, message: str,
        cooldown_seconds: float = 300,
    ) -> Optional[AlertItem]:
        """Create alert with cooldown: skip if same rule triggered recently."""
        conn = self._get_alerts_conn()
        cutoff = time.time() - cooldown_seconds
        existing = conn.execute(
            "SELECT id FROM alerts WHERE rule_id = ? AND triggered_at > ? AND acknowledged = 0",
            (rule_id, cutoff),
        ).fetchone()
        if existing:
            return None  # Cooldown active

        alert_id = f"alert_{uuid.uuid4().hex[:8]}"
        now = time.time()
        with self._write_lock:
            conn.execute(
                "INSERT INTO alerts (id, rule_id, rule_name, triggered_at, severity, message, acknowledged) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (alert_id, rule_id, rule_name, now, severity, message),
            )
            conn.commit()

        return AlertItem(
            id=alert_id, rule_id=rule_id, rule_name=rule_name,
            triggered_at=now, severity=severity, message=message, acknowledged=False,
        )

    def acknowledge_alert(self, alert_id: str) -> bool:
        with self._write_lock:
            conn = self._get_alerts_conn()
            cursor = conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,),
            )
            conn.commit()
        return cursor.rowcount > 0
