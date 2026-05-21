# Phase 7: 生产级能力 - 详细技术设计

> 版本: 1.0
> 日期: 2026-05-20
> 状态: 设计稿

## 一、概述

### 1.1 目标

为系统添加生产部署必需的监控、日志、告警、成本控制、熔断等能力，使系统可从实验环境升级到生产环境。

### 1.2 生产需求清单

| 需求 | 重要性 | 说明 |
|------|--------|------|
| 可观测性 | P0 | Metrics + Tracing + 结构化日志 |
| 成本控制 | P0 | 实时追踪、预算熔断 |
| 弹性恢复 | P0 | Circuit Breaker + Retry Policy |
| 告警通知 | P1 | 异常自动告警 |
| 健康检查 | P1 | 系统状态探测 |
| API Server | P2 | 外部集成接口 |

---

## 二、可观测性设计

### 2.1 Metrics 架构

```
┌─────────────────────────────────────────────────────┐
│                    MetricsCollector                  │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Execution    │  │   Token      │  │  Cost     │  │
│  │  Metrics      │  │   Metrics    │  │  Metrics  │  │
│  └──────────────┘  └──────────────┘  └───────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Success     │  │   Agent      │  │  Latency  │  │
│  │  Rate        │  │   Load       │  │  Metrics  │  │
│  └──────────────┘  └──────────────┘  └───────────┘  │
│                                                      │
│  Storage: 内存环形缓冲区（最近1000条）                  │
│  Export:   Prometheus 文本格式                         │
└─────────────────────────────────────────────────────┘
```

### 2.2 src/observability/metrics.py

```python
import time
import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    labels: dict = field(default_factory=dict)


class MetricsCollector:
    """指标收集器（异步安全）"""
    
    def __init__(self, max_points: int = 10000):
        self._points: deque = deque(maxlen=max_points)
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
    
    # --- Counter (累加计数器) ---
    async def increment(self, name: str, value: float = 1.0, labels: dict = None):
        async with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- Gauge (瞬时值) ---
    async def set_gauge(self, name: str, value: float, labels: dict = None):
        async with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- Histogram (分布) ---
    async def observe(self, name: str, value: float, labels: dict = None):
        async with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- 快捷方法 ---
    def record_execution(self, agent: str, duration: float, success: bool, cost: float):
        """记录一次 Agent 执行"""
        self.increment("agent_executions_total", labels={"agent": agent, "success": str(success)})
        self.observe("agent_duration_seconds", duration, {"agent": agent})
        self.increment("agent_cost_total", cost, {"agent": agent})
        self.increment("agent_tokens_total", labels={"agent": agent})
    
    def record_token_usage(self, agent: str, input_tokens: int, output_tokens: int):
        """记录 Token 使用"""
        self.increment("tokens_input_total", input_tokens, {"agent": agent})
        self.increment("tokens_output_total", output_tokens, {"agent": agent})
    
    # --- Prometheus 导出 ---
    def export_prometheus(self) -> str:
        """导出 Prometheus 文本格式"""
        lines = []
        
        # Counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        # Gauges
        for key, value in self._gauges.items():
            name = key.split("{")[0] if "{" in key else key
            lines.append(f"# TYPE {name} gauge")
            if "{" in key:
                lines.append(f"{key} {value}")
            else:
                lines.append(f"{name} {value}")
        
        # Histograms
        for name, values in self._histograms.items():
            lines.append(f"# TYPE {name} histogram")
            count = len(values)
            total = sum(values)
            lines.append(f"{name}_count {count}")
            lines.append(f"{name}_sum {total:.6f}")
            
            # Bucket
            buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf")]
            cumulative = 0
            for bucket in buckets:
                cumulative += sum(1 for v in values if v <= bucket)
                lines.append(f"{name}_bucket{{le="{bucket}"}} {cumulative}")
            lines.append(f"{name}_bucket{{le="+Inf"}} {count}")
        
        lines.append("")
        return "\n".join(lines)
    
    def _record_point(self, point: MetricPoint):
        self._points.append(point)
    
    @staticmethod
    def _make_key(name: str, labels: dict) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    async def reset(self):
        """重置所有指标"""
        async with self._lock:
            self._points.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
```

