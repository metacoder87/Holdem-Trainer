import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Session from "./Session";
import { getGameHandState, getGameSession } from "../api/client";

const testState = vi.hoisted(() => {
  const refreshSummary = vi.fn();
  return {
    refreshSummary,
    shellContext: {
      summary: {
        player: { name: "Hero", skill_level: "rookie", last_played: null },
        live_metrics: [],
        training_tracks: [],
        focus_queue: [],
        focus_queue_items: [],
        timeline: []
      },
      activePlayer: "Hero",
      refreshSummary
    }
  };
});

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => testState.shellContext
  };
});

vi.mock("../components/NeonTable", () => ({
  default: () => <div data-testid="neon-table" />
}));

vi.mock("../api/useSessionSocket", () => ({
  useSessionSocket: () => ({
    status: "closed",
    state: null,
    send: vi.fn(),
    startHand: vi.fn(),
    submitInput: vi.fn(),
    refresh: vi.fn()
  })
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    getGameHandState: vi.fn(),
    getGameSession: vi.fn(),
    startGameHand: vi.fn(),
    submitGameInput: vi.fn()
  };
});

describe("Session page", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("ph_session_id", "session-1");
    testState.refreshSummary.mockClear();
    vi.mocked(getGameSession).mockResolvedValue({
      id: "session-1",
      player_name: "Hero",
      game_type: "cash",
      limit_type: "no_limit",
      status: "hand_complete",
      config: {}
    });
    vi.mocked(getGameHandState).mockResolvedValue({
      session_id: "session-1",
      status: "hand_complete",
      pending_input: null,
      live_coach: {
        recommended_action: "call",
        confidence: 0.72,
        summary: "Call: equity edge is +4.0 points.",
        math: {
          pot: 120,
          to_call: 20,
          required_equity: 0.1429,
          estimated_equity: 0.183,
          equity_edge: 0.04,
          hand_strength: 0.4,
          hand_potential: 0.1,
          outs: {},
          spr: 12,
          effective_stack: 10000
        },
        opponent: {
          name: "Villain",
          hands: 4,
          vpip: 0.5,
          pfr: 0.25,
          aggression_factor: 1.5,
          type: "loose-aggressive"
        },
        rationale: ["Equity is 18.3% versus 14.3% required."],
        warnings: ["Opponent history sample is small."],
        history_signals: [],
        training_link: "/training/drill?focus=poor_pot_odds"
      },
      input_error: null,
      terminal_reason: null,
      error: null,
      state: {
        game_state: "hand_complete",
        community_cards: ["2c", "7d", "Ts"],
        pot_size: 120,
        players: [],
        hero_cards: ["Ah", "Kd"],
        hero_name: "Hero",
        hero_bankroll: 10000,
        hud: {
          opponents: [
            {
              name: "Villain",
              hands: 4,
              vpip: 0.5,
              pfr: 0.25,
              aggression_factor: 1.5,
              type: "loose-aggressive"
            }
          ]
        }
      },
      last_hand: {
        session_id: "session-1",
        hand_number: 3,
        winners: ["Hero"],
        pot_total: 120,
        coach_notes: {
          hero_won: true,
          headline: "Hero won a $120 pot with 1 tracked decision(s).",
          hand_grade: "A",
          takeaway: "No major decision leak was tagged in this hand.",
          worst_decision: null,
          decision_count: 1
        }
      }
    });
  });

  it("renders backend coach notes and HUD payloads", async () => {
    render(
      <MemoryRouter>
        <Session />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Coach notes - Hand grade/)).toBeInTheDocument();
    expect(screen.getByText("Hero won a $120 pot with 1 tracked decision(s).")).toBeInTheDocument();
    expect(screen.getByText("HUD")).toBeInTheDocument();
    expect(screen.getByText("Live Coach")).toBeInTheDocument();
    expect(screen.getByText("CALL")).toBeInTheDocument();
    expect(screen.getByText("Drill This Spot")).toBeInTheDocument();
    expect(screen.getByText("Villain")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review Last Hand" })).toHaveAttribute(
      "href",
      "/replay/3?session=session-1"
    );
    await waitFor(() => expect(testState.refreshSummary).toHaveBeenCalled());
  });

  it("keeps the action rail available in fullscreen fallback mode", async () => {
    render(
      <MemoryRouter>
        <Session />
      </MemoryRouter>
    );

    const workspace = await screen.findByTestId("session-workspace");
    fireEvent.click(screen.getByRole("button", { name: "Enter fullscreen" }));

    expect(workspace).toHaveClass("is-fallback-fullscreen");
    expect(screen.getByTestId("session-rail")).toBeInTheDocument();
    expect(screen.getByText("Action Console")).toBeInTheDocument();
  });

  it("disables next hand controls when backend reports a terminal game state", async () => {
    vi.mocked(getGameSession).mockResolvedValueOnce({
      id: "session-1",
      player_name: "Hero",
      game_type: "tournament",
      limit_type: "no_limit",
      status: "game_over",
      terminal_reason: "hero_eliminated",
      config: {}
    });
    vi.mocked(getGameHandState).mockResolvedValueOnce({
      session_id: "session-1",
      status: "game_over",
      pending_input: null,
      live_coach: null,
      input_error: null,
      terminal_reason: "hero_eliminated",
      error: null,
      state: {
        game_state: "hand_complete",
        community_cards: [],
        pot_size: 0,
        players: [],
        game_over_reason: "hero_eliminated"
      },
      last_hand: null
    });

    render(
      <MemoryRouter>
        <Session />
      </MemoryRouter>
    );

    const button = await screen.findByRole("button", { name: "Session Over" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Session ended: hero eliminated")).toBeInTheDocument();
  });
});
