# PyHoldem Pro - Plan for Completion

This document provides a comprehensive review of the PyHoldem Pro codebase, summarizing what is currently implemented, identifying active bugs that need fixing, and detailing the remaining features required for project completion.

---

## 1. Project Status & Completed Features

PyHoldem Pro is a feature-rich, high-performance Texas Hold'em poker trainer. The core infrastructure is highly robust, and the test suite verifies correctness across 630+ unit and integration tests.

### 1.1 Core Gameplay & Rules Engine
- **Game Modes:** Support for cash games and single-table tournament structures.
- **Betting Sizing correctness:** 
  - **No-Limit:** Tracks last full raise sizes, computes legal minimum raise thresholds, and enforces that non-full all-ins do not reopen the betting action.
  - **Fixed-Limit:** Enforces fixed bets by street and caps the maximum number of raises per street to 4.
- **Table Dynamics:** Scalable 2–9 handed tables (1 human player and AI opponents) with dealer button rotation, blinds, antes, side pots, and all-in distribution.

### 1.2 Interactive Training & Drills
- **Real-Time Quizzes:** Generates server-graded quizzes at critical decision points during gameplay (Pot Odds, Implied Odds, Bet Sizing, and Required Equity with Fold Equity adjustment).
- **HUD (Heads-Up Display):** Terminal-based rich stats (VPIP, PFR, Aggression Factor) and outs/equity overlays.
- **Drill Engine:** Stateless scenario generator with Bandit Thompson sampling and Elo-rating systems in the `adaptive_engine` to recommend drills targeting a player's weaknesses.
- **Seeded Drills:** The ability to replay and practice a specific hand/decision point directly from the replay vault.

### 1.3 Analytical Services
- **Bayesian Analytics:** VPIP, PFR, and Aggression Factor computed with Bayesian credible intervals.
- **Leak Radar:** Scans historical hands to detect playing style archetypes (e.g., tight/loose, passive/aggressive) and list strategic leaks.
- **EV Leak Lab:** Measures expected value (EV) loss in big blinds for each decision point and groups them by street, position, and action.
- **Regret Heatmap:** A visual density matrix displaying EV loss grouped by street, position, and stack-to-pot ratio (SPR).
- **Variance Panel:** Realized vs. EV profit lines, Standard Deviation, Kelly criterion, Risk of Ruin, and all-in luck delta.
- **ICM Panel:** Textbook Malmuth-Harville Independent Chip Model (ICM) calculator for tournament stack equities, risk premiums, and bubble factors.
- **Range Equity Tool:** Monte Carlo range-vs-range preflop and postflop equity calculators with suit removal and blockers.

### 1.4 Database & Persistence
- **JSON Engine:** Stored player profiles (`data/players.json`) and player hand histories (`data/hand_histories/*.jsonl`).
- **PostgreSQL Engine:** SQL database backend (SQLAlchemy + Alembic migrations) as an alternative to JSON.

---

## 2. Active Bugs Needing Fixes

The following bugs exist in the current main branch and must be resolved before release:

### 2.1 Skill Level & Weakness Detection Overwriting (Bug 1.3)
- **Problem:** `GameEngine._finalize_and_persist_session` passes the progression analyzer the *latest session's* metrics rather than the aggregate historical averages. A short 12-hand session can flip a 5000-hand player's skill level from "advanced" to "beginner".
- **Fix:** Update `_finalize_and_persist_session` in `src/game/game_engine.py` to calculate VPIP, PFR, and Aggression Factor weighted by `hands_played` over all sessions in the player's history before feeding them to the progression analyzer.

### 2.2 Career Analytics Discrepancy (Bug 1.7)
- **Problem:** While `CareerTracker` is used in the CLI, the React web dashboard relies on a custom `_aggregate_metrics` calculation that does not deduplicate sessions and double-counts hands if `sessions` and `last_session` coexist in the database.
- **Fix:** Route all career-related analytics in the API to utilize `CareerTracker` directly.

---

