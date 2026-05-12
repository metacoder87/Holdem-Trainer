import { afterEach, describe, expect, it, vi } from "vitest";
import { createGameSession, getHandDetail, getWebSocketUrl } from "./client";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds websocket URLs from the configured API origin", () => {
    expect(getWebSocketUrl("/ws/session-1")).toBe("ws://127.0.0.1:8000/ws/session-1");
  });

  it("serializes game session creation payloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "session-1",
        player_name: "Hero",
        game_type: "cash",
        limit_type: "no_limit",
        status: "ready",
        config: {}
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    await createGameSession({ player_name: "Hero", game_type: "cash", opponents: 1 });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/games/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ player_name: "Hero", game_type: "cash", opponents: 1 })
      })
    );
  });

  it("requests replay detail by player and hand number", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hand_number: 4 })
    });
    vi.stubGlobal("fetch", fetchMock);

    await getHandDetail("Hero Name", 4);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/hands/Hero%20Name/4",
      expect.any(Object)
    );
  });
});
