"""Kuhn poker - the canonical CFR correctness anchor.

Rules:
  - 3-card deck: J, Q, K.
  - 2 players, 1 card each, both ante 1 (pot starts at 2).
  - Player 0 acts first. Actions: PASS or BET (size 1).
  - On a PASS-PASS: showdown.
  - On a BET-CALL: showdown.
  - On a BET-FOLD: bettor wins the pot.
  - On a PASS-BET: player 0 sees the bet, chooses CALL or FOLD.

Nash equilibrium (well-known, parametrized by alpha in [0, 1/3]):
  Player 0:
    J:  bet with prob alpha
    Q:  always pass
    K:  bet with prob 3*alpha
  Player 1:
    J after pass:  bet with prob 1/3
    J after bet:   always fold
    Q after pass:  always pass
    Q after bet:   call with prob 1/3
    K after pass:  always bet
    K after bet:   always call

CFR should converge to a strategy consistent with the above. The
``test_kuhn.py`` suite checks the key invariants:
  - Q is never bet by player 0 in any equilibrium.
  - K is called by player 1 always after a bet.
  - Game value is -1/18 to player 0 (player 0 loses 1/18 per hand at
    equilibrium when both play optimally).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence, Tuple

from cfr.core.action import Action
from cfr.games.base import Game


_CARDS = ("J", "Q", "K")
_CARD_RANK = {"J": 0, "Q": 1, "K": 2}

# Available actions in any Kuhn player node. Both are pre-allocated.
_PASS = Action("PASS")
_BET = Action("BET")


@dataclass(frozen=True, slots=True)
class KuhnState:
    """Immutable Kuhn state.

    ``cards`` is (player0_card, player1_card). Set to (None, None) at
    the root and filled by chance.

    ``history`` is the concatenated action string from the root, e.g.
    "" (root), "p" (player 0 passed), "pb" (then player 1 bet), "pbf"
    (player 0 folded). Terminal states have history ending in one of:
    "pp", "bp", "bb", "pbp", "pbb".
    """

    cards: Tuple[str, ...]  # always length 2
    history: str = ""

    def with_card(self, player: int, card: str) -> "KuhnState":
        new_cards = list(self.cards)
        new_cards[player] = card
        return replace(self, cards=tuple(new_cards))

    def with_action(self, char: str) -> "KuhnState":
        return replace(self, history=self.history + char)


class KuhnPoker:
    """Kuhn poker as a CFR-compatible game."""

    num_players = 2

    def initial_state(self) -> KuhnState:
        # Cards still to be dealt - represented as empty strings.
        return KuhnState(cards=("", ""))

    def is_terminal(self, state: KuhnState) -> bool:
        h = state.history
        if state.cards[0] == "" or state.cards[1] == "":
            return False
        return h in {"pp", "bp", "bb", "pbp", "pbb"}

    def is_chance(self, state: KuhnState) -> bool:
        return state.cards[0] == "" or state.cards[1] == ""

    def chance_outcomes(
        self, state: KuhnState
    ) -> Sequence[Tuple[KuhnState, float]]:
        # Deal first to player 0, then to player 1, uniformly over
        # remaining cards.
        if state.cards[0] == "":
            return tuple((state.with_card(0, c), 1.0 / 3.0) for c in _CARDS)
        # Player 0 already has a card; deal player 1.
        remaining = [c for c in _CARDS if c != state.cards[0]]
        p = 1.0 / len(remaining)
        return tuple((state.with_card(1, c), p) for c in remaining)

    def acting_player(self, state: KuhnState) -> int:
        # P0 acts first; P1 second; P0 again only on "pb".
        if state.history in {"", "pp", "bp", "bb"}:
            return 0 if len(state.history) % 2 == 0 else 1
        # General rule: position parity, except player-0 re-acts on "pb".
        return len(state.history) % 2

    def legal_actions(self, state: KuhnState) -> Sequence[Action]:
        # Both actions always legal in Kuhn (no folding before a bet).
        return (_PASS, _BET)

    def transition(self, state: KuhnState, action: Action) -> KuhnState:
        if action is _PASS or action.name == "PASS":
            return state.with_action("p")
        return state.with_action("b")

    def utility(self, state: KuhnState, player: int) -> float:
        # Standard Kuhn payoffs in pot units. Each player ante'd 1.
        h = state.history
        c0, c1 = state.cards
        p0_wins = _CARD_RANK[c0] > _CARD_RANK[c1]

        if h == "pp":
            # Showdown, ante 1 each, winner takes 1
            payoff_p0 = 1.0 if p0_wins else -1.0
        elif h == "bp":
            # P0 bet, P1 folded; P0 wins ante
            payoff_p0 = 1.0
        elif h == "bb":
            # P0 bet, P1 called; showdown, 2 chips at stake
            payoff_p0 = 2.0 if p0_wins else -2.0
        elif h == "pbp":
            # P0 passed, P1 bet, P0 folded; P1 wins P0's ante
            payoff_p0 = -1.0
        elif h == "pbb":
            # P0 passed, P1 bet, P0 called; showdown, 2 chips at stake
            payoff_p0 = 2.0 if p0_wins else -2.0
        else:
            raise ValueError(f"utility called on non-terminal {h!r}")

        return payoff_p0 if player == 0 else -payoff_p0

    def infoset_key(self, state: KuhnState, player: int) -> str:
        # The player sees only their own card and the public history.
        return f"{state.cards[player]}:{state.history}"
