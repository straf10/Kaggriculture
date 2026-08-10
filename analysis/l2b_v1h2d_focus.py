"""L2b — focused follow-ups on the L2 ladder findings (docs/data only).

L2 showed: v1h.2d leads the median opponent until ~d20, then loses the whole margin
between d20 and d29. This script pins down *why*, on three axes:
  A. planting curve per crop per day (us vs opp) — is the farm going idle late?
  B. revenue decomposition from the engine-faithful market sim (units + $, same source)
  C. unit-turn budget: idle share over time, and animal upkeep load
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
ROOT = Path("baselines/2026-08-10/replays_v1h2d")
OUT = Path("baselines/2026-08-10/l2b_v1h2d_focus.json")


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def sec(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def main():
    eps = []
    for path in sorted(ROOT.glob("episode-*-replay.json")):
        r = json.load(open(path, encoding="utf-8"))
        teams = r["info"].get("TeamNames") or []
        if OUR not in teams:
            continue
        our = teams.index(OUR)
        opp = 1 - our
        eps.append({
            "id": int(path.stem.split("-")[1]),
            "our": our, "opp": opp, "opp_name": teams[opp],
            "replay": r,
            "pu": extract_profile(r, our),
            "po": extract_profile(r, opp),
            "mu": extract_metrics(r, our),
            "mo": extract_metrics(r, opp),
            "rw": r.get("rewards"),
        })
    print(f"parsed {len(eps)} episodes")

    # ---- A. planting curve -------------------------------------------------
    sec("A. PLANTED TILES PER DAY (median) — us vs opponent")
    print(f"{'day':>4} | {'us_tot':>6} {'wheat':>6} {'straw':>6} {'carrot':>6} "
          f"| {'opp_tot':>7} {'wheat':>6} {'straw':>6} {'melon':>6}")
    curve = {}
    for d in range(30):
        ut = median([e["pu"]["daily"][d]["tiles_planted"] for e in eps
                     if len(e["pu"]["daily"]) > d])
        ot = median([e["po"]["daily"][d]["tiles_planted"] for e in eps
                     if len(e["po"]["daily"]) > d])
        g = lambda p, d, k: median([e[p]["daily"][d].get(k, 0) for e in eps  # noqa: E731
                                    if len(e[p]["daily"]) > d])
        row = {
            "us_total": ut, "opp_total": ot,
            "us_wheat": g("pu", d, "plants_wheat"),
            "us_straw": g("pu", d, "plants_strawberry"),
            "us_carrot": g("pu", d, "plants_carrot"),
            "opp_wheat": g("po", d, "plants_wheat"),
            "opp_straw": g("po", d, "plants_strawberry"),
            "opp_melon": g("po", d, "plants_melon"),
        }
        curve[d] = row
        print(f"{d:4d} | {ut:6.1f} {row['us_wheat']:6.1f} {row['us_straw']:6.1f} "
              f"{row['us_carrot']:6.1f} | {ot:7.1f} {row['opp_wheat']:6.1f} "
              f"{row['opp_straw']:6.1f} {row['opp_melon']:6.1f}")

    # ---- A2. idle / free tiles we own but do not use -----------------------
    sec("A2. OWNED-BUT-EMPTY TILES (unlocked quadrants x 25 minus used), median")
    print(f"{'day':>4} {'us_owned':>9} {'us_used':>8} {'us_EMPTY':>9} | "
          f"{'opp_owned':>10} {'opp_used':>9} {'opp_EMPTY':>10}")
    empties = {}
    for d in [5, 10, 15, 20, 25, 29]:
        vals = {"us": [], "opp": []}
        for e in eps:
            for lbl, pk, seat in (("us", "pu", "our"), ("opp", "po", "opp")):
                if len(e[pk]["daily"]) <= d:
                    continue
                t = min(d * TPD + TPD - 1, len(e["replay"]["steps"]) - 1)
                farm = e["replay"]["steps"][t][0]["observation"]["farms"][e[seat]]
                owned = len(farm["unlocked_quadrants"]) * 25
                used = sum(
                    1 for row in farm["tiles"] for c in row
                    if isinstance(c, dict) and c.get("kind") not in (None, "EMPTY")
                )
                vals[lbl].append((owned, used))
        uo = median([x[0] for x in vals["us"]])
        uu = median([x[1] for x in vals["us"]])
        oo = median([x[0] for x in vals["opp"]])
        ou = median([x[1] for x in vals["opp"]])
        empties[d] = {"us_owned": uo, "us_used": uu, "opp_owned": oo, "opp_used": ou}
        print(f"{d:4d} {uo:9.0f} {uu:8.1f} {uo - uu:9.1f} | {oo:10.0f} {ou:9.1f} "
              f"{oo - ou:10.1f}")

    # ---- B. revenue decomposition (single source: engine market sim) -------
    sec("B. REVENUE DECOMPOSITION — engine-faithful market sim, per episode then median")
    def rev_table(mkey):
        per_ep = []
        for e in eps:
            by = defaultdict(lambda: [0, 0.0])
            for s in e[mkey]["market_sales"]:
                by[s["item"]][0] += 1
                by[s["item"]][1] += s["price"]
            per_ep.append(by)
        return per_ep
    us_t, op_t = rev_table("mu"), rev_table("mo")
    prods = sorted({p for t in us_t + op_t for p in t})
    print(f"{'product':>12} {'us_units':>9} {'us_$':>10} {'us_px':>7} | "
          f"{'opp_units':>10} {'opp_$':>10} {'opp_px':>7} | {'d$':>10}")
    rev_json = {}
    tu = to = 0.0
    for p in prods:
        uu = median([t[p][0] for t in us_t]) or 0
        ur = median([t[p][1] for t in us_t]) or 0
        ou = median([t[p][0] for t in op_t]) or 0
        orv = median([t[p][1] for t in op_t]) or 0
        upx = ur / uu if uu else 0
        opx = orv / ou if ou else 0
        tu += ur
        to += orv
        rev_json[p] = {"us_units": uu, "us_rev": ur, "opp_units": ou, "opp_rev": orv}
        print(f"{p:>12} {uu:9.0f} {ur:10.0f} {upx:7.1f} | {ou:10.0f} {orv:10.0f} "
              f"{opx:7.1f} | {ur - orv:10.0f}")
    # true per-episode totals (not sum of medians)
    tot_u = median([sum(v[1] for v in t.values()) for t in us_t])
    tot_o = median([sum(v[1] for v in t.values()) for t in op_t])
    print(f"{'SUM-OF-MED':>12} {'':9} {tu:10.0f} {'':7} | {'':10} {to:10.0f}")
    print(f"{'TRUE MEDIAN':>12} {'':9} {tot_u:10.0f} {'':7} | {'':10} {tot_o:10.0f} "
          f"{'':7} | {tot_u - tot_o:10.0f}")

    sec("B2. REVENUE BY SEASON PHASE (gross market $ realised, median per episode)")
    print(f"{'phase':>12} {'us_$':>10} {'opp_$':>10} {'ratio':>7}")
    phases = [("d0-d9", 0, 10), ("d10-d19", 10, 20), ("d20-d29", 20, 30)]
    phase_json = {}
    for lbl, a, b in phases:
        # market_sales carries no step index, so the phase split is a net bank delta
        # (revenue minus spend), not gross revenue — labelled as such below.
        du = median([e["pu"]["daily"][min(b - 1, 29)]["money"]
                     - e["pu"]["daily"][a]["money"] for e in eps])
        do = median([e["po"]["daily"][min(b - 1, 29)]["money"]
                     - e["po"]["daily"][a]["money"] for e in eps])
        phase_json[lbl] = {"us_net": du, "opp_net": do}
        print(f"{lbl:>12} {du:10.0f} {do:10.0f} {(du / do if do else 0):7.2f}")
    print("  (net bank delta, i.e. revenue minus spend — market_sales carries no step index)")

    # ---- C. unit-turn budget ------------------------------------------------
    sec("C. UNIT-TURN BUDGET — where our labour goes vs theirs")
    for lbl, mk in (("us", "mu"), ("opp", "mo")):
        mv = sum(e[mk]["worker_turns_moving"] for e in eps)
        wk = sum(e[mk]["worker_turns_working"] for e in eps)
        idl = sum(e[mk]["worker_turns_idle"] for e in eps)
        tot = mv + wk + idl
        print(f"  {lbl:>4}: total={tot / len(eps):7.0f}/ep  moving={mv / tot:6.1%} "
              f"working={wk / tot:6.1%} idle={idl / tot:6.1%}  "
              f"(idle turns/ep = {idl / len(eps):.0f})")
    au = median([e["mu"]["animals_underfed_days"] for e in eps])
    ao = median([e["mo"]["animals_underfed_days"] for e in eps])
    print(f"\n  animals_underfed_days: us_med={au}  opp_med={ao}")

    sec("C2. ANIMALS: composition us vs opponent at d15 (median)")
    akeys = set()
    for e in eps:
        akeys |= {k for k in e["pu"]["daily"][15] if k.startswith("animals_")}
        akeys |= {k for k in e["po"]["daily"][15] if k.startswith("animals_")}
    for k in sorted(akeys):
        u = median([e["pu"]["daily"][15].get(k, 0) for e in eps])
        o = median([e["po"]["daily"][15].get(k, 0) for e in eps])
        if u or o:
            print(f"    {k:22s} us={u:>6} opp={o:>6}")

    sec("D. THE 11 LOSSES TO >$70k OPPONENTS — bank curve of us vs them")
    strong = [e for e in eps if (e["rw"][e["opp"]] or 0) >= 70000]
    print(f"n={len(strong)}")
    print(f"{'day':>4} {'us_med':>9} {'strong_opp_med':>15} {'ratio':>7}")
    for d in [5, 10, 15, 18, 20, 22, 25, 27, 29]:
        u = median([e["pu"]["daily"][d]["money"] for e in strong])
        o = median([e["po"]["daily"][d]["money"] for e in strong])
        print(f"{d:4d} {u:9.0f} {o:15.0f} {(u / o if o else 0):7.2f}")
    print("\n  strong-opponent farm at d15 (median):")
    for k in ["hands", "tiles_planted", "animals_total", "plants_wheat",
              "plants_strawberry", "plants_melon", "plants_carrot"]:
        u = median([e["pu"]["daily"][15].get(k, 0) for e in strong])
        o = median([e["po"]["daily"][15].get(k, 0) for e in strong])
        print(f"    {k:22s} us={u:>6} strong_opp={o:>6}")

    OUT.write_text(json.dumps({
        "n": len(eps), "planting_curve": curve, "owned_vs_used": empties,
        "revenue": rev_json, "revenue_total_median": {"us": tot_u, "opp": tot_o},
        "phase_net": phase_json,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
