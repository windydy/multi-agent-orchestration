"""
Fixer Agent

根据测试失败信息修复代码
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# Fixer Agent的系统提示
FIXER_SYSTEM_PROMPT = """
你是修复工程师。你的职责是：

1. 分析测试失败信息
2. 定位问题代码
3. 修复bug或调整代码
4. 重新验证修复效果

输入：
- Tester Agent的失败报告
- Developer Agent的代码变更
- 相关代码文件

修复流程：
1. 阅读测试失败信息和堆栈追踪
2. 定位到相关代码文件和行号
3. 分析失败原因（逻辑错误、边界条件、类型问题等）
4. 修改代码修复问题
5. 重新运行测试验证

输出格式：
{
    "fixes_applied": [
        {
            "file": "文件路径",
            "line": "行号",
            "issue": "问题描述",
            "fix": "修复内容",
            "rationale": "修复原因"
        }
    ],
    "tests_re_run": true/false,
    "test_result": {
        "passed": true/false,
        "summary": "重新运行结果"
    },
    "remaining_issues": [
        "仍未解决的问题（如果有的话）"
    ],
    "summary": "修复总结"
}

注意：
- 每次只修复一个明确的问题
- 修复后立即验证
- 如果修复后测试仍失败，分析是否是修复方向错误
- 如果无法确定修复方案，返回 [NEEDS_HELP: 原因] 标记
"""


class FixerAgent(ClaudeAgentWrapper):
    """Fixer Agent
    
    继承ClaudeAgentWrapper，配置bug修复专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen3.6-plus",
        hooks: list = None
    ):
        config = AgentConfig(
            name="bug_fixer",
            role=AgentRole.WORKER,
            description="修复工程师 - 分析和修复代码问题",
            model=model,
            tools=["read_file", "edit_file", "bash", "search"],
            max_iterations=15,
            timeout=600,
            temperature=0.1,
            system_prompt=FIXER_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            temperature=0.1,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.EDIT_FILE,
                ClaudeToolType.BASH,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=FIXER_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_fixer_agent(
    api_key: Optional[str] = None,
    model: str = "qwen3.6-plus",
    custom_hooks: list = None
) -> FixerAgent:
    """创建Fixer Agent
    
    Args:
        api_key: Claude API密钥
        model: 使用的模型
        custom_hooks: 自定义Hooks
    
    Returns:
        FixerAgent实例
    """
    return FixerAgent(api_key=api_key, model=model, hooks=custom_hooks)