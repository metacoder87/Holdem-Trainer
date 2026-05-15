"""Leduc Hold'em - the next-step CFR benchmark beyond Kuhn.

Rules:
  - 6-card deck: two suits of {J, Q, K}.
  - 2 players, each gets 1 hole card. Both ante 1 (pot starts at 2).
  - Round 1 (preflop): action P0 -> P1. Bet size = 2 chips. Up to one
    raise allowed (no re-re-raise). Min raise = 2.
  - Public chance: 1 community card revealed.
  - Round 2 (flop): same as round 1 but bet size = 4 chips.
  - Showdown: player who pairs the community card wins; else higher
    rank wins; equal rank splits the pot.

State is encoded with:
  - hole cards (one each), private
  - community card, public (after round 1)
  - round (1 or 2)
  - action history within the round (per round, capped at "_c", "_b",
    "_bc", "_bf", "_bbc", "_bbf" type strings)
  - bets contributed by each player so far this round

Why Leduc matters for CFR validation:
  - Game tree is large enough to be non-trivial (~10^4 infosets) but
    small enough to solve to e-Nash in seconds.
  - Brute-force best response is feasible, so exploitability can be
    computed exactly.
  - Published equilibrium exploitability is < 0.001 BB/hand under
    CFR+ at 5000 iters; we use that as a regression target.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from cfr.core.action import Action
from cfr.games.base import Game


# Two suits of three ranks each. Suits don't matter for showdown rank
# but matter for "card pairing the board". We name them suffixed so we
# can tell J_a from J_b.
_DECK = ("Ja", "Jb", "Qa", "Qb", "Ka", "Kb")
_RANK = {"J": 0, "Q": 1, "K": 2}


def _rank(card: str) -> int:
    return _RANK[card[0]]


_CHECK = Action("CHECK")
_BET = Action("BET")
_CALL = Action("CALL")
_RAISE = Action("RAISE")
_FOLD = Action("FOLD")


@dataclass(frozen=True, slots=True)
class LeducState:
    holes: Tuple[str, str] = ("", "")
    community: str = ""
    # Per-round history strings:
    #   '' (start of round)
    #   'c' (check), 'b' (bet)
    #   'cc' (both check, round done)
    #   'cb', 'cbc', 'cbf', 'cbr', 'cbrc', 'cbrf'
    #   'br', 'brc', 'brf'
    #   etc.
    history_r1: str = ""
    history_r2: str = ""
    # Player who has folded, if any.
    folded: int = -1


def _round_done(h: str) -> bool:
    """True if the betting round is closed."""
    if h == "":
        return False
    last = h[-1]
    # Check-check closes round 1 / round 2.
    if h.endswith("cc"):
        return True
    # Bet-call or raise-call closes a round.
    if last == "c" and "b" in h:
        return True
    # Fold closes the game (not just the round).
    if last == "f":
        return True
    return False


def _bet_size(round_num: int) -> int:
    """Fixed bet size by round: 2 preflop, 4 postflop."""
    return 2 if round_num == 1 else 4


def _round_contributions(h: str, round_num: int) -> Tuple[int, int]:
    """Compute (p0_extra, p1_extra) contributions this round only.

    Players ante 1 each at the start of the game (handled in
    ``utility`` below, not here).
    """
    bet = _bet_size(round_num)
    p0 = 0
    p1 = 0
    # P0 acts first each round.
    current_player = 0
    # Track the standing bet level (max contribution) so 'c' after
    # 'b' = call.
    contributions = [0, 0]
    for ch in h:
        if ch == "c":
            # Check or call: match opponent's contribution.
            opp = 1 - current_player
            contributions[current_player] = contributions[opp]
        elif ch == "b":
            # Bet: increase own contribution by ``bet``.
            opp = 1 - current_player
            contributions[current_player] = contributions[opp] + bet
        elif ch == "r":
            # Raise: same as bet but stacks on existing bet.
            opp = 1 - current_player
            contributions[current_player] = contributions[opp] + bet
        elif ch == "f":
            # Fold doesn't add contribution; just ends.
            break
        current_player = 1 - current_player
    return contributions[0], contributions[1]


def _round_actions(h: str, round_num: int) -> Sequence[Action]:
    """Return the legal actions in the current round given history h."""
    # The acting player is whoever's turn comes after len(h) characters
    # of acting (player 0 acts first in each round).
    if h == "":
        # No bet yet: check or bet.
        return (_CHECK, _BET)
    last = h[-1]
    if last == "c" and len(h) == 1:
        # Opponent checked; we can check (close round) or bet.
        return (_CHECK, _BET)
    # Someone has bet/raised on this round.
    # Count 'b' and 'r' to see whether we've hit the raise cap (2/round).
    aggressions = sum(1 for c in h if c in "br")
    if aggressions >= 2:
        # Cap reached: only call or fold.
        return (_CALL, _FOLD)
    # Bet outstanding, raise still allowed.
    return (_CALL, _RAISE, _FOLD)


class LeducHoldem:
    """Leduc Hold'em as a CFR-compatible game."""

    num_players = 2

    def initial_state(self) -> LeducState:
        return LeducState()

    def _current_round(self, state: LeducState) -> int:
        return 1 if state.community == "" else 2

    def is_chance(self, state: LeducState) -> bool:
        # Deal hole cards first (2 chance nodes).
        if state.holes[0] == "":
            return True
        if state.holes[1] == "":
            return True
        # Then community card after round 1 closes.
        if state.community == "" and _round_done(state.history_r1):
            return True
        return False

    def is_terminal(self, state: LeducState) -> bool:
        if state.folded != -1:
            return True
        if state.community == "":
            return False
        # Round 2 has closed without a fold.
        return _round_done(state.history_r2)

    def chance_outcomes(
        self, state: LeducState
    ) -> Sequence[Tuple[LeducState, float]]:
        used = {c for c in state.holes if c} | (
            {state.community} if state.community else set()
        )
        remaining = [c for c in _DECK if c not in used]
        p = 1.0 / len(remaining)

        if state.holes[0] == "":
            return tuple(
                (
                    LeducState(
                        holes=(c, state.holes[1]),
                        community=state.community,
                        history_r1=state.history_r1,
                        history_r2=state.history_r2,
                        folded=state.folded,
                    ),
                    p,
                )
                for c in remaining
            )
        if state.holes[1] == "":
            return tuple(
                (
                    LeducState(
                        holes=(state.holes[0], c),
                        community=state.community,
                        history_r1=state.history_r1,
                        history_r2=state.history_r2,
                        folded=state.folded,
                    ),
                    p,
                )
                for c in remaining
            )
        # Deal community.
        return tuple(
            (
                LeducState(
                    holes=state.holes,
                    community=c,
                    history_r1=state.history_r1,
                    history_r2=state.history_r2,
                    folded=state.folded,
                ),
                p,
            )
            for c in remaining
        )

    def acting_player(self, state: LeducState) -> int:
        h = state.history_r2 if state.community else state.history_r1
        return len(h) % 2

    def legal_actions(self, state: LeducState) -> Sequence[Action]:
        h = state.history_r2 if state.community else state.history_r1
        return _round_actions(h, self._current_round(state))

    def transition(self, state: LeducState, action: Action) -> LeducState:
        ch = {
            "CHECK": "c",
            "BET": "b",
            "CALL": "c",
            "RAISE": "r",
            "FOLD": "f",
        }[action.name]

        in_round_2 = state.community != ""
        new_folded = state.folded
        if ch == "f":
            new_folded = self.acting_player(state)

        if in_round_2:
            return LeducState(
                holes=state.holes,
                community=state.community,
                history_r1=state.history_r1,
                history_r2=state.history_r2 + ch,
                folded=new_folded,
            )
        return LeducState(
            holes=state.holes,
            community=state.community,
            history_r1=state.history_r1 + ch,
            history_r2=state.history_r2,
            folded=new_folded,
        )

    def utility(self, state: LeducState, player: int) -> float:
        # Each player ante'd 1.
        ante = 1
        r1_p0, r1_p1 = _round_contributions(state.history_r1, 1)
        r2_p0, r2_p1 = _round_contributions(state.history_r2, 2)
        contrib_p0 = ante + r1_p0 + r2_p0
        contrib_p1 = ante + r1_p1 + r2_p1
        pot = contrib_p0 + contrib_p1

        if state.folded == 0:
            payoff_p0 = -contrib_p0
        elif state.folded == 1:
            payoff_p0 = contrib_p1
        else:
            # Showdown.
            winner = _showdown_winner(state.holes, state.community)
            if winner == 0:
                payoff_p0 = contrib_p1
            elif winner == 1:
                payoff_p0 = -contrib_p0
            else:  # split
                payoff_p0 = (pot / 2.0) - contrib_p0

        return payoff_p0 if player == 0 else -payoff_p0

    def infoset_key(self, state: LeducState, player: int) -> str:
        # Player sees their hole card + community (if revealed) + history.
        return (
            f"{state.holes[player]}|{state.community}|"
            f"{state.history_r1}|{state.history_r2}"
        )


def _showdown_winner(holes: Tuple[str, str], community: str) -> int:
    """Return 0/1 for winner or -1 for split."""
    c0_rank = _rank(holes[0])
    c1_rank = _rank(holes[1])
    board_rank = _rank(community)

    p0_pair = c0_rank == board_rank
    p1_pair = c1_rank == board_rank

    if p0_pair and not p1_pair:
        return 0
    if p1_pair and not p0_pair:
        return 1
    # Both paired or neither paired: higher hole card wins.
    if c0_rank > c1_rank:
        return 0
    if c1_rank > c0_rank:
        return 1
    return -1
