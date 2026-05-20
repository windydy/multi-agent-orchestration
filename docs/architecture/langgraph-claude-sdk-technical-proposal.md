# LangGraph + Claude Agent SDK 编排工作流技术方案

> 版本: 1.0
> 日期: 2026-05-19
> 作者: Hermes Agent

---

## 一、方案概述

### 1.1 设计目标

构建一个可编排的多Agent工作流系统：
- **LangGraph**: 编排层，负责状态管理、流程控制、条件路由、持久化
- **Claude Agent SDK**: 执行层，每个节点内的Agent使用Claude SDK执行具体任务

### 1.2 核心价值

| 特性 | LangGraph贡献 | Claude SDK贡献 |
|------|--------------|---------------|
| 状态持久化 | ✓ Checkpointer | ✓ 会话记忆 |
| 条件路由 | ✓ Conditional Edges | - |
| 工具调用 | - | ✓ Built-in Tools |
| 人工干预 | ✓ Interrupt | ✓ Hooks |
| 追踪调试 | ✓ LangSmith | ✓ 内置Tracing |

### 1.3 目标场景

实现完整的开发流水线：
```
需求分析Agent → 技术设计Agent → 开发Agent → Reviewer Agent → Tester Agent
```

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Application Layer                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     Workflow Runner                           │    │
│  │  • 任务提交                                                   │    │
│  │  • 状态查询                                                   │    │
│  │  • 人工干预                                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
├───────────────────────────────┼─────────────────────────────────────┤
│                         Orchestration Layer                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      LangGraph                                │    │
│  │                                                               │    │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │    │
│  │   │需求分析 │───▶│技术设计 │───▶│ 开发    │───▶│ Review  │   │    │
│  │   │  Node   │    │  Node   │    │  Node   │    │  Node   │   │    │
│  │   └─────────┘    └─────────┘    └─────────┘    └─────────┘   │    │
│  │        │              │              │              │         │    │
│  │        ▼              ▼              ▼              ▼         │    │
│  │   ┌──────────────────────────────────────────────────────┐   │    │
│  │   │              Conditional Edges                        │   │    │
│  │   │  • needs_revision → 返回开发节点                       │   │    │
│  │   │  • tests_failed → 返回修复节点                         │   │    │
│  │   │  • approved → 继续下一节点                             │   │    │
│  │   └──────────────────────────────────────────────────────┘   │    │
│  │                                                               │    │
│  │   State: TypedDict with messages, results, next_agent...      │    │
│  │   Checkpointer: SqliteSaver / MemorySaver                     │    │
│  │   Interrupt: ["review", "deploy"] 人工审批点                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
├───────────────────────────────┼─────────────────────────────────────┤
│                         Execution Layer                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Claude Agent SDK                           │    │
│  │                                                               │    │
│  │   ┌───────────────────────────────────────────────────────┐  │    │
│  │   │                 Claude Agents                          │  │    │
│  │   │                                                       │  │    │
│  │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │  │    │
│  │   │  │ Requirements│ │   Designer  │ │  Developer  │      │  │    │
│  │   │  │   Agent     │ │   Agent     │ │   Agent     │      │  │    │
│  │   │  └─────────────┘ └─────────────┘ └─────────────┘      │  │    │
│  │   │                                                       │  │    │
│  │   │  ┌─────────────┐ ┌─────────────┐                      │  │    │
│  │   │  │  Reviewer   │ │   Tester    │                      │  │    │
│  │   │  │   Agent     │ │   Agent     │                      │  │    │
│  │   │  └─────────────┘ └─────────────┘                      │  │    │
│  │   └───────────────────────────────────────────────────────┘  │    │
│  │                                                               │    │
│  │   ┌───────────────────────────────────────────────────────┐  │    │
│  │   │              Built-in Tools                             │  │    │
│  │   │  • read_file    • write_file    • edit_file            │  │    │
│  │   │  • bash         • search       • task                  │  │    │
│  │   └───────────────────────────────────────────────────────┘  │    │
│  │                                                               │    │
│  │   ┌───────────────────────────────────────────────────────┐  │    │
│  │   │                 Hooks System                            │  │    │
│  │   │  • pre_tool_call   - 工具调用前拦截                      │  │    │
│  │   │  • post_tool_call  - 工具调用后记录                      │  │    │
│  │   │  • safety_check    - 危险命令阻止                       │  │    │
│  │   └───────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │                                      │
├───────────────────────────────┼─────────────────────────────────────┤
│                        Infrastructure Layer                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Supporting Services                        │    │
│  │  • Tracing (LangSmith / Console)                              │    │
│  │  • Persistence (SQLite / Redis)                               │    │
│  │  • Configuration (YAML / JSON)                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 ClaudeAgentWrapper

