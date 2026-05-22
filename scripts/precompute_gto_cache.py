"""Train and persist a starter set of canonical postflop spots.

The runtime GTO advisor (``backend/app/services/gto_advisor.py``) is
useless without a populated cache. This script:

  1. Enumerates a small set of canonical heads-up flop spots that
     cover the common (board-texture × SPR-bucket × pot-size) cells.
  2. For each spot, trains an NLHE postflop subgame with CFR+ for
     ``ITERATIONS`` (default 1500). Buckets are equal-width on
     equity-vs-random and the abstraction is the existing
     river-only one (Sub-track 1.2 will upgrade this).
  3. Writes the resulting policy to the SolverCache so the advisor
     can read it from disk.

Runtime: ~1-2 minutes per spot at 1500 iterations × 5 buckets on a
laptop. The starter set has ~20 spots, so the full run is ~30 minutes.
Re-runs are idempotent (existing entries are skipped unless --force).

Usage::

    python scripts/precompute_gto_cache.py
    python scripts/precompute_gto_cache.py --iterations 3000 --force
    python scripts/precompute_gto_cache.py --output backend/cfr_artifacts
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cfr.abstractions.hand_bucketing import DEFAULT_POTENTIAL_WEIGHT  # noqa: E402
from cfr.cache import SolverCache  # noqa: E402
from cfr.games.nlhe_subgame import NLHEPostflopSubgame  # noqa: E402
from cfr.solvers.cfr_plus import CFRPlusSolver  # noqa: E402
from cfr.spot import SpotKey  # noqa: E402


DEFAULT_OUTPUT = REPO_ROOT / "backend" / "cfr_artifacts"
DEFAULT_ITERATIONS = 1500
DEFAULT_NUM_BUCKETS = 5  # smaller bucket count keeps each spot under ~1 min


# Canonical postflop boards covering the strategic texture space.
# These are the canonical_board strings produced by SpotKey, which we
# can't easily generate from cards without imports — so we list them
# directly.
#
# Flop texture groupings:
#   - Dry, A-high:        Aa,Kb,2c  (rainbow A-K-2)
#   - Dry, broadway:      Ka,Qb,9c  (rainbow K-Q-9)
#   - Wet, two-tone:      Ja,Tb,9a  (J-T-9, two hearts on JT)
#   - Paired:             8a,8b,3c  (8-8-3)
#   - Monotone:           Aa,Ja,7a  (all one suit)
#   - Low connected:      6a,5b,4c  (rainbow 6-5-4)
CANONICAL_FLOP_BOARDS = (
    "Aa,Kb,2c",
    "Ka,Qb,9c",
    "Ja,Tb,9a",
    "8a,8b,3c",
    "Aa,Ja,7a",
    "6a,5b,4c",
)

# Turn boards: each flop gets two follow-up turn cards covering the
# common runout shapes (a blank vs a connecting/draw-completing card).
CANONICAL_TURN_BOARDS = (
    # AK2 + blank 5 / + draw-bringing T
    "Aa,Kb,2c,5d",
    "Aa,Kb,2c,Td",
    # KQ9 + blank 4 / + connecting J
    "Ka,Qb,9c,4d",
    "Ka,Qb,9c,Jd",
    # JT9hh + completing 8 / + brick 2
    "Ja,Tb,9a,8c",
    "Ja,Tb,9a,2c",
    # 883 + blank A / + paired board (3)
    "8a,8b,3c,Ad",
    "8a,8b,3c,3d",
    # AJ7 monotone + non-suit K (counterfeit) / + suit 4 (4-flush)
    "Aa,Ja,7a,Kb",
    "Aa,Ja,7a,4a",
    # 654 rainbow + 3 (straight) / + Q (overcard)
    "6a,5b,4c,3d",
    "6a,5b,4c,Qd",
)

# Pot/SPR combinations that map to interesting strategic spots.
# (pot_bb, spr_bucket) — the spr bucket is the SpotKey bucket id.
POT_SPR_GRID = (
    (15, 2),   # 15 BB pot, mid SPR (3-6) — common 3-bet pot flop
    (30, 2),   # 30 BB pot, mid SPR — single-raised flop
    (50, 1),   # 50 BB pot, low SPR (0-3) — committed
)


def _solve_spot(
    spot: SpotKey,
    *,
    iterations: int,
    num_buckets: int,
) -> tuple[NLHEPostflopSubgame, CFRPlusSolver]:
    """Train one subgame for ``spot`` and return (game, trained_solver)."""
    # Convert spot's BB-relative sizes to absolute chip counts. We
    # choose chip values where 1 BB = 100 chips so the integer-rounded
    # bet sizes from action_bucketing don't drop to 0.
    chips_per_bb = 100
    starting_pot = spot.pot_bb * chips_per_bb
    # SPR -> stack. Map the bucket back to a representative SPR value.
    spr_midpoint = {0: 1.5, 1: 4.5, 2: 9.0, 3: 18.0, 4: 35.0}.get(
        spot.spr_bucket, 4.5
    )
    starting_stack = int(spr_midpoint * starting_pot)

    game = NLHEPostflopSubgame(
        num_hand_buckets=num_buckets,
        starting_pot=starting_pot,
        starting_stack=starting_stack,
        first_actor=spot.first_actor,
    )
    solver = CFRPlusSolver(game)
    solver.train(iterations)
    return game, solver


def _iter_spots(streets: tuple[str, ...] = ("flop", "turn")) -> list[SpotKey]:
    spots: list[SpotKey] = []
    if "flop" in streets:
        for board in CANONICAL_FLOP_BOARDS:
            for pot_bb, spr_bucket in POT_SPR_GRID:
                for first_actor in (0, 1):
                    spots.append(
                        SpotKey(
                            street="flop",
                            board_canonical=board,
                            pot_bb=pot_bb,
                            spr_bucket=spr_bucket,
                            first_actor=first_actor,
                        )
                    )
    if "turn" in streets:
        for board in CANONICAL_TURN_BOARDS:
            for pot_bb, spr_bucket in POT_SPR_GRID:
                for first_actor in (0, 1):
                    spots.append(
                        SpotKey(
                            street="turn",
                            board_canonical=board,
                            pot_bb=pot_bb,
                            spr_bucket=spr_bucket,
                            first_actor=first_actor,
                        )
                    )
    return spots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Cache root directory (default: backend/cfr_artifacts/)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"CFR iterations per spot (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--num-buckets",
        type=int,
        default=DEFAULT_NUM_BUCKETS,
        help=f"Hand buckets per player (default: {DEFAULT_NUM_BUCKETS})",
    )
    parser.add_argument(
        "--bucketing",
        choices=("plain", "potential"),
        default="potential",
        help=(
            "Hand abstraction method (default: potential). "
            "'plain' = E[HS] vs uniform opponent. "
            "'potential' = weighted blend of E[HS] and sqrt(E[HS^2]) "
            "so drawing hands get their own bucket on flop/turn."
        ),
    )
    parser.add_argument(
        "--potential-weight",
        type=float,
        default=DEFAULT_POTENTIAL_WEIGHT,
        help=(
            f"Mix weight in [0,1] used by 'potential' bucketing "
            f"(default: {DEFAULT_POTENTIAL_WEIGHT})."
        ),
    )
    parser.add_argument(
        "--streets",
        nargs="+",
        choices=("flop", "turn"),
        default=("flop", "turn"),
        help="Which streets to precompute (default: flop turn).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-train spots already in the cache",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N spots (useful for smoke testing)",
    )
    args = parser.parse_args()

    cache = SolverCache.open(args.output)
    spots = _iter_spots(tuple(args.streets))
    if args.limit is not None:
        spots = spots[: args.limit]

    print(
        f"Precomputing {len(spots)} spots into {args.output} "
        f"({args.iterations} iters, {args.num_buckets} buckets, "
        f"bucketing={args.bucketing}, weight={args.potential_weight})."
    )

    written = skipped = 0
    total_start = time.time()
    for idx, spot in enumerate(spots, 1):
        if cache.has(spot) and not args.force:
            print(f"  [{idx}/{len(spots)}] {spot.signature()} - skip (cached)")
            skipped += 1
            continue

        t0 = time.time()
        try:
            _, solver = _solve_spot(
                spot,
                iterations=args.iterations,
                num_buckets=args.num_buckets,
            )
        except Exception as exc:  # noqa: BLE001 - script is one-shot
            print(f"  [{idx}/{len(spots)}] {spot.signature()} - FAILED: {exc}")
            continue

        policy = solver.policy()
        cache.put(
            spot,
            policy,
            iterations=args.iterations,
            meta={
                "num_buckets": args.num_buckets,
                "bucketing": args.bucketing,
                "potential_weight": float(args.potential_weight),
                "trainer": "cfr_plus",
                "script": "precompute_gto_cache.py",
            },
        )
        written += 1
        elapsed = time.time() - t0
        print(
            f"  [{idx}/{len(spots)}] {spot.signature()} - "
            f"{policy.num_infosets()} infosets, {elapsed:.1f}s"
        )

    total_elapsed = time.time() - total_start
    print(
        f"\nDone. Wrote {written}, skipped {skipped}, "
        f"in {total_elapsed:.1f}s total."
    )
    print(f"Cache root: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
