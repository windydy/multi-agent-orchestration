"""
项目入口
"""

from src.claude import ClaudeAgentWrapper, ClaudeSDKConfig
from src.agents import (
    create_requirements_agent,
    create_designer_agent,
    create_developer_agent,
    create_reviewer_agent,
    create_tester_agent,
    create_fixer_agent,
)
from src.workflows import (
    WorkflowState,
    WorkflowStateManager,
    DevelopmentPipelineBuilder,
    WorkflowRunner,
    create_dev_pipeline,
    run_pipeline,
)

__version__ = "0.1.0"

__all__ = [
    # Claude SDK适配
    "ClaudeAgentWrapper",
    "ClaudeSDKConfig",
    
    # Agent工厂函数
    "create_requirements_agent",
    "create_designer_agent",
    "create_developer_agent",
    "create_reviewer_agent",
    "create_tester_agent",
    "create_fixer_agent",
    
    # Workflow
    "WorkflowState",
    "WorkflowStateManager",
    "DevelopmentPipelineBuilder",
    "WorkflowRunner",
    "create_dev_pipeline",
    "run_pipeline",
]