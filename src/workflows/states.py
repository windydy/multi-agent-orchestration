"""
WorkflowState定义

开发流水线全局状态数据结构
"""

from typing import TypedDict, Annotated, Sequence, Optional
import operator
from datetime import datetime


class WorkflowState(TypedDict):
    """开发流水线全局状态
    
    使用TypedDict定义状态结构，配合LangGraph使用。
    messages字段使用Annotated实现累加模式。
    """
    
    # 基础信息
    task: str                    # 原始任务描述
    project_path: str            # 项目目录路径
    
    # 消息历史 (累加模式 - 每个节点添加的消息自动合并)
    messages: Annotated[Sequence[dict], operator.add]
    
    # 各阶段结果
    requirements: dict           # 需求分析结果
    design: dict                 # 技术设计结果
    code_changes: dict           # 代码变更记录
    review_result: dict          # Review结果
    test_result: dict            # 测试结果
    fix_result: dict             # 修复结果
    
    # 控制流
    current_stage: str           # 当前阶段名称
    next_stage: str              # 下一阶段名称
    iteration_count: int         # 迭代计数（防止死循环）
    needs_revision: bool         # 是否需要返回开发阶段修订
    
    # 人工审批
    human_approval: bool         # 人工审批状态
    approval_comment: str        # 审批意见
    
    # 元数据
    start_time: str              # 开始时间
    end_time: str                # 结束时间
    total_cost: float            # 累计成本（美元）


def create_initial_state(
    task: str,
    project_path: str = "."
) -> WorkflowState:
    """创建初始状态
    
    Args:
        task: 任务描述
        project_path: 项目路径
    
    Returns:
        初始化的WorkflowState
    """
    return WorkflowState(
        task=task,
        project_path=project_path,
        messages=[],
        requirements={},
        design={},
        code_changes={},
        review_result={},
        test_result={},
        fix_result={},
        current_stage="start",
        next_stage="requirements",
        iteration_count=0,
        needs_revision=False,
        human_approval=False,
        approval_comment="",
        start_time=datetime.now().isoformat(),
        end_time="",
        total_cost=0.0,
    )


