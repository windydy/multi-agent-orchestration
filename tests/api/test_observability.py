"""Tests for the Phase 5 Observability API endpoint."""

import pytest
import time
import json
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.api.services.event_log import EventLog


def log_full_execution(log: EventLog, thread_id: str, ts: float, success: bool = True):
    """Helper to log a full execution for testing."""
    node_deltas = {"requirements": 10, "design": 20, "develop": 30}
    log.log(thread_id, "execution_started", ts, data={"task_input": "Test"})
    ts += 1
    for node in ["requirements", "design", "develop"]:
        log.log(thread_id, "node_started", ts, node_name=node)
        ts += 5
        delta = node_deltas[node]
        token_data = {"output_summary": f"{node} done", "token_usage": {"input": 100 + delta, "output": 200 + delta}}
        if success:
            log.log(thread_id, "node_completed", ts, node_name=node, data=token_data)
        else:
            if node == "develop":
                log.log(thread_id, "node_failed", ts, node_name=node, data={"error": "API timeout error"})
            else:
                log.log(thread_id, "node_completed", ts, node_name=node, data=token_data)
        ts += 1
    if success:
        log.log(thread_id, "execution_completed", ts, data={"total_cost": 0.50})
    else:
        log.log(thread_id, "execution_completed", ts)


# Use recent timestamps (within 24h)
RECENT_TS = time.time() - 3600  # 1 hour ago


class TestObservabilityOverview:
    """Integration tests for observability overview."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_overview_empty(self, client):
        """GET returns zeros when no executions exist."""
        r = client.get("/api/observability/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_executions"] == 0
        assert data["total_cost"] == 0.0
        assert data["success_rate"] == 0.0

    def test_overview_with_executions(self, client):
        """GET returns correct stats with executions."""
        from src.api.server import get_event_log
        log = get_event_log()
        base_ts = RECENT_TS
        for i in range(5):
            log_full_execution(log, f"t_{i}", base_ts + i * 100, success=True)
        # 1 failed
        log_full_execution(log, "t_fail", base_ts + 500, success=False)

        r = client.get("/api/observability/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["total_executions"] == 6
        assert data["total_cost"] > 0
        assert 0 < data["success_rate"] < 1.0

    def test_overview_period(self, client):
        """GET with period parameter filters by time range."""
        r = client.get("/api/observability/overview?period=24h")
        assert r.status_code == 200
        data = r.json()
        assert data["period"] == "24h"


class TestCostTrend:
    """Integration tests for cost trend endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_cost_trend_empty(self, client):
        r = client.get("/api/observability/cost/daily")
        assert r.status_code == 200
        data = r.json()
        assert data["trends"] == []

    def test_cost_trend_with_data(self, client):
        """Daily cost trend returns aggregated data."""
        from src.api.server import get_event_log
        log = get_event_log()
        now = time.time()
        # Log executions over multiple days
        for day_offset in range(3):
            ts = now - day_offset * 86400
            log_full_execution(log, f"t_d{day_offset}", ts, success=True)

        r = client.get("/api/observability/cost/daily?days=7")
        assert r.status_code == 200
        data = r.json()
        assert len(data["trends"]) > 0


class TestSuccessRate:
    """Integration tests for success rate endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_success_rate_with_mixed_results(self, client):
        from src.api.server import get_event_log
        log = get_event_log()
        now = time.time()
        for i in range(3):
            log_full_execution(log, f"ok_{i}", now - i * 100, success=True)
        for i in range(1):
            log_full_execution(log, f"fail_{i}", now - i * 200, success=False)

        r = client.get("/api/observability/success-rate?days=7")
        assert r.status_code == 200
        data = r.json()
        assert len(data["rates"]) > 0


class TestNodePerformance:
    """Integration tests for node performance endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_node_performance_with_data(self, client):
        from src.api.server import get_event_log
        log = get_event_log()
        now = time.time()
        for i in range(5):
            log_full_execution(log, f"perf_{i}", now - i * 100, success=True)

        r = client.get("/api/observability/performance")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) >= 3  # requirements, design, develop
        for node in data["nodes"]:
            assert node["count"] > 0
            assert node["avg_ms"] > 0
            assert node["p50_ms"] >= 0
            assert node["p95_ms"] >= 0


class TestFailureReasons:
    """Integration tests for failure reasons endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_failure_reasons_with_failures(self, client):
        from src.api.server import get_event_log
        log = get_event_log()
        now = time.time()
        for i in range(3):
            log_full_execution(log, f"fail_{i}", now - i * 100, success=False)

        r = client.get("/api/observability/failure-reasons")
        assert r.status_code == 200
        data = r.json()
        assert len(data["reasons"]) > 0


class TestAlerts:
    """Integration tests for alerts CRUD."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        obs_db = str(tmp_path / "observability.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db, observability_db_path=obs_db)
        with TestClient(app) as c:
            yield c

    def test_alerts_empty(self, client):
        r = client.get("/api/observability/alerts")
        assert r.status_code == 200
        data = r.json()
        assert data["alerts"] == []

    def test_alert_triggered(self, client):
        """POST triggers a new alert."""
        r = client.post("/api/observability/alerts/trigger", json={
            "rule_id": "rule_test",
            "rule_name": "Test Rule",
            "severity": "high",
            "message": "Cost exceeded threshold",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["message"] == "Cost exceeded threshold"
        assert data["acknowledged"] is False

    def test_alerts_list_after_trigger(self, client):
        client.post("/api/observability/alerts/trigger", json={
            "rule_id": "rule_a", "rule_name": "Rule A",
            "severity": "medium", "message": "Test alert",
        })
        r = client.get("/api/observability/alerts")
        assert r.status_code == 200
        assert len(r.json()["alerts"]) == 1

    def test_acknowledge_alert(self, client):
        r = client.post("/api/observability/alerts/trigger", json={
            "rule_id": "rule_ack", "rule_name": "Ack Rule",
            "severity": "low", "message": "Ack me",
        })
        alert_id = r.json()["id"]

        r = client.put(f"/api/observability/alerts/{alert_id}/acknowledge")
        assert r.status_code == 200
        assert r.json()["acknowledged"] is True
