"""
Phase 6 TDD: 领域专业 Agent (DevOps/Security/Data/Architect/ProductManager)
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestDevOpsAgent:
    """DevOpsAgent 测试"""

    def test_devops_config(self):
        from src.agents.devops import DevOpsAgent, DEVOPS_SYSTEM_PROMPT
        from src.core.agent import AgentConfig

        agent = DevOpsAgent(api_key="test-key")
        config = agent.get_config()

        assert config.name == "devops_engineer"
        assert config.model == "qwen3.6-plus"
        assert "CI/CD" in config.description
        assert "DevOps" in DEVOPS_SYSTEM_PROMPT

    def test_devops_capabilities(self):
        from src.agents.devops import DevOpsAgent
        from src.plan.graph import ExecutorCapability

        agent = DevOpsAgent(api_key="test-key")
        caps = agent.get_capabilities()

        assert ExecutorCapability.DEVOPS_CI_CD in caps
        assert ExecutorCapability.DEVOPS_CONTAINER in caps
        assert ExecutorCapability.DEVOPS_INFRA in caps

    def test_devops_tools_available(self):
        """DevOpsAgent 应有 CI/CD 和 Docker 工具可用"""
        from src.agents.devops import DevOpsAgent
        from src.tools.cicd import CICDTool
        from src.tools.docker_tool import DockerTool

        agent = DevOpsAgent(api_key="test-key")
        tools = agent._get_domain_tools()

        assert any(isinstance(t, CICDTool) for t in tools)
        assert any(isinstance(t, DockerTool) for t in tools)

    def test_cicd_tool_parse_yaml(self):
        """CICDTool 能解析 GitHub Actions workflow"""
        import yaml
        from src.tools.cicd import CICDTool

        tool = CICDTool()
        workflow = """
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
"""
        parsed = tool.parse_workflow(workflow)
        assert parsed["name"] == "CI"
        assert "test" in parsed["jobs"]

    def test_cicd_tool_validate_github_actions(self):
        """CICDTool 能验证 GitHub Actions 配置"""
        from src.tools.cicd import CICDTool

        tool = CICDTool()
        valid = """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo build
"""
        result = tool.validate_config(valid, "github_actions")
        assert result["valid"] is True

    def test_cicd_tool_generate_pipeline(self):
        """CICDTool 能生成 CI/CD pipeline 配置"""
        from src.tools.cicd import CICDTool

        tool = CICDTool()
        config = tool.generate_pipeline(
            platform="github_actions",
            language="python",
            stages=["lint", "test", "build"],
        )
        assert "name:" in config
        assert "jobs:" in config

    def test_docker_tool_build_command(self):
        """DockerTool 能生成 docker build 命令"""
        from src.tools.docker_tool import DockerTool

        tool = DockerTool()
        cmd = tool.build_command(
            context=".",
            tag="myapp:latest",
            dockerfile="Dockerfile",
        )
        assert "docker build" in cmd
        assert "-t myapp:latest" in cmd

    def test_docker_tool_validate_dockerfile(self):
        """DockerTool 能验证 Dockerfile"""
        from src.tools.docker_tool import DockerTool

        tool = DockerTool()
        dockerfile = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""
        result = tool.validate_dockerfile(dockerfile)
        assert result["valid"] is True
        assert result["base_image"] == "python:3.11-slim"

    def test_docker_tool_compose_up(self):
        """DockerTool 能生成 docker-compose up 命令"""
        from src.tools.docker_tool import DockerTool

        tool = DockerTool()
        cmd = tool.compose_up(
            file="docker-compose.yml",
            detach=True,
            build=True,
        )
        assert "docker compose" in cmd or "docker-compose" in cmd
        assert "-d" in cmd


class TestSecurityAgent:
    """SecurityAgent 测试"""

    def test_security_config(self):
        from src.agents.security import SecurityAgent, SECURITY_SYSTEM_PROMPT
        from src.core.agent import AgentConfig

        agent = SecurityAgent(api_key="test-key")
        config = agent.get_config()

        assert config.name == "security_engineer"
        assert config.model == "qwen3.6-plus"
        assert "安全" in config.description
        assert "OWASP" in SECURITY_SYSTEM_PROMPT

    def test_security_capabilities(self):
        from src.agents.security import SecurityAgent
        from src.plan.graph import ExecutorCapability

        agent = SecurityAgent(api_key="test-key")
        caps = agent.get_capabilities()

        assert ExecutorCapability.SECURITY_AUDIT in caps

    def test_security_tools_available(self):
        """SecurityAgent 应有安全扫描和依赖审计工具"""
        from src.agents.security import SecurityAgent
        from src.tools.security_scan import SecurityScanTool
        from src.tools.dependency_audit import DependencyAuditTool

        agent = SecurityAgent(api_key="test-key")
        tools = agent._get_domain_tools()

        assert any(isinstance(t, SecurityScanTool) for t in tools)
        assert any(isinstance(t, DependencyAuditTool) for t in tools)

    def test_security_scan_detect_hardcoded_secrets(self):
        """SecurityScanTool 能检测硬编码凭证"""
        from src.tools.security_scan import SecurityScanTool

        tool = SecurityScanTool()
        code = """
