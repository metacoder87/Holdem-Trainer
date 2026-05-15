"""Game protocol consumed by every solver.

Games are pure functions over *state*. State is an opaque type
(``Hashable``) the solver passes back to ``transition`` / ``utility`` /
etc. The game author chooses whatever representation is cheapest.

Solvers depend only on this protocol; they don't import any concrete
game module. That's the decoupling axis: a new game (e.g. Sheriff,
multiplayer Kuhn) only needs a class implementing ``Game`` and the
solver picks it up unchanged.
"""
from __future__ import annotations

from typing import Hashable, Protocol, Sequence, Tuple, runtime_checkable

from cfr.core.action import Action


# Type alias - kept loose because state is game-specific.
State = Hashable


@runtime_checkable
class Game(Protocol):
    """Protocol for an extensive-form game compatible with CFR.

    All methods are pure. CFR makes ~10^6 transitions on a Leduc
    tree, so implementations should avoid allocations in the hot path.
    """

    num_players: int

    def initial_state(self) -> State:
        """Return the canonical root state (before any chance dealing)."""

    def is_terminal(self, state: State) -> bool:
        """True if the state has a defined utility (no further actions)."""

    def is_chance(self, state: State) -> bool:
        """True if it's nature's turn (a card is about to be dealt)."""

    def chance_outcomes(self, state: State) -> Sequence[Tuple[State, float]]:
        """For chance nodes: list of (next_state, probability) pairs.

        Probabilities must sum to 1.0.
        """

    def acting_player(self, state: State) -> int:
        """Which player is to act at this non-terminal, non-chance state.

        Players are 0-indexed. For heads-up games: 0 and 1.
        """

    def legal_actions(self, state: State) -> Sequence[Action]:
        """Ordered list of legal actions at this player node.

        Must be deterministic given the state - the solver caches action
        indices into the strategy table by infoset.
        """

    def transition(self, state: State, action: Action) -> State:
        """Apply ``action`` to ``state``, return successor state."""

    def utility(self, state: State, player: int) -> float:
        """Payoff for ``player`` at a terminal state, in BBs.

        For zero-sum games, ``sum(utility(state, p) for p in range(num_players)) == 0``.
        """

    def infoset_key(self, state: State, player: int) -> str:
        """Stable string key for the information set as seen by ``player``.

        Two states the player cannot distinguish must produce the same
        key. This is what makes the regret/strategy table well-defined.
        """
