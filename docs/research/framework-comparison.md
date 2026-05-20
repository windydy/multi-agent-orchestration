# 多Agent框架对比报告

> 调研日期: 2026-05-18

## 编排框架对比

| 框架 | Stars | 语言 | 特点 | 适用场景 |
|------|-------|------|------|----------|
| **LangGraph** | 32,334 | Python | 状态图编排、持久化、人工干预 | 自定义流水线 |
| **LangGraph-Swarm** | 1.5k | Python | 动态切换、记忆、协作 | Swarm模式多agent |
| **OpenAI Agents SDK** | 26k | Python | 轻量、Handoff、沙箱agent | 快速构建 |
| **Deep Agents** | 23k | Python | 开箱即用、子agent、文件系统 | 生产级流水线 |
| **DeerFlow** | 68k | Python | 沙箱、技能、子agent | 超级Agent |
| **Microsoft Agent Framework** | 10k | Python/.NET | 企业级、跨语言 | .NET环境 |
| **Pi** | 51k | TypeScript | 40+模型、订阅OAuth、Extensions | 单Agent编码 |
| **Claude Agent SDK** | 7k | Python/TS | Claude Code工具集、Hooks | Claude编码 |

---

## 核心概念对比

### LangGraph 状态图

```
┌─────────────────────────────────────────┐
│              StateGraph                  │
│  ┌──────┐    ┌──────┐    ┌──────┐       │
│  │ Node │───▶│ Node │───▶│ Node │       │
│  │(agent│    │(tool │    │(LLM) │       │
│  │ step)│    │ call)│    │call) │       │
│  └──────┘    └──────┘    └──────┘       │
│      │           │           │          │
│      └───Conditional Edge───▶┘          │
│                                         │
│  State: 消息、工具结果、上下文...        │
│  Checkpointing: 持久化状态              │
│  Interrupt: 人工干预点                  │
└─────────────────────────────────────────┘
```

**核心API**
```python
from langgraph.graph import StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver

# 定义状态
class AgentState(MessagesState):
    next: str

# 构建图
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.add_edge("agent", "tools")
graph.add_conditional_edges("tools", should_continue)

# 添加持久化
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)
```

---

### LangGraph-Swarm 动态协作

```python
from langgraph_swarm import create_handoff_tool, create_swarm

# 定义各专业Agent
requirements_agent = create_agent(
    model,
    tools=[create_handoff_tool(agent_name="designer")],
    system_prompt="你是需求分析专家",
    name="requirements_analyst",
)

design_agent = create_agent(
    model,
    tools=[create_handoff_tool(agent_name="developer")],
    system_prompt="你是技术架构师",
    name="designer",
)

# 创建Swarm
workflow = create_swarm(
    [requirements_agent, design_agent, develop_agent],
    default_active_agent="requirements_analyst"
)
```

---

### OpenAI Agents SDK Handoff

```python
from agents import Agent, Runner
from agents.handoffs import handoff

dev_agent = Agent(
    name="开发",
    instructions="实现代码",
    tools=[write_code, run_tests],
    handoffs=[handoff(agent_name="Reviewer")]
)

review_agent = Agent(
    name="Reviewer",
    instructions="审查代码",
    handoffs=[handoff(agent_name="开发"), handoff(agent_name="测试")]
)
```

---

## 关键功能对比

| 功能 | LangGraph | Swarm | OpenAI SDK | Deep Agents | DeerFlow | Pi |
|------|-----------|-------|------------|-------------|----------|-----|
| 状态持久化 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 人工干预 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 条件路由 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 记忆管理 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 子Agent委托 | 自定义 | Handoff | Handoff | ✓ 内置 | ✓ 并行 | ✗ |
| 文件系统 | 自定义 | 自定义 | 沙箱 | ✓ 内置 | ✓ 沙箱 | ✓ 工具 |
| Tracing | LangSmith | LangSmith | 内置 | LangSmith | 内置 | ✓ |
| MCP协议 | 需集成 | 需集成 | ✓ | 需集成 | ✓ Server | ✗ |

---

## 控制流模式

### 1. 显式控制流

```python
# LangGraph - 预定义顺序
graph.set_entry_point("requirements")
graph.add_edge("requirements", "design")
graph.add_edge("design", "develop")
graph.add_edge("develop", "review")
```

**适用**: 合规流程、审计要求、金融处理

### 2. 动态控制流

```python
# LangGraph - LLM决策
graph.add_conditional_edges("review",
    lambda s: "develop" if s["needs_revision"] else "test")
```

**适用**: 复杂业务、边缘情况、自适应流程

### 3. 层级控制流

```python
# 主管Agent调度子Agent
supervisor_agent = create_agent(
    tools=[developer_tool, reviewer_tool, tester_tool],
    system_prompt="根据任务类型选择合适的子Agent"
)
```

**适用**: 大规模Agent系统、避免协调复杂性

---

## 通信模式对比

| 模式 | 描述 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **Shared Scratchpad** | 所有Agent共享消息历史 | 完全透明、易调试 | 冗长、成本高 | 研究、审计 |
| **Handoff** | 明确传递目标和载荷 | 高效、可控 | 需定义路由 | 流水线、审批 |
| **Tool-Calling** | Agent作为工具被调用 | 动态路由、易扩展 | 单点协调 | 客服、调度 |

---

## 框架选择决策矩阵

| 需求 | 推荐 | 原因 |
|------|------|------|
| **快速搭建生产流水线** | Deep Agents | 开箱即用，子agent内置 |
| **完全自定义流程** | LangGraph | 状态图完全控制 |
| **动态协作/灵活切换** | LangGraph-Swarm | 动态Handoff |
| **OpenAI生态** | OpenAI Agents SDK | 轻量、内置Tracing |
| **Claude编码任务** | Claude Agent SDK | Claude Code工具集 |
| **单Agent编码** | Pi | 40+模型、订阅OAuth |
| **企业级可靠性** | Temporal + LangGraph | 持久执行保证 |
| **研究原型** | AutoGen | 会话式协作 |

---

## 推荐方案

### 开发流水线架构

```
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph 编排层                           │
│                                                               │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐       │
│  │需求分析 │──▶│技术设计 │──▶│ 开发    │──▶│ Review  │       │
│  │ Agent   │   │ Agent   │   │ Agent   │   │ Agent   │       │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘       │
│       │             │             │             │             │
│       ▼             ▼             ▼             ▼             │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Agent Harness (Deep Agents)             │     │
│  │  • Skills: requirements/design/dev/review/test       │     │
│  │  • Tools: 文件读写、代码执行、Git操作                 │     │
│  │  • Memory: 短期(会话) + 持久(跨会话)                  │     │
│  │  • Sub-agents: 并行探索、结构化结果                   │     │
│  │  • Context Management: 自动压缩                       │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  Checkpointer: 持久化状态，支持暂停/恢复                      │
│  Interrupt: 人工审批点                                        │
└──────────────────────────────────────────────────────────────┘
```

### 编码阶段增强

```
开发Agent = Deep Agents + Claude Code MCP

Deep Agents提供:
• Skills (编码模板)
• Sub-agents (代码探索)
• Memory (记住编码风格)
• Context Management (压缩长对话)

Claude Code MCP提供:
• Read/Write/Edit 工具
• Bash执行
• Git工作流
• 代码理解
```

---

## 参考资料

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph-Swarm](https://github.com/langchain-ai/langgraph-swarm-py)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Deep Agents](https://github.com/langchain-ai/deepagents)
- [DeerFlow](https://github.com/bytedance/deer-flow)
- [Pi](https://github.com/earendil-works/pi)
- [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview)