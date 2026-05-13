import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Training from "./Training";
import {
  evaluateTrainingQuiz,
  getPlayers,
  getTrainingContent,
  getTrainingProgress,
  getTrainingQuiz
} from "../api/client";

const shellContext = vi.hoisted(() => ({
  summary: {
    player: { name: "Hero", skill_level: "rookie", last_played: null },
    live_metrics: [],
    training_tracks: [],
    focus_queue: ["Pot odds speed drills"],
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

vi.mock("../api/client", () => ({
  evaluateTrainingQuiz: vi.fn(),
  getPlayers: vi.fn(),
  getTrainingContent: vi.fn(),
  getTrainingProgress: vi.fn(),
  getTrainingQuiz: vi.fn()
}));

describe("Training page", () => {
  beforeEach(() => {
    vi.mocked(getTrainingContent).mockResolvedValue({
      tips: [],
      vocabulary: [],
      strategy_guides: [],
      cheat_sheets: {}
    });
    vi.mocked(getPlayers).mockResolvedValue([]);
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
    vi.mocked(getTrainingQuiz).mockResolvedValue({
      quiz_id: "quiz-1",
      player: "Hero",
      type: "pot_odds",
      question: "Pot is 150, call 35.",
      difficulty: 1
    });
    vi.mocked(evaluateTrainingQuiz).mockResolvedValue({
      correct: true,
      user_answer: 19,
      correct_answer: 0.189,
      feedback: "Correct",
      explanation: "Server explanation",
      performance_stats: { total_quizzes: 1, correct_answers: 1, accuracy: 1 }
    });
  });

  it("submits quiz answers by server-owned quiz id", async () => {
    render(
      <MemoryRouter>
        <Training />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Generate Quiz" }));
    expect(await screen.findByText("Pot is 150, call 35.")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "19" } });
    fireEvent.click(screen.getByRole("button", { name: "Check Answer" }));

    await waitFor(() => {
      expect(evaluateTrainingQuiz).toHaveBeenCalledWith("quiz-1", 19, "Hero", 0.05);
      expect(screen.getByText(/Server explanation/)).toBeInTheDocument();
    });
  });
});
