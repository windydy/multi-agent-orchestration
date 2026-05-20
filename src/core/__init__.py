"""
核心抽象模块

提供Agent、Workflow、State、Orchestrator的基础类定义
"""

from .agent import BaseAgent, AgentConfig, AgentResult, AgentRole
from .workflow import BaseWorkflow, WorkflowConfig, Node, Edge
from .state import BaseState, InMemoryState, StateUpdate
from .orchestrator import BaseOrchestrator, OrchestratorConfig, OrchestrationMode
from .tool import BaseTool, ToolConfig, ToolResult

__all__ = [
    "BaseAgent", "AgentConfig", "AgentResult", "AgentRole",
    "BaseWorkflow", "WorkflowConfig", "Node", "Edge",
    "BaseState", "InMemoryState", "StateUpdate",
    "BaseOrchestrator", "OrchestratorConfig", "OrchestrationMode",
    "BaseTool", "ToolConfig", "ToolResult",
]