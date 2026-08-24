"""Thin CLI wrapper:

    python -m harness.cli play main.py starter --seed 17 --record
    python -m harness.cli compare main.py starter --seeds 0-23 --out runs/<name>
    python -m harness.cli ladder main.py --bench pass,starter,meta_route --seeds 0-2
    python -m harness.cli profile main.py --seed 17
    python -m harness.cli report runs/<name>/seed17_seat0-main.py_seat1-starter.json.gz

Set KAGGRI_DEBUG=1 before `play`/`compare` to capture G11 receipts alongside
the replay, so `report` can compute `unexplained_noops` instead of reporting "not measured".
"""
import argparse
import json
import os
import re
from pathlib import Path

from harness.checkpoint import DEFAULT_CHECKPOINT_ROOT, create_checkpoint
from harness.compare import ARM_ROLES, PRICED_SOURCE_METRICS, VALID_STAGES, compare
from harness.ladder import format_ladder, run_ladder
from harness.play import play
from harness.profile import report
from harness.report import load_receipts, load_replay, write_report
from harness.seeds import DEV_SEEDS, NAMED_SEED_SETS
from harness.town_pin import PIN_MODES

_SEED_SETS = dict(NAMED_SEED_SETS)


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


_STAGE_BY_SEED_SET = {
    "dev": "dev-screen", "holdout": "holdout-confirm", "confirm2": "holdout-confirm",
}  # smoke: no stage, never a GO


def _results_json_dict(result) -> dict:
    return {
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
        "sign_test_p": result.sign_test_p,
        "verdict": result.verdict,
        "incomplete": result.incomplete,
        "code_fingerprints": result.code_fingerprints,
        "stage": result.stage,
        "town_pin": result.town_pin,
        "town_schedules": result.town_schedules,
        "metrics_checked": result.metrics_checked,
        "water_weeds_lost_a": result.water_weeds_lost_a,
        "plant_decay_units_lost_a": result.plant_decay_units_lost_a,
        "animals_escaped_a": result.animals_escaped_a,
        "clipped_production_ticks_a": result.clipped_production_ticks_a,
        "shed_overflow_burnt_a": result.shed_overflow_burnt_a,
        "weeds_lost_a": result.weeds_lost_a,
        "unexpected_weeds_lost_a": result.unexpected_weeds_lost_a,
        "units_sold_at_or_below_5_a": result.units_sold_at_or_below_5_a,
        "sales_count_a": result.sales_count_a,
        "unexplained_noops_a": result.unexplained_noops_a,
        "market_sim_aborted_a": result.market_sim_aborted_a,
        "crop_tile_days_a": result.crop_tile_days_a,
        "crop_tile_days_b": result.crop_tile_days_b,
        "worker_turns_idle_a": result.worker_turns_idle_a,
        "worker_turns_idle_b": result.worker_turns_idle_b,
        "worker_turns_total_a": result.worker_turns_total_a,
        "worker_turns_total_b": result.worker_turns_total_b,
        "worker_turns_moving_a": result.worker_turns_moving_a,  # R15 (ROADMAP §6)
        "worker_turns_moving_b": result.worker_turns_moving_b,
        "worker_turns_working_a": result.worker_turns_working_a,  # R17 (ROADMAP §6)
        "worker_turns_working_b": result.worker_turns_working_b,
        "animals_underfed_days_a": result.animals_underfed_days_a,
        "animals_underfed_days_b": result.animals_underfed_days_b,
        "crop_revenue_a": result.crop_revenue_a,
        "crop_revenue_b": result.crop_revenue_b,
        "melon_units_a": result.melon_units_a,
        "melon_units_b": result.melon_units_b,
        "melon_revenue_a": result.melon_revenue_a,
        "melon_revenue_b": result.melon_revenue_b,
        "milk_units_a": result.milk_units_a,  # R20 (ROADMAP §6)
        "milk_units_b": result.milk_units_b,
        "milk_revenue_a": result.milk_revenue_a,
        "milk_revenue_b": result.milk_revenue_b,
        "wool_units_a": result.wool_units_a,
        "wool_units_b": result.wool_units_b,
        "wool_revenue_a": result.wool_revenue_a,
        "wool_revenue_b": result.wool_revenue_b,
        "animals_escaped_b": result.animals_escaped_b,
        "shed_overflow_burnt_b": result.shed_overflow_burnt_b,
        "unexpected_weeds_lost_b": result.unexpected_weeds_lost_b,
        "water_weeds_lost_b": result.water_weeds_lost_b,
        "weeds_lost_b": result.weeds_lost_b,
        "arm_role": result.arm_role,
        # `priced_loss_per_episode` is agent_a's absolute loss and keeps its pre-Δ name so every
        # gate artefact written before 2026-08-10 still parses; `priced_loss_a` is the same
        # number under the name that reads as a pair with `priced_loss_b`.
        "priced_loss_per_episode": result.priced_loss_per_episode,
        "priced_loss_a": result.priced_loss_per_episode,
        "priced_loss_b": result.priced_loss_b,
        "priced_loss_delta": result.priced_loss_delta,
        "priced_loss_budget_used": result.priced_loss_budget_used,
        "priced_loss_breakdown": result.priced_loss_breakdown,
        "priced_loss_breakdown_b": result.priced_loss_breakdown_b,
        "metric_mechanisms": result.metric_mechanisms,
        "unexplained_metrics": list(result.unexplained_metrics),
        "metric_gate_passed": result.metric_gate_passed,
        "prior_dev_screen_found": result.prior_dev_screen_found,
        "min_effect_used": result.min_effect_used,
        "non_inferiority_margin_used": result.non_inferiority_margin_used,
        "go": result.go,
        "repeat_confirm_index": result.repeat_confirm_index,
        "agent_a_spec": result.agent_a_spec,
        "agent_b_spec": result.agent_b_spec,
        "seed_set_name": result.seed_set_name,
        "harness_git_sha": result.harness_git_sha,
        "platform": result.platform,
        "python_version": result.python_version,
        "env": result.env,
        "warnings": result.warnings,
    }


