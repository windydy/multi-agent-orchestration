# Multi-Agent Orchestration 项目开发规范

## 适用范围

本文件是项目根目录的开发规范，适用于所有在本项目中执行开发任务的 Agent
（DeveloperAgent、FixerAgent、TesterAgent、ReviewerAgent 等）。
子目录中的 `AGENTS.md` 补充本文件，不冲突时两者同时遵循。

---

## 安全边界

### 可自由修改

| 路径 | 说明 |
|------|------|
| `src/agents/` | Agent 实现 |
| `src/tools/` | 工具实现 |
| `src/executors/` | 执行器 |
| `src/clarifier/` | 需求澄清模块 |
| `tests/` | 测试代码 |
| `docs/` | 文档 |
| `web/src/` | 前端代码 |
| `scripts/` | 脚本文件 |
| `examples/` | 示例代码 |

### 禁止自动修改（需人工确认）

| 路径 | 说明 |
|------|------|
| `src/core/` | 核心抽象层（Agent/Workflow/Tool 最小契约） |
| `src/workflows/runner.py` | 统一执行入口 |
| `src/workflows/dynamic_builder.py` | LangGraph 动态工作流构建 |
| `src/api/server.py` | FastAPI 应用工厂 |
| `pyproject.toml` | Python 依赖配置 |
| `web/package.json` | 前端依赖配置 |

### 可修改但必须同步更新对应测试

- 修改 `src/agents/` → 必须更新对应 Agent 测试
- 修改 `src/api/routes/` → 必须有路由集成测试
- 修改 `src/executors/` → 必须有执行器测试
- 修改 `src/clarifier/` → 必须有澄清模块测试
- 修改 `src/knowledge/` → 必须有知识模块测试

---

## 开发标准

### 代码规范

- 所有新增代码必须有对应单元测试
- 新增 API 端点必须有集成测试
- 所有代码必须通过 `ruff check` 且零错误
- Python 类型注解必须完整
- 函数圈复杂度不超过 10
- 新增测试覆盖率 ≥ 80%

### 测试规范

- 测试命令：`.venv/bin/python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/knowledge/`
- 测试框架：pytest + pytest-asyncio
- 异步测试使用 `@pytest.mark.asyncio`
- 测试文件命名：`test_<模块名>.py`
- 测试类命名：`Test<类名>` 或 `Test<功能>`

### Git 规范

- 功能开发使用 `git worktree` 创建隔离环境
- 分支命名：`feature/{描述}` 或 `fix/{描述}`
- 提交信息格式：`<type>(<scope>): <description>`（type: feat/fix/test/docs/refactor）
- 合并前必须：所有测试通过 + lint 通过 + 人工确认

---

## 自开发流程（Self-Dev）

当系统开发自己时，遵循以下流程：

1. **任务描述**：包含目标、隔离要求（git worktree 分支名）、验证标准
2. **隔离开发**：在 worktree 中修改代码，不直接改主干
3. **验证**：运行 pytest + lint + 端到端验证脚本
4. **监测**：生成质量报告（lint/测试/覆盖率/安全合规）
5. **人工确认**：审查报告 + diff，确认合并

详见 `docs/self-dev/README.md`

---

## 项目结构概览

```
multi-agent-orchestration/
├── AGENTS.md              ← 本文件：项目级开发规范
├── src/                   ← Python 后端
│   ├── core/              ← 核心抽象
│   ├── agents/            ← Agent 实现
│   ├── workflows/         ← LangGraph 工作流
│   ├── api/               ← FastAPI 后端
│   ├── clarifier/         ← 需求澄清
│   ├── knowledge/         ← Agent 记忆
│   └── ...
├── tests/                 ← 测试代码
├── web/                   ← React 前端
├── docs/                  ← 文档
│   ├── design/            ← 设计文档（Phase 规格）
│   ├── planning/          ← 规划文档
│   └── self-dev/          ← 自开发任务模板和脚本
└── scripts/               ← 工具脚本
```

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **multi-agent-orchestration** (7998 symbols, 14364 relationships, 228 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/multi-agent-orchestration/context` | Codebase overview, check index freshness |
| `gitnexus://repo/multi-agent-orchestration/clusters` | All functional areas |
| `gitnexus://repo/multi-agent-orchestration/processes` | All execution flows |
| `gitnexus://repo/multi-agent-orchestration/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
