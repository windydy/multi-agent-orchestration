"""Tests for the FastAPI REST API routes (Phase 1 + Phase 2)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.models import OverviewStats, ExecutionItem, ExecutionDetail
from src.api.routes.execution_read import (
    _count_completed,
    _build_nodes,
    _ts_to_dt,
    set_event_log,
)
from src.api.services.event_log import EventLog
from src.api.server import create_app


class TestStatusInference:
    """Test EventLog._infer_status helper."""

    def test_empty(self):
        log = EventLog(db_path=":memory:")
        assert log._infer_status([]) == "unknown"

    def test_success(self):
        log = EventLog(db_path=":memory:")
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_started", "node_name": "req"},
            {"event_type": "node_completed", "node_name": "req"},
            {"event_type": "execution_completed"},
        ]
        assert log._infer_status(events) == "success"

    def test_failed(self):
        log = EventLog(db_path=":memory:")
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_failed", "node_name": "dev"},
            {"event_type": "execution_completed"},
        ]
        assert log._infer_status(events) == "failed"

    def test_interrupted(self):
        log = EventLog(db_path=":memory:")
        events = [
            {"event_type": "execution_started"},
            {"event_type": "interrupted"},
        ]
        assert log._infer_status(events) == "interrupted"

    def test_running(self):
        log = EventLog(db_path=":memory:")
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_started", "node_name": "dev"},
        ]
        assert log._infer_status(events) == "running"


class TestCountCompleted:
    def test_zero(self):
        assert _count_completed([]) == 0

    def test_counts_only_completed(self):
        events = [
            {"event_type": "node_started"},
            {"event_type": "node_completed"},
            {"event_type": "node_completed"},
            {"event_type": "node_failed"},
        ]
        assert _count_completed(events) == 2


class TestBuildNodes:
    def test_empty(self):
        assert _build_nodes([]) == []

    def test_single_node(self):
        events = [
            {"event_type": "node_started", "node_name": "req", "timestamp": 1000.0, "data": None},
            {"event_type": "node_completed", "node_name": "req", "timestamp": 1014.2,
             "data": {"output_summary": "done", "token_usage": {"input": 100, "output": 200}}},
        ]
        nodes = _build_nodes(events)
        assert len(nodes) == 1
        assert nodes[0].node == "req"
        assert nodes[0].status.value == "success"
        assert nodes[0].duration_ms == 14200
        assert nodes[0].output_summary == "done"
        assert nodes[0].token_usage == {"input": 100, "output": 200}


class TestAPIEndpoints:
    """Integration tests against the FastAPI app (Phase 1 read routes)."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        app = create_app(db_path=db_path)
        with TestClient(app) as c:
            yield c

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_overview_empty(self, client):
        r = client.get("/api/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_executions"] == 0

    def test_executions_empty(self, client):
        r = client.get("/api/executions")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_execution_not_found(self, client):
        r = client.get("/api/executions/nonexistent")
        assert r.status_code == 404

    def test_full_workflow(self, client):
        """Simulate a full execution and verify all read endpoints."""
        from src.api.server import get_event_log
        log = get_event_log()

        # Start execution
        log.log("thread_test", "execution_started", 1000.0,
                data={"task_input": "Build an API"})

        # Node: requirements
        log.log("thread_test", "node_started", 1001.0, node_name="requirements")
        log.log("thread_test", "node_completed", 1015.0, node_name="requirements",
                data={"output_summary": "Requirements done", "token_usage": {"input": 300, "output": 800}})

        # Node: design
        log.log("thread_test", "node_started", 1016.0, node_name="design")
        log.log("thread_test", "node_completed", 1038.0, node_name="design",
                data={"output_summary": "Design done", "token_usage": {"input": 900, "output": 1200}})

        # Complete
        log.log("thread_test", "execution_completed", 1040.0,
                data={"total_cost": 0.45})

        # Verify overview
        r = client.get("/api/overview")
        assert r.status_code == 200
        ov = r.json()
        assert ov["total_executions"] == 1
        assert ov["success"] == 1

        # Verify list
        r = client.get("/api/executions")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["thread_id"] == "thread_test"
        assert items[0]["status"] == "success"
        assert items[0]["completed_nodes"] == 2

        # Verify detail
        r = client.get("/api/executions/thread_test")
        assert r.status_code == 200
        detail = r.json()
        assert detail["status"] == "success"
        assert detail["task_input"] == "Build an API"
        assert detail["total_cost"] == 0.45
        assert len(detail["nodes"]) == 2
        assert detail["nodes"][0]["node"] == "requirements"
        assert detail["nodes"][1]["node"] == "design"


