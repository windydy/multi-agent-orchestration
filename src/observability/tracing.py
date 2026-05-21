"""
Phase 7: Tracer — 分布式追踪器

src/observability/tracing.py
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import asyncio


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
        self._active_spans: dict[str, str] = {}
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
