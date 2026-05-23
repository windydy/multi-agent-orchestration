"""FastAPI server entry point for the Web UI Dashboard."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from .services.event_log import EventLog
from .services.execution_manager import ExecutionManager
from .routes import router
from .routes.execution_read import set_event_log as set_read_event_log
from .routes.executions import router as executions_router, set_execution_manager, set_event_log as set_exec_event_log
from .routes.files import router as files_router, set_project_root
from .routes.workflows import router as workflows_router
from .routes.dag import router as dag_router, set_event_log as set_dag_event_log
from .routes.config import router as config_router, set_config_store
from .routes.observability import router as observability_router, set_observability
from .services.config_store import ConfigStore
from .services.observability import ObservabilityStore

_event_log: EventLog | None = None
_execution_manager: ExecutionManager | None = None
_project_root: str = ""
_static_dir: str = ""


def create_app(db_path: str | None = None, state_db_path: str | None = None, config_db_path: str | None = None, observability_db_path: str | None = None) -> FastAPI:
    """Create the FastAPI application."""
    global _event_log, _execution_manager, _project_root, _static_dir

    _project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    if db_path is None:
        db_path = os.path.join(_project_root, "checkpoints", "events.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _event_log = EventLog(db_path=db_path)
    set_read_event_log(_event_log)
    set_exec_event_log(_event_log)
    set_dag_event_log(_event_log)

    # P0-2: Initialize ExecutionManager with SQLite persistence
    if state_db_path is None:
        state_db_path = os.path.join(_project_root, "checkpoints", "execution_state.db")
    _execution_manager = ExecutionManager(db_path=state_db_path)
    set_execution_manager(_execution_manager)

    # Phase 4: Initialize ConfigStore
    if config_db_path is None:
        config_db_path = os.path.join(_project_root, "checkpoints", "config.db")
    _config_store = ConfigStore(db_path=config_db_path)
    set_config_store(_config_store)

    # Phase 5: Initialize ObservabilityStore
    if observability_db_path is None:
        observability_db_path = os.path.join(_project_root, "checkpoints", "observability.db")
    _observability_store = ObservabilityStore(events_db_path=db_path, alerts_db_path=observability_db_path)
    set_observability(_observability_store)

    # P0-3: Set project root for file access validation
    set_project_root(_project_root)

    _static_dir = os.path.join(_project_root, "web", "dist")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # P0-2: Recover execution state from database on startup
        if _execution_manager:
            recovered = await _execution_manager.recover()
            if recovered:
                print(f"[ExecutionManager] Recovered {len(recovered)} interrupted executions: {recovered}")
        yield
        if _event_log:
            _event_log.close()

    app = FastAPI(title="Multi-Agent Dashboard", lifespan=lifespan)

    # TODO: Production should load allowed origins from environment variable
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(router)
    app.include_router(executions_router)
    app.include_router(files_router)
    app.include_router(workflows_router)
    app.include_router(dag_router)
    app.include_router(config_router, prefix="/api")
    app.include_router(observability_router, prefix="/api")

    # Serve SPA static files
    if os.path.isdir(_static_dir):
        # Mount assets directory directly (handles .css, .js with dots in filenames)
        assets_dir = os.path.join(_static_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Root serves index.html
        @app.get("/")
        async def serve_root():
            return FileResponse(os.path.join(_static_dir, "index.html"))

        # Catch-all for SPA routing (paths without dots go to index.html)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = os.path.join(_static_dir, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(_static_dir, "index.html"))

    return app


# Module-level app instance for direct import
app: FastAPI = create_app()


def get_event_log() -> EventLog:
    """Get the global EventLog instance."""
    if _event_log is None:
        raise RuntimeError("EventLog not initialized. Call create_app() first.")
    return _event_log


def get_execution_manager() -> ExecutionManager:
    """Get the global ExecutionManager instance."""
    if _execution_manager is None:
        raise RuntimeError("ExecutionManager not initialized. Call create_app() first.")
    return _execution_manager
