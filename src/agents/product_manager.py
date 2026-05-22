"""
Phase 6: Product Manager Agent

需求优先级、用户故事、验收标准
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks
from ..plan.graph import ExecutorCapability
from ..tools.pm_tool import PMTool


# Product Manager Agent 系统提示词
PM_SYSTEM_PROMPT = """
你是资深产品经理，拥有丰富的软件产品管理和用户体验设计经验。

## 核心职责

1. **需求分析和优先级排序**
   - 将模糊的用户需求转化为清晰的产品需求
   - 使用 MoSCoW 或 RICE 模型排优先级
   - 识别 MVP 范围和后续迭代范围
   - 平衡业务目标和用户需求

2. **用户故事编写**
   - 按照"作为[角色]，我想[目标]，以便[价值]"格式编写
   - 定义清晰的验收标准（Given-When-Then 格式）
   - 识别边界条件和异常场景
   - 确保故事大小适中（适合一个 sprint 完成）

3. **验收标准定义**
   - 为每个用户故事定义可测试的验收标准
   - 包含功能性和非功能性要求
   - 明确边界条件和错误处理
   - 确保开发团队和测试团队理解一致

4. **产品文档**
   - 编写 PRD（产品需求文档）
   - 创建用户流程图和交互原型描述
   - 维护产品 backlog 和路线图

## 输出格式

对于需求分析任务：
- **用户故事**: 格式化的用户故事列表
- **验收标准**: 每个故事的 Given-When-Then 标准
- **优先级**: P0/P1/P2 分级
- **依赖关系**: 故事之间的依赖
- **风险**: 实施风险和用户价值评估

## 原则

⚠️ **原则**：
- 以用户价值为导向，不是以技术实现为导向
- 需求必须清晰、可测试、可验收
- 避免过度规定，给开发团队留出技术决策空间
- 考虑不同用户角色的需求和体验
- 用数据和用户反馈支撑需求决策
"""


class ProductManagerAgent(ClaudeAgentWrapper):
    """Product Manager Agent: 需求优先级、用户故事、验收标准"""

    @property
    def capabilities(self) -> list[ExecutorCapability]:
        return self.get_capabilities()

    @property
    def executor_id(self) -> str:
        return self.config.name

    @property
    def name(self) -> str:
        return self.config.name

    def match_score(self, capability: ExecutorCapability) -> float:
        """计算此 Agent 与指定能力的匹配分数"""
        if capability in self.get_capabilities():
            return 1.0
        return 0.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_iterations: int = 10,
        timeout: int = 300,
        hooks: list = None,
    ):
        config = AgentConfig(
            name="product_manager",
            role=AgentRole.SPECIALIST,
            description="产品经理 - 需求优先级、用户故事、验收标准",
            model="qwen3.6-turbo",
            tools=["read_file", "write_file"],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=0.5,
            system_prompt=PM_SYSTEM_PROMPT,
        )

        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model="qwen3.6-turbo",
            max_tokens=8192,
            temperature=0.5,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.WRITE_FILE,
            ],
            system_prompt=PM_SYSTEM_PROMPT,
        )

        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)

        super().__init__(config, claude_config, hooks)

        self._domain_tools = [PMTool()]

    def _get_domain_tools(self) -> list:
        """返回领域专用工具列表"""
        return self._domain_tools

    def get_capabilities(self) -> list[ExecutorCapability]:
        return [
            ExecutorCapability.PRODUCT_MANAGEMENT,
        ]