def _parse_metric_mechanisms(pairs) -> dict:
    """`--metric-mechanism shed_overflow_burnt=<why>` -> {metric: explanation}.

    Απόφαση Α: a priced counter may only be non-zero if the run says, in
    writing and in the tracked results.json, why it is non-zero.
    """
    mechanisms = {}
    for pair in pairs or ():
        metric, separator, explanation = pair.partition("=")
        if not separator or not metric.strip() or not explanation.strip():
            raise SystemExit(f"--metric-mechanism expects METRIC=explanation, got {pair!r}")
        metric = metric.strip()
        if metric not in PRICED_SOURCE_METRICS:
            raise SystemExit(
                f"--metric-mechanism: {metric!r} is not a priced metric "
                f"(expected one of {sorted(PRICED_SOURCE_METRICS)})"
            )
        mechanisms[metric] = explanation.strip()
    return mechanisms


def _cmd_compare(args):
    seeds = list(_SEED_SETS[args.seed_set]) if args.seed_set else _parse_seeds(args.seeds)
    out_dir = Path(args.out) if args.out else None
    stage = args.stage if args.stage is not None else _STAGE_BY_SEED_SET.get(args.seed_set)
    result = compare(args.agent_a, args.agent_b, seeds, both_seats=not args.single_seat,
                      steps=args.steps, run_dir=out_dir, record=args.record,
                      strict=not args.no_strict, resume=args.resume, workers=args.workers,
                      metrics=args.metrics, stage=stage, town_pin=args.town_pin,
                      min_effect=args.min_effect,
                      non_inferiority_margin=args.non_inferiority_margin,
                      accept_within_margin=args.accept_within_margin,
                      allow_repeat_confirm=args.allow_repeat_confirm,
                      confirm_ledger_path=Path(args.confirm_ledger) if args.confirm_ledger else None,
                      metric_mechanisms=_parse_metric_mechanisms(args.metric_mechanism),
                      arm_role=args.arm_role,
                      screen_evidence_dir=Path(args.gates_dir))
    print(f"seeds={len(seeds)} ({result.seed_set_name}) both_seats={not args.single_seat} "
          f"workers={args.workers}")
    print(f"stage={result.stage} arm_role={result.arm_role} "
          f"metrics_checked={result.metrics_checked} "
          f"town_pin={result.town_pin} prior_dev_screen_found={result.prior_dev_screen_found} "
          f"repeat_confirm_index={result.repeat_confirm_index}")
    print(f"wins_a={result.wins_a} wins_b={result.wins_b} ties={result.ties} "
          f"sign_test_p={result.sign_test_p} errors={len(result.errors)}")
    print(f"episode_wins_a={result.episode_wins_a} episode_wins_b={result.episode_wins_b} "
          f"episode_ties={result.episode_ties} median_bank_a={result.median_bank_a:.1f}")
    print(f"mean_diff={result.mean_diff:.1f} se_diff={result.se_diff:.1f} "
          f"ci95=({result.ci95[0]:.1f}, {result.ci95[1]:.1f}) "
          f"min_effect_used={result.min_effect_used:.1f} "
          f"non_inferiority_margin_used={result.non_inferiority_margin_used:.1f}")
    print(f"significant={result.significant} practical={result.practical} "
          f"verdict={result.verdict}")
    if result.metrics_checked:
        print(f"water_weeds_lost_a={result.water_weeds_lost_a} "
              f"plant_decay_units_lost_a={result.plant_decay_units_lost_a} "
              f"animals_escaped_a={result.animals_escaped_a} "
              f"clipped_production_ticks_a={result.clipped_production_ticks_a} "
              f"shed_overflow_burnt_a={result.shed_overflow_burnt_a} "
              f"weeds_lost_a={result.weeds_lost_a} "
              f"unexpected_weeds_lost_a={result.unexpected_weeds_lost_a} "
              f"units_sold_at_or_below_5_a={result.units_sold_at_or_below_5_a}/"
              f"{result.sales_count_a} "
              f"unexplained_noops_a={result.unexplained_noops_a} "
              f"market_sim_aborted_a={result.market_sim_aborted_a}")
        # Απόφαση Δ: both arms' raw priced counters, then the differenced
        # criterion the acceptance decision is actually made on.
        print(f"arm_b_counters: animals_escaped_b={result.animals_escaped_b} "
              f"shed_overflow_burnt_b={result.shed_overflow_burnt_b} "
              f"unexpected_weeds_lost_b={result.unexpected_weeds_lost_b} "
              f"water_weeds_lost_b={result.water_weeds_lost_b} "
              f"weeds_lost_b={result.weeds_lost_b}")
        print(f"priced_loss_a={result.priced_loss_per_episode:.1f}/ep "
              f"priced_loss_b={result.priced_loss_b:.1f}/ep "
              f"priced_loss_delta={result.priced_loss_delta:.1f}/ep "
              f"budget={result.priced_loss_budget_used:.1f}/ep "
              f"(applies={result.arm_role == 'acceptance'}) "
              f"breakdown_a={ {k: round(v, 1) for k, v in result.priced_loss_breakdown.items() if v} } "
              f"breakdown_b={ {k: round(v, 1) for k, v in result.priced_loss_breakdown_b.items() if v} } "
              f"unexplained_metrics={list(result.unexplained_metrics)} "
              f"metric_gate_passed={result.metric_gate_passed}")
        episodes = max(1, len(result.per_seed) * (1 if args.single_seat else 2))
        print(
            "v1k_diagnostics="
            f"crop_tile_days/ep A={result.crop_tile_days_a / episodes:.1f} "
            f"B={result.crop_tile_days_b / episodes:.1f}; "
            f"worker_idle A={result.worker_turns_idle_a}/{result.worker_turns_total_a} "
            f"({100.0 * result.worker_turns_idle_a / max(1, result.worker_turns_total_a):.1f}%) "
            f"B={result.worker_turns_idle_b}/{result.worker_turns_total_b} "
            f"({100.0 * result.worker_turns_idle_b / max(1, result.worker_turns_total_b):.1f}%); "
            # R15 (ROADMAP §6): worker_turns_moving was aggregated by _V1K_REPORT_METRICS but
            # never surfaced in the CLI summary — the commute share had to be recovered by a
            # separate script (analysis/v1o3_visit_efficiency.py) every time it mattered.
            f"worker_moving A={result.worker_turns_moving_a}/{result.worker_turns_total_a} "
            f"({100.0 * result.worker_turns_moving_a / max(1, result.worker_turns_total_a):.1f}%) "
            f"B={result.worker_turns_moving_b}/{result.worker_turns_total_b} "
            f"({100.0 * result.worker_turns_moving_b / max(1, result.worker_turns_total_b):.1f}%); "
            # R17 (ROADMAP §1.1): a ratio on worker_turns_moving alone is satisfiable by
            # shrinking the farm (v1p1b arm A1) — worker_turns_working is the absolute
            # counterweight that has to sit next to it in every summary line, never quoted alone.
            f"worker_working A={result.worker_turns_working_a}/{result.worker_turns_total_a} "
            f"({100.0 * result.worker_turns_working_a / max(1, result.worker_turns_total_a):.1f}%) "
            f"B={result.worker_turns_working_b}/{result.worker_turns_total_b} "
            f"({100.0 * result.worker_turns_working_b / max(1, result.worker_turns_total_b):.1f}%); "
            f"animals_underfed_days/ep A={result.animals_underfed_days_a / episodes:.1f} "
            f"B={result.animals_underfed_days_b / episodes:.1f}; "
            f"crop_revenue/ep A={result.crop_revenue_a / episodes:.1f} "
            f"B={result.crop_revenue_b / episodes:.1f}; "
            f"melon_units A={result.melon_units_a} "
            f"($/u={((result.melon_revenue_a or 0) / (result.melon_units_a or 1)):.2f}) "
            f"B={result.melon_units_b} "
            f"($/u={((result.melon_revenue_b or 0) / (result.melon_units_b or 1)):.2f}); "
            # R20 (ROADMAP §6): MILK + WOOL realised price ($/u = revenue/units) — the §4.1
            # currency and the number the herd-13 MILK-saturation risk (§3.3) is decided on.
            f"milk_units A={result.milk_units_a} "
            f"($/u={((result.milk_revenue_a or 0) / (result.milk_units_a or 1)):.2f}) "
            f"B={result.milk_units_b} "
            f"($/u={((result.milk_revenue_b or 0) / (result.milk_units_b or 1)):.2f}); "
            f"wool_units A={result.wool_units_a} "
            f"($/u={((result.wool_revenue_a or 0) / (result.wool_units_a or 1)):.2f}) "
            f"B={result.wool_units_b} "
            f"($/u={((result.wool_revenue_b or 0) / (result.wool_units_b or 1)):.2f})"
        )
    if result.env:
        print(f"env={result.env}")
    print(f"GO={result.go}")
    if result.errors:
        print(f"errored seeds: {[e['seed'] for e in result.errors]}")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        results_path = out_dir / "results.json"
        results_json = json.dumps(_results_json_dict(result), indent=2)
        results_path.write_text(results_json)
        print(f"results written to {results_path}")
        # review.md H5: runs/ (replays, per-episode jsonl) stays gitignored — this small
        # results.json is copied into a tracked directory so a gate's evidence survives a
        # `git clean` / disk cleanup instead of only living in gitignored runs/.
        gates_path = Path(args.gates_dir) / out_dir.name / "results.json"
        gates_path.parent.mkdir(parents=True, exist_ok=True)
        gates_path.write_text(results_json)
        print(f"results also written to {gates_path} (tracked)")


