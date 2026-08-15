#!/usr/bin/env python3
"""v1s — inertness proofs for the two agent/ edits this pass makes (prompt.md §1.2).

Both edits default to shipped behaviour and must be proven byte-inert before any screen (R12):

  check A — C2 cleanup + ramp-None: the cleaned current codebase at C2 config (arm B0's package,
    targets {4C,6S}) vs checkpoints/v1r_armC2 (the pre-cleanup C2 package). These differ ONLY by
    the executor's dead-min/max cleanup and the added planner ramp (inert at ramp=None), so a
    behaviour-identical mirror is the joint proof. Required: mean_diff exactly 0.0, ci [0,0],
    ties == len(seeds), every seat-summed counter equal (_a == _b).

  check B — default: live main.py (all new flags default) vs checkpoints/v1q_base — the shipped
    config is untouched by this pass, so an arm's B0-vs-v1q_base delta isolates C2 alone.

Usage:
    .venv/bin/python analysis/v1s_inert.py --b0 <path/to/tmp/v1s_B0/main.py>
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.compare import compare  # noqa: E402

COUNTERS = (
    "crop_tile_days", "worker_turns_working", "worker_turns_moving", "worker_turns_idle",
    "worker_turns_total", "animals_escaped", "plant_decay_units_lost", "clipped_production_ticks",
    "shed_overflow_burnt", "animals_underfed_days", "crop_revenue", "water_weeds_lost",
    "unexpected_weeds_lost", "melon_units", "melon_revenue", "milk_units", "milk_revenue",
    "wool_units", "wool_revenue",
)


def run(tag, agent_a, agent_b, seeds, out_dir):
    r = compare(
        agent_a, agent_b, seeds, both_seats=True, town_pin="basket", arm_role="regression",
        metrics=True, workers=9, require_distinct_versions=False, run_dir=out_dir / tag,
    )
    ok = (r.mean_diff == 0.0 and list(r.ci95) == [0.0, 0.0] and r.ties == len(seeds))
    mism = []
    for c in COUNTERS:
        if not hasattr(r, f"{c}_b"):
            continue  # arm-a-only structural counters (plant_decay, clipped) have no _b field
        a, b = getattr(r, f"{c}_a"), getattr(r, f"{c}_b")
        if a != b:
            mism.append((c, a, b))
    ok = ok and not mism
    print(f"\n=== {tag} ===")
    print(f"  agent_a={agent_a}\n  agent_b={agent_b}")
    print(f"  mean_diff={r.mean_diff}  ci95={r.ci95}  ties={r.ties}/{len(seeds)}  "
          f"episode_ties={r.episode_ties}  verdict={r.verdict}")
    print(f"  counters (a/b): " + ", ".join(
        f"{c}={getattr(r, f'{c}_a')}" for c in
        ("crop_tile_days", "worker_turns_working", "animals_escaped", "crop_revenue",
         "milk_units", "wool_units")))
    if mism:
        print("  ❌ COUNTER MISMATCH:")
        for c, a, b in mism:
            print(f"     {c}: a={a} b={b}")
    print(f"  => {'PASS (byte-inert)' if ok else 'FAIL — NOT inert'}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--b0", required=True, help="path to the temp v1s_B0 main.py")
    parser.add_argument("--out", default="gates/v1s_inert")
    args = parser.parse_args()
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    a = run("checkA_c2cleanup_ramp_none__B0_vs_v1r_armC2",
            args.b0, "checkpoints/v1r_armC2/main.py", list(range(12)), out_dir)
    b = run("checkB_default__live_main_vs_v1q_base",
            "main.py", "checkpoints/v1q_base/main.py", list(range(4)), out_dir)
    print(f"\nBOTH INERT: {a and b}")
    sys.exit(0 if (a and b) else 1)


if __name__ == "__main__":
    main()
