"""
Phase 4: BaseExecutor — 执行器抽象基类

src/executors/base.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.plan.graph import ExecutorCapability, PlanNode


class ExecutorStatus(Enum):
    """Executor 执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"

    @property
    def is_busy(self) -> bool:
        return self == ExecutorStatus.RUNNING


@dataclass
class ExecutorResult:
    """Executor 执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    node_id: str = ""


@dataclass
class BaseExecutor(ABC):
    """
    Executor 抽象基类。
    
    每个 Executor 实现必须:
    - 声明自己的 capabilities
    - 实现 execute 方法
    - 维护自己的状态
    """
    executor_id: str
    name: str
    capabilities: list[ExecutorCapability]

    def __post_init__(self):
        if not hasattr(self, "_status"):
            self._status: ExecutorStatus = ExecutorStatus.IDLE

    @property
    def status(self) -> ExecutorStatus:
        return getattr(self, "_status", ExecutorStatus.IDLE)

    @status.setter
    def status(self, value: ExecutorStatus) -> None:
        self._status = value

    @abstractmethod
    async def execute(self, node: PlanNode, context: dict) -> dict:
        """
        执行 PlanNode 对应的任务。
        
        Args:
            node: 要执行的 PlanNode
            context: 执行上下文（包含前置节点结果等）
            
        Returns:
            dict: 状态更新，将被合并到 LangGraph 全局状态
        """
        pass

    def match_score(self, capability: ExecutorCapability) -> float:
        """
        计算此 Executor 与指定能力的匹配分数。
        
        子类可以覆盖此方法实现更复杂的匹配逻辑。
        
        Returns:
            float: 匹配分数（0 = 不匹配，>0 = 匹配，越高越优先）
        """
        if capability in self.capabilities:
            return 1.0
        return 0.0

    def __repr__(self) -> str:
        return (
            f"Executor(id={self.executor_id!r}, name={self.name!r}, "
            f"caps={[c.value for c in self.capabilities]}, "
            f"status={self.status.value})"
        )