将Claude Agent SDK封装为LangGraph兼容的节点函数：

```python
from typing import TypedDict, Any
from claude_agent_sdk import Agent, Runner

class ClaudeAgentWrapper:
    """Claude Agent SDK适配器 - 封装为LangGraph节点"""
    
    def __init__(
        self,
        name: str,
        model: str = "claude-sonnet-4",
        system_prompt: str = "",
        tools: list[str] = None,
        hooks: list[callable] = None
    ):
        self.name = name
        self.agent = Agent(
            name=name,
            model=model,
            instructions=system_prompt,
            tools=tools or ["read_file", "write_file", "bash", "search"],
        )
        self.runner = Runner(self.agent)
        self._hooks = hooks or []
    
    async def __call__(self, state: TypedDict) -> dict:
        """LangGraph节点函数签名"""
        # 1. 从state提取输入
        task = state.get("task", "")
        context = state.get("context", {})
        
        # 2. 构建Claude Agent输入
        input_message = self._build_input(task, context, state)
        
        # 3. 执行Claude Agent
        result = await self.runner.run(input_message)
        
        # 4. 更新state并返回
        return self._update_state(state, result)
    
    def _build_input(self, task: str, context: dict, state: dict) -> str:
        """构建Agent输入消息"""
        # 合合历史消息、当前任务、上下文
        messages = state.get("messages", [])
        previous_results = state.get("results", {})
        
        input_parts = [
            f"当前任务: {task}",
            f"角色: {self.name}",
            f"上下文: {json.dumps(context, ensure_ascii=False)}",
        ]
        
        if previous_results:
            input_parts.append(f"前置节点结果: {json.dumps(previous_results, ensure_ascii=False)}")
        
        return "\n\n".join(input_parts)
    
    def _update_state(self, state: dict, result: Any) -> dict:
        """更新工作流状态"""
        return {
            "messages": state.get("messages", []) + [{
                "role": self.name,
                "content": result.output,
                "timestamp": datetime.now().isoformat()
            }],
            "results": {**state.get("results", {}), self.name: result.output},
            "current_agent": self.name,
            "next_agent": self._determine_next(result)
        }
    
    def _determine_next(self, result: Any) -> str:
        """根据结果确定下一个Agent"""
        # 可通过result中的特定标记决定路由
        if result.output and "NEEDS_REVISION" in result.output:
            return "developer"
        return "next"  # 默认继续
```

#### 2.2.2 WorkflowState

定义全局状态结构：

```python
from typing import TypedDict, Annotated, Sequence
import operator

class WorkflowState(TypedDict):
    """开发流水线全局状态"""
    
    # 基础信息
    task: str                    # 原始任务描述
    project_path: str            # 项目目录
    
    # 消息历史 (累加模式)
    messages: Annotated[Sequence[dict], operator.add]
    
    # 各阶段结果
    requirements: dict           # 需求分析结果
    design: dict                 # 技术设计结果
    code_changes: dict           # 代码变更记录
    review_result: dict          # Review结果
    test_result: dict            # 测试结果
    
    # 控制流
    current_stage: str           # 当前阶段
    next_stage: str              # 下一阶段
    iteration_count: int         # 迭代计数
    needs_revision: bool         # 是否需要修订
    
    # 人工审批
    human_approval: bool         # 人工审批状态
    approval_comment: str        # 审批意见
    
    # 元数据
    start_time: str              # 开始时间
    end_time: str                # 结束时间
    total_cost: float            # 累计成本
```

#### 2.2.3 LangGraph Workflow Builder

工作流构建器：

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.pregel import Interrupt

