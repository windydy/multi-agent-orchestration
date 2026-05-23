"""
Workflow Runner

运行和管理工作流执行

架构原则：
- PlannerAgent 是唯一路径，所有任务必须经过 Planner 动态规划
- 不再使用硬编码 DevelopmentPipelineBuilder
- 用户可传入自定义 YAML 配置或 ExecutorRegistry 来定制执行行为
"""

import asyncio
from typing import Any, Optional, Callable
from datetime import datetime
import json
import logging

from .states import WorkflowState, create_initial_state, WorkflowStateManager

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """工作流运行器
    
    通过 PlannerAgent 动态规划任务执行计划，使用 DynamicWorkflowBuilder
    从 PlanGraph 构建 LangGraph StateGraph 并执行。
    
    定制方式（可选）：
    - planner: PlannerAgent 实例（必须）
    - dynamic_builder: DynamicWorkflowBuilder 实例（可选，自动创建）
    - registry: ExecutorRegistry 实例（可选，自动创建）
    - config_path: YAML 配置文件路径（可选，覆盖默认配置）
    """
    
    def __init__(
        self,
        planner: Any,                   # PlannerAgent 实例（必须）
        dynamic_builder: Any = None,    # DynamicWorkflowBuilder 实例
        registry: Any = None,           # ExecutorRegistry 实例
        verifier: Any = None,           # VerifierFramework 实例
        config_path: Optional[str] = None,  # YAML 配置路径
        clarifier: Any = None,          # ClarifierAgent 实例（可选）
    ):
        if planner is None:
            raise ValueError("WorkflowRunner 必须传入 PlannerAgent 实例")
        
        self.planner = planner
        self.dynamic_builder = dynamic_builder
        self.registry = registry
        self.verifier = verifier
        self.config_path = config_path
        self.clarifier = clarifier  # Phase 9: ClarifierAgent 注入
        
        # 执行记录
        self._executions: dict[str, dict] = {}
    
    async def _ensure_executors(self):
        """自动将项目中已有的 Agent 注册为 Executor"""
        if self.registry is None:
            from src.executors.registry import ExecutorRegistry
            self.registry = ExecutorRegistry()
        
        # 只注册一次
        if getattr(self, '_executors_registered', False):
            return
        self._executors_registered = True
        
        try:
            from src.plan.graph import ExecutorCapability
            from src.executors.agent_adapter import AgentExecutor
            from src.agents import (
                create_requirements_agent,
                create_designer_agent,
                create_developer_agent,
                create_reviewer_agent,
                create_tester_agent,
                create_fixer_agent,
            )
            
            agent_map = [
                ("requirements_analyst", "requirements", create_requirements_agent, ExecutorCapability.REQUIREMENTS_ANALYSIS),
                ("designer", "design", create_designer_agent, ExecutorCapability.TECHNICAL_DESIGN),
                ("developer", "develop", create_developer_agent, ExecutorCapability.CODE_DEVELOPMENT),
                ("reviewer", "review", create_reviewer_agent, ExecutorCapability.CODE_REVIEW),
                ("tester", "test", create_tester_agent, ExecutorCapability.TESTING),
                ("fixer", "fix", create_fixer_agent, ExecutorCapability.BUG_FIXING),
            ]
            
            for eid, name, create_fn, cap in agent_map:
                try:
                    agent = create_fn()
                    executor = AgentExecutor(
                        executor_id=eid,
                        name=name,
                        agent=agent,
                        capability=cap,
                    )
                    self.registry.register(executor)
                    logger.info("[WorkflowRunner] Registered executor: %s (%s)", name, eid)
                except Exception as e:
                    logger.warning("[WorkflowRunner] Failed to register executor %s: %s", name, e)
        except ImportError as e:
            logger.warning("[WorkflowRunner] Agent executor import failed: %s", e)
    
    async def run(
        self,
        task: str,
        project_path: str = ".",
        thread_id: str = None
    ) -> dict:
        """运行工作流
        
        1. ClarifierAgent 评分（如果配置了 clarifier）
        2. PlannerAgent 生成 PlanGraph
        3. DynamicWorkflowBuilder 构建 LangGraph
        4. Executor 按图执行
        5. Verifier 验证结果
        
        Args:
            task: 任务描述
            project_path: 项目路径
            thread_id: 会话ID
        
        Returns:
            执行结果
        """
        thread_id = thread_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self._executions[thread_id] = {
            "task": task,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "mode": "dynamic",
            "state": None,
        }
        
        logger.info("[WorkflowRunner] 开始动态规划执行: thread_id=%s", thread_id)
        
        # 自动注册 Executor（如果 registry 是空的）
        await self._ensure_executors()
        
        # 1. ClarifierAgent 评分（如果配置了）
        enriched_task = task
        if self.clarifier is not None:
            logger.info("[WorkflowRunner] 启动 ClarifierAgent 评分")
            try:
                clarifier_result = await self.clarifier.analyze(task)
                logger.info("[WorkflowRunner] 澄清评分: %.1f, 推荐: %s",
                          clarifier_result.score, clarifier_result.recommendation)
                
                if clarifier_result.recommendation == "skip":
                    logger.info("[WorkflowRunner] 评分足够，直接执行")
                    enriched_task = task
                elif clarifier_result.recommendation == "conservative":
                    logger.info("[WorkflowRunner] 使用保守模式，填充假设")
                    enriched_task = clarifier_result.enriched_task
                else:
                    logger.info("[WorkflowRunner] 需要交互澄清（当前未实现，降级为保守模式）")
                    enriched_task = clarifier_result.enriched_task
            except Exception as e:
                logger.warning("[WorkflowRunner] ClarifierAgent 失败，使用原始任务: %s", e)
        
        # 2. PlannerAgent 生成 PlanGraph
        logger.info("[WorkflowRunner] PlannerAgent 生成计划: %s", enriched_task)
        try:
            plan = await self.planner.generate_plan(enriched_task, context={
                "project_path": project_path,
            })
            
            valid, errors = self.planner.validate_plan(plan)
            if not valid:
                logger.warning("[WorkflowRunner] 计划验证失败: %s，使用默认计划", errors)
                plan = self.planner._default_plan(enriched_task, plan.id)
                valid, _ = self.planner.validate_plan(plan)
                if not valid:
                    return {
                        "success": False,
                        "thread_id": thread_id,
                        "error": f"无法生成有效的执行计划: {errors}",
                    }
            
            logger.info("[WorkflowRunner] 计划生成完成: %d 节点, %d 边",
                       len(plan.nodes), len(plan.edges))
            
        except Exception as e:
            logger.error("[WorkflowRunner] PlannerAgent 异常: %s", e, exc_info=True)
            return {
                "success": False,
                "thread_id": thread_id,
                "error": f"PlannerAgent 失败: {str(e)}",
            }
        
        # 3. DynamicWorkflowBuilder 构建 LangGraph
        try:
            from src.workflows.dynamic_builder import DynamicWorkflowBuilder
            from src.workflows.states import create_dynamic_initial_state
            from src.executors.registry import ExecutorRegistry
            
            if self.registry is None:
                self.registry = ExecutorRegistry()
            
            if self.dynamic_builder is None:
                self.dynamic_builder = DynamicWorkflowBuilder(registry=self.registry)
            
            app = self.dynamic_builder.from_plan(plan).build()
            
        except ImportError as e:
            logger.error("[WorkflowRunner] LangGraph 未安装: %s", e)
            return {
                "success": False,
                "thread_id": thread_id,
                "error": f"langgraph 未安装: {str(e)}",
            }
        except Exception as e:
            logger.error("[WorkflowRunner] DynamicWorkflowBuilder 失败: %s", e, exc_info=True)
            return {
                "success": False,
                "thread_id": thread_id,
                "error": f"动态工作流构建失败: {str(e)}",
            }
        
        # 4. 执行
        try:
            initial_state = create_dynamic_initial_state(
                task=enriched_task,
                plan_graph=plan,
                project_path=project_path,
            )
            
            config = {"configurable": {"thread_id": thread_id}}
            result = await app.ainvoke(initial_state, config=config)
            
            # 5. 验证结果
            verification_passed = result.get("verification_passed", False)
            
            final_result = {
                "success": True,
                "thread_id": thread_id,
                "final_state": result,
                "plan_id": plan.id,
                "node_count": len(plan.nodes),
                "verification_passed": verification_passed,
                "summary": {
                    "task": enriched_task,
                    "plan_type": plan.plan_type,
                    "nodes": list(plan.nodes.keys()),
                    "verification": "passed" if verification_passed else "failed",
                },
            }
            
            self._executions[thread_id]["status"] = "completed"
            self._executions[thread_id]["end_time"] = datetime.now().isoformat()
            self._executions[thread_id]["state"] = result
            
            logger.info("[WorkflowRunner] 执行完成: thread_id=%s", thread_id)
            return final_result
            
        except Exception as e:
            self._executions[thread_id]["status"] = "failed"
            self._executions[thread_id]["error"] = str(e)
            
            logger.error("[WorkflowRunner] 执行失败: %s", e, exc_info=True)
            return {
                "success": False,
                "thread_id": thread_id,
                "error": str(e),
                "plan_id": plan.id,
            }
    
    def get_state(self, thread_id: str) -> dict:
        """获取当前状态（暂不支持，因为动态工作流使用不同状态类型）"""
        if thread_id not in self._executions:
            return {"thread_id": thread_id, "error": "执行不存在"}
        return self._executions[thread_id]
    
    def get_history(self, thread_id: str) -> list[dict]:
        """获取执行历史（暂不支持）"""
        return []
    
    def list_executions(self) -> list[dict]:
        """列出所有执行记录"""
        return [
            {
                "thread_id": tid,
                **info,
            }
            for tid, info in self._executions.items()
        ]


async def run_pipeline(
    task: str,
    project_path: str = ".",
    planner: Any = None,
    api_key: Optional[str] = None,
) -> dict:
    """便捷函数：运行工作流
    
    必须传入 PlannerAgent 实例。
    
    Args:
        task: 任务描述
        project_path: 项目路径
        planner: PlannerAgent 实例（必须）
        api_key: API 密钥（用于创建 PlannerAgent）
    
    Returns:
        执行结果
    """
    if planner is None:
        from src.plan.planner import PlannerAgent
        planner = PlannerAgent(model="qwen3.6-plus", api_key=api_key)
    
    runner = WorkflowRunner(planner=planner)
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
    for msg in messages[-5:]:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]
        print(f"  [{role}] {content}...")
    
    print("\n" + "=" * 60)
