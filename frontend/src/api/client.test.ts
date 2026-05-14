import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  evaluateTrainingDrill,
  evaluateTrainingQuiz,
  getHandDetail,
  getSummary,
  getTrainingDrill
} from "./client";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
});

function mockJson<T>(payload: T, status = 200) {
  fetchMock.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  } as Response);
}

describe("API client", () => {
  it("encodes player query in summary", async () => {
    mockJson({ player: { name: "Jon" } });
    await getSummary("Jon Doe");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/summary?player=Jon%20Doe");
  });

  it("encodes path segments for hand detail", async () => {
    mockJson({ hand_number: 7 });
    await getHandDetail("Jon Doe", 7);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/hands/Jon%20Doe/7");
  });

  it("builds the drill query string from player + focus", async () => {
    mockJson({
      drill_id: "abc",
      player: "Jon",
      focus_area: "poor_pot_odds",
      configuration: {
        focus_areas: [],
        quiz_distribution: {},
        difficulty: 2,
        estimated_duration: 0,
        weakness_targets: []
      },
      scenario: {},
      quiz: {},
      curriculum: {}
    });
    await getTrainingDrill("Jon", "poor_pot_odds");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("player=Jon");
    expect(url).toContain("focus=poor_pot_odds");
  });

  it("POSTs the drill answer with server-owned drill_id", async () => {
    mockJson({
      drill_id: "abc",
      focus_area: "poor_pot_odds",
      correct: true,
      feedback: "ok",
      user_answer: "call",
      correct_answer: "call",
      recommended_actions: [],
      progress: {
        schema_version: 1,
        quiz_attempts: [],
        drill_attempts: [],
        weakness_history: {},
        mastery_progress: {},
        study_recommendations: [],
        quiz_stats: { total: 0, correct: 0 },
        drill_stats: { total: 0, correct: 0 }
      }
    });
    await evaluateTrainingDrill("abc", "call", "Jon");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      drill_id: "abc",
      player: "Jon",
      user_answer: "call"
    });
  });

  it("POSTs the quiz answer with server-owned quiz_id", async () => {
    mockJson({
      correct: true,
      user_answer: 25,
      correct_answer: 25,
      feedback: "right",
      quiz_id: "xyz"
    });
    await evaluateTrainingQuiz("xyz", 25, "Jon");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      quiz_id: "xyz",
      player: "Jon",
      user_answer: 25,
      tolerance: 0.05
    });
  });

  it("throws ApiError with status on !response.ok", async () => {
    mockJson({ detail: "Session not found" }, 404);
    await expect(getHandDetail("Nobody", 99)).rejects.toMatchObject({
      name: "ApiError",
      status: 404
    });
  });

  it("ApiError carries the status for distinguishing 404 from generic errors", async () => {
    mockJson({ detail: "Server error" }, 500);
    try {
      await getHandDetail("X", 1);
      throw new Error("expected throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(500);
    }
  });
});
