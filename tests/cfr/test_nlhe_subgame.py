"""NLHE postflop subgame tests.

Subgame solving is heavier than Kuhn/Leduc; we only verify the
mechanical correctness here (tree well-formed, terminals reachable,
probabilities sum to 1). Convergence-quality testing happens out of
band via the cfr-models GitHub Action.
"""
from __future__ import annotations

import pytest

from cfr.games.nlhe_subgame import NLHEPostflopSubgame
from cfr.solvers.cfr_plus import CFRPlusSolver


def test_subgame_chance_nodes_deal_buckets_uniformly():
    """Chance distributions must sum to 1.0."""
    game = NLHEPostflopSubgame(num_hand_buckets=5)
    state = game.initial_state()
    outcomes = game.chance_outcomes(state)
    assert len(outcomes) == 5
    total = sum(p for _, p in outcomes)
    assert abs(total - 1.0) < 1e-9


def test_subgame_legal_actions_are_well_formed():
    """At root, no bet outstanding -> no FOLD legal."""
    game = NLHEPostflopSubgame(num_hand_buckets=3)
    state = game.initial_state()
    # Resolve chance nodes to a leaf player node.
    state = game.chance_outcomes(state)[0][0]  # P0 bucket
    state = game.chance_outcomes(state)[0][0]  # P1 bucket
    assert not game.is_chance(state)
    actions = game.legal_actions(state)
    action_names = {a.name for a in actions}
    assert "CHECK_OR_CALL" in action_names
    assert "FOLD" not in action_names  # no bet to fold against
    assert "ALL_IN" in action_names


def test_subgame_solver_runs():
    """1 iteration of CFR+ on a small subgame must not crash."""
    game = NLHEPostflopSubgame(
        num_hand_buckets=3,
        starting_pot=20,
        starting_stack=60,
    )
    solver = CFRPlusSolver(game)
    solver.train(1)
    # Tiny subgame: only a handful of infosets after 1 iteration.
    assert solver.num_infosets() >= 1


def test_subgame_short_training_yields_valid_policy():
    """Probabilities sum to 1, every action probability in [0, 1]."""
    game = NLHEPostflopSubgame(num_hand_buckets=3, starting_pot=20, starting_stack=40)
    solver = CFRPlusSolver(game)
    solver.train(20)
    policy = solver.policy().as_dict()
    assert len(policy) > 0
    for key, dist in policy.items():
        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-6, f"{key} sums to {total}"
        for action, prob in dist.items():
            assert 0.0 <= prob <= 1.0