### 2.3 Tracing 架构

### src/observability/tracing.py

```python
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    def end(self, status: SpanStatus = SpanStatus.OK, error: str = None):
        self.end_time = time.time()
        self.status = status
        if error:
            self.error = error
    
    def add_event(self, name: str, attributes: dict = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })
    
    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


class Tracer:
    """分布式追踪器（兼容 OpenTelemetry 概念）"""
    
    def __init__(self, max_spans: int = 10000):
        self._spans: dict[str, Span] = {}
        self._active_spans: dict[str, str] = {}  # span_id → parent_id
        self._lock = asyncio.Lock()
        self._max_spans = max_spans
        self._exporter = None
    
    async def start_span(self, name: str, parent: Optional["Span"] = None, 
                   attributes: dict = None) -> Span:
        span = Span(
            trace_id=parent.trace_id if parent else uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16],
            parent_id=parent.span_id if parent else None,
            name=name,
            start_time=time.time(),
            attributes=attributes or {},
        )
        
        async with self._lock:
            self._spans[span.span_id] = span
            if len(self._spans) > self._max_spans:
                self._evict_oldest()
        
        return span
    
    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK, error: str = None):
        span.end(status, error)
        if self._exporter:
            self._exporter.export(span.to_dict())
    
    async def get_trace(self, trace_id: str) -> list[Span]:
        async with self._lock:
            return [s for s in self._spans.values() if s.trace_id == trace_id]
    
    def _evict_oldest(self):
        oldest = min(self._spans.values(), key=lambda s: s.start_time)
        del self._spans[oldest.span_id]


import asyncio
```

---

## 三、成本控制设计

### 3.1 src/cost/controller.py

```python
import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CostStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class CostBudget:
    """成本预算"""
    warning_threshold: float = 5.0    # 警告阈值
    limit_threshold: float = 10.0     # 限制阈值
    stop_threshold: float = 20.0      # 停止阈值
    per_agent_budget: Optional[float] = None  # 单Agent预算
    per_task_budget: Optional[float] = None   # 单任务预算


@dataclass
class CostRecord:
    timestamp: float
    agent: str
    task_id: str
    cost: float
    input_tokens: int
    output_tokens: int


class CostController:
    """成本控制器"""
    
    def __init__(self, budget: CostBudget = None, metrics: "MetricsCollector" = None):
        self.budget = budget or CostBudget()
        self.metrics = metrics
        self._records: list[CostRecord] = []
        self._running_total: float = 0.0
        self._agent_totals: dict[str, float] = {}
        self._task_totals: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._status = CostStatus.OK
        self._callbacks: list = []
    
    async def record_cost(self, agent: str, task_id: str, cost: float, 
                    input_tokens: int, output_tokens: int):
        """记录成本"""
        async with self._lock:
            record = CostRecord(
                timestamp=time.time(),
                agent=agent,
                task_id=task_id,
                cost=cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self._records.append(record)
            self._running_total += cost
            self._agent_totals[agent] = self._agent_totals.get(agent, 0) + cost
            self._task_totals[task_id] = self._task_totals.get(task_id, 0) + cost
            
            # 更新指标
            if self.metrics:
                self.metrics.record_token_usage(agent, input_tokens, output_tokens)
            
            # 检查状态
            new_status = self._check_status()
            if new_status != self._status:
                self._status = new_status
                self._notify_status_change(new_status)
    
    def check(self) -> CostStatus:
        """检查当前状态"""
        return self._status
    
    def should_stop(self) -> bool:
        """是否应该停止"""
        return self._status == CostStatus.STOP
    
    def get_total_cost(self) -> float:
        """获取总成本"""
        return self._running_total
    
    def get_agent_cost(self, agent: str) -> float:
        """获取Agent成本"""
        return self._agent_totals.get(agent, 0.0)
    
    def get_task_cost(self, task_id: str) -> float:
        """获取任务成本"""
        return self._task_totals.get(task_id, 0.0)
    
    def get_records(self, task_id: str = None, agent: str = None) -> list[CostRecord]:
        """获取成本记录"""
        records = self._records
        if task_id:
            records = [r for r in records if r.task_id == task_id]
        if agent:
            records = [r for r in records if r.agent == agent]
        return records
    
    def register_callback(self, callback):
        """注册状态变化回调"""
        self._callbacks.append(callback)
    
    def _check_status(self) -> CostStatus:
        if self._running_total >= self.budget.stop_threshold:
            return CostStatus.STOP
        elif self._running_total >= self.budget.limit_threshold:
            return CostStatus.LIMIT
        elif self._running_total >= self.budget.warning_threshold:
            return CostStatus.WARNING
        return CostStatus.OK
    
    def _notify_status_change(self, status: CostStatus):
        for cb in self._callbacks:
            try:
                cb(status, self._running_total)
            except Exception:
                pass
    
    def estimate_cost(self, input_tokens: int, output_tokens: int, 
                      model: str = "qwen3.6-plus") -> float:
        """预估成本
        
        基于模型定价:
        - qwen3.6-plus: $3/M input, $12/M output
        """
        pricing = {
            "qwen3.6-plus": (3.0, 12.0),  # per million tokens
            "qwen3.5-plus": (2.0, 8.0),
        }
        input_price, output_price = pricing.get(model, (3.0, 12.0))
        return (input_tokens / 1_000_000 * input_price + 
                output_tokens / 1_000_000 * output_price)
```

