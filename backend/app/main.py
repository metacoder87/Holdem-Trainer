import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.paths import ensure_src_path

ensure_src_path()


# The engine prints status messages with emojis (dice, chip stacks, trophies,
# etc.). On Windows the console default is cp1252, which can't encode those
# characters - the resulting UnicodeEncodeError used to bubble out of
# play_hand() and kill the hand thread, leaving the UI stuck on "betting
# stops but no money changes hands". Force the API process's stdout/stderr
# to utf-8 with replacement so prints never crash a hand.
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            # Preserve immediate output by enabling line_buffering.
            # Without this, reconfigure strips the effect of PYTHONUNBUFFERED=1
            # when stdout is not a TTY (like in Docker).
            reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (OSError, ValueError):
            pass


from app.api.router import api_router
from app.observability import init_observability

app = FastAPI(title="PyHoldem Pro API", version="0.1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observability must run *after* CORS so the OPTIONS preflight
# doesn't get counted as traffic. Routes are still attached below.
init_observability(app)

app.include_router(api_router)
