"""
Agent抽象基类

定义所有Agent必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class AgentRole(Enum):
    """Agent角色类型"""
    WORKER = "worker"           # 执行具体任务
    MANAGER = "manager"         # 协调其他Agent
    SPECIALIST = "specialist"   # 领域专家
    COORDINATOR = "coordinator" # 流程协调者


@dataclass
class AgentConfig:
    """Agent配置"""
    name: str
    role: AgentRole
    description: str
    model: str = "gpt-4"
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 10
    timeout: int = 300
    temperature: float = 0.7
    system_prompt: str = ""


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    confidence: float = 1.0
    steps: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Agent基类
    
    所有Agent必须实现run和plan方法
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._state: dict = {}
        self._history: list[dict] = []
    
    @abstractmethod
    async def run(self, input: Any, context: dict = None) -> AgentResult:
        """执行Agent任务
        
        Args:
            input: 任务输入
            context: 执行上下文(包含全局状态等)
            
        Returns:
            AgentResult: 执行结果
        """
        pass
    
    @abstractmethod
    async def plan(self, task: str) -> list[str]:
        """规划任务步骤
        
        Args:
            task: 任务描述
            
        Returns:
            执行步骤列表
        """
        pass
    
    def update_state(self, key: str, value: Any) -> None:
        """更新Agent内部状态"""
        self._state[key] = value
        self._history.append({"key": key, "value": value, "timestamp": self._get_timestamp()})
    
    def get_state(self, key: str) -> Optional[Any]:
        """获取Agent内部状态"""
        return self._state.get(key)
    
    def clear_state(self) -> None:
        """清空内部状态"""
        self._state.clear()
    
    def get_history(self) -> list[dict]:
        """获取状态变更历史"""
        return self._history
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def __repr__(self) -> str:
        return f"Agent(name={self.config.name}, role={self.config.role.value})"


class SimpleAgent(BaseAgent):
    """简单Agent实现示例"""
    
    async def run(self, input: Any, context: dict = None) -> AgentResult:
        # 实际实现中会调用LLM
        return AgentResult(
            success=True,
            output=f"Processed: {input}",
            metadata={"agent": self.config.name}
        )
    
    async def plan(self, task: str) -> list[str]:
        return [f"Step 1: Analyze {task}", f"Step 2: Execute {task}"]