# Phase 10 技术方案：系统自开发（Self-Dev）

| 字段 | 值 |
|------|-----|
| **文档版本** | v1.0 |
| **创建日期** | 2026-05-24 |
| **状态** | 评审中 |
| **作者** | Multi-Agent 系统 |
| **目标** | 让系统用现有流水线安全地开发自己，不改架构 |

---

## 1. 背景与目标

### 1.1 现状

系统已具备完整的多 Agent 流水线：

```
Clarifier → Planner → Developer → Reviewer → Tester → Fixer
```

已有能力：
- 代码读写（DeveloperAgent 的 terminal / write_file 工具）
- 测试执行（TesterAgent 的 pytest）
- 代码审查（ReviewerAgent 的 ruff / 逻辑审查）
- 需求澄清（ClarifierAgent 的 9 维度评分）
- 失败修复（FixerAgent 的迭代修复）

但让系统开发自己时，存在以下缺口：

| 缺口 | 说明 |
|------|------|
| **项目级约束缺失** | 没有告诉 Agent 哪些文件能改、哪些不能、开发标准是什么 |
| **隔离策略缺失** | 直接改主干代码，改错就污染项目 |
| **验证规范缺失** | 新功能完成后怎么才算"跑通了"，没有明确标准 |
| **过程监测缺失** | Agent 开发过程是黑盒，无法评估质量和效率 |

### 1.2 核心原则

**Self-Dev 不改系统架构，它只是系统的一个普通任务。**

| 层面 | 实现方式 |
|------|---------|
| 安全约束 | 写在项目文件 `AGENTS.md` 中，不注入 Agent prompt |
| 隔离开发 | 任务描述中指定 `git worktree`，Agent 用现有 terminal 工具执行 |
| 功能验证 | 现有 pytest + 验证脚本 |
| 过程监测 | 采集执行数据（日志/测试/lint/git diff）生成报告 |
| 流水线 | 走现有 Clarifier → Planner → Developer → Reviewer → Tester → Fixer，零改动 |

---

## 2. 架构设计

### 2.1 整体数据流

```
┌─────────────────────────────────────────────────────────┐
│ 用户提交自开发任务（CLI / API / 任务文件）                    │
│ 任务包含：目标、隔离要求、验证标准、监测阈值                     │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 现有流水线（零改动）                                        │
│                                                         │
│  1. ClarifierAgent  评分 + 澄清                           │
│  2. PlannerAgent    生成执行计划                           │
│  3. DeveloperAgent  开发（在 worktree 中）                  │
│  4. ReviewerAgent   代码审查                              │
│  5. TesterAgent     运行测试                              │
│  6. FixerAgent      修复失败（如有）                        │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 验证阶段（现有能力组合）                                     │
│                                                         │
│  1. pytest tests/              ← TesterAgent 已有        │
│  2. ruff check src/            ← 已有 lint                │
│  3. 运行验证脚本               ← 终端命令                   │
│  4. git diff 检查安全边界      ← 终端命令                   │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 监测报告生成（新增脚本）                                     │
│                                                         │
│  采集：执行日志 + 测试结果 + lint 结果 + git diff          │
│  分析：代码质量 + 测试覆盖 + 开发效率 + 安全合规            │
│  输出：JSON 报告 → 文件存储                                │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 人工确认合并                                               │
│  查看监测报告 → 审查代码 diff → 确认 merge                   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 组件与职责

| 组件 | 是否新增 | 职责 | 实现方式 |
|------|---------|------|---------|
| `AGENTS.md` | **新增** | 项目级开发规范 | Markdown 文件 |
| 任务模板 | **新增** | 自开发任务描述标准 | YAML 文件 |
| 验证脚本 | **新增** | 端到端功能验证 | Shell / Python |
| 监测脚本 | **新增** | 采集执行数据生成报告 | Python |
| 流水线 | 不改 | 执行开发任务 | 现有系统 |
| 终端工具 | 不改 | 运行 git / pytest / ruff | 现有 terminal 工具 |
| 文件工具 | 不改 | 读写代码文件 | 现有 file 工具 |

---

## 3. 详细设计

### 3.1 项目约束文件

#### 3.1.1 根目录 `AGENTS.md`

```markdown
# Multi-Agent Orchestration 项目开发规范

