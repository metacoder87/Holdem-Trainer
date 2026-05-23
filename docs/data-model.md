# Data Model & Migration Strategy

This document details the database schema, file-system storage layout, and the migration strategy for player profiles and hand histories in PyHoldem Pro.

---

## 1. Storage Layers

The platform supports dual-mode persistence controlled via environment variables:

1. **Local JSON Database (Default):** High-portability, single-file player store and per-player JSONL hand history logs.
2. **PostgreSQL Database (Enterprise Mode):** Triggered when `PYHOLDEM_DB_URL` is set, executing ORM operations using SQLAlchemy.

---

## 2. Player Profile Data Model

### 2.1 JSON Schema (`data/players.json`)
The root object is a dictionary keyed by the player's name:
```json
{
  "PlayerName": {
    "name": "PlayerName",
    "bankroll": 10000,
    "skill_level": "intermediate",
    "created_at": "2026-05-23T00:00:00Z",
    "last_played": "2026-05-23T02:00:00Z",
    "weaknesses": ["too_passive", "poor_pot_odds"],
    "recommended_topics": ["value_betting", "pot_odds_calculation"],
    "sessions": [
      {
        "id": "session_uuid",
        "game_type": "cash",
        "hands_played": 120,
        "profit": 450,
        "vpip": 0.22,
        "pfr": 0.17,
        "aggression_factor": 2.2,
        "decision_accuracy": 0.78,
        "quiz_accuracy": 0.85,
        "started_at": "...",
        "ended_at": "..."
      }
    ],
    "training_progress": {
      "schema_version": 1,
      "quiz_attempts": [],
      "drill_attempts": [],
      "weakness_history": {},
      "mastery_progress": {}
    }
  }
}
```

### 2.2 SQL Relational Schema (PostgreSQL)
Mapping is handled via `backend/app/models.py` (SQLAlchemy):
- **`players` Table:**
  - `id` (UUID, Primary Key)
  - `name` (String, Unique, Index)
  - `bankroll` (Integer)
  - `skill_level` (String)
  - `created_at` (Timestamp)
  - `last_played` (Timestamp)
- **`sessions` Table:**
  - `id` (UUID, Primary Key)
  - `player_id` (ForeignKey reference to `players.id`)
  - `game_type` (String)
  - `hands_played` (Integer)
  - `net_result` (Integer)
  - `vpip` (Float), `pfr` (Float), `aggression_factor` (Float)
  - `decision_accuracy` (Float), `quiz_accuracy` (Float)

---

## 3. Hand History Data Model

Hand histories are appended sequentially as JSON Lines (JSONL) files in `data/hand_histories/{player_name}.jsonl`.

### 3.1 Structure of a Hand Record
```json
{
  "hand_number": 42,
  "session_id": "session_uuid",
  "meta": {
    "game_type": "cash",
    "limit_type": "no_limit",
    "small_blind": 50,
    "big_blind": 100,
    "hero_name": "Hero",
    "hero_position": 0
  },
  "community_cards": ["Qs", "Jh", "2d", "9s", "4h"],
  "winner": "Hero",
  "won_by_fold": false,
  "pot_total": 38000,
  "action_log": [
    {
      "round": "preflop",
      "player": "Hero",
      "action": "raise",
      "amount": 300,
      "is_aggressive_intent": true
    }
  ],
  "decision_points": [
    {
      "betting_round": "flop",
      "pot_total": 600,
      "to_call": 200,
      "hero_hole_cards": ["Ah", "Ad"],
      "board": ["Qs", "Jh", "2d"],
      "chosen_action": "call",
      "recommended_action": "call",
      "quality": "optimal",
      "equity": 0.82,
      "required_equity": 0.25,
      "ev_loss_bb": 0.0,
      "ev_loss_chips": 0.0
    }
  ]
}
```

---

## 4. Migration Strategy (JSON to PostgreSQL)

When transitioning to a hosted PostgreSQL deployment, the system executes migrations in two steps:

### Step 4.1: SQL Schema Initialization
SQL schemas are managed via Alembic. To initialize or update a database deployment to the latest schema:
```bash
cd backend
alembic upgrade head
```

### Step 4.2: Data Import Script
We provide a standalone utility script to parse local JSON databases and import them cleanly into Postgres tables:
```bash
python scripts/migrate_json_to_db.py --db-url "postgresql://user:password@localhost:5432/holdem_trainer"
```
The script:
1. Reads `data/players.json`.
2. Creates database records for players and their associated sessions.
3. Loads `.jsonl` files in `data/hand_histories/` and populates the sql database equivalent tables, resolving foreign keys.
