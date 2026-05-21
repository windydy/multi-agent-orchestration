"""
Phase 4 TDD: PlanNode + PlanGraph 数据模型

严格遵循 TDD: 先写失败测试 → 再写最小代码 → 重构
"""

import pytest
from src.plan.graph import (
    PlanNode,
    PlanGraph,
    NodeStatus,
    NodeType,
    ExecutorCapability,
)


# ============================================================
# 测试: PlanNode
# ============================================================

class TestPlanNodeCreation:
    """PlanNode 创建和基本属性"""

    def test_create_minimal_node(self):
        """创建最简 PlanNode（仅 id + name）"""
        node = PlanNode(id="node-1", name="测试节点")
        assert node.id == "node-1"
        assert node.name == "测试节点"
        assert node.node_type == NodeType.TASK
        assert node.description == ""
        assert node.required_capability == ExecutorCapability.GENERIC

    def test_create_node_with_fields(self):
        """创建带完整字段的 PlanNode"""
        node = PlanNode(
            id="req-1",
            name="需求分析",
            node_type=NodeType.TASK,
            description="分析用户需求",
            required_capability=ExecutorCapability.REQUIREMENTS_ANALYSIS,
            dependencies=["start"],
            parallel_group="group-a",
            max_retries=5,
            timeout_seconds=600,
        )
        assert node.required_capability == ExecutorCapability.REQUIREMENTS_ANALYSIS
        assert node.dependencies == ["start"]
        assert node.parallel_group == "group-a"
        assert node.max_retries == 5
        assert node.timeout_seconds == 600

    def test_defaults(self):
        """PlanNode 默认值"""
        node = PlanNode(id="x", name="y")
        assert node.status == NodeStatus.PENDING
        assert node.retry_count == 0
        assert node.result is None
        assert node.error is None
        assert node.metadata == {}


class TestPlanNodeProperties:
    """PlanNode 属性"""

    def test_is_entry_with_no_deps(self):
        """无依赖的节点是入口节点"""
        node = PlanNode(id="start", name="开始")
        assert node.is_entry is True

    def test_is_entry_with_deps(self):
        """有依赖的节点不是入口节点"""
        node = PlanNode(id="step-2", name="步骤2", dependencies=["step-1"])
        assert node.is_entry is False


class TestPlanNodeSerialization:
    """PlanNode 序列化/反序列化"""

    def test_to_dict(self):
        """序列化为 dict"""
        node = PlanNode(
            id="dev-1",
            name="开发",
            required_capability=ExecutorCapability.CODE_DEVELOPMENT,
            dependencies=["design"],
            max_retries=3,
            timeout_seconds=300,
        )
        d = node.to_dict()
        assert d["id"] == "dev-1"
        assert d["required_capability"] == "code_development"
        assert d["dependencies"] == ["design"]
        assert d["max_retries"] == 3

    def test_from_dict(self):
        """从 dict 反序列化"""
        data = {
            "id": "test-1",
            "name": "测试",
            "node_type": "task",
            "description": "运行测试",
            "required_capability": "testing",
            "dependencies": ["dev-1"],
            "parallel_group": None,
            "condition": None,
            "executor_name": None,
            "max_retries": 2,
            "timeout_seconds": 120,
            "status": "pending",
            "retry_count": 0,
            "result": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "metadata": {},
        }
        node = PlanNode.from_dict(data)
        assert node.id == "test-1"
        assert node.required_capability == ExecutorCapability.TESTING
        assert node.dependencies == ["dev-1"]

    def test_roundtrip(self):
        """序列化→反序列化→与原对象一致"""
        original = PlanNode(
            id="roundtrip",
            name="往返测试",
            description="测试 roundtrip",
            required_capability=ExecutorCapability.CODE_REVIEW,
            dependencies=["a", "b"],
        )
        restored = PlanNode.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.required_capability == original.required_capability
        assert restored.dependencies == original.dependencies


# ============================================================
# 测试: PlanGraph
# ============================================================

