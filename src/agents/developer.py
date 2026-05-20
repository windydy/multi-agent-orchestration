"""
开发Agent

根据技术设计实现代码
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# 开发Agent的系统提示
DEVELOPER_SYSTEM_PROMPT = """
你是开发工程师。你的职责是：

1. 根据技术设计文档实现代码
2. 编写单元测试验证功能
3. 遵循项目代码规范和风格
4. 记录代码变更和实现说明

输入：
- 技术设计结果（technical_designer的输出）
- 需求分析结果（requirements_analyst的输出）
- 项目现有代码

输出格式：
{
    "files_created": [
        {"path": "文件路径", "purpose": "用途说明"}
    ],
    "files_modified": [
        {"path": "文件路径", "changes": "变更说明"}
    ],
    "tests_added": [
        {"path": "测试文件路径", "coverage": "覆盖范围"}
    ],
    "implementation_notes": [
        "实现要点和注意事项"
    ],
    "commands_run": [
        {"command": "执行命令", "result": "结果"}
    ],
    "issues_encountered": [
        {"issue": "问题描述", "solution": "解决方案"}
    ],
    "needs_revision": false  // 如果Review要求修改，设为true并说明原因
}

使用write_file创建新文件，edit_file修改现有代码。
使用bash执行测试验证（pytest、npm test等）。
遵循现有代码风格，查看现有文件作为参考。

如果遇到设计问题无法实现，使用 [BLOCKED: 原因] 标记并说明。
"""


class DeveloperAgent(ClaudeAgentWrapper):
    """开发Agent
    
    继承ClaudeAgentWrapper，配置开发专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None
    ):
        config = AgentConfig(
            name="developer",
            role=AgentRole.WORKER,
            description="开发工程师 - 实现代码和编写测试",
            model=model,
            tools=["read_file", "write_file", "edit_file", "bash", "search"],
            max_iterations=20,
            timeout=900,
            temperature=0.1,
            system_prompt=DEVELOPER_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=8192,
            temperature=0.1,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.WRITE_FILE,
                ClaudeToolType.EDIT_FILE,
                ClaudeToolType.BASH,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=DEVELOPER_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_developer_agent(
    api_key: Optional[str] = None,
    model: str = "qwen3.6-plus",
    custom_hooks: list = None
) -> DeveloperAgent:
    """创建开发Agent
    
    Args:
        api_key: Claude API密钥
        model: 使用的模型（默认sonnet，平衡成本）
        custom_hooks: 自定义Hooks
    
    Returns:
        DeveloperAgent实例
    """
    return DeveloperAgent(api_key=api_key, model=model, hooks=custom_hooks)