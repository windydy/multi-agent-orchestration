# 多Agent工作流编排项目

> 基于 LangGraph + Claude Agent SDK 的开发流水线

## 项目状态

**Phase 1-3 完成** ✅

- [x] 技术方案设计
- [x] ClaudeAgentWrapper实现
- [x] WorkflowState定义
- [x] 6个Agent实现（含Fixer）
- [x] LangGraph工作流构建
- [x] Hooks安全控制
- [x] CLI接口
- [x] 测试框架

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph 编排层                          │
│                                                              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐     │
│  │需求分析 │──▶│技术设计 │──▶│ 开发    │──▶│ Review  │     │
│  │  Node   │   │  Node   │   │  Node   │   │  Node   │     │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘     │
│       │             │             │             │           │
│       └──────Conditional Edges──────▶ Fixer ──▶ Test       │
│                                                              │
│  State: TypedDict + Checkpointer                            │
│  Interrupt: Review/Test节点可暂停                           │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Claude Agent SDK 执行层                       │
│                                                              │
│  Agents: requirements, designer, developer,                 │
│          reviewer, tester, fixer                            │
│                                                              │
│  Tools: read_file, write_file, edit_file,                   │
│         bash, search                                         │
│                                                              │
│  Hooks: Safety, Logging, CostControl                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
multi-agent-orchestration/
│
├── src/
│   ├── core/                  # 已有抽象层（保持）
│   │   ├── agent.py          # BaseAgent
│   │   ├── state.py          # BaseState + InMemoryState
│   │   ├── workflow.py       # BaseWorkflow
│   │   ├── orchestrator.py   # BaseOrchestrator
│   │   └── tool.py           # BaseTool
│   │
│   ├── claude/                # Claude SDK适配层
│   │   ├── wrapper.py        # ClaudeAgentWrapper(BaseAgent)
│   │   ├── hooks.py          # SafetyHook, LoggingHook, CostHook
│   │   └── tools.py          # ClaudeToolRegistry
│   │
│   ├── agents/                # Agent实现
│   │   ├── requirements.py   # RequirementsAgent
│   │   ├── designer.py       # DesignerAgent
│   │   ├── developer.py      # DeveloperAgent
│   │   ├── reviewer.py       # ReviewerAgent
│   │   ├── tester.py         # TesterAgent
│   │   └── fixer.py          # FixerAgent
│   │
│   ├── workflows/             # Workflow实现
│   │   ├── states.py         # WorkflowState + WorkflowStateManager
│   │   ├── builder.py        # DevelopmentPipelineBuilder
│   │   └── runner.py         # WorkflowRunner
│   │
│   └── cli/                   # CLI接口
│       └ main.py              # 命令行入口
│
├── examples/                  # 示例
│   └ langgraph-demo/         # 原有示例
│   └ dev_pipeline.py         # 开发流水线示例
│
├── tests/                     # 测试
│   ├── test_wrapper.py
│   ├── test_builder.py
│   └ test_pipeline.py
│
├── docs/
│   ├── architecture/
│   │   ├── langgraph-claude-sdk-technical-proposal.md  # 技术方案
│   │   └ technical-proposal-revision.md                # 修订版
│   │   └ system-design.md                              # 原有设计
│   │
│   └ research/
│   │   ├── agent-harness-comparison.md                  # Agent Harness对比
│   │   ├── framework-comparison.md                      # 框架对比
│   │   └ design-patterns.md                             # 设计模式
│
│   └ checkpoints/              # 检查点存储
│
│   ├── README.md
│   └── TODO.md
```

---

## 使用方法

### 1. 环境准备

```bash
# 安装依赖
pip install langgraph anthropic pyyaml aiofiles pytest pytest-asyncio

# 设置API Key
export ANTHROPIC_API_KEY='your-api-key'
```

### 2. CLI命令

```bash
# 运行开发流水线（自动模式）
python -m src.cli.main run "实现用户登录功能" --path ./project/

# 运行开发流水线（交互模式）
python -m src.cli.main run "实现用户登录功能" --path ./project/

# 恢复中断的工作流
python -m src.cli.main resume <thread_id> --approve --comment "通过"

# 查看状态
python -m src.cli.main status <thread_id>

# 查看历史
python -m src.cli.main history <thread_id>

# 可视化工作流
python -m src.cli.main visualize
```

### 3. Python API

```python
from src.workflows.runner import run_pipeline, WorkflowRunner

# 便捷函数
result = await run_pipeline(
    task="实现斐波那契数列函数",
    project_path="./project/",
    enable_human_review=False
)

# 或使用Runner
runner = WorkflowRunner(api_key="your-key")

# 运行直到中断
result = await runner.run_until_interrupt("实现登录功能", "./project/")

# 人工审批后恢复
resume_result = await runner.resume(result['thread_id'], approval=True)
```

---

## Agent角色

| Agent | 模型 | 工具 | 输出 |
|-------|------|------|------|
| Requirements Analyst | opus | read, search | 需求文档 |
| Technical Designer | opus | read, write, search | 技术设计 |
| Developer | sonnet | read, write, edit, bash, search | 代码 + 测试 |
| Code Reviewer | opus | read, search | 审查结果 |
| QA Tester | sonnet | bash, read, search | 测试结果 |
| Bug Fixer | sonnet | read, edit, bash, search | 修复结果 |

---

## 工作流

```
START → requirements → design → develop → review
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                    approved          needs_revision    human_review
                        │                 │                 │
                        ▼                 ▼                 ▼
                      test          → develop          → 等待审批
                        │
               ┌────────┼────────┐
               │        │        │
            passed   fixable  needs_help
               │        │        │
               ▼        ▼        ▼
             END      fix    → human_review
                        │
                        ▼
                      test (循环)
```

---

## 关键特性

### 1. Hooks安全控制

```python
from src.claude.hooks import SafetyHook, LoggingHook, CostHook

# 自动拦截危险命令
# rm -rf, sudo rm, curl | sh 等被阻止

# 成本控制
# warning: $5, limit: $10, stop: $20
```

### 2. 状态持久化

```python
# LangGraph Checkpointer
# 支持SQLite持久化，可暂停/恢复

runner = WorkflowRunner()
state = runner.get_state(thread_id)  # 获取当前状态
history = runner.get_history(thread_id)  # 获取历史
```

### 3. 迭代限制

```python
# 防止死循环
# max_iterations = 10
# 达到限制后强制结束
```

---

## 测试

```bash
# 运行测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=html
```

---

## 技术方案

详见：
- [技术方案](docs/architecture/langgraph-claude-sdk-technical-proposal.md)
- [修订版](docs/architecture/technical-proposal-revision.md)

---

## 依赖

```toml
[project]
dependencies = [
    "langgraph>=0.2.0",
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
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

## 下一步

- [ ] Phase 4: 集成测试（需要API Key）
- [ ] Phase 5: 实际项目验证
- [ ] Web UI可视化
- [ ] 更多Agent角色（DevOps, Data等）

---

*更新日期: 2026-05-19*