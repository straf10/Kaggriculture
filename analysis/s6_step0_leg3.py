#!/usr/bin/env python3
"""S6 step 0, leg 3 — is the town readable in time? (ROADMAP §4.3 S6 step 0).

C-B conditions on `obs.town.unlocked_shops`. Shops unlock one every `townShopUnlockInterval`
(3) days, capped at 8 (engine_reference/kaggriculture.py:884-891), so the town is not fully
known until ~day 24, while the sell calendar starts on day 2-6 (§4.0). This measures *when*
the draw becomes decision-relevant: per episode, the earliest day after which the rank order
of STRAWBERRY / WOOL / MILK shop drain is stable for the rest of the season.

Also checks the agent's own gate: `agent/planner.py` gates the shop-adaptive floor on
`shop_evidence_min_unlocks` (default 5). Five unlocks = day 15 (unlock on day%3==0). We report
what fraction of the season and of premium sells happen before that threshold, i.e. whether it
is early enough to matter or so late that C-B can only act on the last third of the season.

Reads the official kaggle/kaggriculture-episodes-2026-08-16 replays (engine 1.32.7). Aggregate
only (per-day shop lists + per-product drain rank); no per-unit action sequence is read.

Usage:
    python analysis/s6_step0_leg3.py data/archive/raw/2026-08-16 --sample 150
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.v1v_shop_demand import units_per_tick  # noqa: E402

PREMIUM = ("STRAWBERRY", "WOOL", "MILK")
SHOP_EVIDENCE_MIN_UNLOCKS = 5          # agent/config.py default
UNLOCK_INTERVAL = 3                    # townShopUnlockInterval
# §4.0 sell calendar first-sell days (median over 120 seats)
FIRST_SELL_DAY = {"WHEAT": 5, "FERTILIZER": 2, "WOOL": 6, "MILK": 9, "MELON": 10, "STRAWBERRY": 14}


def load(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def _rank_order(drain: dict) -> tuple:
    """Rank order of the three premiums by drain, ties broken by fixed name order so a stable
    tie does not read as churn."""
    return tuple(sorted(PREMIUM, key=lambda p: (-drain.get(p, 0), p)))


def profile_episode(replay: dict, turns_per_day: int = 24) -> dict | None:
    steps = replay["steps"]
    if len(steps) < 700:
        return None
    n_days = len(steps) // turns_per_day
    # unlocked_shops at the end of each day (read at the last step of the day)
    day_drain = []
    day_nshops = []
    for day in range(n_days):
        idx = min(day * turns_per_day + turns_per_day - 1, len(steps) - 1)
        town = steps[idx][0]["observation"].get("town", {}) or {}
        shops = list(town.get("unlocked_shops") or ())
        upt = units_per_tick(shops)
        day_drain.append({p: upt.get(p, 0) for p in PREMIUM})
        day_nshops.append(len(shops))

    final_rank = _rank_order(day_drain[-1])
    # earliest day D such that rank order is `final_rank` for every day >= D
    stable_from = n_days - 1
    for day in range(n_days - 1, -1, -1):
        if _rank_order(day_drain[day]) == final_rank:
            stable_from = day
        else:
            break
    # day at which >=5 shops first unlocked
    day_5_unlocks = next((d for d, n in enumerate(day_nshops) if n >= SHOP_EVIDENCE_MIN_UNLOCKS), None)
    day_8_unlocks = next((d for d, n in enumerate(day_nshops) if n >= 8), None)
    return {
        "episode_id": (replay.get("info") or {}).get("EpisodeId"),
        "n_days": n_days,
        "final_drain": day_drain[-1],
        "rank_stable_from_day": stable_from,
        "day_5_unlocks": day_5_unlocks,
        "day_8_unlocks": day_8_unlocks,
        "nshops_by_day": day_nshops,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, nargs="?", default=Path("data/archive/raw/2026-08-16"))
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--out", type=Path, default=Path("data/derived/s6_step0_leg3.json"))
    args = ap.parse_args()

    paths = sorted(p for p in args.source.iterdir()
                   if p.suffix in (".json", ".gz") and p.stem != "manifest")
    if args.sample and len(paths) > args.sample:
        stride = len(paths) / args.sample
        paths = [paths[int(i * stride)] for i in range(args.sample)]

    rows = []
    for i, path in enumerate(paths, 1):
        try:
            row = profile_episode(load(path))
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] {path.name}: FAILED {exc}", file=sys.stderr)
            continue
        if row:
            rows.append(row)

    stable = [r["rank_stable_from_day"] for r in rows]
    d5 = [r["day_5_unlocks"] for r in rows if r["day_5_unlocks"] is not None]
    d8 = [r["day_8_unlocks"] for r in rows if r["day_8_unlocks"] is not None]

    def q(xs, p):
        s = sorted(xs)
        return s[min(len(s) - 1, int(p * (len(s) - 1)))]

    # of episodes: is the premium rank stable by the time each premium starts selling?
    stable_before_sell = {}
    for p in PREMIUM:
        d = FIRST_SELL_DAY[p]
        stable_before_sell[p] = sum(1 for r in rows if r["rank_stable_from_day"] <= d) / len(rows)

    summary = {
        "episodes": len(rows),
        "rank_stable_from_day": {"p10": q(stable, .10), "p25": q(stable, .25),
                                 "median": statistics.median(stable), "p75": q(stable, .75),
                                 "p90": q(stable, .90), "mean": round(statistics.fmean(stable), 1)},
        "day_5_unlocks": {"median": statistics.median(d5), "p90": q(d5, .90)} if d5 else None,
        "day_8_unlocks": {"median": statistics.median(d8), "p90": q(d8, .90)} if d8 else None,
        "premium_first_sell_day": FIRST_SELL_DAY,
        "share_rank_stable_by_first_sell_day": stable_before_sell,
        "shop_evidence_min_unlocks": SHOP_EVIDENCE_MIN_UNLOCKS,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1),
                        encoding="utf-8")

    print(f"\n{'='*72}\nLEG 3 — is the town readable in time?\n{'='*72}")
    print(f"episodes: {len(rows)}  (engine 1.32.7, official 08-16 dataset)")
    s = summary["rank_stable_from_day"]
    print(f"\npremium drain rank order becomes stable-to-end on day:")
    print(f"  p10={s['p10']}  p25={s['p25']}  median={s['median']}  p75={s['p75']}  "
          f"p90={s['p90']}  mean={s['mean']}")
    print(f"\nshops unlocked (1 per {UNLOCK_INTERVAL} days, cap 8):")
    if summary["day_5_unlocks"]:
        print(f"  >=5 shops (the shop_evidence_min_unlocks gate): "
              f"median day {summary['day_5_unlocks']['median']}, p90 day {summary['day_5_unlocks']['p90']}")
    if summary["day_8_unlocks"]:
        print(f"  all 8 shops: median day {summary['day_8_unlocks']['median']}, "
              f"p90 day {summary['day_8_unlocks']['p90']}")
    print(f"\nshare of episodes whose premium rank is already stable by that product's first sell day:")
    for p in PREMIUM:
        print(f"  {p:<11} first sell day {FIRST_SELL_DAY[p]:>2}: {stable_before_sell[p]:.0%} stable in time")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