API_KEY = "sk-1234567890abcdef"
password = "super_secret_123"
db_url = "postgres://admin:password123@db.example.com/mydb"
"""
        result = tool.scan_for_secrets(code)
        assert len(result["findings"]) > 0
        assert result["severity"] in ("HIGH", "CRITICAL")

    def test_security_scan_owasp_patterns(self):
        """SecurityScanTool 能识别 OWASP 常见漏洞模式"""
        from src.tools.security_scan import SecurityScanTool

        tool = SecurityScanTool()
        code = """
@app.route('/search')
def search():
    query = request.args.get('q')
    return f"<h1>Results for {query}</h1>"

cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
        result = tool.scan_owasp(code)
        assert len(result["findings"]) > 0
        vuln_types = [f["type"] for f in result["findings"]]
        assert any("xss" in vt.lower() or "injection" in vt.lower() for vt in vuln_types)

    def test_security_scan_generate_report(self):
        """SecurityScanTool 能生成安全报告"""
        from src.tools.security_scan import SecurityScanTool

        tool = SecurityScanTool()
        findings = [
            {"type": "hardcoded_secret", "file": "config.py", "line": 5, "severity": "HIGH"},
            {"type": "sql_injection", "file": "db.py", "line": 12, "severity": "CRITICAL"},
        ]
        report = tool.generate_report(findings)
        assert "CRITICAL" in report
        assert "HIGH" in report
        assert "config.py" in report

    def test_dependency_audit_analyze(self):
        """DependencyAuditTool 能分析依赖风险"""
        from src.tools.dependency_audit import DependencyAuditTool

        tool = DependencyAuditTool()
        requirements = """
flask==2.0.1
requests==2.25.1
django==3.2.0
urllib3==1.26.4
"""
        result = tool.analyze_requirements(requirements)
        assert "packages" in result
        assert len(result["packages"]) == 4
        assert result["has_known_vulnerabilities"] is True or result["has_outdated"] is True

    def test_dependency_audit_generate_requirements(self):
        """DependencyAuditTool 能生成安全的 requirements"""
        from src.tools.dependency_audit import DependencyAuditTool

        tool = DependencyAuditTool()
        content = tool.generate_secure_requirements(
            base_packages=["flask", "requests", "sqlalchemy"],
        )
        assert "flask" in content.lower()
        assert "requests" in content.lower()