class WorkflowStateManager:
    """WorkflowState管理器
    
    提供状态更新和查询的便捷方法。
    不继承BaseState，作为独立的管理器使用。
    """
    
    def __init__(self, initial_state: WorkflowState = None):
        self._state: dict = dict(initial_state or create_initial_state(""))
    
    def get(self, key: str, default: any = None) -> any:
        """获取状态值"""
        return self._state.get(key, default)
    
    def set(self, key: str, value: any) -> None:
        """设置状态值"""
        self._state[key] = value
    
    def update(self, updates: dict) -> None:
        """批量更新状态"""
        self._state.update(updates)
    
    def snapshot(self) -> WorkflowState:
        """获取完整状态快照"""
        return WorkflowState(**self._state)
    
    def update_stage_result(self, stage: str, result: dict) -> None:
        """更新阶段结果
        
        Args:
            stage: 阶段名称 (requirements/design/code_changes/review_result/test_result)
            result: 阶段执行结果
        """
        self.set(stage, result)
        self.set("current_stage", stage)
        self.set("iteration_count", self.get("iteration_count", 0) + 1)
    
    def add_message(self, role: str, content: str, metadata: dict = None) -> None:
        """添加消息
        
        Args:
            role: 消息来源角色
            content: 消息内容
            metadata: 元数据
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        # 由于messages是累加模式，直接添加到列表
        current_messages = list(self.get("messages", []))
        current_messages.append(message)
        self.set("messages", current_messages)
    
    def set_next_stage(self, stage: str) -> None:
        """设置下一阶段"""
        self.set("next_stage", stage)
    
    def mark_revision_needed(self, reason: str = "") -> None:
        """标记需要修订"""
        self.set("needs_revision", True)
        if reason:
            self.add_message("system", f"需要修订: {reason}")
    
    def mark_revision_complete(self) -> None:
        """标记修订完成"""
        self.set("needs_revision", False)
    
    def set_human_approval(self, approved: bool, comment: str = "") -> None:
        """设置人工审批结果"""
        self.set("human_approval", approved)
        self.set("approval_comment", comment)
    
    def add_cost(self, cost: float) -> None:
        """累加成本"""
        current = self.get("total_cost", 0.0)
        self.set("total_cost", current + cost)
    
    def complete(self) -> None:
        """标记完成"""
        self.set("end_time", datetime.now().isoformat())
        self.set("current_stage", "completed")
        self.set("next_stage", "end")
    
    def is_max_iterations(self, max: int = 10) -> bool:
        """检查是否达到最大迭代次数"""
        return self.get("iteration_count", 0) >= max
    
    def get_summary(self) -> dict:
        """获取执行摘要"""
        return {
            "task": self.get("task"),
            "current_stage": self.get("current_stage"),
            "iteration_count": self.get("iteration_count"),
            "total_cost": self.get("total_cost"),
            "duration": self._calculate_duration(),
            "stages_completed": self._get_completed_stages(),
        }
    
    def _calculate_duration(self) -> str:
        """计算执行时长"""
        start = self.get("start_time")
        end = self.get("end_time") or datetime.now().isoformat()
        
        if start and end:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            duration = end_dt - start_dt
            return f"{duration.total_seconds():.1f}s"
        return "unknown"
    
    def _get_completed_stages(self) -> list[str]:
        """获取已完成的阶段"""
        completed = []
        for stage in ["requirements", "design", "code_changes", "review_result", "test_result"]:
            if self.get(stage):
                completed.append(stage)
        return completed


# 默认状态验证函数
def validate_state(state: WorkflowState) -> bool:
    """验证状态是否有效
    
    Args:
        state: WorkflowState
    
    Returns:
        是否有效
    """
    required_keys = ["task", "project_path", "current_stage"]
    return all(key in state for key in required_keys)


# 状态更新辅助函数
def merge_state(old: WorkflowState, new: dict) -> WorkflowState:
    """合并状态更新
    
    保持TypedDict结构，合并新的更新。
    对于messages字段，使用operator.add实现累加。
    
    Args:
        old: 原状态
        new: 新更新
    
    Returns:
        合并后的状态
    """
    merged = dict(old)
    
    for key, value in new.items():
        if key == "messages":
            # messages使用累加模式
            old_messages = merged.get("messages", [])
            merged["messages"] = operator.add(old_messages, value)
        else:
            merged[key] = value
    
    return WorkflowState(**merged)


# ============================================================
# Phase 4: DynamicWorkflowState — 动态工作流状态
# ============================================================

class DynamicWorkflowState(TypedDict):
    """
    动态工作流全局状态。

    扩展原有的 WorkflowState，新增 PlanGraph 和 P/E/V 相关字段。
    """

    # === 继承自 WorkflowState 的字段 ===
    task: str
    project_path: str
    messages: Annotated[Sequence[dict], operator.add]
    current_stage: str
    iteration_count: int
    total_cost: float
    start_time: str
    end_time: str

    # === PlanGraph 相关 ===
    plan_graph_id: str
    """当前执行计划的 ID"""

    plan_graph_json: str
    """PlanGraph 的 JSON 序列化"""

    plan_status: str
    """计划状态: draft / executing / completed / failed / replanning"""

    # === Executor 结果 ===
    executor_results: Annotated[dict, lambda a, b: {**a, **b}]
    """所有节点的执行结果映射: {node_id: result}"""

    current_node: str
    """当前正在执行的节点 ID"""

    # === Verifier 结果 ===
    verifier_results: Annotated[dict, lambda a, b: {**a, **b}]
    """所有节点的验证结果映射: {node_id: result}"""

    verification_passed: bool
    """最近一次验证是否通过"""

    # === 控制流 ===
    needs_replan: bool
    """是否需要重新规划"""

    replan_reason: str
    """重新规划的原因"""

    completed_nodes: Annotated[list, operator.add]
    """已完成节点 ID 列表"""

    failed_nodes: Annotated[list, operator.add]
    """失败节点 ID 列表"""


def create_dynamic_initial_state(
    task: str,
    plan_graph,  # PlanGraph 实例
    project_path: str = ".",
) -> DynamicWorkflowState:
    """创建动态工作流初始状态"""
    return DynamicWorkflowState(
        task=task,
        project_path=project_path,
        messages=[],
        current_stage="planning",
        iteration_count=0,
        total_cost=0.0,
        start_time=datetime.now().isoformat(),
        end_time="",
        plan_graph_id=plan_graph.id,
        plan_graph_json=plan_graph.to_json(),
        plan_status="executing",
        executor_results={},
        current_node="",
        verifier_results={},
        verification_passed=True,
        needs_replan=False,
        replan_reason="",
        completed_nodes=[],
        failed_nodes=[],
    )