# PyHoldem Pro API Contract

Base URL: `http://localhost:8000`

## Health
- `GET /health`
  - Response: `{ "status": "ok" }`

## Dashboard Summary
- `GET /api/summary?player={name}`
  - Returns the active player, live metrics, training tracks, focus queue, and recent timeline.
- `GET /api/charts/{metric}?player={name}`
  - Returns recorded session trend points for metrics such as `vpip`, `pfr`, `decision_accuracy`, and `aggression_factor`.
- `GET /api/summary/report?player={name}`
  - Returns aggregate playing style, recommendations, performance metrics, and strategy score.

## Players And Bankroll
- `GET /api/players`
- `GET /api/players/{player_name}`
- `GET /api/bankroll/players`
- `POST /api/bankroll/players`
  - Body: `{ "name": "Hero", "bankroll": 10000 }`
- `PATCH /api/bankroll/players/{player_name}`
  - Body: `{ "bankroll": 12000 }`
- `GET /api/bankroll/summary`

## Game Sessions
- `GET /api/games/modes`
  - Returns supported game modes and default config.
- `POST /api/games/sessions`
  - Body: `{ "player_name": "Hero", "game_type": "cash", "limit_type": "no_limit", "opponents": 3 }`
  - Response: `{ "id", "player_name", "game_type", "limit_type", "status", "config" }`
- `GET /api/games/sessions/{session_id}`
- `POST /api/games/sessions/{session_id}/hand/start`
- `GET /api/games/sessions/{session_id}/hand`
- `POST /api/games/sessions/{session_id}/hand/input`
  - Body for menu inputs: `{ "choice": 1 }`
  - Body for number/yes-no inputs: `{ "value": 120 }`
- `POST /api/games/sessions/{session_id}/demo-hand`

## Training
- `GET /api/training/content`
- `GET /api/training/quiz?player={name}&quiz_type=pot_odds`
  - Returns a server-owned `quiz_id`, public question text, quiz type, and difficulty. Correct answers are not returned until evaluation.
- `POST /api/training/quiz/evaluate`
  - Body: `{ "quiz_id": "abc", "player": "Hero", "user_answer": 23, "tolerance": 0.05 }`
  - Returns correctness, feedback, correct answer, explanation, and cumulative quiz stats for the player.
- `GET /api/training/drill?player={name}&focus={weakness}`
  - Returns a server-owned `drill_id`, targeted scenario, public quiz prompt, and curriculum metadata.
- `POST /api/training/drill/evaluate`
  - Body: `{ "drill_id": "abc", "player": "Hero", "user_answer": "call" }`
  - Records the attempt and returns feedback, recommended actions, explanation, and updated progress.
- `GET /api/training/progress?player={name}`
  - Returns quiz/drill attempts, weakness history, mastery progress, and study recommendations. Pending quiz/drill answers are never returned.

## Hand Histories And Replay
- `GET /api/hands?player={name}&limit=50&reverse=true`
- `GET /api/hands/{player_name}/{hand_number}`
- `GET /api/hands/filter?player={name}&winner=hero&min_pot=100`

## Analytics
- `GET /api/stats/sessions?player={name}&limit=20`
  - Returns recorded session rows from the active persistence layer.
- `GET /api/charts/{metric}?player={name}`
  - Supported metrics include `vpip`, `pfr`, `aggression_factor`, `decision_accuracy`, `quiz_accuracy`, `profit`, `hands_played`, and `winrate`.

## WebSocket
- `WS /ws/{session_id}`
  - Sends the same hand-state shape returned by `GET /api/games/sessions/{session_id}/hand` whenever state changes.

## Persistence
- JSON files are the local fallback for players, sessions, and hand histories.
- Set `PYHOLDEM_DB_URL` to use PostgreSQL for persistent players, sessions, and hands.