class TestPlanGraphCreation:
    """PlanGraph 创建"""

    def test_create_graph(self):
        """创建 PlanGraph"""
        graph = PlanGraph(id="plan-1", task="实现登录功能")
        assert graph.id == "plan-1"
        assert graph.task == "实现登录功能"
        assert graph.nodes == {}
        assert graph.edges == []
        assert graph.plan_type == "default"
        assert graph.status == "draft"

    def test_create_graph_with_nodes(self):
        """创建带节点的 PlanGraph"""
        n1 = PlanNode(id="n1", name="需求")
        n2 = PlanNode(id="n2", name="设计", dependencies=["n1"])
        graph = PlanGraph(
            id="p1",
            task="开发",
            nodes={"n1": n1, "n2": n2},
            edges=[("n1", "n2")],
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1


class TestPlanGraphOperations:
    """PlanGraph 图操作"""

    def test_add_node(self):
        """添加节点"""
        graph = PlanGraph(id="p1", task="t1")
        node = PlanNode(id="n1", name="节点1")
        graph.add_node(node)
        assert "n1" in graph.nodes
        assert graph.nodes["n1"] is node

    def test_add_node_with_edges(self):
        """添加节点时自动添加边"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        assert ("n1", "n2") in graph.edges

    def test_remove_node(self):
        """移除节点"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        removed = graph.remove_node("n2")
        assert removed is not None
        assert removed.id == "n2"
        assert "n2" not in graph.nodes
        # 边也应该被清理
        assert ("n1", "n2") not in graph.edges

    def test_get_entry_nodes(self):
        """获取入口节点"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        graph.add_node(PlanNode(id="n3", name="C"))  # 另一个入口
        entries = graph.get_entry_nodes()
        assert len(entries) == 2
        entry_ids = {n.id for n in entries}
        assert entry_ids == {"n1", "n3"}

    def test_get_ready_nodes(self):
        """获取可执行节点"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        graph.add_node(PlanNode(id="n3", name="C", dependencies=["n1"]))

        # 初始只有 n1 可执行
        ready = graph.get_ready_nodes(set())
        assert len(ready) == 1
        assert ready[0].id == "n1"

        # n1 完成后，n2 和 n3 可执行
        ready = graph.get_ready_nodes({"n1"})
        assert len(ready) == 2
        assert {n.id for n in ready} == {"n2", "n3"}

    def test_get_parallel_groups(self):
        """获取并行组"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A", parallel_group="g1"))
        graph.add_node(PlanNode(id="n2", name="B", parallel_group="g1"))
        graph.add_node(PlanNode(id="n3", name="C"))  # 无并行组

        groups = graph.get_parallel_groups()
        assert "g1" in groups
        assert len(groups["g1"]) == 2

    def test_topological_sort(self):
        """拓扑排序"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        graph.add_node(PlanNode(id="n3", name="C", dependencies=["n2"]))

        order = graph.topological_sort()
        assert order.index("n1") < order.index("n2") < order.index("n3")

    def test_topological_sort_cycle_detection(self):
        """检测循环依赖"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"]))
        graph.add_node(PlanNode(id="n3", name="C", dependencies=["n2"]))
        # 手动添加循环边: n3 -> n1
        graph.edges.append(("n3", "n1"))

        with pytest.raises(ValueError, match="循环|cycle"):
            graph.topological_sort()

    def test_topological_sort_with_parallel(self):
        """拓扑排序处理并行节点"""
        graph = PlanGraph(id="p1", task="t1")
        graph.add_node(PlanNode(id="n1", name="A"))
        graph.add_node(PlanNode(id="n2", name="B", dependencies=["n1"], parallel_group="g1"))
        graph.add_node(PlanNode(id="n3", name="C", dependencies=["n1"], parallel_group="g1"))
        graph.add_node(PlanNode(id="n4", name="D", dependencies=["n2", "n3"]))

        order = graph.topological_sort()
        assert order.index("n1") < order.index("n2")
        assert order.index("n1") < order.index("n3")
        assert order.index("n2") < order.index("n4")
        assert order.index("n3") < order.index("n4")

    def test_to_json(self):
        """序列化为 JSON 字符串"""
        graph = PlanGraph(id="p1", task="test")
        graph.add_node(PlanNode(id="n1", name="节点"))
        json_str = graph.to_json()
        assert isinstance(json_str, str)
        assert '"id": "p1"' in json_str or '"id":"p1"' in json_str

    def test_from_json(self):
        """从 JSON 反序列化"""
        graph = PlanGraph(id="p1", task="test")
        graph.add_node(PlanNode(id="n1", name="节点", dependencies=[]))
        json_str = graph.to_json()
        restored = PlanGraph.from_json(json_str)
        assert restored.id == "p1"
        assert "n1" in restored.nodes
