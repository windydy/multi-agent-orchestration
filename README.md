# Multi-Agent Orchestration

多 Agent 工作流编排系统，用于把复杂软件工程任务拆解为可执行 DAG，并通过 Planner、Executor、LangGraph 工作流、FastAPI Dashboard 和 React Web UI 进行执行、观测与配置管理。

项目目标不是提供单个聊天 Agent，而是提供一套可扩展的“开发流水线运行时”：用户提交任务，系统生成执行计划，匹配具备相应能力的 Agent/Executor，驱动需求分析、设计、开发、评审、测试、修复、部署等节点，并记录执行状态、事件、成本和结果摘要。

## 核心能力

- **DAG 任务规划**：`src/plan` 将用户任务拆解为 `PlanGraph`/`PlanNode`，约束依赖关系必须无环。
- **动态工作流执行**：`src/workflows` 根据计划构建 LangGraph `StateGraph`，支持验证、失败重试和 replan。
- **多角色 Agent**：`src/agents` 和根目录 `agents/*.md` 提供需求、设计、开发、评审、测试、安全、DevOps、数据、产品等角色定义。
- **Executor 调度**：`src/executors` 通过能力声明匹配最合适的执行器，并提供通用执行适配层。
- **Claude/Anthropic 兼容适配**：`src/claude` 封装 Agent SDK、工具注册和 Hook 安全控制。
- **API 与 Dashboard 后端**：`src/api` 提供 FastAPI 路由、执行控制、配置管理、文件访问、DAG、事件、WebSocket 与可观测性接口。
- **Web UI**：`web` 提供 Vite + React Dashboard，用于启动执行、查看 DAG、编辑 YAML 配置、观察成本与成功率。
- **配置化编排**：`src/config` 和 `config/workflows` 支持用 YAML 描述 workflow、executors、verifiers、human review、cost control 和 checkpoint。
- **知识与记忆**：`src/knowledge` 使用 SQLite 记录 Agent 记忆，并可接入 embedding provider 做语义检索。
- **多项目工作区**：`src/workspace` 管理 `.workspace.yaml`，支持项目注册、切换和模板应用。
- **外部集成**：`src/integrations` 放置 GitHub、Jira、Slack 等系统集成适配。
- **可观测性与韧性**：`src/observability`、`src/resilience`、`src/cost` 覆盖指标、追踪、告警、重试、熔断和成本控制。

## 架构概览

```text
User / Web UI / CLI
        |
        v
FastAPI API Layer -------------------- WebSocket / Event Log / Config Store
        |
        v
PlannerAgent -> PlanGraph(DAG) -> DynamicWorkflowBuilder(LangGraph)
        |                                  |
        |                                  v
        |                         ExecutorRegistry
        |                                  |
        v                                  v
agents/*.md definitions          Agent executors / tools / Claude wrapper
        |
        v
Checkpoints / Memory / Observability / Integrations
```

核心数据流：

1. 用户通过 CLI 或 API 创建任务。
2. Planner 将任务拆解为 `PlanGraph`。
3. DynamicWorkflowBuilder 将 DAG 编译为 LangGraph 工作流。
4. ExecutorRegistry 根据 `ExecutorCapability` 匹配执行器。
5. 执行过程写入事件、检查点、指标和记忆。
6. Web UI 通过 REST/WebSocket 展示执行、DAG、配置和可观测性。

## 目录说明

```text
.
├── agents/                  # Markdown Agent 定义，包含 frontmatter 与 system prompt
├── config/workflows/        # YAML 工作流配置模板
├── docs/                    # 架构、设计、评审、规划与报告文档
├── examples/                # 端到端、bootstrap、框架演示脚本
├── src/
│   ├── agents/              # Python Agent 实现与 AgentLoader
│   ├── api/                 # FastAPI app、routes、services、WebSocket manager
│   ├── bug/                 # Bug 分类、报告与跟踪
│   ├── claude/              # Claude wrapper、hooks、tools
│   ├── cli/                 # 命令行入口
│   ├── config/              # workflow YAML schema 与 loader
│   ├── core/                # BaseAgent/BaseWorkflow/BaseTool/BaseState 抽象
│   ├── cost/                # 成本控制
│   ├── executors/           # Executor 基类、适配器和 registry
│   ├── integrations/        # GitHub/Jira/Slack 集成
│   ├── knowledge/           # Agent memory 与 embeddings
│   ├── observability/       # metrics、tracing、alerts store
│   ├── plan/                # PlanGraph 与 PlannerAgent
│   ├── resilience/          # retry policy 与 circuit breaker
│   ├── tools/               # PM、架构、CI/CD、安全、SQL、Docker 等工具
│   ├── verifier/            # 验证规则
│   ├── workflows/           # 静态与动态 LangGraph workflow builder/runner/state
│   └── workspace/           # 多项目 workspace 管理
├── tests/                   # pytest 测试，包括 API、knowledge、UI 等
└── web/                     # Vite + React dashboard
```

## 快速开始

### 1. 准备 Python 环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Dashboard 后端当前源码还使用 FastAPI/Uvicorn 等运行时依赖；如果本地环境没有这些包，请补充安装：

```bash
pip install fastapi uvicorn aiofiles pytest-cov
```

### 2. 配置模型密钥

Planner 默认优先读取 DashScope 兼容 Anthropic API，也支持 Anthropic API Key：

```bash
export DASHSCOPE_API_KEY="your-key"
# 或
export ANTHROPIC_API_KEY="your-key"
```

`PlannerAgent` 还会尝试读取 `~/.hermes/config.yaml` 中的兼容 API 配置。

### 3. 运行 CLI

