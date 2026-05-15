"""Vanilla CFR.

Classic recursive implementation. For each player p, performs a full
tree traversal where at each player-p infoset:
  1. Compute current strategy via regret matching over stored regrets.
  2. Recursively compute utilities for each action.
  3. Update cumulative regrets by (action_utility - node_utility) *
     opponent_reach (where opponent_reach is the product of opponent
     and chance probabilities reaching this state).
  4. Update cumulative strategy by current_strategy * own_reach.

Returns: utility of the node for player p.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from cfr.games.base import Game, State
from cfr.solvers.base import Solver


class VanillaCFRSolver(Solver):
    """Vanilla CFR (Zinkevich et al. 2007)."""

    def _iterate_once(self, iter_idx: int) -> None:
        # Run one full pass per player. Reach probabilities start at
        # 1.0 for both players.
        for p in range(self.game.num_players):
            self._cfr(
                self.game.initial_state(),
                player=p,
                reach=(1.0, 1.0),
                chance_reach=1.0,
            )

    def _cfr(
        self,
        state: State,
        player: int,
        reach: Tuple[float, float],
        chance_reach: float,
    ) -> float:
        """Return utility of ``state`` for ``player``.

        ``reach`` = (pi_0, pi_1) - product of own action probabilities
        getting to this state, per player.
        ``chance_reach`` - product of chance probabilities.
        """
        if self.game.is_terminal(state):
            return self.game.utility(state, player)

        if self.game.is_chance(state):
            total = 0.0
            for next_state, prob in self.game.chance_outcomes(state):
                total += prob * self._cfr(
                    next_state, player, reach, chance_reach * prob
                )
            return total

        acting = self.game.acting_player(state)
        actions = self.game.legal_actions(state)
        infoset = self.game.infoset_key(state, acting)
        strategy = self.regrets.regret_matching(infoset, actions)

        node_util = 0.0
        action_utils = np.zeros(len(actions))
        for i, action in enumerate(actions):
            next_state = self.game.transition(state, action)
            if acting == 0:
                next_reach = (reach[0] * strategy[i], reach[1])
            else:
                next_reach = (reach[0], reach[1] * strategy[i])
            action_utils[i] = self._cfr(
                next_state, player, next_reach, chance_reach
            )
            node_util += strategy[i] * action_utils[i]

        if acting == player:
            # Update regrets weighted by the opponent's + chance reach
            # to this infoset.
            opp_reach = reach[1 - player] * chance_reach
            regret_delta = opp_reach * (action_utils - node_util)
            self.regrets.add(infoset, actions, regret_delta)
            # Update average strategy weighted by player's own reach.
            self.strategy_sums.add(
                infoset, actions, strategy, weight=reach[player]
            )

        return node_util
