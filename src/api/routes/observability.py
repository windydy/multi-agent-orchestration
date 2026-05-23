"""Observability API routes (Phase 5)."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.observability import ObservabilityStore

router = APIRouter(tags=["api"])

_observability: ObservabilityStore | None = None


def set_observability(store: ObservabilityStore) -> None:
    global _observability
    _observability = store


def _get_obs() -> ObservabilityStore:
    if _observability is None:
        raise HTTPException(500, "ObservabilityStore not initialized")
    return _observability


# ── Request/Response Models ──

class ObservabilityOverviewResponse(BaseModel):
    period: str
    total_executions: int
    total_cost: float
    total_tokens: int
    success_rate: float
    avg_duration_ms: float
    alert_count: int


class CostTrendResponse(BaseModel):
    trends: list[dict]


class SuccessRateResponse(BaseModel):
    rates: list[dict]


class NodePerformanceResponse(BaseModel):
    nodes: list[dict]


class FailureReasonsResponse(BaseModel):
    reasons: list[dict]


class AlertResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    triggered_at: float
    severity: str
    message: str
    acknowledged: bool


class AlertsListResponse(BaseModel):
    alerts: list[AlertResponse]


class AlertTriggerRequest(BaseModel):
    rule_id: str
    rule_name: str
    severity: str = "medium"
    message: str


# ── Routes ──

@router.get("/observability/overview", response_model=ObservabilityOverviewResponse)
async def get_observability_overview(period: str = "24h"):
    obs = _get_obs()
    overview = obs.get_overview(period=period)
    return ObservabilityOverviewResponse(**overview)


@router.get("/observability/cost/daily", response_model=CostTrendResponse)
async def get_cost_trend(days: int = 7):
    obs = _get_obs()
    trends = obs.get_cost_trend(days=days)
    return CostTrendResponse(trends=trends)


@router.get("/observability/success-rate", response_model=SuccessRateResponse)
async def get_success_rate(days: int = 7):
    obs = _get_obs()
    rates = obs.get_success_rate(days=days)
    return SuccessRateResponse(rates=rates)


@router.get("/observability/performance", response_model=NodePerformanceResponse)
async def get_node_performance():
    obs = _get_obs()
    nodes = obs.get_node_performance()
    return NodePerformanceResponse(nodes=nodes)


@router.get("/observability/failure-reasons", response_model=FailureReasonsResponse)
async def get_failure_reasons():
    obs = _get_obs()
    reasons = obs.get_failure_reasons()
    return FailureReasonsResponse(reasons=reasons)


@router.get("/observability/alerts", response_model=AlertsListResponse)
async def list_alerts():
    obs = _get_obs()
    alerts = obs.list_alerts()
    return AlertsListResponse(
        alerts=[AlertResponse(**a.__dict__) for a in alerts]
    )


@router.post("/observability/alerts/trigger", response_model=AlertResponse, status_code=201)
async def trigger_alert(req: AlertTriggerRequest):
    obs = _get_obs()
    alert = obs.create_alert(
        rule_id=req.rule_id,
        rule_name=req.rule_name,
        severity=req.severity,
        message=req.message,
    )
    if alert is None:
        raise HTTPException(409, "Alert already triggered within cooldown period")
    return AlertResponse(**alert.__dict__)


@router.put("/observability/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: str):
    obs = _get_obs()
    success = obs.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    alert = obs.list_alerts()
    matched = next((a for a in alert if a.id == alert_id), None)
    if matched is None:
        raise HTTPException(404, f"Alert '{alert_id}' not found after acknowledge")
    return AlertResponse(**matched.__dict__)
