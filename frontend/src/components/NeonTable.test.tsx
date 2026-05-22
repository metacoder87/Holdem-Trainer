import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NeonTable from "./NeonTable";

/**
 * NeonTable is now a DOM-based table (see NeonTable.tsx comment for
 * the migration rationale). These tests pin the *user-visible*
 * outputs we promised to keep stable across the Pixi -> DOM
 * migration: pot readout, action label, community slots, hero
 * cards, and player seats with role badges + bet chips.
 */

describe("NeonTable (DOM)", () => {
  it("renders pot, action label, and 5 community-card slots", () => {
    render(<NeonTable pot="$100 POT" action="preflop" />);

    expect(screen.getByText("$100 POT")).toBeInTheDocument();
    expect(screen.getByText("preflop")).toBeInTheDocument();
    // Five face-down slots by default (no community cards passed).
    const faceDown = screen.getAllByLabelText(/Face-down card/i);
    expect(faceDown.length).toBeGreaterThanOrEqual(5);
  });

  it("renders hero hole cards when hero is in players", () => {
    render(
      <NeonTable
        pot="$10 POT"
        action="flop"
        heroCards={["A♠", "K♥"]}
        communityCards={["10♦", "J♣", "Q♠"]}
        players={[
          {
            name: "Hero",
            bankroll: 1000,
            current_bet: 0,
            folded: false,
            all_in: false,
            isHero: true,
          },
          {
            name: "Villain",
            bankroll: 1000,
            current_bet: 0,
            folded: false,
            all_in: false,
          },
        ]}
      />
    );

    // Hero cards.
    expect(screen.getByLabelText(/A of Spades/)).toBeInTheDocument();
    expect(screen.getByLabelText(/K of Hearts/)).toBeInTheDocument();
    // Community cards (first three).
    expect(screen.getByLabelText(/10 of Diamonds/)).toBeInTheDocument();
    expect(screen.getByLabelText(/J of Clubs/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Q of Spades/)).toBeInTheDocument();
  });

  it("recognizes backend is_hero payloads and seats hero at the bottom", () => {
    const { container } = render(
      <NeonTable
        pot="$42 POT"
        action="river"
        heroCards={["As", "Kh"]}
        players={[
          {
            name: "Villain",
            bankroll: 1200,
            current_bet: 0,
            folded: false,
            all_in: false,
          },
          {
            name: "Hero",
            bankroll: 980,
            current_bet: 40,
            folded: false,
            all_in: false,
            is_hero: true,
          },
        ]}
      />
    );

    expect(screen.getByLabelText(/A of Spades/)).toBeInTheDocument();
    expect(screen.getByLabelText(/K of Hearts/)).toBeInTheDocument();

    const heroSeat = container.querySelector(".dom-seat-hero") as HTMLElement | null;
    expect(heroSeat).not.toBeNull();
    expect(heroSeat?.style.top).toBe("89%");
    expect(heroSeat?.style.left).toBe("50%");
  });

  it("places seats after hero clockwise so SB is left and BB is right", () => {
    const { container } = render(
      <NeonTable
        pot="$30 POT"
        action="preflop"
        players={[
          {
            name: "Hero",
            bankroll: 1000,
            current_bet: 0,
            folded: false,
            all_in: false,
            is_hero: true,
            is_dealer: true,
          },
          {
            name: "SmallBlind",
            bankroll: 990,
            current_bet: 5,
            folded: false,
            all_in: false,
            is_small_blind: true,
          },
          {
            name: "BigBlind",
            bankroll: 980,
            current_bet: 10,
            folded: false,
            all_in: false,
            is_big_blind: true,
          },
        ]}
      />
    );

    const seats = Array.from(container.querySelectorAll(".dom-seat")) as HTMLElement[];
    expect(seats).toHaveLength(3);
    expect(seats[0].textContent).toContain("Hero");
    expect(seats[1].textContent).toContain("SmallBlind");
    expect(seats[2].textContent).toContain("BigBlind");
    expect(parseFloat(seats[1].style.left)).toBeLessThan(parseFloat(seats[0].style.left));
    expect(parseFloat(seats[2].style.left)).toBeGreaterThan(parseFloat(seats[0].style.left));
    expect(screen.getByText("D")).toBeInTheDocument();
    expect(screen.getByText("SB")).toBeInTheDocument();
    expect(screen.getByText("BB")).toBeInTheDocument();
  });

  it("renders seat panels with name, stack, and role badges", () => {
    render(
      <NeonTable
        pot="$60 POT"
        action="turn"
        players={[
          {
            name: "Hero",
            bankroll: 950,
            current_bet: 50,
            folded: false,
            all_in: false,
            isHero: true,
            is_dealer: true,
          },
          {
            name: "Vega",
            bankroll: 800,
            current_bet: 100,
            folded: false,
            all_in: false,
            is_big_blind: true,
          },
        ]}
      />
    );

    // Names rendered.
    expect(screen.getByText("Hero")).toBeInTheDocument();
    expect(screen.getByText("Vega")).toBeInTheDocument();
    // Dealer + BB role chips rendered as their letter labels.
    expect(screen.getByText("D")).toBeInTheDocument();
    expect(screen.getByText("BB")).toBeInTheDocument();
    // Stacks rendered with $.
    expect(screen.getByText("$950")).toBeInTheDocument();
    expect(screen.getByText("$800")).toBeInTheDocument();
  });

  it("shows folded / all-in status banners", () => {
    render(
      <NeonTable
        players={[
          {
            name: "FoldedGuy",
            bankroll: 600,
            current_bet: 0,
            folded: true,
            all_in: false,
          },
          {
            name: "AllInGuy",
            bankroll: 0,
            current_bet: 0,
            folded: false,
            all_in: true,
          },
        ]}
      />
    );

    expect(screen.getByText("FOLDED")).toBeInTheDocument();
    expect(screen.getByText("ALL-IN")).toBeInTheDocument();
  });

  it("renders a bet chip stack when a player has current_bet > 0", () => {
    render(
      <NeonTable
        players={[
          {
            name: "Bettor",
            bankroll: 800,
            current_bet: 250,
            folded: false,
            all_in: false,
          },
        ]}
      />
    );
    // The chip-stack title surfaces the bet amount and the panel
    // status shows the same number.
    expect(screen.getByTitle(/Bet: 250/)).toBeInTheDocument();
    expect(screen.getByText("BET $250")).toBeInTheDocument();
  });
});
