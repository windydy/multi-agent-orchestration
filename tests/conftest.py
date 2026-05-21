"""
共享测试 fixtures
"""
import pytest
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def mock_agent():
    """创建一个 mock agent"""
    agent = Mock()
    agent.name = "test-agent"
    agent.capabilities = ["coding", "review"]
    agent.run = AsyncMock(return_value="OK")
    return agent


@pytest.fixture
def sample_plan_graph():
    """创建一个示例 PlanGraph"""
    from src.core.plan import PlanGraph, PlanNode
    graph = PlanGraph(
        name="test-pipeline",
        nodes=[
            PlanNode(name="requirements", agent_type="planner", dependencies=[]),
            PlanNode(name="design", agent_type="designer", dependencies=["requirements"]),
            PlanNode(name="develop", agent_type="coder", dependencies=["design"]),
            PlanNode(name="review", agent_type="reviewer", dependencies=["develop"]),
            PlanNode(name="test", agent_type="tester", dependencies=["develop"]),
        ],
    )
    return graph


@pytest.fixture
def empty_registry():
    """创建一个空 ExecutorRegistry"""
    from src.executors.registry import ExecutorRegistry
    return ExecutorRegistry()