def _cmd_ladder(args):
    """ROADMAP R22 / S6 step 3 — rank against a graded bench in the ladder's own currency."""
    bench = {}
    for spec in args.bench.split(","):
        spec = spec.strip()
        if not spec:
            continue
        name, _, path = spec.partition("=")
        bench[name] = path or name
    if not bench:
        raise SystemExit("--bench is empty")
    result = run_ladder(args.agent, bench, _parse_seeds(args.seeds),
                        challenger_name=args.name or args.agent,
                        steps=args.steps, round_robin=args.round_robin,
                        shop_draw=args.shop_draw,
                        run_dir=Path(args.out) if args.out else None)
    print(format_ladder(result))
    if args.out:
        out_path = Path(args.out) / "ladder.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nwrote {out_path}")


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


def main(argv=None):
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
                              "(implies --record)")
    p_play.set_defaults(func=_cmd_play)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("agent_a")
    p_compare.add_argument("agent_b")
    p_compare.add_argument(
        "--seeds", default=f"{DEV_SEEDS.start}-{DEV_SEEDS.stop - 1}",
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
                            help="extract all hard-loss, low-price-sale, no-op, and market-"
                                 "simulation metrics for agent_a; required (with an unpinned, "
                                 "both-seats --stage holdout-confirm) for GO=True")
    p_compare.add_argument("--metric-mechanism", action="append", metavar="METRIC=WHY",
                            help="declare why a priced loss counter is non-zero, e.g. "
                                 "--metric-mechanism shed_overflow_burnt='peak-production days'. "
                                 "Απόφαση Α: any non-zero priced counter "
                                 "without one fails the metric gate (repeatable)")
    p_compare.add_argument("--arm-role", choices=ARM_ROLES, default="acceptance",
                            help="which question this comparison asks (Απόφαση Δ): "
                                 "acceptance = vs the meta bench, the arm that "
                                 "decides whether an increment is taken, priced leg applies to "
                                 "priced_loss_a-priced_loss_b | regression = mirror vs our own "
                                 "baseline, a regression detector where only the $-verdict and "
                                 "the structural/mechanism legs apply. Default acceptance (the "
                                 "stricter regime), so the looser one is always explicit")
    p_compare.add_argument("--min-effect", type=float, default=None,
                           help="practical improvement threshold in dollars per episode "
                                "(default: max($200, 2%% of mean bank_b))")
    p_compare.add_argument("--non-inferiority-margin", type=float, default=None,
                           help="maximum allowed lower-confidence regression in dollars per "
                                "episode (default: the effective --min-effect)")
    p_compare.add_argument("--accept-within-margin", action="store_true",
                            help="allow GO=True when verdict=WITHIN_MARGIN (a statistically "
                                 "confirmed regression that's still inside the margin) or when "
                                 "a sign test confirms wins_b>wins_a at p<0.01 — otherwise "
                                 "either blocks GO regardless of the $-verdict (review.md H2)")
    p_compare.add_argument("--allow-repeat-confirm", action="store_true",
                            help="allow a second stage=holdout-confirm run against the same "
                                 "(agent_b, seed set) already recorded in the confirm ledger — "
                                 "otherwise this raises (review.md C1/C2)")
    p_compare.add_argument("--confirm-ledger", default=None,
                            help="path to the confirm ledger jsonl (default: "
                                 "harness.compare.DEFAULT_CONFIRM_LEDGER, gates/confirm_log.jsonl)")
    p_compare.add_argument("--gates-dir", default="gates",
                            help="tracked directory that also receives a copy of --out's "
                                 "results.json (small, no replays) — the durable, git-tracked "
                                 "evidence a gate ran (review.md H5)")
    p_compare.add_argument("--town-pin", choices=PIN_MODES, default=None,
                            help="pin which shops the town unlocks so both arms play the same "
                                 "town per seed (§Β.0′): schedule=permutation "
                                 "of the 8 types (today's engine) | basket=draw with "
                                 "replacement (announced balance change) | no_shops=town centre "
                                 "only. Required for occupancy knobs (crew, planting, BUY_LAND, "
                                 "animal placement); screening only — the final confirm must "
                                 "also run unpinned")
    p_compare.add_argument("--stage", choices=VALID_STAGES, default=None,
                            help="dev-screen|holdout-confirm — defaults to the matching stage "
                                 "for --seed-set dev/holdout; smoke has no default stage and "
                                 "GO is always False for it")
    p_compare.add_argument("--out")
    p_compare.set_defaults(func=_cmd_compare)

    p_ladder = sub.add_parser(
        "ladder", help="Bradley-Terry ranking against a graded bench (ROADMAP R22)")
    p_ladder.add_argument("agent")
    p_ladder.add_argument(
        "--bench", required=True,
        help="comma-separated opponents, each 'name' or 'name=path'. Keep it GRADED and keep "
             "earlier meta generations in it (ROADMAP §2), e.g. "
             "'pass,starter,meta_route,v1i=checkpoints/v1i/main.py'")
    p_ladder.add_argument("--seeds", default="0-2",
                          help="e.g. '0-11'; every pairing is played from BOTH seats (§2.1.1)")
    p_ladder.add_argument("--name", default=None, help="label for the challenger")
    p_ladder.add_argument("--steps", type=int, default=None)
    p_ladder.add_argument(
        "--round-robin", action="store_true",
        help="also play the bench against itself. Slower, and it is what makes the bench's own "
             "BT ratings identified rather than inferred through the challenger alone")
    p_ladder.add_argument(
        "--shop-draw", action="store_true",
        help="report the shop draw this seed set actually sampled (ROADMAP R21 / §4.1b — "
             "realised premium price moves 5-18x with it). Implies recording replays")
    p_ladder.add_argument("--out", default=None, help="directory for ladder.json + replays")
    p_ladder.set_defaults(func=_cmd_ladder)

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

    args = parser.parse_args(argv)
    # review.md C2(c): --stage silently overrode --seed-set's implied stage with no warning,
    # so `--seed-set dev --stage holdout-confirm` could produce a GO from seeds that were just
    # tuned on. A mismatched explicit pair is now a usage error, not a silent override.
    if args.command == "compare" and args.stage is not None and args.seed_set is not None:
        expected_stage = _STAGE_BY_SEED_SET.get(args.seed_set)
        if expected_stage is not None and args.stage != expected_stage:
            p_compare.error(
                f"--stage {args.stage!r} conflicts with --seed-set {args.seed_set!r} (expects "
                f"--stage {expected_stage!r}) — pass matching flags, or omit --stage to use "
                "the seed-set's default"
            )
    args.func(args)


if __name__ == "__main__":
    main()
