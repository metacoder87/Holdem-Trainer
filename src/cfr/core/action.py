"""Generic action enum used across games.

Games may extend this with custom semantic strings ("bet_0.5pot",
"bet_pot", "all_in") rather than maintaining per-game enums. Keeping a
single Action class keeps Policy / Strategy table keys uniform: every
infoset maps to ``dict[str, float]`` where the keys come from the
game's ``legal_actions`` method.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Action:
    """Symbolic action. Compared by ``name`` only.

    For Hold'em the convention is:
      - ``"FOLD"``
      - ``"CHECK"`` (only when current_bet == 0)
      - ``"CALL"``
      - ``"BET_<frac>"`` (e.g. ``"BET_0.5"``, ``"BET_1.0"``)
      - ``"RAISE_<frac>"`` (same convention, applies on top of existing bet)
      - ``"ALL_IN"``

    For Kuhn:
      - ``"PASS"`` / ``"BET"``
    For Leduc:
      - ``"CHECK"`` / ``"BET"`` / ``"CALL"`` / ``"RAISE"`` / ``"FOLD"``
    """

    name: str

    # Common action singletons (small wins on memory + comparison speed)
    FOLD: ClassVar["Action"]
    CHECK: ClassVar["Action"]
    CALL: ClassVar["Action"]
    PASS: ClassVar["Action"]
    BET: ClassVar["Action"]
    RAISE: ClassVar["Action"]
    ALL_IN: ClassVar["Action"]

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Action({self.name})"

    def __str__(self) -> str:
        return self.name


Action.FOLD = Action("FOLD")
Action.CHECK = Action("CHECK")
Action.CALL = Action("CALL")
Action.PASS = Action("PASS")
Action.BET = Action("BET")
Action.RAISE = Action("RAISE")
Action.ALL_IN = Action("ALL_IN")
