"""
Phase 7: MetricsCollector — 指标收集器

src/observability/metrics.py
"""

import time
import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    labels: dict = field(default_factory=dict)


class MetricsCollector:
    """指标收集器（异步安全）"""
    
    def __init__(self, max_points: int = 10000, max_histogram: int = 10000):
        self._points: deque = deque(maxlen=max_points)
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, deque] = {}
        self._max_histogram = max_histogram
        self._lock = asyncio.Lock()
    
    # --- Counter (累加计数器) ---
    def increment(self, name: str, value: float = 1.0, labels: dict = None):
        self._counters[name] = self._counters.get(name, 0) + value
        self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- Gauge (瞬时值) ---
    def set_gauge(self, name: str, value: float, labels: dict = None):
        key = self._make_key(name, labels)
        self._gauges[key] = value
        self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- Histogram (分布) ---
    def observe(self, name: str, value: float, labels: dict = None):
        if name not in self._histograms:
            self._histograms[name] = deque(maxlen=self._max_histogram)
        self._histograms[name].append(value)
        self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- Async lock-protected operations ---
    async def aincrement(self, name: str, value: float = 1.0, labels: dict = None):
        """异步安全的 increment"""
        async with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    async def aset_gauge(self, name: str, value: float, labels: dict = None):
        """异步安全的 set_gauge"""
        async with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    async def aobserve(self, name: str, value: float, labels: dict = None):
        """异步安全的 observe"""
        async with self._lock:
            if name not in self._histograms:
                self._histograms[name] = deque(maxlen=self._max_histogram)
            self._histograms[name].append(value)
            self._record_point(MetricPoint(name, value, time.time(), labels or {}))
    
    # --- 快捷方法 ---
    def record_execution(self, agent: str, duration: float, success: bool, cost: float):
        """记录一次 Agent 执行"""
        self.increment("agent_executions_total", labels={"agent": agent, "success": str(success)})
        self.observe("agent_duration_seconds", duration, {"agent": agent})
        self.increment("agent_cost_total", cost, {"agent": agent})
    
    def record_token_usage(self, agent: str, input_tokens: int, output_tokens: int):
        """记录 Token 使用"""
        self.increment("tokens_input_total", input_tokens, {"agent": agent})
        self.increment("tokens_output_total", output_tokens, {"agent": agent})
    
    # --- Prometheus 导出 ---
    def export_prometheus(self) -> str:
        """导出 Prometheus 文本格式"""
        lines = []
        
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        for key, value in self._gauges.items():
            name = key.split("{")[0] if "{" in key else key
            lines.append(f"# TYPE {name} gauge")
            if "{" in key:
                lines.append(f"{key} {value}")
            else:
                lines.append(f"{name} {value}")
        
        for name, values in self._histograms.items():
            lines.append(f"# TYPE {name} histogram")
            count = len(values)
            total = sum(values)
            lines.append(f"{name}_count {count}")
            lines.append(f"{name}_sum {total:.6f}")
            
            buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf")]
            cumulative = 0
            for bucket in buckets:
                cumulative += sum(1 for v in values if v <= bucket)
                lines.append(f'{name}_bucket{{le="{bucket}"}} {cumulative}')
            lines.append(f'{name}_bucket{{le="+Inf"}} {count}')
        
        lines.append("")
        return "\n".join(lines)
    
    async def reset(self):
        """重置所有指标"""
        async with self._lock:
            self._points.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
    
    def _record_point(self, point: MetricPoint):
        self._points.append(point)
    
    @staticmethod
    def _make_key(name: str, labels: dict) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
