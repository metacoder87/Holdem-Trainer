import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createDrill,
  getAnalyticsLeaks,
  getHandReplay,
  getSummary
} from "./client";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
});

function mockJson<T>(payload: T) {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  } as Response);
}

describe("API client", () => {
  it("encodes player query in summary", async () => {
    mockJson({ player: { name: "Jon" } });
    await getSummary("Jon Doe");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/summary?player=Jon%20Doe");
  });

  it("encodes player path segment in replay", async () => {
    mockJson({ hand_number: 1, hero_hole_cards: [], winners: [], pot_total: 0, meta: {}, streets: [], summary: {} });
    await getHandReplay("Jon Doe", 7);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/hands/Jon%20Doe/7/replay");
  });

  it("posts JSON body for createDrill", async () => {
    mockJson({
      drill_id: "abc",
      kind: "pot_odds",
      scenario: "...",
      options: [],
      correct_action: "call",
      context: {},
      difficulty: 2,
      focus_area: "poor_pot_odds"
    });
    await createDrill({ player_name: "Jon", focus_area: "poor_pot_odds", difficulty: 3 });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      player_name: "Jon",
      focus_area: "poor_pot_odds",
      difficulty: 3
    });
  });

  it("omits player query when not provided", async () => {
    mockJson({ player: null, leaks: [] });
    await getAnalyticsLeaks();
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url.endsWith("/api/analytics/leaks")).toBe(true);
  });
});
