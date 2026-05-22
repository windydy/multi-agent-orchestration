"""Execution list and detail read routes (Phase 1)."""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from ..models import ExecutionListResponse, ExecutionItem, ExecutionDetail, NodeEvent, NodeStatus
from ..services.event_log import EventLog

router = APIRouter()

# Module-level event log (injected at startup)
_event_log: EventLog | None = None


def set_event_log(log: EventLog) -> None:
    global _event_log
    _event_log = log


def _get_log() -> EventLog:
    if _event_log is None:
        raise HTTPException(500, "EventLog not initialized")
    return _event_log


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _count_completed(events: list[dict]) -> int:
    return sum(1 for e in events if e["event_type"] == "node_completed")


def _count_nodes_started(events: list[dict]) -> int:
    return sum(1 for e in events if e["event_type"] == "node_started")


def _build_nodes(events: list[dict]) -> list[NodeEvent]:
    """Aggregate node events into NodeEvent list."""
    node_map: dict[str, dict] = {}
    for e in events:
        node = e.get("node_name")
        if not node:
            continue
        if node not in node_map:
            node_map[node] = {"node": node, "started": None, "ended": None,
                              "status": "pending", "output": None, "error": None, "tokens": None}
        et = e["event_type"]
        ts = e["timestamp"]
        data = e.get("data") or {}
        if et == "node_started":
            node_map[node]["started"] = ts
            node_map[node]["status"] = "running"
        elif et == "node_completed":
            node_map[node]["ended"] = ts
            node_map[node]["status"] = "success"
            node_map[node]["output"] = data.get("output_summary")
            node_map[node]["tokens"] = data.get("token_usage")
        elif et == "node_failed":
            node_map[node]["ended"] = ts
            node_map[node]["status"] = "failed"
            node_map[node]["error"] = data.get("error")

    result = []
    for n in node_map.values():
        dur = None
        if n["started"] and n["ended"]:
            dur = int((n["ended"] - n["started"]) * 1000)
        result.append(NodeEvent(
            node=n["node"],
            status=NodeStatus(n["status"]),
            started_at=_ts_to_dt(n["started"]),
            ended_at=_ts_to_dt(n["ended"]),
            duration_ms=dur,
            output_summary=n["output"],
            error=n["error"],
            token_usage=n["tokens"],
        ))
    return result


@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(limit: int = 20, offset: int = 0, status: str | None = None):
    log = _get_log()
    executions = log.list_executions(limit=limit, offset=offset)

    items: list[ExecutionItem] = []
    for ex in executions:
        events_data = log.get_execution(ex["thread_id"])
        events = events_data["events"] if events_data else []
        ex_status = events_data["status"] if events_data else "unknown"

        if status and ex_status != status:
            continue

        started_ts = None
        ended_ts = None
        for e in events:
            if e["event_type"] == "execution_started" and started_ts is None:
                started_ts = e["timestamp"]
            if e["event_type"] in ("execution_completed", "node_failed", "interrupted"):
                ended_ts = e["timestamp"]

        dur = None
        if started_ts and ended_ts:
            dur = int((ended_ts - started_ts) * 1000)

        items.append(ExecutionItem(
            thread_id=ex["thread_id"],
            status=ex_status,
            started_at=_ts_to_dt(started_ts) or _ts_to_dt(ex["latest_event_time"]),
            ended_at=_ts_to_dt(ended_ts),
            duration_ms=dur,
            node_count=_count_nodes_started(events),
            completed_nodes=_count_completed(events),
        ))

    total = log.get_total_count(status=status) if items else log.get_total_count(status=None)
    return ExecutionListResponse(total=total, items=items)


@router.get("/executions/{thread_id}", response_model=ExecutionDetail)
async def get_execution(thread_id: str):
    log = _get_log()
    data = log.get_execution(thread_id)
    if data is None:
        raise HTTPException(404, f"Execution {thread_id} not found")

    events = data["events"]
    ex_status = data["status"]

    started_ts = None
    ended_ts = None
    total_cost = None
    total_tokens = 0
    task_input = None

    for e in events:
        et = e["event_type"]
        ts = e["timestamp"]
        d = e.get("data") or {}
        if et == "execution_started":
            if started_ts is None:
                started_ts = ts
            task_input = d.get("task_input")
        elif et in ("execution_completed", "interrupted"):
            ended_ts = ts
            if d.get("total_cost") is not None:
                total_cost = d["total_cost"]

    # Sum tokens from node events
    for e in events:
        d = e.get("data") or {}
        tu = d.get("token_usage")
        if tu:
            total_tokens += tu.get("input", 0) + tu.get("output", 0)

    dur = None
    if started_ts and ended_ts:
        dur = int((ended_ts - started_ts) * 1000)

    return ExecutionDetail(
        thread_id=thread_id,
        status=ex_status,
        started_at=_ts_to_dt(started_ts),
        ended_at=_ts_to_dt(ended_ts),
        duration_ms=dur,
        nodes=_build_nodes(events),
        total_cost=total_cost,
        total_tokens=total_tokens or None,
        task_input=task_input,
    )
