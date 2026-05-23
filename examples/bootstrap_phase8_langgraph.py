#!/usr/bin/env python
"""
Phase 8 自举执行 — 子功能 1: 多项目管理 (WorkspaceManager)

使用 LangGraph 完整编排系统真实执行:
1. 加载 YAML 配置
2. PlannerAgent (MiniMax-M2.5) 生成 PlanGraph
3. ConfigurableWorkflowBuilder 注册真实 Executor + 编译 LangGraph
4. LangGraph 编排执行: plan → review → test → develop → review → verify
5. 自动修复闭环 (replan)
"""

import asyncio
import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
PLANNING_DIR = DOCS_DIR / "planning"
PLANNING_DIR.mkdir(parents=True, exist_ok=True)

# ── 读取 API 配置 ──
def get_api_config():
    conf_path = Path.home() / ".hermes" / "config.yaml"
    if conf_path.exists():
        conf = yaml.safe_load(conf_path.read_text())
        m = conf.get("model", {})
        return {
            "api_key": m.get("api_key", ""),
            "base_url": m.get("base_url", "https://coding.dashscope.aliyuncs.com/apps/anthropic"),
        }
    return {"api_key": os.environ.get("DASHSCOPE_API_KEY", ""), "base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic"}

API = get_api_config()


# ═══════════════════════════════════════════════════════════
# Step 1: PlannerAgent 生成 PlanGraph
# ═══════════════════════════════════════════════════════════
async def generate_plangraph():
    from src.plan.planner import PlannerAgent
    
    print("📋 Step 1: PlannerAgent (MiniMax-M2.5) 生成 PlanGraph...")
    
    task = """
实现 Phase 8 的多项目管理功能 (WorkspaceManager)。

需求:
1. ProjectConfig 和 WorkspaceConfig 数据类 (dataclass)
2. WorkspaceManager 类: CRUD、.workspace.yaml 持久化、项目模板
3. 文件: src/workspace/__init__.py, src/workspace/manager.py
4. 测试: tests/test_phase8_workspace.py (100% 覆盖)

请生成执行计划 DAG。每个节点 type 从这些选:
requirements_analysis, technical_design, code_development, code_review, testing, documentation
"""
    
    planner = PlannerAgent(
        model="MiniMax-M2.5",
        api_key=API["api_key"],
        base_url=API["base_url"],
    )
    plan = await planner.generate_plan(task)
    
    print(f"   ✅ {len(plan.nodes)} nodes, type={plan.plan_type}")
    for nid, node in plan.nodes.items():
        deps = f" → deps: {node.dependencies}" if node.dependencies else ""
        print(f"   [{nid}] {node.name} ({node.required_capability.value}){deps}")
    
    # 保存方案
    plan_doc = PLANNING_DIR / "phase8-workspace-langgraph-plan.md"
    content = f"""# Phase 8 LangGraph 自执方案: 多项目管理

> 生成时间: {datetime.now().isoformat()}
> Planner: MiniMax-M2.5
> 类型: {plan.plan_type}

{plan.to_json()}
"""
    plan_doc.write_text(content, encoding="utf-8")
    
    return plan


# ═══════════════════════════════════════════════════════════
# Step 2: 构建 LangGraph 工作流 + 注册真实 Executor
# ═══════════════════════════════════════════════════════════
def build_workflow(plan):
    from src.config.loader import ConfigLoader
    from src.workflows.config_builder import ConfigurableWorkflowBuilder
    from src.workflows.states import create_dynamic_initial_state
    from src.executors.registry import ExecutorRegistry
    from src.plan.graph import PlanNode, NodeType, ExecutorCapability
    
    print("\n🔧 Step 2: 构建 LangGraph 工作流...")
    
    # 加载配置获取 Executor 模型分配
    loader = ConfigLoader()
    cfg = loader.load("config/workflows/phase8-bootstrap.yaml")
    
    # 创建 Builder 并注册 Executor
    builder = ConfigurableWorkflowBuilder(cfg)
    builder._register_executors()  # 必须先注册 Executor
    registry = builder._executor_registry
    
    print(f"   ✅ 注册了 {len(registry.list_all())} 个 Executor:")
    for exec in registry.list_all():
        caps = [c.value for c in exec.capabilities]
        model = getattr(exec._agent, 'claude_config', None)
        model_name = model.model if model else 'unknown'
        print(f"     {exec.name}: model={model_name}, caps={caps}")
    
    # 用 Planner 生成的 PlanGraph (替换配置中的静态 flow_template)
    # 需要将 PlanGraph 转为 ConfigurableWorkflowBuilder 能理解的格式
    builder._dynamic_builder._plan = plan
    builder._dynamic_builder._registry = registry
    
    app = builder._dynamic_builder.build()
    print(f"   ✅ LangGraph StateGraph 编译完成")
    
    # 创建初始状态
    state = create_dynamic_initial_state(
        task="Phase 8: 实现 WorkspaceManager 多项目管理",
        plan_graph=plan,
        project_path=str(PROJECT_ROOT),
    )
    
    return app, state


# ═══════════════════════════════════════════════════════════
# Step 3: LangGraph 编排执行
# ═══════════════════════════════════════════════════════════
async def execute_workflow(app, initial_state):
    print("\n🚀 Step 3: LangGraph 编排执行...")
    print("   (Agent 通过全局状态交接，文件系统协作)")
    
    # LangGraph ainvoke 异步调用
    final_state = await app.ainvoke(initial_state)
    
    # 打印执行摘要
    print("\n📊 执行摘要:")
    executor_results = final_state.get("executor_results", {})
    for node_id, result in executor_results.items():
        success = result.get("success", False) if isinstance(result, dict) else False
        status = "✅" if success else "❌"
        print(f"   {status} [{node_id}] success={success}")
    
    completed = final_state.get("completed_nodes", [])
    failed = final_state.get("failed_nodes", [])
    print(f"\n   完成节点: {completed}")
    if failed:
        print(f"   失败节点: {failed}")
    
    return final_state


# ═══════════════════════════════════════════════════════════
# Step 4: 运行 pytest 最终验证
# ═══════════════════════════════════════════════════════════
async def final_verification():
    print("\n🧪 Step 4: 运行 pytest 最终验证...")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_phase8_workspace.py", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
    )
    
    lines = result.stdout.split("\n")
    for line in lines:
        if "PASSED" in line or "FAILED" in line or "passed" in line or "failed" in line:
            print(f"   {line}")
    
    return result.returncode == 0


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    print("\n" + "🚀" * 30)
    print("  Phase 8 自举执行 — 子功能 1: 多项目管理")
    print("  使用 LangGraph 完整编排 (非串行脚本)")
    print("🚀" * 30)
    
    start = datetime.now()
    
    # Step 1: Planner 生成 PlanGraph
    plan = await generate_plangraph()
    
    # Step 2: 构建 LangGraph 工作流
    app, state = build_workflow(plan)
    
    # Step 3: 编排执行
    final_state = await execute_workflow(app, state)
    
    # Step 4: pytest 验证
    tests_passed = await final_verification()
    
    elapsed = (datetime.now() - start).total_seconds()
    
    print("\n" + "=" * 60)
    if tests_passed:
        print("✅ Phase 8 子功能 1 LangGraph 自执完成！")
        print(f"   耗时: {elapsed:.0f}s")
        print(f"   代码: src/workspace/manager.py")
        print(f"   测试: tests/test_phase8_workspace.py")
    else:
        print("⚠️  测试未通过，需要修复")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
