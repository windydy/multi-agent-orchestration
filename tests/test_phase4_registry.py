"""
Phase 4 TDD: ExecutorRegistry 注册与调度

严格遵循 TDD: 先写失败测试 → 再写最小代码 → 重构
"""

import pytest
from src.executors.registry import ExecutorRegistry
from src.executors.base import BaseExecutor, ExecutorStatus
from src.plan.graph import ExecutorCapability, PlanNode


# Concrete executor for testing
class _TestExecutor(BaseExecutor):
    def __init__(
        self,
        executor_id: str,
        name: str,
        capabilities: list[ExecutorCapability],
        match_scores: dict[ExecutorCapability, float] = None,
    ):
        super().__init__(executor_id=executor_id, name=name, capabilities=capabilities)
        self._match_scores = match_scores or {}
        self.status = ExecutorStatus.IDLE

    def match_score(self, capability: ExecutorCapability) -> float:
        return self._match_scores.get(capability, super().match_score(capability))

    async def execute(self, node: PlanNode, context: dict) -> dict:
        return {"output": "ok"}


class TestExecutorRegistryRegistration:
    """注册与注销"""

    def test_register_executor(self):
        registry = ExecutorRegistry()
        ex = _TestExecutor("dev-1", "developer", [ExecutorCapability.CODE_DEVELOPMENT])
        registry.register(ex)
        assert registry.get("dev-1") is ex

    def test_register_with_capabilities_override(self):
        """register() 支持 capabilities 参数覆盖"""
        registry = ExecutorRegistry()
        ex = _TestExecutor("dev-1", "developer", [ExecutorCapability.GENERIC])
        registry.register(ex, capabilities=[ExecutorCapability.CODE_DEVELOPMENT])
        # 应该能通过 CODE_DEVELOPMENT 找到
        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is ex

    def test_unregister_executor(self):
        registry = ExecutorRegistry()
        ex = _TestExecutor("dev-1", "developer", [ExecutorCapability.CODE_DEVELOPMENT])
        registry.register(ex)
        result = registry.unregister("dev-1")
        assert result is True
        assert registry.get("dev-1") is None

    def test_unregister_nonexistent(self):
        registry = ExecutorRegistry()
        result = registry.unregister("no-such-id")
        assert result is False

    def test_unregister_removes_capability_index(self):
        """注销后能力索引应清理"""
        registry = ExecutorRegistry()
        ex = _TestExecutor("dev-1", "developer", [ExecutorCapability.CODE_DEVELOPMENT])
        registry.register(ex)
        registry.unregister("dev-1")
        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is None

    def test_list_all(self):
        registry = ExecutorRegistry()
        ex1 = _TestExecutor("e1", "a", [ExecutorCapability.GENERIC])
        ex2 = _TestExecutor("e2", "b", [ExecutorCapability.GENERIC])
        registry.register(ex1)
        registry.register(ex2)
        all_executors = registry.list_all()
        assert len(all_executors) == 2

    def test_list_by_capability(self):
        registry = ExecutorRegistry()
        ex1 = _TestExecutor("e1", "dev", [ExecutorCapability.CODE_DEVELOPMENT])
        ex2 = _TestExecutor("e2", "reviewer", [ExecutorCapability.CODE_REVIEW])
        ex3 = _TestExecutor("e3", "multi", [ExecutorCapability.CODE_DEVELOPMENT, ExecutorCapability.CODE_REVIEW])
        registry.register(ex1)
        registry.register(ex2)
        registry.register(ex3)

        dev_list = registry.list_by_capability(ExecutorCapability.CODE_DEVELOPMENT)
        assert len(dev_list) == 2
        assert {e.executor_id for e in dev_list} == {"e1", "e3"}


class TestExecutorRegistryFindBest:
    """能力匹配与查找"""

    def test_find_best_matching(self):
        registry = ExecutorRegistry()
        ex1 = _TestExecutor("e1", "a", [ExecutorCapability.CODE_DEVELOPMENT])
        ex2 = _TestExecutor("e2", "b", [ExecutorCapability.CODE_REVIEW])
        registry.register(ex1)
        registry.register(ex2)

        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is ex1

    def test_find_best_with_score_ranking(self):
        """优先选择匹配分数更高的"""
        registry = ExecutorRegistry()
        ex1 = _TestExecutor("e1", "a", [ExecutorCapability.CODE_DEVELOPMENT],
                            match_scores={ExecutorCapability.CODE_DEVELOPMENT: 0.5})
        ex2 = _TestExecutor("e2", "b", [ExecutorCapability.CODE_DEVELOPMENT],
                            match_scores={ExecutorCapability.CODE_DEVELOPMENT: 1.0})
        registry.register(ex1)
        registry.register(ex2)

        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is ex2

    def test_find_best_exclude(self):
        """排除指定的 Executor"""
        registry = ExecutorRegistry()
        ex1 = _TestExecutor("e1", "a", [ExecutorCapability.CODE_DEVELOPMENT])
        ex2 = _TestExecutor("e2", "b", [ExecutorCapability.CODE_DEVELOPMENT])
        registry.register(ex1)
        registry.register(ex2)

        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT, exclude_ids={"e1"})
        assert found is ex2

    def test_find_best_no_match_returns_none(self):
        registry = ExecutorRegistry()
        ex = _TestExecutor("e1", "a", [ExecutorCapability.CODE_REVIEW])
        registry.register(ex)

        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is None

    def test_find_best_fallback_to_generic(self):
        """没有精确匹配时，降级到 GENERIC"""
        registry = ExecutorRegistry()
        ex = _TestExecutor("e1", "generic", [ExecutorCapability.GENERIC])
        registry.register(ex)

        found = registry.find_best(ExecutorCapability.CODE_DEVELOPMENT)
        assert found is ex
