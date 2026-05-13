# PyHoldem Pro API Contract

Base URL: `http://localhost:8000`

This documents the **implemented** REST surface. WebSocket support is a future
phase (see [ROADMAP.md](ROADMAP.md)).

## Health
- `GET /health`
  - Response: `{ "status": "ok" }`

## Summary (dashboard)
- `GET /api/summary?player={name}`
  - Response:
    ```json
    {
      "player": { "name": "Jon", "skill_level": "beginner", "last_played": "2025-12-26T11:20:44.019846" },
      "live_metrics": [{ "label": "VPIP", "value": "23%", "delta": "+2%", "tone": "good" }],
      "training_tracks": [{ "title": "Preflop Mastery", "summary": "...", "cadence": "Daily drills", "intensity": "Core", "progress": 62 }],
      "focus_queue": ["Position-based range review"],
      "timeline": [{ "time": "10:12", "label": "Hand 42", "detail": "Missed thin value spot" }]
    }
    ```

## Players
- `GET /api/players`
  - Response: list of `{ name, bankroll, last_played, skill_level }`
- `GET /api/players/{player_name}`
  - Response: `{ name, bankroll, last_played, skill_level, sessions, last_session }`

## Bankroll
- `GET /api/bankroll/players` - list of `{ name, bankroll, last_played, skill_level }`
- `POST /api/bankroll/players` - body `{ name, bankroll }`
- `PATCH /api/bankroll/players/{player_name}` - body `{ bankroll }`
- `GET /api/bankroll/summary` - `{ total_players, total_bankroll, total_games_played }`

## Game sessions (live gameplay)
The CLI engine is wrapped in a threaded session that surfaces blocking input
prompts as `pending_input` payloads. Tournaments are auto-finalized when the
hero is eliminated or wins, and the chip stack is converted back to cash.

- `GET /api/games/modes` - registered cash + tournament modes
- `POST /api/games/sessions`
  - Body: `{ player_name, game_type, limit_type, small_blind, big_blind, opponents, buy_in?, starting_chips? }`
  - Response: `{ id, player_name, game_type, limit_type, status, config }`
- `GET /api/games/sessions/{session_id}` - session metadata
- `POST /api/games/sessions/{session_id}/hand/start`
  - Response: `GameHandState`
- `GET /api/games/sessions/{session_id}/hand`
  - Response: `GameHandState`
- `POST /api/games/sessions/{session_id}/hand/input`
  - Body: `{ choice?: int, value?: any }` (one of)
  - Response: `GameHandState`
- `POST /api/games/sessions/{session_id}/demo-hand`
  - Auto-plays one hand to completion (hero auto-checks/calls).

`GameHandState`:
```json
{
  "session_id": "abc",
  "status": "in_hand | awaiting_input | hand_complete | tournament_complete | error | idle",
  "state": {
    "game_state": "...", "community_cards": [...], "pot_size": 0,
    "players": [...], "blinds": {...}, "hero_cards": [...], "hero_name": "...",
    "hero_bankroll": 0, "hand_number": 0
  },
  "pending_input": { "kind": "menu|number|yes_no", "prompt": "...", "options": [...], "min_value": 0, "max_value": 0, "integer_only": false },
  "input_error": null,
  "last_hand": { ...HandHistory },
  "error": null,
  "tournament_result": { "result": "won|lost|forfeit", "final_bankroll": 0, "chip_stack_at_end": 0 }
}
```

## Training
- `GET /api/training/content` - `{ tips, vocabulary, strategy_guides, cheat_sheets }`
- `GET /api/training/tracks?player={name}` - `{ player, training_tracks, focus_queue }`
- `GET /api/training/quiz?quiz_type=pot_odds&pot_size=...&bet_to_call=...`
  - Returns a quiz with `correct_answer`, `question`, `explanation`, `difficulty`.
- `POST /api/training/quiz/evaluate`
  - Body: `{ correct_answer, user_answer, tolerance? }`
  - Response: `{ correct, feedback, performance_stats }`
