# PyHoldem Pro

PyHoldem Pro is a terminal-based Texas Hold’em poker game and training platform. It includes cash games and tournaments, multiple AI styles, a training HUD, in-game quizzes, post-hand feedback, persistent player profiles, and replayable hand histories.

## Status

- Core gameplay and rules engine implemented (cash + tournament, limit + no-limit)
- Training experience integrated (HUD, quizzes, post-hand feedback, adaptive session menu)
- Hand history persistence + replay implemented (per-player JSONL histories)
- Decision-point capture + grading implemented (stored per hand and summarized per session)
- Test suite: 358 passing tests

## Features

### Gameplay

- Cash games and tournaments
- No-limit and fixed-limit betting
- 2–9 handed tables (1 human + AI opponents)
- Side pots and all-in handling
- Realistic tournament structure (blind levels, antes, eliminations, payouts)

### Betting correctness

- No-limit minimum raise sizing (tracks last full raise size)
- Non-full all-in raises do not reopen betting
- Fixed-limit street bet sizing and raise cap (max 4 bets per round)

### AI opponents

- Multiple AI styles (cautious, wild, balanced, random)

### Training and analytics

- Optional in-game training:
  - Pot-odds quizzes at decision points
  - HUD with opponent stats (VPIP/PFR/AF), pot odds, and equity/outs overlays
  - Post-hand feedback summaries
- Session tracking (VPIP, PFR, aggression factor, quiz accuracy, decision accuracy)
- Training Session mode with:
  - Personalized drills and scenarios (from identified weaknesses)
  - Session review and career report
  - Recent hand review + replay

### Persistence

- Player profiles stored in `data/players.json`
- Per-player hand histories stored as JSONL in `data/hand_histories/`
- Recent hands are also cached into player profiles for quick access

## Requirements

- Python 3.8+

Dependencies are listed in `requirements.txt` (Rich, jsonschema). Dev/test tools are in `requirements-dev.txt`.

## Quick start with Docker (recommended)

The whole stack (FastAPI backend + React frontend) runs with a single command:

```bash
docker compose up --build
```

Then open <http://localhost:5173>. The frontend talks to the API on
<http://localhost:8000>. Player data + hand histories persist in the
`pyholdem-data` Docker volume between runs.

To stop:

```bash
docker compose down
```

To wipe persisted data:

```bash
docker compose down -v
```

## Install (without Docker)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
```

For development and testing:

```bash
pip install -r requirements-dev.txt
```

## Run

```bash
python main.py
```

Optional demos:

```bash
python scripts/simple_demo.py
python scripts/training_demo.py
python scripts/demo.py
```

## Web API (FastAPI)

The API wraps the core engine for UI consumption (summary, training content, bankroll, demo hands).
See `docs/api-contract.md` for the full contract.

Run the API:

```bash
pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload
```

Useful endpoints:
- `GET /health`
- `GET /api/summary`, `GET /api/players`
- `GET /api/bankroll/players`, `POST /api/bankroll/players`, `PATCH /api/bankroll/players/{player_name}`
- `GET /api/games/modes`, `POST /api/games/sessions`, `POST /api/games/sessions/{session_id}/demo-hand`
- `GET /api/games/sessions/{session_id}/hand`, `POST /api/games/sessions/{session_id}/hand/start`, `POST /api/games/sessions/{session_id}/hand/input`
- `GET /api/training/content`, `GET /api/training/tracks`, `GET /api/training/quiz`, `POST /api/training/quiz/evaluate`
- `POST /api/training/drills`, `POST /api/training/drills/answer`, `GET /api/training/drills/focus-areas`
- `GET /api/analytics/summary`, `GET /api/analytics/leaks`
- `GET /api/hands`, `GET /api/hands/export`, `GET /api/hands/{player}/{n}`, `GET /api/hands/{player}/{n}/replay`
- `WS /ws/sessions/{session_id}` (live state stream)

Environment variables:
- `PYHOLDEM_DATA_FILE` - override the JSON data file location
- `PYHOLDEM_CORS_ORIGINS` - comma-separated allowed origins (default `http://localhost:5173`)
- `PYHOLDEM_SESSION_LIMIT` (default 64) and `PYHOLDEM_SESSION_TTL_SECONDS` (default 3600) - bound the in-memory session store

## Frontend (React)

The web UI lives in `frontend/` and consumes the FastAPI endpoints.
See `frontend/README.md` for details.

```bash
cd frontend
npm install
npm run dev
```

If the API is not on `http://localhost:8000`, set `VITE_API_URL` in `frontend/.env`.

## How to use

1. Create or select a player profile
2. Choose a mode:
   - Cash Game
   - Tournament
   - Training Session (standalone drills and reviews)
3. For Cash/Tournament, optionally enable training:
   - In-game quizzes
   - HUD
   - Post-hand feedback
4. Play hands and review results

### Hand history replay

Go to `Training Session` → `Review Recent Hands` and select:

- Quick view (prints the full hand)
- Replay (street-by-street, including decision grades when available)

### Educational content

The Training Session menu includes an option to export default study materials into `educational_content/`.

## Data files

- Player profiles: `data/players.json`
- Hand histories (JSONL): `data/hand_histories/*.jsonl`

If you want a clean slate, delete those files/directories (or back them up first).

## Testing

Backend (Python):

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Frontend (Vitest + jsdom):

```bash
cd frontend
npm install
npm test          # one-shot
npm run test:watch
npm run typecheck
```

Or use the Makefile (`make test`) for the backend suite.

## Project layout

- `src/game/`: engine, rules, AI, table, pot, hand evaluation
- `src/stats/`: session tracking and odds/stat calculators
- `src/training/`: HUD, analyzers, adaptive training, replay tools
- `src/data/`: player persistence and hand-history storage
- `src/ui/`: terminal display and input handling
- `scripts/`: demos and manual test scripts
- `tests/`: unit + integration tests

## Roadmap

See `docs/ROADMAP.md` for actionable phases, deliverables, and acceptance criteria.

## Disclaimer

This project is for education and practice. It is not intended for real-money play.

## Contributing

- Keep changes focused and add/update tests when modifying behavior.
- Run `python -m pytest -q` (or `make test`) before opening a PR.

## License

A license file is not currently included in this repository. If you plan to redistribute, add an explicit license first.
