# PyHoldem Pro API Contract

Base URL: `http://localhost:8000`

This documents the **implemented** REST + WebSocket surface as of the current
main branch. Endpoints listed below are wired and reachable.

## Health

- `GET /health` → `{ "status": "ok" }`
- `GET /` → small service descriptor

## Summary (dashboard)

- `GET /api/summary?player={name}` → `SummaryResponse` (live metrics, training
  tracks, focus queue, timeline)
- `GET /api/charts/{metric}?player={name}` → `[{ label, value }, ...]` for a
  single metric across the player's recent sessions
- `GET /api/summary/report?player={name}` → playing-style classification,
  recommendations, strategy score

> The chart and report endpoints currently live under the summary router; the
> analytics router below exposes additional reports.

## Players

- `GET /api/players` → list of `{ name, bankroll, last_played, skill_level }`
- `GET /api/players/{name}` → adds `sessions`, `last_session`

## Bankroll

- `GET /api/bankroll/players`
- `POST /api/bankroll/players` — body `{ name, bankroll }`
- `PATCH /api/bankroll/players/{player_name}` — body `{ bankroll }`
- `GET /api/bankroll/summary` → `{ total_players, total_bankroll, total_games_played }`

## Game sessions (live gameplay)

The CLI engine is wrapped in a threaded session that surfaces blocking input
prompts as `pending_input` payloads. Tournaments are auto-settled when the
hero is eliminated or wins; the chip stack is converted back to cash.

- `GET /api/games/modes` — registered cash + tournament modes
- `POST /api/games/sessions` — body `SessionCreate` → `GameSession`
- `GET /api/games/sessions/{session_id}` → `GameSession`
- `POST /api/games/sessions/{session_id}/hand/start` → `GameHandState`
- `GET /api/games/sessions/{session_id}/hand` → `GameHandState`
- `POST /api/games/sessions/{session_id}/hand/input` — body
  `{ choice?: int, value?: any }` (exactly one) → `GameHandState`
- `POST /api/games/sessions/{session_id}/demo-hand` — auto-plays one hand to
  completion (hero auto-checks/calls)

`GameHandState`:

```json
{
  "session_id": "abc",
  "status": "in_hand | awaiting_input | hand_complete | game_over | error | idle",
  "state": {
    "game_state": "...", "community_cards": [...], "pot_size": 0,
    "players": [...], "blinds": {...}, "hero_cards": [...], "hero_name": "...",
    "hero_bankroll": 0, "hand_number": 0, "game_over_reason": null
  },
  "pending_input": { "kind": "menu|number|yes_no", "prompt": "...", "options": [...], "min_value": 0, "max_value": 0, "integer_only": false },
  "input_error": null,
  "last_hand": { ...HandHistory },
  "terminal_reason": null,
  "error": null
}
```

## Training

All quiz/drill endpoints use **server-owned IDs**: the server keeps the
correct answer privately on the player's `training_progress`, so clients
never see it until after grading.

- `GET /api/training/content` → tips, vocabulary, strategy guides, cheat sheets
- `GET /api/training/quiz?quiz_type=...&player=...&pot_size=...&bet_to_call=...`
  → `{ quiz_id, player, type, question, difficulty }`
- `POST /api/training/quiz/evaluate` — body `{ quiz_id, player?, user_answer, tolerance? }`
  → `QuizEvaluation` (and persists the attempt to `quiz_attempts`)
- `GET /api/training/drill?player=...&focus=...` → `{ drill_id, focus_area, scenario, quiz, configuration, curriculum }`
- `POST /api/training/drill/evaluate` — body `{ drill_id, player?, user_answer }`
  → `DrillEvaluation` (and persists the attempt to `drill_attempts`)
- `GET /api/training/progress?player=...` → quiz_attempts, drill_attempts,
  weakness_history, mastery_progress, study_recommendations, quiz_stats,
  drill_stats

## Analytics

- `GET /api/stats/sessions?player={name}&limit=20` → recent session rows
- `GET /api/analytics/career?player={name}` → CareerTracker aggregates +
  milestones
- `GET /api/analytics/sessions/latest?player={name}` → SessionReviewer report
  for the most recent session
- `GET /api/analytics/sessions/{idx}?player={name}` → SessionReviewer report
  for a specific session index

## Hand history

- `GET /api/hands?player={name}&limit=50&reverse=true` → list of `HandHistory`
- `GET /api/hands/filter?player={name}&winner=...&min_pot=...&street=...&decision_quality=...&weakness=...&session_id=...&game_type=...&limit=50`
  → filtered list (note: `/filter` is declared before `/{name}/{n}` so it
  resolves correctly)
- `GET /api/hands/{player_name}/{hand_number}` → full `HandHistory`

## WebSocket

- `WS /ws/sessions/{session_id}`
  - On connect the server sends an initial `GameHandState` snapshot.
  - The server polls `_build_hand_response` on a short interval (env-tunable
    via `PYHOLDEM_WS_POLL_INTERVAL`, default `0.1s`) and pushes a fresh
    snapshot only when the relevant state changes (status, pending input,
    last hand, terminal reason, error).
  - Clients can send commands as JSON:
    - `{ "action": "start" }` — start the next hand
    - `{ "action": "input", "value": <int|string|bool> }` — answer the
      pending prompt (or `"choice"` for menu options)
    - `{ "action": "snapshot" }` — request a fresh snapshot immediately
  - Errors are returned inline as `{ "error": "..." }`.
  - Closes with code `4404` if the session id is unknown.

## Environment

- `PYHOLDEM_DATA_FILE` — JSON store path (default `data/players.json`)
- `PYHOLDEM_DB_URL` or `DATABASE_URL` — opt-in PostgreSQL persistence
- `PYHOLDEM_USE_DB` — set to `1`/`true` to also enable Postgres when only
  `DATABASE_URL` is set
- `PYHOLDEM_CORS_ORIGINS` — comma-separated allow-list (default
  `http://localhost:5173,http://127.0.0.1:5173`)
- `PYHOLDEM_SESSION_TTL_SECONDS` — idle session eviction (default `14400`)
- `PYHOLDEM_WS_POLL_INTERVAL` — WS push poll interval seconds (default `0.1`)

## Not yet implemented

- Auth / guest tokens
- DB-backed analytics aggregates / scheduled jobs
- Hand history export endpoint (only list/filter/detail today)
- `/ws/training/{player_name}` (training-only stream)