---

## 四、弹性设计

### 4.1 Circuit Breaker 状态机

```
                  连续失败 N 次
    ┌─────────┐ ──────────────▶ ┌─────────┐
    │  CLOSED │                 │  OPEN   │
    │ (正常)  │                 │ (熔断)  │
    └────┬────┘ ◀────────────── └────┬────┘
         │          成功                 │
         │                          等待期结束
         │                          (half-open)
         ▼                              ▼
    ┌─────────┐                 ┌─────────┐
    │ HALF    │ ── 失败 ──────▶ │  OPEN   │
    │ OPEN    │                 │(重置计时)│
    │ (试探)  │                 └─────────┘
    └────┬────┘
         │ 成功
         ▼
    ┌─────────┐
    │ CLOSED  │
    └─────────┘
```

### 4.2 src/resilience/circuit_breaker.py

```python
import time
import asyncio
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断
    HALF_OPEN = "half_open" # 试探


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()
    
    def call(self, func, *args, **kwargs):
        """执行受保护的调用"""
        state = self._get_state()
        
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Failures: {self._failure_count}"
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    async def acall(self, func, *args, **kwargs):
        """异步版本"""
        state = self._get_state()
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _get_state(self) -> CircuitState:
        """获取熔断器状态（纯同步，无需锁）"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state
    
    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
            self._failure_count = 0
    
    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    @property
    def state(self) -> CircuitState:
        return self._get_state()
    
    def reset(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
```

> **注意**: CircuitBreaker 的 `_get_state()` 改为无锁（纯读取+状态机转换），
> 因为 CircuitBreaker 的状态转换频率远低于 MetricsCollector，且 `with self._lock`
> 在同步方法中保持 threading.Lock 是合理的（CircuitBreaker 不进入 async 路径）。
> MetricsCollector/Tracer/CostController 等高频组件已改为 asyncio.Lock + async def。

### 4.3 src/resilience/retry_policy.py

```python
import time
import random
from typing import Callable, Optional


class RetryPolicy:
    """重试策略"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def execute(self, func: Callable, *args, **kwargs):
        """执行带重试的调用"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt >= self.max_retries:
                    break
                
                delay = self._calculate_delay(attempt)
                time.sleep(delay)
        
        raise last_exception
    
    async def aexecute(self, func, *args, **kwargs):
        """异步版本"""
        import asyncio
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt >= self.max_retries:
                    break
                
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
```

---

## 五、日志系统设计

### 5.1 src/logging/structured.py

