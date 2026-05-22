"""Track 5 poker math endpoints.

Public API:
  GET  /api/poker/preflop-charts  Named preflop ranges (class maps).
  POST /api/poker/range-equity    Multiway equity for arbitrary spots.
"""
from __future__ import annotations

from typing import Any, List, Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.poker_service import (
    compute_range_equity,
    get_preflop_charts,
)

router = APIRouter(tags=["poker"])


class PlayerSpec(BaseModel):
    """One player's hand in a range-equity request.

    Exactly one of ``hand``, ``range``, or ``preflop_chart`` must be
    provided.
    """

    hand: Optional[List[str]] = None
    range: Optional[str] = None
    preflop_chart: Optional[str] = None


class RangeEquityRequest(BaseModel):
    players: List[PlayerSpec] = Field(..., min_length=2, max_length=9)
    board: Optional[List[str]] = None
    trials: Optional[int] = Field(default=None, ge=50, le=50000)


@router.get("/poker/preflop-charts")
def poker_preflop_charts() -> dict:
    """Named preflop ranges + raw notation strings.

    Frontend uses ``charts`` to render the 13x13 grid; ``raw`` is the
    paste-back form for the range editor.
    """
    return get_preflop_charts()


@router.post("/poker/range-equity")
def poker_range_equity(payload: RangeEquityRequest) -> dict:
    """Compute multiway equity for any mix of fixed hands, notation
    ranges, and named preflop charts.

    Card removal is enforced across all players and the board. Trial
    count auto-adjusts based on street if not specified.
    """
    try:
        return compute_range_equity(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
