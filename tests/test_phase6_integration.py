"""
Phase 6.6: 集成测试 — 多 Agent 并发调度、能力匹配、全链路集成
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestExecutorRegistryIntegration:
    """ExecutorRegistry 集成测试"""

    def test_register_all_agents_by_capability(self):
        """所有 Agent 注册后能通过能力查找"""
        from src.executors.registry import ExecutorRegistry
        from src.agents.devops import DevOpsAgent
        from src.agents.security import SecurityAgent
        from src.agents.data import DataAgent
        from src.agents.architect import ArchitectAgent
        from src.agents.product_manager import ProductManagerAgent
        from src.plan.graph import ExecutorCapability

        registry = ExecutorRegistry()
        agents = [
            DevOpsAgent(api_key="test"),
            SecurityAgent(api_key="test"),
            DataAgent(api_key="test"),
            ArchitectAgent(api_key="test"),
            ProductManagerAgent(api_key="test"),
        ]
        for agent in agents:
            registry.register(agent, capabilities=agent.get_capabilities())

        # 每个能力都能找到对应 Agent
        found = registry.find_best(ExecutorCapability.DEVOPS_CI_CD)
        assert found is not None
        assert found.name == "devops_engineer"

        found = registry.find_best(ExecutorCapability.SECURITY_AUDIT)
        assert found is not None
        assert found.name == "security_engineer"

        found = registry.find_best(ExecutorCapability.DATA_ENGINEERING)
        assert found is not None
        assert found.name == "data_engineer"

    def test_find_by_capability_returns_first_match(self):
        """find_by_capability 返回第一个匹配"""
        from src.executors.registry import ExecutorRegistry
        from src.agents.devops import DevOpsAgent
        from src.plan.graph import ExecutorCapability

        registry = ExecutorRegistry()
        agent = DevOpsAgent(api_key="test")
        registry.register(agent, capabilities=agent.get_capabilities())

        result = registry.find_by_capability(ExecutorCapability.DEVOPS_CONTAINER)
        assert result is not None
        assert result.name == "devops_engineer"

    def test_get_by_name(self):
        """按名称查找 Agent"""
        from src.executors.registry import ExecutorRegistry
        from src.agents.architect import ArchitectAgent

        registry = ExecutorRegistry()
        agent = ArchitectAgent(api_key="test")
        registry.register(agent, capabilities=agent.get_capabilities())

        found = registry.get_by_name("architect")
        assert found is not None
        assert found.name == "architect"

        not_found = registry.get_by_name("nonexistent")
        assert not_found is None

    def test_unregister_agent(self):
        """注销 Agent 后无法找到"""
        from src.executors.registry import ExecutorRegistry
        from src.agents.product_manager import ProductManagerAgent
        from src.plan.graph import ExecutorCapability

        registry = ExecutorRegistry()
        agent = ProductManagerAgent(api_key="test")
        registry.register(agent, capabilities=agent.get_capabilities())

        assert registry.find_best(ExecutorCapability.PRODUCT_MANAGEMENT) is not None

        registry.unregister(agent.executor_id)

        result = registry.find_best(ExecutorCapability.PRODUCT_MANAGEMENT)
        assert result is None

    def test_list_by_capability(self):
        """按能力列出所有匹配的 Agent"""
        from src.executors.registry import ExecutorRegistry
        from src.agents.devops import DevOpsAgent
        from src.plan.graph import ExecutorCapability

        registry = ExecutorRegistry()
        agent = DevOpsAgent(api_key="test")
        registry.register(agent, capabilities=agent.get_capabilities())

        ci_cd_agents = registry.list_by_capability(ExecutorCapability.DEVOPS_CI_CD)
        assert len(ci_cd_agents) == 1
        assert ci_cd_agents[0].name == "devops_engineer"

    def test_match_score(self):
        """Agent match_score 正确计算"""
        from src.agents.devops import DevOpsAgent
        from src.plan.graph import ExecutorCapability

        agent = DevOpsAgent(api_key="test")
        assert agent.match_score(ExecutorCapability.DEVOPS_CI_CD) == 1.0
        assert agent.match_score(ExecutorCapability.SECURITY_AUDIT) == 0.0


class TestAgentDomainTools:
    """Agent 领域工具集成测试"""

    def test_devops_agent_has_tools(self):
        """DevOpsAgent 有 CI/CD 和 Docker 工具"""
        from src.agents.devops import DevOpsAgent
        from src.tools.cicd import CICDTool
        from src.tools.docker_tool import DockerTool

        agent = DevOpsAgent(api_key="test")
        tools = agent._get_domain_tools()
        assert len(tools) == 2
        assert isinstance(tools[0], CICDTool)
        assert isinstance(tools[1], DockerTool)

    def test_security_agent_has_tools(self):
        """SecurityAgent 有安全扫描和依赖审计工具"""
        from src.agents.security import SecurityAgent
        from src.tools.security_scan import SecurityScanTool
        from src.tools.dependency_audit import DependencyAuditTool

        agent = SecurityAgent(api_key="test")
        tools = agent._get_domain_tools()
        assert len(tools) == 2
        assert isinstance(tools[0], SecurityScanTool)
        assert isinstance(tools[1], DependencyAuditTool)

    def test_data_agent_has_tools(self):
        """DataAgent 有数据分析和 SQL 工具"""
        from src.agents.data import DataAgent
        from src.tools.data_analysis import DataAnalysisTool
        from src.tools.sql_tool import SQLTool

        agent = DataAgent(api_key="test")
        tools = agent._get_domain_tools()
        assert len(tools) == 2
        assert isinstance(tools[0], DataAnalysisTool)
        assert isinstance(tools[1], SQLTool)

    def test_architect_agent_has_tools(self):
        """ArchitectAgent 有架构分析工具"""
        from src.agents.architect import ArchitectAgent
        from src.tools.architect_tool import ArchitectTool

        agent = ArchitectAgent(api_key="test")
        tools = agent._get_domain_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], ArchitectTool)

    def test_pm_agent_has_tools(self):
        """ProductManagerAgent 有需求分析工具"""
        from src.agents.product_manager import ProductManagerAgent
        from src.tools.pm_tool import PMTool

        agent = ProductManagerAgent(api_key="test")
        tools = agent._get_domain_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], PMTool)


class TestFullPipelineIntegration:
    """P/E/V 全链路集成测试"""

    def test_all_agents_importable(self):
        """所有 Agent 可以从 src.agents 导入"""
        from src.agents import (
            DevOpsAgent,
            SecurityAgent,
            DataAgent,
            ArchitectAgent,
            ProductManagerAgent,
        )

    def test_all_agents_instantiable(self):
        """所有 Agent 可以实例化"""
        from src.agents import (
            DevOpsAgent,
            SecurityAgent,
            DataAgent,
            ArchitectAgent,
            ProductManagerAgent,
        )

        agents = [
            DevOpsAgent(api_key="test"),
            SecurityAgent(api_key="test"),
            DataAgent(api_key="test"),
            ArchitectAgent(api_key="test"),
            ProductManagerAgent(api_key="test"),
        ]
        for agent in agents:
            assert agent.get_config() is not None
            assert agent.get_capabilities() is not None
            assert len(agent.get_capabilities()) > 0

    def test_all_capabilities_registered(self):
        """所有 ExecutorCapability 都有对应 Agent"""
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
        agents = [
            DevOpsAgent(api_key="test"),
            SecurityAgent(api_key="test"),
            DataAgent(api_key="test"),
            ArchitectAgent(api_key="test"),
            ProductManagerAgent(api_key="test"),
        ]
        for agent in agents:
            registry.register(agent, capabilities=agent.get_capabilities())

        # Phase 6 能力都应该有匹配
        phase6_caps = [
            ExecutorCapability.DEVOPS_CI_CD,
            ExecutorCapability.DEVOPS_CONTAINER,
            ExecutorCapability.DEVOPS_INFRA,
            ExecutorCapability.SECURITY_AUDIT,
            ExecutorCapability.DATA_ENGINEERING,
            ExecutorCapability.ARCHITECTURE_DESIGN,
            ExecutorCapability.PRODUCT_MANAGEMENT,
        ]
        for cap in phase6_caps:
            found = registry.find_best(cap)
            assert found is not None, f"No agent found for capability {cap.value}"

    def test_cicd_tool_full_workflow(self):
        """CICDTool 完整工作流: 生成 → 验证 → 解析"""
        from src.tools.cicd import CICDTool

        tool = CICDTool()

        # 1. 生成 pipeline
        pipeline = tool.generate_pipeline(
            platform="github_actions",
            language="python",
            stages=["lint", "test", "build"],
        )

        # 2. 验证生成的配置
        validation = tool.validate_config(pipeline, "github_actions")
        assert validation["valid"] is True

        # 3. 解析生成的配置
        parsed = tool.parse_workflow(pipeline)
        assert parsed["name"] == "CI"
        assert len(parsed["jobs"]) == 3

    def test_security_scan_full_workflow(self):
        """SecurityScanTool 完整工作流: 扫描 → 报告"""
        from src.tools.security_scan import SecurityScanTool

        tool = SecurityScanTool()

        # 1. 扫描代码
        code = """
