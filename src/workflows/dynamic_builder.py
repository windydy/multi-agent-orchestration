"""
Phase 4: DynamicWorkflowBuilder — 从 PlanGraph 动态构建 LangGraph StateGraph

src/workflows/dynamic_builder.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Awaitable
import logging

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None

from src.plan.graph import PlanGraph, PlanNode, NodeStatus, NodeType, ExecutorCapability
from src.workflows.states import DynamicWorkflowState
from src.executors.registry import ExecutorRegistry
from src.executors.base import ExecutorStatus

logger = logging.getLogger(__name__)

NodeFunction = Callable[[DynamicWorkflowState], Awaitable[dict]]


class DynamicWorkflowBuilder:
    """
    从 PlanGraph 动态构建 LangGraph StateGraph。
    
    工作流程：
    1. 接收 PlanGraph
    2. 拓扑排序获取执行顺序
    3. 为每个 PlanNode 创建 LangGraph 节点函数
    4. 添加条件边（验证/路由）
    5. 编译为可执行 app
    """

    def __init__(self, registry: ExecutorRegistry = None):
        self._plan: PlanGraph | None = None
        self._registry = registry or ExecutorRegistry()
        self._workflow: Any = None
        self._node_functions: dict[str, NodeFunction] = {}

    def from_plan(self, plan: PlanGraph) -> "DynamicWorkflowBuilder":
        """设置 PlanGraph"""
        self._plan = plan
        return self

    def build(self) -> Any:
        """构建并编译 LangGraph StateGraph"""
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("langgraph 未安装: pip install langgraph")
        if self._plan is None:
            raise ValueError("请先调用 from_plan() 设置 PlanGraph")

        # 创建状态图
        self._workflow = StateGraph(DynamicWorkflowState)

        # 拓扑排序获取执行顺序
        order = self._plan.topological_sort()

        # 为每个节点创建 LangGraph 节点函数
        for node_id in order:
            node = self._plan.nodes[node_id]
            node_func = self._create_node_function(node)
            self._node_functions[node_id] = node_func
            self._workflow.add_node(node_id, node_func)

        # 添加 replan 节点
        self._workflow.add_node("replan", self._replan_node)
        # 添加 verifier 节点
        self._workflow.add_node("verify", self._verify_node)

        # 构建边
        self._build_edges(order)

        # 设置入口点
        entry_nodes = self._plan.get_entry_nodes()
        if entry_nodes:
            self._workflow.set_entry_point(entry_nodes[0].id)
        else:
            self._workflow.set_entry_point(END)

        # 编译
        self._app = self._workflow.compile()
        return self._app

    def _create_node_function(self, node: PlanNode) -> NodeFunction:
        """为 PlanNode 创建 LangGraph 节点函数"""

        async def node_func(state: DynamicWorkflowState) -> dict:
            """LangGraph 节点函数"""
            node.status = NodeStatus.RUNNING
            node.started_at = state.get("start_time", "")

            # 查找匹配的 Executor
            executor = self._registry.find_best(node.required_capability)
            if executor is None:
                return {
                    "executor_results": {node.id: {"success": False, "error": "No matching executor"}},
                    "failed_nodes": [node.id],
                    "current_node": node.id,
                }

            # 执行
            try:
                context = {
                    "project_path": state.get("project_path", "."),
                    "previous_results": self._get_previous_results(state, node),
                }
                result = await executor.execute(node, context)

                node.status = NodeStatus.COMPLETED
                node.started_at = datetime.now().isoformat()
                node.completed_at = datetime.now().isoformat()

                return {
                    "executor_results": {node.id: result},
                    "completed_nodes": [node.id],
                    "current_node": node.id,
                }
            except Exception as e:
                node.status = NodeStatus.FAILED
                node.error = str(e)
                return {
                    "executor_results": {node.id: {"success": False, "error": str(e)}},
                    "failed_nodes": [node.id],
                    "current_node": node.id,
                }

        return node_func

    def _get_previous_results(self, state: DynamicWorkflowState, node: PlanNode) -> dict:
        """获取前置节点的结果"""
        prev = {}
        results = state.get("executor_results", {})
        for dep_id in node.dependencies:
            if dep_id in results:
                prev[dep_id] = results[dep_id]
        return prev

    def _build_edges(self, order: list[str]) -> None:
        """构建 LangGraph 边"""
        # 按拓扑顺序添加边
        for node_id in order:
            node = self._plan.nodes[node_id]

            # 找到该节点的所有下游节点
            downstream = []
            for nid, n in self._plan.nodes.items():
                if node_id in n.dependencies:
                    downstream.append(nid)

            # 找到该节点的所有上游节点
            upstream = node.dependencies

            if not downstream:
                # 终端节点 -> verify -> END
                self._workflow.add_edge(node_id, "verify")
            else:
                for down_id in downstream:
                    self._workflow.add_edge(node_id, down_id)

        # verify 节点后路由
        self._workflow.add_conditional_edges(
            "verify",
            self._verify_router,
            {
                "replan": "replan",
                "complete": END,
            },
        )

        # replan 后重新从入口开始
        self._workflow.add_edge("replan", order[0] if order else END)

    def _verify_router(self, state: DynamicWorkflowState) -> str:
        """验证后路由"""
        if state.get("needs_replan", False):
            return "replan"
        return "complete"

    async def _replan_node(self, state: DynamicWorkflowState) -> dict:
        """重新规划节点（占位）"""
        return {
            "needs_replan": False,
            "plan_status": "replanning",
            "messages": [{"role": "system", "content": "Replanning..."}],
        }

    async def _verify_node(self, state: DynamicWorkflowState) -> dict:
        """验证节点（占位）"""
        return {
            "verifier_results": {"verify": {"passed": True}},
            "verification_passed": True,
        }