- `GET /api/training/drills/focus-areas` - list of `{ id, label }` weakness types the drill engine supports.
- `POST /api/training/drills`
  - Body: `{ player_name?, focus_area?, difficulty? }`
  - Picks `focus_area` from the player's identified weaknesses if omitted.
  - Response: `{ drill_id, kind, scenario, options, correct_action, context, difficulty, focus_area }`. The scenario is fully reproducible from `drill_id` alone (re-POST with the same id to get the same drill).
- `POST /api/training/drills/answer`
  - Body: `{ drill_id, kind, correct_action, user_answer, player_name?, focus_area? }`
  - When `player_name` is supplied the result is appended to that player's `practice_history` and `practice_stats` is updated.
  - Response: `{ drill_id, kind, correct, user_answer, correct_action, feedback, persisted, persist_error? }`

## Analytics
- `GET /api/analytics/summary?player={name}`
  - Response: `{ player, metrics: { vpip, pfr, aggression_factor, decision_accuracy, ... }, session_count, trends: { vpip: [...], pfr: [...], aggression_factor: [...], decision_accuracy: [...], profit: [...] } }`
- `GET /api/analytics/leaks?player={name}`
  - Response: `{ player, leaks: [{ id, title, severity, fix }], recommended_topics }`

## Hand history
- `GET /api/hands?player={name}&limit=50&reverse=true`
  - Filter params: `won` (bool), `min_pot`, `max_pot`, `street_at_least` (`preflop|flop|turn|river`).
  - Cursor pagination: pass `before_hand_number=<last_hand_number>` (newest-first) or `after_hand_number=<last_hand_number>` (oldest-first) from the last item of the previous page.
  - Response: list of `HandHistory` records (newest-first by default).
- `GET /api/hands/export?player={name}&fmt=json|jsonl`
  - Streams the (filtered) history as a download. Same filter params as `/api/hands`.
- `GET /api/hands/{player_name}/{hand_number}`
  - Response: full `HandHistory`.
- `GET /api/hands/{player_name}/{hand_number}/replay`
  - Response: ordered replay payload:
    ```json
    {
      "hand_number": 1, "started_at": "...", "ended_at": "...",
      "hero_hole_cards": ["Ah","Kd"], "winners": ["Jon"], "pot_total": 240,
      "meta": {...},
      "summary": { "small_blind": 5, "big_blind": 10, "ante": 0, "blind_level": 1, "game_type": "cash", "limit_type": "no_limit", "hero_won": true },
      "streets": [
        { "name": "preflop", "board": [], "actions": [...], "decisions": [...] },
        { "name": "flop", "board": ["2c","7d","Ts"], "actions": [...], "decisions": [...] }
      ]
    }
    ```

## WebSocket

- `WS /ws/sessions/{session_id}`
  - On connect the server sends an initial `GameHandState` snapshot.
  - The server pushes a fresh snapshot whenever the engine transitions state
    (pending input changes, hand completes, tournament settles, etc.).
  - Clients can send commands as JSON:
    - `{ "action": "start" }` — start the next hand
    - `{ "action": "input", "value": <int|string|bool> }` — answer the pending prompt
    - `{ "action": "snapshot" }` — request a fresh snapshot immediately
  - Errors are returned inline as `{ "error": "..." }`.
  - Closes with code `4404` if the session id is unknown.

## Not yet implemented
- `WS /ws/training/{player_name}`
- Auth / guest tokens
- DB-backed analytics aggregates / scheduled jobs

## CORS
The dev server allows `http://localhost:5173` by default. Set `PYHOLDEM_CORS_ORIGINS`
to a comma-separated list of origins for non-dev environments.

## Session limits
The in-memory `SESSIONS` registry is bounded by `PYHOLDEM_SESSION_LIMIT` (default 64)
and `PYHOLDEM_SESSION_TTL_SECONDS` (default 3600). Active threads are never evicted.
