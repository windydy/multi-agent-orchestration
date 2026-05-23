"""
Phase 9: ClarifierAgent — 数据模型

定义 ClarifierResult、ClarificationQuestion、Assumption 等数据类。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClarificationQuestion:
    """单个澄清问题"""
    dimension: str          # 维度名 (如 "functional_scope")
    question: str           # 问题文本
    importance: str = "medium"  # "high" / "medium" / "low"
    user_answer: Optional[str] = None  # 用户回复（交互模式）

    @property
    def dimension_label(self) -> str:
        """获取维度中文标签"""
        from .dimensions import CLARIFICATION_DIMENSIONS
        dim = CLARIFICATION_DIMENSIONS.get(self.dimension)
        return dim.label if dim else self.dimension


@dataclass
class Assumption:
    """保守模式的假设"""
    dimension: str          # 维度名
    assumption: str         # 假设内容
    risk_level: str = "medium"  # "low" / "medium" / "high"

    @property
    def dimension_label(self) -> str:
        """获取维度中文标签"""
        from .dimensions import CLARIFICATION_DIMENSIONS
        dim = CLARIFICATION_DIMENSIONS.get(self.dimension)
        return dim.label if dim else self.dimension


@dataclass
class ClarifierResult:
    """ClarifierAgent 的澄清结果"""
    score: float                              # 0-100 澄清分数
    dimensions: dict[str, "DimensionScore"]   # 各维度评分
    questions: list[ClarificationQuestion]    # 待澄清问题
    assumptions: list[Assumption]             # 保守模式的假设
    recommendation: str                       # "skip" / "conservative" / "interactive"
    enriched_task: str = ""                   # 增强后的任务描述（含假设）
    raw_input: str = ""                       # 原始用户输入
    task_type: str = "development"            # 任务类型

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "score": self.score,
            "dimensions": {
                k: {
                    "dimension": v.dimension,
                    "score": v.score,
                    "reason": v.reason,
                    "question": v.question,
                }
                for k, v in self.dimensions.items()
            },
            "questions": [
                {
                    "dimension": q.dimension,
                    "question": q.question,
                    "importance": q.importance,
                    "user_answer": q.user_answer,
                }
                for q in self.questions
            ],
            "assumptions": [
                {
                    "dimension": a.dimension,
                    "assumption": a.assumption,
                    "risk_level": a.risk_level,
                }
                for a in self.assumptions
            ],
            "recommendation": self.recommendation,
            "enriched_task": self.enriched_task,
            "raw_input": self.raw_input,
            "task_type": self.task_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClarifierResult":
        """从字典反序列化"""
        from .dimensions import DimensionScore

        dimensions = {}
        for k, v in data.get("dimensions", {}).items():
            dimensions[k] = DimensionScore(
                dimension=v.get("dimension", k),
                score=v.get("score", 1),
                reason=v.get("reason", ""),
                question=v.get("question"),
            )

        questions = [
            ClarificationQuestion(
                dimension=q.get("dimension", ""),
                question=q.get("question", ""),
                importance=q.get("importance", "medium"),
                user_answer=q.get("user_answer"),
            )
            for q in data.get("questions", [])
        ]

        assumptions = [
            Assumption(
                dimension=a.get("dimension", ""),
                assumption=a.get("assumption", ""),
                risk_level=a.get("risk_level", "medium"),
            )
            for a in data.get("assumptions", [])
        ]

        return cls(
            score=data.get("score", 0.0),
            dimensions=dimensions,
            questions=questions,
            assumptions=assumptions,
            recommendation=data.get("recommendation", "interactive"),
            enriched_task=data.get("enriched_task", ""),
            raw_input=data.get("raw_input", ""),
            task_type=data.get("task_type", "development"),
        )


# 导入 DimensionScore 避免循环引用
from .dimensions import DimensionScore  # noqa: E402, F401
