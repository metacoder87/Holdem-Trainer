// Full game session lifecycle: create -> demo-hand -> create another...
//
// Drives sustained concurrent game sessions to verify the engine
// thread-pool + session TTL store hold up. This is the closest
// emulation to real user behavior.
//
// 100 concurrent VUs, each running a session every ~3 seconds for
// 2 minutes => ~3,800 sessions exercised.
//
//   k6 run -e BASE_URL=http://localhost:8000 scripts/load/game_session_lifecycle.js

import { check, sleep } from "k6";

import { REQUEST_NAMES, SLO } from "./common/config.js";
import { get, post, expect2xx, vuPlayerName } from "./common/helpers.js";

export const options = {
  scenarios: {
    sessions: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "20s", target: 100 },
        { duration: "1m",  target: 100 },
        { duration: "20s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    [`http_req_duration{name:${REQUEST_NAMES.session_create}}`]: [
      `p(95)<${SLO.write.p95}`,
      `p(99)<${SLO.write.p99}`,
    ],
    [`http_req_duration{name:${REQUEST_NAMES.demo_hand}}`]: [
      `p(95)<1500`,  // demo-hand runs a full hand internally, so it's slower
      `p(99)<3000`,
    ],
    "http_req_failed": [`rate<${SLO.max_error_rate}`],
    "checks": ["rate>0.99"],
  },
};

const GAME_TYPES = ["cash", "tournament"];

export default function () {
  const playerName = vuPlayerName("lifecycle");
  const gameType = GAME_TYPES[Math.floor(Math.random() * GAME_TYPES.length)];

  const body = {
    player_name: playerName,
    game_type: gameType,
    limit_type: "no_limit",
    small_blind: 10,
    big_blind: 20,
    opponents: 1,
  };
  if (gameType === "tournament") {
    body.buy_in = 100;
    body.starting_chips = 500;
    body.opponents = 1;
  }

  const create = post("/api/games/sessions", body, REQUEST_NAMES.session_create);
  if (!expect2xx(create, "session_create")) {
    sleep(1);
    return;
  }
  const session = JSON.parse(create.body);

  // Play one auto-resolving hand.
  const demo = post(
    `/api/games/sessions/${session.id}/demo-hand`,
    {},
    REQUEST_NAMES.demo_hand,
  );
  expect2xx(demo, "demo_hand");

  // Read it back.
  expect2xx(
    get(`/api/games/sessions/${session.id}`, "session_get"),
    "session_get",
  );

  sleep(2);
}
