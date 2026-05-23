"""Clarification API routes (Phase 9).

Provides endpoints for the ClarifierAgent:
- POST /api/clarification/analyze — Analyze task completeness
- GET  /api/clarification/dimensions — Get clarification dimension definitions
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.clarifier.agent import ClarifierAgent
from src.clarifier.dimensions import CLARIFICATION_DIMENSIONS

router = APIRouter(prefix="/api", tags=["api"])

_clarifier: ClarifierAgent | None = None


def set_clarifier(agent: ClarifierAgent) -> None:
    """Inject ClarifierAgent instance into routes."""
    global _clarifier
    _clarifier = agent


def _get_clarifier() -> ClarifierAgent:
    if _clarifier is None:
        raise HTTPException(500, "ClarifierAgent not initialized")
    return _clarifier


# ── Request/Response Models ──

class ClarificationAnalyzeRequest(BaseModel):
    task: str = Field(min_length=1, description="User task description to analyze")
    task_type: Optional[str] = Field(
        default="development",
        description="Task type: development / design / analysis",
    )


class DimensionScoreResponse(BaseModel):
    dimension: str
    score: int
    reason: str
    question: Optional[str] = None


class ClarificationQuestionResponse(BaseModel):
    dimension: str
    question: str
    importance: str
    user_answer: Optional[str] = None


class AssumptionResponse(BaseModel):
    dimension: str
    assumption: str
    risk_level: str


class ClarificationAnalyzeResponse(BaseModel):
    score: float
    recommendation: str  # "skip" / "conservative" / "interactive"
    dimensions: dict[str, DimensionScoreResponse]
    questions: list[ClarificationQuestionResponse]
    assumptions: list[AssumptionResponse]
    enriched_task: str
    raw_input: str
    task_type: str


class ClarificationDimensionInfo(BaseModel):
    name: str
    label: str
    description: str
    weight: float
    example_question: str


class ClarificationDimensionsResponse(BaseModel):
    dimensions: list[ClarificationDimensionInfo]
    thresholds: dict[str, float]


# ── Routes ──

@router.post("/clarification/analyze", response_model=ClarificationAnalyzeResponse)
async def analyze_task(req: ClarificationAnalyzeRequest):
    """Analyze task description completeness using ClarifierAgent.

    Returns a score (0-100), recommendation, and optionally
    clarification questions or conservative assumptions.
    """
    clarifier = _get_clarifier()
    try:
        result = await clarifier.analyze(req.task, task_type=req.task_type)
        return ClarificationAnalyzeResponse(
            score=result.score,
            recommendation=result.recommendation,
            dimensions={
                k: DimensionScoreResponse(
                    dimension=v.dimension,
                    score=v.score,
                    reason=v.reason,
                    question=v.question,
                )
                for k, v in result.dimensions.items()
            },
            questions=[
                ClarificationQuestionResponse(
                    dimension=q.dimension,
                    question=q.question,
                    importance=q.importance,
                    user_answer=q.user_answer,
                )
                for q in result.questions
            ],
            assumptions=[
                AssumptionResponse(
                    dimension=a.dimension,
                    assumption=a.assumption,
                    risk_level=a.risk_level,
                )
                for a in result.assumptions
            ],
            enriched_task=result.enriched_task,
            raw_input=result.raw_input,
            task_type=result.task_type,
        )
    except Exception as e:
        raise HTTPException(500, f"Clarification analysis failed: {str(e)}")


@router.get("/clarification/dimensions", response_model=ClarificationDimensionsResponse)
async def get_dimensions():
    """Get all clarification dimension definitions and thresholds.

    Returns the 9 evaluation dimensions used by ClarifierAgent
    along with the scoring thresholds.
    """
    from src.clarifier.dimensions import THRESHOLD_PASS, THRESHOLD_CLARIFY

    dimensions = [
        ClarificationDimensionInfo(
            name=dim.name,
            label=dim.label,
            description=dim.description,
            weight=dim.weight,
            example_question=dim.example_question,
        )
        for dim in CLARIFICATION_DIMENSIONS.values()
    ]

    return ClarificationDimensionsResponse(
        dimensions=dimensions,
        thresholds={
            "pass": THRESHOLD_PASS,
            "clarify": THRESHOLD_CLARIFY,
        },
    )
