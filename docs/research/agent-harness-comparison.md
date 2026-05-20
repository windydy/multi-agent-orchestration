# Agent Harness 深度调研报告

> 调研日期: 2026-05-18

## 概述

Agent Harness 是构建AI Agent应用的基础框架，提供模型接入、工具调用、记忆管理、状态持久化等核心能力。本报告对比三大主流Agent Harness：Deep Agents (LangChain官方)、Claude Agent SDK (Anthropic官方)、Pi (社区开源)。

---

## 一、Deep Agents (LangChain官方)

### 基本信息

| 项目 | langchain-ai/deepagents |
|------|-------------------------|
| **Stars** | 22,938 |
| **语言** | Python |
| **出品方** | LangChain官方 |
| **定位** | 开箱即用的Agent Harness，LangGraph兼容 |
| **版本** | 活跃开发 |

### 核心特性

```
Deep Agents 架构:
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Model     │  │    Tools     │  │    Memory    │       │
│  │  (任意LLM)   │  │ (自定义注册) │  │ (短期+持久)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Skills     │  │ Sub-agents   │  │  Filesystem  │       │
│  │  (按需加载)  │  │ (隔离上下文) │  │ (多后端)     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LangGraph 编排层                          │   │
│  │  • StateGraph (状态节点图)                             │   │
│  │  • Checkpointer (持久化)                               │   │
│  │  • Interrupt (人工干预)                                │   │
│  │  • Conditional Edges (动态路由)                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Tracing: LangSmith / Langfuse                              │
└─────────────────────────────────────────────────────────────┘
```

### 六大核心能力

#### 1. Skills (技能系统)

Skills是可复用的任务知识，按需加载，减少上下文噪音。

```
Skills结构:
my-skill/
├── SKILL.md              # Required: frontmatter + instructions
├── scripts/              # Helper scripts (Python/Bash)
├── references/           # Detailed docs (按需加载)
└── templates/            # Templates and configs
    └── example.json

Frontmatter:
---
name: my-skill
description: 什么时候用什么技能
allowed-tools: read write bash  # 预批准工具
---
```

**Skills加载路径:**
- Global: `~/.agents/skills/`
- Project: `.agents/skills/`
- CLI: `--skill <path>`
- 配置: `skills: ["path1", "path2"]`

#### 2. Sub-agents (子Agent委托)

Sub-agents在隔离上下文中执行子任务，结果摘要返回父Agent。

```python
from deepagents import Agent, SubAgent

# 定义子Agent
research_subagent = SubAgent(
    name="research",
    model="claude-sonnet-4",
    tools=[web_search, read_file],
    max_steps=10
)

# 父Agent委托子任务
main_agent = Agent(
    model="claude-opus-4",
    subagents=[research_subagent, code_subagent],
    system_prompt="""
    复杂研究任务委托给 research 子Agent。
    代码探索委托给 code 子Agent。
    """
)

# 调用
result = main_agent.run("研究LangGraph的架构并总结")
# main_agent收到摘要结果，而非完整研究过程
```

**Sub-agents优势:**
- 隔离上下文 - 子任务不污染父Agent对话
- 摘要返回 - 只返回关键结果
- 并行执行 - 多个子Agent同时工作
- 专业化 - 每个子Agent专注特定任务

#### 3. Memory (记忆系统)

```
Memory架构:
┌─────────────────────────────────────────┐
│            Memory Manager               │
│                                         │
│  Short-term Memory (会话内)             │
│  • 对话历史                             │
│  • 工具调用结果                         │
│  • 当前任务状态                         │
│                                         │
│  Long-term Memory (跨会话)              │
│  • 用户偏好                             │
│  • 项目惯例                             │
│  • 过往经验                             │
│                                         │
│  Context Management                     │
│  • 自动压缩                             │
│  • 关键信息保留                         │
│  • 滑动窗口                             │
└─────────────────────────────────────────┘
```

#### 4. Filesystem (文件系统)

