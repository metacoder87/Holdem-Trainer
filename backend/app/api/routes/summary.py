from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.summary import SummaryResponse
from app.services.summary_service import build_summary

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def get_summary(player: Optional[str] = Query(default=None)) -> SummaryResponse:
    return SummaryResponse(**build_summary(player))
