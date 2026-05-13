# Mastery Training Epics

These are target epics for future mastery coverage. The current app implements
foundational tracked play, server-owned quizzes, simple adaptive drills, hand
replay, and heuristic decision grading; the deeper criteria below are not yet
complete unless separately marked in the roadmap.

Each epic includes clear acceptance criteria to reach "master-level" coverage.

## 1) Preflop Mastery
Acceptance criteria:
- Position-based opening ranges for 6-max and 9-max.
- 3-bet/4-bet strategies by position and stack depth.
- Push/fold and ICM charts for short-stack tournament play.
- Drill generator with 200+ preflop spots.

## 2) Postflop Fundamentals
Acceptance criteria:
- Board texture classification and range advantages.
- Bet sizing rules across flop/turn/river with examples.
- Check-raise, probe, and delayed c-bet decision trees.
- Drill generator with 300+ postflop spots.

## 3) Multi-Street Planning
Acceptance criteria:
- Barrel frequency guidance for value and bluffs.
- Polar vs merged range construction by texture.
- River block/value/bluff selection modules.
- Training scenarios that grade line planning.

## 4) Range vs Range Equity
Acceptance criteria:
- Range equity calculator with blockers and suit removal.
- Multiway equity calculator with breakdowns.
- Equity quiz mode and time trials.
- HUD overlay to display live equity when enabled.

## 5) Tournament Strategy
Acceptance criteria:
- ICM-aware decision grading.
- Bubble and final table modules with payout pressure.
- Stack depth ladders (10bb, 20bb, 30bb, 50bb+).
- Tournament-specific leaks and drills.

## 6) Exploit and Adjustment
Acceptance criteria:
- Opponent type detection (tight/loose, passive/aggressive).
- Dynamic adjustments with example counter-strats.
- Exploit drills vs archetypes and mixed strategies.

## 7) Mental Game and Consistency
Acceptance criteria:
- Tilt detection heuristics and recovery routines.
- Session pacing guidance (time, decision speed).
- Mental game quizzes and self-assessments.

## 8) Hand Review and Replay
Acceptance criteria:
- Search, tag, and filter hand histories.
- Replay with decision grading overlays and hints.
- Export to common formats for external review.

## 9) Coaching Engine
Acceptance criteria:
- EV-based grading (where possible) and heuristics otherwise.
- Leak detection pipeline with severity ranking.
- Personalized study plan with weekly goals.

## 10) Progression and Mastery Tracking
Acceptance criteria:
- Skill tier system with milestone thresholds.
- Trend analysis and improvement forecasting.
- Mastery badge requirements per domain.
