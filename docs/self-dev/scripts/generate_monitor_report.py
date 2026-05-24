#!/usr/bin/env python3
"""
generate_monitor_report.py
采集执行数据，生成自开发监测报告。

运行方式：
  python generate_monitor_report.py \
    --worktree .worktrees/feature-memory-search \
    --python .venv/bin/python \
    --output docs/self-dev/reports/ \
    --title "新增 AgentMemory 查询 API" \
    --branch feature/memory-search-api
"""

import argparse
import json
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


def run_cmd(cmd: list[str], cwd: str = None, timeout: int = 120) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def collect_lint_metrics(worktree: Path) -> dict:
    code, stdout, stderr = run_cmd(["ruff", "check", "--output-format=json", "src/"], cwd=str(worktree))
    lint_errors = 0
    lint_warnings = 0
    if stdout:
        try:
            results = json.loads(stdout)
            for file_result in results:
                for msg in file_result.get("messages", []):
                    level = msg.get("severity") or msg.get("level", "error")
                    if level in ("error", 1):
                        lint_errors += 1
                    elif level in ("warning", 2):
                        lint_warnings += 1
        except json.JSONDecodeError:
            pass
    if code != 0 and lint_errors == 0:
        lint_errors = 1
    return {"lint_errors": lint_errors, "lint_warnings": lint_warnings, "passed": lint_errors == 0}


def collect_test_metrics(worktree: Path, venv_python: str) -> dict:
    code, stdout, stderr = run_cmd(
        [venv_python, "-m", "pytest", "tests/",
         "--ignore=tests/ui/", "--ignore=tests/knowledge/",
         "-v", "--tb=short"],
        cwd=str(worktree), timeout=180
    )
    tests_passed = tests_failed = tests_skipped = 0
    for line in stdout.splitlines():
        if "passed" in line or "failed" in line or "skipped" in line:
            for part in line.split(","):
                part = part.strip()
                if part.endswith("passed"):
                    try:
                        tests_passed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif part.endswith("failed"):
                    try:
                        tests_failed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif part.endswith("skipped"):
                    try:
                        tests_skipped = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
    return {
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "tests_skipped": tests_skipped,
        "passed": tests_failed == 0,
    }


def collect_security_metrics(worktree: Path) -> dict:
    code, stdout, stderr = run_cmd(["git", "diff", "--name-only", "HEAD"], cwd=str(worktree))
    modified = [f for f in stdout.strip().splitlines() if f]
    unsafe_modified = []
    review_required = []
    for f in modified:
        for pattern in UNSAFE_FILES:
            if pattern.endswith("/"):
                if f.startswith(pattern):
                    unsafe_modified.append(f)
            elif f == pattern:
                review_required.append(f)
    return {
        "unsafe_files_modified": unsafe_modified,
        "review_required_files_modified": review_required,
        "passed": len(unsafe_modified) == 0,
    }


def collect_e2e_metrics(worktree: Path, scripts: list[str]) -> dict:
    total = passed = failed = 0
    details = []
    for script in scripts:
        sp = worktree / script
        if sp.exists():
            code, stdout, stderr = run_cmd(["bash", str(sp)], cwd=str(worktree))
            total += 1
            if code == 0:
                passed += 1
                details.append({"script": script, "status": "passed"})
            else:
                failed += 1
                details.append({"script": script, "status": "failed", "error": stderr[:500]})
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
    e2e_scripts = e2e_scripts or []
    report = {
        "report_id": f"self-dev-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "task_title": task_title,
        "branch": branch,
        "generated_at": datetime.now().isoformat(),
        "metrics": {
            "code_quality": collect_lint_metrics(worktree),
            "test_quality": collect_test_metrics(worktree, venv_python),
            "security_compliance": collect_security_metrics(worktree),
        },
    }
    if e2e_scripts:
        report["metrics"]["functional_verification"] = collect_e2e_metrics(worktree, e2e_scripts)

    all_passed = True
    issues = []
    for cat, metrics in report["metrics"].items():
        if isinstance(metrics, dict):
            for key, val in metrics.items():
                if key == "passed" and not val:
                    all_passed = False
                    issues.append(f"{cat} check failed")
                elif isinstance(val, dict) and "passed" in val and not val["passed"]:
                    all_passed = False
                    issues.append(f"{cat}.{key} check failed")

    report["status"] = "passed" if all_passed else "failed"
    report["summary"] = {
        "all_passed": all_passed,
        "issues": issues,
        "recommendation": "ready_for_merge" if all_passed else "needs_review",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{report['report_id']}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return out


def main():
    p = argparse.ArgumentParser(description="生成自开发监测报告")
    p.add_argument("--worktree", required=True, help="worktree 路径")
    p.add_argument("--python", required=True, help="venv Python 路径")
    p.add_argument("--output", default="docs/self-dev/reports/")
    p.add_argument("--title", default="自开发任务")
    p.add_argument("--branch", default="unknown")
    p.add_argument("--e2e-scripts", nargs="*", default=[])
    args = p.parse_args()

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
