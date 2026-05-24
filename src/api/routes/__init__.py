"""FastAPI REST routes for the Web UI."""

from fastapi import APIRouter

from src.api.services.event_log import EventLog

from .clarification import (
    router as clarification_router,
    set_clarifier,
)
from .dag import router as dag_router
from .dag import set_event_log as dag_set_event_log
from .events_export import router as events_export_router
from .execution_read import (
    router as execution_read_router,
    set_event_log as read_set_event_log,
)
from .executions import (
    router as executions_router,
    set_event_log as ctrl_set_event_log,
    set_execution_manager,
    set_workflow_runner,
)
from .files import router as files_router
from .health import router as health_router
from .memory import router as memory_router
from .overview import router as overview_router
from .workflows import router as workflows_router
from .ws import router as ws_router
from .ws import set_ws_manager

router = APIRouter(prefix="/api", tags=["api"])

# Mount sub-routers
router.include_router(health_router)
router.include_router(overview_router)
router.include_router(execution_read_router)
router.include_router(executions_router)
router.include_router(files_router)
router.include_router(workflows_router)
router.include_router(dag_router)
router.include_router(ws_router)
router.include_router(clarification_router)
router.include_router(memory_router)
router.include_router(events_export_router)
