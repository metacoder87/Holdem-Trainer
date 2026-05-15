"""Kuhn poker - canonical CFR correctness anchor.

After 10k iterations of vanilla CFR or 2k of CFR+, the average
strategy must satisfy the textbook Nash invariants:

  - Player 0's Queen ("Q:") never bets (BET prob < 0.05).
  - Player 1's King after a bet ("K:b") always calls (BET prob > 0.95).
  - Player 1's Jack after a bet ("J:b") always folds (PASS prob > 0.95).
  - Game value to P0 at equilibrium is ~ -1/18.

Tolerances are intentionally loose; this is a smoke test that the
algorithm converges, not a precision benchmark.
"""
from __future__ import annotations

import pytest

from cfr.games.kuhn import KuhnPoker
from cfr.solvers.cfr_plus import CFRPlusSolver
from cfr.solvers.vanilla_cfr import VanillaCFRSolver


def _expected_value_p0(game: KuhnPoker, policy_dict: dict[str, dict[str, float]]) -> float:
    """Compute EV of the policy for player 0 by full tree traversal."""
    return _ev(game, game.initial_state(), policy_dict)


def _ev(game: KuhnPoker, state, policy_dict) -> float:
    if game.is_terminal(state):
        return game.utility(state, player=0)
    if game.is_chance(state):
        total = 0.0
        for next_state, prob in game.chance_outcomes(state):
            total += prob * _ev(game, next_state, policy_dict)
        return total
    actor = game.acting_player(state)
    actions = game.legal_actions(state)
    key = game.infoset_key(state, actor)
    probs = policy_dict.get(key, {})
    if not probs:
        # Uniform if unseen.
        probs = {a.name: 1.0 / len(actions) for a in actions}
    total = 0.0
    for action in actions:
        p = probs.get(action.name, 0.0)
        if p == 0.0:
            continue
        next_state = game.transition(state, action)
        total += p * _ev(game, next_state, policy_dict)
    return total


def test_cfr_plus_converges_on_kuhn():
    """CFR+ at 2k iters should hit Nash invariants."""
    game = KuhnPoker()
    solver = CFRPlusSolver(game)
    solver.train(2000)
    policy = solver.policy().as_dict()

    # Q never bets as P0.
    q_p0 = policy.get("Q:", {})
    assert q_p0.get("BET", 0.0) < 0.05, (
        f"P0 Q should not bet (Nash); got {q_p0!r}"
    )

    # K always calls a bet (P1 facing bet).
    k_after_bet = policy.get("K:b", {})
    assert k_after_bet.get("BET", 0.0) > 0.95, (
        f"P1 K should always call/bet facing bet; got {k_after_bet!r}"
    )

    # J always folds (passes) after a bet.
    j_after_bet = policy.get("J:b", {})
    assert j_after_bet.get("PASS", 0.0) > 0.95, (
        f"P1 J should always fold facing bet; got {j_after_bet!r}"
    )

    # Game value is ~-1/18 for P0 (≈ -0.0556).
    ev = _expected_value_p0(game, policy)
    assert -0.10 < ev < -0.02, f"EV(P0) at Kuhn Nash ≈ -1/18; got {ev:.4f}"


def test_vanilla_cfr_converges_on_kuhn():
    """Vanilla CFR at 10k iters should also pass."""
    game = KuhnPoker()
    solver = VanillaCFRSolver(game)
    solver.train(10000)
    policy = solver.policy().as_dict()

    q_p0 = policy.get("Q:", {})
    assert q_p0.get("BET", 0.0) < 0.10

    k_after_bet = policy.get("K:b", {})
    assert k_after_bet.get("BET", 0.0) > 0.90

    j_after_bet = policy.get("J:b", {})
    assert j_after_bet.get("PASS", 0.0) > 0.90


def test_kuhn_infoset_count_matches_textbook():
    """Sanity check: Kuhn has exactly 12 infosets (6 per player).

    P0 infosets: {J,Q,K} x {"", "pb"} = 6
    P1 infosets: {J,Q,K} x {"p", "b"} = 6
    """
    game = KuhnPoker()
    solver = CFRPlusSolver(game)
    solver.train(100)
    assert solver.num_infosets() == 12


def test_kuhn_action_probs_sum_to_one():
    game = KuhnPoker()
    solver = CFRPlusSolver(game)
    solver.train(500)
    policy = solver.policy().as_dict()
    for key, dist in policy.items():
        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-6, (
            f"Probs at {key} should sum to 1; got {total}"
        )
