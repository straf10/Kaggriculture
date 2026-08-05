"""Thin CLI wrapper (plan.md §2.4):

    python -m harness.cli play main.py starter --seed 17 --record
    python -m harness.cli compare main.py starter --seeds 0-23 --out runs/<name>
    python -m harness.cli profile main.py --seed 17
"""
import argparse
import json
import re
from pathlib import Path

from harness.compare import compare
from harness.play import play
from harness.profile import report


def _parse_seeds(spec: str):
    """"0-11,17,23-24" -> [0..11, 17, 23, 24]. Only non-negative ints/ranges are supported;
    a bare regex match (instead of str.split("-")) avoids misparsing a leading "-" as a
    range separator (review.md L1)."""
    seeds = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            seeds.extend(range(lo, hi + 1))
        else:
            seeds.append(int(part))
    return seeds


def _cmd_play(args):
    record = args.record or bool(args.out)  # --out implies --record (review.md L2)
    result = play(args.agent_a, args.agent_b, args.seed, steps=args.steps,
                   record=record, run_dir=Path(args.out) if args.out else None,
                   strict=not args.no_strict)
    print(f"seed={result.seed} agents={result.agents} rewards={result.rewards} "
          f"winner={result.winner} statuses={result.statuses} clean={result.clean}")
    if result.replay_path:
        print(f"replay: {result.replay_path}")


def _cmd_compare(args):
    seeds = _parse_seeds(args.seeds)
    out_dir = Path(args.out) if args.out else None
    result = compare(args.agent_a, args.agent_b, seeds, both_seats=not args.single_seat,
                      steps=args.steps, run_dir=out_dir, record=args.record,
                      strict=not args.no_strict, resume=args.resume)
    print(f"seeds={len(seeds)} both_seats={not args.single_seat}")
    print(f"wins_a={result.wins_a} wins_b={result.wins_b} ties={result.ties} "
          f"errors={len(result.errors)}")
    print(f"mean_diff={result.mean_diff:.1f} se_diff={result.se_diff:.1f} "
          f"ci95=({result.ci95[0]:.1f}, {result.ci95[1]:.1f})")
    print(f"significant={result.significant} practical={result.practical} "
          f"verdict={result.verdict}")
    if result.errors:
        print(f"errored seeds: {[e['seed'] for e in result.errors]}")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        results_path = out_dir / "results.json"
        results_path.write_text(json.dumps({
            "per_seed": result.per_seed,
            "errors": result.errors,
            "mean_diff": result.mean_diff,
            "se_diff": result.se_diff,
            "n_effective": result.n_effective,
            "t_crit": result.t_crit,
            "ci95": result.ci95,
            "wins_a": result.wins_a,
            "wins_b": result.wins_b,
            "ties": result.ties,
            "significant": result.significant,
            "practical": result.practical,
            "verdict": result.verdict,
        }, indent=2))
        print(f"results written to {results_path}")


def _cmd_profile(args):
    agent_a, agent_b = (args.agent, args.opponent) if args.seat == 0 else (args.opponent, args.agent)
    result = play(agent_a, agent_b, args.seed, steps=args.steps,
                   record=False, profile_seat=args.seat, strict=False)
    stats = report(result.turn_times, act_timeout=1.0)
    print(f"n={stats['n']} max={stats['max']*1000:.1f}ms median={stats['median']*1000:.1f}ms "
          f"p99={stats['p99']*1000:.1f}ms turn1={stats['turn1']*1000:.1f}ms total={stats['total']:.2f}s")
    checks = {
        "max*3 < 1s": stats["max"] * 3 < 1.0,
        "turn1 < 5s": stats["turn1"] < 5.0,
        "overage_used*3 < 60s": stats["overage_used"] * 3 < 60.0,
    }
    for label, ok in checks.items():
        print(f"{label}: {'PASS' if ok else 'FAIL'}")
    if not result.clean:
        print(f"WARNING: episode was not clean — health={result.health}")


def main():
    parser = argparse.ArgumentParser(prog="python -m harness.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_play = sub.add_parser("play")
    p_play.add_argument("agent_a")
    p_play.add_argument("agent_b")
    p_play.add_argument("--seed", type=int, default=0)
    p_play.add_argument("--steps", type=int, default=None)
    p_play.add_argument("--record", action="store_true")
    p_play.add_argument("--no-strict", action="store_true",
                         help="don't raise on a crashing/timing-out/invalid agent")
    p_play.add_argument("--out")
    p_play.set_defaults(func=_cmd_play)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("agent_a")
    p_compare.add_argument("agent_b")
    p_compare.add_argument("--seeds", default="0-23")
    p_compare.add_argument("--steps", type=int, default=None)
    p_compare.add_argument("--single-seat", action="store_true")
    p_compare.add_argument("--record", action="store_true")
    p_compare.add_argument("--no-strict", action="store_true",
                            help="don't raise on a crashing/timing-out/invalid agent")
    p_compare.add_argument("--resume", action="store_true",
                            help="skip seeds already present in <out>/results.jsonl")
    p_compare.add_argument("--out")
    p_compare.set_defaults(func=_cmd_compare)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("agent")
    p_profile.add_argument("--opponent", default="pass")
    p_profile.add_argument("--seed", type=int, default=0)
    p_profile.add_argument("--steps", type=int, default=None)
    p_profile.add_argument("--seat", type=int, default=0, choices=[0, 1])
    p_profile.set_defaults(func=_cmd_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
