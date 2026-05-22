"""
需求分析Agent

分析用户需求，提取关键功能点
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# 需求分析Agent的系统提示
REQUIREMENTS_SYSTEM_PROMPT = """
你是需求分析专家。你的职责是：

1. 分析用户需求，提取关键功能点
2. 识别技术约束和依赖关系
3. 澄清模糊需求，提出澄清问题
4. 输出结构化的 Markdown 格式需求文档

输出要求：
- 使用 Markdown 格式，包含标题、列表、表格等
- 包含以下章节：功能需求、非功能需求、技术约束、依赖项、待澄清问题、假设
- 功能需求用表格展示（ID、描述、优先级）
- 语言简洁专业，适合团队阅读
- 不要输出 JSON，只输出 Markdown 文档

使用search工具查找相关代码，使用read_file理解现有结构。
在分析过程中保持客观，不要做出未验证的技术选择。
"""


class RequirementsAgent(ClaudeAgentWrapper):
    """需求分析Agent
    
    继承ClaudeAgentWrapper，配置需求分析专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None
    ):
        config = AgentConfig(
            name="requirements_analyst",
            role=AgentRole.SPECIALIST,
            description="需求分析专家 - 分析用户需求，提取关键功能点",
            model=model,
            tools=["read_file", "search", "bash"],
            max_iterations=15,
            timeout=600,
            temperature=0.3,
            system_prompt=REQUIREMENTS_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=8192,
            temperature=0.3,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.SEARCH,
                ClaudeToolType.BASH,
            ],
            system_prompt=REQUIREMENTS_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_requirements_agent(
    api_key: Optional[str] = None,
    model: str = "qwen3.6-plus",
    custom_hooks: list = None
) -> RequirementsAgent:
    """创建需求分析Agent
    
    Args:
        api_key: Claude API密钥（可选，默认从环境变量获取）
        model: 使用的模型
        custom_hooks: 自定义Hooks
    
    Returns:
        RequirementsAgent实例
    """
    return RequirementsAgent(api_key=api_key, model=model, hooks=custom_hooks)