# 核心抽象设计

## 设计目标

1. **框架无关:** 提供统一抽象，可切换底层实现
2. **可扩展:** 易于添加新Agent、工具、编排模式
3. **可观测:** 完整的执行追踪和状态监控
4. **可测试:** 支持单元测试和集成测试

## 核心接口

### Agent 抽象

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum

class AgentRole(Enum):
    WORKER = "worker"
    MANAGER = "manager"
    SPECIALIST = "specialist"
    COORDINATOR = "coordinator"

@dataclass
class AgentConfig:
    name: str
    role: AgentRole
    description: str
    model: str
    tools: list[str]
    max_iterations: int = 10
    timeout: int = 300

@dataclass
class AgentResult:
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict = None

class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = {}
    
    @abstractmethod
    async def run(self, input: Any, context: dict = None) -> AgentResult:
        """执行Agent任务"""
        pass
    
    @abstractmethod
    async def plan(self, task: str) -> list[str]:
        """规划任务步骤"""
        pass
    
    def update_state(self, key: str, value: Any):
        """更新内部状态"""
        self.state[key] = value
    
    def get_state(self, key: str) -> Any:
        """获取内部状态"""
        return self.state.get(key)
```

### Workflow 抽象

```python
from typing import Callable, Awaitable
from dataclasses import dataclass, field

NodeFunction = Callable[[dict], Awaitable[dict]]

@dataclass
class Node:
    id: str
    name: str
    agent: BaseAgent
    timeout: int = 300
    retry: int = 3
    on_success: str = None  # 下一个节点ID
    on_failure: str = None  # 失败时跳转的节点ID

@dataclass
class Edge:
    source: str
    target: str
    condition: Callable[[dict], bool] = None  # 条件边

@dataclass
class WorkflowConfig:
    name: str
    description: str
    nodes: list[Node]
    edges: list[Edge]
    entry_point: str
    checkpointer: Any = None  # 状态持久化器

class BaseWorkflow(ABC):
    """工作流基类"""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.graph = self._build_graph()
        self.current_node = config.entry_point
    
    @abstractmethod
    def _build_graph(self) -> Any:
        """构建执行图"""
        pass
    
    @abstractmethod
    async def run(self, input: dict) -> dict:
        """执行工作流"""
        pass
    
    @abstractmethod
    async def step(self, state: dict) -> dict:
        """执行单步"""
        pass
    
    @abstractmethod
    def get_state(self) -> dict:
        """获取当前状态"""
        pass
    
    @abstractmethod
    def save_checkpoint(self) -> str:
        """保存检查点"""
        pass
    
    @abstractmethod
    def restore_checkpoint(self, checkpoint_id: str):
        """恢复检查点"""
        pass
```

### State 抽象

```python
from typing import Any, Optional
from datetime import datetime
import json

@dataclass
class StateUpdate:
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    node_id: str

class BaseState(ABC):
    """状态管理基类"""
    
    @abstractmethod
    def get(self, key: str) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any):
        pass
    
    @abstractmethod
    def update(self, updates: dict):
        pass
    
    @abstractmethod
    def history(self, key: str = None) -> list[StateUpdate]:
        """获取状态变更历史"""
        pass
    
    @abstractmethod
    def snapshot(self) -> dict:
        """获取完整快照"""
        pass
    
    @abstractmethod
    def restore(self, snapshot: dict):
        """从快照恢复"""
        pass

class InMemoryState(BaseState):
    """内存状态管理"""
    
    def __init__(self):
        self._state = {}
        self._history = []
    
    def get(self, key: str) -> Any:
        return self._state.get(key)
    
    def set(self, key: str, value: Any):
        old = self._state.get(key)
        self._state[key] = value
        self._history.append(StateUpdate(
            key=key,
            old_value=old,
            new_value=value,
            timestamp=datetime.now(),
            node_id=""
        ))
    
    def history(self, key: str = None) -> list[StateUpdate]:
        if key:
            return [u for u in self._history if u.key == key]
        return self._history
```

### Orchestrator 抽象

```python
from enum import Enum
from typing import Optional

class OrchestrationMode(Enum):
    SEQUENTIAL = "sequential"      # 顺序执行
    PARALLEL = "parallel"          # 并行执行
    HIERARCHICAL = "hierarchical"  # 层级执行
    CONVERSATIONAL = "conversational"  # 对话模式

@dataclass
class OrchestratorConfig:
    mode: OrchestrationMode
    max_workers: int = 5
    timeout: int = 3600
    retry_policy: dict = None
    human_in_loop: bool = False
    checkpoint_enabled: bool = True

