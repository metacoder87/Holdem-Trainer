from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.summary import SummaryResponse
from app.services.summary_service import build_summary

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def get_summary(player: Optional[str] = Query(default=None)) -> SummaryResponse:
    return SummaryResponse(**build_summary(player))


@router.get("/charts/{metric}")
def get_charts(
    metric: str,
    player: Optional[str] = Query(default=None),
    window: int = Query(default=1, ge=1, le=50),
    include_adjusted: bool = Query(default=False),
):
    """Chart data, optionally with rolling window + EV-adjusted line.

    Backed by ``analytics_service.get_chart_data`` so the chart route
    benefits from the Bayesian/variance pipeline. The original
    function lived in summary_service but was never implemented;
    this is the canonical path.
    """
    from app.services.analytics_service import get_chart_data

    return get_chart_data(
        player, metric, window=window, include_adjusted=include_adjusted
    )


@router.get("/summary/report")
def get_report(player: Optional[str] = Query(default=None)):
    """Aggregate analytics report (alias of /analytics/career-like).

    Routes to analytics_service.get_analytics_report so the
    Bayesian credible-interval fields land here too.
    """
    from app.services.analytics_service import get_analytics_report

    return get_analytics_report(player)
