import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GameControls from "./GameControls";
import { submitGameInput } from "../api/client";

vi.mock("../api/client", () => ({
  submitGameInput: vi.fn()
}));

const mockedSubmit = vi.mocked(submitGameInput);

describe("GameControls", () => {
  beforeEach(() => {
    mockedSubmit.mockReset();
    mockedSubmit.mockResolvedValue({
      session_id: "session-1",
      status: "awaiting_input",
      state: {
        game_state: "preflop",
        community_cards: [],
        pot_size: 0,
        players: []
      }
    });
  });

  it("submits menu actions as one-based choices", async () => {
    const onAction = vi.fn();
    render(
      <GameControls
        sessionId="session-1"
        pendingInput={{
          kind: "menu",
          prompt: "Choose action",
          options: ["Call", "Raise", "Fold"],
          min_value: 1,
          max_value: 3,
          integer_only: true
        }}
        onAction={onAction}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Raise" }));

    await waitFor(() => {
      expect(mockedSubmit).toHaveBeenCalledWith("session-1", { choice: 2 });
      expect(onAction).toHaveBeenCalled();
    });
  });

  it("submits numeric action input", async () => {
    render(
      <GameControls
        sessionId="session-2"
        pendingInput={{
          kind: "number",
          prompt: "Raise amount",
          min_value: 40,
          max_value: 400,
          integer_only: true
        }}
        onAction={vi.fn()}
      />
    );

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "120" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(mockedSubmit).toHaveBeenCalledWith("session-2", { value: 120 });
    });
  });
});