class DevelopmentPipelineBuilder:
    """开发流水线构建器"""
    
    def __init__(self, checkpointer_path: str = "./checkpoints.db"):
        self.checkpointer = SqliteSaver.from_conn_string(checkpointer_path)
        self.agents: dict[str, ClaudeAgentWrapper] = {}
    
    def register_agent(self, name: str, wrapper: ClaudeAgentWrapper):
        """注册Agent"""
        self.agents[name] = wrapper
    
    def build(self) -> StateGraph:
        """构建工作流"""
        
        # 1. 创建状态图
        workflow = StateGraph(WorkflowState)
        
        # 2. 添加节点
        workflow.add_node("requirements", self.agents["requirements"])
        workflow.add_node("design", self.agents["design"])
        workflow.add_node("develop", self.agents["developer"])
        workflow.add_node("review", self.agents["reviewer"])
        workflow.add_node("test", self.agents["tester"])
        workflow.add_node("fix", self.agents["fixer"])
        
        # 3. 添加条件边
        workflow.add_conditional_edges(
            "review",
            self._review_router,
            {
                "approved": "test",
                "revision": "develop",
                "human": "human_review"
            }
        )
        
        workflow.add_conditional_edges(
            "test",
            self._test_router,
            {
                "pass": END,
                "fail": "fix",
                "human": "human_review"
            }
        )
        
        # 4. 添加固定边
        workflow.add_edge("requirements", "design")
        workflow.add_edge("design", "develop")
        workflow.add_edge("develop", "review")
        workflow.add_edge("fix", "test")
        
        # 5. 设置入口
        workflow.set_entry_point("requirements")
        
        # 6. 编译 (带中断点和持久化)
        return workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["review", "test"]  # 人工审批点
        )
    
    def _review_router(self, state: WorkflowState) -> str:
        """Review节点路由决策"""
        result = state.get("review_result", {})
        
        if result.get("approved"):
            return "approved"
        elif result.get("needs_revision"):
            return "revision"
        else:
            return "human"  # 需人工介入
    
    def _test_router(self, state: WorkflowState) -> str:
        """Test节点路由决策"""
        result = state.get("test_result", {})
        
        if result.get("passed"):
            return "pass"
        elif result.get("fixable"):
            return "fail"
        else:
            return "human"
```

---

## 三、Agent角色定义

### 3.1 需求分析Agent (Requirements Agent)

```python
REQUIREMENTS_AGENT_CONFIG = {
    "name": "requirements_analyst",
    "model": "claude-opus-4",  # 高级模型做分析
    "system_prompt": """
    你是需求分析专家。你的职责是：
    
    1. 分析用户需求，提取关键功能点
    2. 识别技术约束和依赖
    3. 澄清模糊需求，提出问题
    4. 输出结构化的需求文档
    
    输出格式：
    - 功能列表
    - 技术要求
    - 边界条件
    - 待澄清问题
    
    使用search工具查找相关代码，使用read_file理解现有结构。
    """,
    "tools": ["read_file", "search", "bash"],
    "temperature": 0.3
}
```

### 3.2 技术设计Agent (Designer Agent)

```python
DESIGNER_AGENT_CONFIG = {
    "name": "technical_designer",
    "model": "claude-opus-4",
    "system_prompt": """
    你是技术架构师。你的职责是：
    
    1. 根据需求设计技术方案
    2. 选择合适的技术栈和架构模式
    3. 设计模块划分和接口定义
    4. 输出详细的技术设计文档
    
    输出格式：
    - 架构图描述
    - 模块设计
    - 接口定义
    - 数据结构
    
    基于requirements_analyst的结果继续设计。
    """,
    "tools": ["read_file", "write_file", "search"],
    "temperature": 0.2
}
```

### 3.3 开发Agent (Developer Agent)

```python
DEVELOPER_AGENT_CONFIG = {
    "name": "developer",
    "model": "claude-sonnet-4",  # 平衡成本
    "system_prompt": """
    你是开发工程师。你的职责是：
    
    1. 根据技术设计实现代码
    2. 编写单元测试
    3. 遵循项目代码规范
    4. 记录代码变更
    
    输出格式：
    - 新增文件列表
    - 修改文件列表
    - 关键代码说明
    
    使用write_file创建文件，使用edit_file修改现有代码。
    使用bash执行测试验证。
    
    如果Review要求修改，使用 [NEEDS_REVISION] 标记。
    """,
    "tools": ["read_file", "write_file", "edit_file", "bash", "search"],
    "temperature": 0.1,
    "hooks": [
        # 阻止危险命令
        lambda tool, args: {"block": True} if "rm -rf" in args.get("command", "") else {"allow": True}
    ]
}
```

### 3.4 Reviewer Agent

```python
REVIEWER_AGENT_CONFIG = {
    "name": "code_reviewer",
    "model": "claude-opus-4",
    "system_prompt": """
    你是代码审查专家。你的职责是：
    
    1. 审查代码质量和风格
    2. 检查潜在安全问题
    3. 验证是否符合设计要求
    4. 提出修改建议
    
    输出格式：
    - approved: true/false
    - issues: 问题列表
    - suggestions: 改进建议
    
    如果发现问题需要修改，设置 approved=false 并说明原因。
    """,
    "tools": ["read_file", "search"],
    "temperature": 0.0
}
```

### 3.5 Tester Agent

```python
TESTER_AGENT_CONFIG = {
    "name": "qa_tester",
    "model": "claude-sonnet-4",
    "system_prompt": """
    你是测试工程师。你的职责是：
    
    1. 运行单元测试
    2. 执行集成测试
    3. 验证功能完整性
    4. 报告测试结果
    
    输出格式：
    - passed: true/false
    - coverage: 覆盖率
    - failures: 失败测试列表
    - fixable: 是否可自动修复
    
    使用bash执行pytest等测试工具。
    """,
    "tools": ["bash", "read_file", "search"],
    "temperature": 0.0
}
```

---

## 四、核心流程

### 4.1 正常流程

```
START
  │
  ▼
