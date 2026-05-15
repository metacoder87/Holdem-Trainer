"""CFR solver implementations."""

from cfr.solvers.cfr_plus import CFRPlusSolver  # noqa: F401
from cfr.solvers.vanilla_cfr import VanillaCFRSolver  # noqa: F401

__all__ = ["VanillaCFRSolver", "CFRPlusSolver"]
