// WebSocket live-session scenario.
//
// 50 concurrent VUs, each opens a WS to /ws/sessions/{id} after
// creating a session via REST. We hold the connection open for 30s
// receiving the periodic snapshot pushes, then close cleanly.
//
// Validates:
//   - WS upgrade latency (recorded as http_req_duration with the
//     special internal name "ws_connecting")
//   - The push loop doesn't crash on first state read
//   - Many open sockets don't break the server thread pool

import ws from "k6/ws";
import { check, sleep } from "k6";

import { BASE_URL, WS_URL, REQUEST_NAMES, SLO } from "./common/config.js";
import { post, expect2xx, vuPlayerName } from "./common/helpers.js";

export const options = {
  scenarios: {
    ws_live: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 50 },
        { duration: "60s", target: 50 },
        { duration: "10s", target: 0 },
      ],
    },
  },
  thresholds: {
    "ws_session_duration": ["p(95)<60000"],
    "ws_msgs_received": ["count>50"],
    "checks": ["rate>0.95"],
    [`http_req_duration{name:${REQUEST_NAMES.session_create}}`]: [
      `p(95)<${SLO.write.p95}`,
    ],
  },
};

export default function () {
  const playerName = vuPlayerName("wsuser");
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
  if (!expect2xx(create, "ws_session_create")) {
    sleep(1);
    return;
  }
  const session = JSON.parse(create.body);
  const wsUrl = `${WS_URL}/ws/sessions/${session.id}`;

  const res = ws.connect(wsUrl, {}, (socket) => {
    let snapshotsReceived = 0;
    let firstSnapshotOk = false;

    socket.on("open", () => {
      // Server sends an initial snapshot immediately on connect.
    });

    socket.on("message", (msg) => {
      snapshotsReceived += 1;
      try {
        const payload = JSON.parse(msg);
        if (!firstSnapshotOk && payload.session_id) {
          firstSnapshotOk = true;
          // Ask for a start to drive at least one state transition.
          socket.send(JSON.stringify({ action: "start" }));
        }
      } catch {
        // Non-JSON, ignore.
      }
    });

    socket.setTimeout(() => {
      // Sample the snapshot count we've seen, then close.
      check(snapshotsReceived, {
        "received >= 1 snapshot": (n) => n >= 1,
      });
      socket.close();
    }, 30000);
  });

  check(res, { "ws status 101": (r) => r && r.status === 101 });
}
