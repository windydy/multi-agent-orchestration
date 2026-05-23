"""Config management API routes (Phase 4)."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.config_store import ConfigStore

router = APIRouter(tags=["api"])

_config_store: ConfigStore | None = None


def set_config_store(store: ConfigStore) -> None:
    global _config_store
    _config_store = store


def _get_store() -> ConfigStore:
    if _config_store is None:
        raise HTTPException(500, "ConfigStore not initialized")
    return _config_store


# ── Request/Response Models ──

class WorkflowResponse(BaseModel):
    name: str
    description: str
    yaml_content: str
    created_at: float
    updated_at: float


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]


class WorkflowCreateRequest(BaseModel):
    yaml_content: str = Field(min_length=1, description="YAML workflow definition")
    description: str = ""


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    capabilities: list[str]
    model: str
    enabled: bool
    created_at: float
    updated_at: float


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]


class AgentUpdateRequest(BaseModel):
    model: Optional[str] = None
    enabled: Optional[bool] = None


class VerifierResponse(BaseModel):
    id: str
    name: str
    condition: str
    threshold: float
    action: str
    severity: str
    enabled: bool
    created_at: float
    updated_at: float


class VerifierListResponse(BaseModel):
    rules: list[VerifierResponse]


class VerifierCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    condition: str
    threshold: float
    action: str
    severity: str = "medium"


class VerifierUpdateRequest(BaseModel):
    threshold: Optional[float] = None
    enabled: Optional[bool] = None
    action: Optional[str] = None
    severity: Optional[str] = None


# ── Workflow Config Routes ──

@router.get("/api/config/workflows", response_model=WorkflowListResponse)
async def list_workflows():
    store = _get_store()
    workflows = store.list_workflows()
    return WorkflowListResponse(
        workflows=[WorkflowResponse(**w.__dict__) for w in workflows]
    )


@router.get("/api/config/workflows/{name}", response_model=WorkflowResponse)
async def get_workflow(name: str):
    store = _get_store()
    wf = store.get_workflow(name)
    if wf is None:
        raise HTTPException(404, f"Workflow '{name}' not found")
    return WorkflowResponse(**wf.__dict__)


@router.put("/api/config/workflows/{name}", response_model=WorkflowResponse)
async def upsert_workflow(name: str, req: WorkflowCreateRequest):
    store = _get_store()
    try:
        wf = store.upsert_workflow(name, req.yaml_content, req.description)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if wf is None:
        raise HTTPException(500, "Failed to save workflow")
    return WorkflowResponse(**wf.__dict__)


# ── Agent Config Routes ──

@router.get("/api/config/agents", response_model=AgentListResponse)
async def list_agents():
    store = _get_store()
    agents = store.list_agents()
    return AgentListResponse(
        agents=[AgentResponse(**a.__dict__) for a in agents]
    )


@router.get("/api/config/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    store = _get_store()
    agent = store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return AgentResponse(**agent.__dict__)


@router.put("/api/config/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, req: AgentUpdateRequest):
    store = _get_store()
    agent = store.update_agent(agent_id, model=req.model, enabled=req.enabled)
    if agent is None:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return AgentResponse(**agent.__dict__)


# ── Verifier Rule Routes ──

@router.get("/api/config/verifiers", response_model=VerifierListResponse)
async def list_verifiers():
    store = _get_store()
    rules = store.list_verifiers()
    return VerifierListResponse(
        rules=[VerifierResponse(**r.__dict__) for r in rules]
    )


@router.post("/api/config/verifiers", response_model=VerifierResponse, status_code=201)
async def create_verifier(req: VerifierCreateRequest):
    store = _get_store()
    rule = store.create_verifier(
        name=req.name,
        condition=req.condition,
        threshold=req.threshold,
        action=req.action,
        severity=req.severity,
    )
    return VerifierResponse(**rule.__dict__)


@router.put("/api/config/verifiers/{rule_id}", response_model=VerifierResponse)
async def update_verifier(rule_id: str, req: VerifierUpdateRequest):
    store = _get_store()
    rule = store.update_verifier(
        rule_id,
        threshold=req.threshold,
        enabled=req.enabled,
        action=req.action,
        severity=req.severity,
    )
    if rule is None:
        raise HTTPException(404, f"Verifier rule '{rule_id}' not found")
    return VerifierResponse(**rule.__dict__)


@router.delete("/api/config/verifiers/{rule_id}")
async def delete_verifier(rule_id: str):
    store = _get_store()
    success = store.delete_verifier(rule_id)
    if not success:
        raise HTTPException(404, f"Verifier rule '{rule_id}' not found")
    return {"status": "deleted"}
