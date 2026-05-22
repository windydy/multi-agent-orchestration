"""FastAPI REST routes for the Web UI."""

from fastapi import APIRouter

from .health import router as health_router
from .overview import router as overview_router
from .execution_read import (
    router as execution_read_router,
)
from .execution_read import set_event_log as read_set_event_log
from .executions import router as executions_router
from .executions import set_execution_manager, set_event_log as ctrl_set_event_log
from .files import router as files_router
from .workflows import router as workflows_router
from .dag import router as dag_router
from .dag import set_event_log as dag_set_event_log
from src.api.services.event_log import EventLog

router = APIRouter(prefix="/api", tags=["api"])

# Mount sub-routers
router.include_router(health_router)
router.include_router(overview_router)
router.include_router(execution_read_router)
router.include_router(executions_router)
router.include_router(files_router)
router.include_router(workflows_router)
router.include_router(dag_router)
