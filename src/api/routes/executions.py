"""Execution control API routes for Phase 2."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..services.execution_manager import ExecutionManager
from ..services.event_log import EventLog

router = APIRouter(prefix="/api", tags=["api"])

# Module-level services (injected at startup)
_execution_manager: Optional[ExecutionManager] = None
_event_log: Optional[EventLog] = None


def set_execution_manager(em: ExecutionManager) -> None:
    global _execution_manager
    _execution_manager = em


def set_event_log(log: EventLog) -> None:
    global _event_log
    _event_log = log


def _get_em() -> ExecutionManager:
    if _execution_manager is None:
        raise HTTPException(500, "ExecutionManager not initialized")
    return _execution_manager


def _get_log() -> EventLog:
    if _event_log is None:
        raise HTTPException(500, "EventLog not initialized")
    return _event_log


# ── Request/Response models ──

class CreateExecutionRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10000, description="Task description for the execution")
    workflow: str = Field(default="development", pattern="^[a-zA-Z_]+$", description="Workflow template name")
    project_path: Optional[str] = Field(default=None, max_length=500, description="Optional project directory path")
    models: Optional[dict] = Field(default=None, description="Optional model configuration (agent name -> model name)")
    max_iterations: int = Field(default=10, ge=1, le=50, description="Maximum iteration count")


class CreateExecutionResponse(BaseModel):
    thread_id: str
    status: str
    started_at: float
    workflow: str


class ControlResponse(BaseModel):
    thread_id: str
    status: str


class LogEntry(BaseModel):
    node: str
    timestamp: float
    level: str
    message: str


class LogResponse(BaseModel):
    logs: list[LogEntry]
    total: int = 0
    has_more: bool = False
    next_offset: int = 0


# ── Routes ──

@router.post("/executions", response_model=CreateExecutionResponse, status_code=201)
async def create_execution(req: CreateExecutionRequest):
    """Create a new execution.

    P0-1: Returns a thread_id that should be injected into the LangGraph
    execution context via the `config` parameter.

    P0-4: Uses asyncio.Lock internally for state safety.
    """
    em = _get_em()
    log = _get_log()
    handle = await em.create_execution(
        task=req.task,
        workflow=req.workflow,
        project_path=req.project_path,
        model_config=req.models,
    )
    # Log the execution_started event so read endpoints can find it
    import time
    log.log(handle.thread_id, "execution_started", time.time(),
            data={"task_input": req.task, "workflow": req.workflow})
    return CreateExecutionResponse(
        thread_id=handle.thread_id,
        status=handle.status,
        started_at=handle.started_at,
        workflow=handle.workflow,
    )


@router.post("/executions/{thread_id}/cancel", response_model=ControlResponse)
async def cancel_execution(thread_id: str):
    """Cancel a running execution.

    P0-1: Cancels the underlying asyncio.Task and sets the cancel_event.
    The LangGraph node functions should check for cancellation between steps.
    """
    em = _get_em()
    success = await em.cancel_execution(thread_id)
    if not success:
        raise HTTPException(400, f"Cannot cancel execution {thread_id} (not running)")

    # Log the cancellation event
    log = _get_log()
    import time
    log.log(thread_id, "interrupted", time.time(), data={"reason": "user_cancelled"})

    return ControlResponse(thread_id=thread_id, status="cancelled")


@router.post("/executions/{thread_id}/pause", response_model=ControlResponse)
async def pause_execution(thread_id: str):
    """Pause a running execution."""
    em = _get_em()
    success = await em.pause_execution(thread_id)
    if not success:
        raise HTTPException(400, f"Cannot pause execution {thread_id} (not running)")
    return ControlResponse(thread_id=thread_id, status="paused")


@router.post("/executions/{thread_id}/resume", response_model=ControlResponse)
async def resume_execution(thread_id: str):
    """Resume a paused execution."""
    em = _get_em()
    success = await em.resume_execution(thread_id)
    if not success:
        raise HTTPException(400, f"Cannot resume execution {thread_id} (not paused)")
    return ControlResponse(thread_id=thread_id, status="running")


@router.get("/executions/{thread_id}/logs", response_model=LogResponse)
async def get_execution_logs(thread_id: str, offset: int = 0, limit: int = 100):
    """Get log entries for an execution (polling-based, Phase 2 MVP).

    S1: Returns has_more and next_offset for incremental querying.
    Phase 3 should upgrade to WebSocket streaming.
    """
    em = _get_em()
    logs = await em.get_logs(thread_id, offset=offset)
    total = len(logs)
    # Trim to requested limit
    page_logs = logs[:limit]
    has_more = total > limit

    return LogResponse(
        logs=[LogEntry(**entry) for entry in page_logs],
        total=total,
        has_more=has_more,
        next_offset=offset + len(page_logs),
    )
