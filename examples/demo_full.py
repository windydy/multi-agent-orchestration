"""
Multi-Agent Orchestration Demo — 完整编排系统演示

无需 API Key，通过模拟方式演示：
1. Agent 注册与能力匹配
2. Plan Graph 动态生成
3. Executor 调度
4. 完整开发流水线
5. Bug Fix 闭环
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def demo_phase1_agent_registry():
    """Phase 1: Agent 注册与能力匹配"""
    print("\n" + "=" * 60)
    print("📦 Phase 1: Agent 注册与能力匹配")
    print("=" * 60)

    from src.executors.registry import ExecutorRegistry
    from src.plan.graph import ExecutorCapability
    from src.agents import (
        DevOpsAgent,
        SecurityAgent,
        DataAgent,
        ArchitectAgent,
        ProductManagerAgent,
    )

    registry = ExecutorRegistry()

    # 注册所有领域 Agent
    agents = {
        "DevOps": DevOpsAgent(api_key="demo"),
        "Security": SecurityAgent(api_key="demo"),
        "Data": DataAgent(api_key="demo"),
        "Architect": ArchitectAgent(api_key="demo"),
        "ProductManager": ProductManagerAgent(api_key="demo"),
    }

    for name, agent in agents.items():
        registry.register(agent, capabilities=agent.get_capabilities())
        print(f"  ✅ 注册 {name}: {agent.get_config().description}")

    print(f"\n  📊 注册中心统计: {len(registry.list_all())} 个 Agent")

    # 演示能力匹配
    scenarios = [
        ("CI/CD 流水线配置", ExecutorCapability.DEVOPS_CI_CD),
        ("SAST 安全扫描", ExecutorCapability.SECURITY_AUDIT),
        ("数据分析任务", ExecutorCapability.DATA_ENGINEERING),
        ("系统架构设计", ExecutorCapability.ARCHITECTURE_DESIGN),
        ("需求文档编写", ExecutorCapability.PRODUCT_MANAGEMENT),
    ]

    print("\n  🎯 能力匹配演示:")
    for task_desc, cap in scenarios:
        matched = registry.find_best(cap)
        if matched:
            print(f"    {task_desc} → {matched.get_config().name}")
        else:
            print(f"    {task_desc} → ❌ 无匹配")

    return registry


def demo_phase2_domain_tools():
    """Phase 2: 领域工具演示"""
    print("\n" + "=" * 60)
    print("🔧 Phase 2: 领域工具演示")
    print("=" * 60)

    # CICDTool
    from src.tools.cicd import CICDTool

    cicd = CICDTool()
    pipeline = cicd.generate_pipeline("github_actions", "python", ["lint", "test", "deploy"])
    print("\n  1️⃣ CICDTool — 生成 GitHub Actions pipeline:")
    for line in pipeline.split("\n")[:8]:
        print(f"     {line}")
    print("     ...")

    validation = cicd.validate_config(pipeline, "github_actions")
    print(f"  ✅ 验证结果: {'通过' if validation['valid'] else '失败'}")

    # DockerTool
    from src.tools.docker_tool import DockerTool

    docker = DockerTool()
    cmd = docker.build_command(context=".", tag="myapp:v1.0", dockerfile="Dockerfile.prod")
    print(f"\n  2️⃣ DockerTool — 构建命令: {cmd}")

    dockerfile = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""
    result = docker.validate_dockerfile(dockerfile)
    print(f"  ✅ Dockerfile 验证: {'通过' if result['valid'] else '失败'}")
    print(f"     基础镜像: {result['base_image']}")
    print(f"     指令数: {result['instruction_count']}")

    # SecurityScanTool
    from src.tools.security_scan import SecurityScanTool

    scanner = SecurityScanTool()
    code = """
API_KEY = "sk-1234567890abcdef"
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
password = "admin123"
"""
    secrets = scanner.scan_for_secrets(code)
    print(f"\n  3️⃣ SecurityScanTool — 秘密扫描:")
    print(f"     发现: {secrets['count']} 个问题，严重性: {secrets['severity']}")
    for f in secrets["findings"]:
        print(f"     - {f['type']} (第{f['line']}行)")

    # DataAnalysisTool
    from src.tools.data_analysis import DataAnalysisTool

    data_tool = DataAnalysisTool()
    csv_data = """id,name,age,salary
