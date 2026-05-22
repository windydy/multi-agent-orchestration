"""
Phase 6: Architect Agent

架构设计、技术选型、性能优化
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks
from ..plan.graph import ExecutorCapability


# Architect Agent 系统提示词
ARCHITECT_SYSTEM_PROMPT = """
你是资深系统架构师和技术顾问，拥有 15 年以上分布式系统和微服务架构设计经验。

## 核心职责

1. **架构设计**
   - 设计高可用、可扩展的系统架构
   - 评估架构方案的优缺点（CAP 定理、一致性权衡）
   - 设计微服务边界和 API 契约
   - 制定架构原则和规范

2. **技术选型**
   - 评估技术栈和框架选择
   - 分析技术方案的长期维护成本
   - 制定技术债务管理策略
   - 提供技术评估报告

3. **性能优化**
   - 性能瓶颈分析和调优建议
   - 容量规划和资源预估
   - 缓存策略设计（Redis、CDN、本地缓存）
   - 数据库查询优化和索引策略

4. **非功能性需求**
   - 可扩展性、可用性、容错性设计
   - 安全架构和零信任模型
   - 合规性和审计要求

## 输出格式

对于架构设计任务：
- **架构概述**: 整体架构图（文字描述组件关系）
- **技术选型**: 选型理由和替代方案评估
- **详细设计**: 关键组件的设计细节
- **权衡分析**: 做出的技术权衡和理由
- **风险和缓解**: 潜在风险和应对策略
- **演进路线**: 从现状到目标架构的迁移步骤

## 约束

⚠️ **原则**：
- 优先考虑简单性和可维护性，避免过度工程
- 明确假设条件，避免不切实际的建议
- 所有架构决策必须有明确的技术依据
- 考虑团队的技能和经验水平
- 提供渐进式迁移方案，不推荐大爆炸式重写
"""


class ArchitectAgent(ClaudeAgentWrapper):
    """Architect Agent: 架构设计、技术选型、性能优化"""

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
        max_iterations: int = 15,
        timeout: int = 600,
        hooks: list = None,
    ):
        config = AgentConfig(
            name="architect",
            role=AgentRole.SPECIALIST,
            description="架构师 - 架构设计、技术选型、性能优化",
            model="qwen3.6-plus",
            tools=["read_file", "write_file", "search"],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=0.3,
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
        )

        claude_config = ClaudeSDKConfig(
            api_key=api_key,
            model="qwen3.6-plus",
            max_tokens=8192,
            temperature=0.3,
            tools=[
                ClaudeToolType.READ_FILE,
                ClaudeToolType.WRITE_FILE,
                ClaudeToolType.SEARCH,
            ],
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
        )

        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)

        super().__init__(config, claude_config, hooks)

    def get_capabilities(self) -> list[ExecutorCapability]:
        return [
            ExecutorCapability.ARCHITECTURE_DESIGN,
        ]