[requirements_analyst]
  │ 分析需求，输出需求文档
  ▼
[technical_designer]
  │ 设计方案，输出技术设计
  ▼
[developer]
  │ 实现代码，编写测试
  ▼
[review] ◄── INTERRUPT (人工审批可选)
  │ 审查代码质量
  ├─ approved? ──────▶ [test]
  │                       │ 运行测试
  │                       ▼
  │                   [test] ◄── INTERRUPT (人工审批可选)
  │                       │
  │                       ├─ passed? ──────▶ END
  │                       │
  │                       └─ fixable? ─────▶ [fixer]
  │                                            │ 修复代码
  │                                            ▼
  │                                        [test] (循环)
  │
  └─ needs_revision? ──▶ [developer] (返回修改)
```

### 4.2 中断恢复流程

```python
# 提交任务
thread_id = "task_001"
result = app.invoke(
    {"task": "实现用户登录功能"},
    config={"configurable": {"thread_id": thread_id}}
)

# 工作流在review节点中断，等待人工审批

# 查询当前状态
state = app.get_state(config={"configurable": {"thread_id": thread_id}})
print(f"当前阶段: {state.values['current_stage']}")
print(f"Review结果: {state.values['review_result']}")

# 人工审批后继续
if human_approves:
    # 更新状态
    app.update_state(
        config={"configurable": {"thread_id": thread_id}},
        values={"human_approval": True, "approval_comment": "通过"}
    )
    # 继续执行
    result = app.invoke(None, config={"configurable": {"thread_id": thread_id}})
