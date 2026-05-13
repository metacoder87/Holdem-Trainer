# Training & Analytics Improvement Plan

A focused audit of the training and analytics surface area, with a prioritized
backlog of bugs to fix, mechanics to optimize, half-built features to finish,
and net-new work to build. Concrete acceptance criteria are listed so the
roadmap can be executed without re-deriving the design.

## Where things live today

Backend (`src/`, `backend/app/`)
- [src/stats/calculator.py](../src/stats/calculator.py) - pot odds, outs, hand strength, equity (heuristic).
- [src/stats/analyzer.py](../src/stats/analyzer.py) - `GameAnalyzer.analyze_preflop_action` (used inline by the engine for decision grading).
- [src/stats/session_tracker.py](../src/stats/session_tracker.py) - per-hand action log + per-session VPIP/PFR/AF/quiz/decision aggregates.
- [src/training/trainer.py](../src/training/trainer.py) - `PokerTrainer` with 4 quiz types (pot odds, required equity, implied odds, bet sizing) and accuracy/streak tracking.
- [src/training/analyzer.py](../src/training/analyzer.py) - `HandAnalyzer` for post-hand feedback + opponent type profiles.
- [src/training/adaptive_trainer.py](../src/training/adaptive_trainer.py) - weakness->topic mapping, scenario stubs, curriculum builder (paper).
- [src/training/progression_analyzer.py](../src/training/progression_analyzer.py) - skill level + weakness identification from session metrics.
- [src/training/career_tracker.py](../src/training/career_tracker.py) - long-term aggregates + milestone tracking (used only by CLI).
- [src/training/content_loader.py](../src/training/content_loader.py) - tips, vocabulary, strategy guides, cheat sheets.
- [src/training/hud.py](../src/training/hud.py) - Rich/terminal HUD (CLI only).
- [src/training/hand_replayer.py](../src/training/hand_replayer.py) - terminal replay.
- [backend/app/services/training_service.py](../backend/app/services/training_service.py) - wraps `PokerTrainer` for the REST API.
- [backend/app/services/drill_service.py](../backend/app/services/drill_service.py) - stateless drill engine (4 generators, deterministic via `drill_id` seed, persists to `practice_history`).
- [backend/app/services/analytics_service.py](../backend/app/services/analytics_service.py) - `/api/analytics/summary` and `/api/analytics/leaks`.
- [backend/app/services/summary_service.py](../backend/app/services/summary_service.py) - dashboard payload (live metrics, training tracks, focus queue, timeline).

Frontend (`frontend/src/pages/`)
- [Training.tsx](../frontend/src/pages/Training.tsx) - quiz tool, focus queue list, tips library.
- [Drill.tsx](../frontend/src/pages/Drill.tsx) - drill picker, single-question runner, session-local history.
- [Analytics.tsx](../frontend/src/pages/Analytics.tsx) - 4 metric cards, leak radar, last-5 trend strip.
- [Replay.tsx](../frontend/src/pages/Replay.tsx), [ReplayDetail.tsx](../frontend/src/pages/ReplayDetail.tsx) - hand list + per-hand street stepper with decision grades.

---

## 1) Bugs to fix

