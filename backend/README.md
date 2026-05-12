# PyHoldem Pro API

FastAPI service wrapper for the game engine in `src/`.

## Run (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
- The API will call into the existing engine in `src/` as endpoints are added.
- WebSocket endpoints will stream live game state and training telemetry.
