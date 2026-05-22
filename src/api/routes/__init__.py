"""FastAPI REST routes for the Web UI."""

from fastapi import APIRouter

from .health import router as health_router
from .overview import router as overview_router
from .execution_read import router as execution_read_router

router = APIRouter(prefix="/api", tags=["api"])

# Mount sub-routers
router.include_router(health_router)
router.include_router(overview_router)
router.include_router(execution_read_router)
