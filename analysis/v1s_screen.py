#!/usr/bin/env python3
"""v1s — screen the herd-13 race arms (ROADMAP §4.3 S3 step 2, prompt.md §3).

Arm 0 (v1q_base vs itself) is the noise floor; B0/H1/H2/H2R (all carrying C2) are each compared
against v1q_base. SMOKE 0-11, both seats, --town-pin basket, --arm-role regression, --metrics.

Emits, per arm: animals_escaped a/b (paired baseline), crop_tile_days, worker_turns_working/moving,
MILK + WOOL realised price ($/u = revenue/units, R20), the structural hard-zeros, mean_diff/verdict,
and the placed-herd-by-day trajectory (candidate seat 0) out to episode end — criterion 2 (the herd
exists and holds) is read off this, distinguishing OWNED (bought) from PLACED (on tiles).

Usage:
    .venv/bin/python analysis/v1s_screen.py --seeds 0-11
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

ARMS = [
    ("arm0", BASE),
    ("B0", "checkpoints/v1s_B0/main.py"),
    ("H1", "checkpoints/v1s_H1/main.py"),
    ("H2", "checkpoints/v1s_H2/main.py"),
    ("H2R", "checkpoints/v1s_H2R/main.py"),
]


def placed_on_tiles(obs, seat):
    tiles = obs["farms"][seat]["tiles"]
    return sum(1 for row in tiles for t in row if isinstance(t, dict) and "animal" in t)


def owned(obs0, obs_seat, seat):
    """placed on tiles + carried in hands + in shed (bought but not placed)."""
    priv = obs_seat["private"]
    infl = sum(int(priv["shed"].get(n, 0)) for n in ANIMAL_NAMES)
    for inv in priv["inventories"]:
        infl += sum(int(inv.get(n, 0)) for n in ANIMAL_NAMES)
    return placed_on_tiles(obs0, seat) + infl


def herd_by_day(cand, seeds, out_dir):
    """Mean placed and mean owned animal count at each day boundary for the candidate (seat 0),
    across seeds, to episode end."""
    days = None
    placed_sum = owned_sum = None
    n = 0
    for seed in seeds:
        run_dir = out_dir / "herd" / f"seed{seed}"
        with pinned_town("basket", schedule_for_mode("basket", seed)):
            result = play(cand, BASE, seed=seed, record=True, run_dir=run_dir,
                          metrics=False, strict=False)
        with gzip.open(result.replay_path, "rt", encoding="utf-8") as handle:
            steps = json.load(handle)["steps"]
        n_days = (len(steps) + TURNS_PER_DAY - 1) // TURNS_PER_DAY
        if days is None:
            days = n_days
            placed_sum = [0.0] * days
            owned_sum = [0.0] * days
        for d in range(min(days, n_days)):
            step = min(d * TURNS_PER_DAY, len(steps) - 1)
            obs0 = steps[step][0]["observation"]
            obs_seat = steps[step][0]["observation"]  # seat 0 candidate; private on [0] entry
            placed_sum[d] += placed_on_tiles(obs0, 0)
            owned_sum[d] += owned(obs0, obs_seat, 0)
        n += 1
        Path(result.replay_path).unlink(missing_ok=True)
    placed_avg = [round(c / n, 1) for c in placed_sum]
    owned_avg = [round(c / n, 1) for c in owned_sum]
    return placed_avg, owned_avg


def price(rev, units):
    return round(rev / units, 2) if units else 0.0


def run_arm(tag, agent_a, seeds, out_dir):
    run_dir = out_dir / "compare" / tag
    r = compare(
        agent_a, BASE, seeds, both_seats=True, town_pin="basket", arm_role="regression",
        metrics=True, workers=9, require_distinct_versions=(agent_a != BASE),
        run_dir=run_dir,
    )
    row = {
        "tag": tag, "agent_a": agent_a,
        "mean_diff": r.mean_diff, "verdict": r.verdict,
        "escaped_a": r.animals_escaped_a, "escaped_b": r.animals_escaped_b,
        "crop_tile_days_a": r.crop_tile_days_a, "crop_tile_days_b": r.crop_tile_days_b,
        "worker_working_a": r.worker_turns_working_a, "worker_working_b": r.worker_turns_working_b,
        "worker_moving_a": r.worker_turns_moving_a, "worker_moving_b": r.worker_turns_moving_b,
        "plant_decay_a": r.plant_decay_units_lost_a, "clipped_a": r.clipped_production_ticks_a,
        "noops_a": r.unexplained_noops_a, "market_abort_a": r.market_sim_aborted_a,
        "shed_overflow_a": r.shed_overflow_burnt_a,
        "milk_units_a": r.milk_units_a, "milk_rev_a": r.milk_revenue_a,
        "milk_units_b": r.milk_units_b, "milk_rev_b": r.milk_revenue_b,
        "wool_units_a": r.wool_units_a, "wool_rev_a": r.wool_revenue_a,
        "wool_units_b": r.wool_units_b, "wool_rev_b": r.wool_revenue_b,
        "milk_price_a": price(r.milk_revenue_a, r.milk_units_a),
        "milk_price_b": price(r.milk_revenue_b, r.milk_units_b),
        "wool_price_a": price(r.wool_revenue_a, r.wool_units_a),
        "wool_price_b": price(r.wool_revenue_b, r.wool_units_b),
    }
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0-11")
    parser.add_argument("--out", default="gates/v1s_race")
    parser.add_argument("--no-herd", action="store_true", help="skip herd-by-day recorded plays")
    args = parser.parse_args()
    lo, hi = (args.seeds.split("-") + [args.seeds.split("-")[0]])[:2]
    seeds = list(range(int(lo), int(hi) + 1))
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    table = []
    for tag, agent_a in ARMS:
        print(f"--- compare {tag} ({agent_a})")
        row = run_arm(tag, agent_a, seeds, out_dir)
        if not args.no_herd:
            placed, owned_ = herd_by_day(agent_a, seeds, out_dir / tag)
            row["placed_by_day"] = placed
            row["owned_by_day"] = owned_
        table.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "agent_a"}, indent=2))

    (out_dir / "race.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    print("\n=== SUMMARY (all vs v1q_base; arm0 = noise floor) ===")
    hdr = (f"{'arm':<5} {'escA':>4} {'escB':>4} {'ctd_a':>6} {'work_a':>7} {'move%':>6} "
           f"{'milk$/u_a':>9} {'wool$/u_a':>9} {'decay':>5} {'mean_diff':>10} {'verdict':>13}")
    print(hdr)
    for r in table:
        movpct = 100.0 * r["worker_moving_a"] / max(1, r["worker_working_a"] + r["worker_moving_a"])
        print(f"{r['tag']:<5} {str(r['escaped_a']):>4} {str(r['escaped_b']):>4} "
              f"{str(r['crop_tile_days_a']):>6} {str(r['worker_working_a']):>7} {movpct:>5.1f}% "
              f"{r['milk_price_a']:>9.2f} {r['wool_price_a']:>9.2f} {str(r['plant_decay_a']):>5} "
              f"{r['mean_diff']:>10.1f} {r['verdict']:>13}")
        if "placed_by_day" in r:
            print(f"    placed/day: {r['placed_by_day']}")
            print(f"    owned /day: {r['owned_by_day']}")


if __name__ == "__main__":
    main()
