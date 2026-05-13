import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReplayDetail from "./ReplayDetail";
import { getHandDetail } from "../api/client";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: { name: "Hero", skill_level: "rookie", last_played: null },
    live_metrics: [],
    training_tracks: [],
    focus_queue: [],
    timeline: []
  },
  activePlayer: "Hero"
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => shellContext,
    useParams: () => ({ handNumber: "7" })
  };
});

vi.mock("../api/client", () => ({
  getHandDetail: vi.fn()
}));

describe("ReplayDetail page", () => {
  beforeEach(() => {
    vi.mocked(getHandDetail).mockResolvedValue({
      hand_number: 7,
      hero_hole_cards: ["Ah", "Kd"],
      board: ["2c", "7d", "Ts"],
      winners: ["Hero"],
      pot_total: 120,
      decision_points: [
        {
          betting_round: "flop",
          chosen_action: "call",
          recommended_action: "fold",
          quality: "suboptimal",
          equity: 0.12,
          required_equity: 0.25,
          analysis: { reasoning: "Equity is below the required threshold." }
        }
      ],
      actions: []
    });
  });

  it("surfaces decision reasoning and equity details", async () => {
    render(
      <MemoryRouter>
        <ReplayDetail />
      </MemoryRouter>
    );

    expect(await screen.findByText("call vs fold")).toBeInTheDocument();
    expect(screen.getByText(/equity 12.0%/)).toBeInTheDocument();
    expect(screen.getByText("Equity is below the required threshold.")).toBeInTheDocument();
  });
});
