"""Workflows and models enumeration API (S4)."""

from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


# ── Response models ──

class WorkflowItem(BaseModel):
    name: str
    description: str


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowItem]


class ModelOption(BaseModel):
    name: str
    provider: str
    description: str


class ModelListResponse(BaseModel):
    models: list[ModelOption]


# ── Routes ──

@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows():
    """S4: List available workflow templates.

    Returns the set of workflow templates that can be used when creating
    a new execution. Currently hard-coded but should be loaded from
    workflow configuration in a future iteration.
    """
    return WorkflowListResponse(
        workflows=[
            WorkflowItem(
                name="development",
                description="Full development pipeline: requirements → design → develop → review → test → fix",
            ),
        ]
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """S4: List available model configurations.

    Returns the models that can be assigned to agents when creating
    a new execution.
    """
    return ModelListResponse(
        models=[
            ModelOption(name="sonnet", provider="anthropic", description="Claude Sonnet - balanced speed/quality"),
            ModelOption(name="opus", provider="anthropic", description="Claude Opus - highest quality"),
            ModelOption(name="haiku", provider="anthropic", description="Claude Haiku - fastest, lowest cost"),
        ]
    )
