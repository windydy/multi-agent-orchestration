"""
Phase 7: CircuitBreaker — 熔断器

src/resilience/circuit_breaker.py
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """熔断器打开时抛出的异常"""
    pass


@dataclass
class CircuitBreaker:
    """
    熔断器实现。
    
    状态转换：
    - CLOSED → OPEN: 失败次数达到阈值
    - OPEN → HALF_OPEN: 恢复超时过去
    - HALF_OPEN → CLOSED: 一次成功调用
    - HALF_OPEN → OPEN: 调用失败
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    
    @property
    def state(self) -> CircuitState:
        """获取熔断器状态"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器调用函数"""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """异步版本"""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._failure_count = 0
    
    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
    
    def reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
