from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.summary import SummaryResponse
from app.services.summary_service import build_summary

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def get_summary(player: Optional[str] = Query(default=None)) -> SummaryResponse:
    return SummaryResponse(**build_summary(player))

@router.get("/charts/{metric}")
def get_charts(metric: str, player: Optional[str] = Query(default=None)):
    from app.services.summary_service import get_chart_data
    return get_chart_data(player, metric)

@router.get("/summary/report")
def get_report(player: Optional[str] = Query(default=None)):
    from app.services.summary_service import get_analytics_report
    return get_analytics_report(player)