| # | Issue | Where | Fix |
|---|---|---|---|
| 1.1 | **Required-equity quiz is identical to pot-odds quiz.** [trainer.py:126](../src/training/trainer.py) reuses `PotOddsCalculator.calculate_pot_odds` and the explanation says "this is the same calculation as pot odds". The two quiz types are mathematically the same, so the "Required Equity" track inflates accuracy and the user never trains a distinct skill. | [src/training/trainer.py](../src/training/trainer.py) | Differentiate: required equity should ask `"to break even calling, what % equity do you need?"` and accept fold-equity adjustments for implied-odds variants. Add a separate variant where bet/pot sizes differ from a paired pot-odds question so the answer isn't the same number. |
| 1.2 | **Implied-odds calc treats future winnings as part of the pot.** [calculator.py:71-86](../src/stats/calculator.py) uses `effective_pot = pot_size + expected_future_bets` and reuses the pot-odds formula. That under-counts the *call's* contribution; standard implied-odds is `bet / (pot + bet + future)`. The current `calculate_implied_odds` returns `bet / (pot + future + bet)` only because the helper inverts terms - verify with a unit test, then document the chosen definition. | [src/stats/calculator.py](../src/stats/calculator.py) | Pin the formula in code + docstring, add a worked example, and unit-test against textbook outputs (e.g. pot 100, call 25, future 50 -> required equity 14.3%). |
| 1.3 | **Skill level + weakness detection runs once per session and overwrites.** [game_engine.py:_finalize_and_persist_session](../src/game/game_engine.py) feeds `ProgressionAnalyzer.identify_weaknesses` only the *latest* session's metrics, so a 12-hand session can flip a 5000-hand profile from "advanced" to "beginner". | [src/game/game_engine.py:_finalize_and_persist_session](../src/game/game_engine.py) | Aggregate over the player's full session history (or a rolling window weighted by hands played) before classifying. Drop labels that don't have enough sample. |
| 1.4 | **`identify_weaknesses` can return the same weakness twice.** [progression_analyzer.py:113](../src/training/progression_analyzer.py) appends `TOO_PASSIVE` for low PFR and again for low AF, which then double-shows in the leak list and the focus queue. | [src/training/progression_analyzer.py](../src/training/progression_analyzer.py) | Switch the result to a `set`/de-dup before returning. |
| 1.5 | **`get_random_quiz_type` ignores `IMPLIED_ODDS`/`BET_SIZING` correctness checks at low difficulty correctly but never adapts when the user is strong on basics.** Right now weights are static after `< 1.0` vs `>= 1.0`. The accuracy goes up, but the user never sees the harder topics more often. | [src/training/trainer.py:361](../src/training/trainer.py) | Replace the binary cutoff with a per-topic mastery score (correct-rate over the last 20 reps); under-trained topics get higher weight. |
| 1.6 | **`session_tracker` counts an open/raise as "raise" with `did_raise=False` when it's a non-full all-in.** [game_engine.py:660-720](../src/game/game_engine.py) - the action gets `did_raise` set based on full-raise logic. This is technically correct but the PFR/aggression stats classify a non-full-raise all-in as a call, which understates aggression for short stacks. | [src/game/game_engine.py](../src/game/game_engine.py), [src/stats/session_tracker.py](../src/stats/session_tracker.py) | Track `is_aggressive_intent` separately from `did_raise` so the metric reflects intent, not full-raise mechanics. |
| 1.7 | **`career_tracker` is wired into the CLI menu but not surfaced via the API**, so the React dashboard's career stats fall back to `_aggregate_metrics` which doesn't dedupe sessions and double-counts hand totals when `sessions` and `last_session` coexist. | [backend/app/services/analytics_service.py](../backend/app/services/analytics_service.py) | Use `CareerTracker` as the source of career aggregates; expose `/api/analytics/career` (see section 4). |
| 1.8 | **`pot_odds_accuracy` defaults to `0.0` when missing, then `_classify_severity` treats `0.0` as "very poor".** [analytics_service.py:46-76](../backend/app/services/analytics_service.py) - new players with no quizzes are flagged as having a "high severity" pot-odds leak. | [backend/app/services/analytics_service.py](../backend/app/services/analytics_service.py) | Replace `0.0` with `None`; gate severity on having a minimum sample (e.g. >=10 quiz attempts). |
| 1.9 | **Analytics trends silently truncate `aggression_factor` to a float without handling `Infinity`.** When postflop calls == 0 the engine emits `float("inf")`; JSON serialization quietly converts that to `Infinity` (invalid JSON) on some stacks. | [src/stats/session_tracker.py:to_dict](../src/stats/session_tracker.py), [backend/app/services/analytics_service.py](../backend/app/services/analytics_service.py) | Cap at a finite sentinel (e.g. `99.9`) at serialization time and document the semantics. |
| 1.10 | **Frontend Analytics trend "strip" shows last 5 values as text `"23% -> 24% -> ..."`.** No charts despite `Trend Overview` panel header. The original roadmap promised ECharts. | [frontend/src/pages/Analytics.tsx](../frontend/src/pages/Analytics.tsx) | Replace with a real line chart (see section 4.1). |

