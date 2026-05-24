"""Tests for the Events Export API (Phase 10 Self-Dev real scenario)."""

import csv
import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.api.services.event_log import EventLog


@pytest.fixture
def elog():
    """Create EventLog with test data (file-based to share across threads)."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    elog = EventLog(db_path=db_path)
    # Thread 1: successful execution
    elog.log("thread_1", "execution_started", 1000.0)
    elog.log("thread_1", "node_started", 1001.0, node_name="planner")
    elog.log("thread_1", "node_completed", 1002.0, node_name="planner")
    elog.log("thread_1", "execution_completed", 1003.0)
    # Thread 2: failed execution
    elog.log("thread_2", "execution_started", 2000.0)
    elog.log("thread_2", "node_started", 2001.0, node_name="developer")
    elog.log("thread_2", "node_failed", 2002.0, node_name="developer")
    elog.close()
    yield elog
    os.unlink(db_path)


@pytest.fixture
def client(elog):
    """Create FastAPI test client and inject EventLog into execution_read."""
    from src.api.routes.execution_read import set_event_log as read_set_event_log
    from src.api.server import create_app

    tmpdir = tempfile.mkdtemp()
    app = create_app(
        db_path=os.path.join(tmpdir, "events.db"),
        state_db_path=os.path.join(tmpdir, "state.db"),
    )
    # Replace the EventLog with our test instance
    read_set_event_log(elog)
    with TestClient(app) as c:
        yield c


class TestEventsExportJSON:
    """Test GET /api/events/export with JSON format."""

    def test_export_all_events(self, client):
        resp = client.get("/api/events/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] == 7  # 4 + 3 events

    def test_export_with_thread_filter(self, client):
        resp = client.get("/api/events/export?thread_id=thread_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for e in data["events"]:
            assert e["thread_id"] == "thread_1"

    def test_export_nonexistent_thread(self, client):
        resp = client.get("/api/events/export?thread_id=no_such_thread")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total"] == 0

    def test_export_with_limit(self, client):
        resp = client.get("/api/events/export?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 2

    def test_export_descending_order(self, client):
        resp = client.get("/api/events/export")
        assert resp.status_code == 200
        data = resp.json()
        ts_list = [e["timestamp"] for e in data["events"]]
        assert ts_list == sorted(ts_list, reverse=True)

    def test_export_event_fields(self, client):
        resp = client.get("/api/events/export?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        e = data["events"][0]
        assert "id" in e
        assert "event_type" in e
        assert "timestamp" in e


class TestEventsExportCSV:
    """Test GET /api/events/export?format=csv."""

    def test_csv_content_type(self, client):
        resp = client.get("/api/events/export?format=csv&limit=1")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_csv_has_header(self, client):
        resp = client.get("/api/events/export?format=csv&limit=1")
        reader = csv.reader(io.StringIO(resp.text))
        header = next(reader)
        assert "id" in header
        assert "thread_id" in header
        assert "event_type" in header
        assert "timestamp" in header

    def test_csv_thread_filter(self, client):
        resp = client.get("/api/events/export?format=csv&thread_id=thread_1")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        # header + 4 events
        assert len(rows) == 5
        for row in rows[1:]:
            assert row[1] == "thread_1"

    def test_csv_empty_for_nonexistent(self, client):
        resp = client.get("/api/events/export?format=csv&thread_id=nope")
        assert resp.status_code == 200
        assert resp.text == ""


class TestEventsExportSince:
    """Test ?since parameter."""

    def test_since_filters_by_time(self, client):
        # Since 1500s should only get thread_2 events (2000+)
        resp = client.get("/api/events/export?since=2001-01-01T00:00:00")
        assert resp.status_code == 200
        data = resp.json()
        for e in data["events"]:
            assert e["timestamp"] >= 2000.0

    def test_since_invalid_returns_400(self, client):
        resp = client.get("/api/events/export?since=not-a-date")
        assert resp.status_code == 400
