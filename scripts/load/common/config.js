// Shared config for the k6 load suite.
//
// `BASE_URL` defaults to the dockerized backend at backend:8000 (the
// hostname inside the docker-compose network). Override when running
// k6 from the host: `k6 run -e BASE_URL=http://localhost:8000 smoke.js`.

export const BASE_URL = __ENV.BASE_URL || "http://backend:8000";
export const WS_URL = (__ENV.WS_URL || BASE_URL).replace(/^http/, "ws");

// Per-endpoint SLO thresholds. Each scenario imports the slice it
// cares about. Keep targets *intentionally tight* - the whole point
// of load testing is to fail when the system starts cutting corners.
export const SLO = {
  api: {
    p50: 100,   // ms
    p95: 200,   // ms
    p99: 400,   // ms
  },
  write: {
    p50: 250,
    p95: 500,
    p99: 1000,
  },
  ws_connect: {
    p95: 100,
  },
  // Maximum acceptable error rate, expressed as a fraction.
  max_error_rate: 0.001, // 0.1%
};

export const COMMON_HEADERS = {
  "Content-Type": "application/json",
  "User-Agent": "k6-pyholdem-load/1.0",
};

// Standard names for stable thresholds. Keep these in sync with the
// `tags.name` set in helpers.js requests.
export const REQUEST_NAMES = {
  summary: "summary",
  players: "players",
  hand_list: "hand_list",
  session_create: "session_create",
  hand_start: "hand_start",
  hand_input: "hand_input",
  demo_hand: "demo_hand",
  training_quiz: "training_quiz",
  training_eval: "training_eval",
  analytics_career: "analytics_career",
  metrics: "metrics",
};
