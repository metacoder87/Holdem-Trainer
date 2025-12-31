# PyHoldem Pro API

FastAPI service wrapper for the game engine in `src/`.

## Run (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload
```

## Notes
- The API will call into the existing engine in `src/` as endpoints are added.
- WebSocket endpoints will stream live game state and training telemetry.
