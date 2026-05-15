"""Policy + .npz roundtrip tests."""
from __future__ import annotations

import random

from cfr.games.kuhn import KuhnPoker
from cfr.io import load, save
from cfr.policy import Policy
from cfr.solvers.cfr_plus import CFRPlusSolver


def test_policy_round_trip(tmp_path):
    game = KuhnPoker()
    solver = CFRPlusSolver(game)
    solver.train(300)
    original = solver.policy()

    out = tmp_path / "kuhn.npz"
    save(original, out)
    assert out.exists()
    assert out.stat().st_size > 0

    loaded = load(out)
    assert loaded.num_infosets() == original.num_infosets()
    for key in original.infoset_keys():
        a = original.probs(key)
        b = loaded.probs(key)
        assert a is not None and b is not None
        assert a.keys() == b.keys()
        for action, prob in a.items():
            assert abs(b[action] - prob) < 1e-9


def test_policy_returns_none_for_unknown_infoset():
    p = Policy({"foo": {"BET": 1.0}})
    assert p.probs("bar") is None
    assert "bar" not in p
    assert "foo" in p


def test_policy_sample_respects_distribution():
    """Heavily-weighted action should be sampled most of the time."""
    p = Policy({"infoset": {"BET": 0.95, "FOLD": 0.05}})
    rng = random.Random(7)
    counts = {"BET": 0, "FOLD": 0}
    for _ in range(1000):
        a = p.sample("infoset", rng)
        counts[a] += 1
    assert counts["BET"] > 900
