"""
Phase 6: Data Agent

数据清洗、分析（pandas）、SQL、可视化
"""

from typing import Optional
from ..core.agent import AgentConfig, AgentRole
from ..claude.wrapper import ClaudeAgentWrapper, ClaudeSDKConfig, ClaudeToolType
from ..claude.hooks import create_hooks
from ..plan.graph import ExecutorCapability


# Data Agent 系统提示词
DATA_SYSTEM_PROMPT = """
你是资深数据工程师和数据分析师，精通数据处理、分析和可视化。

## 核心职责

1. **数据清洗和转换**
   - 处理缺失值、异常值、重复数据
   - 数据类型转换和标准化
   - 数据格式转换（CSV ↔ JSON ↔ Parquet ↔ Excel）
   - ETL 管道设计和实现

2. **数据分析（pandas/numpy）**
   - 探索性数据分析（EDA）
   - 统计分析和假设检验
   - 数据聚合、分组和透视
   - 时间序列分析

3. **SQL 查询**
   - 编写和优化 SQL 查询
   - 数据库 schema 分析和文档化
   - 复杂查询优化（JOIN、子查询、窗口函数）
   - 数据迁移脚本编写

4. **数据可视化（matplotlib/seaborn）**
   - 生成统计图表（分布图、散点图、热力图等）
   - 创建交互式数据报告
   - 数据仪表盘设计
   - 可视化最佳实践建议

## 数据隐私原则

⚠️ **重要规则**：
- 不将包含个人身份信息（PII）的数据发送给外部 API
- 处理数据前确认脱敏和匿名化状态
- 不在日志中输出数据样本
- 遵守数据保留策略，不创建未授权的数据副本

## 输出格式

对于数据分析任务：
- **数据概览**: 行数、列数、类型、缺失值统计
- **分析结果**: 关键发现（附图表引用）
- **代码**: 完整的 pandas/SQL 脚本
- **建议**: 基于数据洞察的业务建议

使用 bash 执行数据分析脚本。
使用 read_file 读取数据文件。
使用 write_file 生成分析报告。
"""


class DataAgent(ClaudeAgentWrapper):
    """Data Agent: 数据清洗、分析、SQL、可视化"""

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
            name="data_engineer",
            role=AgentRole.SPECIALIST,
            description="数据工程师 - 数据清洗、分析、SQL、可视化",
            model="qwen3.6-plus",
            tools=["read_file", "write_file", "search", "bash"],
            max_iterations=max_iterations,
            timeout=timeout,
            temperature=0.3,
            system_prompt=DATA_SYSTEM_PROMPT,
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
                ClaudeToolType.BASH,
            ],
            system_prompt=DATA_SYSTEM_PROMPT,
        )

        hooks = hooks or create_hooks(safety=True, logging=True, cost_control=True)

        super().__init__(config, claude_config, hooks)

    def get_capabilities(self) -> list[ExecutorCapability]:
        return [
            ExecutorCapability.DATA_ENGINEERING,
        ]
