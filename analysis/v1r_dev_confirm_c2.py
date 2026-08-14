#!/usr/bin/env python3
"""DEV-scale (0-47) confirmation of the SMOKE winner, arm C2 (feed_reserve_horizon="target").
Two regression-mirror runs vs v1q_base: (a) normal config — the price we'd ship; (b) A1-stacked
— does the defect-kill hold beyond 12 seeds. Not the full Phase-2 acceptance gate (that bundles
with herd 13); this only strengthens the SMOKE increment claim."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from analysis.v1r_screen import run_compare  # noqa: E402

STACK = Path(sys.argv[1])
SEEDS = list(range(48))
OUT = Path("gates/v1r_feed_reserve/dev_confirm")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    runs = [
        ("armC2_normal_dev", "checkpoints/v1r_armC2/main.py"),
        ("armC2_a1stacked_dev", str(STACK / "c2_a1" / "main.py")),
    ]
    rows = []
    for tag, a in runs:
        r = run_compare(a, SEEDS, OUT, tag)
        rows.append(r)
        print(f"{tag:<22} escA={r['escaped_a']} escB={r['escaped_b']} "
              f"ctd_a={r['crop_tile_days_a']} ctd_b={r['crop_tile_days_b']} "
              f"work_a={r['worker_working_a']} plant_decay={r['plant_decay_a']} "
              f"clipped={r['clipped_a']} noops={r['noops_a']} mkt_abort={r['market_abort_a']} "
              f"mean_diff={r['mean_diff']:.1f} {r['verdict']}")
    (OUT / "dev_confirm.json").write_text(json.dumps(rows, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
