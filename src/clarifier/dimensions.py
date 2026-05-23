"""
Phase 9: ClarifierAgent — 9 维度评分模型

定义需求澄清的 9 个评估维度、评分计算和判定逻辑。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClarificationDimension:
    """单个澄清维度定义"""
    name: str           # 维度标识符
    label: str          # 中文标签
    description: str    # 维度说明
    weight: float = 1.0  # 权重（默认等权）
    example_question: str = ""  # 示例问题


@dataclass
class DimensionScore:
    """单个维度的评分结果"""
    dimension: str      # 维度名
    score: int          # 1-5 分
    reason: str = ""    # 评分理由
    question: Optional[str] = None  # 如需澄清，生成的问题


# 9 个澄清维度定义
CLARIFICATION_DIMENSIONS: dict[str, ClarificationDimension] = {
    "functional_scope": ClarificationDimension(
        name="functional_scope",
        label="功能范围",
        description="需要实现哪些核心功能？功能边界在哪里？",
        weight=1.0,
        example_question="需要哪些核心功能？功能的边界是什么？",
    ),
    "target_users": ClarificationDimension(
        name="target_users",
        label="目标用户",
        description="面向什么用户群体？用户画像是什么？",
        weight=1.0,
        example_question="面向什么用户群体？他们的特征和使用场景是什么？",
    ),
    "tech_constraints": ClarificationDimension(
        name="tech_constraints",
        label="技术约束",
        description="有技术栈偏好或限制吗？需要兼容哪些平台？",
        weight=1.0,
        example_question="有技术栈偏好或限制吗？需要兼容哪些平台或浏览器？",
    ),
    "timeline": ClarificationDimension(
        name="timeline",
        label="时间要求",
        description="期望的交付时间是？有里程碑节点吗？",
        weight=1.0,
        example_question="期望的交付时间是？有没有关键的里程碑节点？",
    ),
    "budget": ClarificationDimension(
        name="budget",
        label="预算范围",
        description="预算或成本限制是？",
        weight=1.0,
        example_question="预算或成本限制是多少？",
    ),
    "quality_reqs": ClarificationDimension(
        name="quality_reqs",
        label="质量要求",
        description="对性能、安全、可用性有什么要求？",
        weight=1.0,
        example_question="对性能、安全性、可用性有什么具体要求？",
    ),
    "integration": ClarificationDimension(
        name="integration",
        label="集成需求",
        description="需要对接现有系统或第三方服务吗？",
        weight=1.0,
        example_question="需要对接现有系统或第三方 API 吗？",
    ),
    "success_criteria": ClarificationDimension(
        name="success_criteria",
        label="成功标准",
        description="怎么判断这个项目成功了？验收标准是什么？",
        weight=1.0,
        example_question="怎么判断这个项目成功了？验收标准是什么？",
    ),
    "context": ClarificationDimension(
        name="context",
        label="项目背景",
        description="这个项目的背景和业务场景是什么？",
        weight=1.0,
        example_question="这个项目的背景和业务场景是什么？为什么要做这个项目？",
    ),
}

# 默认权重配置（可按任务类型调整）
DEFAULT_WEIGHTS: dict[str, float] = {
    name: dim.weight for name, dim in CLARIFICATION_DIMENSIONS.items()
}

# 任务类型权重配置
TASK_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "development": {
        "functional_scope": 1.5,
        "tech_constraints": 1.5,
        "target_users": 1.0,
        "timeline": 1.0,
        "budget": 0.8,
        "quality_reqs": 1.2,
        "integration": 1.0,
        "success_criteria": 1.0,
        "context": 0.8,
    },
    "design": {
        "functional_scope": 1.0,
        "target_users": 1.5,
        "tech_constraints": 0.8,
        "timeline": 1.0,
        "budget": 1.0,
        "quality_reqs": 1.5,
        "integration": 0.5,
        "success_criteria": 1.0,
        "context": 1.2,
    },
    "analysis": {
        "functional_scope": 1.0,
        "target_users": 1.0,
        "tech_constraints": 0.5,
        "timeline": 1.0,
        "budget": 1.0,
        "quality_reqs": 1.0,
        "integration": 0.5,
        "success_criteria": 1.5,
        "context": 1.5,
    },
}

# 判定阈值
THRESHOLD_PASS: float = 80.0      # >= 80 直接通过
THRESHOLD_CLARIFY: float = 50.0   # 50-79 需要澄清，< 50 强烈建议交互


def calculate_total_score(
    dimension_scores: dict[str, DimensionScore],
    weights: Optional[dict[str, float]] = None,
) -> float:
    """计算加权总分 (0-100)

    Args:
        dimension_scores: 各维度评分 {维度名: DimensionScore}
        weights: 权重配置，默认使用 DEFAULT_WEIGHTS

    Returns:
        float: 0-100 的总分
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total_weight = 0.0
    weighted_sum = 0.0

    for dim_name, dim_score in dimension_scores.items():
        weight = weights.get(dim_name, 1.0)
        weighted_sum += dim_score.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    # 加权平均 (1-5) 转换为 0-100
    average = weighted_sum / total_weight
    return round((average - 1) / 4 * 100, 1)


def get_recommendation(score: float) -> str:
    """根据分数给出建议

    Args:
        score: 0-100 的总分

    Returns:
        str: "skip" / "conservative" / "interactive"
    """
    if score >= THRESHOLD_PASS:
        return "skip"
    elif score >= THRESHOLD_CLARIFY:
        return "conservative"
    else:
        return "interactive"


def get_low_score_dimensions(
    dimension_scores: dict[str, DimensionScore],
    threshold: int = 3,
) -> list[str]:
    """获取评分低于阈值的维度

    Args:
        dimension_scores: 各维度评分
        threshold: 分数阈值（默认 3，即 <= 2 分视为低分）

    Returns:
        list[str]: 低分维度名列表
    """
    return [
        dim_name
        for dim_name, dim_score in dimension_scores.items()
        if dim_score.score <= threshold
    ]


def get_weights_for_task_type(task_type: str) -> dict[str, float]:
    """获取指定任务类型的权重配置

    Args:
        task_type: 任务类型 ("development" / "design" / "analysis")

    Returns:
        dict[str, float]: 权重配置
    """
    return TASK_TYPE_WEIGHTS.get(task_type, DEFAULT_WEIGHTS)