## 3. Outstanding / Unfinished Features

To reach "master-level" coverage, the following features need to be completed:

### 3.1 Session Authentication / Guest Tokens (Phase 1)
- **Status:** Empty placeholders exist in the API router.
- **Requirement:** Secure session routes via JWT tokens or light profile sessions so multiple players on different browsers do not collide.

### 3.2 Scheduled Background Analytics Jobs (Phase 2)
- **Status:** Unimplemented.
- **Requirement:** Monte Carlo range computations and heavy multiway hands-history aggregations are currently run synchronously, which can block the FastAPI event loop under heavy loads. Introduce a worker interface (Celery or RQ) to compute heavy metrics asynchronously.

### 3.3 Curriculum Runner & Weekly Study Plan (Phase 5 / Section 4.3)
- **Status:** `AdaptiveTrainer.generate_personalized_curriculum` generates curriculum objects, but there is no API endpoint to run/persist them, and no React UI component to walk the user through modules.
- **Requirement:**
  - Build a `POST /api/training/plan` endpoint to create a 7-day study plan from identified leaks.
  - Implement a stepper/stepper-panel UI in React (under `Training.tsx` or `Learn.tsx`) to show "Today's Plan" and track progress.

### 3.6 Hand History Export API (Phase 1 / Section 3.10)
- **Status:** Endpoint only supports returning JSON arrays.
- **Requirement:** Add a "Download History" button to the Replay vault page that calls a `GET /api/hands/export` endpoint to download hand logs in industry-standard formats (e.g., PokerStars-compatible text files) for external solver analysis.

### 3.7 Spaced-Repetition System (SRS) Optimization (Section 2.8)
- **Status:** Drill scenarios are sampled randomly from static lists.
- **Requirement:** Update player database schema to track `{topic, scenario_id, last_seen, correct_rate}`. Adapt `drill_service` to prioritize drilling spots where the user has recently struggled.

---

## 4. Suggested Sequencing for Completion

Here is the proposed 3-stage plan to finish the project:

### Sprint A: Correctness & Bug-Fixing Pass (Estimated: 1-2 Days)
1. Fix **Bug 2.1** (Skill level and weakness recalculation using aggregate session history).
2. Wire up the **Career API** to use `CareerTracker` exclusively.
3. Clean up loose database schema logic to ensure correct hand tracking.
4. Add unit and integration tests under `tests/test_progression_full_history.py`.

### Sprint B: User Experience & Interactive Practice (Estimated: 2-3 Days)
1. Implement the **Drill Spaced-Repetition System (SRS)** in the backend.
2. Connect the **Focus Queue** elements in `Training.tsx` to automatically start a drill targeting the selected leak.
3. Add the **Download Hand History** button on the Replay page.
4. Render decision grades reasoning (`decision.analysis`) inside an expandable block on the Replay detail page.

### Sprint C: Mastery System & Background Tasking (Estimated: 3-4 Days)
1. Write the **7-Day Study Plan** API generator and wire it to a new React stepper widget on the Home page.
2. Introduce a Celery/Redis queue for asynchronous Monte Carlo runs.
3. Finalize all GTO and range solver integration tests.
4. Compile the final release checklist and build packaging.

---

## 5. Verification Plan

### 5.1 Automated Tests
- Run fast unit/integration tests:
  ```powershell
  ..\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/cfr/ -q
  ```
- Run full CFR convergence tests:
  ```powershell
  ..\.venv\Scripts\python.exe -m pytest tests/cfr/ -q
  ```
- Verify frontend TypeScript & Vitest suite:
  ```bash
  cd frontend
  npm run typecheck
  npm run test
  ```

### 5.2 Manual Verification
- Deploy FastAPI server locally, start the React dev server, and check the Analytics dashboard under multiple players to verify:
  1. Skill levels do not reset/degrade on short sessions.
  2. Spaced repetition serves weak scenarios correctly.
  3. "Today's Study Plan" marks tasks completed upon finishing corresponding drills.
