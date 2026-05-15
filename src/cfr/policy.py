"""Frozen-strategy lookup.

A ``Policy`` is what the game engine consumes: it doesn't know about
CFR, regrets, or iterations - it just asks "what's the action
distribution at this infoset?".

Policies can be built from a live ``StrategyTable`` (during training)
or loaded from an .npz file shipped as a GitHub Release Asset
(production). The engine path is the second one.
"""
from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional

from cfr.core.strategy import StrategyTable


class Policy:
    """Frozen mapping infoset_key -> {action_name: probability}.

    Construction:
      - ``Policy.from_strategy_table(...)`` - live snapshot during training.
      - ``Policy.load(path)`` - load from disk (see ``cfr.io``).

    Consumption:
      - ``probs(key)`` - returns the action distribution or None.
      - ``sample(key, rng)`` - sample one action by its distribution.
    """

    __slots__ = ("_table",)

    def __init__(self, table: Dict[str, Dict[str, float]]) -> None:
        self._table = dict(table)

    @classmethod
    def from_strategy_table(cls, table: StrategyTable) -> "Policy":
        return cls(table.all_averages())

    def probs(self, infoset_key: str) -> Optional[Dict[str, float]]:
        """Return the action distribution for ``infoset_key`` or None.

        Returning None (rather than raising) lets callers fall back to
        the engine's heuristic grading when an infoset wasn't covered
        by the precomputed solver run.
        """
        return self._table.get(infoset_key)

    def sample(
        self, infoset_key: str, rng: Optional[random.Random] = None
    ) -> Optional[str]:
        probs = self.probs(infoset_key)
        if probs is None:
            return None
        rng = rng or random.Random()
        actions, weights = zip(*probs.items())
        return rng.choices(actions, weights=weights)[0]

    def num_infosets(self) -> int:
        return len(self._table)

    def infoset_keys(self) -> List[str]:
        return list(self._table.keys())

    def merge(self, other: "Policy") -> "Policy":
        """Merge in another policy; other's entries take precedence."""
        merged = dict(self._table)
        merged.update(other._table)
        return Policy(merged)

    # Allow the policy to be used as a flat dict for serialization.
    def as_dict(self) -> Dict[str, Dict[str, float]]:
        return dict(self._table)

    def __len__(self) -> int:
        return len(self._table)

    def __contains__(self, key: str) -> bool:
        return key in self._table
