"""SpotKey tests.

These pin the canonicalization invariants the cache depends on:

  - Suit-isomorphism: the same strategic spot collapses to one key.
  - Pot/SPR discretization is monotone and deterministic.
  - ``from_decision`` returns None for unparseable inputs (never
    raises) so the gameplay path is robust to missing data.
"""
from __future__ import annotations

import pytest

from cfr.spot import (
    SpotKey,
    canonical_board,
    pot_bb_discretize,
    spr_bucket_for,
)


# ---------- Board canonicalization ----------


def test_canonical_board_is_suit_isomorphic():
    """Same ranks + same suit-pattern -> identical key regardless of suits."""
    a = canonical_board(["A♥", "K♦", "2♣"])  # A-K-2 rainbow
    b = canonical_board(["A♠", "K♣", "2♦"])  # A-K-2 rainbow
    assert a == b == "Aa,Kb,2c"


def test_canonical_board_preserves_order():
    """Card order matters (it encodes which card came on turn/river)."""
    flop_then_turn = canonical_board(["A♥", "K♦", "2♣", "Q♥"])
    different_order = canonical_board(["K♦", "A♥", "2♣", "Q♥"])
    assert flop_then_turn != different_order


def test_canonical_board_paired_suits_get_same_letter():
    """Two hearts on the board both get 'a'."""
    out = canonical_board(["A♥", "K♥", "2♣"])
    assert out == "Aa,Ka,2b"


def test_canonical_board_handles_ascii_inputs():
    """Cards may arrive as 'Ks' or 'Kh' from non-engine code paths."""
    assert canonical_board(["As", "Kh", "2c"]) == canonical_board(
        ["A♠", "K♥", "2♣"]
    )


def test_canonical_board_handles_ten_glyph():
    """10 -> T in the canonical form."""
    out = canonical_board(["10♥", "9♦"])
    assert out == "Ta,9b"


def test_canonical_board_empty_returns_empty_string():
    assert canonical_board([]) == ""


def test_canonical_board_rejects_garbage():
    with pytest.raises(ValueError):
        canonical_board(["Zz"])


# ---------- Pot discretization ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0, 0),
        (3, 5),  # rounds up off the floor
        (7, 5),
        (8, 10),
        (50, 50),
        (97, 95),
        (101, 100),
        (123, 125),
        (450, 450),
        (501, 500),
        (1234, 1200),
    ],
)
def test_pot_bb_discretize_known_values(raw, expected):
    assert pot_bb_discretize(raw) == expected


def test_pot_bb_discretize_handles_floats():
    assert pot_bb_discretize(12.7) == 15  # nearest 5
    assert pot_bb_discretize(150.0) == 150  # nearest 25


# ---------- SPR bucketing ----------


@pytest.mark.parametrize(
    "spr, expected_bucket",
    [
        (0.0, 0),
        (2.9, 1),
        (3.0, 1),
        (3.5, 2),
        (6.0, 2),
        (8.0, 3),
        (12.0, 3),
        (20.0, 4),
        (25.0, 4),
        (30.0, 5),  # over the last bound
    ],
)
def test_spr_bucket_for(spr, expected_bucket):
    assert spr_bucket_for(spr) == expected_bucket


def test_spr_bucket_handles_nan_and_none():
    # Both treated as zero-SPR shoves (degenerate).
    assert spr_bucket_for(float("nan")) == 0
    assert spr_bucket_for(None) == 0


# ---------- SpotKey construction & signature ----------


def test_spot_key_signature_is_stable_across_construction():
    a = SpotKey(
        street="flop",
        board_canonical="Aa,Kb,2c",
        pot_bb=20,
        spr_bucket=2,
        first_actor=0,
    )
    b = SpotKey(
        street="flop",
        board_canonical="Aa,Kb,2c",
        pot_bb=20,
        spr_bucket=2,
        first_actor=0,
    )
    assert a == b
    assert hash(a) == hash(b)
    assert a.signature() == b.signature()


def test_spot_key_signature_is_filesystem_safe():
    """No comma in signatures -> safe to use as a filename basename."""
    key = SpotKey(
        street="turn",
        board_canonical="Aa,Kb,2c,Qa",
        pot_bb=40,
        spr_bucket=3,
        first_actor=1,
    )
    sig = key.signature()
    assert "," not in sig
    assert sig == "turn__Aa-Kb-2c-Qa__p40__spr3__fa1"


def test_spot_key_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        SpotKey(street="preflop", board_canonical="", pot_bb=0, spr_bucket=0, first_actor=0)
    with pytest.raises(ValueError):
        SpotKey(street="flop", board_canonical="Aa", pot_bb=10, spr_bucket=0, first_actor=2)
    with pytest.raises(ValueError):
        SpotKey(street="flop", board_canonical="Aa", pot_bb=-1, spr_bucket=0, first_actor=0)


# ---------- from_decision ----------


def _base_decision() -> dict:
    return {
        "betting_round": "flop",
        "pot_total": 60,
        "hero_stack": 240,
        "hero_position": 0,
        "board": ["A♥", "K♦", "2♣"],
        "hero_hole_cards": ["A♠", "Q♠"],
        "chosen_action": "call",
    }


def test_from_decision_happy_path():
    key = SpotKey.from_decision(_base_decision(), big_blind=2)
    assert key is not None
    assert key.street == "flop"
    assert key.board_canonical == "Aa,Kb,2c"
    # pot 60 / bb 2 = 30 BB -> rounds to 30
    assert key.pot_bb == 30
    # SPR = stack 240 / pot 60 = 4.0 -> bucket 2 (3 < x <= 6)
    assert key.spr_bucket == 2
    assert key.first_actor == 0


def test_from_decision_returns_none_for_preflop():
    decision = _base_decision()
    decision["betting_round"] = "preflop"
    decision["board"] = []
    assert SpotKey.from_decision(decision) is None


def test_from_decision_returns_none_for_missing_board():
    decision = _base_decision()
    decision["board"] = []
    decision["betting_round"] = "flop"
    assert SpotKey.from_decision(decision) is None


def test_from_decision_returns_none_for_zero_pot():
    decision = _base_decision()
    decision["pot_total"] = 0
    assert SpotKey.from_decision(decision) is None


def test_from_decision_returns_none_for_garbage_cards():
    decision = _base_decision()
    decision["board"] = ["??", "??", "??"]
    assert SpotKey.from_decision(decision) is None


def test_from_decision_collapses_isomorphic_spots():
    """Two boards with the same suit-pattern hit the same cache entry."""
    a = SpotKey.from_decision(_base_decision(), big_blind=2)
    other = _base_decision()
    other["board"] = ["A♠", "K♣", "2♦"]
    b = SpotKey.from_decision(other, big_blind=2)
    assert a is not None and b is not None
    assert a == b
    assert a.signature() == b.signature()


def test_from_decision_uses_hero_position_for_first_actor():
    d = _base_decision()
    d["hero_position"] = 0
    assert SpotKey.from_decision(d, big_blind=2).first_actor == 0
    d["hero_position"] = 3
    assert SpotKey.from_decision(d, big_blind=2).first_actor == 1
