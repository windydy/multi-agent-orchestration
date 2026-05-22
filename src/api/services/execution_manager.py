"""ExecutionManager - manages running execution instances with persistence and concurrency safety."""

import asyncio
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExecutionHandle:
    """Represents a running execution instance."""
    thread_id: str
    task: str
    workflow: str
    status: str  # running / paused / cancelled / completed / failed / interrupted
    started_at: float
    project_path: Optional[str] = None
    model_config: Optional[dict] = None
    task_handle: Optional[asyncio.Task] = None
    cancel_event: Optional[asyncio.Event] = None
    pause_event: Optional[asyncio.Event] = None
    log_buffer: list[dict] = field(default_factory=list)


class ExecutionManager:
    """Manages running execution instances with SQLite persistence and asyncio.Lock safety.

    Addresses P0 issues:
    - P0-1: Thread-safe cancellation via asyncio.Task.cancel() + CancelledError handling
    - P0-2: SQLite persistence - survives service restart
    - P0-4: asyncio.Lock for all shared state mutations
    """

    def __init__(self, db_path: str = "./checkpoints/execution_state.db"):
        self._executions: dict[str, ExecutionHandle] = {}
        self._lock = asyncio.Lock()  # P0-4: Protects all shared state mutations
        self._db_path = db_path
        self._write_lock = threading.Lock()  # For SQLite write serialization
        self._local = threading.local()
        self._ensure_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._ensure_table(conn)
        return self._local.conn

    def _ensure_db(self) -> None:
        """Create the database and table if they don't exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        self._ensure_table(conn)

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """Create the execution_state table if it doesn't exist."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_state (
                thread_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                workflow TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                project_path TEXT,
                model_config TEXT,
                updated_at REAL NOT NULL
            );
        """)
        conn.commit()

    async def recover(self) -> list[str]:
        """P0-2: Recover running executions from database on service startup.

        Returns list of thread_ids that were recovered with 'running' status
        (these should be marked as 'interrupted' since the process is gone).
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM execution_state WHERE status IN ('running', 'paused') ORDER BY started_at"
        ).fetchall()

        recovered_interrupted = []
        for row in rows:
            handle = ExecutionHandle(
                thread_id=row["thread_id"],
                task=row["task"],
                workflow=row["workflow"],
                status="interrupted",  # Mark as interrupted since process died
                started_at=row["started_at"],
                project_path=row["project_path"],
            )
            self._executions[row["thread_id"]] = handle
            recovered_interrupted.append(row["thread_id"])

            # Update status in database
            with self._write_lock:
                conn.execute(
                    "UPDATE execution_state SET status = ?, updated_at = ? WHERE thread_id = ?",
                    ("interrupted", time.time(), row["thread_id"]),
                )
                conn.commit()

        return recovered_interrupted

    def _persist(self, handle: ExecutionHandle) -> None:
        """P0-2: Persist execution state to SQLite on every state change."""
        import json
        model_config_json = json.dumps(handle.model_config) if handle.model_config else None
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO execution_state "
                "(thread_id, task, workflow, status, started_at, project_path, model_config, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    handle.thread_id,
                    handle.task,
                    handle.workflow,
                    handle.status,
                    handle.started_at,
                    handle.project_path,
                    model_config_json,
                    time.time(),
                ),
            )
            conn.commit()

    async def create_execution(
        self,
        task: str,
        workflow: str = "development",
        project_path: Optional[str] = None,
        model_config: Optional[dict] = None,
    ) -> ExecutionHandle:
        """P0-4: Create a new execution with lock-protected state mutation.

        P0-1: The returned handle has cancel_event and pause_event for LangGraph integration.
        The caller should pass handle.thread_id into the LangGraph execution context.
        """
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"

        async with self._lock:
            handle = ExecutionHandle(
                thread_id=thread_id,
                task=task,
                workflow=workflow,
                status="running",
                started_at=time.time(),
                project_path=project_path,
                model_config=model_config,
                cancel_event=asyncio.Event(),
                pause_event=asyncio.Event(),
            )
            handle.pause_event.set()  # Not paused initially
            self._executions[thread_id] = handle
            self._persist(handle)

        return handle

    async def cancel_execution(self, thread_id: str) -> bool:
        """P0-4: Cancel an execution with lock-protected state mutation.

        P0-1: Cancels the underlying asyncio.Task and sets the cancel_event.
        The LangGraph node functions should check cancel_event.is_set() between steps.
        For blocking LLM calls, the asyncio.Task.cancel() will raise CancelledError
        on the next await point.
        """
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle or handle.status not in ("running", "paused"):
                return False

            handle.status = "cancelled"
            if handle.cancel_event:
                handle.cancel_event.set()

            # P0-1: Cancel the underlying asyncio.Task if running
            if handle.task_handle and not handle.task_handle.done():
                handle.task_handle.cancel()

            self._persist(handle)
            return True

    async def pause_execution(self, thread_id: str) -> bool:
        """P0-4: Pause an execution with lock-protected state mutation."""
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle or handle.status != "running":
                return False

            handle.status = "paused"
            if handle.pause_event:
                handle.pause_event.clear()

            self._persist(handle)
            return True

    async def resume_execution(self, thread_id: str) -> bool:
        """P0-4: Resume a paused execution with lock-protected state mutation."""
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle or handle.status != "paused":
                return False

            handle.status = "running"
            if handle.pause_event:
                handle.pause_event.set()

            self._persist(handle)
            return True

    async def bind_task(self, thread_id: str, task: asyncio.Task) -> bool:
        """P0-1: Bind the LangGraph asyncio.Task to an existing ExecutionHandle.

        Called by the LangGraph runner immediately after starting the execution
        task, so that cancel_execution() can call task.cancel() on it.
        """
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle:
                return False
            handle.task_handle = task
            self._persist(handle)
            return True

    async def bind_task(self, thread_id: str, task: asyncio.Task) -> bool:
        """P0-1: Bind the LangGraph asyncio.Task to an existing ExecutionHandle.

        Called by the LangGraph runner immediately after starting the execution
        task, so that cancel_execution() can call task.cancel() on it.
        """
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle:
                return False
            handle.task_handle = task
            self._persist(handle)
            return True

    async def complete_execution(self, thread_id: str, status: str = "completed") -> bool:
        """Mark an execution as completed/failed. Called by the LangGraph runner."""
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle:
                return False

            handle.status = status
            self._persist(handle)
            return True

    async def get_execution(self, thread_id: str) -> Optional[ExecutionHandle]:
        """Get execution handle by thread_id."""
        async with self._lock:
            return self._executions.get(thread_id)

    async def list_executions(self, status: Optional[str] = None) -> list[ExecutionHandle]:
        """List executions, optionally filtered by status."""
        async with self._lock:
            handles = list(self._executions.values())
            if status:
                handles = [h for h in handles if h.status == status]
            return handles

    def log_event(self, thread_id: str, level: str, message: str, node: Optional[str] = None) -> None:
        """Add a log entry to the execution's log buffer."""
        handle = self._executions.get(thread_id)
        if handle:
            handle.log_buffer.append({
                "node": node or "system",
                "timestamp": time.time(),
                "level": level,
                "message": message,
            })

    async def get_logs(self, thread_id: str, offset: int = 0) -> list[dict]:
        """Get log entries for an execution starting from offset."""
        async with self._lock:
            handle = self._executions.get(thread_id)
            if not handle:
                return []
            return handle.log_buffer[offset:]

    async def cleanup_old(self, max_age_seconds: float = 86400) -> int:
        """Remove completed/cancelled/failed executions older than max_age_seconds."""
        async with self._lock:
            now = time.time()
            to_remove = []
            for tid, handle in self._executions.items():
                if handle.status in ("completed", "cancelled", "failed", "interrupted"):
                    if now - handle.started_at > max_age_seconds:
                        to_remove.append(tid)

            for tid in to_remove:
                del self._executions[tid]

            return len(to_remove)
