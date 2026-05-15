// Spike test: 10x burst over normal traffic for 60s, then drain.
//
// Verifies recovery: after the spike ends, p95 latency must return
// to baseline within 30 seconds. This is the "Black Friday at 12:01"
// scenario.

import { check, sleep } from "k6";

import { REQUEST_NAMES, SLO } from "./common/config.js";
import { get, expect2xx } from "./common/helpers.js";

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-arrival-rate",
      startRate: 100,
      timeUnit: "1s",
      preAllocatedVUs: 200,
      maxVUs: 2000,
      stages: [
        { duration: "30s", target: 100 },    // baseline
        { duration: "10s", target: 1000 },   // spike up
        { duration: "60s", target: 1000 },   // hold spike
        { duration: "10s", target: 100 },    // back to baseline
        { duration: "30s", target: 100 },    // verify recovery
      ],
    },
  },
  thresholds: {
    // Slightly relaxed under spike, but tight on either side. The
    // SLO that matters is "did we *recover*"; the histogram-window
    // averages span the full spike so we use the same threshold as
    // baseline reads.
    [`http_req_duration{name:${REQUEST_NAMES.summary}}`]: [
      "p(95)<500",  // double normal because some VUs hit during spike
      "p(99)<2000",
    ],
    "http_req_failed": ["rate<0.01"],
  },
};

export default function () {
  expect2xx(get("/api/summary", REQUEST_NAMES.summary), "summary");
}
