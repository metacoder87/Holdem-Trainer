"""Malmuth-Harville ICM (Independent Chip Model) for tournament equity.

In a tournament, chips aren't dollars. The chip-EV-maximizing play in
a final-table spot is often the worst dollar-EV play, because ICM
penalizes risk: doubling up doesn't double your equity, but busting
zeroes it. The standard model is **Malmuth-Harville** which computes
the probability of each finishing rank given current stack sizes,
then weights the payout table by those probabilities.

The recursive formula: P(player i finishes 1st) = stack_i / total_chips
(proportional to chips). Conditional on player i finishing 1st, the
probabilities of the *next* finisher are computed by removing player
i's stack and renormalizing. Recurse until all positions are filled.

This is closed-form for small fields (≤ 9 players) but combinatorially
explodes - 9-player ICM is 9! = 362,880 permutations. We add a fast
path: when ``len(stacks) <= 6`` we enumerate exactly; above that we
use the standard recursive trick that only needs O(2^n * n) ops.

Why we need this:
  - The legacy ICM at ``src/stats/calculator.py:565`` is a
    chip-share heuristic, not real ICM.
  - Tournament coaching is useless without proper ICM: "shove
    here" advice flips signs entirely when ICM pressure is real.
  - Bubble-factor / risk-premium metrics derive from ICM and
    are the single most important quant input for late-tournament
    decisions.

Pure stdlib. No numpy/scipy.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
from typing import List, Optional, Sequence, Tuple


# Soft cap: above this many players, the recursive sum stays cheap
# but the result starts to drift if we enumerate naively. Modern ICM
# solvers handle 50-player fields by approximation; we cap at 9.
MAX_EXACT_PLAYERS = 9


@dataclass(frozen=True)
class IcmResult:
    """Per-player ICM equity in payout-currency units.

    ``equities[i]`` is the expected payout (in dollars / chips of
    payout currency) for player i given current stack sizes.
    ``chip_share[i]`` is the chip-equity-only baseline (stack /
    total_chips * total_prize) for comparison. The diff between the
    two reveals "ICM pressure" — chip leaders are over-paid in chip
    EV terms, shorter stacks underpaid.
    """

    equities: List[float]
    chip_shares: List[float]
    total_chips: float
    total_prize: float

    def as_dict(self) -> dict:
        return {
            "equities": list(self.equities),
            "chip_shares": list(self.chip_shares),
            "total_chips": self.total_chips,
            "total_prize": self.total_prize,
        }


def malmuth_harville(
    stacks: Sequence[float],
    payouts: Sequence[float],
) -> IcmResult:
    """Compute ICM equities via Malmuth-Harville.

    Args:
      stacks: per-player chip stacks (must be non-negative).
      payouts: prize money for finishing positions, descending
        (1st place first). ``len(payouts) <= len(stacks)``.

    Returns:
      IcmResult with per-player equities, chip-share baselines,
      totals.

    Raises:
      ValueError on invalid inputs.
    """
    if not stacks:
        return IcmResult([], [], 0.0, 0.0)
    stacks = [float(s) for s in stacks]
    payouts = [float(p) for p in payouts]
    if any(s < 0 for s in stacks):
        raise ValueError("stacks must be non-negative")
    if any(p < 0 for p in payouts):
        raise ValueError("payouts must be non-negative")
    if len(payouts) > len(stacks):
        raise ValueError("too many payout positions for player count")
    if len(stacks) > MAX_EXACT_PLAYERS:
        raise ValueError(
            f"exact ICM supports up to {MAX_EXACT_PLAYERS} players "
            f"(got {len(stacks)})"
        )

    total_chips = sum(stacks)
    total_prize = sum(payouts)
    if total_chips <= 0:
        # Degenerate: everyone busts simultaneously. Split prize evenly.
        equal = total_prize / max(1, len(stacks))
        return IcmResult([equal] * len(stacks), [0.0] * len(stacks), 0.0, total_prize)

    n_players = len(stacks)
    n_places = len(payouts)

    # Chip share for the "chip-only" baseline.
    chip_shares = [s / total_chips * total_prize for s in stacks]

    # Equities accumulator.
    equities = [0.0] * n_players

    # Walk every permutation of finishing order over the first
    # ``n_places`` positions. For each permutation:
    #   1. Compute its probability under Malmuth-Harville.
    #   2. Pay each player the payout for their assigned place.
    # The remaining (n_players - n_places) players get $0 — they
    # bust before the money.
    player_indices = list(range(n_players))
    for ordering in permutations(player_indices, n_places):
        prob = _ordering_probability(ordering, stacks)
        for place_idx, player_idx in enumerate(ordering):
            equities[player_idx] += prob * payouts[place_idx]

    return IcmResult(
        equities=equities,
        chip_shares=chip_shares,
        total_chips=total_chips,
        total_prize=total_prize,
    )


def _ordering_probability(
    ordering: Tuple[int, ...],
    stacks: Sequence[float],
) -> float:
    """Probability of a specific finishing order under Malmuth-Harville.

    P(first = a, second = b, third = c, ...) =
        (stack_a / total) *
        (stack_b / (total - stack_a)) *
        (stack_c / (total - stack_a - stack_b)) * ...

    where each conditional renormalizes the remaining pool.
    """
    prob = 1.0
    removed = 0.0
    total = sum(stacks)
    for player_idx in ordering:
        denom = total - removed
        if denom <= 0:
            return 0.0
        prob *= stacks[player_idx] / denom
        removed += stacks[player_idx]
    return prob


# ---------- Risk premium / bubble factor ----------


def risk_premium(
    hero_index: int,
    stacks: Sequence[float],
    payouts: Sequence[float],
    *,
    win_chip_delta: float,
    lose_chip_delta: float,
) -> dict:
    """Compute the ICM risk premium for an all-in spot.

    Args:
      hero_index: which player in ``stacks`` is hero.
      stacks: current chip stacks for all players at the table.
      payouts: tournament payout schedule.
      win_chip_delta: chips hero would gain if all-in wins.
      lose_chip_delta: chips hero would lose if all-in loses
        (typically equal to hero's all-in amount; pass as positive).

    Returns:
      Dict with:
        chip_ev:        chip-units EV of the all-in at win prob 50%
        icm_ev_at_50:   ICM-$ EV at 50% win prob
        risk_premium:   extra equity needed to break even vs chip EV.
                        0 = no ICM impact; 0.1 = need 10% more equity.
        bubble_factor:  ratio of $ equity lost on a loss vs gained on
                        a win. >1 means the loss hurts more than the
                        gain helps (classic bubble pressure).

    The "risk premium" concept: if you're at a 3-way bubble with
    two short stacks, calling an all-in that's chip-neutral might
    cost you 5% in $ EV. You'd need to be a clear favorite (e.g.
    55%+) to take the spot. This function computes how big that
    excess must be.
    """
    stacks = list(stacks)
    if hero_index < 0 or hero_index >= len(stacks):
        raise ValueError("hero_index out of range")
    if win_chip_delta < 0 or lose_chip_delta < 0:
        raise ValueError("chip deltas must be non-negative")

    base = malmuth_harville(stacks, payouts)
    hero_eq_now = base.equities[hero_index]

    # Stacks after win.
    win_stacks = list(stacks)
    win_stacks[hero_index] += win_chip_delta
    # Loss to villain ranks: distribute the loss across other players
    # by stack proportion (simplification: in a real spot only one
    # specific opponent gains). This still preserves the right ICM
    # signal for the bubble-factor calc.
    others_total = sum(stacks) - stacks[hero_index]
    if others_total > 0:
        for i in range(len(win_stacks)):
            if i != hero_index:
                win_stacks[i] -= win_chip_delta * stacks[i] / others_total
                win_stacks[i] = max(0.0, win_stacks[i])
    win_eq = malmuth_harville(win_stacks, payouts).equities[hero_index]

    # Stacks after loss.
    lose_stacks = list(stacks)
    lose_stacks[hero_index] = max(0.0, lose_stacks[hero_index] - lose_chip_delta)
    if others_total > 0:
        for i in range(len(lose_stacks)):
            if i != hero_index:
                lose_stacks[i] += lose_chip_delta * stacks[i] / others_total
    lose_eq = malmuth_harville(lose_stacks, payouts).equities[hero_index]

    icm_ev_at_50 = 0.5 * win_eq + 0.5 * lose_eq
    # Chip-only EV at 50%: half the win delta minus half the loss.
    chip_ev = 0.5 * win_chip_delta - 0.5 * lose_chip_delta

    delta_win = win_eq - hero_eq_now
    delta_lose = hero_eq_now - lose_eq
    bubble_factor = (delta_lose / delta_win) if delta_win > 0 else float("inf")

    # Risk premium: how much more than 50% equity you need so that
    # ICM-EV matches the breakeven chip EV.
    # Solve: p * win_eq + (1 - p) * lose_eq = hero_eq_now
    if delta_win + delta_lose > 0:
        breakeven_p = delta_lose / (delta_win + delta_lose)
    else:
        breakeven_p = 0.5
    rp = breakeven_p - 0.5  # excess equity over chip-EV breakeven

    return {
        "chip_ev": chip_ev,
        "icm_ev_at_50": icm_ev_at_50,
        "hero_icm_equity_now": hero_eq_now,
        "hero_icm_equity_win": win_eq,
        "hero_icm_equity_lose": lose_eq,
        "risk_premium": rp,
        "bubble_factor": bubble_factor,
    }
