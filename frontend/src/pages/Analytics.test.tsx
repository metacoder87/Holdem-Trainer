import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Analytics from "./Analytics";
import { getAnalyticsReport, getAnalyticsSessions, getChartData, getPlayers } from "../api/client";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: { name: "Hero", skill_level: "rookie", last_played: null },
    live_metrics: [{ label: "VPIP", value: "24%", delta: "+0%", tone: "good" }],
    training_tracks: [],
    focus_queue: [],
    timeline: []
  },
  activePlayer: "Hero",
  setActivePlayer: vi.fn()
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => shellContext
  };
});

vi.mock("../components/StatsChart", () => ({
  default: () => <div data-testid="stats-chart" />
}));

vi.mock("../api/client", () => ({
  getAnalyticsReport: vi.fn(),
  getAnalyticsSessions: vi.fn(),
  getChartData: vi.fn(),
  getPlayers: vi.fn()
}));

describe("Analytics page", () => {
  beforeEach(() => {
    vi.mocked(getPlayers).mockResolvedValue([]);
    vi.mocked(getChartData).mockResolvedValue([{ label: "Session 1", value: 24 }]);
    vi.mocked(getAnalyticsReport).mockResolvedValue({
      playing_style: { player_type: "Normal-Aggressive", vpip: 0.24, pfr: 0.18, aggression_factor: 2.5 },
      recommendations: ["Run drills for poor pot odds"],
      performance_metrics: { total_hands: 50 },
      strategy_score: 88,
      metric_options: { vpip: "VPIP", profit: "Profit" }
    });
    vi.mocked(getAnalyticsSessions).mockResolvedValue([
      { id: "s1", game_type: "cash", hands_played: 50, profit: 120, decision_accuracy: 0.8, quiz_accuracy: 1 }
    ]);
  });

  it("renders metric chart, recommendations, and session rows", async () => {
    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    );

    expect(await screen.findByTestId("stats-chart")).toBeInTheDocument();
    expect(screen.getByText("Run drills for poor pot odds")).toBeInTheDocument();
    expect(screen.getByText("cash")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
  });
});