```python
from deepagents import FilesystemTool

# 多后端支持
fs = FilesystemTool(
    backend="local",  # local / s3 / gcs / azure
    root_dir="/workspace"
)

# 工具能力
agent.add_tool(fs.read)       # 读文件
agent.add_tool(fs.write)      # 写文件
agent.add_tool(fs.edit)       # 编辑文件
agent.add_tool(fs.search)     # 搜索文件
agent.add_tool(fs.list)       # 列出目录
```

#### 5. Shell (命令执行)

```python
from deepagents import ShellTool

shell = ShellTool(
    sandbox=True,           # 沙箱模式
    allowed_commands=["git", "npm", "pytest"],
    timeout=300
)

agent.add_tool(shell.run)
```

#### 6. Context Management (上下文管理)

```
Compaction流程:
┌─────────────────────────────────────────┐
│  原始对话 (100k tokens)                 │
│                                         │
│  Step 1: 识别关键信息                   │
│  • 决策点                               │
│  • 工具调用成功/失败                    │
│  • 用户指令                             │
│                                         │
│  Step 2: 压缩为摘要                     │
│  "用户要求实现X功能，                   │
│   Agent尝试了方案A失败，                │
│   方案B成功，最终输出文件Y"             │
│                                         │
│  Step 3: 保留摘要                       │
│  压缩后对话 (10k tokens)                │
└─────────────────────────────────────────┘
```

### LangGraph兼容性

Deep Agents与LangGraph无缝集成，可作为LangGraph节点：

```python
from langgraph.graph import StateGraph
from deepagents import Agent

# Agent作为节点
dev_agent = Agent(model="claude-sonnet-4", tools=[...])
review_agent = Agent(model="claude-opus-4", tools=[...])

# 构建LangGraph
graph = StateGraph(AgentState)
graph.add_node("develop", dev_agent.node)
graph.add_node("review", review_agent.node)
graph.add_edge("develop", "review")

# 持久化
app = graph.compile(checkpointer=MemorySaver())
```

---

## 二、Claude Agent SDK (Anthropic官方)

### 基本信息

| 项目 | Anthropic官方 |
|------|---------------|
| **Stars** | ~6,930 (估算) |
| **语言** | Python + TypeScript |
| **出品方** | Anthropic官方 |
| **定位** | Claude专用Agent SDK，Claude Code工具集封装 |
| **特点** | 内置Claude Code工具，无额外模型支持 |

### 核心特性

```
Claude Agent SDK 架构:
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                             │
│                                                              │
│  ┌──────────────┐                                           │
│  │    Model     │  仅支持Claude                              │
│  │ claude-opus  │  claude-sonnet, claude-haiku              │
│  │ claude-sonnet│                                           │
│  └──────────────┘                                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Claude Code Built-in Tools                  │   │
│  │  • read_file    - 读取文件                             │   │
│  │  • write_file   - 写入文件                             │   │
│  │  • edit_file    - 编辑文件                             │   │
│  │  • bash         - 执行命令                             │   │
│  │  • search       - 搜索文件                             │   │
│  │  • task         - 并行子任务                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Hooks     │  │    Memory    │  │  MCP Client  │       │
│  │  (事件拦截)  │  │  (会话级)    │  │  (进程内)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  无Skills、无Sub-agents、无LangGraph兼容                     │
└─────────────────────────────────────────────────────────────┘
```

### Claude Code工具集

| 工具 | 功能 | 示例 |
|------|------|------|
| `read_file` | 读取文件 | `read_file("src/main.py")` |
| `write_file` | 写入文件 | `write_file("output.txt", content)` |
| `edit_file` | 编辑文件 | `edit_file("config.yaml", old, new)` |
| `bash` | 执行命令 | `bash("pytest tests/")` |
| `search` | 搜索文件 | `search("*.py", "def main")` |
| `task` | 并行任务 | `task([task1, task2, task3])` |

### Hooks系统

