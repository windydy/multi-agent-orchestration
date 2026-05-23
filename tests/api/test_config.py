"""Tests for the Phase 4 Config API endpoint."""

import pytest
import time
import json
from fastapi.testclient import TestClient

from src.api.server import create_app


VALID_WORKFLOW_YAML = """
name: development
description: Full development pipeline
nodes:
  - name: requirements
    agent: requirements_agent
  - name: design
    agent: design_agent
  - name: develop
    agent: develop_agent
edges:
  - from: requirements
    to: design
  - from: design
    to: develop
"""

INVALID_YAML_MISSING_NODES = """
name: test-workflow
description: Invalid workflow
edges:
  - from: a
    to: b
"""

INVALID_YAML_SYNTAX = """
name: test
description: test
  - invalid: yaml
    broken
"""


class TestWorkflowConfig:
    """Integration tests for workflow config CRUD."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db)
        with TestClient(app) as c:
            yield c

    def test_list_workflows_empty(self, client):
        """GET /api/config/workflows returns empty list when no configs exist."""
        r = client.get("/api/config/workflows")
        assert r.status_code == 200
        data = r.json()
        assert data["workflows"] == []

    def test_create_workflow(self, client):
        """PUT /api/config/workflows/{name} creates a new workflow."""
        r = client.put("/api/config/workflows/test-flow", json={
            "yaml_content": VALID_WORKFLOW_YAML,
            "description": "Test workflow",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "test-flow"

    def test_get_workflow(self, client):
        """GET /api/config/workflows/{name} returns YAML content."""
        # Create first
        client.put("/api/config/workflows/my-flow", json={
            "yaml_content": VALID_WORKFLOW_YAML,
        })

        r = client.get("/api/config/workflows/my-flow")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "my-flow"
        assert "requirements" in data["yaml_content"]

    def test_get_nonexistent_workflow(self, client):
        """GET nonexistent workflow returns 404."""
        r = client.get("/api/config/workflows/nonexistent")
        assert r.status_code == 404

    def test_update_workflow(self, client):
        """PUT updates existing workflow YAML."""
        client.put("/api/config/workflows/update-flow", json={
            "yaml_content": VALID_WORKFLOW_YAML,
        })

        r = client.put("/api/config/workflows/update-flow", json={
            "yaml_content": "name: updated\nnodes: []\nedges: []",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["yaml_content"].startswith("name: updated")

    def test_reject_invalid_yaml_syntax(self, client):
        """PUT with invalid YAML syntax returns 422."""
        r = client.put("/api/config/workflows/bad-yaml", json={
            "yaml_content": INVALID_YAML_SYNTAX,
        })
        assert r.status_code == 422

    def test_reject_missing_nodes(self, client):
        """PUT with YAML missing required 'nodes' field returns 422."""
        r = client.put("/api/config/workflows/bad-nodes", json={
            "yaml_content": INVALID_YAML_MISSING_NODES,
        })
        assert r.status_code == 422

    def test_list_workflows_after_create(self, client):
        """List shows all created workflows."""
        client.put("/api/config/workflows/flow-a", json={"yaml_content": VALID_WORKFLOW_YAML})
        client.put("/api/config/workflows/flow-b", json={"yaml_content": VALID_WORKFLOW_YAML})

        r = client.get("/api/config/workflows")
        assert r.status_code == 200
        data = r.json()
        names = [w["name"] for w in data["workflows"]]
        assert "flow-a" in names
        assert "flow-b" in names

    def test_delete_workflow(self, client):
        """DELETE removes a workflow."""
        client.put("/api/config/workflows/to-delete", json={"yaml_content": VALID_WORKFLOW_YAML})
        r = client.delete("/api/config/workflows/to-delete")
        assert r.status_code == 200

        r = client.get("/api/config/workflows/to-delete")
        assert r.status_code == 404

    def test_delete_nonexistent_workflow(self, client):
        """DELETE nonexistent workflow returns 404."""
        r = client.delete("/api/config/workflows/nonexistent")
        assert r.status_code == 404

    def test_reject_edge_refs_unknown_node(self, client):
        """PUT with edge referencing unknown node returns 422."""
        r = client.put("/api/config/workflows/bad-edge", json={
            "yaml_content": "name: test\nnodes:\n  - name: a\nedges:\n  - from: a\n    to: b",
        })
        assert r.status_code == 422
        assert "unknown node" in r.json()["detail"].lower()

    def test_reject_self_loop_edge(self, client):
        """PUT with self-loop edge returns 422."""
        r = client.put("/api/config/workflows/self-loop", json={
            "yaml_content": "name: test\nnodes:\n  - name: a\nedges:\n  - from: a\n    to: a",
        })
        assert r.status_code == 422
        assert "self-loop" in r.json()["detail"].lower()

    def test_reject_duplicate_node_names(self, client):
        """PUT with duplicate node names returns 422."""
        r = client.put("/api/config/workflows/dup-nodes", json={
            "yaml_content": "name: test\nnodes:\n  - name: a\n  - name: a\nedges: []",
        })
        assert r.status_code == 422


class TestAgentConfig:
    """Integration tests for Agent config management."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db)
        with TestClient(app) as c:
            yield c

    def test_list_agents(self, client):
        """GET /api/config/agents returns registered agents."""
        r = client.get("/api/config/agents")
        assert r.status_code == 200
        data = r.json()
        assert len(data["agents"]) > 0

    def test_get_agent(self, client):
        """GET /api/config/agents/{id} returns agent details."""
        r = client.get("/api/config/agents")
        agents = r.json()["agents"]
        assert len(agents) > 0
        agent_id = agents[0]["id"]

        r = client.get(f"/api/config/agents/{agent_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == agent_id

    def test_get_nonexistent_agent(self, client):
        """GET nonexistent agent returns 404."""
        r = client.get("/api/config/agents/nonexistent")
        assert r.status_code == 404

    def test_update_agent_model(self, client):
        """PUT updates agent model configuration."""
        r = client.get("/api/config/agents")
        agent_id = r.json()["agents"][0]["id"]

        r = client.put(f"/api/config/agents/{agent_id}", json={
            "model": "gpt-4o",
            "enabled": False,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["model"] == "gpt-4o"
        assert data["enabled"] is False

    def test_toggle_agent_enabled(self, client):
        """Enable/disable agent."""
        r = client.get("/api/config/agents")
        agent_id = r.json()["agents"][0]["id"]

        # Disable
        r = client.put(f"/api/config/agents/{agent_id}", json={"enabled": False})
        assert r.json()["enabled"] is False

        # Re-enable
        r = client.put(f"/api/config/agents/{agent_id}", json={"enabled": True})
        assert r.json()["enabled"] is True


class TestVerifierRules:
    """Integration tests for Verifier rule CRUD."""

    @pytest.fixture
    def client(self, tmp_path):
        db_path = str(tmp_path / "events.db")
        state_db = str(tmp_path / "execution_state.db")
        config_db = str(tmp_path / "config.db")
        app = create_app(db_path=db_path, state_db_path=state_db, config_db_path=config_db)
        with TestClient(app) as c:
            yield c

    def test_list_verifiers_empty(self, client):
        """GET /api/config/verifiers returns empty list initially."""
        r = client.get("/api/config/verifiers")
        assert r.status_code == 200
        data = r.json()
        assert data["rules"] == []

    def test_create_verifier(self, client):
        """POST creates a new verifier rule."""
        r = client.post("/api/config/verifiers", json={
            "name": "Token Limit",
            "condition": "token_limit",
            "threshold": 10000,
            "action": "warn",
            "severity": "medium",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Token Limit"
        assert data["condition"] == "token_limit"
        assert data["threshold"] == 10000
        assert data["enabled"] is True

    def test_list_verifiers_after_create(self, client):
        """List shows created rules."""
        client.post("/api/config/verifiers", json={
            "name": "Rule A", "condition": "cost_threshold",
            "threshold": 5.0, "action": "fail", "severity": "high",
        })
        client.post("/api/config/verifiers", json={
            "name": "Rule B", "condition": "node_timeout",
            "threshold": 300, "action": "retry", "severity": "low",
        })

        r = client.get("/api/config/verifiers")
        assert r.status_code == 200
        assert len(r.json()["rules"]) == 2

    def test_update_verifier(self, client):
        """PUT updates an existing rule."""
        r = client.post("/api/config/verifiers", json={
            "name": "Update Me", "condition": "token_limit",
            "threshold": 5000, "action": "warn", "severity": "medium",
        })
        rule_id = r.json()["id"]

        r = client.put(f"/api/config/verifiers/{rule_id}", json={
            "threshold": 20000,
            "enabled": False,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["threshold"] == 20000
        assert data["enabled"] is False

    def test_delete_verifier(self, client):
        """DELETE removes a rule."""
        r = client.post("/api/config/verifiers", json={
            "name": "Delete Me", "condition": "token_limit",
            "threshold": 1000, "action": "warn", "severity": "low",
        })
        rule_id = r.json()["id"]

        r = client.delete(f"/api/config/verifiers/{rule_id}")
        assert r.status_code == 200

        r = client.get("/api/config/verifiers")
        assert len(r.json()["rules"]) == 0

    def test_delete_nonexistent_verifier(self, client):
        """DELETE nonexistent rule returns 404."""
        r = client.delete("/api/config/verifiers/nonexistent")
        assert r.status_code == 404