class TestPhase2ExecutionControl:
    """Integration tests for Phase 2 execution control routes."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        app = create_app(db_path=db_path, state_db_path=state_db)
        with TestClient(app) as c:
            yield c

    def test_create_execution(self, client):
        """POST /api/executions — create a new execution."""
        r = client.post("/api/executions", json={
            "task": "Build a REST API",
            "workflow": "development",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["thread_id"].startswith("thread_")
        assert data["status"] == "running"
        assert data["workflow"] == "development"
        assert data["started_at"] > 0

    def test_create_execution_with_project_path(self, client):
        """POST /api/executions — with optional project path."""
        r = client.post("/api/executions", json={
            "task": "Test task",
            "project_path": "/tmp/my-project",
            "max_iterations": 20,
        })
        assert r.status_code == 201
        data = r.json()
        thread_id = data["thread_id"]

        # Verify it appears in list
        r = client.get(f"/api/executions/{thread_id}")
        assert r.status_code == 200

    def test_create_execution_validation(self, client):
        """POST /api/executions — validation rejects empty task."""
        r = client.post("/api/executions", json={"task": ""})
        assert r.status_code == 422

    def test_cancel_execution(self, client):
        """POST /api/executions/{id}/cancel — cancel a running execution."""
        # Create first
        r = client.post("/api/executions", json={"task": "Cancel me"})
        thread_id = r.json()["thread_id"]

        # Cancel
        r = client.post(f"/api/executions/{thread_id}/cancel")
        assert r.status_code == 200
        data = r.json()
        assert data["thread_id"] == thread_id
        assert data["status"] == "cancelled"

    def test_cancel_nonexistent(self, client):
        """Cancel a non-existent execution returns 400."""
        r = client.post("/api/executions/nonexistent/cancel")
        assert r.status_code == 400

    def test_pause_and_resume(self, client):
        """Pause and resume a running execution."""
        # Create
        r = client.post("/api/executions", json={"task": "Pause test"})
        thread_id = r.json()["thread_id"]

        # Pause
        r = client.post(f"/api/executions/{thread_id}/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

        # Resume
        r = client.post(f"/api/executions/{thread_id}/resume")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_pause_non_running(self, client):
        """Pause an already cancelled execution returns 400."""
        r = client.post("/api/executions", json={"task": "Test"})
        thread_id = r.json()["thread_id"]
        client.post(f"/api/executions/{thread_id}/cancel")

        r = client.post(f"/api/executions/{thread_id}/pause")
        assert r.status_code == 400

    def test_resume_non_paused(self, client):
        """Resume a running (non-paused) execution returns 400."""
        r = client.post("/api/executions", json={"task": "Test"})
        thread_id = r.json()["thread_id"]

        r = client.post(f"/api/executions/{thread_id}/resume")
        assert r.status_code == 400

    def test_get_logs_empty(self, client):
        """GET /api/executions/{id}/logs — returns empty list for new execution."""
        r = client.post("/api/executions", json={"task": "Log test"})
        thread_id = r.json()["thread_id"]

        r = client.get(f"/api/executions/{thread_id}/logs")
        assert r.status_code == 200
        data = r.json()
        assert data["logs"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_executions_with_data(self, client):
        """GET /api/executions — shows created executions."""
        # Create two
        client.post("/api/executions", json={"task": "Task A"})
        client.post("/api/executions", json={"task": "Task B"})

        r = client.get("/api/executions")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2

    def test_workflows_endpoint(self, client):
        """GET /api/workflows — returns available workflow templates."""
        r = client.get("/api/workflows")
        assert r.status_code == 200
        data = r.json()
        assert len(data["workflows"]) >= 1
        assert data["workflows"][0]["name"] == "development"

    def test_models_endpoint(self, client):
        """GET /api/models — returns available model options."""
        r = client.get("/api/models")
        assert r.status_code == 200
        data = r.json()
        assert len(data["models"]) >= 1
