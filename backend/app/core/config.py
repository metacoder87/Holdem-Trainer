import os
from typing import List

class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5435/holdem_trainer"
    )
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "PYHOLDEM_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    WS_POLL_INTERVAL_SECONDS: float = float(os.getenv("PYHOLDEM_WS_POLL_INTERVAL", "0.1"))
    SESSION_TTL_SECONDS: int = int(os.getenv("PYHOLDEM_SESSION_TTL_SECONDS", "14400"))

settings = Settings()
