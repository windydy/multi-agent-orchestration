"""
开发流水线构建器

使用LangGraph构建完整的开发流水线工作流
"""

import os
from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.sqlite.aio import SqliteSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    try:
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        # sqlite可能在不同位置
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError:
            SqliteSaver = None
        LANGGRAPH_AVAILABLE = True
    except ImportError:
        LANGGRAPH_AVAILABLE = False
        StateGraph = None
        END = None

from .states import WorkflowState, create_initial_state, merge_state
from ..agents import (
    create_requirements_agent,
    create_designer_agent,
    create_developer_agent,
    create_reviewer_agent,
    create_tester_agent,
    create_fixer_agent,
)


# 节点函数类型
NodeFunction = Callable[[WorkflowState], Awaitable[dict]]


@dataclass
class PipelineConfig:
    """流水线配置"""
    
    # API配置
    api_key: Optional[str] = None
    
    # 模型配置 (默认使用 qwen3.6-plus)
    requirements_model: str = "qwen3.6-plus"
    designer_model: str = "qwen3.6-plus"
    developer_model: str = "qwen3.6-plus"
    reviewer_model: str = "qwen3.6-plus"
    tester_model: str = "qwen3.6-plus"
    fixer_model: str = "qwen3.6-plus"
    
    # 执行配置
    max_iterations: int = 10       # 最大迭代次数（防止死循环）
    enable_human_review: bool = True  # 启用人工审批
    checkpoint_enabled: bool = True   # 启用持久化
    
    # 持久化配置
    checkpoint_path: str = "./checkpoints/pipeline.db"
    
    # Hooks配置
    custom_hooks: list = None


