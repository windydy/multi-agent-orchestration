# 系统自开发（Self-Dev）

> Self-Dev 不是改系统架构，只是系统的一个普通任务。系统用现有流水线开发自己。

---

## 核心理念

Self-Dev 跟"帮用户做电商网站"走**同一条流水线**：

```
Clarifier → Planner → Developer → Reviewer → Tester → Fixer
```

区别只在三件事：

| 层面 | 说明 | 实现方式 |
|------|------|---------|
| 约束在哪 | 项目规则，不在 Agent prompt | `AGENTS.md`（根目录） |
| 隔离在哪 | 执行策略 | 任务描述中指定 git worktree |
| 验证在哪 | 正常测试 + 端到端脚本 | pytest + 验证脚本 |

---

## 如何让系统开发自己

### 方式一：通过 CLI

```bash
python -m src.cli.main run "新增 AgentMemory 查询 API，支持关键词检索"
```

### 方式二：通过 API

```bash
curl -X POST http://localhost:8000/api/executions \
  -H "Content-Type: application/json" \
  -d '{
    "task": "新增 AgentMemory 查询 API...",
    "tags": ["self-dev"]
  }'
```

### 方式三：通过 Web UI

1. 在首页点击 "创建任务"
2. 填写任务描述
3. 提交

---

## 开发流程

```
1. 提交任务 → 2. git worktree 创建隔离环境 → 3. Agent 开发
   ↓
4. pytest 测试 → 5. ruff 检查 → 6. 端到端验证
   ↓
7. 生成监测报告 → 8. 人工 review → 9. git merge
```

---

## 约束规范

详见根目录 `AGENTS.md`：
- 安全边界（哪些能改、哪些不能改）
- 开发标准（测试、lint、代码质量）
- Git 规范（分支命名、提交格式）

---

## 任务模板

参考 `task-template.yaml`

---

## 验证脚本

放在 `scripts/` 目录下：
- `verify_memory_search.sh` — 验证记忆查询 API
- `generate_monitor_report.py` — 生成监测报告

---

## 监测报告

放在 `docs/self-dev/reports/` 目录下，文件名格式 `self-dev-{timestamp}.json`
