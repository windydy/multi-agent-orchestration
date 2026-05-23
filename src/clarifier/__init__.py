"""
Phase 9: ClarifierAgent — 需求澄清模块

src/clarifier/
├── __init__.py
├── agent.py          # ClarifierAgent 主类
├── dimensions.py      # 维度定义和评分模型
├── prompts.py         # 系统提示和模板
└── result.py          # 数据模型
"""

from .dimensions import (
    CLARIFICATION_DIMENSIONS,
    DEFAULT_WEIGHTS,
    TASK_TYPE_WEIGHTS,
    THRESHOLD_CLARIFY,
    THRESHOLD_PASS,
    ClarificationDimension,
    DimensionScore,
    calculate_total_score,
    get_low_score_dimensions,
    get_recommendation,
    get_weights_for_task_type,
)
from .result import Assumption, ClarificationQuestion, ClarifierResult
from .agent import ClarifierAgent, create_clarifier

__all__ = [
    # Agent
    "ClarifierAgent",
    "create_clarifier",
    # Result models
    "ClarifierResult",
    "ClarificationQuestion",
    "Assumption",
    # Dimensions
    "CLARIFICATION_DIMENSIONS",
    "DEFAULT_WEIGHTS",
    "TASK_TYPE_WEIGHTS",
    "THRESHOLD_CLARIFY",
    "THRESHOLD_PASS",
    "ClarificationDimension",
    "DimensionScore",
    # Functions
    "calculate_total_score",
    "get_low_score_dimensions",
    "get_recommendation",
    "get_weights_for_task_type",
]
