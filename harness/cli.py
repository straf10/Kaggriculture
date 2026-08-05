"""Thin CLI wrapper (plan.md §2.4):

    python -m harness.cli play main.py starter --seed 17 --record
    python -m harness.cli compare main.py starter --seeds 0-11 --out runs/<name>
    python -m harness.cli profile main.py --seed 17
"""
import argparse
import json
from pathlib import Path

from harness.compare import compare
from harness.play import play
from harness.profile import report, timed
from harness.play import resolve_agent


def _parse_seeds(spec: str):
    seeds = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def _cmd_play(args):
    result = play(args.agent_a, args.agent_b, args.seed, steps=args.steps,
                   record=args.record, run_dir=Path(args.out) if args.out else None)
    print(f"seed={result.seed} agents={result.agents} rewards={result.rewards} "
          f"winner={result.winner} statuses={result.statuses}")
    if result.replay_path:
        print(f"replay: {result.replay_path}")


def _cmd_compare(args):
    seeds = _parse_seeds(args.seeds)
    out_dir = Path(args.out) if args.out else None
    result = compare(args.agent_a, args.agent_b, seeds, both_seats=not args.single_seat,
                      steps=args.steps, run_dir=out_dir)
    print(f"seeds={len(seeds)} both_seats={not args.single_seat}")
    print(f"wins_a={result.wins_a} wins_b={result.wins_b} ties={result.ties}")
    print(f"mean_diff={result.mean_diff:.1f} se_diff={result.se_diff:.1f} significant={result.significant}")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        results_path = out_dir / "results.json"
        results_path.write_text(json.dumps({
            "per_seed": result.per_seed,
            "mean_diff": result.mean_diff,
            "se_diff": result.se_diff,
            "wins_a": result.wins_a,
            "wins_b": result.wins_b,
            "ties": result.ties,
            "significant": result.significant,
        }, indent=2))
        print(f"results written to {results_path}")


def _cmd_profile(args):
    fn = resolve_agent(args.agent)
    wrapped, times = timed(fn)
    play(wrapped, args.opponent, args.seed, steps=args.steps, record=False)
    stats = report(times)
    print(f"n={stats['n']} max={stats['max']*1000:.1f}ms median={stats['median']*1000:.1f}ms "
          f"p99={stats['p99']*1000:.1f}ms total={stats['total']:.2f}s")
    print(f"3x margin check (max*3 < 1s): {'PASS' if stats['max'] * 3 < 1.0 else 'FAIL'}")


def main():
    parser = argparse.ArgumentParser(prog="python -m harness.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_play = sub.add_parser("play")
    p_play.add_argument("agent_a")
    p_play.add_argument("agent_b")
    p_play.add_argument("--seed", type=int, default=0)
    p_play.add_argument("--steps", type=int, default=720)
    p_play.add_argument("--record", action="store_true")
    p_play.add_argument("--out")
    p_play.set_defaults(func=_cmd_play)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("agent_a")
    p_compare.add_argument("agent_b")
    p_compare.add_argument("--seeds", default="0-11")
    p_compare.add_argument("--steps", type=int, default=720)
    p_compare.add_argument("--single-seat", action="store_true")
    p_compare.add_argument("--out")
    p_compare.set_defaults(func=_cmd_compare)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("agent")
    p_profile.add_argument("--opponent", default="pass")
    p_profile.add_argument("--seed", type=int, default=0)
    p_profile.add_argument("--steps", type=int, default=720)
    p_profile.set_defaults(func=_cmd_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