API_KEY = "sk-1234567890abcdef"
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
        secrets = tool.scan_for_secrets(code)
        owasp = tool.scan_owasp(code)

        # 2. 合并发现
        all_findings = []
        for f in secrets["findings"]:
            all_findings.append({**f, "file": "app.py"})
        for f in owasp["findings"]:
            all_findings.append({**f, "file": "app.py"})

        # 3. 生成报告
        report = tool.generate_report(all_findings)
        assert len(report) > 0
        assert "Security Audit Report" in report

    def test_data_analysis_full_workflow(self):
        """DataAnalysisTool 完整工作流: 描述 → 问题检测"""
        from src.tools.data_analysis import DataAnalysisTool

        tool = DataAnalysisTool()

        csv_data = """id,name,age,salary,department
1,Alice,30,50000,Engineering
2,Bob,25,45000,Marketing
3,Charlie,35,60000,Engineering
4,Diana,28,,Marketing
5,Eve,28,52000,Engineering
1,Alice,30,50000,Engineering
"""
        desc = tool.describe_csv(csv_data)
        assert desc["row_count"] == 6
        assert desc["column_count"] == 5

        issues = tool.detect_issues(csv_data)
        assert issues["missing_values"] >= 1
        assert issues["duplicate_rows"] >= 1

    def test_sql_tool_full_workflow(self):
        """SQLTool 完整工作流: 创建表 → 生成查询 → 验证"""
        from src.tools.sql_tool import SQLTool

        tool = SQLTool()

        # 1. 创建表
        ddl = tool.create_table(
            table="users",
            columns=[
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("name", "VARCHAR(255) NOT NULL"),
                ("email", "VARCHAR(255) UNIQUE"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        assert "CREATE TABLE" in ddl

        # 2. 生成查询
        query = tool.generate_select(
            table="users",
            columns=["name", "email"],
            where={"name": "Alice"},
            order_by="created_at DESC",
            limit=10,
        )
        assert "SELECT" in query

        # 3. 验证查询
        validation = tool.validate_query(query)
        assert validation["valid"] is True
