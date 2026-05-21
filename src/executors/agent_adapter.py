"""
Phase 4: AgentExecutor — Agent → Executor 适配器

src/executors/agent_adapter.py

将现有的 BaseAgent 包装为 BaseExecutor，使其可在 P/E/V 架构中使用。
"""

from __future__ import annotations

from typing import Any, Optional

from src.executors.base import BaseExecutor, ExecutorStatus, ExecutorResult
from src.plan.graph import ExecutorCapability, PlanNode


class AgentExecutor(BaseExecutor):
    """
    Agent → Executor 适配器。
    
    将 Phase 1-3 的 BaseAgent 实例包装为 Executor，
    使其可以在 P/E/V 架构中作为执行单元使用。
    """

    def __init__(
        self,
        executor_id: str,
        name: str,
        agent: Any,
        capability: Optional[ExecutorCapability] = None,
        capabilities: Optional[list[ExecutorCapability]] = None,
    ):
        self._agent = agent
        self._status = ExecutorStatus.IDLE

        caps = capabilities or ([capability] if capability else [ExecutorCapability.GENERIC])

        super().__init__(
            executor_id=executor_id,
            name=name,
            capabilities=caps,
        )

    @property
    def status(self) -> ExecutorStatus:
        return self._status

    @status.setter
    def status(self, value: ExecutorStatus) -> None:
        self._status = value

    async def execute(self, node: PlanNode, context: dict) -> dict:
        """
        调用 agent.run() 执行任务。
        """
        if self._agent is None:
            return {
                "success": False,
                "error": f"Executor '{self.executor_id}' 没有关联的 agent",
            }

        self.status = ExecutorStatus.RUNNING
        try:
            agent_result = await self._agent.run(
                node.description or node.name,
                context=context,
            )

            updates = {
                "output": agent_result.output,
                "success": agent_result.success,
            }

            if not agent_result.success:
                updates["error"] = agent_result.error

            if agent_result.metadata:
                updates["metadata"] = agent_result.metadata

            return updates
        except Exception as e:
            self.status = ExecutorStatus.ERROR
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            if self.status != ExecutorStatus.ERROR:
                self.status = ExecutorStatus.IDLE
