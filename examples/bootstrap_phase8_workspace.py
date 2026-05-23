#!/usr/bin/env python
"""
Phase 8 自举执行 — 子功能 1: 多项目管理 (WorkspaceManager)

用系统真实 Agent 执行 5 步流程:
1. PlannerAgent (MiniMax-M2.5) → 生成技术方案
2. DeveloperAgent (qwen3.6-plus) → 编写测试和实现
3. ReviewerAgent (kimi-k2.5) → 代码审查
4. TesterAgent (qwen3.6-plus) → 运行测试验证
5. 自动修复闭环
"""

import asyncio
import os
import sys
import json
import yaml
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

def log(step, msg):
    print(f"\n{'='*60}")
    print(f"  Step {step}: {msg}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════
# STEP 1: PlannerAgent 生成技术方案
# ═══════════════════════════════════════════════════════════
async def step1_plan():
    log("1", "PlannerAgent (MiniMax-M2.5) 生成技术方案")
    
    from src.plan.planner import PlannerAgent
    
    task = """
实现 Phase 8 的多项目管理功能 (WorkspaceManager)。

参考设计: docs/design/phase8-advanced-features.md 第二部分

需求:
1. ProjectConfig 和 WorkspaceConfig 数据类
2. WorkspaceManager 类：CRUD 操作、配置持久化、项目模板
3. .workspace.yaml 配置文件读写
4. 文件放在 src/workspace/manager.py 和 src/workspace/__init__.py
5. 测试放在 tests/test_phase8_workspace.py
6. 需要 100% 测试覆盖率

请生成一个详细的实施计划 (DAG 节点)，包含:
- 数据类定义
- 核心方法实现  
- 持久化逻辑
- 模板功能
- 测试用例
"""
    
    planner = PlannerAgent(model="MiniMax-M2.5", api_key=API["api_key"], base_url=API["base_url"])
    plan = await planner.generate_plan(task)
    
    print(f"\n📋 Plan 生成完成: {plan.plan_type}")
    print(f"   节点数: {len(plan.nodes)}")
    for nid, node in plan.nodes.items():
        deps = f" → deps: {node.dependencies}" if node.dependencies else ""
        print(f"   [{nid}] {node.name}{deps}")
    
    # 保存方案
    plan_doc = PLANNING_DIR / "phase8-workspace-llm-plan.md"
    content = f"""# Phase 8 自执方案: 多项目管理

> 生成时间: {datetime.now().isoformat()}
> Planner: MiniMax-M2.5
> 类型: {plan.plan_type}

## 执行计划

{plan.to_json()}

## 节点详情

"""
    for nid, node in plan.nodes.items():
        content += f"\n### {nid}: {node.name}\n- 描述: {node.description}\n- 能力: {node.required_capability.value}\n- 依赖: {node.dependencies or '无'}\n"
    
    plan_doc.write_text(content, encoding="utf-8")
    print(f"\n📄 方案已保存: {plan_doc}")
    
    return plan


# ═══════════════════════════════════════════════════════════
# STEP 2: DeveloperAgent 编写测试和实现代码
# ═══════════════════════════════════════════════════════════
async def step2_develop(plan):
    log("2", "DeveloperAgent (qwen3.6-plus) 编写测试和实现")
    
    from src.agents.developer import DeveloperAgent
    
    dev = DeveloperAgent(api_key=API["api_key"], model="qwen3.6-plus")
    
    # 2.1 先写测试 (TDD)
    print("\n📝 2.1 编写测试用例...")
    
    test_task = f"""
你是 Python 测试工程师。请为多项目管理功能编写完整的 pytest 测试。

项目路径: {PROJECT_ROOT}
测试文件: tests/test_phase8_workspace.py

功能需求:
1. ProjectConfig 数据类测试
   - 创建、默认值验证
   - __post_init__ 自动填充时间
   
2. WorkspaceConfig 数据类测试
   - 创建、带项目的配置
   
3. WorkspaceManager CRUD 测试
   - create_project: 创建项目并保存到 .workspace.yaml
   - switch_project: 切换当前项目，不存在则 ValueError
   - get_current_project: 获取当前项目
   - list_projects: 列出所有项目
   - delete_project: 删除项目
   
4. 持久化测试
   - create_project 后检查 .workspace.yaml 存在且内容正确
   - 从已存在的 .workspace.yaml 自动加载
   
5. 模板测试
   - 使用模板创建项目时复制文件
   
6. 边界情况
   - 重复创建（覆盖）
   - 删除不存在的项目
   - YAML 格式正确性
   - 标签持久化

要求:
- 使用 pytest.fixture 创建 temp_dir
- 每个测试一个功能点
- 使用 assert 验证
- 约 15-20 个测试

请直接使用 write_file 工具写入 tests/test_phase8_workspace.py
"""
    
    result = await dev.run(test_task)
    if result.success:
        print("  ✅ 测试编写完成")
    else:
        print(f"  ⚠️  测试编写可能有误: {result.error}")
    
    # 2.2 编写实现代码
    print("\n📝 2.2 编写实现代码...")
    
    impl_task = f"""
你是 Python 开发工程师。根据以下需求实现多项目管理功能。

项目路径: {PROJECT_ROOT}

需要创建的文件:
1. src/workspace/__init__.py — 模块导出
2. src/workspace/manager.py — WorkspaceManager 实现

实现需求:

ProjectConfig (dataclass):
- name: str, root_path: str, description: str=""
- created_at: str="", updated_at: str=""
- default_workflow: str="software-development"
- vars: dict = field(default_factory=dict)
- tags: list = field(default_factory=list)
- __post_init__: 自动填充 created_at 和 updated_at

WorkspaceConfig (dataclass):
- name: str
- projects: dict = field(default_factory=dict)
- default_project: Optional[str] = None
- shared_tools: list, shared_env: dict

WorkspaceManager 类:
- WORKSPACE_FILE = ".workspace.yaml"
- __init__(root_path="."): 加载配置
- _load_workspace() -> WorkspaceConfig: 从 YAML 加载
- _save_workspace(): 保存到 YAML
- create_project(name, path, description="", template=None) -> ProjectConfig
- switch_project(name) -> ProjectConfig (不存在 raise ValueError)
- get_current_project() -> Optional[ProjectConfig]
- list_projects() -> list[ProjectConfig]
- delete_project(name) -> None
- _apply_template(name, path, template): 从项目根目录的父级 templates/ 复制

注意:
- 使用 yaml 和 pathlib
- 使用 dataclass
- _apply_template 的模板路径: self.root.parent / "templates" / template
- _save_workspace 只保存 root_path, description, tags, vars 字段
- 使用 shutil.copytree 时 dirs_exist_ok=True

请直接使用 write_file 工具写入文件。
"""
    
    result = await dev.run(impl_task)
    if result.success:
        print("  ✅ 实现代码编写完成")
    else:
        print(f"  ⚠️  实现代码可能有误: {result.error}")
    
    return result.success


# ═══════════════════════════════════════════════════════════
# STEP 3: 运行测试验证
# ═══════════════════════════════════════════════════════════
async def step3_test():
    log("3", "运行测试验证")
    
    import subprocess
    
    print("\n🧪 运行 pytest...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_phase8_workspace.py", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
    )
    
    # 只显示关键输出
    lines = result.stdout.split("\n")
    for line in lines:
        if "PASSED" in line or "FAILED" in line or "ERROR" in line or "passed" in line or "failed" in line:
            print(f"  {line}")
    
    if result.returncode == 0:
        passed_count = [l for l in lines if "passed" in l]
        print(f"\n✅ {passed_count[-1] if passed_count else '全部通过'}")
        return True
    else:
        print(f"\n❌ 测试失败")
        # 显示失败详情
        for line in lines:
            if "FAILED" in line or "AssertionError" in line or "Error" in line:
                print(f"  {line}")
        print("\n" + result.stderr[-500:] if result.stderr else "")
        return False


# ═══════════════════════════════════════════════════════════
# STEP 4: ReviewerAgent 代码审查
# ═══════════════════════════════════════════════════════════
async def step4_review():
    log("4", "ReviewerAgent (kimi-k2.5) 代码审查")
    
    from src.agents.reviewer import ReviewerAgent
    
    reviewer = ReviewerAgent(api_key=API["api_key"], model="kimi-k2.5")
    
    review_task = f"""
你是代码审查专家。请审查以下实现代码。

项目路径: {PROJECT_ROOT}
文件:
- src/workspace/manager.py
- src/workspace/__init__.py
- tests/test_phase8_workspace.py

审查要点:
1. 类型注解是否完整
2. 错误处理是否充分
3. 测试覆盖是否全面
4. 代码风格和规范
5. 是否有安全或逻辑 bug

请使用 read_file 工具读取并审查上述文件。
输出审查报告，指出问题并给出修改建议（如有）。
"""
    
    result = await reviewer.run(review_task)
    if result.success:
        print("\n📖 审查完成:")
        output = result.output or "审查完成"
        print(f"  {output[:500]}...")
    else:
        print(f"  ⚠️  审查失败: {result.error}")
    
    return result.success


# ═══════════════════════════════════════════════════════════
# STEP 5: 自动修复闭环
# ═══════════════════════════════════════════════════════════
async def step5_fix(max_attempts=2):
    log("5", "自动修复闭环")
    
    for attempt in range(1, max_attempts + 1):
        passed = await step3_test()
        if passed:
            print(f"\n✅ 第 {attempt} 次测试通过，无需修复")
            return True
        
        # 获取测试失败信息
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_phase8_workspace.py", "-v", "--tb=short"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
        )
        
        print(f"\n🔧 第 {attempt} 次修复...")
        
        from src.agents.developer import DeveloperAgent
        dev = DeveloperAgent(api_key=API["api_key"], model="qwen3.6-plus")
        
        fix_task = f"""
你是修复专家。以下测试失败了，请修复代码。

测试输出:
{result.stdout[-2000:] if result.stdout else '无输出'}

项目路径: {PROJECT_ROOT}
实现文件: src/workspace/manager.py
测试文件: tests/test_phase8_workspace.py

请使用 read_file 读取文件，分析失败原因，然后修复。
修复后使用 write_file 保存。
"""
        
        await dev.run(fix_task)
    
    # 最终测试
    return await step3_test()


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    print("\n" + "🚀" * 30)
    print("  Phase 8 自举执行 — 子功能 1: 多项目管理")
    print("  使用真实 Agent 执行 (非 Mock)")
    print("🚀" * 30)
    
    start = datetime.now()
    
    # Step 1: Plan
    plan = await step1_plan()
    
    # Step 2: Develop (TDD: test + impl)
    dev_ok = await step2_develop(plan)
    if not dev_ok:
        print("\n❌ 开发失败，终止")
        return
    
    # Step 3: Test
    tests_passed = await step3_test()
    
    if not tests_passed:
        # Step 5: Fix
        tests_passed = await step5_fix()
    
    # Step 4: Review
    if tests_passed:
        await step4_review()
    
    elapsed = (datetime.now() - start).total_seconds()
    
    print("\n" + "=" * 60)
    if tests_passed:
        print("✅ Phase 8 子功能 1 自举完成！")
        print(f"   耗时: {elapsed:.0f}s")
        print(f"   方案: {PLANNING_DIR / 'phase8-workspace-llm-plan.md'}")
        print(f"   代码: src/workspace/manager.py")
        print(f"   测试: tests/test_phase8_workspace.py")
    else:
        print("⚠️  部分测试未通过，需要人工介入")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
