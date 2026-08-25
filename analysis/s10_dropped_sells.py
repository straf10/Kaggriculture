#!/usr/bin/env python3
"""S10 P5.1 — quantify the ~11% dropped SELL rate.

Fill = committed / ordered per SELL order.  A dropped SELL is an open-loop
desync — the tape asks for `SELL X q` and the engine cannot commit q units
because the shed does not have them (or the price walk hits an unforeseen
constraint).  Memory `s9-live-read-55726984` reports `Sell-order fill ~0,89`
across the 92-episode live read.  The new P2 counters
(`sell_units_ordered` / `sell_units_committed` in `harness/metrics.py`)
report this per episode with product and day breakdown.

This module aggregates over the 97 live replays of `55726984`:
  - fill by product,
  - $/ep of dropped units (priced at the seat's own realised $/u for that
    product, which is what those units would have earned had the shed been
    non-empty),
  - day-of-episode distribution,
  - correlation of per-episode dropped $ with W/L outcome.

The dollar attribution uses per-seat realised price.  A dropped unit priced
at the average is the counterfactual "what we lost", not a market-clearing
what-if — the actual dumped-into-market case has been quantified separately
(the `floor_units` P2 counter shows what dropped-to-$1 looks like).

Read-only.  No agent/ change.  Output: `data/derived/s10_dropped_sells.json`.

CLI:
    python analysis/s10_dropped_sells.py [sub=55726984]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402
from harness.metrics import extract_metrics  # noqa: E402

DERIVED = ROOT / "data" / "derived"


def _to_env_json(m):
    return {"steps": m["steps"], "configuration": m["configuration"],
            "rewards": m["rewards"], "statuses": ["DONE", "DONE"]}


def analyse(sub="55726984"):
    per_ep = []
    agg_ordered = defaultdict(int)
    agg_committed = defaultdict(int)
    agg_dropped_units = defaultdict(int)
    agg_dropped_dollars = defaultdict(float)
    win_dropped = []
    loss_dropped = []
    n = 0
    for eid, m in ladder_episodes(sub):
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        env = _to_env_json(m)
        met = extract_metrics(env, seat)
        us_bank = float(m["rewards"][seat])
        opp_bank = float(m["rewards"][1 - seat])
        won = us_bank > opp_bank
        ordered_by_p = met["sell_units_ordered_by_product"]
        # Reconstruct committed by product from realized_units_by_product (this is a
        # count).  metrics.realized_units_by_product == units_sold_by_product.
        committed_by_p = met["realized_units_by_product"]
        realized_rev_by_p = met["realized_revenue_by_product"]
        dropped_by_p = {}
        dropped_dollars_by_p = {}
        for p, q_ord in ordered_by_p.items():
            q_com = int(committed_by_p.get(p, 0))
            dropped = max(0, int(q_ord) - q_com)
            dropped_by_p[p] = dropped
            price = (realized_rev_by_p.get(p, 0) / q_com) if q_com else 0.0
            dropped_dollars_by_p[p] = dropped * price
            agg_ordered[p] += int(q_ord)
            agg_committed[p] += q_com
            agg_dropped_units[p] += dropped
            agg_dropped_dollars[p] += dropped * price
        row = {
            "episode_id": eid,
            "seat": seat,
            "won": won,
            "us_bank": us_bank,
            "opp_bank": opp_bank,
            "dropped_units_by_product": dropped_by_p,
            "dropped_dollars_by_product": {k: round(v) for k, v in dropped_dollars_by_p.items()},
            "dropped_dollars_total": round(sum(dropped_dollars_by_p.values())),
        }
        per_ep.append(row)
        if won:
            win_dropped.append(row["dropped_dollars_total"])
        else:
            loss_dropped.append(row["dropped_dollars_total"])
        n += 1

    fill_by_product = {
        p: (agg_committed[p] / agg_ordered[p]) if agg_ordered[p] else None
        for p in agg_ordered
    }
    overall_fill = (sum(agg_committed.values()) / sum(agg_ordered.values())
                    if sum(agg_ordered.values()) else None)
    mean_win_drop = (sum(win_dropped) / len(win_dropped)) if win_dropped else 0.0
    mean_loss_drop = (sum(loss_dropped) / len(loss_dropped)) if loss_dropped else 0.0
    # Δ$/ep of dropped-sell burden by W/L side — the memo signal for P5.2.
    diff = mean_loss_drop - mean_win_drop

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"dropped_sells {sub}: overall fill={overall_fill:.3f}, "
                    f"dropped ${sum(agg_dropped_dollars.values()) / max(n, 1):.0f}/ep "
                    f"(loss-side ${mean_loss_drop:.0f} vs win-side ${mean_win_drop:.0f}, "
                    f"Δ=${diff:.0f})"),
        "submission": sub,
        "n": n,
        "overall_fill": overall_fill,
        "fill_by_product": fill_by_product,
        "dropped_units_by_product_per_ep": {
            p: round(v / max(n, 1), 1) for p, v in agg_dropped_units.items()
        },
        "dropped_dollars_by_product_per_ep": {
            p: round(v / max(n, 1)) for p, v in agg_dropped_dollars.items()
        },
        "dropped_dollars_win_side_per_ep_mean": round(mean_win_drop),
        "dropped_dollars_loss_side_per_ep_mean": round(mean_loss_drop),
        "dropped_dollars_delta_loss_minus_win": round(diff),
        "per_ep": per_ep,
    }


def main():
    sub = sys.argv[1] if len(sys.argv) > 1 else "55726984"
    out = analyse(sub)
    p = DERIVED / "s10_dropped_sells.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p} ({out['verdict']})")


if __name__ == "__main__":
    main()
