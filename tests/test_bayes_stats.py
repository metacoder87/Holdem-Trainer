"""Tests for Bayesian rate + winrate inference."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.bayes_stats import (
    CredibleInterval,
    SMALL_SAMPLE_THRESHOLD,
    Z_95,
    bb100_credible_interval,
    beta_binomial_posterior,
    bootstrap_ci,
    merge_rates_into_payload,
    rate_excludes_target,
)


# ---------- Beta-Binomial posterior ----------


def test_beta_binomial_uniform_prior_centers_on_observed_rate():
    """Beta(1,1) prior + 30/100 -> posterior mean ~0.304 (regularized)."""
    post = beta_binomial_posterior(30, 100)
    # Posterior is Beta(31, 71), mean = 31/102 ~= 0.304
    assert math.isclose(post.value, 31 / 102, abs_tol=1e-9)
    # CI must contain the point estimate.
    assert post.ci_lower < post.value < post.ci_upper
    assert post.sample_size == 100


def test_beta_binomial_ci_narrows_with_sample_size():
    """Same rate, more trials -> tighter CI."""
    small = beta_binomial_posterior(15, 50)
    large = beta_binomial_posterior(300, 1000)
    small_width = small.ci_upper - small.ci_lower
    large_width = large.ci_upper - large.ci_lower
    assert large_width < small_width / 2.5


def test_beta_binomial_small_sample_flag_triggers_below_threshold():
    assert beta_binomial_posterior(10, 30).small_sample is True
    assert beta_binomial_posterior(50, 200).small_sample is False
    # Exact boundary case.
    assert beta_binomial_posterior(0, SMALL_SAMPLE_THRESHOLD - 1).small_sample is True
    assert beta_binomial_posterior(0, SMALL_SAMPLE_THRESHOLD).small_sample is False


def test_beta_binomial_handles_zero_trials():
    """Zero trials -> prior mean 0.5, full [0, 1] width."""
    post = beta_binomial_posterior(0, 0)
    assert post.value == 0.5
    assert post.sample_size == 0
    assert post.ci_lower <= 0.5 <= post.ci_upper


def test_beta_binomial_handles_edges_without_collapsing():
    """All-success / all-failure don't give zero-width CI."""
    all_calls = beta_binomial_posterior(100, 100)
    assert all_calls.value < 1.0  # regularized away from 1
    assert all_calls.ci_lower < all_calls.value

    all_folds = beta_binomial_posterior(0, 100)
    assert all_folds.value > 0.0
    assert all_folds.ci_upper > all_folds.value


def test_beta_binomial_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        beta_binomial_posterior(-1, 10)
    with pytest.raises(ValueError):
        beta_binomial_posterior(15, 10)  # successes > trials
    with pytest.raises(ValueError):
        beta_binomial_posterior(5, 10, alpha_prior=0)
    with pytest.raises(ValueError):
        beta_binomial_posterior(5, 10, beta_prior=-1)


# ---------- Target-band excludes ----------


def test_rate_excludes_target_when_ci_above_band():
    """High VPIP (60%) over 500 trials -> excludes 18-24% target."""
    post = beta_binomial_posterior(300, 500)
    assert rate_excludes_target(post, target_band=(0.18, 0.24)) == "high"


def test_rate_excludes_target_when_ci_below_band():
    post = beta_binomial_posterior(5, 500)
    assert rate_excludes_target(post, target_band=(0.18, 0.24)) == "low"


def test_rate_excludes_target_returns_none_inside_band():
    """22% rate over enough trials sits inside 18-24%."""
    post = beta_binomial_posterior(110, 500)
    assert rate_excludes_target(post, target_band=(0.18, 0.24)) is None


