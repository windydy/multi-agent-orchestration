"""
Phase 4: ExecutorRegistry — 注册与调度中心

src/executors/registry.py
"""

from __future__ import annotations

from typing import Optional
import logging

from src.plan.graph import ExecutorCapability
from src.executors.base import BaseExecutor

logger = logging.getLogger(__name__)


class ExecutorRegistry:
    """
    Executor 注册与调度中心。

    职责：
    - 管理 Executor 实例池（注册/注销）
    - 能力匹配：根据所需能力找到最佳 Executor
    - 负载均衡：在多个匹配 Executor 中选择最合适的
    """

    def __init__(self):
        self._executors: dict[str, BaseExecutor] = {}
        self._capability_index: dict[ExecutorCapability, list[str]] = {}

    def register(
        self,
        executor: BaseExecutor,
        capabilities: Optional[list[ExecutorCapability]] = None,
    ) -> None:
        """
        注册一个 Executor 实例。

        Args:
            executor: Executor 实例
            capabilities: 可选的能力覆盖。如果不提供，使用 executor.capabilities。
        """
        self._executors[executor.executor_id] = executor
        caps = capabilities if capabilities is not None else executor.capabilities
        for cap in caps:
            self._capability_index.setdefault(cap, []).append(executor.executor_id)
        logger.info(f"Registered executor: {executor.executor_id}")

    def unregister(self, executor_id: str) -> bool:
        """注销一个 Executor 实例"""
        if executor_id not in self._executors:
            return False

        executor = self._executors.pop(executor_id)
        # 清理能力索引
        caps = executor.capabilities
        for cap in caps:
            if cap in self._capability_index:
                self._capability_index[cap] = [
                    eid for eid in self._capability_index[cap]
                    if eid != executor_id
                ]
        logger.info(f"Unregistered executor: {executor_id}")
        return True

    def get(self, executor_id: str) -> Optional[BaseExecutor]:
        return self._executors.get(executor_id)

    def find_best(
        self,
        required_capability: ExecutorCapability,
        exclude_ids: set[str] = None,
    ) -> Optional[BaseExecutor]:
        """
        找到处理指定能力的最佳 Executor。

        匹配策略：
        1. 过滤：只保留支持该能力且未被排除的 Executor
        2. 排序：按 match_score 降序
        3. 选择：最高分且空闲的 Executor
        """
        exclude_ids = exclude_ids or set()
        candidates: list[tuple[float, BaseExecutor]] = []

        for eid in self._capability_index.get(required_capability, []):
            if eid in exclude_ids:
                continue
            executor = self._executors.get(eid)
            if executor is None:
                continue
            score = executor.match_score(required_capability)
            if score > 0:
                candidates.append((score, executor))
            elif required_capability not in executor.capabilities:
                # Executor 是通过 capabilities override 注册的，给默认分数
                candidates.append((1.0, executor))

        if not candidates:
            # 降级：尝试 GENERIC 能力的 Executor
            for eid in self._capability_index.get(ExecutorCapability.GENERIC, []):
                if eid in exclude_ids:
                    continue
                executor = self._executors.get(eid)
                if executor and not executor.status.is_busy:
                    return executor
            return None

        # 按分数排序，优先选择高分的
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def list_all(self) -> list[BaseExecutor]:
        return list(self._executors.values())

    def list_by_capability(self, capability: ExecutorCapability) -> list[BaseExecutor]:
        """列出支持指定能力的所有 Executor"""
        result = []
        for eid in self._capability_index.get(capability, []):
            executor = self._executors.get(eid)
            if executor is not None:
                result.append(executor)
        return result
