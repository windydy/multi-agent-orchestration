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
