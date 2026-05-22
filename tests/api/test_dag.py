"""Tests for the Phase 3 DAG API endpoint."""

import pytest
import time
from fastapi.testclient import TestClient

from src.api.services.event_log import EventLog
from src.api.server import create_app


class TestDAGEndpoint:
    """Integration tests for GET /api/executions/{id}/dag."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        app = create_app(db_path=db_path, state_db_path=state_db)
        with TestClient(app) as c:
            yield c

    def test_dag_empty_execution(self, client):
        """A fresh execution with no events returns empty DAG."""
        from src.api.server import get_event_log
        log = get_event_log()
        log.log("thread_empty", "execution_started", 1000.0, data={"task_input": "Test"})

        r = client.get("/api/executions/thread_empty/dag")
        assert r.status_code == 200
        data = r.json()
        assert data["thread_id"] == "thread_empty"
        assert data["nodes"] == []
        assert data["edges"] != []  # Edges exist (workflow template)

    def test_dag_single_node(self, client):
        """Execution with one completed node returns correct DAG."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_one", "execution_started", ts, data={"task_input": "Test"})
        log.log("thread_one", "node_started", ts + 1, node_name="requirements")
        log.log("thread_one", "node_completed", ts + 15, node_name="requirements",
                data={"output_summary": "Done", "token_usage": {"input": 100, "output": 200}})

        r = client.get("/api/executions/thread_one/dag")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["id"] == "requirements"
        assert node["status"] == "success"
        assert node["duration_ms"] == 14000

    def test_dag_full_pipeline(self, client):
        """Full development pipeline shows all 6 nodes."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_full", "execution_started", ts, data={"task_input": "Full"})
        ts += 1
        for node_name in ["requirements", "design", "develop", "review", "test", "fix"]:
            log.log("thread_full", "node_started", ts, node_name=node_name)
            ts += 5
            log.log("thread_full", "node_completed", ts, node_name=node_name,
                    data={"output_summary": f"{node_name} done"})
            ts += 1
        log.log("thread_full", "execution_completed", ts, data={"total_cost": 1.50})

        r = client.get("/api/executions/thread_full/dag")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 6
        assert len(data["edges"]) >= 5

        # All nodes should be success
        statuses = [n["status"] for n in data["nodes"]]
        assert all(s == "success" for s in statuses)

    def test_dag_failed_node(self, client):
        """A failed node shows red status in DAG."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_fail", "execution_started", ts, data={"task_input": "Fail"})
        ts += 1
        log.log("thread_fail", "node_started", ts, node_name="requirements")
        ts += 5
        log.log("thread_fail", "node_completed", ts, node_name="requirements",
                data={"output_summary": "req done"})
        ts += 1
        log.log("thread_fail", "node_started", ts, node_name="design")
        ts += 3
        log.log("thread_fail", "node_failed", ts, node_name="design",
                data={"error": "Failed to generate design"})
        ts += 1
        log.log("thread_fail", "execution_completed", ts)

        r = client.get("/api/executions/thread_fail/dag")
        assert r.status_code == 200
        data = r.json()

        design_node = next(n for n in data["nodes"] if n["id"] == "design")
        assert design_node["status"] == "failed"

    def test_dag_nonexistent_execution(self, client):
        """Request for nonexistent execution returns 404."""
        r = client.get("/api/executions/nonexistent/dag")
        assert r.status_code == 404

    def test_dag_edges_structure(self, client):
        """Verify development workflow edge structure."""
        from src.api.server import get_event_log
        log = get_event_log()
        log.log("thread_edges", "execution_started", 1000.0, data={"task_input": "Test"})

        r = client.get("/api/executions/thread_edges/dag")
        assert r.status_code == 200
        data = r.json()

        # Check key edges exist
        edge_pairs = {(e["from_node"], e["to_node"]) for e in data["edges"]}
        assert ("requirements", "design") in edge_pairs
        assert ("design", "develop") in edge_pairs
        assert ("develop", "review") in edge_pairs
        assert ("develop", "test") in edge_pairs
        # review->fix and test->fix
        assert ("review", "fix") in edge_pairs
        assert ("test", "fix") in edge_pairs

    def test_dag_running_node(self, client):
        """A started but not completed node shows running status."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_run", "execution_started", ts, data={"task_input": "Running"})
        ts += 1
        log.log("thread_run", "node_started", ts, node_name="requirements")
        ts += 5
        log.log("thread_run", "node_completed", ts, node_name="requirements")
        ts += 1
        log.log("thread_run", "node_started", ts, node_name="design")
        # design is still running (no completed/failed event)

        r = client.get("/api/executions/thread_run/dag")
        assert r.status_code == 200
        data = r.json()

        req_node = next(n for n in data["nodes"] if n["id"] == "requirements")
        assert req_node["status"] == "success"

        design_node = next(n for n in data["nodes"] if n["id"] == "design")
        assert design_node["status"] == "running"

    def test_dag_node_with_token_usage(self, client):
        """Node with token usage shows correct token counts."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_tokens", "execution_started", ts, data={"task_input": "Tokens"})
        ts += 1
        log.log("thread_tokens", "node_started", ts, node_name="develop")
        ts += 10
        log.log("thread_tokens", "node_completed", ts, node_name="develop",
                data={"output_summary": "Code done", "token_usage": {"input": 500, "output": 1200}})

        r = client.get("/api/executions/thread_tokens/dag")
        assert r.status_code == 200
        data = r.json()

        node = data["nodes"][0]
        assert node["token_usage"]["input"] == 500
        assert node["token_usage"]["output"] == 1200
        assert node["duration_ms"] == 10000

    def test_dag_parallel_nodes(self, client):
        """Parallel nodes (review + test after develop) both appear correctly."""
        from src.api.server import get_event_log
        log = get_event_log()

        ts = 1000.0
        log.log("thread_parallel", "execution_started", ts, data={"task_input": "Parallel"})
        ts += 1
        for node in ["requirements", "design", "develop"]:
            log.log("thread_parallel", "node_started", ts, node_name=node)
            ts += 5
            log.log("thread_parallel", "node_completed", ts, node_name=node,
                    data={"output_summary": f"{node} done"})
            ts += 1
        # review and test run in parallel
        log.log("thread_parallel", "node_started", ts, node_name="review")
        log.log("thread_parallel", "node_started", ts, node_name="test")
        ts += 8
        log.log("thread_parallel", "node_completed", ts, node_name="review")
        ts += 2
        log.log("thread_parallel", "node_completed", ts, node_name="test")

        r = client.get("/api/executions/thread_parallel/dag")
        assert r.status_code == 200
        data = r.json()

        review = next(n for n in data["nodes"] if n["id"] == "review")
        test = next(n for n in data["nodes"] if n["id"] == "test")
        assert review["status"] == "success"
        assert test["status"] == "success"