class BaseOrchestrator(ABC):
    """编排器基类"""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.agents: dict[str, BaseAgent] = {}
        self.workflows: dict[str, BaseWorkflow] = {}
        self.state: BaseState = None
    
    @abstractmethod
    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        pass
    
    @abstractmethod
    def register_workflow(self, workflow: BaseWorkflow):
        """注册工作流"""
        pass
    
    @abstractmethod
    async def execute(self, task: str, context: dict = None) -> AgentResult:
        """执行任务"""
        pass
    
    @abstractmethod
    async def pause(self, execution_id: str):
        """暂停执行"""
        pass
    
    @abstractmethod
    async def resume(self, execution_id: str):
        """恢复执行"""
        pass
    
    @abstractmethod
    async def cancel(self, execution_id: str):
        """取消执行"""
        pass
    
    @abstractmethod
    def get_status(self, execution_id: str) -> dict:
        """获取执行状态"""
        pass
```

## 实现适配器

### LangGraph 适配器

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class LangGraphAdapter(BaseOrchestrator):
    """LangGraph适配器"""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config)
        self._checkpointer = MemorySaver() if config.checkpoint_enabled else None
    
    def register_agent(self, agent: BaseAgent):
        self.agents[agent.config.name] = agent
    
    async def execute(self, task: str, context: dict = None) -> AgentResult:
        # 构建LangGraph工作流
        graph = StateGraph(dict)
        
        for name, agent in self.agents.items():
            graph.add_node(name, lambda s: agent.run(s))
        
        # 根据mode配置边
        if self.config.mode == OrchestrationMode.SEQUENTIAL:
            agents = list(self.agents.keys())
            for i in range(len(agents) - 1):
                graph.add_edge(agents[i], agents[i + 1])
            graph.add_edge(agents[-1], END)
        
        app = graph.compile(checkpointer=self._checkpointer)
        result = await app.ainvoke(context or {"task": task})
        return AgentResult(success=True, output=result)
```

### AutoGen 适配器

```python
import autogen

class AutoGenAdapter(BaseOrchestrator):
    """AutoGen适配器"""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config)
        self._groupchat = None
        self._manager = None
    
    def register_agent(self, agent: BaseAgent):
        autogen_agent = autogen.ConversableAgent(
            name=agent.config.name,
            system_message=agent.config.description,
            llm_config={"model": agent.config.model}
        )
        self.agents[agent.config.name] = autogen_agent
    
    async def execute(self, task: str, context: dict = None) -> AgentResult:
        if self.config.mode == OrchestrationMode.CONVERSATIONAL:
            self._groupchat = autogen.GroupChat(
                agents=list(self.agents.values()),
                messages=[]
            )
            self._manager = autogen.GroupChatManager(self._groupchat)
            
            # 启动对话
            first_agent = list(self.agents.values())[0]
            first_agent.initiate_chat(self._manager, message=task)
            
            return AgentResult(success=True, output=self._groupchat.messages)
```

## 工具抽象

```python
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class ToolConfig:
    name: str
    description: str
    parameters: dict  # JSON Schema
    timeout: int = 60

@dataclass
class ToolResult:
    success: bool
    output: Any
    error: str = None

class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, config: ToolConfig):
        self.config = config
    
    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass
    
    def to_function_schema(self) -> dict:
        """转换为函数调用Schema"""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "parameters": self.config.parameters
        }

# 内置工具
class SearchTool(BaseTool):
    async def run(self, query: str) -> ToolResult:
        # 实现搜索逻辑
        pass

class CodeExecutionTool(BaseTool):
    async def run(self, code: str) -> ToolResult:
        # 实现代码执行
        pass
```

## 可观测性

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json

@dataclass
class Span:
    id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    attributes: dict = None
    events: list = None

class Tracer:
    """执行追踪器"""
    
    def __init__(self):
        self.spans: dict[str, Span] = {}
        self.current_span: Optional[Span] = None
    
    def start_span(self, name: str, attributes: dict = None) -> Span:
        span = Span(
            id=self._generate_id(),
            name=name,
            start_time=datetime.now(),
            attributes=attributes or {},
            events=[]
        )
        self.spans[span.id] = span
        return span
    
    def end_span(self, span_id: str, status: str = "success"):
        if span_id in self.spans:
            self.spans[span_id].end_time = datetime.now()
            self.spans[span_id].status = status
    
    def add_event(self, span_id: str, name: str, attributes: dict = None):
        if span_id in self.spans:
            self.spans[span_id].events.append({
                "name": name,
                "timestamp": datetime.now().isoformat(),
                "attributes": attributes or {}
            })
    
    def export(self) -> dict:
        return {
            span_id: {
                "name": span.name,
                "duration": (span.end_time - span.start_time).total_seconds() if span.end_time else None,
                "status": span.status,
                "attributes": span.attributes,
                "events": span.events
            }
            for span_id, span in self.spans.items()
        }
```

## 下一步

1. 实现 `src/core/` 目录下的核心类
2. 为LangGraph、AutoGen、CrewAI创建适配器
3. 添加单元测试
4. 实现Web UI可视化