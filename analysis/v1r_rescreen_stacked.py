#!/usr/bin/env python3
"""Re-run only the A1-stacked screens after the builder duplicate-key fix."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from analysis.v1r_screen import run_compare, herd_by_day  # noqa: E402

STACK = Path(sys.argv[1])
SEEDS = list(range(12))
OUT = Path("gates/v1r_feed_reserve")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    rows = []
    for tag, arm in [("armC1_a1stacked", "c1_a1"),
                     ("armC2_a1stacked", "c2_a1"),
                     ("armX_a1stacked", "x_a1")]:
        a = str(STACK / arm / "main.py")
        r = run_compare(a, SEEDS, OUT, tag)
        ch, bh = herd_by_day(a, SEEDS, OUT / tag)
        r["herd_by_day_a"] = ch
        r["herd_by_day_base"] = bh
        rows.append(r)
        print(f"{tag:<18} escA={r['escaped_a']} escB={r['escaped_b']} "
              f"ctd_a={r['crop_tile_days_a']} work_a={r['worker_working_a']} "
              f"mean_diff={r['mean_diff']:.1f} {r['verdict']}")
        print(f"   herd cand={ch}")
        print(f"   herd base={bh}")
    (OUT / "screen_stacked_rerun.json").write_text(json.dumps(rows, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
