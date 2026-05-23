"""
Agents实现模块

提供各角色Agent的具体实现
"""

from .requirements import RequirementsAgent, create_requirements_agent
from .designer import DesignerAgent, create_designer_agent
from .developer import DeveloperAgent, create_developer_agent
from .reviewer import ReviewerAgent, create_reviewer_agent
from .tester import TesterAgent, create_tester_agent
from .fixer import FixerAgent, create_fixer_agent

# Phase 6: 领域专业 Agent
from .devops import DevOpsAgent
from .security import SecurityAgent
from .data import DataAgent
from .architect import ArchitectAgent
from .product_manager import ProductManagerAgent

# Phase 8: 总结 Agent
from .summarizer import SummarizerAgent, create_summarizer

__all__ = [
    "RequirementsAgent",
    "DesignerAgent",
    "DeveloperAgent",
    "ReviewerAgent",
    "TesterAgent",
    "FixerAgent",
    "create_requirements_agent",
    "create_designer_agent",
    "create_developer_agent",
    "create_reviewer_agent",
    "create_tester_agent",
    "create_fixer_agent",
    # Phase 6
    "DevOpsAgent",
    "SecurityAgent",
    "DataAgent",
    "ArchitectAgent",
    "ProductManagerAgent",
    # Phase 8
    "SummarizerAgent",
    "create_summarizer",
]