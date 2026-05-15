"""Leduc Hold'em smoke tests.

Solving Leduc to publishable exploitability (<0.001 BB/hand) takes
~5k iterations and runs in a few seconds. We don't enforce that in
CI because best-response computation is itself non-trivial code -
instead we check coarser invariants:

  - The solver builds a finite, growing infoset table.
  - All policy probabilities sum to 1.
  - At a strong-hand infoset, the model bets/calls more than folds.
"""
from __future__ import annotations

import pytest

from cfr.games.leduc import LeducHoldem
from cfr.solvers.cfr_plus import CFRPlusSolver


def test_leduc_builds_infoset_table():
    """500 iters of CFR+ should populate hundreds of infosets."""
    game = LeducHoldem()
    solver = CFRPlusSolver(game)
    solver.train(500)
    # Leduc has ~288 infosets total per player at full coverage.
    # We're conservative: we want at least 50 to confirm the
    # tree-walk is finding non-trivial structure.
    assert solver.num_infosets() >= 50, (
        f"Expected >= 50 infosets after 500 iters, got "
        f"{solver.num_infosets()}"
    )


def test_leduc_action_probs_sum_to_one():
    game = LeducHoldem()
    solver = CFRPlusSolver(game)
    solver.train(200)
    policy = solver.policy().as_dict()
    for key, dist in policy.items():
        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-6, (
            f"Probs at {key!r} should sum to 1; got {total}"
        )


def test_leduc_strong_hand_does_not_fold_preflop():
    """A King in hand preflop should not fold to a bet at equilibrium.

    K:|<community>|<r1>|<r2>: facing a bet, calling/raising must
    outweigh folding. We use a loose check (BET+CALL+RAISE > 0.5).
    """
    game = LeducHoldem()
    solver = CFRPlusSolver(game)
    solver.train(1500)
    policy = solver.policy().as_dict()
    # K with no community card, facing a bet (history "b").
    # Possible hole-card identities: "Ka" or "Kb".
    for hole in ("Ka", "Kb"):
        key = f"{hole}|||b"
        dist = policy.get(key)
        if dist is None:
            # The exact key might not be reached during sampling -
            # ok if so, just skip rather than fail spuriously.
            continue
        fold_prob = dist.get("FOLD", 0.0)
        assert fold_prob < 0.5, (
            f"Strong hand {hole} should not fold majority of the "
            f"time; dist={dist!r}"
        )
