from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.core.paths import get_data_file
from app.services.hand_history_service import get_hand
from data.manager import DataManager

router = APIRouter(prefix="/hands", tags=["hands"])


@router.get("", response_model=List[dict])
def get_hand_history(
    player: str = Query(..., description="Player name to fetch history for"),
    limit: int = Query(50, ge=1, le=500),
    reverse: bool = Query(True, description="Return newest first"),
):
    """Retrieve hand history for a specific player."""
    manager = DataManager(data_file=str(get_data_file()))

    if not manager.player_exists(player):
        # Brand-new guest with no history yet: return empty rather than 404
        return []

    try:
        history = manager.load_hand_history(player, limit=limit, reverse=reverse)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# IMPORTANT: declare /filter BEFORE /{player_name}/{hand_number} so FastAPI's
# path matcher tries the literal first. The int-typed path would otherwise
# shadow /filter and the validator would return 422 on the string "filter".
@router.get("/filter", response_model=List[dict])
def filter_hands(
    player: str = Query(..., description="Player name"),
    winner: Optional[str] = Query(
        None,
        description="Filter by winner ('hero' for current player, or specific name)",
    ),
    min_pot: Optional[int] = Query(None, description="Minimum pot size"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
    game_type: Optional[str] = Query(None, description="Filter by game type"),
    street: Optional[str] = Query(None, description="Filter by street"),
    decision_quality: Optional[str] = Query(None, description="Filter by decision grade"),
    weakness: Optional[str] = Query(None, description="Filter by weakness tag text"),
    limit: int = Query(50, le=100),
):
    """Filter hands by criteria (winner, pot size, street, decision grade, ...)."""
    manager = DataManager(data_file=str(get_data_file()))
    return manager.get_filtered_hands(
        player,
        winner=winner,
        min_pot=min_pot,
        limit=limit,
        session_id=session_id,
        game_type=game_type,
        street=street,
        decision_quality=decision_quality,
        weakness=weakness,
    )


@router.get("/{player_name}/{hand_number}", response_model=dict)
def get_hand_detail(
    player_name: str,
    hand_number: int,
    session_id: Optional[str] = Query(None, description="Disambiguate repeated hand numbers by session id"),
) -> dict:
    """Retrieve a specific hand from a player's history."""
    hand = get_hand(player_name, hand_number, session_id=session_id)
    if not hand:
        raise HTTPException(status_code=404, detail="Hand not found")
    return hand
