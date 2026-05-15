"""Solver base class.

Each solver owns a ``RegretTable`` and ``StrategyTable``, exposes a
``train(iterations)`` method, and (when training finishes) can hand the
average strategy back via ``policy()``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from cfr.core.strategy import RegretTable, StrategyTable
from cfr.games.base import Game
from cfr.policy import Policy


class Solver(ABC):
    """Abstract solver.

    Subclasses implement ``_iterate_once`` (one full traversal of the
    game tree updating regrets + strategy sums). ``train`` drives the
    iteration count and weighting.
    """

    def __init__(self, game: Game) -> None:
        self.game = game
        self.regrets = RegretTable()
        self.strategy_sums = StrategyTable()
        self.iteration: int = 0

    @abstractmethod
    def _iterate_once(self, iter_idx: int) -> None:
        """Run one CFR iteration: full traversal updating both tables."""

    def train(self, iterations: int) -> None:
        """Run ``iterations`` rounds of CFR.

        Iteration count is cumulative across calls so you can checkpoint
        mid-training by calling ``train`` repeatedly.
        """
        for _ in range(iterations):
            self.iteration += 1
            self._iterate_once(self.iteration)

    def policy(self) -> Policy:
        """Snapshot the current average strategy as a frozen Policy."""
        return Policy.from_strategy_table(self.strategy_sums)

    def num_infosets(self) -> int:
        return self.strategy_sums.num_infosets()