```bash
python -m src.cli.main run "为目标项目实现一个登录功能" --path ./demo_project --no-review

python -m src.cli.main status <thread_id>
python -m src.cli.main history <thread_id>
python -m src.cli.main resume <thread_id> --approve --comment "通过"
python -m src.cli.main visualize
```

CLI 会把最近一次执行的 thread id 写入 `.pipeline_thread_YYYYMMDD.txt`。

### 4. 运行 API 后端

```bash
python -m uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

常用接口：

| 能力 | 路径 |
| --- | --- |
| 健康检查 | `GET /api/health` |
| 概览统计 | `GET /api/overview` |
| 创建执行 | `POST /api/executions` |
| 暂停/恢复/取消 | `POST /api/executions/{thread_id}/pause|resume|cancel` |
| 执行日志 | `GET /api/executions/{thread_id}/logs` |
| 配置工作流 | `GET/PUT/DELETE /api/config/workflows/{name}` |
| Agent 配置 | `GET/PUT /api/config/agents/{agent_id}` |
| 验证规则 | `GET/POST /api/config/verifiers` |
| 可观测性 | `GET /api/observability/*` |
| WebSocket | `WS /api/ws/{task_id}` |

### 5. 运行 Web UI

```bash
cd web
npm install
npm run dev
```

生产构建：

```bash
cd web
npm run build
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

后端会在存在 `web/dist` 时挂载 SPA 静态资源。

### 6. Docker

```bash
docker compose --profile dev up dev
```

注意：当前 `Dockerfile` 期望存在 `requirements.txt`，而仓库依赖权威来源是 `pyproject.toml`。在修复 Docker 构建前，推荐使用本地 Python 环境或开发镜像流程。

## 工作流配置

配置模型位于 `src/config/schema.py`，示例位于 `config/workflows/phase8-bootstrap.yaml`。一个 workflow 通常包含：

- `planner`：规划模型、最大深度、是否允许并行和自动 replan。
- `executors`：各执行器模型、工具、超时、重试与并发实例数。
- `flow_template`：入口节点、节点列表、边和条件。
- `verifiers`：token、成本、超时等规则。
- `human_review`：人工审批节点与自动审批时间。
- `cost_control`：成本 warning/limit/stop 阈值。
- `checkpoint`：检查点数据库路径与保存间隔。

修改 YAML 后应通过配置 API 或 schema loader 校验，确保 entry point 存在、依赖节点存在且流程无环。

## Agent 定义规范

根目录 `agents/*.md` 使用 YAML frontmatter + Markdown body：

```markdown
---
name: developer
role: Code Developer
description: Implements code and tests
model: qwen3.6-plus
max_iterations: 10
timeout: 300
temperature: 0.1
tools:
  - read
  - write
  - edit
  - bash
---

System prompt content...
```

加载逻辑在 `src/agents/loader.py`。新增 Agent 时应保证：

1. 文件名与 `name` 可被稳定引用。
2. `tools` 是列表，不要把多个工具写成逗号字符串。
3. Prompt 明确输入、输出、边界和失败策略。
4. 能力要能映射到 `ExecutorCapability` 或显式接入对应 executor。
5. 不要在 Agent 定义中硬编码密钥、私有路径或一次性环境信息。

## 开发与测试

```bash
pytest
pytest tests/api -v
pytest tests/knowledge -v
pytest --cov=src --cov-report=term-missing
ruff check src tests
mypy src
```

前端：

```bash
cd web
npm run build
```

建议开发顺序：

1. 先明确变更属于 plan、workflow、executor、API、Web UI、knowledge 还是 integration。
2. 修改对应子目录前阅读该目录的 `AGENTS.md`。
3. 新行为优先补 pytest 或前端测试。
4. 涉及 API/配置/外部集成时补充输入校验和错误路径测试。
5. 涉及 UI 时实际启动页面验证主要路径和边界状态。

## 子功能 LLM 索引

本仓库在核心子功能目录下维护 `AGENTS.md`，用于给 LLM/代码代理提供局部上下文：

- `src/AGENTS.md`：全局源码约束。
- `src/core/AGENTS.md`：基础抽象。
- `src/agents/AGENTS.md`：Agent 实现与 Markdown 定义加载。
- `src/plan/AGENTS.md`：任务规划与 DAG 模型。
- `src/workflows/AGENTS.md`：LangGraph 构建、运行和状态。
- `src/executors/AGENTS.md`：执行器调度与能力匹配。
- `src/api/AGENTS.md`：FastAPI、routes、services、WebSocket。
- `src/config/AGENTS.md`：YAML workflow schema。
- `src/claude/AGENTS.md`：Claude wrapper、tools、hooks。
- `src/knowledge/AGENTS.md`：记忆与 embedding。
- `src/integrations/AGENTS.md`：外部系统集成。
- `src/workspace/AGENTS.md`：多项目工作区。
- `src/observability/AGENTS.md`：指标、追踪和告警。
- `web/AGENTS.md`：React Dashboard。

## 安全注意事项

- 不要把 API Key 写入源码、Agent prompt、YAML 配置或测试 fixture。
- API 边界必须使用 Pydantic 或等价方式验证输入。
- 文件访问必须限制在允许的 project root 内，避免路径穿越。
- 外部集成必须显式处理认证失败、速率限制和网络错误。
- 执行 shell/tool 前应经过 Hook 或工具白名单约束。
- 生产部署应补齐 CORS、CSP、认证、授权、速率限制和持久化备份策略。

## 当前状态提示

该仓库处于持续演进状态，历史文档中仍包含 Phase 1-8 的规划、评审和完成报告。以当前源码、`pyproject.toml`、`web/package.json` 和本 README 为运行入口的优先参考；设计背景可查阅 `docs/architecture`、`docs/design` 和 `docs/report`。
