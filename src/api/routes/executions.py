"""Execution control API routes for Phase 2."""

import asyncio
import logging
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..services.execution_manager import ExecutionManager
from ..services.event_log import EventLog

router = APIRouter(prefix="/api", tags=["api"])

# Module-level services (injected at startup)
_execution_manager: Optional[ExecutionManager] = None
_event_log: Optional[EventLog] = None
_workflow_runner: Optional["WorkflowRunner"] = None  # Bridge to the actual LangGraph runner


def set_execution_manager(em: ExecutionManager) -> None:
    global _execution_manager
    _execution_manager = em


def set_event_log(log: EventLog) -> None:
    global _event_log
    _event_log = log


def set_workflow_runner(runner: "WorkflowRunner") -> None:
    """Inject the WorkflowRunner instance so the API can trigger real execution."""
    global _workflow_runner
    _workflow_runner = runner


def _get_em() -> ExecutionManager:
    if _execution_manager is None:
        raise HTTPException(500, "ExecutionManager not initialized")
    return _execution_manager


def _get_log() -> EventLog:
    if _event_log is None:
        raise HTTPException(500, "EventLog not initialized")
    return _event_log


# Deferred import avoids circular dependency
def _get_runner() -> "WorkflowRunner":
    if _workflow_runner is None:
        raise HTTPException(500, "WorkflowRunner not initialized — cannot start execution")
    return _workflow_runner


async def _execute_background(thread_id: str, task: str, project_path: Optional[str]) -> None:
    """Run the LangGraph workflow in the background, bridging API -> real execution.

    This is the missing link: after create_execution persists the handle,
    this coroutine actually invokes the workflow and reports completion.
    """
    em = _get_em()
    log = _get_log()
    runner = _get_runner()
    logger = logging.getLogger(__name__)

    try:
        # Wait for the handle's pause_event (running means it's set)
        handle = await em.get_execution(thread_id)
        if handle and handle.pause_event:
            await handle.pause_event.wait()

        log.log(thread_id, "workflow_start", time.time(),
                data={"task": task, "project_path": project_path})

        result = await runner.run(
            task=task,
            project_path=project_path or ".",
            thread_id=thread_id,
        )

        if result.get("success"):
            log.log(thread_id, "workflow_completed", time.time(),
                    data={"summary": result.get("summary")})
            await em.complete_execution(thread_id, status="completed")
        else:
            log.log(thread_id, "workflow_failed", time.time(),
                    data={"error": result.get("error")})
            await em.complete_execution(thread_id, status="failed")

    except asyncio.CancelledError:
        log.log(thread_id, "workflow_cancelled", time.time())
        await em.complete_execution(thread_id, status="cancelled")
    except Exception as e:
        logger.exception("Background execution failed for %s", thread_id)
        log.log(thread_id, "workflow_error", time.time(), data={"error": str(e)})
        await em.complete_execution(thread_id, status="failed")


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
    """Create a new execution and trigger the LangGraph workflow.

    P0-1: Returns a thread_id that is injected into the LangGraph
    execution context via the `config` parameter.

    P0-4: Uses asyncio.Lock internally for state safety.

    FIX: Now actually spawns the background task via asyncio.create_task
    and binds it to the ExecutionHandle for cancellation support.
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
    log.log(handle.thread_id, "execution_started", time.time(),
            data={"task_input": req.task, "workflow": req.workflow})

    # ── ARCHITECTURE FIX: spawn the actual workflow runner ──
    background_task = asyncio.create_task(
        _execute_background(handle.thread_id, req.task, req.project_path)
    )
    await em.bind_task(handle.thread_id, background_task)

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
