"""Counterfactual Regret Minimization library.

Decoupled from the live game engine: nothing under ``src.cfr`` imports
from ``src.game`` or ``backend.app``. The engine consumes only
``cfr.policy.Policy`` (typically loaded from disk) so the CPU-heavy
training loop never runs on the API request path.

Module layout::

    cfr/
      core/         Algorithm-agnostic data structures (InfoSet, Strategy)
      games/        Game definitions (Kuhn, Leduc, NLHE subgame)
      solvers/      Solver implementations (vanilla CFR, CFR+, MCCFR)
      abstractions/ Hand bucketing + action bucketing for NLHE
      policy.py     Frozen-strategy adapter the engine consumes
      io.py         Serialization (.npz)
"""

from cfr.core.action import Action  # noqa: F401
from cfr.core.strategy import RegretTable, StrategyTable  # noqa: F401
from cfr.policy import Policy  # noqa: F401

__all__ = ["Action", "RegretTable", "StrategyTable", "Policy"]
