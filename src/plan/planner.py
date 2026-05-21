"""
Phase 4: PlannerAgent — LLM 驱动的任务规划器

src/plan/planner.py
"""

from __future__ import annotations

from typing import Any, Optional
import json
import logging

from src.plan.graph import PlanGraph, PlanNode, NodeStatus, NodeType, ExecutorCapability

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    规划器 Agent。
    
    职责：
    - 理解用户意图
    - 任务分解
    - 构建依赖 DAG
    - 输出 PlanGraph
    
    注意：本实现提供结构化的默认 plan 生成逻辑，
    后续可替换为 LLM 驱动的 generate_plan。
    """

    def __init__(self, model: str = "qwen3.6-plus"):
        self.model = model

    async def generate_plan(self, task: str) -> PlanGraph:
        """
        根据任务描述生成执行计划。
        
        当前版本返回一个简单的默认计划。
        后续版本将调用 LLM 生成智能计划。
        """
        import uuid

        plan = PlanGraph(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            task=task,
            plan_type="default",
            status="draft",
            planner_model=self.model,
        )

        # 默认计划：需求 -> 设计 -> 开发 -> 审查 -> 测试
        default_steps = [
            ("req", "需求分析", ExecutorCapability.REQUIREMENTS_ANALYSIS, []),
            ("design", "技术设计", ExecutorCapability.TECHNICAL_DESIGN, ["req"]),
            ("dev", "开发实现", ExecutorCapability.CODE_DEVELOPMENT, ["design"]),
            ("review", "代码审查", ExecutorCapability.CODE_REVIEW, ["dev"]),
            ("test", "测试验证", ExecutorCapability.TESTING, ["review"]),
        ]

        for nid, name, cap, deps in default_steps:
            node = PlanNode(
                id=nid,
                name=name,
                required_capability=cap,
                dependencies=deps,
            )
            plan.add_node(node)

        plan.status = "approved"
        return plan

    def validate_plan(self, plan: PlanGraph) -> tuple[bool, list[str]]:
        """
        验证 PlanGraph 是否有效。
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        # 检查是否有节点
        if not plan.nodes:
            errors.append("计划中没有节点")
            return False, errors

        # 检查入口节点
        entry_nodes = plan.get_entry_nodes()
        if not entry_nodes:
            errors.append("没有入口节点（所有节点都有依赖）")

        # 检查拓扑排序（检测循环）
        try:
            plan.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        # 检查每个节点
        for node_id, node in plan.nodes.items():
            if not node.name:
                errors.append(f"节点 {node_id} 缺少名称")
            # 检查依赖是否存在
            for dep in node.dependencies:
                if dep not in plan.nodes:
                    errors.append(f"节点 {node_id} 依赖不存在的节点 {dep}")

        return len(errors) == 0, errors
