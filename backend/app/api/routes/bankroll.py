from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.bankroll_service import create_player, get_summary, list_players, update_bankroll

router = APIRouter()


class BankrollUpdate(BaseModel):
    bankroll: int


class PlayerCreate(BaseModel):
    name: str
    bankroll: int


@router.get("/bankroll/players")
def bankroll_players() -> List[dict]:
    return list_players()


@router.post("/bankroll/players")
def bankroll_create(payload: PlayerCreate) -> dict:
    try:
        return create_player(payload.name, payload.bankroll)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/bankroll/players/{player_name}")
def bankroll_update(player_name: str, payload: BankrollUpdate) -> dict:
    try:
        return update_bankroll(player_name, payload.bankroll)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bankroll/summary")
def bankroll_summary() -> dict:
    return get_summary()
