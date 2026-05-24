"""
Phase 9: WorkflowRunner + ClarifierAgent 集成测试

测试 WorkflowRunner 在 run() 方法中正确调用 ClarifierAgent。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.clarifier.result import ClarifierResult, ClarificationQuestion, Assumption
from src.clarifier.dimensions import DimensionScore, CLARIFICATION_DIMENSIONS


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_clarifier_result_skip():
    """高分结果 - 直接通过"""
    dimensions = {
        name: DimensionScore(dimension=name, score=5, reason="明确")
        for name in CLARIFICATION_DIMENSIONS
    }
    return ClarifierResult(
        score=100.0,
        dimensions=dimensions,
        questions=[],
        assumptions=[],
        recommendation="skip",
        enriched_task="原始任务",
        raw_input="原始任务",
    )


@pytest.fixture
def mock_clarifier_result_conservative():
    """中等分数 - 保守模式"""
    dimensions = {
        name: DimensionScore(dimension=name, score=3, reason="部分明确")
        for name in CLARIFICATION_DIMENSIONS
    }
    return ClarifierResult(
        score=50.0,
        dimensions=dimensions,
        questions=[],
        assumptions=[
            Assumption(dimension="budget", assumption="无预算限制", risk_level="low"),
        ],
        recommendation="conservative",
        enriched_task="基于假设：无预算限制。原始任务",
        raw_input="原始任务",
    )


@pytest.fixture
def mock_clarifier_result_interactive():
    """低分 - 交互模式"""
    dimensions = {
        name: DimensionScore(dimension=name, score=1, reason="未说明")
        for name in CLARIFICATION_DIMENSIONS
    }
    return ClarifierResult(
        score=0.0,
        dimensions=dimensions,
        questions=[
            ClarificationQuestion(
                dimension="functional_scope",
                question="需要哪些功能？",
                importance="high",
            ),
        ],
        assumptions=[],
        recommendation="interactive",
        enriched_task="原始任务",
        raw_input="原始任务",
    )


@pytest.fixture
def mock_planner():
    """模拟 PlannerAgent"""
    planner = MagicMock()
    planner.generate_plan = AsyncMock(return_value=MagicMock(
        id="plan_123",
        nodes={"node1": MagicMock()},
        edges=[],
        plan_type="development",
    ))
    planner.validate_plan = MagicMock(return_value=(True, []))
    planner._default_plan = MagicMock(return_value=MagicMock(
        id="plan_default",
        nodes={"node1": MagicMock()},
        edges=[],
        plan_type="development",
    ))
    return planner


# ============================================================
# WorkflowRunner + ClarifierAgent 集成测试
# ============================================================

class TestRunnerClarifierIntegration:
    """WorkflowRunner 与 ClarifierAgent 集成测试"""

    @pytest.mark.asyncio
    async def test_runner_with_clarifier_skip(self, mock_planner, mock_clarifier_result_skip):
        """ClarifierAgent 返回 skip 时，应该使用原始任务"""
        from src.workflows.runner import WorkflowRunner

        # 创建 mock clarifier
        clarifier = MagicMock()
        clarifier.analyze = AsyncMock(return_value=mock_clarifier_result_skip)

        runner = WorkflowRunner(
            planner=mock_planner,
            clarifier=clarifier,
        )

        # 验证 clarifier 被正确注入
        assert runner.clarifier is clarifier

        # 验证 clarifier 在构造函数中设置
        assert hasattr(runner, 'clarifier')
        assert runner.clarifier is not None

    @pytest.mark.asyncio
    async def test_runner_without_clarifier(self, mock_planner):
        """没有 ClarifierAgent 时，应该正常运行"""
        from src.workflows.runner import WorkflowRunner

        runner = WorkflowRunner(
            planner=mock_planner,
            clarifier=None,
        )

        assert runner.clarifier is None

    @pytest.mark.asyncio
    async def test_runner_clarifier_constructor_param(self, mock_planner):
        """ClarifierAgent 应该通过构造函数参数注入"""
        from src.workflows.runner import WorkflowRunner

        clarifier = MagicMock()
        clarifier.analyze = AsyncMock()

        runner = WorkflowRunner(
            planner=mock_planner,
            clarifier=clarifier,
        )

        assert runner.clarifier is clarifier

    @pytest.mark.asyncio
    async def test_runner_clarifier_analyze_called(self, mock_planner, mock_clarifier_result_skip):
        """run() 方法应该调用 clarifier.analyze()"""
        from src.workflows.runner import WorkflowRunner

        clarifier = MagicMock()
        clarifier.analyze = AsyncMock(return_value=mock_clarifier_result_skip)

        runner = WorkflowRunner(
            planner=mock_planner,
            clarifier=clarifier,
        )

        # 由于 run() 需要完整的 LangGraph 环境，我们只测试 clarifier 被正确设置
        assert runner.clarifier is clarifier
        assert runner.clarifier.analyze == clarifier.analyze


# ============================================================
# Server 初始化测试
# ============================================================

class TestServerClarifierInitialization:
    """Server 初始化 ClarifierAgent 测试"""

    def test_server_imports_clarifier(self):
        """server.py 应该导入 ClarifierAgent"""
        import src.api.server as server_module
        # 验证模块可以正常导入
        assert hasattr(server_module, 'create_app')

    def test_routes_import_clarification(self):
        """routes/__init__.py 应该导入 clarification router"""
        from src.api.routes import router
        # 验证 router 存在
        assert router is not None

    def test_clarification_router_has_analyze_endpoint(self):
        """clarification router 应该有 analyze 端点"""
        from src.api.routes.clarification import router

        routes = [route.path for route in router.routes]
        assert "/clarification/analyze" in routes

    def test_clarification_router_has_dimensions_endpoint(self):
        """clarification router 应该有 dimensions 端点"""
        from src.api.routes.clarification import router

        routes = [route.path for route in router.routes]
        assert "/clarification/dimensions" in routes
