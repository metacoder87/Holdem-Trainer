import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Games from "./Games";
import {
  ApiError,
  deleteGameSession,
  getSavedGameSessions,
  getGameHandState,
  getGameModes,
  getGameSession,
  pauseGameSession,
  resumeGameSession,
  startGameHand
} from "../api/client";

const testState = vi.hoisted(() => ({
  navigate: vi.fn(),
  shellContext: {
    summary: {
      player: { name: "Hero", skill_level: "rookie", last_played: null },
      live_metrics: [],
      training_tracks: [],
      focus_queue: [],
      focus_queue_items: [],
      timeline: []
    },
    activePlayer: "Hero"
  }
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => testState.navigate,
    useOutletContext: () => testState.shellContext
  };
});

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    createGameSession: vi.fn(),
    deleteGameSession: vi.fn(),
    getSavedGameSessions: vi.fn(),
    getGameHandState: vi.fn(),
    getGameModes: vi.fn(),
    getGameSession: vi.fn(),
    pauseGameSession: vi.fn(),
    resumeGameSession: vi.fn(),
    startGameHand: vi.fn()
  };
});

const staleSessionError = () => (
  new ApiError(404, "Session not found", "{\"detail\":\"Session not found\"}")
);

describe("Games page", () => {
  beforeEach(() => {
    localStorage.clear();
    testState.navigate.mockClear();
    vi.mocked(getGameModes).mockResolvedValue([]);
    vi.mocked(getSavedGameSessions).mockResolvedValue([]);
    vi.mocked(deleteGameSession).mockResolvedValue({ id: "session-1", status: "deleted" });
    vi.mocked(pauseGameSession).mockResolvedValue({
      id: "session-1",
      player_name: "Hero",
      game_type: "cash",
      limit_type: "no_limit",
      status: "paused",
      config: {}
    });
    vi.mocked(resumeGameSession).mockResolvedValue({
      session_id: "session-1",
      status: "awaiting_input",
      pending_input: null,
      input_error: null,
      terminal_reason: null,
      error: null,
      state: {
        game_state: "preflop",
        community_cards: [],
        pot_size: 30,
        players: []
      },
      last_hand: null
    });
    vi.mocked(getGameHandState).mockResolvedValue({
      session_id: "session-1",
      status: "hand_complete",
      pending_input: null,
      input_error: null,
      terminal_reason: null,
      error: null,
      state: {
        game_state: "hand_complete",
        community_cards: [],
        pot_size: 0,
        players: []
      },
      last_hand: null
    });
    vi.mocked(getGameSession).mockResolvedValue({
      id: "session-1",
      player_name: "Hero",
      game_type: "cash",
      limit_type: "no_limit",
      status: "ready",
      config: {}
    });
    vi.mocked(startGameHand).mockResolvedValue({
      session_id: "session-1",
      status: "awaiting_input",
      pending_input: null,
      input_error: null,
      terminal_reason: null,
      error: null,
      state: {
        game_state: "preflop",
        community_cards: [],
        pot_size: 30,
        players: []
      },
      last_hand: null
    });
  });

  it("clears a stale stored session without leaking raw API JSON", async () => {
    localStorage.setItem("ph_session_id", "missing-session");
    vi.mocked(getGameSession).mockRejectedValueOnce(staleSessionError());

    render(
      <MemoryRouter>
        <Games />
      </MemoryRouter>
    );

    expect(
      await screen.findByText("Your previous session is no longer available. Start a new session to continue.")
    ).toBeInTheDocument();
    expect(localStorage.getItem("ph_session_id")).toBeNull();
    expect(screen.queryByText("{\"detail\":\"Session not found\"}")).not.toBeInTheDocument();
    expect(getGameHandState).not.toHaveBeenCalled();
  });

  it("clears stale active session state when starting the next hand fails", async () => {
    localStorage.setItem("ph_session_id", "session-1");
    vi.mocked(startGameHand).mockRejectedValueOnce(staleSessionError());

    render(
      <MemoryRouter>
        <Games />
      </MemoryRouter>
    );

    expect(await screen.findByText("Session session-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start Next Hand" }));

    expect(
      await screen.findByText("Your previous session is no longer available. Start a new session to continue.")
    ).toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem("ph_session_id")).toBeNull());
    expect(screen.queryByText("{\"detail\":\"Session not found\"}")).not.toBeInTheDocument();
  });

  it("lists saved sessions and selects one for resume", async () => {
    vi.mocked(getSavedGameSessions).mockResolvedValueOnce([
      {
        id: "saved-1",
        player_name: "Hero",
        game_type: "tournament",
        limit_type: "no_limit",
        status: "awaiting_input",
        hands_played: 12,
        hero_stack: 4200
      }
    ]);

    render(
      <MemoryRouter>
        <Games />
      </MemoryRouter>
    );

    expect(await screen.findByText("saved-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));

    await waitFor(() => expect(localStorage.getItem("ph_session_id")).toBe("saved-1"));
    expect(resumeGameSession).toHaveBeenCalledWith("saved-1");
    expect(testState.navigate).toHaveBeenCalledWith("/session");
  });
});
