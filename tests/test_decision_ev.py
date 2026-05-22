import pytest

from game.game_engine import _build_priced_ev_fields


def test_priced_ev_profitable_call_has_no_loss():
    fields = _build_priced_ev_fields(
        chosen_action="call",
        pot_total=100,
        call_amount=50,
        equity_estimate=0.5,
        big_blind=10,
    )

    assert fields["chosen_ev_chips"] == pytest.approx(25.0)
    assert fields["best_ev_chips"] == pytest.approx(25.0)
    assert fields["ev_loss_bb"] == pytest.approx(0.0)
    assert fields["ev_method"] == "call_fold_continue_v1"


def test_priced_ev_losing_call_records_bb_loss():
    fields = _build_priced_ev_fields(
        chosen_action="call",
        pot_total=100,
        call_amount=50,
        equity_estimate=0.2,
        big_blind=10,
    )

    assert fields["chosen_ev_chips"] == pytest.approx(-20.0)
    assert fields["best_ev_chips"] == pytest.approx(0.0)
    assert fields["ev_loss_chips"] == pytest.approx(20.0)
    assert fields["ev_loss_bb"] == pytest.approx(2.0)


def test_priced_ev_correct_fold_has_no_loss():
    fields = _build_priced_ev_fields(
        chosen_action="fold",
        pot_total=100,
        call_amount=50,
        equity_estimate=0.2,
        big_blind=10,
    )

    assert fields["chosen_ev_chips"] == pytest.approx(0.0)
    assert fields["best_ev_chips"] == pytest.approx(0.0)
    assert fields["ev_loss_bb"] == pytest.approx(0.0)


def test_priced_ev_missing_equity_keeps_loss_null():
    fields = _build_priced_ev_fields(
        chosen_action="call",
        pot_total=100,
        call_amount=50,
        equity_estimate=0.0,
        big_blind=10,
    )

    assert fields["chosen_ev_chips"] is None
    assert fields["best_ev_chips"] is None
    assert fields["ev_loss_bb"] is None
    assert fields["ev_method"] == "missing_equity"
