import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionSocket } from "./useSessionSocket";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  listeners: Record<string, Array<(event: any) => void>> = {};

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event: any) => void) {
    this.listeners[type] = [...(this.listeners[type] || []), listener];
  }

  send(value: string) {
    this.sent.push(value);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  emit(type: string, event: any = {}) {
    if (type === "open") this.readyState = MockWebSocket.OPEN;
    if (type === "close") this.readyState = MockWebSocket.CLOSED;
    for (const listener of this.listeners[type] || []) {
      listener(event);
    }
  }
}

describe("useSessionSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0);
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("reconnects with backoff, requests a snapshot, and preserves last state", async () => {
    const { result, unmount } = renderHook(() => useSessionSocket("session-1"));

    const firstSocket = MockWebSocket.instances[0];
    act(() => firstSocket.emit("open"));
    expect(result.current.status).toBe("open");
    expect(firstSocket.sent).toContain(JSON.stringify({ action: "snapshot" }));

    const payload = {
      session_id: "session-1",
      status: "awaiting_input",
      state: {
        game_state: "river",
        community_cards: [],
        pot_size: 250,
        players: [],
        next_to_act: "Hero"
      },
      pending_input: { kind: "menu", prompt: "Act", options: ["Call"], min_value: 1, max_value: 1, integer_only: true },
      input_error: null,
      terminal_reason: null,
      error: null,
      last_hand: null
    };
    act(() => firstSocket.emit("message", { data: JSON.stringify(payload) }));
    expect(result.current.state?.state.next_to_act).toBe("Hero");

    act(() => firstSocket.emit("close"));
    expect(result.current.status).toBe("reconnecting");
    expect(result.current.state?.state.next_to_act).toBe("Hero");

    act(() => vi.advanceTimersByTime(1000));
    const secondSocket = MockWebSocket.instances[1];
    act(() => secondSocket.emit("open"));

    expect(result.current.status).toBe("open");
    expect(secondSocket.sent).toContain(JSON.stringify({ action: "snapshot" }));

    unmount();
  });
});
