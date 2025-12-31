# PyHoldem Pro API Contract (Draft)

Base URL: `http://localhost:8000`

## Health
- `GET /health`
  - Response: `{ "status": "ok" }`

## Summary (used by dashboard)
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

## Sessions (planned)
- `POST /api/sessions`
  - Body: `{ player_name, game_type, limit_type, settings }`
  - Response: `{ session_id, status }`
- `GET /api/sessions/{session_id}`
  - Response: `{ session_id, status, current_hand, players, table_state }`
- `POST /api/sessions/{session_id}/actions`
  - Body: `{ action, amount }`
  - Response: `{ accepted, resulting_state }`
- `POST /api/sessions/{session_id}/end`
  - Response: `{ status, summary }`

## Training (planned)
- `GET /api/training/tracks?player={name}`
  - Response: list of tracks with progress + next drill.
- `POST /api/training/drills`
  - Body: `{ player_name, focus_areas, difficulty }`
  - Response: `{ drill_id, scenario }`
- `POST /api/training/quizzes/{quiz_id}/answer`
  - Body: `{ answer }`
  - Response: `{ correct, explanation, next_quiz_id }`

## Analytics (planned)
- `GET /api/analytics/summary?player={name}`
  - Response: `{ vpip, pfr, aggression_factor, decision_accuracy, trends }`
- `GET /api/analytics/leaks?player={name}`
  - Response: list of detected leaks with severity and recommended drills.

## Hand histories (planned)
- `GET /api/hands?player={name}&limit=50`
  - Response: list of hand summaries.
- `GET /api/hands/{hand_id}`
  - Response: full hand history + decision points.
- `GET /api/hands/{hand_id}/replay`
  - Response: ordered events for replay UI.

## WebSocket (planned)
- `WS /ws/sessions/{session_id}`
  - Events: `state_update`, `action_result`, `hand_complete`.
- `WS /ws/training/{player_name}`
  - Events: `drill_update`, `quiz_result`, `performance_snapshot`.
