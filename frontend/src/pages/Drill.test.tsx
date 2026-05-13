import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Drill from "./Drill";
import { evaluateTrainingDrill, getTrainingDrill, getTrainingProgress } from "../api/client";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: { name: "Hero", skill_level: "rookie", last_played: null },
    live_metrics: [],
    training_tracks: [],
    focus_queue: ["Pot odds speed drills"],
    timeline: []
  },
  activePlayer: "Hero"
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => shellContext
  };
});

vi.mock("../api/client", () => ({
  evaluateTrainingDrill: vi.fn(),
  getTrainingDrill: vi.fn(),
  getTrainingProgress: vi.fn()
}));

describe("Drill page", () => {
  beforeEach(() => {
    vi.mocked(getTrainingDrill).mockResolvedValue({
      drill_id: "drill-1",
      player: "Hero",
      focus_area: "poor_pot_odds",
      configuration: {
        focus_areas: ["pot_odds"],
        quiz_distribution: { pot_odds: 1 },
        difficulty: 1,
        estimated_duration: 10,
        weakness_targets: ["poor_pot_odds"]
      },
      scenario: {
        situation: "Straight draw on the turn",
        pot_size: 150,
        opponents: 1
      },
      quiz: {
        question: "Should you call?",
        type: "pot_odds"
      },
      curriculum: {}
    });
    vi.mocked(getTrainingProgress).mockResolvedValue({
      player: "Hero",
      quiz_attempts: [],
      drill_attempts: [],
      weakness_history: {},
      mastery_progress: {},
      study_recommendations: [],
      quiz_stats: { total: 0, correct: 0, accuracy: null },
      drill_stats: { total: 0, correct: 0, accuracy: null }
    });
    vi.mocked(evaluateTrainingDrill).mockResolvedValue({
      drill_id: "drill-1",
      focus_area: "poor_pot_odds",
      correct: true,
      feedback: "Correct",
      user_answer: "call",
      correct_answer: "call",
      explanation: "Compare pot odds to equity.",
      recommended_actions: ["calculate pot odds"],
      progress: {
        quiz_attempts: [],
        drill_attempts: [],
        weakness_history: {},
        mastery_progress: { poor_pot_odds: 100 },
        study_recommendations: [],
        quiz_stats: { total: 0, correct: 0, accuracy: null },
        drill_stats: { total: 1, correct: 1, accuracy: 1 },
        schema_version: 1
      }
    });
  });

  it("submits drill answers and reveals review guidance", async () => {
    render(
      <MemoryRouter>
        <Drill />
      </MemoryRouter>
    );

    expect(await screen.findByText("Straight draw on the turn")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Example:/), { target: { value: "call" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit Drill" }));

    await waitFor(() => {
      expect(evaluateTrainingDrill).toHaveBeenCalledWith("drill-1", "call", "Hero");
      expect(screen.getByText("calculate pot odds")).toBeInTheDocument();
    });
  });
});
