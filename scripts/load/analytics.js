// Analytics aggregation scenario.
//
// The /api/analytics/* endpoints hit the heaviest read paths (full
// session log per player) so they're the most likely to need a
// query optimization. This scenario keeps 30 VUs continuously
// hitting career + session-report endpoints.

import { sleep } from "k6";

import { REQUEST_NAMES, SLO } from "./common/config.js";
import { get, expect2xx, vuPlayerName } from "./common/helpers.js";

export const options = {
  scenarios: {
    analytics: {
      executor: "constant-vus",
      vus: 30,
      duration: "1m",
    },
  },
  thresholds: {
    [`http_req_duration{name:${REQUEST_NAMES.analytics_career}}`]: [
      "p(95)<500",
      "p(99)<1000",
    ],
    "http_req_failed": [`rate<${SLO.max_error_rate * 5}`],
  },
};

export default function () {
  const playerName = vuPlayerName("analytics");
  expect2xx(
    get(`/api/analytics/career?player=${playerName}`, REQUEST_NAMES.analytics_career),
    "analytics_career",
  );
  // Session report may 404 for new players - that's expected, don't
  // assert 2xx here. Just record the latency.
  get(`/api/analytics/sessions/latest?player=${playerName}`, "analytics_session_latest");

  // Mix in a chart query.
  get(`/api/charts/vpip?player=${playerName}`, "charts_vpip");

  sleep(0.5);
}
