"""
Workflow Runner

运行和管理工作流执行
"""

import asyncio
from typing import Any, Optional, Callable
from datetime import datetime
import json

from .states import WorkflowState, create_initial_state, WorkflowStateManager
from .builder import DevelopmentPipelineBuilder, create_dev_pipeline


class WorkflowRunner:
    """工作流运行器
    
    提供工作流的启动、监控、暂停、恢复等功能。
    """
    
    def __init__(
        self,
        pipeline: DevelopmentPipelineBuilder = None,
        api_key: Optional[str] = None
    ):
        self.pipeline = pipeline or create_dev_pipeline(api_key=api_key)
        self.app = self.pipeline.get_app()
        
        # 执行记录
        self._executions: dict[str, dict] = {}
    
    async def run(
        self,
        task: str,
        project_path: str = ".",
        thread_id: str = None
    ) -> dict:
        """运行工作流
        
        Args:
            task: 任务描述
            project_path: 项目路径
            thread_id: 会话ID（用于恢复）
        
        Returns:
            执行结果
        """
        thread_id = thread_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建初始状态
        initial_state = create_initial_state(task, project_path)
        
        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        
        # 记录开始
        self._executions[thread_id] = {
            "task": task,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "state": None,
        }
        
        try:
            # 执行
            result = await self.app.ainvoke(initial_state, config=config)
            
            # 更新记录
            self._executions[thread_id]["status"] = "completed"
            self._executions[thread_id]["end_time"] = datetime.now().isoformat()
            self._executions[thread_id]["state"] = result
            
            return {
                "success": True,
                "thread_id": thread_id,
                "final_state": result,
                "summary": self._get_summary(result),
            }
            
        except Exception as e:
            self._executions[thread_id]["status"] = "failed"
            self._executions[thread_id]["error"] = str(e)
            
            return {
                "success": False,
                "thread_id": thread_id,
                "error": str(e),
            }
    
    async def run_until_interrupt(
        self,
        task: str,
        project_path: str = ".",
        thread_id: str = None
    ) -> dict:
        """运行工作流直到中断点
        
        用于人工审批场景，工作流会在human_review节点暂停。
        
        Args:
            task: 任务描述
            project_path: 项目路径
            thread_id: 会话ID
        
        Returns:
            执行结果（包含当前状态）
        """
        thread_id = thread_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        initial_state = create_initial_state(task, project_path)
        config = {"configurable": {"thread_id": thread_id}}
        
        # 记录
        self._executions[thread_id] = {
            "task": task,
            "start_time": datetime.now().isoformat(),
            "status": "interrupted",
        }
        
        # 执行直到中断
        result = await self.app.ainvoke(initial_state, config=config)
        
        # 获取当前状态
        current_state = self.app.get_state(config)
        
        return {
            "thread_id": thread_id,
            "current_state": current_state.values,
            "next_steps": current_state.next,
            "messages": current_state.values.get("messages", []),
        }
    
    async def resume(
        self,
        thread_id: str,
        approval: bool = True,
        comment: str = ""
    ) -> dict:
        """恢复中断的工作流
        
        Args:
            thread_id: 会话ID
            approval: 审批结果
            comment: 审批意见
        
        Returns:
            恢复后的执行结果
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        # 更新状态
        updates = {
            "human_approval": approval,
            "approval_comment": comment,
            "next_stage": "test" if approval else "develop",
        }
        
        self.app.update_state(config, updates)
        
        # 恢复执行
        result = await self.app.ainvoke(None, config=config)
        
        # 更新记录
        if thread_id in self._executions:
            self._executions[thread_id]["status"] = "completed"
            self._executions[thread_id]["end_time"] = datetime.now().isoformat()
            self._executions[thread_id]["state"] = result
        
        return {
            "success": True,
            "thread_id": thread_id,
            "final_state": result,
            "approval_result": {"approved": approval, "comment": comment},
        }
    
    def get_state(self, thread_id: str) -> dict:
        """获取当前状态
        
        Args:
            thread_id: 会话ID
        
        Returns:
            当前状态
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = self.app.get_state(config)
        
        return {
            "thread_id": thread_id,
            "values": state.values,
            "next": state.next,
            "created_at": state.created_at,
            "parent_config": state.parent_config,
        }
    
    def get_history(self, thread_id: str) -> list[dict]:
        """获取执行历史
        
        Args:
            thread_id: 会话ID
        
        Returns:
            状态变更历史
        """
        config = {"configurable": {"thread_id": thread_id}}
        history = list(self.app.get_state_history(config))
        
        return [
            {
                "thread_id": thread_id,
                "step": h.metadata.get("step", 0),
                "values": h.values,
                "created_at": h.created_at,
            }
            for h in history
        ]
    
    def list_executions(self) -> list[dict]:
        """列出所有执行记录"""
        return [
            {
                "thread_id": tid,
                **info,
            }
            for tid, info in self._executions.items()
        ]
    
    def _get_summary(self, state: WorkflowState) -> dict:
        """生成执行摘要"""
        manager = WorkflowStateManager(state)
        return manager.get_summary()


async def run_pipeline(
    task: str,
    project_path: str = ".",
    api_key: Optional[str] = None,
    enable_human_review: bool = True
) -> dict:
    """便捷函数：运行开发流水线
    
    Args:
        task: 任务描述
        project_path: 项目路径
        api_key: Claude API密钥
        enable_human_review: 启用人工审批
    
    Returns:
        执行结果
    """
    runner = WorkflowRunner(api_key=api_key)
    
    if enable_human_review:
        # 运行直到中断
        result = await runner.run_until_interrupt(task, project_path)
        
        # 在实际场景中，这里需要等待人工审批
        # 示例中自动审批通过
        if result.get("next_steps"):
            resume_result = await runner.resume(
                result["thread_id"],
                approval=True,
                comment="自动审批通过（示例）"
            )
            return resume_result
        else:
            return result
    else:
        # 直接运行完整流程
        return await runner.run(task, project_path)


# CLI辅助函数
def print_state_summary(state: dict):
    """打印状态摘要"""
    print("\n" + "=" * 60)
    print("执行状态摘要")
    print("=" * 60)
    
    print(f"任务: {state.get('task', 'N/A')}")
    print(f"当前阶段: {state.get('current_stage', 'N/A')}")
    print(f"迭代次数: {state.get('iteration_count', 0)}")
    print(f"累计成本: ${state.get('total_cost', 0):.2f}")
    
    print("\n已完成阶段:")
    stages = ["requirements", "design", "code_changes", "review_result", "test_result"]
    for stage in stages:
        if state.get(stage):
            print(f"  ✓ {stage}")
        else:
            print(f"  ○ {stage}")
    
    print("\n消息历史:")
    messages = state.get("messages", [])
    for msg in messages[-5:]:  # 显示最近5条
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]
        print(f"  [{role}] {content}...")
    
    print("\n" + "=" * 60)