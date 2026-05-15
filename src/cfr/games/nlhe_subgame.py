"""NLHE postflop subgame.

A *subgame* solver runs CFR over a fixed-root subtree of full NLHE
rather than the whole game. The root specifies:

  - The community cards already dealt (flop = 3 known, turn = 4,
    river = 5).
  - The pot size at the root.
  - Both players' effective stacks (the smaller of the two).
  - Which player acts first (the OOP / IP convention).

Hands are abstracted into ``num_hand_buckets`` strength buckets per
player (default 10) and bet sizes are discretized into a fixed set
(default 33% / 66% / 100% pot, plus all-in).

Why postflop-only:

  - Preflop solving requires a much wider abstraction (169 starting
    hand classes, multiple SPRs, multi-street planning) and you don't
    actually need it for a trainer - canonical preflop charts cover
    that.
  - Postflop is where most decisions feel hard, where solvers add the
    most value as a teaching tool, and where the tree is small
    enough to solve in minutes per spot.

This module is the *skeleton*. The river-only path is fully wired and
tested. Turn and flop both work in principle but need a card-abstraction
step to be tractable (TODO marker below). Until then,
``include_future_streets=False`` keeps it river-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Sequence, Tuple

from cfr.abstractions.action_bucketing import (
    DEFAULT_BET_FRACTIONS,
    make_bet_actions,
)
from cfr.core.action import Action
from cfr.games.base import Game


# Standard postflop action set (CHECK_OR_CALL, FOLD, RAISE_*..., ALL_IN).
_ACTIONS = tuple(make_bet_actions(DEFAULT_BET_FRACTIONS))
_CHECK_OR_CALL = _ACTIONS[0]
_FOLD = _ACTIONS[1]
_ALL_IN = _ACTIONS[-1]


@dataclass(frozen=True, slots=True)
class NLHESubgameState:
    """Subgame state.

    ``hand_buckets`` is the (P0_bucket, P1_bucket) tuple - the only
    private info each player has, post-abstraction.

    ``contributions`` = (P0_chips_in_pot, P1_chips_in_pot) accumulated
    since the start of the subgame. Pot at any state = sum(contributions).

    ``history`` is the action sequence at the root (e.g. "ccrc" =
    check, check, raise, call). Closed on fold or all-call.
    """

    hand_buckets: Tuple[int, int]
    contributions: Tuple[int, int]
    starting_stack: int  # effective stack at the root
    starting_pot: int
    history: str = ""
    folded: int = -1  # -1 = nobody folded
    # First-to-act player at the subgame root.
    first_actor: int = 0


def _max_contribution(state: NLHESubgameState) -> int:
    return max(state.contributions)


def _committed_to_call(state: NLHESubgameState, player: int) -> int:
    return _max_contribution(state) - state.contributions[player]


def _stack_remaining(state: NLHESubgameState, player: int) -> int:
    """Remaining effective stack for ``player`` at this state."""
    return state.starting_stack - state.contributions[player]


def _is_all_in(state: NLHESubgameState, player: int) -> bool:
    return _stack_remaining(state, player) <= 0


def _round_over(state: NLHESubgameState) -> bool:
    """True if the betting round is closed at this state.

    Closed when:
      - A fold has occurred, or
      - Both players have acted at least once AND contributions match.
    """
    if state.folded != -1:
        return True
    if len(state.history) < 2:
        return False
    # If both contributions match and both have acted, round closed.
    if state.contributions[0] == state.contributions[1]:
        # But only if at least 2 actions have happened (both checked, or
        # bet-call sequence completed).
        return True
    return False


class NLHEPostflopSubgame:
    """CFR-compatible postflop subgame.

    Constructed for a specific (board, pot, stack, first_actor) and
    hand-bucketing setup. The solver picks the result up unchanged.
    """

    num_players = 2

    def __init__(
        self,
        *,
        num_hand_buckets: int = 10,
        starting_pot: int = 100,
        starting_stack: int = 100,
        first_actor: int = 0,
        bet_fractions: Sequence[float] = DEFAULT_BET_FRACTIONS,
        include_future_streets: bool = False,
    ) -> None:
        if first_actor not in (0, 1):
            raise ValueError("first_actor must be 0 or 1")
        if include_future_streets:
            # TODO: Card-abstraction for turn/river dealing.
            raise NotImplementedError(
                "include_future_streets requires card abstraction. Use river-only."
            )

        self.num_hand_buckets = num_hand_buckets
        self.starting_pot = starting_pot
        self.starting_stack = starting_stack
        self.first_actor = first_actor
        self.bet_fractions = tuple(bet_fractions)
        self._actions = tuple(make_bet_actions(self.bet_fractions))

    def initial_state(self) -> NLHESubgameState:
        # Hand buckets unset (chance node); filled in by chance_outcomes.
        return NLHESubgameState(
            hand_buckets=(-1, -1),
            contributions=(0, 0),
            starting_stack=self.starting_stack,
            starting_pot=self.starting_pot,
            history="",
            folded=-1,
            first_actor=self.first_actor,
        )

    def is_chance(self, state: NLHESubgameState) -> bool:
        return state.hand_buckets[0] < 0 or state.hand_buckets[1] < 0

    def is_terminal(self, state: NLHESubgameState) -> bool:
        if state.folded != -1:
            return True
        # Subgame ends when one player is all-in and the other has
        # called, or both have acted and contributions match.
        if _round_over(state) and len(state.history) > 0:
            return True
        return False

    def chance_outcomes(
        self, state: NLHESubgameState
    ) -> Sequence[Tuple[NLHESubgameState, float]]:
        # Deal P0's bucket, then P1's bucket. Buckets are independent
        # and uniformly distributed across [0, num_hand_buckets).
        # (In reality they're correlated through card removal, but
        # equal-frequency bucketing approximates uniform marginal.)
        n = self.num_hand_buckets
        if state.hand_buckets[0] < 0:
            return tuple(
                (replace(state, hand_buckets=(b, -1)), 1.0 / n)
                for b in range(n)
            )
        return tuple(
            (replace(state, hand_buckets=(state.hand_buckets[0], b)), 1.0 / n)
            for b in range(n)
        )

    def acting_player(self, state: NLHESubgameState) -> int:
        # first_actor acts at history "", second_actor at "x", etc.
        return (state.first_actor + len(state.history)) % 2

    def legal_actions(self, state: NLHESubgameState) -> Sequence[Action]:
        """Return legal actions given facing-bet state."""
        actor = self.acting_player(state)
        to_call = _committed_to_call(state, actor)
        stack = _stack_remaining(state, actor)

        legal = []
        # CHECK or CALL is always legal (when no bet, this is a check;
        # otherwise it's a call up to stack).
        legal.append(_CHECK_OR_CALL)
        # FOLD only makes sense when facing a bet.
        if to_call > 0:
            legal.append(_FOLD)
        # Raise sizes - only legal if we can actually afford the raise
        # AND raising is allowed (we cap at 1 raise per round to bound
        # the tree).
        if stack > to_call:
            already_raised = "r" in state.history
            if not already_raised:
                pot_now = sum(state.contributions) + state.starting_pot
                for action, frac in zip(self._actions[2:-1], self.bet_fractions):
                    raise_amount = int(round(frac * pot_now))
                    if raise_amount > to_call and raise_amount < stack:
                        legal.append(action)
            # All-in always legal as a final option (can also be a
            # short-stack jam below "raise" thresholds).
            legal.append(_ALL_IN)
        return tuple(legal)

    def transition(
        self, state: NLHESubgameState, action: Action
    ) -> NLHESubgameState:
        actor = self.acting_player(state)
        opp = 1 - actor
        to_call = _committed_to_call(state, actor)
        stack = _stack_remaining(state, actor)
        contribs = list(state.contributions)
        new_history = state.history
        new_folded = state.folded

        if action.name == "FOLD":
            new_folded = actor
            new_history += "f"
        elif action.name == "CHECK_OR_CALL":
            call_amount = min(to_call, stack)
            contribs[actor] += call_amount
            new_history += "c" if to_call > 0 else "k"
        elif action.name == "ALL_IN":
            contribs[actor] += stack
            new_history += "a"
        elif action.name.startswith("RAISE_"):
            # Compute the actual chip raise from fraction.
            frac = float(action.name.split("_")[1])
            pot_now = sum(state.contributions) + state.starting_pot
            raise_to = int(round(frac * pot_now))
            actual = min(raise_to, stack)
            contribs[actor] += actual
            new_history += "r"
        else:
            raise ValueError(f"Unknown action {action.name!r}")

        return replace(
            state,
            contributions=tuple(contribs),
            history=new_history,
            folded=new_folded,
        )

    def utility(self, state: NLHESubgameState, player: int) -> float:
        contrib_p0, contrib_p1 = state.contributions
        pot = state.starting_pot + contrib_p0 + contrib_p1

        if state.folded == 0:
            payoff_p0 = -contrib_p0
        elif state.folded == 1:
            payoff_p0 = contrib_p1
        else:
            # Showdown - higher bucket wins, ties split.
            b0, b1 = state.hand_buckets
            if b0 > b1:
                payoff_p0 = pot - contrib_p0 - state.starting_pot / 2.0
            elif b1 > b0:
                payoff_p0 = -(contrib_p0 + state.starting_pot / 2.0) + state.starting_pot / 2.0
                # equivalent to -contrib_p0 if we credit starting_pot
                # half each, but easier to compute symmetrically:
                payoff_p0 = -contrib_p0
            else:
                # Split: each gets half pot back minus contribs.
                payoff_p0 = (pot / 2.0) - contrib_p0 - state.starting_pot / 2.0

        return payoff_p0 if player == 0 else -payoff_p0

    def infoset_key(self, state: NLHESubgameState, player: int) -> str:
        # Player sees their own bucket and the public history.
        return f"b={state.hand_buckets[player]}|h={state.history}"
