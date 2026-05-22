"""Tests for EventLog service."""

import json
import os
import time

import pytest

from src.api.services.event_log import EventLog


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path for each test."""
    db_file = str(tmp_path / "events.db")
    return db_file


@pytest.fixture
def event_log(tmp_db):
    """Provide a fresh EventLog instance."""
    return EventLog(db_path=tmp_db)


class TestInit:
    def test_creates_database_file(self, tmp_db):
        event_log = EventLog(db_path=tmp_db)
        assert os.path.exists(tmp_db)

    def test_creates_table(self, tmp_db):
        event_log = EventLog(db_path=tmp_db)
        # Should not raise - table exists
        event_log._conn.execute("SELECT * FROM execution_events LIMIT 0")


class TestLog:
    def test_log_execution_started(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="execution_started",
            node_name=None,
            timestamp=time.time(),
            data={"prompt": "build a web app"},
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1
        assert rows[0][1] == "t1"
        assert rows[0][2] == "execution_started"

    def test_log_node_started(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="node_started",
            node_name="requirements",
            timestamp=time.time(),
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1
        assert rows[0][3] == "requirements"

    def test_log_node_completed(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="node_completed",
            node_name="design",
            timestamp=time.time(),
            data={"output": "design doc"},
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1

    def test_log_node_failed(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="node_failed",
            node_name="develop",
            timestamp=time.time(),
            data={"error": "syntax error"},
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1

    def test_log_execution_completed(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="execution_completed",
            timestamp=time.time(),
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1

    def test_log_interrupted(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="interrupted",
            timestamp=time.time(),
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 1

    def test_data_stored_as_json(self, event_log):
        event_log.log(
            thread_id="t1",
            event_type="execution_started",
            timestamp=time.time(),
            data={"key": "value", "nested": {"a": 1}},
        )
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert rows[0][5] == '{"key": "value", "nested": {"a": 1}}'

    def test_log_multiple_events(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=1.0)
        event_log.log(thread_id="t1", event_type="node_started", node_name="req", timestamp=2.0)
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=3.0)
        rows = list(event_log._conn.execute("SELECT * FROM execution_events"))
        assert len(rows) == 3


class TestGetExecution:
    def test_get_execution_aggregates_events(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t1", event_type="node_started", node_name="requirements", timestamp=ts + 1)
        event_log.log(thread_id="t1", event_type="node_completed", node_name="requirements", timestamp=ts + 2)
        event_log.log(thread_id="t1", event_type="execution_completed", timestamp=ts + 3)

        result = event_log.get_execution("t1")
        assert result["thread_id"] == "t1"
        assert len(result["events"]) == 4
        assert "status" in result

    def test_get_execution_nonexistent(self, event_log):
        result = event_log.get_execution("nonexistent")
        assert result is None

    def test_get_execution_events_ordered_by_timestamp(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=3.0)
        event_log.log(thread_id="t1", event_type="node_started", node_name="dev", timestamp=1.0)
        event_log.log(thread_id="t1", event_type="node_completed", node_name="dev", timestamp=2.0)

        result = event_log.get_execution("t1")
        timestamps = [e["timestamp"] for e in result["events"]]
        assert timestamps == sorted(timestamps)


class TestListExecutions:
    def test_list_executions_empty(self, event_log):
        result = event_log.list_executions()
        assert result == []

    def test_list_executions_single(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=time.time())
        result = event_log.list_executions()
        assert len(result) == 1
        assert result[0]["thread_id"] == "t1"
        assert "event_count" in result[0]
        assert "status" in result[0]
        assert "latest_event_time" in result[0]

    def test_list_executions_multiple_threads(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=1.0)
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=2.0)
        event_log.log(thread_id="t3", event_type="execution_started", timestamp=3.0)

        result = event_log.list_executions()
        assert len(result) == 3

    def test_list_executions_descending_order(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=1.0)
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=2.0)
        event_log.log(thread_id="t3", event_type="execution_started", timestamp=3.0)

        result = event_log.list_executions()
        assert result[0]["thread_id"] == "t3"
        assert result[1]["thread_id"] == "t2"
        assert result[2]["thread_id"] == "t1"

    def test_list_executions_pagination(self, event_log):
        for i in range(5):
            event_log.log(thread_id=f"t{i}", event_type="execution_started", timestamp=float(i))

        result_page1 = event_log.list_executions(limit=2, offset=0)
        assert len(result_page1) == 2
        assert result_page1[0]["thread_id"] == "t4"

        result_page2 = event_log.list_executions(limit=2, offset=2)
        assert len(result_page2) == 2
        assert result_page2[0]["thread_id"] == "t2"

    def test_list_executions_counts_events_per_thread(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=1.0)
        event_log.log(thread_id="t1", event_type="node_started", node_name="req", timestamp=2.0)
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=3.0)

        result = event_log.list_executions()
        t1_entry = [e for e in result if e["thread_id"] == "t1"][0]
        t2_entry = [e for e in result if e["thread_id"] == "t2"][0]
        assert t1_entry["event_count"] == 2
        assert t2_entry["event_count"] == 1


class TestGetOverview:
    def test_get_overview_empty(self, event_log):
        result = event_log.get_overview()
        assert result["total_executions"] == 0
        assert result["total_events"] == 0

    def test_get_overview_counts(self, event_log):
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=1.0)
        event_log.log(thread_id="t1", event_type="node_started", node_name="req", timestamp=2.0)
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=3.0)

        result = event_log.get_overview()
        assert result["total_executions"] == 2
        assert result["total_events"] == 3

    def test_get_overview_status_breakdown(self, event_log):
        # Success execution
        ts = time.time()
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t1", event_type="node_started", node_name="req", timestamp=ts + 1)
        event_log.log(thread_id="t1", event_type="node_completed", node_name="req", timestamp=ts + 2)
        event_log.log(thread_id="t1", event_type="execution_completed", timestamp=ts + 3)

        # Failed execution
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t2", event_type="node_started", node_name="dev", timestamp=ts + 1)
        event_log.log(thread_id="t2", event_type="node_failed", node_name="dev", timestamp=ts + 2)

        result = event_log.get_overview()
        assert result["status_breakdown"]["success"] == 1
        assert result["status_breakdown"]["failed"] == 1


class TestStatusInference:
    def test_status_success(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t1", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t1", event_type="node_started", node_name="req", timestamp=ts + 1)
        event_log.log(thread_id="t1", event_type="node_completed", node_name="req", timestamp=ts + 2)
        event_log.log(thread_id="t1", event_type="execution_completed", timestamp=ts + 3)

        result = event_log.get_execution("t1")
        assert result["status"] == "success"

    def test_status_failed(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t2", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t2", event_type="node_started", node_name="dev", timestamp=ts + 1)
        event_log.log(thread_id="t2", event_type="node_failed", node_name="dev", timestamp=ts + 2)

        result = event_log.get_execution("t2")
        assert result["status"] == "failed"

    def test_status_running(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t3", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t3", event_type="node_started", node_name="design", timestamp=ts + 1)

        result = event_log.get_execution("t3")
        assert result["status"] == "running"

    def test_status_running_no_node_completed(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t4", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t4", event_type="node_started", node_name="req", timestamp=ts + 1)
        event_log.log(thread_id="t4", event_type="node_started", node_name="design", timestamp=ts + 2)

        result = event_log.get_execution("t4")
        assert result["status"] == "running"

    def test_status_interrupted(self, event_log):
        ts = time.time()
        event_log.log(thread_id="t5", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="t5", event_type="interrupted", timestamp=ts + 1)

        result = event_log.get_execution("t5")
        assert result["status"] == "interrupted"

    def test_status_in_list_executions(self, event_log):
        ts = time.time()
        event_log.log(thread_id="success", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="success", event_type="execution_completed", timestamp=ts + 1)

        event_log.log(thread_id="running", event_type="execution_started", timestamp=ts)
        event_log.log(thread_id="running", event_type="node_started", node_name="x", timestamp=ts + 1)

        result = event_log.list_executions()
        status_map = {e["thread_id"]: e["status"] for e in result}
        assert status_map["success"] == "success"
        assert status_map["running"] == "running"


class TestFullWorkflow:
    def test_complete_execution_flow(self, event_log):
        """Simulate a full pipeline execution."""
        ts = time.time()
        thread_id = "pipeline-001"

        # Start
        event_log.log(
            thread_id=thread_id,
            event_type="execution_started",
            timestamp=ts,
            data={"prompt": "Build a REST API"},
        )

        # Nodes run sequentially
        nodes = ["requirements", "design", "develop", "review", "test", "fix"]
        current_ts = ts + 1
        for node in nodes:
            event_log.log(
                thread_id=thread_id,
                event_type="node_started",
                node_name=node,
                timestamp=current_ts,
            )
            current_ts += 1
            event_log.log(
                thread_id=thread_id,
                event_type="node_completed",
                node_name=node,
                timestamp=current_ts,
                data={"status": "ok"},
            )
            current_ts += 1

        # Complete
        event_log.log(
            thread_id=thread_id,
            event_type="execution_completed",
            timestamp=current_ts,
            data={"duration": current_ts - ts},
        )

        # Verify get_execution
        execution = event_log.get_execution(thread_id)
        assert execution["thread_id"] == thread_id
        assert execution["status"] == "success"
        assert len(execution["events"]) == 1 + len(nodes) * 2 + 1  # start + 2 per node + complete

        # Verify list_executions
        executions = event_log.list_executions()
        assert len(executions) == 1
        assert executions[0]["status"] == "success"
        assert executions[0]["event_count"] == 14

        # Verify overview
        overview = event_log.get_overview()
        assert overview["total_executions"] == 1
        assert overview["total_events"] == 14
        assert overview["status_breakdown"]["success"] == 1
