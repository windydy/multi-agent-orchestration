"""
Orchestrator编排器抽象

定义多Agent协调和编排的接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from .agent import BaseAgent, AgentResult
from .workflow import BaseWorkflow


class OrchestrationMode(Enum):
    """编排模式"""
    SEQUENTIAL = "sequential"          # 顺序执行
    PARALLEL = "parallel"              # 并行执行
    HIERARCHICAL = "hierarchical"      # 层级执行(Manager-Worker)
    CONVERSATIONAL = "conversational"  # 对话协作模式
    PIPELINE = "pipeline"              # 流水线模式


@dataclass
class OrchestratorConfig:
    """编排器配置"""
    mode: OrchestrationMode
    max_workers: int = 5               # 最大并行Worker数
    timeout: int = 3600                # 整体超时(秒)
    retry_count: int = 3               # 失败重试次数
    retry_delay: int = 5               # 重试间隔(秒)
    human_in_loop: bool = False        # 是否需要人工介入
    checkpoint_enabled: bool = True    # 是否启用checkpoint
    checkpoint_interval: int = 60      # checkpoint间隔(秒)
    verbose: bool = False              # 是否输出详细日志


@dataclass
class ExecutionStatus:
    """执行状态"""
    execution_id: str
    status: str  # pending, running, paused, completed, failed, cancelled
    current_step: str
    progress: float  # 0.0 - 1.0
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
    result: Optional[AgentResult] = None


class BaseOrchestrator(ABC):
    """编排器基类
    
    负责协调多个Agent或Workflow的执行
    """
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._agents: dict[str, BaseAgent] = {}
        self._workflows: dict[str, BaseWorkflow] = {}
        self._executions: dict[str, ExecutionStatus] = {}
        self._current_execution_id: Optional[str] = None
    
    def register_agent(self, agent: BaseAgent) -> None:
        """注册Agent"""
        self._agents[agent.config.name] = agent
    
    def unregister_agent(self, name: str) -> bool:
        """注销Agent"""
        if name in self._agents:
            del self._agents[name]
            return True
        return False
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取Agent"""
        return self._agents.get(name)
    
    def list_agents(self) -> list[str]:
        """列出所有Agent"""
        return list(self._agents.keys())
    
    def register_workflow(self, workflow: BaseWorkflow) -> None:
        """注册Workflow"""
        self._workflows[workflow.config.name] = workflow
    
    def get_workflow(self, name: str) -> Optional[BaseWorkflow]:
        """获取Workflow"""
        return self._workflows.get(name)
    
    def list_workflows(self) -> list[str]:
        """列出所有Workflow"""
        return list(self._workflows.keys())
    
    @abstractmethod
    async def execute(self, task: str, context: dict = None) -> AgentResult:
        """执行任务
        
        Args:
            task: 任务描述
            context: 执行上下文
            
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    async def execute_workflow(self, workflow_name: str, input: dict) -> dict:
        """执行指定Workflow
        
        Args:
            workflow_name: Workflow名称
            input: 输入数据
            
        Returns:
            Workflow执行结果
        """
        pass
    
    @abstractmethod
    async def pause(self, execution_id: str) -> bool:
        """暂停执行"""
        pass
    
    @abstractmethod
    async def resume(self, execution_id: str) -> bool:
        """恢复执行"""
        pass
    
    @abstractmethod
    async def cancel(self, execution_id: str) -> bool:
        """取消执行"""
        pass
    
    def get_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """获取执行状态"""
        return self._executions.get(execution_id)
    
    def list_executions(self) -> list[ExecutionStatus]:
        """列出所有执行"""
        return list(self._executions.values())
    
    @abstractmethod
    def visualize(self) -> str:
        """可视化编排结构"""
        pass
    
    def _generate_execution_id(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    def _create_execution_status(self, execution_id: str) -> ExecutionStatus:
        from datetime import datetime
        return ExecutionStatus(
            execution_id=execution_id,
            status="pending",
            current_step="",
            progress=0.0,
            start_time=datetime.now().isoformat()
        )
    
    def __repr__(self) -> str:
        return f"Orchestrator(mode={self.config.mode.value}, agents={len(self._agents)}, workflows={len(self._workflows)})"