## 2) Optimizations / correctness improvements

| # | What | Why | Where |
|---|---|---|---|
| 2.1 | **Equity is heuristic, not range-based.** `HandOddsCalculator.calculate_hand_strength` maps hand rank -> a fixed strength score, with no Monte Carlo. The grading at [game_engine._record_human_decision_point](../src/game/game_engine.py) computes `equity_estimate = (strength + potential * 0.4) * opponent_factor`, then uses it as if it were vs-range equity. Decision grading is therefore approximate. | Replace with a real equity calculator (see section 3.5). | [src/stats/calculator.py](../src/stats/calculator.py), [src/game/game_engine.py](../src/game/game_engine.py) |
| 2.2 | **Outs calculator has hard ceilings** (`min(outs, 8)` for straights) that double-count overlap (e.g. flush + straight on the same suit). | More accurate outs -> more accurate rule-of-2/4 and HUD overlays. | [src/stats/calculator.py:_calculate_straight_outs](../src/stats/calculator.py), [src/stats/calculator.py:calculate_outs](../src/stats/calculator.py) |
| 2.3 | **`pot.distribute_to_winners` is correct only when `len(winners) > 1` *or* when `len(winners) == 1` and no side pots exist.** [game_engine.py:_distribute_pot](../src/game/game_engine.py) short-circuits "one winner -> entire pot" without consulting eligibility, which is wrong if the lone showdown winner went all-in for a smaller amount than other contributors. | Treats real multi-tier all-in showdowns incorrectly (rare but real). | [src/game/game_engine.py:_distribute_pot](../src/game/game_engine.py), [src/game/pot.py](../src/game/pot.py) |
| 2.4 | **Decision grading buckets are coarse.** [game_engine._record_human_decision_point](../src/game/game_engine.py) uses `optimal/acceptable/suboptimal/ungraded`. An EV-style score (chips/100) would let the dashboard show a true performance metric vs a count. | Enables "EV lost in big blinds" leaderboards and per-position breakdowns. | [src/game/game_engine.py](../src/game/game_engine.py), [src/training/analyzer.py](../src/training/analyzer.py) |
| 2.5 | **Quiz answer evaluator double-counts percent inputs.** [trainer.py:272-286](../src/training/trainer.py) - for fractional answers it accepts both `0.25` *and* `25` as "correct" but the percentage path uses `tolerance * 100`, so a user entering `30` against `0.25` (correct = 25%) is graded correct because difference (5) <= tolerance*100 (5). Tightens or documents intent; either way the current behavior is surprising. | Fix tolerance semantics; expose `tolerance_units` explicitly. | [src/training/trainer.py](../src/training/trainer.py) |
| 2.6 | **`_build_training_tracks` uses magic linear scoring** ([summary_service.py:168-188](../backend/app/services/summary_service.py)) - `preflop_score = 1 - (|vpip - 0.24| + |pfr - 0.18|)/0.5`. Tiny deviations move the score wildly, and the score doesn't reflect actual track completion (drills attempted, accuracy on the track). | Make track progress reflect drills completed + accuracy + reps consistency, not just last-session stats. | [backend/app/services/summary_service.py](../backend/app/services/summary_service.py) |
| 2.7 | **Drill scenarios are static lookups, not range-aware.** [drill_service.py:120-159](../backend/app/services/drill_service.py) - the hand-selection drill has 9 hand-action pairs hard-coded, and the 3-bet drill has 8. After ~20 reps a user has memorized the answers. | Generate scenarios from a range table + sampler (see section 3.1) so reps don't repeat for hundreds of attempts. | [backend/app/services/drill_service.py](../backend/app/services/drill_service.py) |
| 2.8 | **No spaced-repetition over scenarios.** Drill seeding is per-`drill_id`, not per-spot. A user who keeps missing AJo vs 3-bet will get other random spots before seeing it again. | Track per-`(focus_area, scenario_key)` last-seen + correct rate; surface the spots the user is failing at higher cadence. | [backend/app/services/drill_service.py](../backend/app/services/drill_service.py), `data/players.json` schema bump. |
| 2.9 | **`practice_stats` is recomputed by scanning the full `practice_history` on every grade.** [drill_service._record_practice_event](../backend/app/services/drill_service.py) - O(n) per grade, fine at n<=500 but worth caching once we add per-focus-area stats. | Maintain running counters in the player record. | [backend/app/services/drill_service.py](../backend/app/services/drill_service.py) |
| 2.10 | **HUD is terminal-only.** [src/training/hud.py](../src/training/hud.py) uses `rich` and `print()`s panels; nothing surfaces in the browser. The data exists in the backend (opponent profiles via `_get_table_player_stats`) but isn't exposed in `LiveGameState`. | Push HUD payload into the WS state so `Session.tsx` can render it. | [src/game/game_engine.py](../src/game/game_engine.py), [backend/app/services/game_service.py](../backend/app/services/game_service.py), [frontend/src/pages/Session.tsx](../frontend/src/pages/Session.tsx) |

