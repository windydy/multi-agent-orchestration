"""
Phase 4 TDD: BaseExecutor 接口

严格遵循 TDD: 先写失败测试 → 再写最小代码 → 重构
"""

import pytest
from src.executors.base import BaseExecutor, ExecutorStatus
from src.plan.graph import ExecutorCapability, PlanNode


class TestExecutorStatus:
    """ExecutorStatus 枚举"""

    def test_idle_not_busy(self):
        status = ExecutorStatus.IDLE
        assert status.is_busy is False

    def test_running_is_busy(self):
        status = ExecutorStatus.RUNNING
        assert status.is_busy is True

    def test_error_not_busy(self):
        status = ExecutorStatus.ERROR
        assert status.is_busy is False


class TestBaseExecutorAbstract:
    """BaseExecutor 是抽象类"""

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化 BaseExecutor"""
        with pytest.raises(TypeError):
            BaseExecutor(
                executor_id="test",
                name="test",
                capabilities=[],
            )


class TestBaseExecutorConcrete:
    """实现一个具体的 Executor 用于测试"""

    def test_match_score_returns_score(self):
        """match_score: 匹配返回 1.0，不匹配返回 0"""

        class TestExecutor(BaseExecutor):
            async def execute(self, node: PlanNode, context: dict) -> dict:
                return {"output": "ok"}

        ex = TestExecutor(
            executor_id="test-1",
            name="test",
            capabilities=[ExecutorCapability.CODE_DEVELOPMENT],
        )
        # 匹配的能力
        assert ex.match_score(ExecutorCapability.CODE_DEVELOPMENT) == 1.0
        # 不匹配的能力
        assert ex.match_score(ExecutorCapability.TESTING) == 0.0

    def test_executor_id(self):
        class TestExecutor(BaseExecutor):
            async def execute(self, node: PlanNode, context: dict) -> dict:
                return {}

        ex = TestExecutor(
            executor_id="dev-1",
            name="developer",
            capabilities=[ExecutorCapability.CODE_DEVELOPMENT],
        )
        assert ex.executor_id == "dev-1"
        assert ex.name == "developer"
        assert ex.capabilities == [ExecutorCapability.CODE_DEVELOPMENT]
        assert ex.status == ExecutorStatus.IDLE

    def test_repr(self):
        class TestExecutor(BaseExecutor):
            async def execute(self, node: PlanNode, context: dict) -> dict:
                return {}

        ex = TestExecutor(
            executor_id="test-1",
            name="tester",
            capabilities=[ExecutorCapability.TESTING],
        )
        assert "test-1" in repr(ex)
        assert "tester" in repr(ex)

    def test_status_transitions(self):
        """Executor 状态可以在子类中切换"""

        class TestExecutor(BaseExecutor):
            async def execute(self, node: PlanNode, context: dict) -> dict:
                self.status = ExecutorStatus.RUNNING
                result = {"output": "done"}
                self.status = ExecutorStatus.IDLE
                return result

            async def fail(self):
                self.status = ExecutorStatus.ERROR

        ex = TestExecutor(
            executor_id="x",
            name="y",
            capabilities=[ExecutorCapability.GENERIC],
        )
        assert ex.status == ExecutorStatus.IDLE


class TestBaseExecutorExecute:
    """execute 方法签名"""

    def test_execute_returns_dict(self):
        """execute 必须返回 dict"""

        class TestExecutor(BaseExecutor):
            async def execute(self, node: PlanNode, context: dict) -> dict:
                return {"output": "result", "metadata": {"key": "value"}}

        ex = TestExecutor(
            executor_id="t",
            name="test",
            capabilities=[ExecutorCapability.GENERIC],
        )
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ex.execute(PlanNode(id="n1", name="test"), {})
        )
        assert isinstance(result, dict)
        assert result["output"] == "result"