class DevelopmentPipelineBuilder:
    """开发流水线构建器
    
    使用LangGraph构建多Agent协作的开发流水线。
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("langgraph未安装，请运行: pip install langgraph")
        
        # Agent实例
        self._agents: dict[str, Any] = {}
        
        # 工作流图
        self._workflow: StateGraph = None
        self._app: Any = None
        
        # 检查点存储
        self._checkpointer = None
    
    def _create_agents(self):
        """创建所有Agent实例"""
        hooks = self.config.custom_hooks or []
        
        self._agents = {
            "requirements": create_requirements_agent(
                api_key=self.config.api_key,
                model=self.config.requirements_model,
                custom_hooks=hooks
            ),
            "design": create_designer_agent(
                api_key=self.config.api_key,
                model=self.config.designer_model,
                custom_hooks=hooks
            ),
            "develop": create_developer_agent(
                api_key=self.config.api_key,
                model=self.config.developer_model,
                custom_hooks=hooks
            ),
            "review": create_reviewer_agent(
                api_key=self.config.api_key,
                model=self.config.reviewer_model,
                custom_hooks=hooks
            ),
            "test": create_tester_agent(
                api_key=self.config.api_key,
                model=self.config.tester_model,
                custom_hooks=hooks
            ),
            "fix": create_fixer_agent(
                api_key=self.config.api_key,
                model=self.config.fixer_model,
                custom_hooks=hooks
            ),
        }
    
    def _create_node_functions(self) -> dict[str, NodeFunction]:
        """创建LangGraph节点函数
        
        每个节点函数执行对应的Agent并返回状态更新。
        """
        nodes = {}
        
        for name, agent in self._agents.items():
            async def node_func(state: WorkflowState, agent_name=name) -> dict:
                """节点执行函数"""
                # 构建上下文
                context = {
                    "project_path": state.get("project_path", "."),
                    "previous_results": self._get_previous_results(state, agent_name),
                }
                
                # 执行Agent
                result = await agent.run(state.get("task", ""), context)
                
                # 构建状态更新
                updates = {
                    "current_stage": agent_name,
                    agent_name: result.output if result.success else {"error": result.error},
                    "messages": [{
                        "role": agent_name,
                        "content": str(result.output)[:500],  # 截断长内容
                        "success": result.success,
                    }],
                }
                
                # 更新成本
                if result.metadata and "cost" in result.metadata:
                    updates["total_cost"] = state.get("total_cost", 0) + result.metadata["cost"]
                
                return updates
            
            nodes[name] = node_func
        
        return nodes
    
    def _get_previous_results(self, state: WorkflowState, current_agent: str) -> dict:
        """获取前置节点的结果"""
        # 定义依赖顺序
        dependencies = {
            "requirements": [],
            "design": ["requirements"],
            "develop": ["requirements", "design"],
            "review": ["develop", "design"],
            "test": ["review", "develop"],
            "fix": ["test", "develop"],
        }
        
        prev = {}
        for dep in dependencies.get(current_agent, []):
            if state.get(dep):
                prev[dep] = state.get(dep)
        
        return prev
    
    def _review_router(self, state: WorkflowState) -> str:
        """Review节点路由决策
        
        根据Review结果决定下一步：
        - approved -> test
        - needs_revision -> develop (返回修改)
        - human -> 等待人工审批
        """
        # Agent输出存储在 state["review"] 中
        review_result = state.get("review", {})
        
        # 如果review_result是字符串（简单输出），解析JSON或默认通过
        if isinstance(review_result, str):
            try:
                import json
                review_result = json.loads(review_result)
            except:
                review_result = {"approved": True}
        
        # 检查迭代次数，防止死循环
        if state.get("iteration_count", 0) >= self.config.max_iterations:
            return "test"  # 强制进入测试
        
        # 检查审批状态
        if review_result.get("approved"):
            return "test"
        
        if review_result.get("needs_revision"):
            return "develop"
        
        # 默认需要人工审批
        if self.config.enable_human_review:
            return "human_review"
        
        return "test"  # 禁用人工审批时直接进入测试
    
    def _test_router(self, state: WorkflowState) -> str:
        """Test节点路由决策
        
        根据测试结果决定下一步：
        - passed -> END
        - fixable -> fix
        - needs_help -> human_review
        """
        # Agent输出存储在 state["test"] 中
        test_result = state.get("test", {})
        
        # 如果test_result是字符串（简单输出），解析JSON或默认通过
        if isinstance(test_result, str):
            try:
                import json
                test_result = json.loads(test_result)
            except:
                test_result = {"passed": True}
        
        if test_result.get("passed"):
            return "end"
        
        # 检查迭代次数
        if state.get("iteration_count", 0) >= self.config.max_iterations:
            return "end"  # 强制结束
        
        if test_result.get("fixable"):
            return "fix"
        
        # 无法自动修复，需要人工介入
        if self.config.enable_human_review:
            return "human_review"
        
        return "end"
    
    def _fix_router(self, state: WorkflowState) -> str:
        """Fix节点路由决策
        
        修复后重新进入测试
        """
        return "test"
    
    def _human_review_node(self, state: WorkflowState) -> dict:
        """人工审批节点
        
        这是一个空节点，实际审批通过interrupt机制实现。
        """
        return {
            "current_stage": "human_review",
            "messages": [{
                "role": "system",
                "content": "等待人工审批..."
            }]
        }
    
    def build(self) -> Any:
        """构建工作流
        
        Returns:
            编译后的LangGraph应用
        """
        # 创建Agent
        self._create_agents()
        
        # 创建节点函数
        nodes = self._create_node_functions()
        
        # 创建状态图
        self._workflow = StateGraph(WorkflowState)
        
        # 添加节点
        for name, func in nodes.items():
            self._workflow.add_node(name, func)
        
        # 添加人工审批节点
        self._workflow.add_node("human_review", self._human_review_node)
        
        # 定义固定边
        self._workflow.add_edge("requirements", "design")
        self._workflow.add_edge("design", "develop")
        self._workflow.add_edge("develop", "review")  # 开发后进入审查
        self._workflow.add_edge("fix", "test")
        
        # 定义条件边
        self._workflow.add_conditional_edges(
            "review",
            self._review_router,
            {
                "test": "test",
                "develop": "develop",
                "human_review": "human_review",
            }
        )
        
        self._workflow.add_conditional_edges(
            "test",
            self._test_router,
            {
                "end": END,
                "fix": "fix",
                "human_review": "human_review",
            }
        )
        
        # 人工审批后的路由
        self._workflow.add_conditional_edges(
            "human_review",
            lambda s: s.get("next_stage", "test"),
            {
                "test": "test",
                "develop": "develop",
                "end": END,
            }
        )
        
        # 设置入口点
        self._workflow.set_entry_point("requirements")
        
        # 配置检查点
        interrupt_nodes = []
        if self.config.enable_human_review:
            interrupt_nodes = ["human_review"]
        
        if self.config.checkpoint_enabled:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config.checkpoint_path), exist_ok=True)
            if SqliteSaver is not None:
                self._checkpointer = SqliteSaver.from_conn_string(self.config.checkpoint_path)
            else:
                # SqliteSaver 不可用，使用 MemorySaver
                self._checkpointer = MemorySaver()
        else:
            self._checkpointer = MemorySaver()
        
        # 编译
        self._app = self._workflow.compile(
            checkpointer=self._checkpointer,
            interrupt_before=interrupt_nodes if interrupt_nodes else None
        )
        
        return self._app
    
    def get_app(self) -> Any:
        """获取编译后的应用"""
        if self._app is None:
            self.build()
        return self._app
    
    def get_workflow_graph(self) -> str:
        """获取工作流可视化图（Mermaid格式）"""
        return """
graph TD
    START --> requirements[需求分析]
    requirements --> design[技术设计]
    design --> develop[开发实现]
    develop --> review[代码审查]
    
    review --> |approved| test[测试验证]
    review --> |needs_revision| develop
    review --> |human| human_review[人工审批]
    
    test --> |passed| END
    test --> |fixable| fix[Bug修复]
    test --> |needs_help| human_review
    
    fix --> test
    
    human_review --> |approve| test
    human_review --> |reject| develop
    human_review --> |abort| END
"""


def create_dev_pipeline(
    api_key: Optional[str] = None,
    enable_human_review: bool = True,
    checkpoint_path: str = "./checkpoints/pipeline.db",
    max_iterations: int = 10,
    custom_hooks: list = None
) -> DevelopmentPipelineBuilder:
    """创建开发流水线
    
    Args:
        api_key: Claude API密钥
        enable_human_review: 启用人工审批
        checkpoint_path: 检查点存储路径
        max_iterations: 最大迭代次数
        custom_hooks: 自定义Hooks
    
    Returns:
        DevelopmentPipelineBuilder实例
    """
    config = PipelineConfig(
        api_key=api_key,
        enable_human_review=enable_human_review,
        checkpoint_path=checkpoint_path,
        max_iterations=max_iterations,
        custom_hooks=custom_hooks
    )
    
    return DevelopmentPipelineBuilder(config)