```python
import json
import logging
import sys
from datetime import datetime
from typing import Optional


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加自定义字段
        if hasattr(record, "execution_id"):
            log_entry["execution_id"] = record.execution_id
        if hasattr(record, "thread_id"):
            log_entry["thread_id"] = record.thread_id
        if hasattr(record, "agent"):
            log_entry["agent"] = record.agent
        if hasattr(record, "action"):
            log_entry["action"] = record.action
        if hasattr(record, "cost"):
            log_entry["cost"] = record.cost
        
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logger(
    name: str,
    level: str = "INFO",
    output_file: Optional[str] = None
) -> logging.Logger:
    """设置结构化日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    formatter = StructuredFormatter()
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # File handler
    if output_file:
        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        fh = logging.FileHandler(output_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger
```

---

## 六、告警系统设计

### 6.1 src/alerting/notifier.py

```python
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Alert:
    title: str
    message: str
    severity: str  # info, warning, critical
    source: str
    timestamp: float
    metadata: dict = None


class Notifier(ABC):
    @abstractmethod
    async def send(self, alert: Alert):
        pass


class ConsoleNotifier(Notifier):
    async def send(self, alert: Alert):
        print(f"[ALERT] [{alert.severity}] {alert.title}: {alert.message}")


class WebhookNotifier(Notifier):
    def __init__(self, url: str):
        self.url = url
    
    async def send(self, alert: Alert):
        import aiohttp
        payload = {
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity,
            "source": alert.source,
            "timestamp": alert.timestamp,
        }
        async with aiohttp.ClientSession() as session:
            await session.post(self.url, json=payload)


class FeishuNotifier(Notifier):
    """飞书告警通知"""
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, alert: Alert):
        import aiohttp
        severity_colors = {
            "info": "blue",
            "warning": "orange",
            "critical": "red"
        }
        color = severity_colors.get(alert.severity, "gray")
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": alert.title},
                    "template": color,
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": alert.message},
                    }
                ]
            }
        }
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json=payload)


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self._notifiers: list[Notifier] = []
        self._cooldowns: dict[str, float] = {}
        self._cooldown_seconds: int = 300  # 5分钟去重
    
    def add_notifier(self, notifier: Notifier):
        self._notifiers.append(notifier)
    
    async def send_alert(self, alert: Alert):
        # 去重
        key = f"{alert.title}:{alert.source}"
        if key in self._cooldowns:
            return
        self._cooldowns[key] = alert.timestamp
        
        # 清理过期
        import time
        cutoff = time.time() - self._cooldown_seconds
        self._cooldowns = {k: v for k, v in self._cooldowns.items() if v > cutoff}
        
        # 发送
        for notifier in self._notifiers:
            try:
                await notifier.send(alert)
            except Exception:
                pass
```

---

## 七、健康检查

### 7.1 src/health/checker.py

```python
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class HealthStatus:
    component: str
    status: str  # healthy, degraded, unhealthy
    message: str
    last_check: float


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self._checks: dict[str, callable] = {}
    
    def register(self, name: str, check_fn: callable):
        self._checks[name] = check_fn
    
    def check_all(self) -> list[HealthStatus]:
        results = []
        for name, fn in self._checks.items():
            try:
                ok, msg = fn()
                results.append(HealthStatus(
                    component=name,
                    status="healthy" if ok else "unhealthy",
                    message=msg,
                    last_check=time.time(),
                ))
            except Exception as e:
                results.append(HealthStatus(
                    component=name,
                    status="unhealthy",
                    message=str(e),
                    last_check=time.time(),
                ))
        return results
    
    def is_healthy(self) -> bool:
        return all(r.status == "healthy" for r in self.check_all())


# 预设检查
def check_api_key(api_key_env: str) -> callable:
    import os
    def _check():
        key = os.environ.get(api_key_env)
        if key and len(key) > 10:
            return True, "API Key 已配置"
        return False, f"{api_key_env} 未设置"
    return _check
```

---

## 八、API Server (FastAPI)

### 8.1 src/api/server.py

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional


app = FastAPI(title="Multi-Agent Orchestration API")

# --- Metrics endpoint ---
from ..observability.metrics import MetricsCollector
metrics_collector = MetricsCollector()

@app.get("/metrics")
def prometheus_metrics():
    return metrics_collector.export_prometheus()


# --- Health check ---
from ..health.checker import HealthChecker
health_checker = HealthChecker()