## 适用对象

本文件适用于所有在本项目中执行开发任务的 Agent（DeveloperAgent、FixerAgent 等）。

## 安全边界

### 可自由修改
- `src/agents/` — Agent 实现
- `src/tools/` — 工具实现
- `src/executors/` — 执行器
- `tests/` — 测试代码
- `docs/` — 文档
- `web/src/` — 前端代码
- `scripts/` — 脚本文件

### 禁止自动修改（需人工确认）
- `src/core/` — 核心抽象层
- `src/workflows/runner.py` — 统一执行入口
- `src/workflows/dynamic_builder.py` — 工作流构建
- `src/api/server.py` — FastAPI 应用工厂
- `pyproject.toml` — 依赖配置
- `web/package.json` — 前端依赖

### 可修改但必须同步更新对应测试
- `src/agents/` — 修改 Agent 必须更新对应测试
- `src/api/routes/` — 修改路由必须有路由测试
- `src/executors/` — 修改执行器必须有执行器测试

## 开发标准

- 所有新增代码必须有对应单元测试
- 新增 API 端点必须有集成测试
- 所有代码必须通过 `ruff check` 且零错误
- Python 类型注解必须完整
- 函数圈复杂度不超过 10
- 新增测试覆盖率 ≥ 80%

## Git 规范

- 功能开发使用 `git worktree` 创建隔离环境
- 分支命名：`feature/{描述}` 或 `fix/{描述}`
- 提交信息格式：`<type>: <description>`（type: feat/fix/test/docs）
- 合并前必须：所有测试通过 + lint 通过 + 人工确认
```

#### 3.1.2 文件位置

```
multi-agent-orchestration/
├── AGENTS.md                      ← 新增：项目级开发规范
├── docs/
│   └── self-dev/
│       ├── README.md              ← 新增：流程说明
│       ├── task-template.yaml     ← 新增：任务模板
│       ├── scripts/
│       │   └── verify_*.sh        ← 新增：验证脚本
│       └── reports/               ← 新增：监测报告存储
│           └── self-dev-{id}.json
```

### 3.2 任务描述标准

#### 3.2.1 任务模板

```yaml
# docs/self-dev/task-template.yaml
title: "新增 AgentMemory 查询 API"
priority: P1
description: |
  为系统新增记忆查询端点 POST /api/memory/search
  支持按关键词检索 AgentMemory 中的记录
  
  功能要求：
  1. 接受 JSON body: {"query": "关键词", "limit": 10}
  2. 返回匹配的记忆记录列表
  3. 支持分页参数 offset/limit
  4. 空查询返回空列表，不报错

isolation:
  type: git-worktree
  branch: feature/memory-search-api
  worktree_path: .worktrees/feature-memory-search

validation:
  unit_tests:
    - tests/test_knowledge/test_memory.py
  integration_tests:
    - tests/test_api/test_memory_routes.py
  e2e_scripts:
    - docs/self-dev/scripts/verify_memory_search.sh
  lint:
    - ruff check src/knowledge/ src/api/routes/
  regression:
    - pytest tests/ --ignore=tests/ui/ --ignore=tests/knowledge/

acceptance_criteria:
  - "POST /api/memory/search 返回 200"
  - "关键词匹配返回正确结果"
  - "空查询返回空列表 (不报错)"
  - "新增测试覆盖率 ≥ 80%"
  - "所有现有测试无回归"
  - "ruff check 零错误"

