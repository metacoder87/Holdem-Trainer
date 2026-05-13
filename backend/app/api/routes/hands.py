import io
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.hand_history_service import (
    STREET_ORDER,
    get_hand,
    get_replay,
    list_hands,
)

router = APIRouter()


def _parse_street_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value not in STREET_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"street_at_least must be one of {STREET_ORDER}",
        )
    return value


@router.get("/hands")
def hand_list(
    player: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    reverse: bool = Query(default=True),
    won: Optional[bool] = Query(default=None),
    min_pot: Optional[int] = Query(default=None, ge=0),
    max_pot: Optional[int] = Query(default=None, ge=0),
    street_at_least: Optional[str] = Query(default=None),
    before_hand_number: Optional[int] = Query(default=None, ge=1),
    after_hand_number: Optional[int] = Query(default=None, ge=0),
):
    """List hands. Use `before_hand_number` (newest-first) or
    `after_hand_number` (oldest-first) for cursor pagination — pass the
    `hand_number` of the last item from the previous page.
    """
    return list_hands(
        player,
        limit=limit,
        reverse=reverse,
        won=won,
        min_pot=min_pot,
        max_pot=max_pot,
        street_at_least=_parse_street_filter(street_at_least),
        before_hand_number=before_hand_number,
        after_hand_number=after_hand_number,
    )


@router.get("/hands/{player_name}/{hand_number}")
def hand_detail(player_name: str, hand_number: int):
    hand = get_hand(player_name, hand_number)
    if not hand:
        raise HTTPException(status_code=404, detail="Hand not found")
    return hand


@router.get("/hands/{player_name}/{hand_number}/replay")
def hand_replay(player_name: str, hand_number: int):
    replay = get_replay(player_name, hand_number)
    if not replay:
        raise HTTPException(status_code=404, detail="Hand not found")
    return replay


@router.get("/hands/export")
def hand_export(
    player: str = Query(..., min_length=1),
    fmt: str = Query(default="json", pattern="^(json|jsonl)$"),
    limit: int = Query(default=200, ge=1, le=2000),
    won: Optional[bool] = Query(default=None),
    min_pot: Optional[int] = Query(default=None, ge=0),
    max_pot: Optional[int] = Query(default=None, ge=0),
    street_at_least: Optional[str] = Query(default=None),
):
    """Stream a player's hand history as JSON or JSONL.

    Filters mirror the list endpoint. Files are streamed so we can export large
    histories without loading them all into memory at once on the response
    side.
    """
    records = list_hands(
        player,
        limit=limit,
        reverse=False,
        won=won,
        min_pot=min_pot,
        max_pot=max_pot,
        street_at_least=_parse_street_filter(street_at_least),
    )

    suffix = "jsonl" if fmt == "jsonl" else "json"
    filename = f"{player}_hands.{suffix}"

    def iter_jsonl():
        for record in records:
            yield (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")

    def iter_json():
        buffer = io.StringIO()
        json.dump(records, buffer, ensure_ascii=False)
        yield buffer.getvalue().encode("utf-8")

    media_type = "application/x-ndjson" if fmt == "jsonl" else "application/json"
    iterator = iter_jsonl() if fmt == "jsonl" else iter_json()

    return StreamingResponse(
        iterator,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
