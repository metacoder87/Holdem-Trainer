"""Regret and average-strategy tables.

Both tables are keyed by *infoset_key: str* (each game defines its own
key encoding). Values are numpy arrays indexed by *action index* into a
per-infoset action list maintained by the table itself.

The split between ``RegretTable`` (used during training) and
``StrategyTable`` (used for the average / final policy) follows the
standard CFR contract: cumulative regrets drive the next iteration's
strategy via regret matching; the *average* strategy across all
iterations is the one that converges to Nash equilibrium.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

import numpy as np

from cfr.core.action import Action


class RegretTable:
    """Cumulative counterfactual regret R^T per (infoset, action).

    Internally backed by a ``dict[str, np.ndarray]`` so the table grows
    only with reachable infosets. Memory cost is O(infosets * |A|).

    CFR+ regret matching (``regret_matching_plus``) clips negative
    regrets to zero at *update* time, which is the key difference from
    vanilla CFR's clip-at-strategy-time approach. CFR+ converges ~10x
    faster on Leduc-scale games.
    """

    __slots__ = ("_regrets", "_action_lists")

    def __init__(self) -> None:
        self._regrets: Dict[str, np.ndarray] = {}
        # Cached action list per infoset (lets us share regrets across calls).
        self._action_lists: Dict[str, Tuple[Action, ...]] = {}

    def _ensure(self, infoset_key: str, actions: Sequence[Action]) -> np.ndarray:
        arr = self._regrets.get(infoset_key)
        if arr is None:
            arr = np.zeros(len(actions), dtype=np.float64)
            self._regrets[infoset_key] = arr
            self._action_lists[infoset_key] = tuple(actions)
        return arr

    def get(self, infoset_key: str, actions: Sequence[Action]) -> np.ndarray:
        """Return the regret vector for this infoset (lazy-allocated)."""
        return self._ensure(infoset_key, actions)

    def add(
        self,
        infoset_key: str,
        actions: Sequence[Action],
        delta: np.ndarray,
    ) -> None:
        """Accumulate a regret update vector."""
        arr = self._ensure(infoset_key, actions)
        arr += delta

    def regret_matching(self, infoset_key: str, actions: Sequence[Action]) -> np.ndarray:
        """Vanilla regret matching: positive regrets normalized.

        If all regrets are <= 0, return a uniform distribution.
        """
        regrets = self._ensure(infoset_key, actions)
        positive = np.maximum(regrets, 0.0)
        total = positive.sum()
        if total > 0:
            return positive / total
        return np.full(len(actions), 1.0 / len(actions))

    def regret_matching_plus(
        self, infoset_key: str, actions: Sequence[Action]
    ) -> np.ndarray:
        """CFR+ regret matching: clip stored regrets to >= 0 on read.

        Together with the ``update_plus`` helper this produces the
        canonical CFR+ behavior: regrets cannot go negative.
        """
        regrets = self._ensure(infoset_key, actions)
        # Clip in place so subsequent updates also see clipped values.
        np.maximum(regrets, 0.0, out=regrets)
        total = regrets.sum()
        if total > 0:
            return regrets / total
        return np.full(len(actions), 1.0 / len(actions))

    def num_infosets(self) -> int:
        return len(self._regrets)

    def infoset_keys(self) -> List[str]:
        return list(self._regrets.keys())


class StrategyTable:
    """Cumulative *average* strategy across all CFR iterations.

    The average is what converges to Nash equilibrium; the
    iteration-by-iteration strategy does not. Backed by sum-of-weights
    so we can produce a normalized policy at any time.

    CFR+ linear averaging: pass an iteration-dependent ``weight`` to
    ``add`` (typically ``t``, the iteration number) which puts more
    mass on later iterations and dramatically improves convergence
    speed in practice.
    """

    __slots__ = ("_sums", "_action_lists")

    def __init__(self) -> None:
        self._sums: Dict[str, np.ndarray] = {}
        self._action_lists: Dict[str, Tuple[Action, ...]] = {}

    def add(
        self,
        infoset_key: str,
        actions: Sequence[Action],
        strategy: np.ndarray,
        weight: float = 1.0,
    ) -> None:
        arr = self._sums.get(infoset_key)
        if arr is None:
            arr = np.zeros(len(actions), dtype=np.float64)
            self._sums[infoset_key] = arr
            self._action_lists[infoset_key] = tuple(actions)
        arr += weight * strategy

    def average(self, infoset_key: str) -> np.ndarray:
        """Return the normalized average strategy for one infoset.

        Returns a uniform distribution if the infoset was never
        visited (sum is 0).
        """
        arr = self._sums.get(infoset_key)
        if arr is None:
            return np.array([])
        total = arr.sum()
        if total > 0:
            return arr / total
        return np.full(len(arr), 1.0 / len(arr))

    def all_averages(self) -> Dict[str, Dict[str, float]]:
        """Snapshot every infoset's average strategy as {infoset: {action_name: prob}}."""
        result: Dict[str, Dict[str, float]] = {}
        for infoset_key, sums in self._sums.items():
            actions = self._action_lists[infoset_key]
            probs = self.average(infoset_key)
            result[infoset_key] = {a.name: float(p) for a, p in zip(actions, probs)}
        return result

    def num_infosets(self) -> int:
        return len(self._sums)

    def infoset_keys(self) -> List[str]:
        return list(self._sums.keys())

    def action_list(self, infoset_key: str) -> Tuple[Action, ...]:
        return self._action_lists[infoset_key]