monitoring:
  thresholds:
    test_coverage_min: 80
    lint_errors_max: 0
    cyclomatic_complexity_max: 10
    llm_calls_max: 30
    fix_iterations_max: 5
    unsafe_file_changes_max: 0
  collect:
    - pytest_output: true
    - ruff_output: true
    - git_diff: true
    - execution_log: true
```

### 3.3 验证设计

#### 3.3.1 验证类型

| 类型 | 工具 | 触发时机 | 负责 Agent |
|------|------|---------|-----------|
| 单元测试 | pytest | 开发完成后 | TesterAgent |
| 集成测试 | pytest | 开发完成后 | TesterAgent |
| 代码质量 | ruff check | 开发完成后 | ReviewerAgent |
| 端到端验证 | 验证脚本 | 测试通过后 | DeveloperAgent |
| 回归测试 | pytest 全部 | 合并前 | TesterAgent |

#### 3.3.2 验证脚本示例

```bash
#!/bin/bash
# docs/self-dev/scripts/verify_memory_search.sh
# 端到端验证新增的 AgentMemory 查询 API

set -e

PORT=8100
echo "Starting API server on port $PORT..."
python -m uvicorn src.api.server:app --port $PORT &
SERVER_PID=$!
sleep 3

cleanup() {
    kill $SERVER_PID 2>/dev/null || true
}
trap cleanup EXIT

# 测试 1：API 端点返回 200
echo "Test 1: API endpoint returns 200"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}')
if [ "$STATUS" != "200" ]; then
  echo "FAIL: Expected 200, got $STATUS"
  exit 1
fi
echo "PASS"

# 测试 2：返回正确字段
echo "Test 2: Response has required fields"
BODY=$(curl -s \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}')
echo "$BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'results' in d, 'Missing results field'
assert isinstance(d['results'], list), 'results must be a list'
print('PASS')
"

