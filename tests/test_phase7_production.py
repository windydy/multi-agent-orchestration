"""
Phase 7 TDD: MetricsCollector + Tracer + CostController + CircuitBreaker + RetryPolicy

严格遵循 TDD
"""

import pytest
import time
import asyncio
from collections import deque
from src.observability.metrics import MetricsCollector, MetricPoint
from src.observability.tracing import Tracer, Span, SpanStatus
from src.cost.controller import CostController, CostBudget, CostStatus
from src.resilience.circuit_breaker import CircuitBreaker, CircuitState
from src.resilience.retry_policy import RetryPolicy


# ============================================================
# TDD: MetricsCollector
# ============================================================

class TestMetricsCollector:
    """MetricsCollector"""

    def test_create_collector(self):
        mc = MetricsCollector()
        assert mc is not None

    def test_increment_counter(self):
        mc = MetricsCollector()
        mc.increment("test_counter")
        assert mc._counters["test_counter"] == 1.0

    def test_increment_with_value(self):
        mc = MetricsCollector()
        mc.increment("test_counter", value=5.0)
        assert mc._counters["test_counter"] == 5.0

    def test_set_gauge(self):
        mc = MetricsCollector()
        mc.set_gauge("cpu_usage", 75.5)
        assert mc._gauges["cpu_usage"] == 75.5

    def test_observe_histogram(self):
        mc = MetricsCollector()
        mc.observe("latency", 0.5)
        mc.observe("latency", 1.2)
        assert mc._histograms["latency"] == [0.5, 1.2]

    def test_record_execution(self):
        mc = MetricsCollector()
        mc.record_execution("agent-1", duration=1.5, success=True, cost=0.01)
        assert mc._counters.get("agent_executions_total", 0) > 0

    def test_export_prometheus(self):
        mc = MetricsCollector()
        mc.increment("test", 1.0)
        output = mc.export_prometheus()
        assert isinstance(output, str)
        assert "test" in output

    def test_reset(self):
        mc = MetricsCollector()
        mc.increment("test", 1.0)
        mc.set_gauge("g", 1.0)
        mc.observe("h", 1.0)
        asyncio.get_event_loop().run_until_complete(mc.reset())
        assert mc._counters == {}
        assert mc._gauges == {}
        assert mc._histograms == {}


# ============================================================
# TDD: Tracer
# ============================================================

class TestTracer:
    """Tracer"""

    def test_create_tracer(self):
        tracer = Tracer()
        assert tracer is not None

    def test_start_span(self):
        tracer = Tracer()
        span = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("test-operation")
        )
        assert span.name == "test-operation"
        assert span.trace_id is not None
        assert span.span_id is not None

    def test_end_span(self):
        tracer = Tracer()
        span = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("test")
        )
        time.sleep(0.01)
        tracer.end_span(span, status=SpanStatus.OK)
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms > 0

    def test_span_with_parent(self):
        tracer = Tracer()
        parent = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("parent")
        )
        child = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("child", parent=parent)
        )
        assert child.parent_id == parent.span_id
        assert child.trace_id == parent.trace_id

    def test_get_trace(self):
        tracer = Tracer()
        parent = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("root")
        )
        asyncio.get_event_loop().run_until_complete(
            tracer.start_span("child", parent=parent)
        )
        spans = asyncio.get_event_loop().run_until_complete(
            tracer.get_trace(parent.trace_id)
        )
        assert len(spans) == 2

    def test_span_to_dict(self):
        tracer = Tracer()
        span = asyncio.get_event_loop().run_until_complete(
            tracer.start_span("test")
        )
        d = span.to_dict()
        assert d["name"] == "test"
        assert "trace_id" in d


# ============================================================
# TDD: CostController
# ============================================================

