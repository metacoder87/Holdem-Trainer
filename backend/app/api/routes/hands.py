from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.hand_history_service import get_hand, list_hands

router = APIRouter()


@router.get("/hands")
def hand_list(
    player: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    reverse: bool = Query(default=True),
):
    return list_hands(player, limit=limit, reverse=reverse)


@router.get("/hands/{player_name}/{hand_number}")
def hand_detail(player_name: str, hand_number: int):
    hand = get_hand(player_name, hand_number)
    if not hand:
        raise HTTPException(status_code=404, detail="Hand not found")
    return hand
