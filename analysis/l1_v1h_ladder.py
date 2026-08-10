"""L1 ladder diagnostic for live v1h (submission 55383610).

Docs/data only — no agent changes. Reuses analysis.replay_profile.extract_profile
(MASTERPLAN §3.4: aggregate per-day state only, no trajectories).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.replay_profile import extract_profile

OUR = "STRAF"
ELITE = {5: 299, 10: 2212, 15: 21272, 20: 45689}
CHECK_DAYS = [0, 5, 10, 14, 15, 18, 20, 25, 29]
TPD = 24
ROOT = Path("baselines/2026-08-10/replays_v1h")
OUT = Path("baselines/2026-08-10/l1_v1h_curves.json")


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


def main() -> None:
    episodes = []
    silent = {
        "non_done_status": [],
        "empty_action_turns_our": [],
        "per_step_bad_status": [],
    }

    for path in sorted(ROOT.glob("episode-*-replay.json")):
        r = json.load(open(path, encoding="utf-8"))
        teams = r["info"].get("TeamNames") or []
        if OUR not in teams:
            print("WARN no STRAF", path.name, teams)
            continue
        our_seat = teams.index(OUR)
        opp_seat = 1 - our_seat
        opp_name = teams[opp_seat]
        rewards = r.get("rewards") or [None, None]
        statuses = r.get("statuses") or [None, None]

        if statuses and any(s not in (None, "DONE") for s in statuses):
            silent["non_done_status"].append((path.name, statuses))

        empty = 0
        bad_status = defaultdict(int)
        for step in r["steps"]:
            act = step[our_seat].get("action")
            if act is None:
                empty += 1
            st = step[our_seat].get("status")
            if st and st not in ("ACTIVE", "DONE", None):
                bad_status[st] += 1
        silent["empty_action_turns_our"].append((path.name, empty, len(r["steps"])))
        if bad_status:
            silent["per_step_bad_status"].append((path.name, dict(bad_status)))

        profiles = {}
        for seat in (0, 1):
            prof = extract_profile(r, seat)
            steps = r["steps"]
            daily_sales = []
            for day_row in prof["daily"]:
                day = day_row["day"]
                sold: dict = defaultdict(int)
                rev: dict = defaultdict(float)
                for hour in range(day * TPD, min((day + 1) * TPD, len(steps))):
                    obs = steps[hour][0]["observation"]
                    prices = (obs.get("market") or {}).get("prices") or {}
                    action = steps[hour][seat].get("action") or {}
                    for order in action.get("market") or []:
                        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                            prod, units = order[1], int(order[2])
                            sold[prod] += units
                            px = prices.get(prod)
                            if px is not None:
                                rev[prod] += float(px) * units
                avg_px = {p: (rev[p] / sold[p] if sold[p] else None) for p in sold}
                daily_sales.append(
                    {
                        "sold": dict(sold),
                        "avg_price": avg_px,
                        "units_total": sum(sold.values()),
                    }
                )
            profiles[seat] = {
                "daily": prof["daily"],
                "sales": daily_sales,
                "cum_sales": prof["final_cum_sales"],
            }

        our_final = rewards[our_seat] if rewards else profiles[our_seat]["daily"][-1]["money"]
        opp_final = rewards[opp_seat] if rewards else profiles[opp_seat]["daily"][-1]["money"]
        our_bank = {d["day"]: d["money"] for d in profiles[our_seat]["daily"]}
        opp_bank = {d["day"]: d["money"] for d in profiles[opp_seat]["daily"]}

        episodes.append(
            {
                "episode_id": int(path.stem.split("-")[1]),
                "our_seat": our_seat,
                "opp": opp_name,
                "our_final": our_final,
                "opp_final": opp_final,
                "win": our_final > opp_final,
                "statuses": statuses,
                "our_bank": our_bank,
                "opp_bank": opp_bank,
                "our_daily": profiles[our_seat]["daily"],
                "opp_daily": profiles[opp_seat]["daily"],
                "our_sales_daily": profiles[our_seat]["sales"],
                "our_cum_sales": profiles[our_seat]["cum_sales"],
                "opp_cum_sales": profiles[opp_seat]["cum_sales"],
                "empty_actions": empty,
            }
        )

    print(f"parsed {len(episodes)} episodes")
    wins = sum(1 for e in episodes if e["win"])
    print(f"W/L {wins}-{len(episodes) - wins}")
    print(f"our final median {median([e['our_final'] for e in episodes]):.0f}")
    print(f"opp final median {median([e['opp_final'] for e in episodes]):.0f}")

    print("\n=== BANK CURVE (median) vs ELITE ===")
    print(
        f"{'day':>4} {'us_med':>10} {'us_mean':>10} {'opp_med':>10} "
        f"{'elite':>10} {'gap_elite':>10} {'us/elite':>8}"
    )
    for d in CHECK_DAYS:
        us = [e["our_bank"].get(d) for e in episodes]
        opp = [e["opp_bank"].get(d) for e in episodes]
        um, om = median(us), median(opp)
        u_mean = mean(us)
        el = ELITE.get(d)
        gap = (um - el) if (um is not None and el is not None) else None
        ratio = (um / el) if (um is not None and el is not None and el) else None
        el_s = f"{el}" if el is not None else "-"
        gap_s = f"{gap:.0f}" if gap is not None else "-"
        ratio_s = f"{ratio:.2f}" if ratio else "-"
        print(f"{d:4d} {um:10.0f} {u_mean:10.0f} {om:10.0f} {el_s:>10} {gap_s:>10} {ratio_s:>8}")

    print("\n=== GAP GROWTH (us median vs elite) ===")
    for d in [5, 10, 15, 20]:
        um = median([e["our_bank"].get(d) for e in episodes])
        el = ELITE[d]
        print(f"d{d}: us={um:.0f} elite={el} gap={um - el:.0f} ratio={um / el:.2f}x")

    us0 = median([e["our_bank"].get(0) for e in episodes])
    us5 = median([e["our_bank"].get(5) for e in episodes])
    us10 = median([e["our_bank"].get(10) for e in episodes])
    us15 = median([e["our_bank"].get(15) for e in episodes])
    us20 = median([e["our_bank"].get(20) for e in episodes])
    print("\nAbsolute increments:")
    print(f"  us  d0->d5:  {us5 - us0:.0f}  | elite at d5={ELITE[5]}")
    print(f"  us  d5->d10: {us10 - us5:.0f}  | elite: {ELITE[10] - ELITE[5]}")
    print(f"  us  d10->d15: {us15 - us10:.0f} | elite: {ELITE[15] - ELITE[10]}")
    print(f"  us  d15->d20: {us20 - us15:.0f} | elite: {ELITE[20] - ELITE[15]}")

    print("\n=== FARM STATE at d5 (median our) ===")
    for key in [
        "hands",
        "tiles_planted",
        "animals_total",
        "unlocked_quadrants",
        "plants_wheat",
        "plants_strawberry",
        "plants_carrot",
    ]:
        usv = [e["our_daily"][5].get(key, 0) for e in episodes if len(e["our_daily"]) > 5]
        print(f"  {key:22s} us_med={median(usv)}")

    print("\n=== FARM STATE at d20 (median our / opp) ===")
    for key in [
        "hands",
        "tiles_planted",
        "animals_total",
        "unlocked_quadrants",
        "plants_wheat",
        "plants_strawberry",
        "plants_carrot",
    ]:
        usv = [e["our_daily"][20].get(key, 0) for e in episodes if len(e["our_daily"]) > 20]
        opv = [e["opp_daily"][20].get(key, 0) for e in episodes if len(e["opp_daily"]) > 20]
        print(f"  {key:22s} us_med={median(usv)}  opp_med={median(opv)}")

    print("\n=== CUM SALES end (median units) ===")
    all_prods = sorted({p for e in episodes for p in e["our_cum_sales"]})
    for p in all_prods:
        usv = [e["our_cum_sales"].get(p, 0) for e in episodes]
        opv = [e["opp_cum_sales"].get(p, 0) for e in episodes]
        print(f"  {p:12s} us={median(usv):.0f}  opp={median(opv):.0f}")

    print("\n=== MEAN SELL PRICE (volume-weighted per episode, then median) ===")
    for p in ["WHEAT", "STRAWBERRY", "MILK", "WOOL", "CARROT", "FERTILIZER"]:
        ep_avgs = []
        for e in episodes:
            units = rev = 0.0
            for day_s in e["our_sales_daily"]:
                u = day_s["sold"].get(p, 0)
                px = day_s["avg_price"].get(p)
                if u and px is not None:
                    units += u
                    rev += px * u
            if units:
                ep_avgs.append(rev / units)
        print(f"  {p:12s} median_avg_px={median(ep_avgs)}  n_eps={len(ep_avgs)}")

    print("\n=== EPISODE SCOREBOARD ===")
    for e in sorted(episodes, key=lambda x: -x["our_final"]):
        mark = "W" if e["win"] else "L"
        print(
            f"  {mark} ep={e['episode_id']} seat={e['our_seat']} "
            f"us={e['our_final']:.0f} opp={e['opp_final']:.0f} ({e['opp']}) "
            f"none_acts={e['empty_actions']}"
        )

    print("\n=== SILENT FAILURE CHECK ===")
    print("non_done_status:", silent["non_done_status"] or "none")
    empties = [x[1] for x in silent["empty_action_turns_our"]]
    print(
        f"None action turns (our seat): median={median(empties)} "
        f"max={max(empties) if empties else 0} / 720"
    )
    print("per-step bad statuses our seat:", silent["per_step_bad_status"] or "none")

    # Daily sold units median at key days
    print("\n=== DAILY SOLD UNITS (median our) at check days ===")
    for d in [5, 10, 15, 20]:
        by_prod = defaultdict(list)
        for e in episodes:
            if d < len(e["our_sales_daily"]):
                for p, u in e["our_sales_daily"][d]["sold"].items():
                    by_prod[p].append(u)
                # also zeros for missing
        print(f"  day {d}: " + ", ".join(
            f"{p}={median(by_prod[p]):.0f}" for p in sorted(by_prod) if median(by_prod[p])
        ))

    agg = {
        "n": len(episodes),
        "wins": wins,
        "our_final_median": median([e["our_final"] for e in episodes]),
        "opp_final_median": median([e["opp_final"] for e in episodes]),
        "bank_median": {
            str(d): median([e["our_bank"].get(d) for e in episodes]) for d in range(30)
        },
        "opp_bank_median": {
            str(d): median([e["opp_bank"].get(d) for e in episodes]) for d in range(30)
        },
        "elite": ELITE,
        "farm_d5": {
            k: median([e["our_daily"][5].get(k, 0) for e in episodes])
            for k in [
                "hands",
                "tiles_planted",
                "animals_total",
                "plants_wheat",
                "plants_strawberry",
            ]
        },
        "farm_d20": {
            k: median([e["our_daily"][20].get(k, 0) for e in episodes])
            for k in [
                "hands",
                "tiles_planted",
                "animals_total",
                "unlocked_quadrants",
                "plants_wheat",
                "plants_strawberry",
                "plants_carrot",
            ]
        },
        "silent": {
            "non_done": silent["non_done_status"],
            "none_action_median": median(empties),
            "none_action_max": max(empties) if empties else 0,
            "bad_status_eps": silent["per_step_bad_status"],
        },
        "scoreboard": [
            {
                "episode_id": e["episode_id"],
                "win": e["win"],
                "our": e["our_final"],
                "opp": e["opp_final"],
                "opp_name": e["opp"],
                "seat": e["our_seat"],
            }
            for e in sorted(episodes, key=lambda x: -x["our_final"])
        ],
    }
    OUT.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
