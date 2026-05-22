"""
技术设计Agent

根据需求设计技术方案
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# 技术设计Agent的系统提示
DESIGNER_SYSTEM_PROMPT = """
你是技术架构师。你的职责是：

1. 根据需求文档设计技术方案
2. 选择合适的技术栈和架构模式
3. 设计模块划分和接口定义
4. 输出详细的 Markdown 格式技术设计文档

输入：
- 需求分析结果（requirements_analyst的输出）
- 项目现有代码结构

输出要求：
- 使用 Markdown 格式，包含标题、代码块、表格、列表等
- 包含以下章节：架构概述、架构图(ASCII)、模块设计、技术栈选型、数据模型、实现计划、风险与注意事项
- 模块设计用表格或列表展示职责和接口
- 数据模型用表格展示字段和类型
- 语言简洁专业，适合团队阅读
- 不要输出 JSON，只输出 Markdown 文档

使用read_file查看现有代码。
基于需求分析结果设计，确保设计满足所有需求。
"""


class DesignerAgent(ClaudeAgentWrapper):
    """技术设计Agent
    
    继承ClaudeAgentWrapper，配置技术设计专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None
    ):
        config = AgentConfig(
            name="technical_designer",
            role=AgentRole.SPECIALIST,
            description="技术架构师 - 设计技术方案和架构",
            model=model,
            tools=["read_file", "write_file", "search", "bash"],
            max_iterations=15,
            timeout=600,
            temperature=0.2,
            system_prompt=DESIGNER_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=8192,
            temperature=0.2,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.WRITE_FILE,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=DESIGNER_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_designer_agent(
    api_key: Optional[str] = None,
    model: str = "qwen3.6-plus",
    custom_hooks: list = None
) -> DesignerAgent:
    """创建技术设计Agent
    
    Args:
        api_key: Claude API密钥
        model: 使用的模型
        custom_hooks: 自定义Hooks
    
    Returns:
        DesignerAgent实例
    """
    return DesignerAgent(api_key=api_key, model=model, hooks=custom_hooks)