"""CFR training CLI.

Used by the ``cfr-models.yml`` GitHub Action to produce .npz strategy
files that get attached to a release. Also handy for local
development.

Usage:
    python -m cfr.cli train --game kuhn --solver cfr_plus --iterations 5000 --out kuhn.npz
    python -m cfr.cli train --game leduc --solver cfr_plus --iterations 10000 --out leduc.npz
    python -m cfr.cli train --game nlhe_subgame --solver cfr_plus --iterations 5000 \
                            --out river_3bet_pot.npz --pot 100 --stack 400 --buckets 10
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Type

from cfr.games.base import Game
from cfr.games.kuhn import KuhnPoker
from cfr.games.leduc import LeducHoldem
from cfr.games.nlhe_subgame import NLHEPostflopSubgame
from cfr.io import save
from cfr.solvers.base import Solver
from cfr.solvers.cfr_plus import CFRPlusSolver
from cfr.solvers.vanilla_cfr import VanillaCFRSolver


_GAMES = {
    "kuhn": KuhnPoker,
    "leduc": LeducHoldem,
}

_SOLVERS: dict[str, Type[Solver]] = {
    "vanilla_cfr": VanillaCFRSolver,
    "cfr_plus": CFRPlusSolver,
}


def _build_game(name: str, args: argparse.Namespace) -> Game:
    if name == "nlhe_subgame":
        return NLHEPostflopSubgame(
            num_hand_buckets=args.buckets,
            starting_pot=args.pot,
            starting_stack=args.stack,
            first_actor=args.first_actor,
        )
    cls = _GAMES[name]
    return cls()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cfr")
    sub = parser.add_subparsers(dest="cmd", required=True)

    train = sub.add_parser("train", help="Train a policy and save to .npz")
    train.add_argument(
        "--game",
        choices=list(_GAMES.keys()) + ["nlhe_subgame"],
        required=True,
    )
    train.add_argument("--solver", choices=list(_SOLVERS.keys()), default="cfr_plus")
    train.add_argument("--iterations", type=int, default=5000)
    train.add_argument("--out", type=Path, required=True)
    train.add_argument("--log-every", type=int, default=500)

    # NLHE subgame specific
    train.add_argument("--pot", type=int, default=100)
    train.add_argument("--stack", type=int, default=400)
    train.add_argument("--buckets", type=int, default=10)
    train.add_argument("--first-actor", type=int, default=0, choices=[0, 1])

    args = parser.parse_args(argv)

    if args.cmd == "train":
        return _run_train(args)
    return 1


def _run_train(args: argparse.Namespace) -> int:
    game = _build_game(args.game, args)
    solver_cls = _SOLVERS[args.solver]
    solver = solver_cls(game)

    start = time.perf_counter()
    last_log = start
    chunk = args.log_every
    remaining = args.iterations
    while remaining > 0:
        step = min(chunk, remaining)
        solver.train(step)
        remaining -= step
        now = time.perf_counter()
        rate = solver.iteration / (now - start)
        print(
            f"[{solver.iteration}/{args.iterations}] "
            f"{solver.num_infosets()} infosets | {rate:.1f} iter/s | "
            f"{now - last_log:.1f}s since last log",
            file=sys.stderr,
        )
        last_log = now

    args.out.parent.mkdir(parents=True, exist_ok=True)
    save(solver.policy(), args.out)
    elapsed = time.perf_counter() - start
    print(
        f"Saved policy to {args.out} ({solver.num_infosets()} infosets) "
        f"in {elapsed:.1f}s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