def test_rate_excludes_target_returns_none_when_ci_straddles_band():
    """Wide CI from small sample touching the band -> no flag."""
    # 6/30 = 20% point estimate, but the 95% CI is wide enough to
    # cover the entire 18-24% target band, so no leak fires.
    post = beta_binomial_posterior(6, 30)
    assert post.ci_lower < 0.24 and post.ci_upper > 0.18
    assert rate_excludes_target(post, target_band=(0.18, 0.24)) is None


# ---------- BB/100 ----------


def test_bb100_handles_empty_input():
    ci = bb100_credible_interval([], [])
    assert ci.value == 0.0
    assert ci.sample_size == 0
    assert ci.small_sample is True


def test_bb100_pooled_estimate_matches_total_over_total():
    """Pooled BB/100 over multiple sessions = sum(profit) / sum(hands) * 100."""
    profits = [100.0, -50.0, 30.0]  # in BBs
    hands = [200, 200, 100]
    ci = bb100_credible_interval(profits, hands)
    expected = (sum(profits) / sum(hands)) * 100.0
    assert math.isclose(ci.value, expected, abs_tol=1e-9)
    assert ci.sample_size == 500


def test_bb100_ci_grows_with_session_variance():
    """High variance in per-session BB/100 -> wider CI."""
    low_var = bb100_credible_interval([50.0, 60.0, 55.0], [100, 100, 100])
    high_var = bb100_credible_interval([-200.0, 400.0, 100.0], [100, 100, 100])
    assert (high_var.ci_upper - high_var.ci_lower) > (
        low_var.ci_upper - low_var.ci_lower
    )


def test_bb100_small_sample_at_under_1000_hands():
    ci = bb100_credible_interval([10.0, 5.0], [300, 200])  # 500 hands
    assert ci.small_sample is True
    ci2 = bb100_credible_interval([10.0] * 4, [300] * 4)  # 1200 hands
    assert ci2.small_sample is False


def test_bb100_input_length_mismatch_raises():
    with pytest.raises(ValueError):
        bb100_credible_interval([1.0, 2.0], [100])


# ---------- Bootstrap ----------


def test_bootstrap_mean_contains_population_mean():
    """The bootstrap CI for the mean must contain the sample mean."""
    rng = random.Random(7)
    values = [rng.gauss(50, 20) for _ in range(200)]
    ci = bootstrap_ci(values, statistic="mean", iterations=500, rng=random.Random(7))
    assert ci.ci_lower <= ci.value <= ci.ci_upper


def test_bootstrap_median_supported():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci = bootstrap_ci(values, statistic="median", iterations=200)
    assert ci.value == 3.0
    assert ci.ci_lower <= 3.0 <= ci.ci_upper


def test_bootstrap_rejects_invalid_statistic():
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], statistic="mode")


def test_bootstrap_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], confidence=1.5)


def test_bootstrap_handles_empty():
    ci = bootstrap_ci([])
    assert ci.value == 0.0
    assert ci.sample_size == 0


# ---------- Payload merger ----------


def test_merge_rates_into_payload_adds_ci_field():
    payload = {"vpip": 0.22}
    merge_rates_into_payload(payload, field="vpip", successes=22, trials=100)
    assert "vpip_ci" in payload
    assert "value" in payload["vpip_ci"]
    assert "ci_lower" in payload["vpip_ci"]
    assert "sample_size" in payload["vpip_ci"]
    assert payload["vpip"] == 0.22  # original unchanged


def test_merge_rates_into_payload_attaches_position_vs_target():
    payload = {}
    merge_rates_into_payload(
        payload,
        field="vpip",
        successes=300,
        trials=500,
        target_band=(0.18, 0.24),
    )
    assert payload["vpip_ci"]["position_vs_target"] == "high"


# ---------- Dataclass shape ----------


def test_credible_interval_as_dict_round_trip():
    ci = CredibleInterval(0.3, 0.2, 0.4, 100, False)
    d = ci.as_dict()
    assert d == {
        "value": 0.3,
        "ci_lower": 0.2,
        "ci_upper": 0.4,
        "sample_size": 100,
        "small_sample": False,
    }
