"""GTO advisor tests.

The advisor is the integration point between the cache and the live
gameplay code path. We need to verify:

  - Cache miss returns None (silent fallback, no crash).
  - Cache hit returns the documented payload shape.
  - Unparseable cards/positions return None instead of raising.
  - Frequency aggregation collapses fine-grained RAISE_* into RAISE.
  - EV-delta is 0 when hero plays GTO's modal action; negative
    otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make sure the backend path is importable.
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services import gto_advisor as advisor  # noqa: E402
from cfr.cache import SolverCache  # noqa: E402
from cfr.policy import Policy  # noqa: E402
from cfr.spot import SpotKey  # noqa: E402


def _baseline_decision() -> dict:
    return {
        "betting_round": "flop",
        "pot_total": 40,
        "hero_stack": 160,
        "hero_position": 0,
        "to_call": 0,
        "can_check": True,
        "board": ["A♥", "K♦", "2♣"],
        "hero_hole_cards": ["A♠", "Q♠"],
        "chosen_action": "check",
        "chosen_amount": 0,
    }


def _make_policy_for_decision(
    *,
    raise_freq: float = 0.7,
    call_freq: float = 0.2,
    fold_freq: float = 0.1,
    bucket: int = 9,  # AKx top pair -> high bucket
) -> Policy:
    """Build a policy that covers the infoset of _baseline_decision."""
    return Policy(
        {
            f"b={bucket}|h=": {
                "RAISE_0.66": raise_freq,
                "CHECK_OR_CALL": call_freq,
                "FOLD": fold_freq,
            },
        }
    )


def _spot_from(decision: dict, big_blind: int = 2) -> SpotKey:
    return SpotKey.from_decision(decision, big_blind=big_blind)


# ---------- Configure cache root for tests ----------


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Each test gets a fresh cache directory."""
    advisor.configure(tmp_path)
    yield
    advisor.reset_cache()


# ---------- Behavior tests ----------


def test_advisor_returns_none_on_empty_cache():
    assert advisor.gto_advice(_baseline_decision(), big_blind=2) is None


def test_advisor_returns_none_for_preflop_decision(tmp_path):
    decision = _baseline_decision()
    decision["betting_round"] = "preflop"
    decision["board"] = []
    assert advisor.gto_advice(decision, big_blind=2) is None


def test_advisor_returns_payload_on_cache_hit(tmp_path):
    decision = _baseline_decision()
    cache = SolverCache.open(tmp_path)
    spot = _spot_from(decision)
    cache.put(spot, _make_policy_for_decision(), iterations=1234)

    advisor.reset_cache()  # pick up new index entry
    advice = advisor.gto_advice(decision, big_blind=2)

    assert advice is not None
    assert advice["source"] == "cache"
    assert advice["iterations"] == 1234
    # The modal action is "raise" at 70%.
    assert advice["gto_action"] == "raise"
    assert advice["gto_frequency"] == 0.7
    # Hero "check" maps to CHECK_OR_CALL category.
    assert advice["hero_action"] == "check"
    assert advice["hero_frequency"] == 0.2
    # action_breakdown labels are user-facing.
    assert set(advice["action_breakdown"].keys()) == {"raise", "check", "fold"}


def test_advisor_ev_delta_is_zero_when_hero_picks_modal_action(tmp_path):
    decision = _baseline_decision()
    decision["chosen_action"] = "raise"
    cache = SolverCache.open(tmp_path)
    cache.put(_spot_from(decision), _make_policy_for_decision(), iterations=10)

    advisor.reset_cache()
    advice = advisor.gto_advice(decision, big_blind=2)
    assert advice is not None
    assert advice["ev_delta_bb"] == 0.0


def test_advisor_ev_delta_is_negative_when_hero_off_gto(tmp_path):
    decision = _baseline_decision()
    decision["chosen_action"] = "check"  # GTO raises 70% here
    cache = SolverCache.open(tmp_path)
    cache.put(_spot_from(decision), _make_policy_for_decision(), iterations=10)

    advisor.reset_cache()
    advice = advisor.gto_advice(decision, big_blind=2)
    assert advice is not None
    assert advice["ev_delta_bb"] is not None
    assert advice["ev_delta_bb"] < 0.0


def test_advisor_handles_missing_infoset(tmp_path):
    """Policy exists but hero's bucket/history isn't in it -> None."""
    decision = _baseline_decision()
    cache = SolverCache.open(tmp_path)
    # Policy only covers bucket=0, but AKx hero gets a high bucket.
    cache.put(_spot_from(decision), _make_policy_for_decision(bucket=0), iterations=10)

    advisor.reset_cache()
    advice = advisor.gto_advice(decision, big_blind=2)
    assert advice is None


def test_advisor_returns_none_for_bad_cards(tmp_path):
    decision = _baseline_decision()
    decision["hero_hole_cards"] = ["??", "??"]
    cache = SolverCache.open(tmp_path)
    cache.put(_spot_from(decision), _make_policy_for_decision(), iterations=10)

    advisor.reset_cache()
    assert advisor.gto_advice(decision, big_blind=2) is None


def test_advisor_aggregates_raise_sizes(tmp_path):
    """RAISE_0.33 + RAISE_0.66 + RAISE_1.0 collapse to a single RAISE freq."""
    decision = _baseline_decision()
    cache = SolverCache.open(tmp_path)
    bucket = 9
    cache.put(
        _spot_from(decision),
        Policy(
            {
                f"b={bucket}|h=": {
                    "RAISE_0.33": 0.3,
                    "RAISE_0.66": 0.3,
                    "RAISE_1.0": 0.2,
                    "CHECK_OR_CALL": 0.2,
                }
            }
        ),
        iterations=10,
    )

    advisor.reset_cache()
    advice = advisor.gto_advice(decision, big_blind=2)
    assert advice is not None
    # Raise freq aggregated: 0.3 + 0.3 + 0.2 = 0.8.
    assert advice["action_breakdown"]["raise"] == 0.8
    assert advice["action_breakdown"]["check"] == 0.2
    assert advice["gto_action"] == "raise"


def test_advisor_history_inference_for_facing_bet(tmp_path):
    """to_call > 0 maps to history='r'."""
    decision = _baseline_decision()
    decision["to_call"] = 20
    decision["can_check"] = False
    decision["chosen_action"] = "call"
    cache = SolverCache.open(tmp_path)
    bucket = 9
    cache.put(
        _spot_from(decision),
        Policy(
            {
                f"b={bucket}|h=r": {
                    "FOLD": 0.4,
                    "CHECK_OR_CALL": 0.5,
                    "RAISE_0.66": 0.1,
                }
            }
        ),
        iterations=10,
    )

    advisor.reset_cache()
    advice = advisor.gto_advice(decision, big_blind=2)
    assert advice is not None
    assert advice["gto_action"] == "call"
    assert advice["hero_action"] == "call"
    assert advice["action_breakdown"]["fold"] == 0.4
    assert advice["action_breakdown"]["call"] == 0.5
    assert advice["action_breakdown"]["raise"] == 0.1
