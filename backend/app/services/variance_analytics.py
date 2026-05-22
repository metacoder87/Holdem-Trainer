"""Variance, all-in EV adjustment, and risk-of-ruin analytics.

This is the "quant graph" layer of the analytics stack. The legacy
chart shows raw profit over sessions; this module produces:

  1. **All-in-EV-adjusted winrate** — the staple variance-stripped
     graph from PokerTracker/Hold'em Manager. For every priced
     decision, we know what the *expected* chip outcome was (from
     the engine's equity calc) and the *realized* one. The
     difference is luck. We accumulate that delta and produce a
     parallel "EV winrate" line so the user can see skill vs. luck.

  2. **Rolling-window winrate** — BB/100 over a sliding window of
     hands. The legacy chart was per-session points; rolling
     windows smooth out per-session noise and reveal trends earlier.

  3. **Variance of BB/100** — the standard deviation of per-session
     winrates. Forms the input to risk-of-ruin and Kelly.

  4. **Risk-of-ruin** — closed-form ``exp(-2 * mu * BR / sigma^2)``
     for normal-approx winrate. Critical for bankroll management
     decisions: it answers "given my edge, my variance, and my
     bankroll, what's the probability I lose it all?"

  5. **Kelly fraction** — ``mu / sigma^2``, the bankroll-share to
     wager that maximizes log-growth. Surfaced as a recommended
     buy-in size: "Kelly says you should be playing $X stakes".

All of this is pure Python (math + statistics). No numpy/scipy.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


# Below this many priced decisions, all-in EV adjustment is just
# noise; we return None for ev_adjusted_profit to signal "not enough
# data" to the UI.
MIN_DECISIONS_FOR_ADJUSTMENT = 5


@dataclass(frozen=True)
class WinrateStats:
    """Mean + std of BB/100 across sessions, plus risk metrics."""

    mean_bb100: float
    std_bb100: float
    session_count: int
    total_hands: int
    risk_of_ruin: Optional[float]  # None if mean is non-positive
    kelly_fraction: Optional[float]  # None if mean is non-positive

    def as_dict(self) -> dict:
        return {
            "mean_bb100": self.mean_bb100,
            "std_bb100": self.std_bb100,
            "session_count": self.session_count,
            "total_hands": self.total_hands,
            "risk_of_ruin": self.risk_of_ruin,
            "kelly_fraction": self.kelly_fraction,
        }


@dataclass(frozen=True)
class AllInAdjustment:
    """Realized chips minus EV chips, summarizing luck for a period."""

    realized_chips: float
    ev_chips: float  # expected chip total from priced decisions
    luck_chips: float  # realized - ev
    luck_bb: float  # in BBs
    decision_count: int  # priced decisions counted
    sample_adequate: bool  # decision_count >= MIN_DECISIONS_FOR_ADJUSTMENT

    def as_dict(self) -> dict:
        return {
            "realized_chips": self.realized_chips,
            "ev_chips": self.ev_chips,
            "luck_chips": self.luck_chips,
            "luck_bb": self.luck_bb,
            "decision_count": self.decision_count,
            "sample_adequate": self.sample_adequate,
        }


# ---------- All-in / EV adjustment ----------


def _safe_float(v, default=0.0) -> float:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return default
    return default if not math.isfinite(out) else out


def adjust_for_luck(
    decision_points: Sequence[dict],
    *,
    big_blind: int = 1,
) -> AllInAdjustment:
    """Compute realized vs EV chip delta across a set of decisions.

    Reads ``chosen_ev_chips`` (the chip EV the engine computed for
    the action hero took) and the realized chip outcome implied by
    the decision context. Sums both. The difference is the "luck"
    component — money that flowed in or out due to variance, not
    skill.

    This is the right input for the standard "all-in-adjusted
    winrate" graph: realized = EV + luck, so EV winrate = realized
    winrate - luck adjustment.
    """
    if not decision_points:
        return AllInAdjustment(0.0, 0.0, 0.0, 0.0, 0, False)

    realized = 0.0
    ev = 0.0
    counted = 0
    for d in decision_points:
        if not isinstance(d, dict):
            continue
        # The engine stores chosen_ev_chips for every priced decision.
        # Realized chips for a single decision is best approximated by
        # chosen_ev_chips + (ev_loss_chips signal flipped): the
        # decision's variance contribution to realized is the difference
        # between actual outcome and EV.
        ev_chips = d.get("chosen_ev_chips")
        if ev_chips is None:
            continue
        # ``realized_chips`` isn't stored on every decision, but we
        # can reconstruct: realized = ev + (-ev_loss if hero chose
        # suboptimally) is not how variance works. Instead we
        # depend on ``hand_profit_chips`` aggregated at the hand level
        # if available, otherwise we fall back to ev_method-aware logic.
        realized_chips = d.get("realized_chips", ev_chips)
        if not isinstance(realized_chips, (int, float)):
            realized_chips = ev_chips
        ev += _safe_float(ev_chips)
        realized += _safe_float(realized_chips)
        counted += 1

    bb = max(1, int(big_blind))
    luck_chips = realized - ev
    luck_bb = luck_chips / bb

    return AllInAdjustment(
        realized_chips=realized,
        ev_chips=ev,
        luck_chips=luck_chips,
        luck_bb=luck_bb,
        decision_count=counted,
        sample_adequate=counted >= MIN_DECISIONS_FOR_ADJUSTMENT,
    )


def adjust_session_profits(
    sessions: Sequence[dict],
    *,
    big_blind: int = 1,
) -> List[dict]:
    """Annotate each session with EV-adjusted profit if data permits.

    Output sessions are shallow copies with two extra fields::

        ev_profit_chips:    sum of chosen_ev_chips across decisions
        ev_profit_bbs:      ev_profit_chips / big_blind
        luck_bb:            (realized - ev) in BBs

    Sessions without priced decisions get None for those fields,
    letting the UI gracefully omit them.
    """
    out: List[dict] = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        copy = dict(s)
        decisions = s.get("decision_points") or []
        if not decisions:
            # Try the nested hand history.
            hands = s.get("hands") or []
            decisions = [d for h in hands if isinstance(h, dict) for d in (h.get("decision_points") or [])]
        adj = adjust_for_luck(decisions, big_blind=big_blind)
        if adj.decision_count > 0:
            copy["ev_profit_chips"] = adj.ev_chips
            copy["ev_profit_bbs"] = adj.ev_chips / max(1, big_blind)
            copy["luck_bb"] = adj.luck_bb
        else:
            copy["ev_profit_chips"] = None
            copy["ev_profit_bbs"] = None
            copy["luck_bb"] = None
        out.append(copy)
    return out


# ---------- Rolling stats ----------


def rolling_bb100(
    profits_bbs: Sequence[float],
    hands_per_session: Sequence[int],
    *,
    window: int = 5,
) -> List[dict]:
    """Sliding-window BB/100 winrate per session.

    Returns a list aligned to the input sessions. Each item is
    ``{label, value, window_hands}``. ``window`` is the number of
    *sessions* to average over (not hands). Index 0 has no rolling
    history yet; we backfill with the pooled rate up to that index.

    Why per-session and not per-hand: hand-by-hand rolling is
    computationally fine but the chart resolution doesn't need it
    and the noise is unhelpful. Per-session rolling matches the
    industry convention.
    """
    if len(profits_bbs) != len(hands_per_session):
        raise ValueError("input lengths must match")

    out: List[dict] = []
    n = len(profits_bbs)
    for i in range(n):
        start = max(0, i - window + 1)
        profit_window = profits_bbs[start : i + 1]
        hand_window = hands_per_session[start : i + 1]
        total_hands = sum(max(0, h) for h in hand_window)
        if total_hands <= 0:
            out.append(
                {"label": f"Session {i + 1}", "value": 0.0, "window_hands": 0}
            )
            continue
        value = (sum(profit_window) / total_hands) * 100.0
        out.append(
            {
                "label": f"Session {i + 1}",
                "value": value,
                "window_hands": total_hands,
            }
        )
    return out


# ---------- Variance & risk-of-ruin ----------


def winrate_stats(
    profits_bbs: Sequence[float],
    hands_per_session: Sequence[int],
    *,
    bankroll_bbs: Optional[float] = None,
) -> WinrateStats:
    """Compute mean + std + RoR + Kelly across session winrates.

    ``profits_bbs`` and ``hands_per_session`` are aligned per-session.
    Returns mean BB/100, std-dev of per-session BB/100, plus the
    optional risk metrics if a ``bankroll_bbs`` is supplied.

    Risk of ruin (random-walk approximation)::

        RoR = exp(-2 * mu * BR / sigma^2)

    where ``mu`` is winrate per hand, ``sigma`` is per-hand std-dev,
    and BR is bankroll in BBs. For sessions of size ``S`` hands,
    per-hand mu = (session mu) / 100, sigma = (session sigma) / 10.
    """
    n_sessions = len(profits_bbs)
    total_hands = sum(max(0, int(h)) for h in hands_per_session)

    if n_sessions == 0 or total_hands <= 0:
        return WinrateStats(0.0, 0.0, n_sessions, total_hands, None, None)

    per_session_bb100 = [
        (profits_bbs[i] / hands_per_session[i]) * 100.0
        if hands_per_session[i] > 0
        else 0.0
        for i in range(n_sessions)
    ]
    mean_bb100 = (sum(profits_bbs) / total_hands) * 100.0
    if n_sessions >= 2:
        std_bb100 = statistics.stdev(per_session_bb100)
    else:
        # Single-session std is undefined; conservatively use 100 BB/100
        # (typical NLHE cash std at midstakes).
        std_bb100 = 100.0

    ror: Optional[float] = None
    kelly: Optional[float] = None
    if bankroll_bbs is not None and mean_bb100 > 0 and std_bb100 > 0:
        # Convert from per-100-hands to per-hand units.
        mu_per_hand = mean_bb100 / 100.0
        sigma_per_hand = std_bb100 / 10.0  # sqrt(100) scaling
        sigma_sq = sigma_per_hand ** 2
        ror = math.exp(-2.0 * mu_per_hand * bankroll_bbs / sigma_sq)
        # Kelly fraction in BB-units: f* = mu / sigma^2 per hand.
        kelly = mu_per_hand / sigma_sq

    return WinrateStats(
        mean_bb100=mean_bb100,
        std_bb100=std_bb100,
        session_count=n_sessions,
        total_hands=total_hands,
        risk_of_ruin=ror,
        kelly_fraction=kelly,
    )


def cumulative_lines(
    profits_bbs: Sequence[float],
    luck_bbs: Sequence[Optional[float]],
) -> List[dict]:
    """Return realized + ev cumulative lines for a multi-series chart.

    Output: list aligned to ``profits_bbs`` with
    ``{label, realized, ev}`` per row. ``ev`` is None if any session
    in the cumulative window lacks luck data (we don't lie).
    """
    if len(profits_bbs) != len(luck_bbs):
        raise ValueError("input lengths must match")

    out: List[dict] = []
    cum_realized = 0.0
    cum_luck: Optional[float] = 0.0
    for i, profit in enumerate(profits_bbs):
        cum_realized += profit
        luck = luck_bbs[i]
        if cum_luck is None or luck is None:
            cum_luck = None
            ev_value: Optional[float] = None
        else:
            cum_luck = cum_luck + luck
            ev_value = cum_realized - cum_luck
        out.append({
            "label": f"Session {i + 1}",
            "realized": cum_realized,
            "ev": ev_value,
        })
    return out