```

---

## 五、目录结构

```
langgraph-claude-pipeline/
│
├── pyproject.toml              # 项目配置
├── README.md                   # 项目说明
├── config/
│   ├── agents.yaml             # Agent配置
│   └── workflow.yaml           # 工作流配置
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                   # 核心抽象
│   │   ├── __init__.py
│   │   ├── state.py            # WorkflowState定义
│   │   ├── wrapper.py          # ClaudeAgentWrapper
│   │   ├── builder.py          # WorkflowBuilder
│   │   └── runner.py           # WorkflowRunner
│   │
│   ├── agents/                 # Agent实现
│   │   ├── __init__.py
│   │   ├── requirements.py     # 需求分析Agent
│   │   ├── designer.py         # 技术设计Agent
│   │   ├── developer.py        # 开发Agent
│   │   ├── reviewer.py         # Review Agent
│   │   ├── tester.py           # 测试Agent
│   │   └── fixer.py            # 修复Agent
│   │
│   ├── hooks/                  # Hooks实现
│   │   ├── __init__.py
│   │   ├── safety.py           # 安全检查Hook
│   │   └── logging.py          # 日志记录Hook
│   │
│   └── utils/                  # 工具函数
│   │   ├── __init__.py
│   │   ├── tracing.py          # 追踪工具
│   │   └── cost.py             # 成本计算
│   │
│   └── cli/                    # CLI接口
│       ├── __init__.py
│       └ main.py               # CLI入口
│
├── examples/                   # 示例
│   ├── simple_pipeline.py      # 简单流水线
│   ├── dev_pipeline.py         # 开发流水线
│   └── bug_fix.py              # Bug修复流程
│
├── tests/                      # 测试
│   ├── test_wrapper.py
│   ├── test_builder.py
│   └── test_pipeline.py
│
└── checkpoints/                # 检查点存储
    └── .gitkeep
```

---

## 六、依赖清单

```toml
[project]
name = "langgraph-claude-pipeline"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "langgraph>=0.2.0",
    "claude-agent-sdk>=0.1.0",  # Anthropic官方SDK
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "sqlite3",  # 内置
    "aiofiles>=23.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
]
```

---

## 七、关键技术决策

### 7.1 为什么选LangGraph做编排？

| 能力 | LangGraph | 其他选项 |
|------|-----------|----------|
| 状态持久化 | ✓ SqliteSaver原生支持 | 需自建 |
| 条件路由 | ✓ Conditional Edges灵活 | Swarm仅Handoff |
| 人工干预 | ✓ Interrupt机制完善 | 需Hack |
| 可视化 | ✓ Mermaid原生 | 有限 |
| 调试 | ✓ LangSmith集成 | 各家自建 |

### 7.2 为什么选Claude Agent SDK做执行？

| 能力 | Claude SDK | 其他选项 |
|------|------------|----------|
| 代码能力 | ✓ Claude Code专业 | 通用LLM |
| 内置工具 | ✓ 文件/命令/Search | 需自建 |
| Hooks | ✓ 拦截机制完善 | 需自建 |
| 成本 | ✓ 按使用量计费 | 固定成本 |

### 7.3 架构优势

1. **职责清晰**: 编排和执行分离
2. **可替换性**: Claude SDK可替换为Deep Agents或其他
3. **可观测性**: LangGraph + LangSmith + Claude SDK内置追踪
4. **可扩展性**: 易于添加新Agent和新工作流

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Claude API限流 | 执行中断 | 添加重试机制，使用Queue |
| 状态膨胀 | 内存溢出 | 定期压缩，只保留关键信息 |
| 循环死锁 | 无限迭代 | 设置max_iterations限制 |
| 工具滥用 | 安全问题 | Hooks强制拦截危险命令 |
| 成本失控 | 费用超标 | 成本计算Hook，设置阈值 |

---

## 九、下一步计划

### Phase 1: 核心框架 (Day 1)
- 实现ClaudeAgentWrapper
- 实现WorkflowState
- 实现基础WorkflowBuilder

### Phase 2: Agent实现 (Day 1-2)
- 实现各角色Agent
- 配置System Prompt
- 添加Hooks

### Phase 3: 工作流集成 (Day 2)
- 构建完整开发流水线
- 添加条件路由
- 实现中断恢复

### Phase 4: 测试验证 (Day 2-3)
- 单元测试
- 集成测试
- 示例运行

### Phase 5: 文档完善 (Day 3)
- README完善
- API文档
- 使用示例

---

## 十、验收标准

1. ✓ 可以提交任务并自动执行流水线
2. ✓ 在Review/Test节点可以暂停等待人工审批
3. ✓ 审批后可以继续执行
4. ✓ 可以查询执行状态和历史
5. ✓ 条件路由正确工作 (revision返回develop)
6. ✓ Hooks拦截危险命令
7. ✓ 成本可追踪
8. ✓ 有完整的测试覆盖

---

*方案完成，待Review验证*