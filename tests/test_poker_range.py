"""Tests for poker.range — Combo, Range, notation parsing, charts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game.card import Card, Rank, Suit
from poker.range import (
    Combo,
    PREFLOP_CHARTS,
    Range,
    all_combos_for_class,
    list_preflop_charts,
    parse_range_string,
    preflop_range,
)


# ---------- Combo ----------


def test_combo_make_orders_high_rank_first():
    a = Card(Suit.SPADES, Rank.KING)
    b = Card(Suit.HEARTS, Rank.ACE)
    combo = Combo.make(a, b)
    assert combo.high.rank == Rank.ACE
    assert combo.low.rank == Rank.KING


def test_combo_make_is_canonical_for_equal_ranks():
    """Two pairs with same ranks reduce to one combo regardless of input order."""
    a = Card(Suit.SPADES, Rank.ACE)
    b = Card(Suit.HEARTS, Rank.ACE)
    c1 = Combo.make(a, b)
    c2 = Combo.make(b, a)
    assert c1 == c2
    assert hash(c1) == hash(c2)


def test_combo_notation_round_trip():
    assert Combo.make(
        Card(Suit.SPADES, Rank.ACE), Card(Suit.SPADES, Rank.KING)
    ).to_notation() == "AKs"
    assert Combo.make(
        Card(Suit.SPADES, Rank.ACE), Card(Suit.HEARTS, Rank.KING)
    ).to_notation() == "AKo"
    assert Combo.make(
        Card(Suit.SPADES, Rank.TEN), Card(Suit.HEARTS, Rank.TEN)
    ).to_notation() == "TT"


# ---------- all_combos_for_class ----------


def test_class_pair_yields_six_combos():
    combos = all_combos_for_class("AA")
    assert len(combos) == 6
    assert all(c.is_pair() for c in combos)


def test_class_suited_yields_four_combos():
    combos = all_combos_for_class("AKs")
    assert len(combos) == 4
    assert all(c.is_suited() for c in combos)


def test_class_offsuit_yields_twelve_combos():
    combos = all_combos_for_class("AKo")
    assert len(combos) == 12
    assert all(not c.is_suited() for c in combos)


def test_class_both_yields_sixteen_combos():
    combos = all_combos_for_class("AK")
    assert len(combos) == 16


def test_class_lowercase_handled():
    combos = all_combos_for_class("aks")
    assert len(combos) == 4


def test_class_rejects_garbage():
    with pytest.raises(ValueError):
        all_combos_for_class("ZZ")


# ---------- parse_range_string ----------


def test_parse_basic_classes():
    parsed = parse_range_string("AA, KK, AKs")
    assert parsed == {"AA": 1.0, "KK": 1.0, "AKS": 1.0}


def test_parse_pair_plus():
    parsed = parse_range_string("TT+")
    # TT, JJ, QQ, KK, AA.
    assert set(parsed.keys()) == {"TT", "JJ", "QQ", "KK", "AA"}


def test_parse_class_plus():
    parsed = parse_range_string("ATs+")
    # ATs, AJs, AQs, AKs.
    assert set(parsed.keys()) == {"ATS", "AJS", "AQS", "AKS"}


def test_parse_weights():
    parsed = parse_range_string("AA:0.5, KK:0.25")
    assert parsed["AA"] == 0.5
    assert parsed["KK"] == 0.25


def test_parse_no_suffix_expands_to_both():
    parsed = parse_range_string("AK")
    assert "AKS" in parsed
    assert "AKO" in parsed


def test_parse_empty_returns_empty():
    assert parse_range_string("") == {}
    assert parse_range_string("   ") == {}


# ---------- Range ----------


def test_range_from_string_combo_count():
    """AA + AKs = 6 + 4 = 10 combos."""
    r = Range.from_string("AA, AKs")
    assert r.total_combos() == 10
    assert r.combo_count() == 10.0


def test_range_pair_plus_combo_count():
    """TT+ has 5 pairs * 6 combos = 30."""
    r = Range.from_string("TT+")
    assert r.total_combos() == 30


def test_range_card_removal_excludes_blockers():
    """If hero holds As, Range.combo_list should drop combos containing As."""
    r = Range.from_string("AA, KK")
    blockers = [Card(Suit.SPADES, Rank.ACE)]
    combos = r.combo_list(blockers=blockers)
    # AA originally has 6 combos. As is in 3 of them. Should drop to 3 + 6 KK = 9.
    assert len(combos) == 9


def test_range_remove_blockers_returns_new_range():
    r = Range.from_string("AA")
    blockers = [Card(Suit.SPADES, Rank.ACE), Card(Suit.HEARTS, Rank.ACE)]
    smaller = r.remove_blockers(blockers)
    # AA originally 6 combos; removing As + Ah leaves only the Ad-Ac pair (1).
    assert smaller.total_combos() == 1
    # Original unchanged.
    assert r.total_combos() == 6


def test_range_union_keeps_max_weight():
    a = Range.from_string("AA:0.5")
    b = Range.from_string("AA:0.8")
    merged = a.union(b)
    for combo in merged.combos():
        assert merged.weight(combo) == 0.8


def test_range_intersection_keeps_min_weight():
    a = Range.from_string("AA:0.8, KK:0.5")
    b = Range.from_string("AA:0.4, QQ:1.0")
    inter = a.intersection(b)
    # Only AA overlaps; weight = min(0.8, 0.4) = 0.4.
    for combo in inter.combos():
        assert inter.weight(combo) == 0.4


def test_range_class_map_averages_partial_weights():
    """Partial class with only some combos -> weight < 1.0."""
    r = Range({})
    # Add only one of the four AKs combos with weight 1.
    spades_ak = Combo.make(
        Card(Suit.SPADES, Rank.ACE), Card(Suit.SPADES, Rank.KING)
    )
    r2 = Range({spades_ak: 1.0})
    # Total class weight = 1.0 / 4 (full class count) = 0.25.
    assert r2.class_map()["AKs"] == 0.25


def test_range_empty_construction():
    assert Range.empty().total_combos() == 0
    assert Range.empty().combo_count() == 0.0


# ---------- Preflop charts ----------


def test_preflop_chart_names_exist():
    for name in ("UTG_OPEN", "BTN_OPEN", "BB_DEFEND", "TIGHT_3BET"):
        assert name in PREFLOP_CHARTS


def test_utg_open_returns_a_range():
    r = preflop_range("UTG_OPEN")
    assert isinstance(r, Range)
    # Tight UTG range — must contain AA but not 72o.
    aa_combo = Combo.make(
        Card(Suit.SPADES, Rank.ACE), Card(Suit.HEARTS, Rank.ACE)
    )
    junky = Combo.make(
        Card(Suit.SPADES, Rank.SEVEN), Card(Suit.HEARTS, Rank.TWO)
    )
    assert r.contains(aa_combo)
    assert not r.contains(junky)


def test_btn_open_wider_than_utg_open():
    """Button range should be strictly wider than UTG."""
    utg = preflop_range("UTG_OPEN")
    btn = preflop_range("BTN_OPEN")
    assert btn.total_combos() > utg.total_combos()


def test_list_preflop_charts_returns_class_maps():
    charts = list_preflop_charts()
    assert "UTG_OPEN" in charts
    assert "AA" in charts["UTG_OPEN"]
    assert charts["UTG_OPEN"]["AA"] == 1.0


def test_tight_3bet_is_narrow():
    """Tight 3-bet range is QQ+, AKs, AKo = 3 pairs + AKs + AKo."""
    r = preflop_range("TIGHT_3BET")
    # QQ (6) + KK (6) + AA (6) + AKs (4) + AKo (12) = 34.
    assert r.total_combos() == 34