# 测试 3：空查询返回空列表
echo "Test 3: Empty query returns empty list"
BODY=$(curl -s \
  -X POST http://localhost:$PORT/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": ""}')
echo "$BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['results'] == [], 'Empty query should return empty list'
print('PASS')
"

echo "All verification passed!"
```

### 3.4 监测设计

#### 3.4.1 监测维度与指标

| 维度 | 指标 | 采集方式 | 阈值 | 说明 |
|------|------|---------|------|------|
| **代码质量** | Lint 错误数 | `ruff check --output-format=json` | = 0 | 零错误 |
| **代码质量** | 圈复杂度 | `radon cc src/` | ≤ 10 | 单函数最大复杂度 |
| **测试质量** | 测试覆盖率 | `pytest --cov=src --cov-report=json` | ≥ 80% | 新增代码覆盖率 |
| **测试质量** | 测试通过率 | pytest exit code | 100% | 零失败 |
| **开发效率** | LLM 调用次数 | 从执行日志统计 | ≤ 30 | 过度迭代说明需求不清 |
| **开发效率** | 修复迭代次数 | 从执行日志统计 | ≤ 5 | FixerAgent 循环次数 |
| **安全合规** | 核心文件修改数 | `git diff --name-only` 对比 UNSAFE_FILES | = 0 | 不能改核心文件 |
| **功能正确** | 验证脚本通过率 | 验证脚本 exit code | 100% | 端到端必须跑通 |

#### 3.4.2 监测报告数据结构

```json
{
  "report_id": "self-dev-20260524-001",
  "task_title": "新增 AgentMemory 查询 API",
  "branch": "feature/memory-search-api",
  "generated_at": "2026-05-24T10:30:00Z",
  "status": "passed",
  "metrics": {
    "code_quality": {
      "lint_errors": 0,
      "lint_warnings": 2,
      "max_complexity": 8,
      "passed": true
    },
    "test_quality": {
      "coverage_percent": 85.3,
      "tests_passed": 42,
      "tests_failed": 0,
      "tests_skipped": 3,
      "passed": true
    },
    "development_efficiency": {
      "llm_calls": 18,
      "fix_iterations": 2,
      "total_development_time_seconds": 320,
      "passed": true
    },
    "security_compliance": {
      "unsafe_files_modified": [],
      "review_required_files_modified": ["src/api/routes/__init__.py"],
      "passed": true
    },
    "functional_verification": {
      "e2e_tests_run": 3,
      "e2e_tests_passed": 3,
      "e2e_tests_failed": 0,
      "passed": true
    }
  },
  "summary": {
    "all_passed": true,
    "issues": [],
    "recommendation": "ready_for_merge"
  }
}
```

#### 3.4.3 监测脚本实现

```python
#!/usr/bin/env python3
"""
docs/self-dev/scripts/generate_monitor_report.py

采集执行数据，生成监测报告。
运行方式：python generate_monitor_report.py --worktree .worktrees/feature-memory-search --output docs/self-dev/reports/
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime


UNSAFE_FILES = [
    "src/core/",
    "src/workflows/runner.py",
    "src/workflows/dynamic_builder.py",
    "src/api/server.py",
    "pyproject.toml",
    "web/package.json",
]


def run_command(cmd: list[str], cwd: str = None) -> tuple[int, str, str]:
    """运行命令并返回 (exit_code, stdout, stderr)"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def collect_lint_metrics(worktree: Path) -> dict:
    """采集 lint 指标"""
    code, stdout, stderr = run_command(
        ["ruff", "check", "--output-format=json", "src/"],
        cwd=str(worktree),
    )
    lint_errors = 0
    lint_warnings = 0
    if code == 0 and stdout:
        try:
            results = json.loads(stdout)
            for file_result in results:
                for msg in file_result.get("messages", []):
                    if msg.get("level") == "error":
                        lint_errors += 1
                    elif msg.get("level") == "warning":
                        lint_warnings += 1
        except json.JSONDecodeError:
            lint_errors = 1 if code != 0 else 0
    else:
        lint_errors = 1 if code != 0 else 0

    return {
        "lint_errors": lint_errors,
        "lint_warnings": lint_warnings,
        "passed": lint_errors == 0,
    }


def collect_complexity_metrics(worktree: Path) -> dict:
    """采集圈复杂度指标"""
    code, stdout, stderr = run_command(
        ["radon", "cc", "src/", "--min", "C"],
        cwd=str(worktree),
    )
    max_complexity = 0
    # 解析 radon 输出: file.py:10:0 F my_function - C (12)
    for line in stdout.splitlines():
        if " - C (" in line or " - B (" in line:
            try:
                complexity = int(line.split("(")[-1].rstrip(")"))
                max_complexity = max(max_complexity, complexity)
            except ValueError:
                pass
    return {"max_complexity": max_complexity, "passed": max_complexity <= 10}


def collect_test_metrics(worktree: Path, venv_python: str) -> dict:
    """采集测试指标"""
    code, stdout, stderr = run_command(
        [venv_python, "-m", "pytest", "tests/",
         "--ignore=tests/ui/", "--ignore=tests/knowledge/",
         "-v", "--tb=short"],
        cwd=str(worktree),
    )
    # 解析 pytest 输出
    tests_passed = 0
    tests_failed = 0
    tests_skipped = 0
    for line in stdout.splitlines():
        if "passed" in line:
            for part in line.split(","):
                if "passed" in part:
                    tests_passed = int(part.strip().split()[0])
                elif "failed" in part:
                    tests_failed = int(part.strip().split()[0])
                elif "skipped" in part:
                    tests_skipped = int(part.strip().split()[0])

    return {
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "tests_skipped": tests_skipped,
        "passed": tests_failed == 0,
    }


def collect_security_metrics(worktree: Path) -> dict:
    """采集安全合规指标"""
    code, stdout, stderr = run_command(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(worktree),
    )
    modified_files = stdout.strip().splitlines() if stdout.strip() else []
    
    unsafe_modified = []
    review_required = []
    for f in modified_files:
        for pattern in UNSAFE_FILES:
            if pattern.endswith("/"):
                if f.startswith(pattern):
                    unsafe_modified.append(f)
            else:
                if f == pattern:
                    review_required.append(f)

    return {
        "unsafe_files_modified": unsafe_modified,
        "review_required_files_modified": review_required,
        "passed": len(unsafe_modified) == 0,
    }


def collect_e2e_metrics(worktree: Path, scripts: list[str]) -> dict:
    """采集端到端验证指标"""
    total = len(scripts)
    passed = 0
    failed = 0
    details = []
    for script in scripts:
        script_path = worktree / script
        if script_path.exists():
            code, stdout, stderr = run_command(
                ["bash", str(script_path)],
                cwd=str(worktree),
            )
            if code == 0:
                passed += 1
                details.append({"script": script, "status": "passed"})
            else:
                failed += 1
                details.append({"script": script, "status": "failed", "error": stderr})
        else:
            details.append({"script": script, "status": "not_found"})

    return {
        "e2e_tests_run": total,
        "e2e_tests_passed": passed,
        "e2e_tests_failed": failed,
        "details": details,
        "passed": failed == 0 and total > 0,
    }


def generate_report(
    worktree: Path,
    venv_python: str,
    output_dir: Path,
    task_title: str = "自开发任务",
    branch: str = "unknown",
    e2e_scripts: list[str] = None,
) -> Path:
    """生成完整监测报告"""
    e2e_scripts = e2e_scripts or []
    
    report = {
        "report_id": f"self-dev-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "task_title": task_title,
        "branch": branch,
        "generated_at": datetime.now().isoformat(),
        "metrics": {
            "code_quality": {
                **collect_lint_metrics(worktree),
                **collect_complexity_metrics(worktree),
            },
            "test_quality": collect_test_metrics(worktree, venv_python),
            "security_compliance": collect_security_metrics(worktree),
        },
    }

    # E2E 验证（可选）
    if e2e_scripts:
        report["metrics"]["functional_verification"] = collect_e2e_metrics(
            worktree, e2e_scripts
        )

    # 汇总
    all_passed = True
    issues = []
    for category, metrics in report["metrics"].items():
        if isinstance(metrics, dict) and "passed" in metrics:
            if not metrics["passed"]:
                all_passed = False
                issues.append(f"{category} check failed")
        elif isinstance(metrics, dict):
            for sub_key, sub_val in metrics.items():
                if isinstance(sub_val, dict) and "passed" in sub_val:
                    if not sub_val["passed"]:
                        all_passed = False
                        issues.append(f"{category}.{sub_key} check failed")

    report["status"] = "passed" if all_passed else "failed"
    report["summary"] = {
        "all_passed": all_passed,
        "issues": issues,
        "recommendation": "ready_for_merge" if all_passed else "needs_review",
    }

    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{report['report_id']}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return output_file


def main():
    parser = argparse.ArgumentParser(description="生成自开发监测报告")
    parser.add_argument("--worktree", required=True, help="worktree 路径")
    parser.add_argument("--python", required=True, help="venv Python 路径")
    parser.add_argument("--output", default="docs/self-dev/reports/", help="输出目录")
    parser.add_argument("--title", default="自开发任务", help="任务标题")
    parser.add_argument("--branch", default="unknown", help="分支名")
    parser.add_argument("--e2e-scripts", nargs="*", default=[], help="E2E 验证脚本路径")
    args = parser.parse_args()

    report_path = generate_report(
        worktree=Path(args.worktree),
        venv_python=args.python,
        output_dir=Path(args.output),
        task_title=args.title,
        branch=args.branch,
        e2e_scripts=args.e2e_scripts,
    )
    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    main()
```

---

## 4. 实施计划

### 4.1 阶段划分

| 阶段 | 内容 | 交付物 | 工作量 |
|------|------|--------|--------|
| **10.1** | 项目约束 | `AGENTS.md` | 0.5 天 |
| **10.2** | 任务模板 + 流程文档 | `docs/self-dev/task-template.yaml`<br>`docs/self-dev/README.md` | 0.5 天 |
| **10.3** | 验证脚本 + 监测脚本 | `docs/self-dev/scripts/verify_*.sh`<br>`docs/self-dev/scripts/generate_monitor_report.py` | 1 天 |
| **10.4** | MVP 任务端到端验证 | 用系统自己开发"AgentMemory 查询 API"<br>生成监测报告 | 1-2 天 |

### 4.2 MVP 任务详情

**任务**：新增 AgentMemory 查询 API

| 项目 | 值 |
|------|-----|
| 端点 | `POST /api/memory/search` |
| 请求体 | `{"query": "关键词", "limit": 10, "offset": 0}` |
| 响应体 | `{"results": [...], "total": N}` |
| 隔离 | `git worktree add .worktrees/feature-memory-search -b feature/memory-search-api` |
| 验证 | pytest + verify_memory_search.sh |
| 监测 | generate_monitor_report.py |

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Agent 改了核心文件 | 破坏系统 | `AGENTS.md` 约束 + 监测脚本检测 + 人工最终确认 |
| 测试通过但功能不对 | 错误功能上线 | E2E 验证脚本覆盖真实场景 |
| 开发过程无限循环 | 浪费 token | 监测报告中的 LLM 调用次数/修复迭代阈值 |
| worktree 创建失败 | 无法隔离 | 降级为普通 git branch |

---

## 6. 验收标准

1. 项目有 `AGENTS.md` 约束文件
2. 有完整的任务模板、验证脚本、监测脚本
3. MVP 任务用系统自己的流水线完成（不手动写代码）
4. 生成完整的监测报告，所有指标达标
5. 整个过程系统核心代码零改动

---

## 7. 附录

### 7.1 完整文件清单

```
multi-agent-orchestration/
├── AGENTS.md                              ← 新增
├── docs/
│   └── self-dev/
│       ├── README.md                      ← 新增
│       ├── task-template.yaml             ← 新增
│       ├── scripts/
│       │   ├── verify_memory_search.sh    ← 新增
│       │   └── generate_monitor_report.py ← 新增
│       └── reports/                       ← 新增（运行时生成）
│           └── self-dev-{timestamp}.json
└── （系统核心代码零改动）
```

### 7.2 监测报告字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_id` | string | 唯一标识 |
| `task_title` | string | 任务标题 |
| `branch` | string | 开发分支 |
| `generated_at` | string | 生成时间 |
| `status` | string | passed / failed |
| `metrics.code_quality.lint_errors` | int | Lint 错误数 |
| `metrics.code_quality.lint_warnings` | int | Lint 警告数 |
| `metrics.code_quality.max_complexity` | int | 最大圈复杂度 |
| `metrics.code_quality.passed` | bool | 代码质量是否达标 |
| `metrics.test_quality.tests_passed` | int | 通过测试数 |
| `metrics.test_quality.tests_failed` | int | 失败测试数 |
| `metrics.test_quality.coverage_percent` | float | 覆盖率（如采集） |
| `metrics.test_quality.passed` | bool | 测试是否达标 |
| `metrics.security_compliance.unsafe_files_modified` | list | 被修改的核心文件 |
| `metrics.security_compliance.passed` | bool | 安全是否达标 |
| `metrics.functional_verification.e2e_tests_passed` | int | E2E 通过数 |
| `metrics.functional_verification.passed` | bool | 功能验证是否达标 |
| `summary.all_passed` | bool | 所有检查是否通过 |
| `summary.issues` | list | 问题列表 |
| `summary.recommendation` | string | ready_for_merge / needs_review |
