#!/usr/bin/env python
"""
Phase 8 自举执行 — 子功能 4: 第三方集成 (GitHub/Jira/Slack)

使用 LangGraph 完整编排执行
"""

import asyncio
import os
import sys
import yaml
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / "docs" / "planning"
PLANNING_DIR.mkdir(parents=True, exist_ok=True)

def get_api():
    conf = yaml.safe_load((Path.home() / ".hermes" / "config.yaml").read_text())
    m = conf.get("model", {})
    return {"api_key": m.get("api_key", ""), "base_url": m.get("base_url", "https://coding.dashscope.aliyuncs.com/apps/anthropic")}

API = get_api()


async def main():
    print("\n" + "🚀" * 30)
    print("  Phase 8 自举执行 — 子功能 4: 第三方集成")
    print("  使用 LangGraph 编排")
    print("🚀" * 30)
    
    start = datetime.now()
    
    from src.plan.planner import PlannerAgent
    from src.config.loader import ConfigLoader
    from src.workflows.config_builder import ConfigurableWorkflowBuilder
    from src.workflows.states import create_dynamic_initial_state
    from src.plan.graph import PlanGraph, PlanNode, ExecutorCapability
    
    # ── Step 1: PlannerAgent 生成 PlanGraph ──
    print("\n📋 Step 1: PlannerAgent (MiniMax-M2.5) 生成 PlanGraph...")
    
    task = """
实现 Phase 8 的第三方集成功能。

参考设计: docs/design/phase8-advanced-features.md 第六部分

需求:
1. GitHubIntegration 类:
   - __init__(token, owner, repo)
   - create_pr(title, body, head, base="main") → dict
   - create_issue(title, body, labels=None) → dict
   - list_issues(state="open") → list
   - create_comment(issue_number, body) → dict

2. JiraIntegration 类:
   - __init__(server, user, api_token)
   - create_issue(project, summary, description, issue_type="Task") → dict
   - get_issue(issue_key) → dict
   - transition_issue(issue_key, transition_id) → dict
   - add_comment(issue_key, body) → dict

3. SlackNotifier 类:
   - __init__(webhook_url)
   - send_message(text, blocks=None) → dict
   - send_code_snippet(text, language="python") → dict

4. 文件: src/integrations/__init__.py, src/integrations/github.py, src/integrations/jira.py, src/integrations/slack.py
5. 测试: tests/test_phase8_integrations.py (使用 mock，不实际调用 API)

注意:
- 所有 API 调用使用 requests 或 httpx (同步)
- 测试使用 unittest.mock 或 responses mock HTTP 请求
- 不要实际调用外部 API
"""
    
    planner = PlannerAgent(model="MiniMax-M2.5", api_key=API["api_key"], base_url=API["base_url"])
    plan = await planner.generate_plan(task)
    
    print(f"   ✅ {len(plan.nodes)} nodes")
    for nid, node in plan.nodes.items():
        deps = f" → deps: {node.dependencies}" if node.dependencies else ""
        print(f"   [{nid}] {node.name} ({node.required_capability.value}){deps}")
    
    plan_doc = PLANNING_DIR / "phase8-integrations-plan.md"
    plan_doc.write_text(f"# Phase 8: 第三方集成\n> {datetime.now().isoformat()}\n{plan.to_json()}", encoding="utf-8")
    
    # ── Step 2: 构建 LangGraph ──
    print("\n🔧 Step 2: 构建 LangGraph 工作流...")
    
    loader = ConfigLoader()
    cfg = loader.load("config/workflows/phase8-bootstrap.yaml")
    builder = ConfigurableWorkflowBuilder(cfg)
    builder._register_executors()
    builder._dynamic_builder._plan = plan
    builder._dynamic_builder._registry = builder._executor_registry
    app = builder._dynamic_builder.build()
    
    state = create_dynamic_initial_state(
        task="Phase 8: 第三方集成 (GitHub/Jira/Slack)",
        plan_graph=plan,
        project_path=str(PROJECT_ROOT),
    )
    
    print(f"   ✅ 注册了 {len(builder._executor_registry.list_all())} 个 Executor")
    print(f"   ✅ LangGraph 编译完成")
    
    # ── Step 3: 编排执行 ──
    print("\n🚀 Step 3: LangGraph 编排执行...")
    final = await app.ainvoke(state)
    
    results = final.get("executor_results", {})
    for nid, r in results.items():
        success = r.get("success", False) if isinstance(r, dict) else False
        print(f"   {'✅' if success else '❌'} [{nid}] success={success}")
    
    # ── Step 4: pytest 验证 ──
    print("\n🧪 Step 4: 运行 pytest...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_phase8_integrations.py", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
    )
    
    lines = result.stdout.split("\n")
    for line in lines:
        if "PASSED" in line or "FAILED" in line or "passed" in line or "failed" in line:
            print(f"   {line}")
    
    tests_passed = result.returncode == 0
    
    elapsed = (datetime.now() - start).total_seconds()
    
    print("\n" + "=" * 60)
    if tests_passed:
        print(f"✅ Phase 8 子功能 4 完成！耗时 {elapsed:.0f}s")
    else:
        print("⚠️  测试未通过，需要修复")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