@app.get("/health")
def health_check():
    results = health_checker.check_all()
    healthy = all(r.status == "healthy" for r in results)
    return {
        "status": "healthy" if healthy else "unhealthy",
        "checks": [r.__dict__ for r in results],
    }


# --- Task submission ---
class TaskRequest(BaseModel):
    task: str
    workflow: Optional[str] = "software-development"
    project_path: Optional[str] = "."
    auto_approve: Optional[bool] = False


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@app.post("/tasks", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    import uuid
    task_id = uuid.uuid4().hex[:16]
    # TODO: 提交到执行队列
    return TaskResponse(
        task_id=task_id,
        status="queued",
        message="Task submitted successfully",
    )


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    # TODO: 查询任务状态
    return {"task_id": task_id, "status": "running", "progress": 0.5}
```

---

## 九、与 Phase 4-6 集成

### 9.1 嵌入点

| 组件 | 集成方式 |
|------|---------|
| Executor 执行 | 每个 Agent 调用前后记录 Metrics |
| Tool 调用 | Hooks 中添加 Tracing Span |
| 工作流开始/结束 | CostController 报告总成本 |
| 失败重试 | CircuitBreaker 包裹 Executor 调用 |
| 异常 | AlertManager 发送告警 |

### 9.2 配置集成

```yaml
# 在生产配置中启用
observability:
  metrics:
    enabled: true
    export_interval: 15  # 秒
  tracing:
    enabled: true
    sample_rate: 1.0  # 100% 采样

cost_control:
  enabled: true
  budget:
    warning: 5.0
    limit: 10.0
    stop: 20.0

resilience:
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout: 30.0
  retry:
    max_retries: 3
    base_delay: 1.0

alerting:
  enabled: true
  notifiers:
    - type: feishu
      webhook_url: ${FEISHU_WEBHOOK_URL}
    - type: console

api_server:
  enabled: true
  host: 0.0.0.0
  port: 8000
```

---

## 十、文件变更清单

### 新增文件
```
src/observability/
├── __init__.py
├── metrics.py          # MetricsCollector
└── tracing.py          # Tracer, Span

src/cost/
├── __init__.py
└── controller.py       # CostController, CostBudget

src/resilience/
├── __init__.py
├── circuit_breaker.py  # CircuitBreaker
└── retry_policy.py     # RetryPolicy

src/logging/
├── __init__.py
└── structured.py       # StructuredFormatter

src/alerting/
├── __init__.py
└── notifier.py         # AlertManager, Notifiers

src/health/
├── __init__.py
└── checker.py          # HealthChecker

src/api/
├── __init__.py
└── server.py           # FastAPI 应用
```

### 修改文件
- `src/claude/wrapper.py` - 集成 Metrics 和 Tracing
- `src/claude/hooks.py` - 集成 Cost Hook 和 Alert
- `src/workflows/runner.py` - 集成 Circuit Breaker
- `src/config/schema.py` - 新增 observability/cost/resilience 配置

---

## 十一、测试策略

### 11.1 单元测试
- MetricsCollector: 计数器累加、Prometheus 导出格式
- CostController: 阈值触发、状态变化
- CircuitBreaker: 状态转换（CLOSED → OPEN → HALF_OPEN → CLOSED）
- RetryPolicy: 指数退避、jitter

### 11.2 集成测试
- 模拟 API 调用失败触发熔断
- 模拟成本超限触发停止
- 告警通知发送

### 11.3 性能测试
- MetricsCollector 在高并发下的表现
- Prometheus 导出延迟 < 10ms

---

## 十二、实施步骤

| 步骤 | 内容 | 预估时间 |
|------|------|---------|
| 1 | MetricsCollector + Prometheus 导出 | 1 天 |
| 2 | Tracer (Span 模型) | 0.5 天 |
| 3 | CostController | 0.5 天 |
| 4 | CircuitBreaker + RetryPolicy | 1 天 |
| 5 | 结构化日志 | 0.5 天 |
| 6 | AlertManager + 通知器 | 1 天 |
| 7 | HealthChecker | 0.5 天 |
| 8 | FastAPI Server | 1 天 |
| 9 | 集成到现有代码 | 1.5 天 |
| 10 | 测试和文档 | 1 天 |
| **总计** | | **8.5 天** |

