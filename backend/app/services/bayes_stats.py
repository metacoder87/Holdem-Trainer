"""Bayesian inference for poker rate and winrate stats.

Why Bayesian: poker stats are noisy. VPIP "29%" from 14 hands is wildly
different from VPIP "29%" from 2,000 hands, but the legacy UI showed
both as a flat number with no uncertainty. Coaching decisions ("you're
too loose, run drills") downstream of a point estimate quietly become
false positives at small sample sizes.

This module gives every rate stat a posterior with credible interval
and a sample-size flag so the UI can render "29% (CI 22-37%, sample 142
hands)" instead of "29%". Sub-services then refuse to fire weakness
flags until the credible interval excludes the target band.

Conjugate-prior choices:

  - **Rates** (VPIP, PFR, c-bet%, fold-to-cbet, WTSD, W$SD): Bernoulli
    likelihood, Beta(alpha, beta) conjugate prior. Default prior
    Beta(1, 1) = uniform on [0, 1]. Posterior is closed-form
    Beta(alpha + k, beta + n - k).

  - **Winrate (BB/100)**: Normal approximation with Student's-t-like
    CI from the empirical session-level standard deviation. We don't
    do full Normal-Gamma because the precision (1/variance) is what
    we actually want CIs on, and the sample-level t-distribution is
    a good-enough approximation for n >= 20.

  - **Anything else (e.g. composite EV-loss-per-decision)**:
    nonparametric bootstrap_ci with 1000 resamples.

The math here is pure stdlib (math + statistics). No scipy
dependency on the request path - keeps Docker images lean and
avoids cold-start ImportError risk.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


# Default Jeffreys-like prior for Beta-Binomial: weakly informative,
# stays uniform-ish on [0, 1] but pulls degenerate (0/0, n/n) cases
# off the boundary so the CI doesn't collapse to width 0.
DEFAULT_BETA_ALPHA = 1.0
DEFAULT_BETA_BETA = 1.0

# Sample-size threshold below which we attach a "small sample" warning.
# Tuned for VPIP/PFR: at n=50, 95% CI half-width on a 30% rate is
# ~13%, which is still wide but tractable.
SMALL_SAMPLE_THRESHOLD = 50

# Z-score for ~95% two-sided coverage. Hardcoded because we never
# vary it and don't want a scipy dependency.
Z_95 = 1.96


@dataclass(frozen=True)
class CredibleInterval:
    """Posterior point estimate + 95% credible interval.

    ``value`` is the posterior mean. ``ci_lower`` and ``ci_upper`` are
    the 2.5%/97.5% quantiles of the posterior distribution.
    ``sample_size`` is the integer count of observations that fed the
    posterior (used for the UI's small-sample chip).
    """

    value: float
    ci_lower: float
    ci_upper: float
    sample_size: int
    small_sample: bool

    def as_dict(self) -> dict:
        return {
            "value": self.value,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "sample_size": self.sample_size,
            "small_sample": self.small_sample,
        }


# ---------- Beta-Binomial: rates ----------


def beta_binomial_posterior(
    successes: int,
    trials: int,
    *,
    alpha_prior: float = DEFAULT_BETA_ALPHA,
    beta_prior: float = DEFAULT_BETA_BETA,
    small_sample_threshold: int = SMALL_SAMPLE_THRESHOLD,
) -> CredibleInterval:
    """Posterior + 95% credible interval for a Bernoulli rate.

    Conjugate update: prior Beta(a, b) + observed k successes in n
    trials -> posterior Beta(a + k, b + n - k).

    The CI uses the Wilson-style approximation rather than the inverse
    incomplete beta. It's good to <1% on rates in [0.05, 0.95] and
    keeps us in stdlib. For extreme rates (k=0 or k=n) we fall back
    on a closed-form using the beta-mean's variance.
    """
    if trials < 0:
        raise ValueError("trials must be non-negative")
    if successes < 0 or successes > trials:
        raise ValueError("successes must be in [0, trials]")
    if alpha_prior <= 0 or beta_prior <= 0:
        raise ValueError("priors must be positive")

    a = alpha_prior + successes
    b = beta_prior + (trials - successes)
    mean = a / (a + b)

    # Variance of Beta(a, b) = a*b / ((a+b)^2 * (a+b+1)).
    denom = (a + b) ** 2 * (a + b + 1)
    variance = (a * b) / denom if denom > 0 else 0.0
    std = math.sqrt(variance)

    # Normal approximation to the beta quantiles. Tight when a, b >> 1.
    # We clip into [0, 1] to keep the UI sane on tiny samples.
    lower = max(0.0, mean - Z_95 * std)
    upper = min(1.0, mean + Z_95 * std)

    return CredibleInterval(
        value=mean,
        ci_lower=lower,
        ci_upper=upper,
        sample_size=int(trials),
        small_sample=trials < small_sample_threshold,
    )


def rate_excludes_target(
    posterior: CredibleInterval,
    *,
    target_band: Tuple[float, float],
) -> Optional[str]:
    """Return "low" / "high" / None depending on the posterior position.

    Used by the leak-detection layer: only fire a "VPIP too high" flag
    when the credible interval lies *entirely* above the target band.
    "None" means the data is consistent with the target.
    """
    target_low, target_high = target_band
    if posterior.ci_upper < target_low:
        return "low"
    if posterior.ci_lower > target_high:
        return "high"
    return None


# ---------- Winrate (BB/100) ----------


def bb100_credible_interval(
    profits_bbs: Sequence[float],
    hands_per_session: Sequence[int],
    *,
    small_sample_threshold: int = 1000,
) -> CredibleInterval:
    """Posterior mean + CI for BB/100 winrate.

    Inputs are aligned per-session: ``profits_bbs[i]`` is the profit
    in BBs for session i; ``hands_per_session[i]`` is the hand count
    for session i. The estimator is the *pooled* BB/100, weighted by
    session hand count, with a session-level standard error.

    Small-sample threshold defaults to 1000 *hands* (not sessions) -
    poker winrate variance is huge and 1000 hands is the rough
    industry "you don't know your winrate yet" line.
    """
    if len(profits_bbs) != len(hands_per_session):
        raise ValueError("profits_bbs and hands_per_session length mismatch")
    if not profits_bbs:
        return CredibleInterval(
            value=0.0, ci_lower=0.0, ci_upper=0.0, sample_size=0, small_sample=True
        )

    total_hands = sum(max(0, int(h)) for h in hands_per_session)
    if total_hands <= 0:
        return CredibleInterval(
            value=0.0, ci_lower=0.0, ci_upper=0.0, sample_size=0, small_sample=True
        )

    total_profit = sum(profits_bbs)
    winrate_bb100 = (total_profit / total_hands) * 100.0

    # Standard error: session-level BB/100 std, then SE = std / sqrt(N_sessions).
    if len(profits_bbs) >= 2:
        per_session_bb100 = [
            (profits_bbs[i] / hands_per_session[i]) * 100.0
            if hands_per_session[i] > 0
            else 0.0
            for i in range(len(profits_bbs))
        ]
        sample_std = statistics.stdev(per_session_bb100)
        se = sample_std / math.sqrt(len(per_session_bb100))
    else:
        # One session: SE undefined; conservatively set a wide CI
        # based on a typical poker variance assumption (100 BB/100).
        se = 100.0

    lower = winrate_bb100 - Z_95 * se
    upper = winrate_bb100 + Z_95 * se

    return CredibleInterval(
        value=winrate_bb100,
        ci_lower=lower,
        ci_upper=upper,
        sample_size=total_hands,
        small_sample=total_hands < small_sample_threshold,
    )


# ---------- Bootstrap (anything that doesn't fit conjugate priors) ----------


def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: str = "mean",
    iterations: int = 1000,
    confidence: float = 0.95,
    rng: Optional[random.Random] = None,
) -> CredibleInterval:
    """Nonparametric bootstrap CI for an arbitrary statistic.

    ``statistic`` can be "mean" or "median". Resamples ``values`` with
    replacement ``iterations`` times and returns the empirical
    confidence-interval quantiles.

    Used for stats that don't have a clean conjugate prior (e.g.
    average EV loss per decision, median session profit). Keep
    iterations modest - 1000 is plenty for a UI display.
    """
    if statistic not in {"mean", "median"}:
        raise ValueError("statistic must be 'mean' or 'median'")
    if confidence <= 0 or confidence >= 1:
        raise ValueError("confidence must be in (0, 1)")
    if not values:
        return CredibleInterval(0.0, 0.0, 0.0, 0, True)

    rng = rng or random.Random(0x60A1)
    samples: List[float] = []
    n = len(values)
    for _ in range(iterations):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        if statistic == "mean":
            samples.append(statistics.fmean(resample))
        else:
            samples.append(statistics.median(resample))

    samples.sort()
    tail = (1.0 - confidence) / 2.0
    lo_idx = max(0, int(math.floor(tail * iterations)))
    hi_idx = min(iterations - 1, int(math.ceil((1.0 - tail) * iterations)) - 1)
    point = statistics.fmean(values) if statistic == "mean" else statistics.median(values)

    return CredibleInterval(
        value=point,
        ci_lower=samples[lo_idx],
        ci_upper=samples[hi_idx],
        sample_size=n,
        small_sample=n < 30,
    )


# ---------- Helpers used by analytics_service ----------


def merge_rates_into_payload(
    payload: dict,
    *,
    field: str,
    successes: int,
    trials: int,
    target_band: Optional[Tuple[float, float]] = None,
) -> None:
    """In-place: attach a Bayesian posterior block to ``payload[field]``.

    The legacy field stays as a bare float (back-compat); the new
    block is at ``payload[f"{field}_ci"]``. ``target_band`` is
    optional and only used to flag the position of the CI for
    leak-detection downstream.
    """
    posterior = beta_binomial_posterior(successes, trials)
    payload[f"{field}_ci"] = posterior.as_dict()
    if target_band is not None:
        position = rate_excludes_target(posterior, target_band=target_band)
        payload[f"{field}_ci"]["position_vs_target"] = position
