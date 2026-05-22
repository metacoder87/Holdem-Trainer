import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Analytics from "./Analytics";
import {
  getAnalyticsReport,
  getAnalyticsSessions,
  getChartData,
  getEvLeakReport,
  getIcmForSpot,
  getPlayers,
  getPreflopCharts,
  getRegretHeatmap,
  getVarianceReport,
  postDrillFromDecision,
  postRangeEquity,
} from "../api/client";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: { name: "Hero", skill_level: "rookie", last_played: null },
    live_metrics: [
      { label: "VPIP", value: "0%", delta: "+0%", tone: "warn" },
      { label: "PFR", value: "0%", delta: "+0%", tone: "warn" },
      { label: "AGG", value: "0.0", delta: "+0.0", tone: "warn" },
      { label: "DEC", value: "0%", delta: "+0%", tone: "warn" }
    ],
    training_tracks: [],
    focus_queue: [],
    focus_queue_items: [],
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
  getEvLeakReport: vi.fn(),
  getPlayers: vi.fn(),
  // Track 2: variance + ICM endpoints. Default to empty payloads
  // so the new panels render but don't pollute existing assertions.
  getVarianceReport: vi.fn(),
  getIcmReport: vi.fn(),
  getIcmForSpot: vi.fn(),
  // Track 3: regret heatmap + drill-from-decision.
  getRegretHeatmap: vi.fn(),
  postDrillFromDecision: vi.fn(),
  // Track 5: range/equity endpoints.
  getPreflopCharts: vi.fn(),
  postRangeEquity: vi.fn(),
}));

describe("Analytics page", () => {
  beforeEach(() => {
    vi.mocked(getPlayers).mockResolvedValue([]);
    vi.mocked(getChartData).mockResolvedValue([{ label: "Session 1", value: 24 }]);
    vi.mocked(getVarianceReport).mockResolvedValue({
      player: "Hero",
      winrate: null,
      rolling_bb100: [],
      ev_adjusted_lines: [],
      all_in_luck: null,
      session_count: 0,
    });
    vi.mocked(getIcmForSpot).mockResolvedValue({
      player: null,
      icm: null,
      note: "Compute an ICM spot",
    });
    vi.mocked(getRegretHeatmap).mockResolvedValue({
      player: "Hero",
      cells: [],
      max_loss_bb: 0,
      totals: { decisions: 0, ev_loss_bb: 0 },
    });
    vi.mocked(postDrillFromDecision).mockResolvedValue({
      drill: null,
      error: "stub",
    });
    // Track 5 stubs — empty charts so the range panel renders without
    // a network call but with no preset content.
    vi.mocked(getPreflopCharts).mockResolvedValue({
      charts: {},
      raw: {},
    });
    vi.mocked(postRangeEquity).mockResolvedValue({
      equities: [],
      players: [],
      trials: null,
      board: [],
    });
    vi.mocked(getAnalyticsReport).mockResolvedValue({
      playing_style: {
        player_type: "Normal-Aggressive",
        vpip: 0.24,
        pfr: 0.18,
        aggression_factor: 2.5,
        // Track 2 Bayesian blocks attached by the backend.
        vpip_ci: {
          value: 0.24,
          ci_lower: 0.18,
          ci_upper: 0.30,
          sample_size: 200,
          small_sample: false,
          position_vs_target: null,
          target_low: 0.18,
          target_high: 0.28,
        },
        pfr_ci: {
          value: 0.18,
          ci_lower: 0.13,
          ci_upper: 0.23,
          sample_size: 200,
          small_sample: false,
          position_vs_target: null,
          target_low: 0.15,
          target_high: 0.22,
        },
        aggression_factor_ci: {
          value: 2.5,
          ci_lower: 2.0,
          ci_upper: 3.0,
          sample_size: 200,
          small_sample: false,
        },
      },
      recommendations: ["Run drills for poor pot odds"],
      performance_metrics: { total_hands: 50 },
      strategy_score: 88,
      metric_options: { vpip: "VPIP", profit: "Profit" }
    });
    vi.mocked(getAnalyticsSessions).mockResolvedValue([
      {
        id: "s1",
        game_type: "cash",
        hands_played: 50,
        profit: 120,
        vpip: 0.2,
        pfr: 0.15,
        aggression_factor: 2.0,
        decision_accuracy: 0.7,
        quiz_accuracy: 1
      },
      {
        id: "s2",
        game_type: "cash",
        hands_played: 150,
        profit: 240,
        vpip: 0.3,
        pfr: 0.21,
        aggression_factor: 3.0,
        decision_accuracy: 0.9,
        quiz_accuracy: 1
      }
    ]);
    vi.mocked(getEvLeakReport).mockResolvedValue({
      player: "Hero",
      priced_decision_count: 4,
      mistake_count: 2,
      total_ev_loss_bb: 3.25,
      total_ev_loss_chips: 65,
      worst_group: {
        street: "turn",
        position: "2",
        chosen_action: "call",
        recommended_action: "fold",
        opponent_type: "loose-aggressive",
        decision_count: 2,
        total_ev_loss_bb: 3.25,
        total_ev_loss_chips: 65,
        average_ev_loss_bb: 1.625,
        examples: []
      },
      groups: [
        {
          street: "turn",
          position: "2",
          chosen_action: "call",
          recommended_action: "fold",
          opponent_type: "loose-aggressive",
          decision_count: 2,
          total_ev_loss_bb: 3.25,
          total_ev_loss_chips: 65,
          average_ev_loss_bb: 1.625,
          examples: []
        }
      ]
    });
  });

  it("renders metric chart, recommendations, and session rows", async () => {
    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    );

    expect(await screen.findByTestId("stats-chart")).toBeInTheDocument();
    expect(screen.getByText("Run drills for poor pot odds")).toBeInTheDocument();
    expect(screen.getAllByText("cash").length).toBeGreaterThan(0);
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("EV Leak Lab")).toBeInTheDocument();
    expect(screen.getAllByText("3.25 bb").length).toBeGreaterThan(0);
  });

  it("renders Bayesian credible intervals for VPIP/PFR/AGG", async () => {
    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    );

    // BayesianStatCard formats percent values as "24.0%" with one
    // decimal. The CI is rendered "CI X.X% – Y.Y%".
    expect(await screen.findByTestId("stats-chart")).toBeInTheDocument();
    expect(screen.getByText("24.0%")).toBeInTheDocument(); // VPIP point
    expect(screen.getByText("18.0%")).toBeInTheDocument(); // PFR point
    expect(screen.getByText("2.50")).toBeInTheDocument();   // AGG point (ratio)
    // Sample-size note appears for every Bayesian card; we have 3 of them.
    expect(screen.getAllByText(/n=200/).length).toBeGreaterThanOrEqual(3);
  });

  it("does not keep a stale failed status when partial analytics data succeeds", async () => {
    vi.mocked(getChartData).mockRejectedValueOnce(new Error("Failed to fetch"));

    render(
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    );

    expect(await screen.findByText("Run drills for poor pot odds")).toBeInTheDocument();
    expect(screen.queryByText("Failed to fetch")).not.toBeInTheDocument();
  });
});
