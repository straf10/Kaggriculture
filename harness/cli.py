"""Thin CLI wrapper (plan.md §2.4):

    python -m harness.cli play main.py starter --seed 17 --record
    python -m harness.cli compare main.py starter --seeds 0-23 --out runs/<name>
    python -m harness.cli profile main.py --seed 17
    python -m harness.cli report runs/<name>/seed17_seat0-main.py_seat1-starter.json.gz

Set KAGGRI_DEBUG=1 before `play`/`compare` (plan.md §1.5.4) to capture G11 receipts alongside
the replay, so `report` can compute `unexplained_noops` instead of reporting "not measured".
"""
import argparse
import json
import os
import re
from pathlib import Path

from harness.checkpoint import DEFAULT_CHECKPOINT_ROOT, create_checkpoint
from harness.compare import VALID_STAGES, compare
from harness.play import play
from harness.profile import report
from harness.report import load_receipts, load_replay, write_report
from harness.seeds import DEV_SEEDS, HOLDOUT_SEEDS, SMOKE_SEEDS

_SEED_SETS = {"dev": DEV_SEEDS, "holdout": HOLDOUT_SEEDS, "smoke": SMOKE_SEEDS}


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
    record = args.record or bool(args.out) or args.render_html  # --out/--render-html imply --record
    result = play(args.agent_a, args.agent_b, args.seed, steps=args.steps,
                   record=record, run_dir=Path(args.out) if args.out else None,
                   strict=not args.no_strict, render_html=args.render_html)
    print(f"seed={result.seed} agents={result.agents} rewards={result.rewards} "
          f"winner={result.winner} statuses={result.statuses} clean={result.clean}")
    if result.replay_path:
        print(f"replay: {result.replay_path}")
    if result.html_path:
        print(f"html: {result.html_path}")
    if result.receipts_path:
        print(f"receipts: {result.receipts_path}")


_STAGE_BY_SEED_SET = {"dev": "dev-screen", "holdout": "holdout-confirm"}  # smoke: no stage, never a GO


def _cmd_compare(args):
    seeds = list(_SEED_SETS[args.seed_set]) if args.seed_set else _parse_seeds(args.seeds)
    out_dir = Path(args.out) if args.out else None
    stage = args.stage if args.stage is not None else _STAGE_BY_SEED_SET.get(args.seed_set)
    result = compare(args.agent_a, args.agent_b, seeds, both_seats=not args.single_seat,
                      steps=args.steps, run_dir=out_dir, record=args.record,
                      strict=not args.no_strict, resume=args.resume, workers=args.workers,
                      metrics=args.metrics, stage=stage)
    print(f"seeds={len(seeds)} both_seats={not args.single_seat} workers={args.workers}")
    print(f"stage={result.stage} metrics_checked={result.metrics_checked}")
    print(f"wins_a={result.wins_a} wins_b={result.wins_b} ties={result.ties} "
          f"errors={len(result.errors)}")
    print(f"episode_wins_a={result.episode_wins_a} episode_wins_b={result.episode_wins_b} "
          f"episode_ties={result.episode_ties} median_bank_a={result.median_bank_a:.1f}")
    print(f"mean_diff={result.mean_diff:.1f} se_diff={result.se_diff:.1f} "
          f"ci95=({result.ci95[0]:.1f}, {result.ci95[1]:.1f})")
    print(f"significant={result.significant} practical={result.practical} "
          f"verdict={result.verdict}")
    if result.metrics_checked:
        print(f"water_weeds_lost_a={result.water_weeds_lost_a} "
              f"plant_decay_units_lost_a={result.plant_decay_units_lost_a} "
              f"animals_escaped_a={result.animals_escaped_a} "
              f"clipped_production_ticks_a={result.clipped_production_ticks_a} "
              f"metric_gate_passed={result.metric_gate_passed}")
    print(f"GO={result.go}")
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
            "episode_wins_a": result.episode_wins_a,
            "episode_wins_b": result.episode_wins_b,
            "episode_ties": result.episode_ties,
            "median_bank_a": result.median_bank_a,
            "significant": result.significant,
            "practical": result.practical,
            "verdict": result.verdict,
            "code_fingerprints": result.code_fingerprints,
            "stage": result.stage,
            "metrics_checked": result.metrics_checked,
            "water_weeds_lost_a": result.water_weeds_lost_a,
            "plant_decay_units_lost_a": result.plant_decay_units_lost_a,
            "animals_escaped_a": result.animals_escaped_a,
            "clipped_production_ticks_a": result.clipped_production_ticks_a,
            "metric_gate_passed": result.metric_gate_passed,
            "go": result.go,
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


