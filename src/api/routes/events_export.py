"""Events export API route.

Provides a single export endpoint:
- GET /api/events/export - Export execution events as JSON or CSV

Shares the EventLog instance from the execution_read module (injected at server startup).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

ExportFormat = Literal["json", "csv"]


def _get_event_log():
    """Get shared EventLog from execution_read module."""
    from src.api.routes.execution_read import _get_log
    return _get_log()


@router.get("/export")
async def export_events(
    thread_id: str | None = Query(default=None, description="Filter by execution thread ID"),
    since: str | None = Query(default=None, description="Start time (ISO 8601)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max events to return"),
    fmt: ExportFormat = Query(default="json", alias="format", description="Output format: json or csv"),
):
    """Export execution events in JSON or CSV format."""
    elog = _get_event_log()

    # Parse since timestamp
    since_ts: float | None = None
    if since:
        try:
            dt = datetime.fromisoformat(since)
            since_ts = dt.timestamp()
        except ValueError:
            raise HTTPException(400, f"Invalid since format: {since}. Use ISO 8601.")

    # Fetch events
    if thread_id:
        execution = elog.get_execution(thread_id)
        events: list[dict] = [] if execution is None else execution["events"]
        # Add thread_id to each event
        for e in events:
            e["thread_id"] = thread_id
        if since_ts is not None:
            events = [e for e in events if e["timestamp"] >= since_ts]
    else:
        conn = elog._get_conn()
        sql = "SELECT * FROM execution_events"
        params: list = []
        if since_ts is not None:
            sql += " WHERE timestamp >= ?"
            params.append(since_ts)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        events = []
        for r in rows:
            e = elog._row_to_event(r)
            e["thread_id"] = r["thread_id"]
            events.append(e)

    events = events[:limit]

    if fmt == "csv":
        if not events:
            return Response(content="", media_type="text/csv")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "thread_id", "event_type", "node_name", "timestamp", "data"])
        for e in events:
            writer.writerow([
                e.get("id", ""),
                thread_id or "",
                e.get("event_type", ""),
                e.get("node_name", ""),
                e.get("timestamp", ""),
                e.get("data", ""),
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=events_{thread_id or 'all'}.csv"},
        )

    return {"events": events, "total": len(events)}
