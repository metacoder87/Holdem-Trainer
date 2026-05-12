from fastapi import APIRouter

from app.core.paths import ensure_src_path

ensure_src_path()

from app.api.routes import health, summary, players, training, bankroll, games, hands, ws, analytics

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(summary.router, prefix="/api", tags=["summary"])
api_router.include_router(players.router, prefix="/api", tags=["players"])
api_router.include_router(training.router, prefix="/api", tags=["training"])
api_router.include_router(bankroll.router, prefix="/api", tags=["bankroll"])
api_router.include_router(games.router, prefix="/api", tags=["games"])
api_router.include_router(hands.router, prefix="/api", tags=["hands"])
api_router.include_router(analytics.router, prefix="/api", tags=["analytics"])
api_router.include_router(ws.router, tags=["websockets"])
