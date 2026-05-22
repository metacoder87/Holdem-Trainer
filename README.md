# PyHoldem Pro

PyHoldem Pro is a terminal-based Texas Hold’em poker game and training platform. It includes cash games and tournaments, multiple AI styles, a training HUD, in-game quizzes, post-hand feedback, persistent player profiles, and replayable hand histories.

## Status

- Core gameplay and rules engine implemented (cash + tournament, limit + no-limit)
- Training experience integrated (HUD, server-owned quizzes, post-hand feedback, adaptive session menu)
- Hand history persistence + replay implemented (per-player JSONL histories)
- Decision-point capture + grading implemented (stored per hand and summarized per session)
- Web training progress stores quiz/drill attempts per player profile
- Test suite: 372 passing Python tests plus frontend Vitest coverage

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
  - Server-graded quiz and drill attempts persisted to the active player
  - Session review and career report
  - Recent hand review + replay

### Persistence

- Player profiles stored in `data/players.json`
- Per-player hand histories stored as JSONL in `data/hand_histories/`
- Recent hands are also cached into player profiles for quick access

### PostgreSQL (optional)

Set `PYHOLDEM_DB_URL` to use PostgreSQL for persistence instead of JSON files.

Example:

```bash
export PYHOLDEM_DB_URL="postgresql://user:password@localhost:5432/pyholdem"
```

To migrate existing JSON data:

```bash
python scripts/migrate_json_to_db.py --db-url "$PYHOLDEM_DB_URL"
```

## Requirements

- Python 3.8+

Runtime dependencies are listed in `requirements.txt` and backend service dependencies are listed in `backend/requirements.txt`. Dev/test installs should use `requirements-dev.txt`, which includes both.

## Install

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
```

For development and testing:

```bash
py -3 -m pip install -r requirements-dev.txt
```

## Run CLI Application

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
- `GET /api/summary`
- `GET /api/training/content`
- `GET /api/training/quiz`
- `POST /api/training/quiz/evaluate`
- `GET /api/training/drill`
- `POST /api/training/drill/evaluate`
- `GET /api/training/progress`
- `GET /api/bankroll/players`
- `POST /api/bankroll/players`
- `PATCH /api/bankroll/players/{player_name}`
- `GET /api/games/modes`
- `POST /api/games/sessions`
- `GET /api/games/sessions/{session_id}`
- `POST /api/games/sessions/{session_id}/hand/start`
- `POST /api/games/sessions/{session_id}/hand/input`
- `WS /ws/sessions/{session_id}`
- `POST /api/games/sessions/{session_id}/demo-hand`

## Frontend (React)

The web UI lives in `frontend/` and consumes the FastAPI endpoints.
See `frontend/README.md` for details.

```bash
cd frontend
npm install
npm run dev
```

If the API is not on `http://localhost:8000`, set `VITE_API_URL` in `frontend/.env`.
The API allows `http://localhost:5173` and `http://127.0.0.1:5173` by default; override with `PYHOLDEM_CORS_ORIGINS` for other frontend hosts.

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
4. Play hands, complete drills/quizzes, and review results

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

Run the full test suite:

```bash
py -3 -m pip install -r requirements-dev.txt
python -m pytest -q
```
On Windows systems where `python` is the Microsoft Store alias, use `py -3 -m pytest -q`.

Or use the Makefile:

```bash
make test
```

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
