"""Bet-size discretization for NLHE.

A truly continuous bet space is intractable for CFR. Real-world
solvers use a small set of canonical bet sizes per street. We
default to fractions of pot used in industry solvers (PioSolver,
GTO+):

  - 0.33 pot (small block bet)
  - 0.66 pot (standard cbet)
  - 1.00 pot (overbet pressure)
  - all-in

This gives ~3-4 branches per action node, which keeps the tree
size manageable while covering the strategic flavors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from cfr.core.action import Action


# Canonical postflop bet-size fractions. Tweak by experiment.
DEFAULT_BET_FRACTIONS = (0.33, 0.66, 1.0)


@dataclass(frozen=True, slots=True)
class BetSizeBucket:
    """A discrete bet size, as a fraction of the current pot."""

    fraction: float

    @property
    def action_name(self) -> str:
        return f"BET_{self.fraction:.2f}".rstrip("0").rstrip(".")

    def chip_amount(self, pot: int) -> int:
        return max(1, int(round(self.fraction * pot)))


def make_bet_actions(
    fractions: tuple = DEFAULT_BET_FRACTIONS,
) -> List[Action]:
    """Build the canonical postflop Action set:

    [CHECK/CALL, FOLD, RAISE_0.33, RAISE_0.66, RAISE_1.0, ALL_IN]

    Caller decides whether CHECK or CALL is appropriate based on
    current state (the action set just provides the *names*).
    """
    actions = [Action("CHECK_OR_CALL"), Action("FOLD")]
    for f in fractions:
        actions.append(Action(f"RAISE_{f:.2f}".rstrip("0").rstrip(".")))
    actions.append(Action.ALL_IN)
    return actions
