"""Tests for the Memory API routes (Phase 10 Self-Dev MVP)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.knowledge.memory import AgentMemory, MemoryEntry


@pytest.fixture
def temp_db():
    """Create a temporary database for memory tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def memory(temp_db):
    """Create an AgentMemory instance with test data."""
    mem = AgentMemory(db_path=temp_db)
    # Seed some test data
    mem.remember(MemoryEntry(
        key="test_key_1",
        value="test value one",
        category="test",
        project_id="test_project",
        tags=["tag1", "tag2"],
    ))
    mem.remember(MemoryEntry(
        key="test_key_2",
        value="test value two",
        category="test",
        project_id="test_project",
        tags=["tag3"],
    ))
    mem.remember(MemoryEntry(
        key="other_key",
        value="other value",
        category="other",
        project_id="other_project",
        tags=[],
    ))
    return mem


@pytest.fixture
def client(memory):
    """Create a FastAPI test client with injected memory."""
    from src.api.routes.memory import set_memory_instance
    set_memory_instance(memory)
    app = create_app(
        db_path=tempfile.mktemp(suffix=".db"),
        state_db_path=tempfile.mktemp(suffix=".db"),
    )
    with TestClient(app) as c:
        yield c
    # Clean up
    set_memory_instance(None)


# ── Search Tests ──

class TestMemorySearch:
    """Test POST /api/memory/search"""

    def test_search_empty_returns_empty_list(self, client):
        """Empty query on empty DB should return empty list."""
        # Use a clean DB
        from src.api.routes.memory import set_memory_instance
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        clean_mem = AgentMemory(db_path=path)
        set_memory_instance(clean_mem)
        try:
            resp = client.post("/api/memory/search", json={"query": ""})
            assert resp.status_code == 200
            data = resp.json()
            assert data["results"] == []
            assert data["total"] == 0
        finally:
            set_memory_instance(None)
            os.unlink(path)

    def test_search_returns_matching_results(self, client):
        """Query should return matching entries."""
        resp = client.post("/api/memory/search", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        keys = [r["key"] for r in data["results"]]
        assert "test_key_1" in keys
        assert "test_key_2" in keys

    def test_search_empty_query_returns_entries(self, client):
        """Empty query should return entries (not error)."""
        resp = client.post("/api/memory/search", json={"query": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["results"], list)

    def test_search_with_project_filter(self, client):
        """Project ID filter should work."""
        resp = client.post("/api/memory/search", json={
            "query": "",
            "project_id": "test_project",
        })
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["project_id"] == "test_project"

    def test_search_with_category_filter(self, client):
        """Category filter should work."""
        resp = client.post("/api/memory/search", json={
            "query": "",
            "category": "other",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for r in data["results"]:
            assert r["category"] == "other"

    def test_search_with_limit(self, client):
        """Limit should restrict result count."""
        resp = client.post("/api/memory/search", json={
            "query": "",
            "limit": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 1

    def test_search_response_format(self, client):
        """Response should have correct format."""
        resp = client.post("/api/memory/search", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)
        if data["results"]:
            entry = data["results"][0]
            assert "key" in entry
            assert "value" in entry
            assert "category" in entry
            assert "project_id" in entry
            assert "tags" in entry

    def test_search_no_match_returns_empty(self, client):
        """Non-matching query should return empty results."""
        resp = client.post("/api/memory/search", json={"query": "nonexistent_xyz"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0


# ── Stats Tests ──

class TestMemoryStats:
    """Test GET /api/memory/stats"""

    def test_stats_returns_total_and_by_category(self, client):
        """Stats should return total and breakdown."""
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_category" in data
        assert data["total"] >= 3

    def test_stats_with_project_filter(self, client):
        """Project filter should work for stats."""
        resp = client.get("/api/memory/stats?project_id=test_project")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    def test_stats_empty_db(self, client):
        """Stats on empty DB should return zero."""
        from src.api.routes.memory import set_memory_instance
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        clean_mem = AgentMemory(db_path=path)
        set_memory_instance(clean_mem)
        try:
            resp = client.get("/api/memory/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["by_category"] == {}
        finally:
            set_memory_instance(None)
            os.unlink(path)
