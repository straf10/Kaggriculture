"""L2c — revenue per planted tile-day, us vs ladder opponent (docs/data only).

The pre-gate product ranking in current_phase.md ranks crops by *shop saturation*
(cliff depth). That answers "how much can I dump before the price dies", not
"what does a tile of my farm earn while it is occupied". This script measures the
second quantity directly from ladder replays: gross market revenue per crop,
divided by the tile-days that crop occupied.

Usage: python analysis/l2c_tile_economics.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.replay_profile import extract_profile  # noqa: E402
from harness.metrics import extract_metrics  # noqa: E402

OUR = "STRAF"
ROOT = Path("baselines/2026-08-10/replays_v1h2d")
OUT = Path("baselines/2026-08-10/l2c_tile_economics.json")


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return 0
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def main() -> None:
    per_ep = {"us": [], "opp": []}
    for path in sorted(ROOT.glob("episode-*-replay.json")):
        r = json.load(open(path, encoding="utf-8"))
        teams = r["info"].get("TeamNames") or []
        if OUR not in teams:
            continue
        our = teams.index(OUR)
        for lbl, seat in (("us", our), ("opp", 1 - our)):
            prof = extract_profile(r, seat)
            metrics = extract_metrics(r, seat)
            tile_days: dict = defaultdict(float)
            for day in prof["daily"]:
                for key, val in day.items():
                    if key.startswith("plants_"):
                        tile_days[key[7:].upper()] += val
            revenue: dict = defaultdict(float)
            for sale in metrics["market_sales"]:
                revenue[sale["item"]] += sale["price"]
            per_ep[lbl].append((dict(tile_days), dict(revenue)))

    n = len(per_ep["us"])
    print(f"parsed {n} episodes\n")
    products = sorted(
        {k for lbl in per_ep for td, _ in per_ep[lbl] for k in td}
        | {k for lbl in per_ep for _, rv in per_ep[lbl] for k in rv}
    )
    print(f"{'crop':>12} | {'us_tiledays':>11} {'us_rev':>9} {'us_$/td':>9} | "
          f"{'opp_tiledays':>12} {'opp_rev':>9} {'opp_$/td':>9}")
    out = {}
    for crop in products:
        cells = []
        for lbl in ("us", "opp"):
            td = median([t.get(crop, 0) for t, _ in per_ep[lbl]])
            rv = median([r.get(crop, 0) for _, r in per_ep[lbl]])
            cells.append((td, rv, rv / td if td else 0.0))
        if any(c[0] or c[1] for c in cells):
            out[crop] = {
                "us": {"tile_days": cells[0][0], "rev": cells[0][1], "per_td": cells[0][2]},
                "opp": {"tile_days": cells[1][0], "rev": cells[1][1], "per_td": cells[1][2]},
            }
            print(f"{crop:>12} | {cells[0][0]:11.0f} {cells[0][1]:9.0f} {cells[0][2]:9.1f} | "
                  f"{cells[1][0]:12.0f} {cells[1][1]:9.0f} {cells[1][2]:9.1f}")
    print("\n  (FERTILIZER/MILK/WOOL have 0 tile-days — they are animal output, not crops)")

    totals = {}
    for lbl in ("us", "opp"):
        totals[lbl] = {
            "crop_tile_days": median([sum(t.values()) for t, _ in per_ep[lbl]]),
            "crop_rev": median([
                sum(v for k, v in r.items() if k in ("WHEAT", "STRAWBERRY", "CARROT",
                                                     "MELON", "TOMATO"))
                for _, r in per_ep[lbl]
            ]),
            "animal_rev": median([
                sum(v for k, v in r.items() if k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
                for _, r in per_ep[lbl]
            ]),
        }
    print()
    for lbl in ("us", "opp"):
        t = totals[lbl]
        print(f"  {lbl:>4}: crop tile-days/ep={t['crop_tile_days']:.0f}  "
              f"crop $={t['crop_rev']:.0f}  animal+fert $={t['animal_rev']:.0f}")

    OUT.write_text(json.dumps({"n": n, "by_crop": out, "totals": totals}, indent=2),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
