# PyHoldem Pro Roadmap - Action Steps

This roadmap mixes shipped foundations with aspirational strategy depth. Solver-grade
EV analysis, ICM-aware grading, range-vs-range mastery, and long-form curriculum
coverage are not complete unless called out as implemented below.

This roadmap breaks the vision into completable steps with clear deliverables.
Each step is intended to be independently shippable.

## Phase 0 - Architecture and scope
- [ ] Define API boundary and data contracts. Deliverables: docs/api-contract.md,
  endpoint list, initial schemas.
- [ ] Decide frontend stack and design system. Deliverables: docs/frontend-stack.md,
  typography/colors, asset plan.
- [ ] Data model and migration plan (JSON to DB). Deliverables: docs/data-model.md,
  migration strategy.

## Phase 1 - FastAPI service foundation
- [x] Create FastAPI app skeleton with health endpoint. Deliverables: backend/app,
  requirements, run instructions.
- [ ] Add auth and session model (guest + profile). Deliverables: token/session
  endpoints, middleware.
- [x] Game session APIs (create session, start hand, action). Deliverables: REST
  endpoints + WebSocket game stream.
- [x] Training APIs foundation (content, server-owned quizzes, drills, progress). Deliverables: REST endpoints +
  schemas.
- [x] Hand history APIs (list, detail, replay filters). Deliverables: pagination,
  filters, export.

## Phase 2 - Persistence and analytics
- [x] Introduce DB layer (SQLAlchemy + Alembic). Deliverables: models,
  migrations, data import.
- [x] Analytics aggregate APIs for summaries, reports, charts, and session rows.
- [ ] Scheduled analytics jobs and heavier background aggregation.
- [ ] Background tasks for heavy work. Deliverables: worker interface
  (Celery/RQ), job queue.

## Phase 3 - Frontend foundation
- [ ] Scaffold React + TypeScript app (Vite). Deliverables: lint/build/test
  baseline, routing, state store.
- [ ] Design system (Tailwind + Radix UI). Deliverables: tokens, components,
  typography, layout grid.
- [ ] Graphics pipeline. Deliverables: PixiJS table renderer with cards/chips,
  asset loading. Notes: optional 3D mode with React Three Fiber.
- [ ] Motion/audio/charts. Deliverables: GSAP/Framer Motion, Howler SFX,
  ECharts dashboards.
- [ ] API client and WebSocket integration. Deliverables: typed client, live
  state sync, optimistic actions.

## Phase 4 - Gameplay UI
- [x] Table view (players, pot, actions, betting controls).
- [x] Hand history and replay UI with decision details and filters.
- [ ] Browser-native training HUD overlays (terminal HUD exists; web overlay is partial).
- [x] Analytics dashboards (multi-metric trends, leaks, recent sessions).

## Phase 5 - Mastery training system
- [ ] Preflop curriculum. Deliverables: position ranges, open/call/3bet/4bet,
  push/fold, ICM drills.
- [ ] Postflop curriculum. Deliverables: board texture, range vs range equity,
  sizing, multi-street plans.
- [ ] Multiway and tournament modules. Deliverables: stack depth, payout
  pressure, bubble play, final table.
- [ ] Drill engine. Deliverables: scenario generator, spaced repetition, quiz
  bank.
- [ ] Coaching and grading. Deliverables: EV grading, leak detection, study plan
  generator.
- [ ] Progression and mastery tracking. Deliverables: skill levels, milestones,
  adaptive training paths.

## Phase 6 - AI and analysis
- [ ] Range-based AI and opponent archetypes.
- [ ] Opponent adaptation and exploit training.
- [ ] Equity calculators (Monte Carlo, blockers, multiway).

## Phase 7 - Quality and release
- [ ] Deterministic RNG hooks and CI stability.
- [ ] Unit/integration/e2e tests.
- [ ] Performance profiling and load testing.
- [ ] Release checklist and documentation.
