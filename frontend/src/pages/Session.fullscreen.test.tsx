import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Session from "./Session";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: {
      name: "Test Hero",
      skill_level: "rookie",
      last_played: null
    },
    live_metrics: [],
    training_tracks: [],
    focus_queue: [],
    timeline: []
  }
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => shellContext
  };
});

vi.mock("../components/NeonTable", () => ({
  default: () => <div data-testid="mock-neon-table" />
}));

vi.mock("../api/client", () => ({
  getGameHandState: vi.fn(),
  getGameSession: vi.fn(),
  startGameHand: vi.fn()
}));

function renderSession() {
  return render(
    <MemoryRouter>
      <Session />
    </MemoryRouter>
  );
}

function clearFullscreenMocks() {
  Reflect.deleteProperty(Element.prototype, "requestFullscreen");
  Reflect.deleteProperty(document, "exitFullscreen");
  Reflect.deleteProperty(document, "fullscreenElement");
}

describe("Session fullscreen controls", () => {
  beforeEach(() => {
    localStorage.clear();
    clearFullscreenMocks();
  });

  afterEach(() => {
    clearFullscreenMocks();
    vi.restoreAllMocks();
  });

  it("uses native fullscreen when the browser API resolves", async () => {
    let fullscreenElement: Element | null = null;
    const requestFullscreen = vi.fn(function requestFullscreenMock(this: Element) {
      fullscreenElement = this;
      document.dispatchEvent(new Event("fullscreenchange"));
      return Promise.resolve();
    });
    const exitFullscreen = vi.fn(() => {
      fullscreenElement = null;
      document.dispatchEvent(new Event("fullscreenchange"));
      return Promise.resolve();
    });

    Object.defineProperty(Element.prototype, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: exitFullscreen
    });
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement
    });

    renderSession();
    const surface = screen.getByTestId("session-game-surface");

    fireEvent.click(screen.getByRole("button", { name: "Enter fullscreen" }));

    await waitFor(() => {
      expect(requestFullscreen).toHaveBeenCalledTimes(1);
      expect(surface).toHaveClass("is-fullscreen");
    });

    fireEvent.click(screen.getByRole("button", { name: "Exit fullscreen" }));

    await waitFor(() => {
      expect(exitFullscreen).toHaveBeenCalledTimes(1);
      expect(surface).not.toHaveClass("is-fullscreen");
    });
  });

  it("falls back to an in-page fullscreen overlay when native fullscreen fails", async () => {
    const requestFullscreen = vi.fn(() => Promise.reject(new Error("blocked")));

    Object.defineProperty(Element.prototype, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen
    });
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => null
    });

    renderSession();
    const surface = screen.getByTestId("session-game-surface");

    fireEvent.click(screen.getByRole("button", { name: "Enter fullscreen" }));

    await waitFor(() => {
      expect(requestFullscreen).toHaveBeenCalledTimes(1);
      expect(surface).toHaveClass("is-fallback-fullscreen");
      expect(screen.getByRole("button", { name: "Exit fullscreen" })).toHaveAttribute("aria-pressed", "true");
    });

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(surface).not.toHaveClass("is-fallback-fullscreen");
    });
  });
});