```python
from claude_agent_sdk import Agent, Hook

agent = Agent(model="claude-sonnet-4")

# 预执行Hook
@agent.hook("pre_tool_call")
def check_danger(tool_call):
    if tool_call.tool == "bash" and "rm -rf" in tool_call.args:
        return {"block": True, "reason": "Dangerous command"}
    return {"allow": True}

# 后执行Hook
@agent.hook("post_tool_call")
def log_result(tool_call, result):
    print(f"Tool {tool_call.tool} returned: {result}")
```

### MCP Client (进程内)

Claude Agent SDK的MCP是进程内集成，不同于外部MCP Server：

```python
from claude_agent_sdk import MCPClient

# 加载MCP工具
mcp = MCPClient(config={
    "mcpServers": {
        "filesystem": {
            "command": "mcp-server-filesystem",
            "args": ["--root", "/workspace"]
        }
    }
})

agent.add_mcp_tools(mcp.tools)
```

### 无Sub-agents

Claude Agent SDK没有内置Sub-agent概念，需通过`task`工具模拟：

```python
# task工具并行执行
result = agent.run("""
使用task工具并行执行:
1. 分析src/目录结构
2. 检查tests/覆盖率
3. 生成docs/文档
""")
```

---

## 三、Pi (社区开源)

### 基本信息

| 项目 | earendil-works/pi |
|------|-------------------|
| **Stars** | **51,101** |
| **语言** | TypeScript |
| **出品方** | 社区开源 |
| **定位** | 编码Agent CLI + Harness，最强模型支持 |
| **版本** | 0.75.3 |
| **官网** | https://pi.dev |

### 核心特性

```
Pi Mono Repo架构:
┌─────────────────────────────────────────────────────────────┐
│                    Packages                                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ coding-agent │  │    agent     │  │     ai       │       │
│  │  CLI + SDK   │  │  (runtime)   │  │ (LLM统一API) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │     tui      │  │   web-ui     │                         │
│  │ (终端界面)   │  │ (Web组件)    │                         │
│  └──────────────┘  └──────────────┘                         │
│                                                              │
│  特点:                                                       │
│  • 40+ Provider (最强模型支持)                               │
│  • 订阅OAuth (Claude/ChatGPT/Copilot无需API Key)             │
│  • Skills (Agent Skills标准)                                 │
│  • Extensions (TypeScript全功能扩展)                         │
│  • Session树 (分支/fork/compaction)                          │
│  • 无Sub-agents                                              │
│  • 无MCP                                                     │
└─────────────────────────────────────────────────────────────┘
```

### 40+ Provider支持

**订阅OAuth (无需API Key):**
| 服务 | 环境变量 | 说明 |
|------|----------|------|
| Claude Pro/Max | 浏览器OAuth | 无需ANTHROPIC_API_KEY |
| ChatGPT Plus/Pro | 浏览器OAuth | 支持Codex模式 |
| GitHub Copilot | VS Code OAuth | 无需OPENAI_API_KEY |

**API Key Provider:**
| Provider | 环境变量 |
|----------|----------|
| Anthropic | ANTHROPIC_API_KEY |
| OpenAI | OPENAI_API_KEY |
| DeepSeek | DEEPSEEK_API_KEY |
| Google Gemini | GEMINI_API_KEY |
| xAI | XAI_API_KEY |
| Groq | GROQ_API_KEY |
| Mistral | MISTRAL_API_KEY |
| Cerebras | CEREBRAS_API_KEY |
| Together AI | TOGETHER_API_KEY |
| Fireworks | FIREWORKS_API_KEY |
| OpenRouter | OPENROUTER_API_KEY |
| Kimi | KIMI_API_KEY |
| MiniMax | MINIMAX_API_KEY |
| Xiaomi MiMo | XIAOMI_API_KEY |
| Hugging Face | HF_TOKEN |
| OpenCode | OPENCODE_API_KEY |
| Vercel AI Gateway | AI_GATEWAY_API_KEY |
| Cloudflare | CLOUDFLARE_API_KEY |