## 3) Partially-built features to complete

| # | Feature | Status | Finish line |
|---|---|---|---|
| 3.1 | **Drill engine: real coverage.** | 4 generators exist (pot-odds, bet-sizing, hand-selection, 3-bet defense). Hand-selection only has 9 pairs; 3-bet defense 8. No turn/river drills, no ICM, no push-fold. | Build (a) a position-aware preflop range table (UTG/MP/CO/BTN/SB/BB), (b) push-fold charts keyed by stack depth in BBs, (c) postflop scenario sampler (board texture + range vs range), (d) ICM drill generator using `EquityCalculator.calculate_tournament_icm_equity` (which itself needs work - see 3.5). |
| 3.2 | **AdaptiveTrainer.generate_personalized_curriculum** is paper. [adaptive_trainer.py:219-263](../src/training/adaptive_trainer.py) returns a list of dicts (`{order, weakness, topics, exercises:10, quizzes:5}`) but no curriculum-runner endpoint, no progress persistence, no "module 3 of 5" UI. | Wire `POST /api/training/curriculum`, persist `{module_idx, exercise_idx, completed_modules}` per player, render a stepper UI in `Training.tsx`. |
| 3.3 | **`CareerTracker` exists but isn't reachable from the web UI.** Used only inside the CLI's "Career Report" branch ([main.py:316-338](../main.py)). The API's analytics summary recomputes career-ish numbers in `_aggregate_metrics` without consulting `CareerTracker`. | Expose `GET /api/analytics/career?player={name}` that returns `CareerMetrics.to_dict()` + milestones, and render a "Career" panel on the Analytics page. |
| 3.4 | **Post-hand feedback only fires in CLI when `post_hand_feedback=True` is enabled at game-setup time.** [game_engine.py:_show_post_hand_feedback](../src/game/game_engine.py) prints to stdout; nothing reaches the frontend. The data (rating, summary, learning points) is already computed by `HandAnalyzer`. | Pipe the feedback payload into `last_hand.coaching` (or a new `last_hand.feedback`) field returned by `_build_hand_response` so `Session.tsx` can show a "Coach notes" card after every hand. |
| 3.5 | **Monte Carlo equity calculator stub.** [stats/calculator.py:EquityCalculator](../src/stats/calculator.py) says in the docstring it would "run Monte Carlo simulations" but instead returns a strength-ratio. ICM is also a placeholder. | Implement (a) `calculate_heads_up_equity(hand1, hand2, board, trials=1000)` via random deal-out, (b) `calculate_range_vs_range_equity(range1, range2, board)`, (c) a textbook recursive ICM using `Malmuth-Harville`. Cache results keyed by canonical (hand, board) tuple. |
| 3.6 | **Replay decision grades are shown but un-explanatory.** [ReplayDetail.tsx](../frontend/src/pages/ReplayDetail.tsx) shows `quality` (OPTIMAL/SUBOPTIMAL) and recommended action but not *why*. The engine stores `analysis` on each decision point but the UI ignores it. | Render `decision.analysis` (the `GameAnalyzer.analyze_preflop_action` and `HandAnalyzer.analyze_decision` outputs) in an expandable "Why" block. |
| 3.7 | **Focus queue is text-only.** [Training.tsx:88-101](../frontend/src/pages/Training.tsx) shows a `<ul>` of leak labels; clicking does nothing. | Each focus-queue item becomes a "Start drill" button that pre-fills `focus_area` on the drill page. |
| 3.8 | **Quiz history isn't persisted.** [PokerTrainer.performance_stats](../src/training/trainer.py) lives in memory inside `_trainer` on the engine. CLI saves a `training_quiz_summary` on the player but the web flow re-instantiates a fresh `PokerTrainer` per request, so `total_quizzes`/`streak` always start at 0. | Persist `quiz_history` per player (drill-style: append to a small JSONL or a field on the player record). Update `evaluate_quiz` to take a `player_name` and persist. |
| 3.9 | **`analyzer.analyze_session` produces a session report (used by CLI's "Last Session Review")** but no API surface. | `GET /api/analytics/sessions/{idx}` returning `SessionReviewer.generate_session_report`. Surface in Analytics page below the trend chart. |
| 3.10 | **Hand replay export is hidden behind `?fmt=jsonl`.** Replay UI has no "Download" button. | Add a "Download history" button on the Replay vault that calls `/api/hands/export` with the active player + filters. |

## 4) New features to build

### 4.1 Real charts on Analytics
Replace the trend text strip with a small chart library (Recharts or `<svg>` line - pick one, target <50 kB gzipped). Acceptance:
- Per-metric line charts for `vpip`, `pfr`, `aggression_factor`, `decision_accuracy`, `profit`, all over the last N sessions (N selectable).
- Reference bands shaded for each metric's optimal range (`OPTIMAL` table in `summary_service.py`).
- Hover tooltip shows the session start time + value.

### 4.2 Range visualizer
A 13x13 grid for pocket pairs / suited / offsuit, color-coded by action (raise/call/fold/mix) for a given (position, vs-action) cell. Used in:
- Preflop drill explanations ("here's the chart you should be using").
- Replay decision grading ("you folded JTs in CO vs SB 3-bet; chart says call 60% / fold 40%").

Acceptance:
- Component takes `{ ranges: Map<HandCombo, Action> }` and renders.
- Backend serves a `GET /api/training/ranges/{position}/{vs_action}` from a canonical chart store (start with a hand-curated cash 100bb chart; bring in solver output later).

### 4.3 Goals / weekly study plan
Generate a 7-day plan from the player's weaknesses + drill history. Acceptance:
- `POST /api/training/plan` -> returns a 7-day plan: each day has 2-3 drills (focus area + count), 1 review of a previous session, ~20 minutes total.
- `GET /api/training/plan?player=` reads the current plan.
- Plan items mark themselves complete when matching drill grades / replay reviews land.
- "Today's plan" widget on the Home/Training pages.

### 4.4 Coach notes / hand-by-hand commentary
For every hand the engine already records `decision_points` with `quality` + `analysis`. Aggregate into a per-hand coaching summary:
- Highlight the single decision with the worst grade.
- Translate `analysis.reasoning` into one human sentence.
- Show on the Session page right after a hand ends, and on the Replay detail.

### 4.5 EV-based grading
Replace the bucket grader with a chips/100 EV loss estimate at each decision. Acceptance:
- `decision_point` gains `ev_chips` and `ev_loss_bb` (chips lost vs. the recommended action).
- Analytics dashboard adds an "EV/100" tile and a "biggest leaks by EV" list (joins decisions across hands, groups by `(betting_round, position, action)`).

### 4.6 Solver-style "node lock" review
Given a flagged hand, let the user replay the spot with a different action and re-run the equity calc to compare outcomes. Acceptance:
- Replay page has "What if I'd done X?" buttons next to each decision.
- Server re-runs from that street using stored cards + history, returning the alternative-line EV.
- This implicitly tests determinism (we already seed the deck through `GameEngine`).

### 4.7 Multiplayer trend comparisons
A small comparative panel on Analytics that compares the active player's metrics against the player's own historical baseline and against a "balanced" reference profile.

### 4.8 Training session mode (timed)
A web-equivalent of the CLI's Training Session menu: 10/20/30-minute timed drill blocks with a randomized mix from the focus queue, scoring at the end. Acceptance:
- "Start 15-min training session" button on Training page.
- Server-tracked timer + drill rotation, final summary stored in `practice_history`.

### 4.9 ICM and tournament-specific analytics
- ICM equity panel when the user is in a tournament session (stack ladder visualization).
- "Bubble factor" multiplier on grading near payout jumps.
- Push/fold charts gated by effective stack in BBs.

### 4.10 Mental game module
The engine flags `WeaknessType.TILT_PRONE` but there's no detector and no module. Build:
- Tilt heuristic: `vpip/pfr` and bet-sizing drift after a 3-bb-loss in a single hand.
- A brief "reset routine" prompt + journal entry the user can save.
- Mental-game quizzes that mirror the existing quiz format.

---

## 5) Suggested sequencing (3 sprints)

**Sprint A — Correctness pass** (most important; ships actual wins for the user)
1. Fix 1.1 (required-equity quiz)
2. Fix 1.3 (skill-level over full history) + 1.4 (de-dupe weaknesses)
3. Fix 1.8 (severity needs sample) + 1.9 (cap infinite AF)
4. Persist quiz history (3.8)
5. Wire focus-queue items to drill launcher (3.7)
6. Add the regression tests for each.

**Sprint B — UI gets useful**
1. Real chart library on Analytics + reference bands (4.1)
2. Pipe coach notes into hand-complete state (3.4) + show on Session page (4.4)
3. Render the decision `analysis` on Replay (3.6)
4. Career API + Analytics panel (3.3 / 1.7)

**Sprint C — Build the real trainer**
1. Range tables + 13x13 visualizer (4.2)
2. Monte Carlo equity + range-vs-range (3.5)
3. EV-based grading and dashboard tile (4.5)
4. Spaced-repetition + scenario sampler (2.7 / 2.8)
5. Weekly study plan (4.3)

Items 2.1-2.3 (engine correctness around equity + side pots) should land alongside Sprint C since they enable EV grading.

## 6) Test plan additions

Each change above needs at least one new test. Suggested clusters:
- `tests/test_training_quiz_distinctness.py` - assert required-equity vs pot-odds quizzes have different correct answers across N random samples (fixes 1.1).
- `tests/test_progression_dedupe.py` - feed a metrics dict that triggers `TOO_PASSIVE` twice, assert single appearance (fixes 1.4).
- `tests/test_progression_full_history.py` - many sessions vs one outlier session, assert skill level reflects the aggregate (fixes 1.3).
- `tests/test_drill_spaced_repetition.py` - 20 reps, ensure the spot most recently failed comes up again within 5 reps (covers 2.8).
- `tests/test_equity_monte_carlo.py` - vs. textbook equities (e.g. AA vs KK = 81/19) to within 2% (covers 3.5).
- `tests/test_ev_grading.py` - regression for the chips/100 calculation against a fixed hand (covers 4.5).

## 7) Data schema bumps

Bump `DataManager.SCHEMA_VERSION` to `1.2` and add a migration that:
- Adds `quiz_history: []` and `quiz_stats: {}` per player (3.8).
- Splits `practice_history` per focus area (`practice_history_by_focus`) so spaced-repetition queries don't scan the full list (2.8/2.9).
- Adds `weekly_plan: { generated_at, day_index, items: [...] }` (4.3).

## 8) Out of scope (deliberate)

- Real GTO solver. The plan above gets us to *exploit-level* accuracy with hand-curated charts + Monte Carlo equity, which is the right altitude for a trainer aimed at beginner-to-advanced players.
- Live multi-table support. Single-table only.
- Stripe / paid tiers / accounts. The trainer remains local-first.
