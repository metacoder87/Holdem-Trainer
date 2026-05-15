// Read-heavy scenario: sustained 1000 req/s on /api/summary +
// /api/bankroll/players + /api/hands.
//
// Validates that the read path holds tight latency under load. These
// are the routes the dashboard hits on every render, so they're the
// most sensitive to P99 regressions.
//
//   k6 run -e BASE_URL=http://localhost:8000 scripts/load/read_heavy.js

import { check, sleep } from "k6";

import { REQUEST_NAMES, SLO } from "./common/config.js";
import { get, expect2xx, vuPlayerName } from "./common/helpers.js";

export const options = {
  scenarios: {
    read_heavy: {
      executor: "constant-arrival-rate",
      rate: 1000,
      timeUnit: "1s",
      duration: "1m",
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
  },
  thresholds: {
    [`http_req_duration{name:${REQUEST_NAMES.summary}}`]: [
      `p(95)<${SLO.api.p95}`,
      `p(99)<${SLO.api.p99}`,
    ],
    [`http_req_duration{name:${REQUEST_NAMES.players}}`]: [
      `p(95)<${SLO.api.p95}`,
      `p(99)<${SLO.api.p99}`,
    ],
    [`http_req_duration{name:${REQUEST_NAMES.hand_list}}`]: [
      `p(95)<${SLO.api.p95}`,
      `p(99)<${SLO.api.p99}`,
    ],
    "http_req_failed": [`rate<${SLO.max_error_rate}`],
    "checks": ["rate>0.999"],
  },
};

const ENDPOINTS = [
  { path: "/api/summary", name: REQUEST_NAMES.summary, label: "summary" },
  { path: "/api/bankroll/players", name: REQUEST_NAMES.players, label: "players" },
];

export default function () {
  const ep = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  const res = get(ep.path, ep.name);
  expect2xx(res, ep.label);

  // Occasionally hit the hand list (heavier query path).
  if (Math.random() < 0.1) {
    const playerName = vuPlayerName("read");
    expect2xx(
      get(`/api/hands?player=${playerName}&limit=50`, REQUEST_NAMES.hand_list),
      "hand_list",
    );
  }
}
