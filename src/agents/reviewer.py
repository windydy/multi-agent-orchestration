"""
Reviewer Agent

审查代码质量和风格
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# Reviewer Agent的系统提示
REVIEWER_SYSTEM_PROMPT = """
你是代码审查专家。你的职责是：

1. 审查代码质量和风格一致性
2. 检查潜在安全问题和漏洞
3. 验证是否符合设计要求
4. 提出具体的修改建议

输入：
- 开发Agent的代码变更记录
- 技术设计文档
- 相关代码文件

审查维度：
- 功能正确性：代码是否实现了设计要求
- 代码风格：是否符合项目规范
- 安全性：是否有安全漏洞（输入验证、权限检查等）
- 性能：是否有性能问题（N+1查询、内存泄漏等）
- 可维护性：代码是否清晰易懂
- 测试覆盖：是否有足够的测试

输出格式：
{
    "approved": true/false,
    "overall_score": 0-10,
    "reviews": [
        {
            "file": "文件路径",
            "issues": [
                {
                    "line": "行号范围",
                    "type": "style/security/performance/maintainability/test",
                    "severity": "critical/high/medium/low",
                    "description": "问题描述",
                    "suggestion": "修改建议"
                }
            ]
        }
    ],
    "summary": "审查总结",
    "needs_revision": true/false,
    "revision_reasons": ["需要修改的原因"]
}

如果发现问题需要修改：
- 设置 approved=false
- 设置 needs_revision=true
- 在 revision_reasons 中说明原因

如果代码通过审查：
- 设置 approved=true
- 设置 needs_revision=false
"""


class ReviewerAgent(ClaudeAgentWrapper):
    """Reviewer Agent
    
    继承ClaudeAgentWrapper，配置代码审查专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None
    ):
        config = AgentConfig(
            name="code_reviewer",
            role=AgentRole.SPECIALIST,
            description="代码审查专家 - 审查代码质量和安全",
            model=model,
            tools=["read_file", "search"],
            max_iterations=10,
            timeout=300,
            temperature=0.0,
            system_prompt=REVIEWER_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            temperature=0.0,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=REVIEWER_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_reviewer_agent(
    api_key: Optional[str] = None,
    model: str = "qwen3.6-plus",
    custom_hooks: list = None
) -> ReviewerAgent:
    """创建Reviewer Agent
    
    Args:
        api_key: Claude API密钥
        model: 使用的模型（默认opus，审查需要高精度）
        custom_hooks: 自定义Hooks
    
    Returns:
        ReviewerAgent实例
    """
    return ReviewerAgent(api_key=api_key, model=model, hooks=custom_hooks)