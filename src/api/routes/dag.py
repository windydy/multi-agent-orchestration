"""DAG visualization API route (Phase 3)."""

from fastapi import APIRouter, HTTPException
from ..models import DAGResponse, DAGNode, DAGEdge
from ..services.event_log import EventLog

router = APIRouter(tags=["api"])

_event_log: EventLog | None = None

# Default workflow template edges (development pipeline)
_DEVELOPMENT_EDGES: list[tuple[str, str]] = [
    ("requirements", "design"),
    ("design", "develop"),
    ("develop", "review"),
    ("develop", "test"),
    ("review", "fix"),
    ("test", "fix"),
]

_WORKFLOW_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "development": _DEVELOPMENT_EDGES,
}

_NODE_LABELS: dict[str, str] = {
    "requirements": "Requirements Agent",
    "design": "Design Agent",
    "develop": "Develop Agent",
    "review": "Review Agent",
    "test": "Test Agent",
    "fix": "Fix Agent",
}


def set_event_log(log: EventLog) -> None:
    global _event_log
    _event_log = log


def _get_log() -> EventLog:
    if _event_log is None:
        raise HTTPException(500, "EventLog not initialized")
    return _event_log


@router.get("/executions/{thread_id}/dag", response_model=DAGResponse)
async def get_execution_dag(thread_id: str):
    """Return DAG structure for an execution with node statuses.

    Nodes: inferred from execution events (success/failed/running/pending).
    Edges: from workflow template definition (defaults to development pipeline).
    """
    log = _get_log()
    data = log.get_execution(thread_id)
    if data is None:
        raise HTTPException(404, f"Execution {thread_id} not found")

    events = data["events"]

    # Build node map from events
    node_map: dict[str, dict] = {}
    for e in events:
        node_name = e.get("node_name")
        if not node_name:
            continue
        if node_name not in node_map:
            node_map[node_name] = {
                "id": node_name,
                "label": _NODE_LABELS.get(node_name, node_name),
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "duration_ms": None,
                "token_usage": None,
                "output_summary": None,
                "cost": None,
            }
        et = e["event_type"]
        ts = e["timestamp"]
        d = e.get("data") or {}

        if et == "node_started":
            node_map[node_name]["started_at"] = ts
            node_map[node_name]["status"] = "running"
        elif et == "node_completed":
            node_map[node_name]["ended_at"] = ts
            node_map[node_name]["status"] = "success"
            node_map[node_name]["output_summary"] = d.get("output_summary")
            tu = d.get("token_usage")
            if tu:
                node_map[node_name]["token_usage"] = tu
                node_map[node_name]["cost"] = d.get("cost")
            if node_map[node_name]["started_at"]:
                node_map[node_name]["duration_ms"] = int(
                    (ts - node_map[node_name]["started_at"]) * 1000
                )
        elif et == "node_failed":
            node_map[node_name]["ended_at"] = ts
            node_map[node_name]["status"] = "failed"
            node_map[node_name]["output_summary"] = d.get("error")
            if node_map[node_name]["started_at"]:
                node_map[node_name]["duration_ms"] = int(
                    (ts - node_map[node_name]["started_at"]) * 1000
                )

    # Build nodes list
    nodes = [DAGNode(**n) for n in node_map.values()]

    # Get edges from workflow template
    edges = [
        DAGEdge(from_node=f, to_node=t)
        for f, t in _WORKFLOW_TEMPLATES.get("development", _DEVELOPMENT_EDGES)
    ]

    return DAGResponse(thread_id=thread_id, nodes=nodes, edges=edges)
