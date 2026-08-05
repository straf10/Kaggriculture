"""plan.md §1.5.2: automated ablation runner.

Flips one (or more) `CONFIG["ablation"]` flags off at a time via the `KAGGRI_ABLATION` env
var (agent/config.py), compares `main.py` against the frozen `checkpoints/v1b` baseline on
a fixed seed set, and writes one row per combo to `ablation.jsonl` so the main.py-vs-v1b
regression can be attributed to a specific flag (or pair) instead of reverted blind.

    python -m harness.ablate                                   # self-test + one-at-a-time sweep
    python -m harness.ablate --combo slack_assign,task_stickiness
    python -m harness.ablate --skip-self-test --seed-set holdout --combo on_event_replan

Each combo is run as its own compare() call so a freshly spawned ProcessPoolExecutor worker
(workers>1) picks up the just-set env var at process-creation time — the agent and this
runner are different processes, so CONFIG["ablation"] can only be steered through the
env var read once at import (see agent/config.py's module docstring), never by mutating
CONFIG here directly (that would only affect this process, not the workers).
"""
import argparse
import json
import os
from pathlib import Path

from agent.config import CONFIG
from harness.compare import compare
from harness.seeds import DEV_SEEDS, HOLDOUT_SEEDS, SMOKE_SEEDS

BASELINE = "checkpoints/v1b/main.py"
MAIN = "main.py"
ALL_FLAGS = sorted(CONFIG["ablation"])
SEED_SETS = {"dev": DEV_SEEDS, "holdout": HOLDOUT_SEEDS, "smoke": SMOKE_SEEDS}


def _combo_env_value(off_flags) -> str:
    return ",".join(f"{flag}=0" for flag in off_flags)


def _default_workers() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def run_combo(off_flags, *, seeds=DEV_SEEDS, workers=None, out_path=None, strict=False):
    """Run compare(main.py, checkpoints/v1b/main.py) with `off_flags` set False, restoring
    the ambient KAGGRI_ABLATION env var afterward regardless of outcome."""
    for flag in off_flags:
        if flag not in CONFIG["ablation"]:
            raise ValueError(f"unknown ablation flag: {flag!r} (known: {ALL_FLAGS})")
    workers = _default_workers() if workers is None else workers
    previous = os.environ.get("KAGGRI_ABLATION")
    os.environ["KAGGRI_ABLATION"] = _combo_env_value(off_flags)
    try:
        result = compare(MAIN, BASELINE, list(seeds), workers=workers, record=False, strict=strict)
    finally:
        if previous is None:
            os.environ.pop("KAGGRI_ABLATION", None)
        else:
            os.environ["KAGGRI_ABLATION"] = previous
    row = {
        "flags_off": sorted(off_flags),
        "mean_diff": result.mean_diff,
        "se_diff": result.se_diff,
        "ci95": list(result.ci95),
        "verdict": result.verdict,
        "n_effective": result.n_effective,
        "errors": len(result.errors),
    }
    if out_path is not None:
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return row


def self_test(*, seeds=DEV_SEEDS, workers=None, strict=False):
    """Critical acceptance criterion #1 (plan.md §1.5.2): with every flag off, main.py must
    be byte-for-byte the v1b baseline — |mean_diff| == 0 AND every per-seed diff exactly 0.
    If this fails, the ablation infrastructure itself is broken and no combo result below it
    may be trusted."""
    workers = _default_workers() if workers is None else workers
    previous = os.environ.get("KAGGRI_ABLATION")
    os.environ["KAGGRI_ABLATION"] = _combo_env_value(ALL_FLAGS)
    try:
        result = compare(MAIN, BASELINE, list(seeds), workers=workers, record=False, strict=strict)
    finally:
        if previous is None:
            os.environ.pop("KAGGRI_ABLATION", None)
        else:
            os.environ["KAGGRI_ABLATION"] = previous
    nonzero = [row for row in result.per_seed if row["diff"] != 0]
    ok = result.mean_diff == 0 and not nonzero
    return ok, result, nonzero


def one_at_a_time_sweep(*, seeds=DEV_SEEDS, workers=None, out_path="ablation.jsonl", strict=False):
    rows = []
    for flag in ALL_FLAGS:
        rows.append(run_combo([flag], seeds=seeds, workers=workers, out_path=out_path, strict=strict))
    return rows


def main():
    parser = argparse.ArgumentParser(prog="python -m harness.ablate")
    parser.add_argument("--combo", help="comma list of flag names to turn OFF, e.g. "
                                         "'slack_assign,task_stickiness'; runs just this one combo")
    parser.add_argument("--seed-set", choices=sorted(SEED_SETS), default="dev")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", default="ablation.jsonl")
    parser.add_argument("--skip-self-test", action="store_true",
                         help="skip criterion #1 — only for re-running a sweep you already validated")
    args = parser.parse_args()

    seeds = SEED_SETS[args.seed_set]

    if args.combo:
        flags = [f.strip() for f in args.combo.split(",") if f.strip()]
        row = run_combo(flags, seeds=seeds, workers=args.workers, out_path=args.out)
        print(json.dumps(row, indent=2))
        return

    if not args.skip_self_test:
        ok, result, nonzero = self_test(seeds=seeds, workers=args.workers)
        print(f"self-test (all flags off vs {BASELINE}): mean_diff={result.mean_diff} "
              f"nonzero_seeds={len(nonzero)}/{len(result.per_seed)} -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            raise SystemExit(
                "ablation self-test FAILED — infrastructure is broken (some behavior differs "
                "from v1b outside the tracked flags). Fix before trusting any sweep result. "
                f"First nonzero seeds: {nonzero[:5]}"
            )

    Path(args.out).touch(exist_ok=True)
    rows = one_at_a_time_sweep(seeds=seeds, workers=args.workers, out_path=args.out)
    rows_sorted = sorted(rows, key=lambda r: r["mean_diff"])
    print(f"\n=== one-at-a-time OFF sweep vs {BASELINE}, sorted by mean_diff (most negative = most "
          "guilty) ===")
    for row in rows_sorted:
        print(f"{row['flags_off']}: mean_diff={row['mean_diff']:.1f} se={row['se_diff']:.1f} "
              f"ci95={row['ci95']} verdict={row['verdict']} errors={row['errors']}")


if __name__ == "__main__":
    main()
