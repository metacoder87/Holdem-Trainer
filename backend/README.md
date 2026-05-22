# PyHoldem Pro API

FastAPI service wrapper for the game engine in `src/`.

## Run (dev)

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
py -3 -m pip install -r requirements-dev.txt
PYTHONPATH=backend uvicorn app.main:app --reload
```

On Windows systems where `python` points at the Microsoft Store alias, use `py -3 -m pip ...` and `py -3 -m uvicorn app.main:app --reload` instead.

## CORS

Development origins default to `http://localhost:5173,http://127.0.0.1:5173`.
Set `PYHOLDEM_CORS_ORIGINS` to a comma-separated list for other frontend hosts.

## PostgreSQL

Set `PYHOLDEM_DB_URL` to use PostgreSQL instead of JSON files:

```bash
export PYHOLDEM_DB_URL="postgresql://user:password@localhost:5432/pyholdem"
```

To migrate existing JSON data:

```bash
python scripts/migrate_json_to_db.py --db-url "$PYHOLDEM_DB_URL"
```

## Notes
- The API wraps the existing engine in `src/` for gameplay, training, replay, bankroll, and analytics.
- Training quizzes and drills are server-owned: clients receive IDs and public prompts, then submit answers for backend grading.
- WebSocket endpoints stream live game state; browser-native HUD overlays are still partial.
