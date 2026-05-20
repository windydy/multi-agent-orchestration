"""
Workflow抽象基类

定义工作流的构建和执行接口
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable, Optional
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """节点类型"""
    AGENT = "agent"     # Agent执行节点
    FUNCTION = "function"  # 函数节点
    CONDITION = "condition"  # 条件判断节点
    HUMAN = "human"     # 人工审核节点
    PARALLEL = "parallel"  # 并行执行节点


@dataclass
class Node:
    """工作流节点"""
    id: str
    name: str
    type: NodeType
    agent_name: Optional[str] = None  # 如果是Agent节点
    function: Optional[Callable] = None  # 如果是函数节点
    timeout: int = 300
    retry: int = 3
    on_success: Optional[str] = None  # 成功时的下一个节点
    on_failure: Optional[str] = None  # 失败时的下一个节点
    description: str = ""


@dataclass  
class Edge:
    """工作流边"""
    source: str  # 源节点ID
    target: str  # 目标节点ID
    condition: Optional[Callable[[dict], bool]] = None  # 条件函数
    label: str = ""  # 边的标签说明


@dataclass
class WorkflowConfig:
    """工作流配置"""
    name: str
    description: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    entry_point: str = ""  # 入口节点ID
    checkpointer: Any = None  # 状态持久化器
    timeout: int = 3600  # 整体超时
    max_iterations: int = 100  # 最大迭代次数防止死循环


class BaseWorkflow(ABC):
    """工作流基类
    
    所有工作流必须实现构建、执行、状态管理等方法
    """
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._graph: Any = None
        self._current_node: str = config.entry_point
        self._execution_history: list[dict] = []
        self._checkpoints: dict[str, dict] = {}
    
    @abstractmethod
    def _build_graph(self) -> Any:
        """构建执行图
        
        Returns:
            内部表示的执行图
        """
        pass
    
    @abstractmethod
    async def run(self, input: dict) -> dict:
        """执行工作流
        
        Args:
            input: 输入数据
            
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    async def step(self, state: dict) -> dict:
        """执行单步
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        pass
    
    @abstractmethod
    def get_state(self) -> dict:
        """获取当前状态"""
        pass
    
    def save_checkpoint(self) -> str:
        """保存检查点
        
        Returns:
            检查点ID
        """
        from datetime import datetime
        checkpoint_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._checkpoints[checkpoint_id] = {
            "current_node": self._current_node,
            "state": self.get_state(),
            "history": self._execution_history.copy()
        }
        return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """从检查点恢复
        
        Args:
            checkpoint_id: 检查点ID
            
        Returns:
            是否恢复成功
        """
        if checkpoint_id not in self._checkpoints:
            return False
        
        checkpoint = self._checkpoints[checkpoint_id]
        self._current_node = checkpoint["current_node"]
        self._execution_history = checkpoint["history"]
        return True
    
    def list_checkpoints(self) -> list[str]:
        """列出所有检查点"""
        return list(self._checkpoints.keys())
    
    def get_execution_history(self) -> list[dict]:
        """获取执行历史"""
        return self._execution_history
    
    def visualize(self) -> str:
        """可视化工作流
        
        Returns:
            ASCII或Mermaid格式的图
        """
        lines = ["graph TD"]
        for node in self.config.nodes:
            lines.append(f"    {node.id}[{node.name}]")
        for edge in self.config.edges:
            label = f"|{edge.label}|" if edge.label else ""
            lines.append(f"    {edge.source} -->{label} {edge.target}")
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"Workflow(name={self.config.name}, nodes={len(self.config.nodes)}, edges={len(self.config.edges)})"