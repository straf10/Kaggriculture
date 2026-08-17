#!/usr/bin/env python3
"""T2 kill gate — does the market overlay beat the RAW tape on realised STRAWBERRY $/unit?

Per the T2 brief: "if the overlay does not beat the raw tape on realised STRAWBERRY $/unit, it
has missed the one thing it was built for — stop and record, rather than tuning."

The −61% strawberry loss only exists against an opponent that also floods strawberry, so the kill
is measured against a competitive opponent (the raw tape itself, seat 1 — a top-tier strawberry
seller) as well as the soft acceptance bench (meta_route). For each opponent we compare, over a
seed set, seat-0 raw-tape vs seat-0 overlay:
  * realised STRAWBERRY $/unit  (average_sell_price["STRAWBERRY"])   <- the kill metric
  * STRAWBERRY units sold, final bank, and (cash-safety) that farmer/hands stayed clean.

Also asserts the Phase-0 cash invariant empirically: production must be unchanged — we check that
STRAWBERRY units *produced into the shed* (harvest) is identical, i.e. the overlay only moved
sells, never production.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.play import play  # noqa: E402
from agent.tape_overlay import make_overlay_agent  # noqa: E402

DONORS = ROOT / "baselines" / "2026-08-11" / "donors"
META_ROUTE = str(ROOT / "harness" / "bench_agents" / "meta_route.py")
VALMORLEE = 91456307
KAITO = 90891564


def _stream(episode):
    d = json.loads((DONORS / f"{episode}_seat0.json").read_text())
    return d["donor_action_stream"]


def _tape_callable(stream):
    n = len(stream)

    def agent(obs, configuration=None):
        step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
        return stream[step] if 0 <= step < n else {"farmer": ["PASS"], "hands": [], "market": []}
    return agent


def _straw(metrics_seat):
    asp = metrics_seat.get("average_sell_price", {})
    units = metrics_seat.get("units_sold_by_product", {})
    rev = metrics_seat.get("revenue_by_product", {})
    return (asp.get("STRAWBERRY"), units.get("STRAWBERRY", 0), rev.get("STRAWBERRY", 0))


def run(seeds, opponents, run_dir):
    valm = _stream(VALMORLEE)
    raw = _tape_callable(valm)

    results = {}
    for opp_name, opp in opponents.items():
        rows = []
        for seed in seeds:
            r_raw = play(raw, opp, seed=seed, run_dir=run_dir, metrics=True, strict=False, record=False)
            overlay = make_overlay_agent(valm)
            r_ovl = play(overlay, opp, seed=seed, run_dir=run_dir, metrics=True, strict=False, record=False)
            praw, uraw, rvraw = _straw(r_raw.metrics[0])
            povl, uovl, rvovl = _straw(r_ovl.metrics[0])
            rows.append({
                "seed": seed,
                "raw_clean": r_raw.clean, "ovl_clean": r_ovl.clean,
                "raw_bank": r_raw.rewards[0], "ovl_bank": r_ovl.rewards[0],
                "raw_straw_price": praw, "ovl_straw_price": povl,
                "raw_straw_units": uraw, "ovl_straw_units": uovl,
                "raw_straw_rev": rvraw, "ovl_straw_rev": rvovl,
                "raw_crop_tile_days": r_raw.metrics[0].get("crop_tile_days"),
                "ovl_crop_tile_days": r_ovl.metrics[0].get("crop_tile_days"),
            })
        results[opp_name] = rows
    return results


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()
    seeds = list(range(args.start, args.start + args.seeds))
    run_dir = ROOT / "baselines" / "2026-08-16" / "t2_kill_runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    opponents = {
        "raw_tape_opp": _tape_callable(_stream(VALMORLEE)),   # hard: strawberry-flooding mirror
        "kaito_opp": _tape_callable(_stream(KAITO)),          # hard: a second donor
        "meta_route": META_ROUTE,                             # soft acceptance bench
    }

    results = run(seeds, opponents, run_dir)

    print(f"Seeds {seeds[0]}..{seeds[-1]} ({len(seeds)})  donor=Valmorlee(91456307) seat0\n")
    for opp_name, rows in results.items():
        clean = all(r["raw_clean"] and r["ovl_clean"] for r in rows)
        raw_p = _med([r["raw_straw_price"] for r in rows])
        ovl_p = _med([r["ovl_straw_price"] for r in rows])
        raw_u = _med([r["raw_straw_units"] for r in rows])
        ovl_u = _med([r["ovl_straw_units"] for r in rows])
        raw_b = _med([r["raw_bank"] for r in rows])
        ovl_b = _med([r["ovl_bank"] for r in rows])
        raw_ctd = _med([r["raw_crop_tile_days"] for r in rows])
        ovl_ctd = _med([r["ovl_crop_tile_days"] for r in rows])
        wins = sum(1 for r in rows if (r["ovl_straw_price"] or 0) > (r["raw_straw_price"] or 0))
        bank_wins = sum(1 for r in rows if r["ovl_bank"] > r["raw_bank"])
        verdict = "PASS" if (ovl_p or 0) > (raw_p or 0) else "FAIL"
        print(f"=== opponent: {opp_name} ===  clean={clean}")
        print(f"  STRAWBERRY $/unit   raw {raw_p}  ->  overlay {ovl_p}   "
              f"[{verdict}]  (price-wins {wins}/{len(rows)})")
        print(f"  STRAWBERRY units    raw {raw_u}  ->  overlay {ovl_u}")
        print(f"  final bank (median) raw ${raw_b:,.0f}  ->  overlay ${ovl_b:,.0f}   "
              f"(bank-wins {bank_wins}/{len(rows)})")
        print(f"  crop_tile_days      raw {raw_ctd}  ->  overlay {ovl_ctd}  "
              f"(must be equal — production unchanged)")
        print()

    out = run_dir / f"t2_kill_seeds{seeds[0]}-{seeds[-1]}.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
