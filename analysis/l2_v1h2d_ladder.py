"""L2 ladder diagnostic for live v1h.2d (submission 55390611).

Docs/data only — no agent changes. Aggregate per-day state + harness metric extraction
on real ladder replays (MASTERPLAN §3.4: no trajectories leave this module).

Answers, on the *real* ladder rather than in mirror:
  1. Did the v1h.2d fixes (overflow / escapes / <=$5 dumping) actually land live?
  2. Where in the season does the gap to the opponent open, and against whom?
  3. Is our ceiling production-side (tiles/hands/units produced) or market-side
     (units sold / price realised)?
  4. What is the priced loss (current_phase.md §1 Απόφαση Α) on the ladder?

Usage:
    python analysis/l2_v1h2d_ladder.py
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
TPD = 24
# L1 elite reference (docs/meta/ladder_snapshots.md#l1-v1h) — median bank of ranks 3-20.
ELITE = {5: 299, 10: 2212, 15: 21272, 20: 45689}
CHECK_DAYS = [0, 3, 5, 8, 10, 12, 15, 18, 20, 25, 29]
# current_phase.md §1 Απόφαση Α
PRICES = {"animals_escaped": 1000.0, "shed_overflow_burnt": 150.0, "lost_crop_tiles": 300.0}

ROOT_2D = Path("baselines/2026-08-10/replays_v1h2d")
ROOT_1H = Path("baselines/2026-08-10/replays_v1h")
OUT = Path("baselines/2026-08-10/l2_v1h2d_curves.json")


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load(root: Path, with_metrics: bool = True) -> list:
    episodes = []
    for path in sorted(root.glob("episode-*-replay.json")):
        r = json.load(open(path, encoding="utf-8"))
        teams = r["info"].get("TeamNames") or []
        if OUR not in teams:
            print("WARN no STRAF", path.name, teams)
            continue
        our = teams.index(OUR)
        opp = 1 - our
        rewards = r.get("rewards") or [None, None]

        prof_us = extract_profile(r, our)
        prof_op = extract_profile(r, opp)

        empty = sum(1 for st in r["steps"] if st[our].get("action") is None)

        row = {
            "episode_id": int(path.stem.split("-")[1]),
            "seat": our,
            "opp_name": teams[opp],
            "our_final": rewards[our],
            "opp_final": rewards[opp],
            "win": (rewards[our] or 0) > (rewards[opp] or 0),
            "statuses": r.get("statuses"),
            "empty_actions": empty,
            "our_bank": {d["day"]: d["money"] for d in prof_us["daily"]},
            "opp_bank": {d["day"]: d["money"] for d in prof_op["daily"]},
            "our_daily": prof_us["daily"],
            "opp_daily": prof_op["daily"],
            "our_cum_sales": prof_us["final_cum_sales"],
            "opp_cum_sales": prof_op["final_cum_sales"],
        }
        if with_metrics:
            try:
                row["m_us"] = extract_metrics(r, our)
                row["m_op"] = extract_metrics(r, opp)
            except Exception as exc:  # noqa: BLE001
                print(f"  metrics FAIL ep={row['episode_id']}: {exc}")
                row["m_us"] = row["m_op"] = None
        episodes.append(row)
    return episodes


def priced_loss(m) -> float:
    if not m:
        return 0.0
    tiles = max(m.get("unexpected_weeds_lost", 0) or 0, m.get("water_weeds_lost", 0) or 0)
    return (
        (m.get("animals_escaped", 0) or 0) * PRICES["animals_escaped"]
        + (m.get("shed_overflow_burnt", 0) or 0) * PRICES["shed_overflow_burnt"]
        + tiles * PRICES["lost_crop_tiles"]
    )


def sec(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> None:
    eps = load(ROOT_2D)
    print(f"\nv1h.2d: parsed {len(eps)} ladder episodes")
    old = load(ROOT_1H, with_metrics=True)
    print(f"v1h   : parsed {len(old)} ladder episodes (comparison)")

    wins = sum(1 for e in eps if e["win"])
    sec("1. SCOREBOARD")
    print(f"W/L = {wins}-{len(eps) - wins}  ({wins / len(eps):.0%})")
    print(f"our final: median={median([e['our_final'] for e in eps]):.0f} "
          f"mean={mean([e['our_final'] for e in eps]):.0f} "
          f"min={min(e['our_final'] for e in eps):.0f} "
          f"max={max(e['our_final'] for e in eps):.0f}")
    print(f"opp final: median={median([e['opp_final'] for e in eps]):.0f} "
          f"max={max(e['opp_final'] for e in eps):.0f}")
    ow = sum(1 for e in old if e["win"])
    print(f"\n[v1h ladder for reference] W/L={ow}-{len(old) - ow}  "
          f"our_median={median([e['our_final'] for e in old]):.0f}")

    sec("2. BANK CURVE — us vs opponent vs elite (median over episodes)")
    print(f"{'day':>4} {'us_med':>9} {'us_mean':>9} {'opp_med':>9} {'us-opp':>9} "
          f"{'elite':>8} {'us/elite':>9} {'v1h_med':>9}")
    for d in CHECK_DAYS:
        us = median([e["our_bank"].get(d) for e in eps])
        um = mean([e["our_bank"].get(d) for e in eps])
        op = median([e["opp_bank"].get(d) for e in eps])
        old_us = median([e["our_bank"].get(d) for e in old])
        el = ELITE.get(d)
        ratio = f"{us / el:.2f}x" if el else "-"
        print(f"{d:4d} {us:9.0f} {um:9.0f} {op:9.0f} {us - op:9.0f} "
              f"{(el if el else '-'):>8} {ratio:>9} {old_us:9.0f}")

    sec("3. WHERE THE GAP OPENS — per-day increment, us vs opponent")
    print(f"{'window':>10} {'us_delta':>10} {'opp_delta':>10} {'ratio':>8}")
    bounds = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 29)]
    for a, b in bounds:
        du = median([e["our_bank"].get(b, 0) - e["our_bank"].get(a, 0) for e in eps])
        do = median([e["opp_bank"].get(b, 0) - e["opp_bank"].get(a, 0) for e in eps])
        r = f"{du / do:.2f}x" if do else "-"
        print(f"  d{a:>2}->d{b:<3} {du:10.0f} {do:10.0f} {r:>8}")

    sec("4. LOSSES ON THE LADDER (harness/metrics on real replays) — our seat")
    keys = ["animals_escaped", "shed_overflow_burnt", "water_weeds_lost",
            "unexpected_weeds_lost", "weeds_lost", "decay_weeds_lost",
            "plant_decay_units_lost", "clipped_production_ticks",
            "units_sold_at_or_below_5", "animals_underfed_days"]
    have = [e for e in eps if e.get("m_us")]
    have_old = [e for e in old if e.get("m_us")]
    print(f"{'metric':>26} {'v1h2d tot':>10} {'/ep':>8} {'max_ep':>8} | "
          f"{'v1h tot':>9} {'/ep':>8}")
    for k in keys:
        v = [e["m_us"][k] or 0 for e in have]
        vo = [e["m_us"][k] or 0 for e in have_old]
        print(f"{k:>26} {sum(v):10d} {sum(v) / len(have):8.2f} {max(v):8d} | "
              f"{sum(vo):9d} {sum(vo) / len(have_old):8.2f}")
    pl = [priced_loss(e["m_us"]) for e in have]
    plo = [priced_loss(e["m_us"]) for e in have_old]
    print(f"\n{'PRICED LOSS $/ep':>26} {sum(pl) / len(have):18.1f} "
          f"{'':8} | {'':9} {sum(plo) / len(have_old):8.1f}")

    sec("5. LOSSES — OPPONENT seat, same metrics (do they leak too?)")
    print(f"{'metric':>26} {'opp tot':>10} {'/ep':>8} | {'our /ep':>8}")
    for k in keys:
        vo = [e["m_op"][k] or 0 for e in have if e.get("m_op")]
        vu = [e["m_us"][k] or 0 for e in have]
        if vo:
            print(f"{k:>26} {sum(vo):10d} {sum(vo) / len(vo):8.2f} | "
                  f"{sum(vu) / len(vu):8.2f}")

    sec("6. WORKER UTILISATION — us vs opponent")
    for lbl, key in (("us", "m_us"), ("opp", "m_op")):
        rows = [e[key] for e in have if e.get(key)]
        mv = sum(r["worker_turns_moving"] for r in rows)
        wk = sum(r["worker_turns_working"] for r in rows)
        idl = sum(r["worker_turns_idle"] for r in rows)
        tot = mv + wk + idl
        print(f"  {lbl:>4}: moving={mv / tot:.1%} working={wk / tot:.1%} idle={idl / tot:.1%} "
              f"(total unit-turns/ep = {tot / len(rows):.0f})")

    sec("7. FARM STATE — us vs opponent, at check days (median)")
    fkeys = ["hands", "tiles_planted", "animals_total", "unlocked_quadrants",
             "plants_wheat", "plants_strawberry", "plants_carrot", "plants_melon"]
    for d in [5, 10, 15, 20, 29]:
        print(f"\n  --- day {d} ---")
        for k in fkeys:
            u = median([e["our_daily"][d].get(k, 0) for e in eps if len(e["our_daily"]) > d])
            o = median([e["opp_daily"][d].get(k, 0) for e in eps if len(e["opp_daily"]) > d])
            if u or o:
                print(f"    {k:22s} us={u:>6} opp={o:>6}")

    sec("8. SALES VOLUME AND PRICE REALISED — us vs opponent (median per episode)")
    prods = sorted({p for e in eps for p in e["our_cum_sales"]}
                   | {p for e in eps for p in e["opp_cum_sales"]})
    print(f"{'product':>12} {'us_units':>9} {'opp_units':>10} {'us_avg_px':>10} "
          f"{'opp_avg_px':>11} {'us_rev':>10} {'opp_rev':>10}")
    tot_us_rev = tot_op_rev = 0.0
    for p in prods:
        uu = median([e["our_cum_sales"].get(p, 0) for e in eps])
        ou = median([e["opp_cum_sales"].get(p, 0) for e in eps])
        upx, opx, urev, orev = [], [], [], []
        for e in have:
            for m, px, rev in ((e["m_us"], upx, urev), (e.get("m_op"), opx, orev)):
                if not m:
                    continue
                s = [x for x in m["market_sales"] if x["item"] == p]
                if s:
                    px.append(sum(x["price"] for x in s) / len(s))
                    rev.append(sum(x["price"] for x in s))
        mu_rev, mo_rev = median(urev) or 0, median(orev) or 0
        tot_us_rev += mu_rev
        tot_op_rev += mo_rev
        print(f"{p:>12} {uu:9.0f} {ou:10.0f} "
              f"{(median(upx) or 0):10.1f} {(median(opx) or 0):11.1f} "
              f"{mu_rev:10.0f} {mo_rev:10.0f}")
    print(f"{'TOTAL(med)':>12} {'':9} {'':10} {'':10} {'':11} "
          f"{tot_us_rev:10.0f} {tot_op_rev:10.0f}")

    sec("9. BREAKDOWN BY OPPONENT STRENGTH")
    buckets = [("weak  <40k", 0, 40000), ("mid 40-70k", 40000, 70000),
               ("strong >70k", 70000, 10 ** 9)]
    for lbl, lo, hi in buckets:
        sel = [e for e in eps if lo <= (e["opp_final"] or 0) < hi]
        if not sel:
            continue
        w = sum(1 for e in sel if e["win"])
        print(f"  {lbl:>12}: n={len(sel):2d} W/L={w}-{len(sel) - w} "
              f"our_med={median([e['our_final'] for e in sel]):>8.0f} "
              f"opp_med={median([e['opp_final'] for e in sel]):>8.0f} "
              f"our_d15={median([e['our_bank'].get(15) for e in sel]):>8.0f} "
              f"opp_d15={median([e['opp_bank'].get(15) for e in sel]):>8.0f}")

    sec("10. PER-EPISODE SCOREBOARD")
    for e in sorted(eps, key=lambda x: -(x["our_final"] or 0)):
        m = e.get("m_us") or {}
        print(f"  {'W' if e['win'] else 'L'} ep={e['episode_id']} seat={e['seat']} "
              f"us={e['our_final']:>7.0f} opp={e['opp_final']:>7.0f} "
              f"esc={m.get('animals_escaped', '?'):>2} ovf={m.get('shed_overflow_burnt', '?'):>4} "
              f"ww={m.get('water_weeds_lost', '?'):>3} lo5={m.get('units_sold_at_or_below_5', '?'):>4} "
              f"none={e['empty_actions']:>3}  ({e['opp_name'][:28]})")

    sec("11. SILENT FAILURE CHECK")
    bad = [(e["episode_id"], e["statuses"]) for e in eps
           if any(s not in (None, "DONE") for s in (e["statuses"] or []))]
    print("non-DONE statuses:", bad or "none")
    em = [e["empty_actions"] for e in eps]
    print(f"None-action turns (our seat): median={median(em)} max={max(em)} / 720")
    ab = [e["episode_id"] for e in have if e["m_us"].get("market_sim_aborted")]
    print("market_sim_aborted episodes:", ab or "none")

    agg = {
        "submission": 55390611,
        "n": len(eps),
        "wins": wins,
        "our_final_median": median([e["our_final"] for e in eps]),
        "opp_final_median": median([e["opp_final"] for e in eps]),
        "bank_median": {str(d): median([e["our_bank"].get(d) for e in eps]) for d in range(30)},
        "opp_bank_median": {str(d): median([e["opp_bank"].get(d) for e in eps]) for d in range(30)},
        "v1h_bank_median": {str(d): median([e["our_bank"].get(d) for e in old]) for d in range(30)},
        "elite": ELITE,
        "ladder_metrics_per_ep": {
            k: sum(e["m_us"][k] or 0 for e in have) / len(have) for k in keys
        },
        "ladder_metrics_per_ep_opp": {
            k: sum(e["m_op"][k] or 0 for e in have if e.get("m_op"))
            / max(1, sum(1 for e in have if e.get("m_op"))) for k in keys
        },
        "priced_loss_per_ep": sum(pl) / len(have),
        "farm_by_day": {
            str(d): {
                "us": {k: median([e["our_daily"][d].get(k, 0) for e in eps
                                  if len(e["our_daily"]) > d]) for k in fkeys},
                "opp": {k: median([e["opp_daily"][d].get(k, 0) for e in eps
                                   if len(e["opp_daily"]) > d]) for k in fkeys},
            } for d in [5, 10, 15, 20, 29]
        },
        "scoreboard": [
            {"episode_id": e["episode_id"], "win": e["win"], "our": e["our_final"],
             "opp": e["opp_final"], "opp_name": e["opp_name"], "seat": e["seat"]}
            for e in sorted(eps, key=lambda x: -(x["our_final"] or 0))
        ],
    }
    OUT.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
