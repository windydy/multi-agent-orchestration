"""Clarification API routes for Phase 9.

Provides endpoints for:
- POST /api/clarification/analyze - Analyze task description completeness
- POST /api/clarification/re-evaluate - Re-evaluate based on user answers
- GET  /api/clarification/dimensions - Get clarification dimension definitions
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.clarifier.agent import ClarifierAgent
from src.clarifier.dimensions import (
    CLARIFICATION_DIMENSIONS,
    DEFAULT_WEIGHTS,
    TASK_TYPE_WEIGHTS,
)

router = APIRouter(prefix="/clarification", tags=["clarification"])

# Module-level ClarifierAgent instance (injected at startup)
_clarifier: Optional[ClarifierAgent] = None

logger = logging.getLogger(__name__)


def set_clarifier(agent: ClarifierAgent) -> None:
    """Inject the ClarifierAgent instance."""
    global _clarifier
    _clarifier = agent


def _get_clarifier() -> ClarifierAgent:
    if _clarifier is None:
        raise HTTPException(500, "ClarifierAgent not initialized")
    return _clarifier


# ── Request/Response models ──

class AnalyzeRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10000, description="Task description to analyze")
    task_type: str = Field(default="development", description="Task type for weighting")


class DimensionScoreResponse(BaseModel):
    dimension: str
    score: int
    reason: str
    question: Optional[str] = None


class ClarificationQuestionResponse(BaseModel):
    dimension: str
    dimension_label: str
    question: str
    importance: str
    user_answer: Optional[str] = None


class AssumptionResponse(BaseModel):
    dimension: str
    dimension_label: str
    assumption: str
    risk_level: str


class AnalyzeResponse(BaseModel):
    score: float
    recommendation: str  # "skip" | "conservative" | "interactive"
    dimensions: dict[str, DimensionScoreResponse]
    questions: list[ClarificationQuestionResponse]
    assumptions: list[AssumptionResponse]
    enriched_task: str
    raw_input: str
    task_type: str


class ReEvaluateRequest(BaseModel):
    original_task: str = Field(min_length=1, max_length=10000, description="Original task description")
    user_answers: dict[str, str] = Field(description="User answers keyed by dimension name")
    task_type: str = Field(default="development", description="Task type for weighting")


class ReEvaluateResponse(BaseModel):
    score: float
    recommendation: str
    dimensions: dict[str, DimensionScoreResponse]
    questions: list[ClarificationQuestionResponse]
    assumptions: list[AssumptionResponse]
    enriched_task: str
    raw_input: str
    task_type: str


class DimensionDefinitionResponse(BaseModel):
    name: str
    label: str
    description: str
    weight: float
    example_question: str


class DimensionsResponse(BaseModel):
    dimensions: list[DimensionDefinitionResponse]
    default_weights: dict[str, float]
    task_type_weights: dict[str, dict[str, float]]


# ── Helper functions ──

def _convert_dimension_scores(dimensions: dict) -> dict[str, DimensionScoreResponse]:
    """Convert internal dimension scores to API response format."""
    result = {}
    for key, score in dimensions.items():
        result[key] = DimensionScoreResponse(
            dimension=score.dimension,
            score=score.score,
            reason=score.reason,
            question=score.question,
        )
    return result


def _convert_questions(questions: list) -> list[ClarificationQuestionResponse]:
    """Convert internal questions to API response format."""
    return [
        ClarificationQuestionResponse(
            dimension=q.dimension,
            dimension_label=q.dimension_label,
            question=q.question,
            importance=q.importance,
            user_answer=q.user_answer,
        )
        for q in questions
    ]


def _convert_assumptions(assumptions: list) -> list[AssumptionResponse]:
    """Convert internal assumptions to API response format."""
    return [
        AssumptionResponse(
            dimension=a.dimension,
            dimension_label=a.dimension_label,
            assumption=a.assumption,
            risk_level=a.risk_level,
        )
        for a in assumptions
    ]


# ── Routes ──

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_task(req: AnalyzeRequest):
    """Analyze task description completeness.

    Evaluates the task against 9 clarification dimensions and returns:
    - Overall score (0-100)
    - Recommendation: skip (>=80), conservative (50-79), interactive (<50)
    - Per-dimension scores with reasons
    - Clarification questions (if interactive mode)
    - Conservative assumptions (if conservative mode)
    - Enriched task description (with assumptions filled in)
    """
    clarifier = _get_clarifier()

    try:
        result = await clarifier.analyze(req.task, task_type=req.task_type)

        return AnalyzeResponse(
            score=result.score,
            recommendation=result.recommendation,
            dimensions=_convert_dimension_scores(result.dimensions),
            questions=_convert_questions(result.questions),
            assumptions=_convert_assumptions(result.assumptions),
            enriched_task=result.enriched_task,
            raw_input=result.raw_input,
            task_type=result.task_type,
        )
    except Exception as e:
        logger.error("[Clarification] Analyze failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Clarification analysis failed: {str(e)}")


@router.post("/re-evaluate", response_model=ReEvaluateResponse)
async def re_evaluate_task(req: ReEvaluateRequest):
    """Re-evaluate task based on user answers to clarification questions.

    Takes the original task and user-provided answers, then re-scores
    the task completeness.
    """
    clarifier = _get_clarifier()

    try:
        result = await clarifier.re_evaluate(
            original_task=req.original_task,
            user_answers=req.user_answers,
            task_type=req.task_type,
        )

        return ReEvaluateResponse(
            score=result.score,
            recommendation=result.recommendation,
            dimensions=_convert_dimension_scores(result.dimensions),
            questions=_convert_questions(result.questions),
            assumptions=_convert_assumptions(result.assumptions),
            enriched_task=result.enriched_task,
            raw_input=result.raw_input,
            task_type=result.task_type,
        )
    except Exception as e:
        logger.error("[Clarification] Re-evaluate failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Clarification re-evaluation failed: {str(e)}")


@router.get("/dimensions", response_model=DimensionsResponse)
async def get_dimensions():
    """Get clarification dimension definitions and weights.

    Returns all 9 clarification dimensions with their labels, descriptions,
    and default/task-type-specific weights.
    """
    dimensions = []
    for name, dim in CLARIFICATION_DIMENSIONS.items():
        dimensions.append(DimensionDefinitionResponse(
            name=name,
            label=dim.label,
            description=dim.description,
            weight=DEFAULT_WEIGHTS.get(name, 1.0),
            example_question=dim.example_question,
        ))

    return DimensionsResponse(
        dimensions=dimensions,
        default_weights=DEFAULT_WEIGHTS,
        task_type_weights=TASK_TYPE_WEIGHTS,
    )