class TestCostController:
    """CostController"""

    def test_create_controller(self):
        cc = CostController()
        assert cc is not None
        assert cc.budget.warning_threshold == 5.0

    def test_record_cost(self):
        cc = CostController()
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 0.5, 100, 200)
        )
        assert cc._running_total == 0.5
        assert cc._agent_totals["agent-1"] == 0.5

    def test_cost_status_ok(self):
        cc = CostController()
        status = asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 1.0, 100, 200)
        )
        assert cc._status == CostStatus.OK

    def test_cost_status_warning(self):
        budget = CostBudget(warning_threshold=1.0, limit_threshold=5.0, stop_threshold=10.0)
        cc = CostController(budget=budget)
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 1.5, 100, 200)
        )
        assert cc._status == CostStatus.WARNING

    def test_cost_status_limit(self):
        budget = CostBudget(warning_threshold=1.0, limit_threshold=2.0, stop_threshold=5.0)
        cc = CostController(budget=budget)
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 3.0, 100, 200)
        )
        assert cc._status == CostStatus.LIMIT

    def test_cost_status_stop(self):
        budget = CostBudget(warning_threshold=1.0, limit_threshold=2.0, stop_threshold=3.0)
        cc = CostController(budget=budget)
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 5.0, 100, 200)
        )
        assert cc._status == CostStatus.STOP

    def test_should_stop(self):
        budget = CostBudget(warning_threshold=1.0, limit_threshold=2.0, stop_threshold=3.0)
        cc = CostController(budget=budget)
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 5.0, 100, 200)
        )
        assert cc.should_stop() is True

    def test_should_stop_false(self):
        cc = CostController()
        asyncio.get_event_loop().run_until_complete(
            cc.record_cost("agent-1", "task-1", 1.0, 100, 200)
        )
        assert cc.should_stop() is False


# ============================================================
# TDD: CircuitBreaker
# ============================================================

class TestCircuitBreaker:
    """CircuitBreaker"""

    def test_create_breaker(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=30)
        assert cb.state == CircuitState.CLOSED

    def test_call_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=30)
        def success_fn():
            return "ok"
        result = cb.call(success_fn)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_call_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=30)
        def failing_fn():
            raise ValueError("fail")
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_call(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=30)
        def failing_fn():
            raise ValueError("fail")
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        with pytest.raises(Exception, match="OPEN"):
            cb.call(lambda: "ok")

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        def failing_fn():
            raise ValueError("fail")
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_reset(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=30)
        def failing_fn():
            raise ValueError("fail")
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        def failing_fn():
            raise ValueError("fail")
        def success_fn():
            return "ok"
        with pytest.raises(ValueError):
            cb.call(failing_fn)
        time.sleep(0.02)
        result = cb.call(success_fn)
        assert cb.state == CircuitState.CLOSED
        assert result == "ok"


# ============================================================
# TDD: RetryPolicy
# ============================================================

class TestRetryPolicy:
    """RetryPolicy"""

    def test_create_policy(self):
        rp = RetryPolicy(max_retries=3, base_delay=1.0)
        assert rp.max_retries == 3

    def test_retry_on_failure(self):
        attempts = 0
        def flaky_fn():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("transient error")
            return "success"
        rp = RetryPolicy(max_retries=3, base_delay=0.01, jitter=False)
        result = rp.call(flaky_fn)
        assert result == "success"
        assert attempts == 3

    def test_no_retry_on_success(self):
        calls = 0
        def success_fn():
            nonlocal calls
            calls += 1
            return "ok"
        rp = RetryPolicy(max_retries=3, base_delay=0.01)
        result = rp.call(success_fn)
        assert result == "ok"
        assert calls == 1

    def test_retry_exhausted_raises(self):
        def always_fail():
            raise RuntimeError("permanent error")
        rp = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)
        with pytest.raises(RuntimeError):
            rp.call(always_fail)

    def test_calculate_delay(self):
        rp = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=False)
        assert rp._calculate_delay(0) == 1.0
        assert rp._calculate_delay(1) == 2.0
        assert rp._calculate_delay(2) == 4.0