**本地模型:**
```json
// ~/.pi/agent/models.json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "models": [
        {"id": "llama3.1:8b"},
        {"id": "qwen2.5-coder:7b"}
      ]
    },
    "vllm": {
      "baseUrl": "http://localhost:8000/v1",
      "api": "openai-completions",
      "models": [
        {"id": "Qwen/Qwen3-32B", "reasoning": true}
      ]
    }
  }
}
```

### Skills系统

Pi采用Agent Skills标准，与其他Harness可共享：

```
Skills结构:
my-skill/
├── SKILL.md              # Required
├── scripts/              # Helper scripts
├── references/           # Detailed docs
└── assets/
    └── template.json

Frontmatter:
---
name: my-skill            # 最多64字符
description: 什么时候用    # 最多1024字符
license: MIT
compatibility: node 18+
allowed-tools: read bash  # 预批准工具(实验性)
---
```

**Skills共享配置:**
```json
// ~/.pi/agent/settings.json
{
  "skills": [
    "~/.pi/agent/skills",
    "~/.claude/skills",     // Claude Code skills
    "~/.codex/skills"       // Codex skills
  ]
}
```

### Extensions系统 (Pi亮点)

TypeScript全功能扩展，可自定义工具、事件拦截、UI组件：

```typescript
// ~/.pi/agent/extensions/my-extension.ts
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
  // 1. 事件拦截
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "bash" && event.input.command?.includes("rm -rf")) {
      const ok = await ctx.ui.confirm("Dangerous!", "Allow rm -rf?");
      if (!ok) return { block: true, reason: "Blocked by user" };
    }
  });

  // 2. 注册自定义工具
  pi.registerTool({
    name: "greet",
    description: "Greet someone",
    parameters: Type.Object({ name: Type.String() }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      return { content: [{ type: "text", text: `Hello, ${params.name}!` }] };
    },
  });

  // 3. 注册命令
  pi.registerCommand("hello", {
    description: "Say hello",
    handler: async (args, ctx) => {
      ctx.ui.notify(`Hello ${args || "world"}!`, "info");
    },
  });

  // 4. 自定义TUI组件
  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("Extension loaded!", "info");
  });
}
```

**Extension能力:**
- 自定义工具注册
- 事件拦截 (tool_call/session_start/model_switch等)
- 用户交互 (confirm/prompt/select)
- 自定义TUI组件
- 命令注册 (/mycommand)
- Session持久化
- 自定义渲染

### Session树形结构

```
Session树:
├─ user: "Hello, can you help..."
│  └─ assistant: "Of course! I can..."
│     ├─ user: "Let's try approach A..."
│     │  └─ assistant: "For approach A..."
│     │     └─ user: "That worked..."  ← active
│     └─ user: "Actually, approach B..."
│        └─ assistant: "For approach B..."

命令:
/resume     → 浏览历史Session
/new        → 新Session
/fork       → 从某点分支
/tree       → 导航树结构
/compact    → 压缩上下文
/export     → 导出HTML
/share      → 上传GitHub Gist
```

### 内置工具

| 工具 | 功能 |
|------|------|
| `read` | 读取文件 |
| `write` | 写入文件 |
| `edit` | 编辑文件 |
| `bash` | 执行命令 |
| `grep` | 搜索文件内容 |
| `find` | 搜索文件名 |
| `ls` | 列出目录 |

---

## 四、三大框架对比

### 功能对比表

