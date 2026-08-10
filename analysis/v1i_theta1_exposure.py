"""Θ1 — §Α.3 differentiation diagnostic (docs/data only, no new episodes, no `agent/` change).

§Α.3 requires the two active submissions to differ in **exposure**, and current_phase.md §Α
records the open debt: `v1m_d2` is `v1h_2d` plus market-order emission ordering — same herd,
same tiles, same sell-side thresholds. This script asks the question that decides whether the
remaining v1i work (per-unit sum + prediction controller) can *be* that differentiation:

    against the opponents v1h.2d actually loses to (§0α: record 0-11 vs >$70k banks), is the
    deficit a **price** gap (what a sell-side increment moves) or a **volume** gap (what it
    cannot)?

Decomposition, per product, on the 34 L2 ladder replays:

    price_gap  = our_units * (their $/u - our $/u)     <- reachable by sell-side/timing
    volume_gap = (their_units - our_units) * their $/u  <- reachable only by production

Usage: python analysis/v1i_theta1_exposure.py
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.metrics import extract_metrics  # noqa: E402

OUR_TEAM = "STRAF"
REPLAYS = REPO / "baselines" / "2026-08-10" / "replays_v1h2d"
OUT = REPO / "gates" / "v1i_theta1_exposure" / "exposure.json"

# §0α buckets the 34 replays by opponent bank; the 0-11 record lives in the top bucket.
BUCKETS = (("lt40k", 0, 40_000), ("40k_70k", 40_000, 70_000), ("gt70k", 70_000, 10**9))


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else 0.0


def main() -> None:
    per_bucket = defaultdict(list)
    for path in sorted(REPLAYS.glob("episode-*-replay.json")):
        replay = json.loads(path.read_text(encoding="utf-8"))
        teams = replay["info"].get("TeamNames") or []
        if OUR_TEAM not in teams:
            continue
        ours = teams.index(OUR_TEAM)
        us = extract_metrics(replay, ours)
        opponent = extract_metrics(replay, 1 - ours)
        bucket = next(
            name for name, low, high in BUCKETS
            if low <= opponent["final_bank"] < high
        )
        per_bucket[bucket].append({"us": us, "opp": opponent, "episode": path.stem})

    report = {"replays": sum(len(v) for v in per_bucket.values()), "buckets": {}}
    for name, _low, _high in BUCKETS:
        episodes = per_bucket.get(name, [])
        if not episodes:
            continue
        wins = sum(1 for e in episodes if e["us"]["final_bank"] > e["opp"]["final_bank"])
        products = sorted(
            {p for e in episodes for side in ("us", "opp")
             for p in e[side]["units_sold_by_product"]}
        )
        by_product = {}
        price_gap_total = 0.0
        volume_gap_total = 0.0
        for product in products:
            our_units = median([e["us"]["units_sold_by_product"].get(product, 0)
                                for e in episodes])
            their_units = median([e["opp"]["units_sold_by_product"].get(product, 0)
                                  for e in episodes])
            our_price = median([e["us"]["realized_price_per_unit"].get(product)
                                for e in episodes if product in e["us"]["realized_price_per_unit"]])
            their_price = median([e["opp"]["realized_price_per_unit"].get(product)
                                  for e in episodes
                                  if product in e["opp"]["realized_price_per_unit"]])
            price_gap = our_units * (their_price - our_price) if our_price and their_price else 0.0
            volume_gap = (their_units - our_units) * (their_price or our_price)
            price_gap_total += max(0.0, price_gap)
            volume_gap_total += max(0.0, volume_gap)
            by_product[product] = {
                "our_units": our_units, "their_units": their_units,
                "our_price_per_unit": round(our_price, 2),
                "their_price_per_unit": round(their_price, 2),
                "price_gap": round(price_gap, 1), "volume_gap": round(volume_gap, 1),
            }
        report["buckets"][name] = {
            "episodes": len(episodes),
            "record": f"{wins}-{len(episodes) - wins}",
            "our_median_bank": median([e["us"]["final_bank"] for e in episodes]),
            "their_median_bank": median([e["opp"]["final_bank"] for e in episodes]),
            "median_bank_deficit": median([e["opp"]["final_bank"] - e["us"]["final_bank"]
                                           for e in episodes]),
            "our_crop_tile_days": median([e["us"]["crop_tile_days"] for e in episodes]),
            "their_crop_tile_days": median([e["opp"]["crop_tile_days"] for e in episodes]),
            "price_gap_total": round(price_gap_total, 1),
            "volume_gap_total": round(volume_gap_total, 1),
            "by_product": by_product,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