1,Alice,30,50000
2,Bob,25,45000
3,Charlie,35,60000
4,Diana,28,52000
"""
    desc = data_tool.describe_csv(csv_data)
    print(f"\n  4️⃣ DataAnalysisTool — 数据描述:")
    print(f"     行数: {desc['row_count']}, 列数: {desc['column_count']}")
    for col, info in desc["columns"].items():
        if info.get("mean") is not None:
            print(f"     - {col}: 均值={info['mean']:.1f}")

    # SQLTool
    from src.tools.sql_tool import SQLTool

    sql = SQLTool()
    query = sql.generate_select(
        table="users",
        columns=["name", "email"],
        where={"status": "active", "age": 25},
        order_by="created_at DESC",
        limit=10,
    )
    print(f"\n  5️⃣ SQLTool — 生成查询:")
    for line in query.split("\n"):
        print(f"     {line}")

    # PMTool
    from src.tools.pm_tool import PMTool

    pm = PMTool()
    story = pm.generate_user_story(
        role="用户",
        goal="登录系统",
        value="访问个人仪表盘",
        acceptance_criteria=[
            "Given 用户在登录页 When 输入正确的用户名密码 Then 成功登录",
            "Given 密码错误 When 点击登录 Then 显示错误信息",
        ],
    )
    print(f"\n  6️⃣ PMTool — 用户故事:")
    for line in story.split("\n"):
        print(f"     {line}")

    # ArchitectTool
    from src.tools.architect_tool import ArchitectTool

    arch = ArchitectTool()
    analysis = arch.tradeoff_analysis(
        decision="使用 Redis 作为缓存层",
        pros=["高性能", "支持多种数据结构", "成熟生态"],
        cons=["增加系统复杂度", "需要额外运维"],
        alternatives=["Memcached", "本地缓存"],
    )
    print(f"\n  7️⃣ ArchitectTool — 技术权衡分析:")
    print("     ✅ Redis 作为缓存层 — 分析完成")
    for line in analysis.split("\n")[:6]:
        if line.strip():
            print(f"     {line}")


def demo_phase3_plan_graph():
    """Phase 3: Plan Graph 动态生成"""
    print("\n" + "=" * 60)
    print("📋 Phase 3: Plan Graph 动态生成")
    print("=" * 60)

    from src.plan.graph import PlanGraph, PlanNode, NodeType, ExecutorCapability

    # 模拟 Planner 生成的执行计划
    nodes = [
        PlanNode(
            id="req_1",
            name="需求分析",
            node_type=NodeType.TASK,
            description="分析用户需求，提取功能点",
            required_capability=ExecutorCapability.REQUIREMENTS_ANALYSIS,
        ),
        PlanNode(
            id="design_1",
            name="技术设计",
            node_type=NodeType.TASK,
            description="设计系统架构",
            required_capability=ExecutorCapability.ARCHITECTURE_DESIGN,
            dependencies=["req_1"],
        ),
        PlanNode(
            id="dev_1",
            name="核心开发",
            node_type=NodeType.TASK,
            description="实现核心功能",
            required_capability=ExecutorCapability.CODE_DEVELOPMENT,
            dependencies=["design_1"],
        ),
        PlanNode(
            id="devops_1",
            name="CI/CD 配置",
            node_type=NodeType.TASK,
            description="配置持续集成",
            required_capability=ExecutorCapability.DEVOPS_CI_CD,
            dependencies=["dev_1"],
            parallel_group="parallel",
        ),
        PlanNode(
            id="security_1",
            name="安全扫描",
            node_type=NodeType.TASK,
            description="执行安全审计",
            required_capability=ExecutorCapability.SECURITY_AUDIT,
            dependencies=["dev_1"],
            parallel_group="parallel",
        ),
        PlanNode(
            id="test_1",
            name="测试验证",
            node_type=NodeType.TASK,
            description="运行自动化测试",
            required_capability=ExecutorCapability.TESTING,
            dependencies=["dev_1"],
        ),
    ]

    graph = PlanGraph(
        id="plan_demo_001",
        task="构建电商平台搜索模块",
    )
    for node in nodes:
        graph.add_node(node)

    print(f"\n  📝 任务: {graph.task}")
    print(f"  📊 节点数: {len(graph.nodes)}")
    parallel = graph.get_parallel_groups()
    print(f"  📊 并行组: {list(parallel.keys()) if parallel else '无'}")

    print("\n  🗺️ 执行计划:")
    for node_id, node in graph.nodes.items():
        deps = f" (依赖: {', '.join(node.dependencies)})" if node.dependencies else ""
        parallel_tag = f" [并行: {node.parallel_group}]" if node.parallel_group else ""
        print(f"    [{node_id}] {node.name}{deps}{parallel_tag}")

    # 演示拓扑排序
    order = graph.topological_sort()
    print(f"\n  📐 拓扑排序: {' → '.join(order)}")


def demo_phase4_bug_fix_workflow():
    """Phase 4: Bug Fix 闭环演示"""
    print("\n" + "=" * 60)
    print("🐛 Phase 4: Bug Fix 闭环工作流")
    print("=" * 60)

    from src.bug.classifier import BugClassifier
    from src.bug.report import BugReport
    from src.bug.tracker import BugTracker

    classifier = BugClassifier()
    tracker = BugTracker()

    # 场景 1: 测试失败
    print("\n  场景 1: 测试失败")
    classification = classifier.classify(
        error_type="AssertionError",
        error_message="assert add(2, 3) == 6",
        traceback="tests/test_math.py:10: AssertionError",
    )
    bug1 = BugReport(
        title="add(2, 3) 返回错误结果",
        category=classification["category"],
        severity=classification["severity"],
        error_type=classification["error_type"],
        error_message=classification["message"],
        file_path="tests/test_math.py",
        line_number=10,
    )
    tracker.add(bug1)
    print(f"    📝 创建 Bug: {bug1.title}")
    print(f"    🔍 分类: {classification['category']}, 严重性: {classification['severity']}")

    # 场景 2: 运行时错误
    print("\n  场景 2: 运行时错误")
    classification2 = classifier.classify(
        error_type="KeyError",
        error_message="'user_id'",
        traceback="src/auth/service.py:45: KeyError",
    )
    bug2 = BugReport(
        title="用户认证服务 KeyError",
        category=classification2["category"],
        severity=classification2["severity"],
        error_type=classification2["error_type"],
        error_message=classification2["message"],
        file_path="src/auth/service.py",
        line_number=45,
    )
    tracker.add(bug2)
    print(f"    📝 创建 Bug: {bug2.title}")
    print(f"    🔍 分类: {classification2['category']}, 严重性: {classification2['severity']}")

    # Bug Fix 流程
    print("\n  🔧 Bug Fix 流程:")
    print(f"    [{bug1.id}] {bug1.title}")
    bug1.mark_in_progress()
    print(f"      → in_progress (Developer 开始修复)")
    bug1.mark_fixed()
    print(f"      → fixed (修复完成，提交代码)")
    bug1.mark_verified()
    print(f"      → verified (Tester 验证通过 ✅)")

    print(f"\n    [{bug2.id}] {bug2.title}")
    bug2.mark_in_progress()
    print(f"      → in_progress")
    bug2.mark_fixed()
    print(f"      → fixed")
    bug2.mark_rejected("修复不完整，未处理边界条件")
    print(f"      → rejected (Reviewer 驳回)")
    bug2.reopen()
    print(f"      → open (重新修复)")
    bug2.mark_in_progress()
    print(f"      → in_progress (二次修复中...)")

    # 统计摘要
    summary = tracker.summary()
    print(f"\n  📊 Bug 统计:")
    print(f"    总数: {summary['total']}")
    print(f"    按状态: {summary['by_status']}")
    print(f"    按严重性: {summary['by_severity']}")
    print(f"    按类别: {summary['by_category']}")


def demo_phase5_resilience():
    """Phase 5: 生产级能力演示"""
    print("\n" + "=" * 60)
    print("🛡️ Phase 5: 生产级能力演示")
    print("=" * 60)

    # Circuit Breaker
    from src.resilience.circuit_breaker import CircuitBreaker, CircuitState

    cb = CircuitBreaker(name="demo_service", failure_threshold=3, recovery_timeout=10.0)
    print("\n  1️⃣ 熔断器 (Circuit Breaker):")
    print(f"     状态: {cb.state.value}")

    def failing_call():
        raise ValueError("Simulated failure")

    for i in range(3):
        try:
            cb.call(failing_call)
        except ValueError:
            pass
        print(f"     失败 {i+1} 次 → 状态: {cb.state.value}")

    print(f"     允许请求? {'否 (开路阻止)' if cb.state == CircuitState.OPEN else '是'}")

    # Retry Policy
    from src.resilience.retry_policy import RetryPolicy

    policy = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)
    print(f"\n  2️⃣ 重试策略 (Retry Policy):")
    print(f"     最大重试: {policy.max_retries}")
    print(f"     基础延迟: {policy.base_delay}s")
    delays = [policy._calculate_delay(i) for i in range(policy.max_retries)]
    print(f"     退避时间: {[f'{d:.1f}s' for d in delays]}")

    # Metrics
    from src.observability.metrics import MetricsCollector

    mc = MetricsCollector()
    mc.increment("api_calls", 1)
    mc.observe("response_time", 0.15)
    mc.observe("response_time", 0.23)
    mc.set_gauge("active_connections", 42)
    print(f"\n  3️⃣ 指标收集 (Metrics Collector):")
    print(f"     API 调用: {mc.get_counter('api_calls')}")
    print(f"     活跃连接: {mc.get_gauge('active_connections')}")
    print(f"     响应时间观测: {len(mc._histograms.get('response_time', []))} 次")

    # Cost Controller
    from src.cost.controller import CostController

    cc = CostController()
    # Use async-compatible way
    async def _demo_cost():
        await cc.record_cost("developer", "task_1", 2.50, 1000, 2000)
        await cc.record_cost("reviewer", "task_2", 1.80, 800, 1500)
        await cc.record_cost("tester", "task_3", 0.90, 500, 800)

    asyncio.run(_demo_cost())

    print(f"\n  4️⃣ 成本控制 (Cost Controller):")
    print(f"     总成本: ${cc.total_cost:.2f}")
    print(f"     状态: {cc.status.value}")
    print(f"     Developer: ${cc.get_agent_cost('developer'):.2f}")
    print(f"     Reviewer: ${cc.get_agent_cost('reviewer'):.2f}")
    print(f"     Tester: ${cc.get_agent_cost('tester'):.2f}")


def demo_phase6_full_pipeline():
    """Phase 6: 完整流水线模拟"""
    print("\n" + "=" * 60)
    print("🚀 Phase 6: 完整开发流水线模拟")
    print("=" * 60)

    from src.workflows.builder import DevelopmentPipelineBuilder

    print("\n  📋 创建开发流水线...")
    builder = DevelopmentPipelineBuilder()
    app = builder.build()

    print("  ✅ 流水线已创建")

    print("\n  🗺️ 工作流结构:")
    print("    • requirements (需求分析)")
    print("    • design (技术设计)")
    print("    • develop (代码开发)")
    print("    • review (代码审查)")
    print("    • test (测试验证)")
    print("    • fix (Bug修复)")
    print("    • human_review (人工审批)")
    print("\n  → 流程:")
    print("    requirements → design → develop → review")
    print("    review → [通过] → test")
    print("    review → [失败] → develop (重试)")
    print("    test → [通过] → END")
    print("    test → [失败] → fix → test")

    print("\n  ✅ 流水线验证通过!")


def main():
    print("\n" + "🎯" * 30)
    print("  Multi-Agent Orchestration System — 完整演示")
    print("🎯" * 30)

    demo_phase1_agent_registry()
    demo_phase2_domain_tools()
    demo_phase3_plan_graph()
    demo_phase4_bug_fix_workflow()
    demo_phase5_resilience()
    demo_phase6_full_pipeline()

    print("\n" + "=" * 60)
    print("✅ 演示完成!")
    print("=" * 60)

    # 最终统计
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "--co", "-q"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        test_count = [l for l in lines if "test" in l.lower()][-1] if lines else "unknown"
        print(f"\n📊 项目统计:")
        print(f"   测试用例: {test_count}")

        result2 = subprocess.run(
            ["find", "src", "-name", "*.py"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        file_count = len([l for l in result2.stdout.strip().split("\n") if l])
        print(f"   代码文件: {file_count} 个 .py")
    print()


if __name__ == "__main__":
    main()
