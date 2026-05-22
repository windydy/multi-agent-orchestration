"""Tests for the FastAPI REST API routes."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.models import OverviewStats, ExecutionItem, ExecutionDetail
from src.api.routes import (
    _infer_status,
    _count_completed,
    _build_nodes,
    _ts_to_dt,
    set_event_log,
    router,
)
from src.api.server import create_app
from src.api.services.event_log import EventLog


class TestStatusInference:
    """Test _infer_status helper."""

    def test_empty(self):
        assert _infer_status([]) == "unknown"

    def test_success(self):
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_started", "node_name": "req"},
            {"event_type": "node_completed", "node_name": "req"},
            {"event_type": "execution_completed"},
        ]
        assert _infer_status(events) == "success"

    def test_failed(self):
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_failed", "node_name": "dev"},
            {"event_type": "execution_completed"},
        ]
        assert _infer_status(events) == "failed"

    def test_interrupted(self):
        events = [
            {"event_type": "execution_started"},
            {"event_type": "interrupted"},
        ]
        assert _infer_status(events) == "interrupted"

    def test_running(self):
        events = [
            {"event_type": "execution_started"},
            {"event_type": "node_started", "node_name": "dev"},
        ]
        assert _infer_status(events) == "running"


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
    """Integration tests against the FastAPI app."""

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
        """Simulate a full execution and verify all endpoints."""
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
