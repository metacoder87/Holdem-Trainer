// Shared helpers for the k6 load suite.
//
// Every HTTP call goes through `tagged()` so latency histograms can
// be split by logical endpoint (vs. raw URL). That lets us write
// per-endpoint thresholds in `options.thresholds` cleanly.

import http from "k6/http";
import { check } from "k6";

import { BASE_URL, COMMON_HEADERS } from "./config.js";

export function tagged(name, fn) {
  return fn({ tags: { name } });
}

export function get(path, name, params = {}) {
  const merged = {
    ...params,
    headers: { ...COMMON_HEADERS, ...(params.headers || {}) },
    tags: { name, ...(params.tags || {}) },
  };
  return http.get(`${BASE_URL}${path}`, merged);
}

export function post(path, body, name, params = {}) {
  const merged = {
    ...params,
    headers: { ...COMMON_HEADERS, ...(params.headers || {}) },
    tags: { name, ...(params.tags || {}) },
  };
  return http.post(`${BASE_URL}${path}`, JSON.stringify(body), merged);
}

export function expect2xx(res, msg) {
  return check(res, {
    [`${msg} status 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });
}

export function expectStatus(res, code, msg) {
  return check(res, {
    [`${msg} status ${code}`]: (r) => r.status === code,
  });
}

// Generate a deterministic player name per VU so concurrent VUs
// don't fight over the same player record. `__VU` is the unique
// virtual-user id in k6.
export function vuPlayerName(prefix) {
  return `${prefix || "load_user"}_${__VU}`;
}

// Pick a random element from a list (k6 lacks a util for this).
export function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
