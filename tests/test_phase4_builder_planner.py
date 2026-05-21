"""
Phase 4 TDD: DynamicWorkflowBuilder + PlannerAgent

严格遵循 TDD
"""

import pytest
import asyncio
from src.plan.graph import PlanNode, PlanGraph, NodeType, ExecutorCapability, NodeStatus
from src.workflows.dynamic_builder import DynamicWorkflowBuilder
from src.workflows.states import DynamicWorkflowState
from src.plan.planner import PlannerAgent


# ============================================================
# TDD-7: DynamicWorkflowBuilder
# ============================================================

class TestDynamicWorkflowBuilder:
    """DynamicWorkflowBuilder — 从 PlanGraph 构建 LangGraph StateGraph"""

    def test_create_builder(self):
        builder = DynamicWorkflowBuilder()
        assert builder is not None

    def test_from_plan(self):
        """from_plan 返回 builder 自身（链式调用）"""
        builder = DynamicWorkflowBuilder()
        graph = PlanGraph(id="p1", task="test")
        result = builder.from_plan(graph)
        assert result is builder

    def test_build_returns_compiled_app(self):
        """build 返回编译后的 LangGraph app"""
        builder = DynamicWorkflowBuilder()
        graph = PlanGraph(id="p1", task="test")
        graph.add_node(PlanNode(id="n1", name="Step 1"))
        builder.from_plan(graph)
        app = builder.build()
        assert app is not None
        # app 应该有 ainvoke 方法
        assert hasattr(app, 'ainvoke')

    def test_build_with_multiple_nodes(self):
        """构建包含多个节点的图"""
        builder = DynamicWorkflowBuilder()
        graph = PlanGraph(id="p1", task="test")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        graph.add_node(PlanNode(id="n3", name="C", dependencies=["n1"]))
        builder.from_plan(graph)
        app = builder.build()
        assert app is not None


# ============================================================
# TDD-8: PlannerAgent
# ============================================================

class TestPlannerAgent:
    """PlannerAgent — LLM 驱动的任务规划器"""

    def test_create_planner(self):
        agent = PlannerAgent(model="qwen3.6-plus")
        assert agent.model == "qwen3.6-plus"

    def test_planner_default_model(self):
        agent = PlannerAgent()
        assert agent.model == "qwen3.6-plus"

    def test_planner_generate_plan_returns_graph(self):
        """generate_plan 返回 PlanGraph"""
        agent = PlannerAgent(model="qwen3.6-plus")
        # 使用 simple 模式返回 mock plan
        result = asyncio.get_event_loop().run_until_complete(
            agent.generate_plan("test task")
        )
        assert isinstance(result, PlanGraph)

    def test_planner_validate_plan(self):
        """验证有效计划通过"""
        agent = PlannerAgent()
        graph = PlanGraph(id="p1", task="test")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        valid, errors = agent.validate_plan(graph)
        assert valid is True

    def test_planner_validate_plan_empty(self):
        """空计划不通过"""
        agent = PlannerAgent()
        graph = PlanGraph(id="p1", task="test")
        valid, errors = agent.validate_plan(graph)
        assert valid is False
