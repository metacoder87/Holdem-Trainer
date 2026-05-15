// Smoke test - one VU, 30 seconds, walks every major route.
//
// Used as the CI smoke gate (see .github/workflows/ci.yml). If this
// fails the PR is blocked because something on the happy path is
// broken.
//
//   k6 run -e BASE_URL=http://localhost:8000 scripts/load/smoke.js
//
// Or inside docker compose:
//
//   docker compose -f docker-compose.yml -f docker-compose.load.yml \
//       run --rm k6 run /scripts/smoke.js

import { sleep } from "k6";

import { REQUEST_NAMES, SLO } from "./common/config.js";
import { get, post, expect2xx, vuPlayerName } from "./common/helpers.js";

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: {
    // The smoke test is a single VU - we tolerate higher tail latency
    // here because we're not driving sustained load. The bigger
    // scenarios enforce strict SLOs.
    [`http_req_duration{name:${REQUEST_NAMES.summary}}`]: ["p(95)<1000"],
    [`http_req_duration{name:${REQUEST_NAMES.players}}`]: ["p(95)<1000"],
    [`http_req_duration{name:${REQUEST_NAMES.session_create}}`]: ["p(95)<2000"],
    "http_req_failed": [`rate<${SLO.max_error_rate * 10}`],
    "checks": ["rate>0.95"],
  },
};

export default function () {
  // 1. Read-side: summary + players + bankroll summary.
  expect2xx(get("/api/summary", REQUEST_NAMES.summary), "summary");
  expect2xx(get("/api/bankroll/players", REQUEST_NAMES.players), "players");
  expect2xx(get("/api/bankroll/summary", "bankroll_summary"), "bankroll_summary");

  // 2. Game session lifecycle: create -> demo-hand -> read state.
  const playerName = vuPlayerName("smoke");
  const create = post(
    "/api/games/sessions",
    {
      player_name: playerName,
      game_type: "cash",
      limit_type: "no_limit",
      small_blind: 5,
      big_blind: 10,
      opponents: 1,
    },
    REQUEST_NAMES.session_create,
  );
  expect2xx(create, "session_create");
  if (create.status === 200) {
    const session = JSON.parse(create.body);
    expect2xx(
      post(`/api/games/sessions/${session.id}/demo-hand`, {}, REQUEST_NAMES.demo_hand),
      "demo_hand",
    );
  }

  // 3. Training: fetch a quiz.
  expect2xx(
    get(`/api/training/quiz?quiz_type=pot_odds&player=${playerName}`, REQUEST_NAMES.training_quiz),
    "training_quiz",
  );

  // 4. Metrics endpoint should serve Prometheus output.
  expect2xx(get("/metrics", REQUEST_NAMES.metrics), "metrics");

  sleep(1);
}