| 特性 | Deep Agents | Claude Agent SDK | Pi |
|------|-------------|------------------|-----|
| **Stars** | 22,938 | ~6,930 | **51,101** |
| **语言** | Python | Python + TS | TypeScript |
| **出品方** | LangChain官方 | Anthropic官方 | 社区开源 |
| **模型支持** | 任意tool-calling LLM | 仅Claude | **40+ Provider** |
| **订阅OAuth** | ✗ | ✗ | ✓ Claude/ChatGPT/Copilot |
| **Skills** | ✓ 按需加载 | ✗ | ✓ Agent Skills标准 |
| **Extensions** | 需LangGraph | Hooks | ✓ TypeScript扩展 |
| **Sub-agents** | ✓ 隔离上下文 | ✗ | ✗ |
| **Memory** | ✓ 短期+持久 | ✗ 会话级 | ✓ Session级 |
| **Filesystem** | ✓ 多后端 | ✓ Claude内置 | ✓ 工具操作 |
| **Shell** | ✓ 沙箱可选 | ✓ Claude内置 | ✓ bash工具 |
| **Session** | ✓ Checkpointer | ✓ 会话管理 | ✓ 树形结构+分支 |
| **Compaction** | ✓ 自动压缩 | ✗ | ✓ 自动+手动+分支摘要 |
| **TUI** | ✗ | ✗ | ✓ Differential渲染 |
| **Web UI** | ✗ | ✗ | ✓ 组件可嵌入 |
| **SDK** | ✓ Python | ✓ Python+TS | ✓ TypeScript |
| **LangGraph兼容** | ✓ 直接 | 需封装 | ✗ |
| **MCP** | 需集成 | ✓ SDK MCP(进程内) | ✗ |
| **Tracing** | LangSmith | 内置 | ✓ |

### 控制流对比

| 控制流 | Deep Agents | Claude Agent SDK | Pi |
|--------|-------------|------------------|-----|
| **显式流程** | ✓ LangGraph节点 | ✗ | ✗ |
| **动态流程** | ✓ Conditional Edges | ✗ | ✗ |
| **事件驱动** | ✓ LangGraph | Hooks | Extensions |
| **层级流程** | ✓ Sub-agents | task工具 | ✗ |

### 通信模式对比

| 通信模式 | Deep Agents | Claude Agent SDK | Pi |
|----------|-------------|------------------|-----|
| **Shared Scratchpad** | ✓ LangGraph State | ✓ 对话历史 | ✓ Session消息 |
| **Handoff** | ✓ LangGraph边 | task工具 | ✗ |
| **Tool-Calling** | ✓ Sub-agents | ✗ | Extensions |

---

## 五、选择建议

### 按场景推荐

| 场景 | 推荐 | 原因 |
|------|------|------|
| **多Agent开发流水线** | Deep Agents | LangGraph兼容 + Skills + Sub-agents |
| **单Agent编码任务** | **Pi** | 40+模型 + Skills + Extensions |
| **Claude生态编码** | Claude Agent SDK | Claude Code内置工具 |
| **多模型测试/切换** | **Pi** | 40+ Provider + 订阅OAuth |
| **Sub-agents委托** | Deep Agents | 隔离上下文 + 摘要返回 |
| **LangGraph集成** | Deep Agents | 直接兼容 |
| **Extensions自定义** | **Pi** | TypeScript全功能扩展 |
| **持久记忆** | Deep Agents | 短期 + 跨会话持久 |
| **Session分支/fork** | **Pi** | 树形结构 + Compaction |
| **无API Key使用Claude** | **Pi** | Claude Pro/Max订阅OAuth |

### 按需求推荐

```
需求优先级:

1. 需要多Agent编排 → Deep Agents (LangGraph)
   └─ 需要Sub-agent委托 → Deep Agents
   └─ 需要动态路由 → LangGraph Conditional Edges

2. 需要多模型支持 → Pi (40+ Provider)
   └─ 需要订阅OAuth → Pi (Claude/ChatGPT/Copilot)
   └─ 需要本地模型 → Pi (Ollama/vLLM)

3. 需要编码能力 →
   └─ Claude专用 → Claude Agent SDK
   └─ 多模型编码 → Pi
   └─ LangGraph集成 → Deep Agents

4. 需要扩展性 →
   └─ TypeScript扩展 → Pi Extensions
   └─ Python扩展 → Deep Agents + LangGraph
   └─ Hooks → Claude Agent SDK

5. 需要Session管理 →
   └─ 树形分支 → Pi
   └─ 持久化恢复 → Deep Agents Checkpointer
```

---

## 六、推荐方案：混合架构

