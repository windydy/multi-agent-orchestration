"""
Tester Agent

运行测试并验证功能
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks


# Tester Agent的系统提示
TESTER_SYSTEM_PROMPT = """
你是测试工程师。你的职责是：

1. 运行单元测试和集成测试
2. 执行功能验证测试
3. 分析测试结果和覆盖率
4. 报告测试结果和问题

输入：
- 开发Agent的代码变更
- Reviewer Agent的审查结果
- 项目测试配置

测试流程：
1. 运行现有测试套件（pytest、npm test等）
2. 分析测试输出和失败原因
3. 运行覆盖率检查
4. 进行功能验证（如果需要）

输出格式：
{
    "passed": true/false,
    "total_tests": 数量,
    "passed_tests": 数量,
    "failed_tests": 数量,
    "coverage_percent": 覆盖率,
    "failures": [
        {
            "test_name": "测试名称",
            "error_message": "错误信息",
            "stack_trace": "堆栈追踪摘要",
            "likely_cause": "可能原因分析"
        }
    ],
    "fixable": true/false,  // 是否可以自动修复
    "fix_suggestions": [
        {
            "test": "失败的测试",
            "suggested_fix": "修复建议"
        }
    ],
    "summary": "测试总结"
}

如果测试通过：
- 设置 passed=true
- 返回覆盖率信息

如果测试失败但可修复：
- 设置 passed=false
- 设置 fixable=true
- 提供修复建议

如果测试失败且需要人工介入：
- 设置 passed=false
- 设置 fixable=false
- 说明无法自动修复的原因
"""


class TesterAgent(ClaudeAgentWrapper):
    """Tester Agent
    
    继承ClaudeAgentWrapper，配置测试专用设置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-5",
        hooks: list = None
    ):
        config = AgentConfig(
            name="qa_tester",
            role=AgentRole.WORKER,
            description="测试工程师 - 运行测试验证功能",
            model=model,
            tools=["bash", "read_file", "search"],
            max_iterations=10,
            timeout=600,
            temperature=0.0,
            system_prompt=TESTER_SYSTEM_PROMPT
        )
        
        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            temperature=0.0,
            tools=[
                ClaudeToolType.BASH,
                ClaudeToolType.READ_FILE,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=TESTER_SYSTEM_PROMPT
        )
        
        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)
        
        super().__init__(config, claude_config, hooks)


def create_tester_agent(
    api_key: Optional[str] = None,
    model: str = "glm-5",
    custom_hooks: list = None
) -> TesterAgent:
    """创建Tester Agent
    
    Args:
        api_key: Claude API密钥
        model: 使用的模型
        custom_hooks: 自定义Hooks
    
    Returns:
        TesterAgent实例
    """
    return TesterAgent(api_key=api_key, model=model, hooks=custom_hooks)