def _cmd_report(args):
    replay_path = Path(args.replay)
    env_json = load_replay(replay_path)
    # Default receipts path mirrors play()'s own naming convention (receipts_<replay stem>.jsonl)
    # so `--receipts` only needs to be passed when the file lives somewhere non-default.
    if args.receipts:
        receipts_path = Path(args.receipts)
    else:
        stem = replay_path.name
        for suffix in (".json.gz", ".json"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        receipts_path = replay_path.parent / f"receipts_{stem}.jsonl"
    diagnostics = load_receipts(receipts_path)
    out_path = Path(args.out) if args.out else replay_path.parent / f"report_{replay_path.stem}.html"
    write_report(env_json, out_path, seat=args.seat, diagnostics=diagnostics)
    print(f"report: {out_path}")
    if diagnostics is None:
        print(f"note: no receipts found at {receipts_path} — unexplained_noops will read "
              "'not measured'; re-run play with KAGGRI_DEBUG=1 to capture them")


def _cmd_checkpoint(args):
    main_path = create_checkpoint(
        args.version,
        source_root=Path(args.source),
        checkpoint_root=Path(args.out),
    )
    print(f"checkpoint written to {main_path}")


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
    p_play.add_argument("--render-html", action="store_true",
                         help="also write the engine's bundled offline visualizer "
                              "(implies --record; plan.md §1.5.4)")
    p_play.set_defaults(func=_cmd_play)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("agent_a")
    p_compare.add_argument("agent_b")
    p_compare.add_argument("--seeds", default="0-47",
                            help="e.g. '0-23,40'; ignored if --seed-set is given "
                                 "(default matches harness.seeds.DEV_SEEDS)")
    p_compare.add_argument("--seed-set", choices=sorted(_SEED_SETS), default=None,
                            help="dev|holdout|smoke — overrides --seeds with the matching "
                                 "harness.seeds constant")
    p_compare.add_argument("--steps", type=int, default=None)
    p_compare.add_argument("--single-seat", action="store_true")
    p_compare.add_argument("--record", action="store_true")
    p_compare.add_argument("--no-strict", action="store_true",
                            help="don't raise on a crashing/timing-out/invalid agent")
    p_compare.add_argument("--resume", action="store_true",
                            help="skip seeds already present in <out>/results.jsonl")
    p_compare.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                            help="ProcessPoolExecutor workers; 1 = sequential (default: cpu_count-1)")
    p_compare.add_argument("--metrics", action="store_true",
                            help="extract water_weeds_lost/plant_decay_units_lost/"
                                 "animals_escaped/clipped_production_ticks for agent_a and "
                                 "require all four ==0 for the metric gate (plan.md §1.5.3, "
                                 "G5/G8); required (with --stage holdout-confirm) for GO=True")
    p_compare.add_argument("--stage", choices=VALID_STAGES, default=None,
                            help="dev-screen|holdout-confirm — defaults to the matching stage "
                                 "for --seed-set dev/holdout; smoke has no default stage and "
                                 "GO is always False for it")
    p_compare.add_argument("--out")
    p_compare.set_defaults(func=_cmd_compare)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("agent")
    p_profile.add_argument("--opponent", default="pass")
    p_profile.add_argument("--seed", type=int, default=0)
    p_profile.add_argument("--steps", type=int, default=None)
    p_profile.add_argument("--seat", type=int, default=0, choices=[0, 1])
    p_profile.set_defaults(func=_cmd_profile)

    p_report = sub.add_parser("report")
    p_report.add_argument("replay", help="path to a play()-recorded .json.gz (or plain .json) replay")
    p_report.add_argument("--receipts", default=None,
                           help="path to a receipts_*.jsonl (default: the matching file next "
                                "to --replay, if any)")
    p_report.add_argument("--seat", type=int, default=0, choices=[0, 1],
                           help="which seat is 'the agent under test' for the report")
    p_report.add_argument("--out", default=None,
                           help="output .html path (default: report_<replay stem>.html next to --replay)")
    p_report.set_defaults(func=_cmd_report)

    p_checkpoint = sub.add_parser("checkpoint")
    p_checkpoint.add_argument("version")
    p_checkpoint.add_argument("--source", default=".")
    p_checkpoint.add_argument("--out", default=DEFAULT_CHECKPOINT_ROOT)
    p_checkpoint.set_defaults(func=_cmd_checkpoint)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
