#!/usr/bin/env python3
"""v1r — screen the feed-reserve arms (ROADMAP §4.3 S3 step 1e, prompt.md §3.3/§3.4).

Runs every arm twice (normal config vs v1q_base; A1-stacked vs v1q_base) plus arm 0 (the
v1q_base paired-baseline noise floor) and the A1 reproducer, all at SMOKE 0-11 both seats,
--town-pin basket, --arm-role regression, --metrics. Emits one table with animals_escaped,
placed-herd-by-day, worker_turns_working/moving, crop_tile_days, mean_diff per run.

placed-herd-by-day is measured separately with short recorded plays: for the candidate (agent A,
seat 0) and the v1q_base baseline (seat 1), the number of animals standing on tiles at each
day boundary, averaged over the SMOKE seeds. Criterion 2 (prompt.md §3.4): an arm that stops
escapes by buying FEWER animals has not fixed anything.

Usage:
    .venv/bin/python analysis/v1r_screen.py --stacked <dir> --seeds 0-11
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.config import CONFIG  # noqa: E402
from agent.constants import ANIMALS  # noqa: E402
from harness.compare import compare  # noqa: E402
from harness.play import play  # noqa: E402
from harness.town_pin import pinned_town, schedule_for_mode  # noqa: E402

BASE = "checkpoints/v1q_base/main.py"
TURNS_PER_DAY = CONFIG["runtime"]["turns_per_day"]
ANIMAL_NAMES = tuple(ANIMALS)


def placed_on_tiles(obs, seat):
    tiles = obs["farms"][seat]["tiles"]
    return sum(1 for row in tiles for t in row if isinstance(t, dict) and "animal" in t)


def herd_by_day(cand, seeds, out_dir):
    """Mean placed-animal count at each day boundary for candidate (seat 0) and baseline
    (seat 1), across seeds. One orientation only — enough for the not-suppressed check."""
    days = None
    cand_sum, base_sum, n = None, None, 0
    for seed in seeds:
        run_dir = out_dir / "herd" / f"seed{seed}"
        with pinned_town("basket", schedule_for_mode("basket", seed)):
            result = play(cand, BASE, seed=seed, record=True, run_dir=run_dir, metrics=False, strict=False)
        with gzip.open(result.replay_path, "rt", encoding="utf-8") as handle:
            steps = json.load(handle)["steps"]
        n_days = (len(steps) + TURNS_PER_DAY - 1) // TURNS_PER_DAY
        if days is None:
            days = n_days
            cand_sum = [0] * days
            base_sum = [0] * days
        for d in range(min(days, n_days)):
            step = min(d * TURNS_PER_DAY, len(steps) - 1)
            obs = steps[step][0]["observation"]
            cand_sum[d] += placed_on_tiles(obs, 0)
            base_sum[d] += placed_on_tiles(obs, 1)
        n += 1
        Path(result.replay_path).unlink(missing_ok=True)
    cand_avg = [round(c / n, 1) for c in cand_sum]
    base_avg = [round(b / n, 1) for b in base_sum]
    return cand_avg, base_avg


def run_compare(agent_a, seeds, out_dir, tag):
    run_dir = out_dir / "compare" / tag
    r = compare(
        agent_a, BASE, seeds, both_seats=True, town_pin="basket", arm_role="regression",
        metrics=True, workers=9, require_distinct_versions=(agent_a != BASE),
        run_dir=run_dir,
    )
    return {
        "tag": tag,
        "agent_a": agent_a,
        "mean_diff": r.mean_diff,
        "verdict": r.verdict,
        "escaped_a": r.animals_escaped_a,
        "escaped_b": r.animals_escaped_b,
        "crop_tile_days_a": r.crop_tile_days_a,
        "crop_tile_days_b": r.crop_tile_days_b,
        "worker_working_a": r.worker_turns_working_a,
        "worker_working_b": r.worker_turns_working_b,
        "worker_moving_a": r.worker_turns_moving_a,
        "worker_moving_b": r.worker_turns_moving_b,
        "plant_decay_a": r.plant_decay_units_lost_a,
        "clipped_a": r.clipped_production_ticks_a,
        "noops_a": r.unexplained_noops_a,
        "market_abort_a": r.market_sim_aborted_a,
        "shed_overflow_a": r.shed_overflow_burnt_a,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stacked", required=True, help="dir of A1-stacked packages")
    parser.add_argument("--seeds", default="0-11")
    parser.add_argument("--out", default="gates/v1r_feed_reserve")
    args = parser.parse_args()

    lo, hi = (args.seeds.split("-") + [args.seeds.split("-")[0]])[:2]
    seeds = list(range(int(lo), int(hi) + 1))
    stacked = Path(args.stacked)
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = [
        ("arm0_v1qbase_vs_self", BASE),
        ("armA1_repro_vs_base", str(stacked / "a1_repro" / "main.py")),
        ("armC1_normal", "checkpoints/v1r_armC1/main.py"),
        ("armC2_normal", "checkpoints/v1r_armC2/main.py"),
        ("armX_normal", "checkpoints/v1r_armX/main.py"),
        ("armC1_a1stacked", str(stacked / "c1_a1" / "main.py")),
        ("armC2_a1stacked", str(stacked / "c2_a1" / "main.py")),
        ("armX_a1stacked", str(stacked / "x_a1" / "main.py")),
    ]

    table = []
    for tag, agent_a in runs:
        print(f"--- compare {tag} ({agent_a})")
        row = run_compare(agent_a, seeds, out_dir, tag)
        # herd-by-day for the runs where suppression is the risk (all candidates + repro)
        if agent_a != BASE:
            cand_herd, base_herd = herd_by_day(agent_a, seeds, out_dir / tag)
            row["herd_by_day_a"] = cand_herd
            row["herd_by_day_base"] = base_herd
        table.append(row)
        print(json.dumps(row, indent=2))

    (out_dir / "screen.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(f"{'run':<22} {'escA':>4} {'escB':>4} {'ctd_a':>6} {'ctd_b':>6} {'work_a':>7} {'work_b':>7} {'mean_diff':>10} {'verdict':>13}")
    for r in table:
        print(f"{r['tag']:<22} {str(r['escaped_a']):>4} {str(r['escaped_b']):>4} "
              f"{str(r['crop_tile_days_a']):>6} {str(r['crop_tile_days_b']):>6} "
              f"{str(r['worker_working_a']):>7} {str(r['worker_working_b']):>7} "
              f"{r['mean_diff']:>10.1f} {r['verdict']:>13}")
        if "herd_by_day_a" in r:
            print(f"    herd/day  cand={r['herd_by_day_a']}")
            print(f"    herd/day  base={r['herd_by_day_base']}")


if __name__ == "__main__":
    main()
