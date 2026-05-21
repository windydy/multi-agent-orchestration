"""
Phase 7: CostController — 成本控制器

src/cost/controller.py
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import asyncio


class CostStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class CostBudget:
    """成本预算"""
    warning_threshold: float = 5.0
    limit_threshold: float = 10.0
    stop_threshold: float = 20.0
    per_agent_budget: Optional[float] = None
    per_task_budget: Optional[float] = None


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
    
    def __init__(self, budget: CostBudget = None, max_records: int = 10000):
        self.budget = budget or CostBudget()
        self._records: list[CostRecord] = []
        self._max_records = max_records
        self._running_total: float = 0.0
        self._agent_totals: dict[str, float] = {}
        self._task_totals: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._status = CostStatus.OK
    
    async def record_cost(self, agent: str, task_id: str, cost: float,
                    input_tokens: int, output_tokens: int) -> CostStatus:
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
            # 防止内存泄露：限制记录数量
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
            self._running_total += cost
            self._agent_totals[agent] = self._agent_totals.get(agent, 0) + cost
            self._task_totals[task_id] = self._task_totals.get(task_id, 0) + cost
            
            # 更新状态
            if self._running_total >= self.budget.stop_threshold:
                self._status = CostStatus.STOP
            elif self._running_total >= self.budget.limit_threshold:
                self._status = CostStatus.LIMIT
            elif self._running_total >= self.budget.warning_threshold:
                self._status = CostStatus.WARNING
            else:
                self._status = CostStatus.OK
            
            return self._status
    
    def should_stop(self) -> bool:
        """是否应该停止执行"""
        return self._status == CostStatus.STOP
    
    @property
    def status(self) -> CostStatus:
        return self._status
    
    @property
    def total_cost(self) -> float:
        return self._running_total
    
    def get_agent_cost(self, agent: str) -> float:
        return self._agent_totals.get(agent, 0.0)
    
    def get_task_cost(self, task_id: str) -> float:
        return self._task_totals.get(task_id, 0.0)
