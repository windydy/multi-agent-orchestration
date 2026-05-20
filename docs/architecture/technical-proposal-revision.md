# 技术方案修订版

> 基于Review反馈修订
> 修订日期: 2026-05-19

---

## 修订内容

### 1. 架构对齐 - 复用已有src/core抽象

**ClaudeAgentWrapper继承BaseAgent:**

```python
from src.core.agent import BaseAgent, AgentConfig, AgentResult

class ClaudeAgentWrapper(BaseAgent):
    """Claude Agent SDK适配器 - 继承BaseAgent"""
    
    def __init__(self, config: AgentConfig, claude_config: dict = None):
        super().__init__(config)
        self.claude_config = claude_config or {}
        # Claude SDK初始化 (待API验证后确定)
        self._sdk_agent = None  # 延迟初始化
    
    async def run(self, input: Any, context: dict = None) -> AgentResult:
        """实现BaseAgent.run接口"""
        # 执行Claude SDK逻辑
        ...
    
    async def plan(self, task: str) -> list[str]:
        """实现BaseAgent.plan接口"""
        return []  # Claude SDK内部规划
```

### 2. 补充Fixer Agent配置

```python
FIXER_AGENT_CONFIG = {
    "name": "bug_fixer",
    "role": AgentRole.WORKER,
    "description": "根据测试失败信息修复代码",
    "model": "claude-sonnet-4",
    "system_prompt": """
    你是修复工程师。你的职责是：
    
    1. 分析测试失败信息
    2. 定位问题代码
    3. 修复bug
    4. 重新运行测试验证
    
    输出格式：
    - fix_summary: 修复概述
    - files_changed: 变更文件列表
    - test_result: 验证结果
    
    使用read_file理解代码，edit_file修改，bash运行测试。
    """,
    "tools": ["read_file", "edit_file", "bash", "search"],
    "temperature": 0.1
}
```

### 3. 状态管理适配

```python
# 方案：WorkflowState作为TypedDict数据结构，InMemoryState作为管理器
from typing import TypedDict, Annotated, Sequence
import operator
from src.core.state import BaseState, InMemoryState

class WorkflowState(TypedDict):
    """开发流水线状态数据结构"""
    task: str
    project_path: str
    messages: Annotated[Sequence[dict], operator.add]
    requirements: dict
    design: dict
    code_changes: dict
    review_result: dict
    test_result: dict
    current_stage: str
    next_stage: str
    iteration_count: int
    needs_revision: bool
    human_approval: bool
    approval_comment: str
    start_time: str
    end_time: str
    total_cost: float

class WorkflowStateManager(InMemoryState):
    """状态管理器 - 继承InMemoryState"""
    
    def __init__(self, initial_state: WorkflowState = None):
        super().__init__()
        if initial_state:
            for key, value in initial_state.items():
                self.set(key, value)
    
    def get_workflow_state(self) -> dict:
        """获取完整WorkflowState"""
        return self.snapshot()
    
    def update_stage(self, stage: str, result: dict):
        """更新阶段结果"""
        self.set("current_stage", stage)
        self.set(stage, result)
        self.set("iteration_count", self.get("iteration_count", 0) + 1)
```

### 4. 目录结构修订 - 复用已有代码

```
src/
├── core/                     # 已有抽象层（保持不变）
│   ├── agent.py             # BaseAgent
│   ├── state.py             # BaseState + InMemoryState
│   ├── workflow.py          # BaseWorkflow
│   ├── orchestrator.py     # BaseOrchestrator
│   ├── tool.py              # BaseTool
│   └── __init__.py
│
├── claude/                   # 新增：Claude SDK适配层
│   ├── __init__.py
│   ├── wrapper.py           # ClaudeAgentWrapper(BaseAgent)
│   ├── tools.py             # Claude内置工具适配
│   └── hooks.py             # Hooks实现
│
├── agents/                   # Agent实现（复用BaseAgent）
│   ├── __init__.py
│   ├── requirements.py      # RequirementsAgent(ClaudeAgentWrapper)
│   ├── designer.py          # DesignerAgent
│   ├── developer.py         # DeveloperAgent
│   ├── reviewer.py          # ReviewerAgent
│   ├── tester.py            # TesterAgent
│   └── fixer.py             # FixerAgent (新增)
│
├── workflows/               # Workflow实现（复用BaseWorkflow）
│   ├── __init__.py
│   ├── states.py            # WorkflowState + WorkflowStateManager
│   ├── builder.py           # DevelopmentPipelineBuilder
│   └── runner.py            # WorkflowRunner
│
└── cli/                     # CLI接口
    ├── __init__.py
    └── main.py
```

### 5. 技术验证计划

Phase 0 先验证Claude Agent SDK:

```bash
# 验证安装
pip install anthropic  # Claude API
# Claude Agent SDK 可能尚未正式发布，准备备选方案

# 备选方案1: 直接使用Anthropic API + Messages API
# 备选方案2: 使用Deep Agents (langchain-ai/deepagents)
```

---

## 执行计划更新

### Phase 0: 技术验证 (先执行)
- 验证Anthropic Claude API可用性
- 测试Claude Messages API工具调用
- 决定SDK选型 (Claude Agent SDK vs 直接API vs Deep Agents)

### Phase 1: 核心框架
- ClaudeAgentWrapper继承BaseAgent
- WorkflowStateManager继承InMemoryState
- 基础LangGraph集成

### Phase 2: Agent实现
- 实现6个Agent (含Fixer)
- 配置System Prompt和Hooks

### Phase 3: 工作流集成
- DevelopmentPipelineBuilder
- 条件路由
- 中断恢复

### Phase 4: 测试验证
- 单元测试
- 集成测试
- 示例运行

---

*修订完成，开始执行*