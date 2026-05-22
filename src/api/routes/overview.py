"""Overview stats route."""

from fastapi import APIRouter
from ..models import OverviewStats
from .executions import _get_log

router = APIRouter()


@router.get("/overview", response_model=OverviewStats)
async def get_overview():
    log = _get_log()
    ov = log.get_overview()
    sb = ov.get("status_breakdown", {})
    return OverviewStats(
        total_executions=ov["total_executions"],
        running=sb.get("running", 0),
        success=sb.get("success", 0),
        failed=sb.get("failed", 0),
        interrupted=sb.get("interrupted", 0),
        total_cost_24h=ov.get("total_cost_24h", 0.0),
        total_tokens_24h=ov.get("total_tokens_24h", 0),
    )
