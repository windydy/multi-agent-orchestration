"""
Phase 4 TDD: AgentExecutor 适配器 + DynamicWorkflowState + Verifier

严格遵循 TDD: 先写失败测试 → 再写最小代码 → 重构
"""

import pytest
import asyncio
from src.executors.agent_adapter import AgentExecutor
from src.executors.base import ExecutorStatus, ExecutorResult
from src.plan.graph import ExecutorCapability, PlanNode, NodeType
from src.workflows.states import DynamicWorkflowState, create_dynamic_initial_state
from src.verifier.rules import (
    VerificationDimension,
    VerificationStatus,
    VerificationRule,
    VerificationItem,
    VerificationResult,
    VerifierFramework,
)


# ============================================================
# TDD-4: AgentExecutor 适配器
# ============================================================

class TestAgentExecutorCreation:
    """AgentExecutor 创建"""

    def test_create_adapter(self):
        """创建 AgentExecutor 适配器"""
        ex = AgentExecutor(
            executor_id="agent-dev-1",
            name="developer",
            agent=None,  # 用 None 模拟
            capability=ExecutorCapability.CODE_DEVELOPMENT,
        )
        assert ex.executor_id == "agent-dev-1"
        assert ex.capabilities == [ExecutorCapability.CODE_DEVELOPMENT]
        assert ex.status == ExecutorStatus.IDLE

    def test_adapter_with_multiple_caps(self):
        """适配器可以声明多个能力"""
        ex = AgentExecutor(
            executor_id="multi-1",
            name="multi",
            agent=None,
            capabilities=[ExecutorCapability.CODE_DEVELOPMENT, ExecutorCapability.CODE_REVIEW],
        )
        assert len(ex.capabilities) == 2


class TestAgentExecutorExecute:
    """AgentExecutor execute 方法"""

    def test_execute_with_none_agent(self):
        """agent 为 None 时返回错误"""
        ex = AgentExecutor(
            executor_id="none-1",
            name="none-agent",
            agent=None,
            capability=ExecutorCapability.GENERIC,
        )
        node = PlanNode(id="n1", name="test")
        result = asyncio.get_event_loop().run_until_complete(
            ex.execute(node, {})
        )
        assert result["success"] is False
        assert "没有关联的 agent" in result["error"]

    def test_execute_delegates_to_agent(self):
        """execute 调用 agent.run()"""

        class MockAgent:
            async def run(self, task, context=None):
                from src.core.agent import AgentResult
                return AgentResult(success=True, output="result", metadata={"cost": 0.01})

        ex = AgentExecutor(
            executor_id="mock-1",
            name="mock",
            agent=MockAgent(),
            capability=ExecutorCapability.GENERIC,
        )
        node = PlanNode(id="n1", name="test", description="test task")
        result = asyncio.get_event_loop().run_until_complete(
            ex.execute(node, {"prev": "data"})
        )
        assert result["output"] == "result"

    def test_execute_handles_agent_failure(self):
        """agent 执行失败时返回错误"""

        class FailingAgent:
            async def run(self, task, context=None):
                from src.core.agent import AgentResult
                return AgentResult(success=False, output=None, error="agent failed")

        ex = AgentExecutor(
            executor_id="fail-1",
            name="fail",
            agent=FailingAgent(),
            capability=ExecutorCapability.GENERIC,
        )
        node = PlanNode(id="n1", name="test")
        result = asyncio.get_event_loop().run_until_complete(
            ex.execute(node, {})
        )
        assert result["error"] == "agent failed"


# ============================================================
# TDD-5: DynamicWorkflowState
# ============================================================

class TestDynamicWorkflowState:
    """DynamicWorkflowState TypedDict"""

    def test_create_initial_state(self):
        """创建初始状态"""
        from src.plan.graph import PlanGraph
        graph = PlanGraph(id="p1", task="test task")
        state = create_dynamic_initial_state("test task", graph)
        assert state["task"] == "test task"
        assert state["plan_graph_id"] == "p1"
        assert state["plan_status"] == "executing"
        assert state["executor_results"] == {}
        assert state["verifier_results"] == {}
        assert state["needs_replan"] is False
        assert state["completed_nodes"] == []
        assert state["failed_nodes"] == []

    def test_create_with_project_path(self):
        """创建带项目路径的初始状态"""
        from src.plan.graph import PlanGraph
        graph = PlanGraph(id="p1", task="test")
        state = create_dynamic_initial_state("test", graph, project_path="/tmp/project")
        assert state["project_path"] == "/tmp/project"


# ============================================================
# TDD-6: VerifierFramework
# ============================================================

class TestVerificationDimension:
    """VerificationDimension 枚举"""

    def test_dimensions_exist(self):
        assert VerificationDimension.QUALITY is not None
        assert VerificationDimension.SECURITY is not None
        assert VerificationDimension.CORRECTNESS is not None


class TestVerificationItem:
    """VerificationItem"""

    def test_create_item_passed(self):
        item = VerificationItem(
            rule_id="lint-check",
            dimension=VerificationDimension.QUALITY,
            status=VerificationStatus.PASSED,
            score=1.0,
            message="lint passed",
        )
        assert item.status == VerificationStatus.PASSED
        assert item.score == 1.0

    def test_create_item_failed(self):
        item = VerificationItem(
            rule_id="sec-scan",
            dimension=VerificationDimension.SECURITY,
            status=VerificationStatus.FAILED,
            score=0.3,
            message="found 2 vulnerabilities",
        )
        assert item.status == VerificationStatus.FAILED


class TestVerificationRule:
    """VerificationRule"""

    def test_create_rule(self):
        rule = VerificationRule(
            rule_id="lint",
            dimension=VerificationDimension.QUALITY,
            check="ruff check .",
            timeout=60,
        )
        assert rule.rule_id == "lint"
        assert rule.timeout == 60


class TestVerifierFramework:
    """VerifierFramework"""

    def test_register_rule(self):
        fw = VerifierFramework()
        rule = VerificationRule(
            rule_id="test-rule",
            dimension=VerificationDimension.QUALITY,
            check="true",
            timeout=10,
        )
        fw.register_rule(rule)
        assert "test-rule" in fw._rules

    def test_verify_all_returns_result(self):
        fw = VerifierFramework()
        result = asyncio.get_event_loop().run_until_complete(
            fw.verify_all("test-node", {"output": "code"})
        )
        assert isinstance(result, VerificationResult)

    def test_verify_result_aggregation(self):
        fw = VerifierFramework()
        fw.register_rule(VerificationRule(
            rule_id="always-pass",
            dimension=VerificationDimension.QUALITY,
            check="true",  # always succeeds
            timeout=10,
        ))
        result = asyncio.get_event_loop().run_until_complete(
            fw.verify_all("node-1", {"output": "good code"})
        )
        assert result.node_id == "node-1"
        assert len(result.items) >= 1
