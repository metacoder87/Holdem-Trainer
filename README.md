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

## Install

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

Run the full test suite:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

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

## Roadmap (planned / high-value)

1. Deeper decision grading:
   - Bet sizing feedback (street-aware sizing, SPR-based guidance)
   - Preflop ranges by position (open/call/3-bet/fold)
   - Multi-street planning feedback (barrel frequencies, value vs bluff)
2. Equity training upgrades:
   - Range-vs-range equity (Monte Carlo where needed)
   - Multiway equity and “clean outs” explanations
   - Board texture and blocker-aware tips
3. Hand history tooling:
   - Search/filter by spot, opponent type, or mistakes
   - Export to common hand-history formats (for external analysis)
4. AI improvements:
   - Strategy/range-based decision logic
   - Opponent adaptation and exploit training
5. Tournament depth:
   - More payout structures, configurable levels, and multi-table support
6. UX polish:
   - Better replay UI, summaries, and training prompts
   - Config file support for defaults (blinds, training toggles, etc.)

## Disclaimer

This project is for education and practice. It is not intended for real-money play.

## Contributing

- Keep changes focused and add/update tests when modifying behavior.
- Run `python -m pytest -q` (or `make test`) before opening a PR.

## License

A license file is not currently included in this repository. If you plan to redistribute, add an explicit license first.