class TestDataAgent:
    """DataAgent 测试"""

    def test_data_config(self):
        from src.agents.data import DataAgent, DATA_SYSTEM_PROMPT

        agent = DataAgent(api_key="test-key")
        config = agent.get_config()

        assert config.name == "data_engineer"
        assert config.model == "qwen3.6-plus"
        assert "数据" in config.description
        assert "pandas" in DATA_SYSTEM_PROMPT

    def test_data_capabilities(self):
        from src.agents.data import DataAgent
        from src.plan.graph import ExecutorCapability

        agent = DataAgent(api_key="test-key")
        caps = agent.get_capabilities()

        assert ExecutorCapability.DATA_ENGINEERING in caps

    def test_data_tools_available(self):
        """DataAgent 应有数据分析和 SQL 工具"""
        from src.agents.data import DataAgent
        from src.tools.data_analysis import DataAnalysisTool
        from src.tools.sql_tool import SQLTool

        agent = DataAgent(api_key="test-key")
        tools = agent._get_domain_tools()

        assert any(isinstance(t, DataAnalysisTool) for t in tools)
        assert any(isinstance(t, SQLTool) for t in tools)

    def test_data_analysis_describe(self):
        """DataAnalysisTool 能生成数据描述统计"""
        import json
        from src.tools.data_analysis import DataAnalysisTool

        tool = DataAnalysisTool()
        csv_data = """name,age,salary
Alice,30,50000
Bob,25,45000
Charlie,35,60000
Diana,28,52000
"""
        result = tool.describe_csv(csv_data)
        assert result["row_count"] == 4
        assert "age" in result["columns"]
        assert "salary" in result["columns"]
        assert result["columns"]["age"]["mean"] == 29.5

    def test_data_analysis_detect_issues(self):
        """DataAnalysisTool 能检测数据问题"""
        from src.tools.data_analysis import DataAnalysisTool

        tool = DataAnalysisTool()
        csv_data = """id,value,category
1,100,A
2,200,B
3,,A
4,150,
1,100,A
"""
        result = tool.detect_issues(csv_data)
        assert result["missing_values"] > 0
        assert result["duplicate_rows"] >= 1

    def test_sql_tool_generate_query(self):
        """SQLTool 能生成 SQL 查询"""
        from src.tools.sql_tool import SQLTool

        tool = SQLTool()
        query = tool.generate_select(
            table="users",
            columns=["name", "email"],
            where={"status": "active"},
            order_by="name",
            limit=10,
        )
        assert "SELECT" in query
        assert "name" in query
        assert "FROM users" in query
        assert "WHERE" in query
        assert "ORDER BY" in query
        assert "LIMIT" in query

    def test_sql_tool_create_table(self):
        """SQLTool 能生成 CREATE TABLE 语句"""
        from src.tools.sql_tool import SQLTool

        tool = SQLTool()
        ddl = tool.create_table(
            table="products",
            columns=[
                ("id", "INTEGER PRIMARY KEY"),
                ("name", "VARCHAR(255) NOT NULL"),
                ("price", "DECIMAL(10,2)"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        assert "CREATE TABLE" in ddl
        assert "products" in ddl
        assert "INTEGER PRIMARY KEY" in ddl
        assert "VARCHAR" in ddl

    def test_sql_tool_validate_query(self):
        """SQLTool 能验证基本 SQL 语法"""
        from src.tools.sql_tool import SQLTool

        tool = SQLTool()
        valid = tool.validate_query("SELECT name, email FROM users WHERE id = 1")
        assert valid["valid"] is True

        invalid = tool.validate_query("SELCT * FRM users")
        assert invalid["valid"] is False


class TestArchitectAgent:
    """ArchitectAgent 测试"""

    def test_architect_config(self):
        from src.agents.architect import ArchitectAgent, ARCHITECT_SYSTEM_PROMPT

        agent = ArchitectAgent(api_key="test-key")
        config = agent.get_config()

        assert config.name == "architect"
        assert config.model == "qwen3.6-plus"
        assert "架构" in config.description
        assert "技术选型" in ARCHITECT_SYSTEM_PROMPT

    def test_architect_capabilities(self):
        from src.agents.architect import ArchitectAgent
        from src.plan.graph import ExecutorCapability

        agent = ArchitectAgent(api_key="test-key")
        caps = agent.get_capabilities()

        assert ExecutorCapability.ARCHITECTURE_DESIGN in caps

    def test_architect_tools_available(self):
        """ArchitectAgent 应有架构分析工具"""
        from src.agents.architect import ArchitectAgent
        from src.tools.architect_tool import ArchitectTool

        agent = ArchitectAgent(api_key="test-key")
        tools = agent._get_domain_tools()

        assert any(isinstance(t, ArchitectTool) for t in tools)

    def test_architect_tool_tradeoff_analysis(self):
        """ArchitectTool 能生成技术权衡分析"""
        from src.tools.architect_tool import ArchitectTool

        tool = ArchitectTool()
        analysis = tool.tradeoff_analysis(
            decision="使用 Redis 作为缓存层",
            pros=["高性能", "支持多种数据结构", "成熟生态"],
            cons=["增加系统复杂度", "需要额外运维", "缓存一致性问题"],
            alternatives=["Memcached", "本地缓存"],
        )
        assert "高性能" in analysis
        assert "系统复杂度" in analysis

    def test_architect_tool_evaluate_tech(self):
        """ArchitectTool 能评估技术选型"""
        from src.tools.architect_tool import ArchitectTool

        tool = ArchitectTool()
        result = tool.evaluate_tech_stack(
            requirement="高并发 Web API",
            candidates=["FastAPI", "Flask", "Django"],
            criteria=["性能", "开发效率", "生态"],
        )
        assert "evaluation" in result
        assert "recommendation" in result
        assert len(result["evaluation"]) == 3

    def test_architect_tool_capacity_estimate(self):
        """ArchitectTool 能估算容量规划"""
        from src.tools.architect_tool import ArchitectTool

        tool = ArchitectTool()
        est = tool.capacity_estimate(
            qps=1000,
            avg_response_size_kb=50,
            data_growth_gb_per_month=10,
        )
        assert est["bandwidth_mbps"] > 0
        assert est["monthly_storage_gb"] > 0


class TestProductManagerAgent:
    """ProductManagerAgent 测试"""

    def test_pm_config(self):
        from src.agents.product_manager import ProductManagerAgent, PM_SYSTEM_PROMPT

        agent = ProductManagerAgent(api_key="test-key")
        config = agent.get_config()

        assert config.name == "product_manager"
        assert config.model == "qwen3.6-turbo"  # PM 用轻量模型
        assert "产品" in config.description
        assert "用户故事" in PM_SYSTEM_PROMPT

    def test_pm_capabilities(self):
        from src.agents.product_manager import ProductManagerAgent
        from src.plan.graph import ExecutorCapability

        agent = ProductManagerAgent(api_key="test-key")
        caps = agent.get_capabilities()

        assert ExecutorCapability.PRODUCT_MANAGEMENT in caps

    def test_pm_tools_available(self):
        """ProductManagerAgent 应有需求分析工具"""
        from src.agents.product_manager import ProductManagerAgent
        from src.tools.pm_tool import PMTool

        agent = ProductManagerAgent(api_key="test-key")
        tools = agent._get_domain_tools()

        assert any(isinstance(t, PMTool) for t in tools)

    def test_pm_tool_generate_user_story(self):
        """PMTool 能生成用户故事"""
        from src.tools.pm_tool import PMTool

        tool = PMTool()
        story = tool.generate_user_story(
            role="用户",
            goal="注册账号",
            value="能够使用平台的全部功能",
            acceptance_criteria=[
                "Given 用户在注册页面 When 填写信息并点击注册 Then 账号创建成功",
                "Given 邮箱已注册 When 尝试注册 Then 提示邮箱已存在",
            ],
        )
        assert "作为[用户]" in story or "作为用户" in story or "用户故事" in story
        assert "注册账号" in story

    def test_pm_tool_prioritize(self):
        """PMTool 能使用 RICE 模型排优先级"""
        from src.tools.pm_tool import PMTool

        tool = PMTool()
        items = [
            {"name": "用户登录", "reach": 1000, "impact": 3, "confidence": 80, "effort": 2},
            {"name": "暗黑模式", "reach": 200, "impact": 1, "confidence": 50, "effort": 1},
        ]
        result = tool.rice_prioritize(items)
        assert len(result) == 2
        assert result[0]["rice_score"] > result[1]["rice_score"] or (
            result[0]["name"] == "用户登录"
        )

    def test_pm_tool_parse_requirements(self):
        """PMTool 能解析需求文档"""
        from src.tools.pm_tool import PMTool

        tool = PMTool()
        text = """
        需求：电商平台搜索功能
        1. 用户应该能按关键词搜索商品
        2. 搜索结果应该按相关性排序
        3. 应该支持筛选和排序
        4. 搜索响应时间应该小于200ms
        """
        result = tool.parse_requirements(text)
        assert len(result["functional"]) >= 2
        assert len(result["non_functional"]) >= 1


class TestAllAgentsRegistered:
    """测试所有新 Agent 可以注册到 Registry"""

    def test_register_all(self):
        from src.executors.registry import ExecutorRegistry
        from src.agents.devops import DevOpsAgent
        from src.agents.security import SecurityAgent
        from src.agents.data import DataAgent
        from src.agents.architect import ArchitectAgent
        from src.agents.product_manager import ProductManagerAgent

        registry = ExecutorRegistry()
        agents = [
            DevOpsAgent(api_key="test"),
            SecurityAgent(api_key="test"),
            DataAgent(api_key="test"),
            ArchitectAgent(api_key="test"),
            ProductManagerAgent(api_key="test"),
        ]
        for agent in agents:
            registry.register(agent)

        # 验证所有 Agent 都被注册
        for agent in agents:
            assert registry.get_by_name(agent.get_config().name) is not None

        # 验证能力匹配
        from src.plan.graph import ExecutorCapability
        assert registry.find_by_capability(ExecutorCapability.DEVOPS_CI_CD) is not None
        assert registry.find_by_capability(ExecutorCapability.SECURITY_AUDIT) is not None
        assert registry.find_by_capability(ExecutorCapability.DATA_ENGINEERING) is not None
        assert registry.find_by_capability(ExecutorCapability.ARCHITECTURE_DESIGN) is not None
        assert registry.find_by_capability(ExecutorCapability.PRODUCT_MANAGEMENT) is not None
