"""CFR+ - faster-converging variant of CFR.

Differences from vanilla CFR (Bowling et al. 2015):

  1. **Regret matching+**: stored regrets are clipped to >= 0 at every
     update. This is implemented in ``RegretTable.regret_matching_plus``.

  2. **Linear averaging**: at iteration ``t`` the contribution to the
     average strategy is weighted by ``t`` instead of 1. This puts more
     mass on later iterations where the strategy is closer to
     equilibrium.

  3. **Alternating updates**: each iteration updates a single player
     rather than both. (Halves the work per iteration; convergence
     speed is the same up to a constant.)

Empirically converges ~10x faster than vanilla CFR on Leduc.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from cfr.games.base import Game, State
from cfr.solvers.base import Solver


class CFRPlusSolver(Solver):
    """CFR+ with regret matching+ and linear weighting."""

    def _iterate_once(self, iter_idx: int) -> None:
        # Alternating-update CFR+: each iteration updates one player.
        updating_player = (iter_idx - 1) % self.game.num_players
        self._cfr(
            self.game.initial_state(),
            updating_player=updating_player,
            reach=(1.0, 1.0),
            chance_reach=1.0,
            iter_idx=iter_idx,
        )

    def _cfr(
        self,
        state: State,
        updating_player: int,
        reach: Tuple[float, float],
        chance_reach: float,
        iter_idx: int,
    ) -> float:
        if self.game.is_terminal(state):
            return self.game.utility(state, updating_player)

        if self.game.is_chance(state):
            total = 0.0
            for next_state, prob in self.game.chance_outcomes(state):
                total += prob * self._cfr(
                    next_state,
                    updating_player,
                    reach,
                    chance_reach * prob,
                    iter_idx,
                )
            return total

        acting = self.game.acting_player(state)
        actions = self.game.legal_actions(state)
        infoset = self.game.infoset_key(state, acting)
        strategy = self.regrets.regret_matching_plus(infoset, actions)

        node_util = 0.0
        action_utils = np.zeros(len(actions))
        for i, action in enumerate(actions):
            next_state = self.game.transition(state, action)
            if acting == 0:
                next_reach = (reach[0] * strategy[i], reach[1])
            else:
                next_reach = (reach[0], reach[1] * strategy[i])
            action_utils[i] = self._cfr(
                next_state,
                updating_player,
                next_reach,
                chance_reach,
                iter_idx,
            )
            node_util += strategy[i] * action_utils[i]

        if acting == updating_player:
            opp_reach = reach[1 - acting] * chance_reach
            regret_delta = opp_reach * (action_utils - node_util)
            self.regrets.add(infoset, actions, regret_delta)
            # Linear averaging: weight = iter_idx * own_reach.
            self.strategy_sums.add(
                infoset,
                actions,
                strategy,
                weight=iter_idx * reach[acting],
            )

        return node_util