### 开发流水线架构

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph 编排层                           │
│                                                              │
│  各阶段Agent:                                                │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │需求分析  │──▶│技术设计  │──▶│开发Agent │──▶│Reviewer  │  │
│  │Deep Agent│   │Deep Agent│   │   Pi     │   │Deep Agent│  │
│  │+ Skills  │   │+ Subagent│   │CLI/SDK   │   │+ Skills  │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                              │
│  开发Agent选Pi原因:                                          │
│  • 40+模型支持 (测试不同模型编码能力)                        │
│  • 订阅OAuth (Claude Pro/Max无需API Key)                     │
│  • Skills加载编码模板                                        │
│  • Extensions拦截危险操作                                    │
│  • TUI交互式开发                                             │
│                                                              │
│  其他Agent选Deep Agents原因:                                 │
│  • LangGraph直接兼容                                         │
│  • Sub-agents委托                                            │
│  • 持久记忆                                                  │
│  • Skills系统                                                │
└─────────────────────────────────────────────────────────────┘
```

### Bug Fix流水线

```
┌─────────────────────────────────────────────────────────────┐
│  Pi CLI (单Agent快速修复)                                    │
│                                                              │
│  Session树形结构:                                            │
│  ├─ Bug描述                                                  │
│  │  ├─ 方案A尝试 (失败)                                      │
│  │  │  └─ 分析失败原因                                       │
│  │  └─ 方案B尝试 (成功)                                      │
│  │     └─ 验证修复                                           │
│                                                              │
│  Compaction流程:                                             │
│  1. 自动压缩失败尝试                                         │
│  2. 保留关键bug信息                                          │
│  3. 摘要成功方案                                             │
│                                                              │
│  多模型验证:                                                 │
│  /model claude-sonnet-4 → 生成修复                           │
│  /model deepseek-chat → 验证修复                             │
│  /model gpt-4o → 二次验证                                    │
│                                                              │
│  Extensions拦截:                                             │
│  • rm -rf 需确认                                             │
│  • git push需确认                                            │
│  • 大文件写入需确认                                          │
└─────────────────────────────────────────────────────────────┘
```

### Skills共享架构

```
Skills目录结构:
~/.agents/skills/             # 全局Skills (Deep Agents)
├── requirements-analysis/
├── technical-design/
├── code-generation/
├── code-review/
└── testing/

~/.pi/agent/skills/           # Pi Skills
├── (共享 ~/.agents/skills)
├── pi-specific-skills/

~/.claude/skills/             # Claude Code Skills
├── (共享 ~/.agents/skills)
├── claude-specific-skills/

配置共享:
// ~/.pi/agent/settings.json
{
  "skills": [
    "~/.agents/skills",
    "~/.claude/skills"
  ]
}
```

---

## 七、总结

### 各框架优势

| 框架 | 核心优势 |
|------|----------|
| **Deep Agents** | LangGraph兼容、Sub-agents、持久记忆、开箱即用 |
| **Claude Agent SDK** | Claude Code内置工具、Hooks、官方支持 |
| **Pi** | 40+模型、订阅OAuth、Extensions、Session树 |

### 最佳实践

```
1. 编排层: LangGraph
   • 显式控制流
   • 状态持久化
   • 人工干预点

2. Agent层:
   • 需求/设计/Review → Deep Agents (Sub-agents + Memory)
   • 开发 → Pi (多模型 + Extensions)
   • 快速修复 → Pi CLI (Session分支)

3. Skills层:
   • 全局共享 ~/.agents/skills/
   • 项目覆盖 .agents/skills/
   • 按需加载，减少上下文噪音

4. 扩展层:
   • TypeScript → Pi Extensions
   • Python → Deep Agents + LangGraph
```

---

## 参考资料

- [Deep Agents GitHub](https://github.com/langchain-ai/deepagents)
- [Claude Agent SDK Docs](https://docs.claude.com/en/api/agent-sdk)
- [Pi GitHub](https://github.com/earendil-works/pi)
- [Pi Docs](https://pi.dev)
- [Agent Skills Spec](https://agentskills.io/specification)
- [LangGraph Docs](https://docs.langchain.com/oss/python/langgraph)