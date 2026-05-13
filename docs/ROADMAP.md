# PyHoldem Pro Roadmap

This roadmap reflects the current state of the codebase. `[x]` is shipped,
`[~]` is partially done, `[ ]` is not started. Updated 2026-05-09.

## Phase 0 - Architecture and scope
- [x] Define API boundary and data contracts. See [api-contract.md](api-contract.md).
- [ ] Decide frontend stack and design system. Vite + React + TS chosen; design system not yet documented (`docs/frontend-stack.md`).
- [ ] Data model and migration plan (JSON to DB). Not started; current persistence is JSON + JSONL.

## Phase 1 - FastAPI service foundation
- [x] FastAPI app skeleton with health endpoint.
- [ ] Auth and session model (guest + profile). Not started; sessions are anonymous.
- [x] Game session APIs (create session, start hand, action). REST flow with `pending_input`. WebSocket stream still TODO.
- [~] Training APIs. `/api/training/content`, `/api/training/tracks`, `/api/training/quiz`, `/api/training/quiz/evaluate`. Drills + per-quiz answer endpoints still TODO.
- [~] Hand history APIs. `GET /api/hands`, `GET /api/hands/{player}/{n}`, `GET /api/hands/{player}/{n}/replay`. Filters/export still TODO.

## Phase 2 - Persistence and analytics
- [ ] DB layer (SQLAlchemy + Alembic). Still pure JSON.
- [~] Analytics endpoints. `/api/analytics/summary` and `/api/analytics/leaks` shipped on top of `ProgressionAnalyzer`. Aggregation pipeline / scheduled jobs still TODO.
- [ ] Background tasks for heavy work.

## Phase 3 - Frontend foundation
- [x] React + TypeScript app (Vite). Lint/build/test baseline minus tests.
- [ ] Design system (Tailwind + Radix). Currently hand-rolled CSS in `app.css`.
- [~] Graphics pipeline. `NeonTable` is a Pixi scene but not yet driven by live game state.
- [ ] Motion/audio/charts. `framer-motion`/`howler`/`echarts` removed until features land.
- [x] API client and REST integration. WebSocket integration still TODO.

## Phase 4 - Gameplay UI
- [x] Table view (players, pot, actions, betting controls). Functional via Action Console; visual table is decorative.
- [x] Hand history list + per-hand replay UI (street-by-street with decision grades).
- [~] Training HUD overlays. Terminal HUD works; in-browser HUD overlays TODO.
- [x] Analytics dashboards. VPIP/PFR/AF metrics, trend lists, and leak radar are wired to live endpoints.

## Phase 5 - Mastery training system
- [ ] Preflop curriculum (position ranges, open/call/3bet/4bet, push/fold, ICM drills). Adaptive trainer scaffold exists; no curriculum content yet.
- [ ] Postflop curriculum.
- [ ] Multiway and tournament modules.
- [~] Drill engine. `AdaptiveTrainer.create_practice_scenario` generates scenarios; no scenario state machine or REST surface.
- [~] Coaching and grading. Preflop grading via `GameAnalyzer` + postflop pot-odds heuristic implemented. EV grading + leak detection pipeline (beyond `ProgressionAnalyzer.identify_weaknesses`) TODO.
- [~] Progression and mastery tracking. `SkillLevel` + weakness vocabulary in place; milestone thresholds in `CareerTracker`. Adaptive paths TODO.

## Phase 6 - AI and analysis
- [ ] Range-based AI and opponent archetypes. Current AI uses heuristic styles.
- [ ] Opponent adaptation and exploit training.
- [ ] Equity calculators (Monte Carlo, blockers, multiway). Current `_compute_equity_and_outs` is heuristic.

## Phase 7 - Quality and release
- [ ] Deterministic RNG hooks and CI stability. `Deck.shuffle(seed=...)` exists but is not wired into `GameEngine`.
- [~] Unit/integration tests. Backend coverage is broad. Frontend tests not present.
- [ ] Performance profiling and load testing.
- [ ] Release checklist and documentation.

## Recently shipped
- Tournament settlement now runs through the REST flow (no more vanishing buy-ins).
- Event-based wakeups in `game_service` (no more 10ms polling loop).
- `/api/hands/{player}/{n}/replay` endpoint and `ReplayDetail` page with street-by-street stepping.
- `/api/analytics/summary` + `/api/analytics/leaks`; Analytics page wired to live data.
- `/api/training/tracks` extracted from the dashboard summary.
- `App.tsx` summary refetches on player switch.
