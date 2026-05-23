#!/usr/bin/env python
"""
Phase 8 自举执行 — 子功能 5: Web UI (FastAPI + React + WebSocket)

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
    print("  Phase 8 自举执行 — 子功能 5: Web UI")
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
实现 Phase 8 的 Web UI 后端部分 (FastAPI + WebSocket)。

参考设计: docs/design/phase8-advanced-features.md 第五部分

需求 (只实现后端，不实现前端 React):
1. WebSocketManager 类 (src/api/ws.py):
   - connect(task_id, websocket)
   - disconnect(task_id, websocket)
   - broadcast(task_id, message: dict)
   - 处理连接异常和死连接清理

2. FastAPI routes 扩展:
   - src/api/routes/ws.py — WebSocket endpoint /ws/{task_id}
   - src/api/routes/health.py — 已有，保持
   - 在 src/api/routes/__init__.py 中注册新路由

3. 实时事件推送:
   - 当 execution 状态变化时，通过 WebSocket 推送事件
   - 事件格式: {"type": "execution_update", "task_id": "...", "status": "...", "data": {...}}

4. 测试: tests/test_phase8_websocket.py
   - 测试 WebSocketManager 的连接/断开/广播
   - 使用 asyncio + mock websocket

注意:
- 只做后端 FastAPI + WebSocket，不做前端 React
- 使用 httpx 或 starlette 测试 WebSocket
- 所有测试用 mock，不启动真实服务器
"""
    
    planner = PlannerAgent(model="qwen3.6-plus", api_key=API["api_key"], base_url=API["base_url"])
    plan = await planner.generate_plan(task)
    
    print(f"   ✅ {len(plan.nodes)} nodes")
    for nid, node in plan.nodes.items():
        deps = f" → deps: {node.dependencies}" if node.dependencies else ""
        print(f"   [{nid}] {node.name} ({node.required_capability.value}){deps}")
    
    plan_doc = PLANNING_DIR / "phase8-webui-plan.md"
    plan_doc.write_text(f"# Phase 8: Web UI 后端\n> {datetime.now().isoformat()}\n{plan.to_json()}", encoding="utf-8")
    
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
        task="Phase 8: Web UI 后端 (FastAPI + WebSocket)",
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
        [sys.executable, "-m", "pytest", "tests/test_phase8_websocket.py", "-v", "--tb=short"],
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
        print(f"✅ Phase 8 子功能 5 完成！耗时 {elapsed:.0f}s")
        print()
        print("Phase 8 全部完成 (1,2,5) ✅")
        print("  1. 多项目管理 ✅")
        print("  2. 知识库与记忆 ✅")
        print("  5. Web UI 后端 ✅")
    else:
        print("⚠️  测试未通过，需要修复")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
