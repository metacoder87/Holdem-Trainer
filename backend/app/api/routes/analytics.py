from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.analytics_service import (
    generate_drill_from_decision,
    get_career_report,
    get_chart_data,
    get_ev_leak_report,
    get_icm_report,
    get_regret_heatmap,
    get_session_report,
    get_session_rows,
    get_variance_report,
)

router = APIRouter(tags=["analytics"])


@router.get("/stats/sessions")
def get_player_sessions(
    player: str = Query(..., description="Player name"),
    limit: int = Query(20, le=100),
):
    """Past game sessions for a player (newest last)."""
    return get_session_rows(player, limit=limit)


@router.get("/analytics/career")
def analytics_career(player: Optional[str] = Query(default=None)) -> dict:
    """Career aggregates + milestones across the player's full session log."""
    return get_career_report(player)


@router.get("/analytics/ev-leaks")
def analytics_ev_leaks(
    player: Optional[str] = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Grouped EV loss from priced decision points."""
    return get_ev_leak_report(player, limit=limit)


# /latest is declared BEFORE /{session_index} so FastAPI's path matcher tries
# the literal "latest" first instead of trying to parse it as an int.
@router.get("/analytics/sessions/latest")
def analytics_latest_session_report(
    player: Optional[str] = Query(default=None),
) -> dict:
    payload = get_session_report(player, None)
    if not payload.get("report"):
        raise HTTPException(status_code=404, detail="No session data yet")
    return payload


@router.get("/analytics/sessions/{session_index}")
def analytics_session_report(
    session_index: int,
    player: Optional[str] = Query(default=None),
) -> dict:
    payload = get_session_report(player, session_index)
    if not payload.get("report"):
        raise HTTPException(status_code=404, detail="Session report unavailable")
    return payload


# ---------- Track 2: Bayesian analytics endpoints ----------


@router.get("/analytics/variance")
def analytics_variance(
    player: Optional[str] = Query(default=None),
    bankroll_bbs: Optional[float] = Query(
        default=None,
        ge=0,
        description=(
            "Bankroll in big blinds. When provided, the response includes "
            "risk_of_ruin and kelly_fraction; otherwise those are null."
        ),
    ),
) -> dict:
    """Variance, all-in luck delta, risk-of-ruin, Kelly fraction.

    Inputs come from the player's session history. Frontend renders
    this as the "Variance & Risk" panel on the Analytics page.
    """
    return get_variance_report(player, bankroll_bbs=bankroll_bbs)


@router.get("/analytics/chart")
def analytics_chart(
    player: Optional[str] = Query(default=None),
    metric: str = Query(default="vpip"),
    window: int = Query(default=1, ge=1, le=50),
    include_adjusted: bool = Query(default=False),
) -> list:
    """Chart series with optional rolling window + EV-adjusted line.

    Returns one row per session with optional fields:
      - ``rolling_value`` when ``window > 1`` (BB/100 rolling-average).
      - ``realized_cumulative_bb`` + ``ev_cumulative_bb`` when
        ``metric=profit`` and ``include_adjusted=True``.
    """
    return get_chart_data(
        player,
        metric=metric,
        window=window,
        include_adjusted=include_adjusted,
    )


class IcmSpotRequest(BaseModel):
    """Body for POST /analytics/icm/spot — explicit hypothetical spot."""

    stacks: List[float] = Field(..., min_length=2, max_length=9)
    payouts: List[float] = Field(..., min_length=1, max_length=9)
    hero_index: int = Field(default=0, ge=0)


@router.post("/analytics/icm/spot")
def analytics_icm_spot(payload: IcmSpotRequest) -> dict:
    """Explicit ICM calculation for a hypothetical spot.

    Use this when the frontend wants to inspect any (stacks, payouts)
    combo, not just the player's most recent tournament. Hero index
    selects which seat the risk-premium is computed for.
    """
    if payload.hero_index >= len(payload.stacks):
        raise HTTPException(
            status_code=400, detail="hero_index out of range for stacks"
        )
    return get_icm_report(
        player_name=None,
        stacks=payload.stacks,
        payouts=payload.payouts,
        hero_index=payload.hero_index,
    )


@router.get("/analytics/icm")
def analytics_icm_player(
    player: Optional[str] = Query(default=None),
) -> dict:
    """ICM equities from a player's most recent tournament session.

    Returns ``{icm: null, note: ...}`` when no tournament data is
    available; the frontend renders a placeholder in that case.
    """
    return get_icm_report(player_name=player)


# ---------- Track 3: Regret heatmap + drill-from-decision ----------


@router.get("/analytics/regret-heatmap")
def analytics_regret_heatmap(
    player: Optional[str] = Query(default=None),
    scan_hands: int = Query(default=500, ge=10, le=2000),
) -> dict:
    """EV-loss heatmap grouped by (street, position, spr_bucket).

    The Track-3 "regret-by-spot" view: identifies where in the
    decision space (which street, which seat, which stack-to-pot
    band) a player concentrates their EV loss. The dominating cells
    are the structural leaks.
    """
    return get_regret_heatmap(player, scan_hands=scan_hands)


class DrillFromDecisionRequest(BaseModel):
    """Body for POST /api/training/drill/from-decision."""

    player: str = Field(..., min_length=1)
    hand_number: int = Field(..., ge=1)
    decision_index: int = Field(..., ge=0)


@router.post("/training/drill/from-decision")
def training_drill_from_decision(payload: DrillFromDecisionRequest) -> dict:
    """Seed a training drill from one specific recorded decision.

    The replay vault uses this to wire each "Practice this spot"
    button: pass the hand number + decision index, get back a drill
    with the exact same board / hole cards / pot / position the
    user originally faced. The drill is registered with the same
    pending_drills bucket the existing evaluator consumes, so the
    grading flow is unchanged.
    """
    result = generate_drill_from_decision(
        player_name=payload.player,
        hand_number=payload.hand_number,
        decision_index=payload.decision_index,
    )
    if result.get("drill") is None:
        raise HTTPException(
            status_code=404,
            detail=result.get("error") or "Decision not found",
        )
    return result
