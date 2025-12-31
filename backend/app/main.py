from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.paths import ensure_src_path

ensure_src_path()

from app.api.router import api_router

app = FastAPI(title="PyHoldem Pro API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
