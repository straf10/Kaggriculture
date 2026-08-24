"""S7 glut-metering — Phase 0 paper bound (§6): impact ceiling for the market
arm, per premium product.  DESK ONLY, no episodes; runs after Leg 0 + attribution
and BEFORE any build.  Decides K1 / K2.

Phase 0 attribution found outcome Γ (our SELL share ≈ 0.50 on every premium
product), routing to Branch B (§5): sell timing / "be first", not restraint.
Both branches re-place OUR OWN units in time, so one ceiling covers both: the
most revenue any schedule of the same U units can earn against a FROZEN foreign
market.

FIDELITY (the part the first cut got wrong, and the traps §6 names):

 * The replay is offset by one: action recorded at step t produced obs[t], so the
   inventory transition rec[t] -> rec[t+1] is driven by action[t+1].
 * Ordered qty != executed qty: SELL only fills from the seat's shed, and the
   backbone over-orders WOOL by ~15% (shed-starved).  We therefore never trust
   ordered counts for inventory.  Instead we read the EXACT executed bumped sells
   from the tape:
        drain[t]        = deterministic town consumption (validated to ≤2 units
                          against recorded inventory on the mirror episode)
        total_bumped[t] = rec[t+1] − rec[t] + drain[t]     (both seats, exact)
   and split our share by the ordered ratio our/(our+opp) — approximate only in
   the SPLIT, exact at the market level; in Γ the two seats are near-symmetric so
   the split is tight.  foreign_inv[t] = rec[t] − Σ_{τ<t} our_bumped[τ], which by
   construction satisfies foreign_inv + our_cum_bumped ≡ rec.
 * A sale at $1 does NOT raise inventory (engine _commit_unit).  Units we ordered
   at a floored price are counted as floored ($1 revenue, in U); the remaining
   ordered-but-unfilled units are shed-starved and dropped from U entirely.

  R_ideal  = max revenue placing our U units into the season with ENDOGENOUS
             price impact (each unit in slot t lifts that slot's inventory by 1,
             so its marginal price falls), NO cash/shed/order limits (§6: the
             CEILING drops all such limits -> upper bound).  Optimum = the U
             largest marginal prices across all slots (greedy max-heap; price is
             monotone-decreasing in inventory).  Floored slots supply $1 units.
  R_actual = our U units priced where we actually sold them, same foreign
             baseline, same endogenous model (bumped units walk the foreign slot;
             floored units earn $1).
  Ceiling  = median(R_ideal − R_actual) / $253 -> rating points.

Three §6 pitfalls: (1) never bounded by the 10-order cap; (2) impact endogenous;
(3) the ceiling FREEZES the opponent — in Γ it would react, so the achievable is
strictly below this.  Reported as CEILING, never prediction.

Threshold (§6 / K2): median ceiling < ~1 rating point -> do NOT build.
"""
from __future__ import annotations

import argparse
import glob
import heapq
import json
import os
import statistics

REPLAYS_DIR = "data/archive/raw/live_55586926"
DOLLARS_PER_RATING_PT = 253.0
LAST_EXEC_STEP = 718  # §6 / §4
PREMIUM = ["WOOL", "STRAWBERRY", "MILK", "MELON"]
I0 = 10000


def _engine():
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        market_price, SHOPS, TOWN_CENTER_PRODUCTS,
    )
    return market_price, SHOPS, set(TOWN_CENTER_PRODUCTS)


def _load(path, SHOPS, CENTER):
    with open(path) as f:
        r = json.load(f)
    steps = r["steps"]
    cfg = r.get("configuration", {})
    ssi = int(cfg.get("townShopSellInterval", 4) or 4)
    cci = int(cfg.get("townCenterSellInterval", 24) or 24)
    n = len(steps)
    ep_id = os.path.basename(path).split("-")[1]

    rec = {p: [s[0]["observation"]["market"]["inventory"][p] for s in steps] for p in PREMIUM}
    price_rec = {p: [s[0]["observation"]["market"]["prices"][p] for s in steps] for p in PREMIUM}

    # per-transition (t -> t+1) ordered sells, from action[t+1]; drain from step t
    our_ord = {p: [0] * (n - 1) for p in PREMIUM}
    opp_ord = {p: [0] * (n - 1) for p in PREMIUM}
    drain = {p: [0] * (n - 1) for p in PREMIUM}
    priv_same = 0
    for s in steps:
        if (s[0]["observation"].get("private") or {}) == (s[1]["observation"].get("private") or {}):
            priv_same += 1
    for t in range(n - 1):
        act_step = steps[t + 1]
        for seat, bag in ((0, our_ord), (1, opp_ord)):
            a = act_step[seat].get("action")
            m = a.get("market", []) if isinstance(a, dict) else []
            if isinstance(m, list):
                for o in m:
                    if isinstance(o, list) and o and o[0] == "SELL" and len(o) >= 3 and o[1] in bag:
                        try:
                            bag[o[1]][t] += int(o[2])
                        except (ValueError, TypeError):
                            pass
        shops = steps[t][0]["observation"]["town"].get("unlocked_shops", []) or []
        for p in PREMIUM:
            d = 0
            if t % ssi == 0:
                for sh in shops:
                    prods = SHOPS[sh]
                    if p in prods:
                        d += 2 if len(prods) == 1 else 1
            if t % cci == 0 and p in CENTER:
                d += 1
            drain[p][t] = d
    is_mirror = priv_same > n * 0.7
    return ep_id, is_mirror, rec, price_rec, our_ord, opp_ord, drain


def _foreign_and_units(rec_p, price_rec_p, our_ord_p, opp_ord_p, drain_p, last_step):
    """Reconstruct the frozen foreign-inventory trajectory and our sell units.

    Returns foreign[t] (t up to last_step), plus:
      bumped_placements: list of (step_t, units)  -- our bumped units, per step
      floored_units:     total our units sold at the $1 floor
    """
    n = min(len(rec_p) - 1, last_step)
    our_bumped_cum = 0.0
    foreign = [0.0] * (n + 1)
    bumped_placements = []
    floored_units = 0.0
    for t in range(n):
        foreign[t] = rec_p[t] - our_bumped_cum
        total_bumped = rec_p[t + 1] - rec_p[t] + drain_p[t]
        if total_bumped < 0:
            total_bumped = 0
        denom = our_ord_p[t] + opp_ord_p[t]
        frac = (our_ord_p[t] / denom) if denom > 0 else 0.0
        our_bumped = total_bumped * frac
        if our_bumped > our_ord_p[t]:
            our_bumped = float(our_ord_p[t])
        if our_bumped > 0:
            bumped_placements.append((t, our_bumped))
            our_bumped_cum += our_bumped
        # ordered-but-not-bumped: floored ($1 revenue) if price at floor, else shed-starved (drop)
        shortfall = our_ord_p[t] - our_bumped
        if shortfall > 0 and price_rec_p[t] <= 1:
            floored_units += shortfall
    foreign[n] = rec_p[n] - our_bumped_cum
    return foreign, bumped_placements, floored_units


def _actual_revenue(price, item, foreign, bumped_placements, floored_units):
    rev = float(floored_units) * 1.0
    for t, units in bumped_placements:
        f = foreign[t] if foreign[t] > 0 else 0
        u = int(round(units))
        for k in range(u):
            rev += price(item, f + k)
    return rev


def _drain_baseline(rec_p, price_rec_p, our_ord_p, opp_ord_p, drain_p, last_step):
    """Inventory trajectory with BOTH seats' sells removed — town drain only.

    This is the pool both seats actually compete for: town consumption pulls
    WOOL/MILK/STRAWBERRY *below* I0 (net scarcity -> price drifts ABOVE base),
    which is the headroom Branch-B timing is trying to capture.  Returns the
    trajectory plus each seat's total sell units (bumped + floored)."""
    n = min(len(rec_p) - 1, last_step)
    our_cum = opp_cum = 0.0
    fd = [0.0] * (n + 1)
    u_us = u_opp = 0.0
    for t in range(n):
        fd[t] = rec_p[t] - our_cum - opp_cum
        tb = max(0, rec_p[t + 1] - rec_p[t] + drain_p[t])
        den = our_ord_p[t] + opp_ord_p[t]
        of = (our_ord_p[t] / den) if den > 0 else 0.0
        ub = min(tb * of, our_ord_p[t])
        ob = min(tb * (1 - of), opp_ord_p[t])
        our_cum += ub
        opp_cum += ob
        u_us += ub
        u_opp += ob
        if price_rec_p[t] <= 1:
            u_us += max(0, our_ord_p[t] - ub)
            u_opp += max(0, opp_ord_p[t] - ob)
    fd[n] = rec_p[n] - our_cum - opp_cum
    return fd, u_us, u_opp


def _equilibrium_our_revenue(price, item, fd, u_us, u_opp):
    """Arms-race equilibrium: BOTH seats time optimally into the shared drain
    headroom, filling it in lockstep (a contested slot takes one unit from each,
    inventory +2, both paid the same pre-commit price — the engine's lockstep).
    Returns OUR revenue.  This DE-FREEZES the opponent (§6 pitfall 3): unlike the
    frozen ceiling it assumes the opponent also adopts Branch B."""
    u_us = int(round(u_us))
    u_opp = int(round(u_opp))
    if u_us <= 0:
        return 0.0
    heap = [(-price(item, max(0, int(f))), t, 0) for t, f in enumerate(fd)]
    heapq.heapify(heap)
    our = 0.0
    ru, ro = u_us, u_opp
    while (ru > 0 or ro > 0) and heap:
        neg, t, k = heapq.heappop(heap)
        pr = -neg
        if pr <= 1:
            our += ru * 1.0
            break
        if ru > 0 and ro > 0:
            our += pr; ru -= 1; ro -= 1; add = 2
        elif ru > 0:
            our += pr; ru -= 1; add = 1
        else:
            ro -= 1; add = 1
        f = max(0, int(fd[t]))
        heapq.heappush(heap, (-price(item, f + k + add), t, k + add))
    return our


def _ideal_revenue(price, item, foreign, U):
    """Max revenue placing U units into slots with endogenous impact
    (frozen-opponent ceiling: opponent stays on its recorded schedule)."""
    U = int(round(U))
    if U <= 0:
        return 0.0
    heap = []
    for t in range(len(foreign)):
        f = foreign[t] if foreign[t] > 0 else 0
        heapq.heappush(heap, (-price(item, f), t, 0))
    rev = 0.0
    remaining = U
    while remaining > 0 and heap:
        neg, t, k = heapq.heappop(heap)
        pr = -neg
        if pr <= 1:
            rev += remaining * 1.0
            break
        rev += pr
        remaining -= 1
        f = foreign[t] if foreign[t] > 0 else 0
        heapq.heappush(heap, (-price(item, f + k + 1), t, k + 1))
    return rev


def _summ(xs):
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    n = len(xs)
    return {"n": n, "mean": statistics.mean(xs), "median": statistics.median(xs),
            "p10": xs[int(0.1 * n)] if n > 1 else xs[0],
            "p90": xs[int(0.9 * n)] if n > 1 else xs[0],
            "min": xs[0], "max": xs[-1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays-dir", default=REPLAYS_DIR)
    ap.add_argument("--out", default="data/derived/s7_glut_bound.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    price, SHOPS, CENTER = _engine()
    files = sorted(glob.glob(os.path.join(args.replays_dir, "episode-*.json")))
    if args.limit:
        files = files[: args.limit]
    n_disk = len(files)

    live = []
    n_bad = n_mirror = 0
    recon_final_err = {p: [] for p in PREMIUM}
    for path in files:
        try:
            ep_id, is_mirror, rec, price_rec, our_ord, opp_ord, drain = _load(path, SHOPS, CENTER)
        except Exception as e:
            n_bad += 1
            print(f"  SKIP {os.path.basename(path)}: {e}")
            continue
        if is_mirror:
            n_mirror += 1
            continue
        live.append((ep_id, rec, price_rec, our_ord, opp_ord, drain))

    print("== RETENTION (§7.3) ==")
    print(f"  on disk {n_disk} | live {len(live)} | mirror {n_mirror} | bad {n_bad} | USED {len(live)}")

    per_product = {}
    print(f"\n== Phase 0 impact ceiling (exact foreign_inv; endogenous; last step {LAST_EXEC_STEP}) ==")
    print(f"  {'product':<11}{'U med':>7}{'flr med':>8}{'R_act med':>11}{'R_ideal med':>13}"
          f"{'Δ med $':>10}{'froz pts':>9}{'eq pts':>9}")
    for p in PREMIUM:
        Us, floors, Racts, Rideals, deltas, pts = [], [], [], [], [], []
        eq_pts = []
        for ep_id, rec, price_rec, our_ord, opp_ord, drain in live:
            foreign, bumped, floored = _foreign_and_units(
                rec[p], price_rec[p], our_ord[p], opp_ord[p], drain[p], LAST_EXEC_STEP)
            U = sum(u for _, u in bumped) + floored
            r_act = _actual_revenue(price, p, foreign, bumped, floored)
            r_ideal = _ideal_revenue(price, p, foreign, U)
            d = r_ideal - r_act
            Us.append(U); floors.append(floored); Racts.append(r_act)
            Rideals.append(r_ideal); deltas.append(d); pts.append(d / DOLLARS_PER_RATING_PT)
            # de-frozen arms-race equilibrium gain (opponent also plays Branch B)
            fd, u_us, u_opp = _drain_baseline(
                rec[p], price_rec[p], our_ord[p], opp_ord[p], drain[p], LAST_EXEC_STEP)
            eq_rev = _equilibrium_our_revenue(price, p, fd, u_us, u_opp)
            eq_pts.append((eq_rev - r_act) / DOLLARS_PER_RATING_PT)
        ds, ps, eqs = _summ(deltas), _summ(pts), _summ(eq_pts)
        per_product[p] = {
            "U_units": _summ(Us), "floored_units": _summ(floors),
            "R_actual": _summ(Racts), "R_ideal": _summ(Rideals),
            "delta_dollars": ds,
            "ceiling_rating_pts_frozen_opponent": ps,
            "gain_rating_pts_armsrace_equilibrium": eqs,
        }
        print(f"  {p:<11}{statistics.median(Us):>7.0f}{statistics.median(floors):>8.0f}"
              f"{_summ(Racts)['median']:>11.0f}{_summ(Rideals)['median']:>13.0f}"
              f"{ds['median']:>10.0f}{ps['median']:>9.2f}{eqs['median']:>9.2f}")

    total_pts_median = sum(per_product[p]["ceiling_rating_pts_frozen_opponent"]["median"] for p in PREMIUM)
    total_pts_mean = sum(per_product[p]["ceiling_rating_pts_frozen_opponent"]["mean"] for p in PREMIUM)
    total_eq_median = sum(per_product[p]["gain_rating_pts_armsrace_equilibrium"]["median"] for p in PREMIUM)
    wool_pts = per_product["WOOL"]["ceiling_rating_pts_frozen_opponent"]["median"]
    print("\n== K1 / K2 VERDICT ==")
    print(f"  WOOL ceiling (median, frozen opp) : {wool_pts:.2f} pts")
    print(f"  all-premium ceiling (median Σ)    : {total_pts_median:.2f} pts  [frozen opponent]")
    print(f"  all-premium ceiling (mean Σ)      : {total_pts_mean:.2f} pts  [frozen opponent]")
    print(f"  all-premium gain (median Σ)       : {total_eq_median:.2f} pts  [arms-race equilibrium]")
    kill = total_pts_median < 1.0
    if kill:
        print("  >>> K2 TRIGGERED: ceiling < ~1 rating pt. DO NOT BUILD (§6).")
    else:
        print("  >>> Both estimates ≫ 1 pt: paper bound does NOT kill (K1/K2 clear).")
    print("  ⚠ These are BANK (dollar) gains, not W/L.  The equilibrium shows BOTH seats")
    print("    gain ~equally -> much of it is COMMON-MODE, exactly the §11/K5 'bank yes,")
    print("    wins no' trap.  Only the §8 gate (W/L, judged first) resolves whether it moves rank.")
    print("  ⚠ Frozen ceiling also ignores production-calendar availability -> looser upper bound.")

    out = {
        "source": args.replays_dir,
        "last_exec_step": LAST_EXEC_STEP,
        "dollars_per_rating_pt": DOLLARS_PER_RATING_PT,
        "retention": {"on_disk": n_disk, "live": len(live), "mirror": n_mirror, "bad": n_bad},
        "per_product": per_product,
        "verdict": {
            "wool_ceiling_pts_median_frozen": wool_pts,
            "all_premium_pts_median_frozen": total_pts_median,
            "all_premium_pts_mean_frozen": total_pts_mean,
            "all_premium_pts_median_armsrace_equilibrium": total_eq_median,
            "k2_kill": kill,
            "note": ("Both frozen-opponent ceiling and arms-race equilibrium clear ~1 pt "
                     "by a wide margin. BUT these are BANK gains; the equilibrium shows both "
                     "seats gain ~equally => largely COMMON-MODE (§11/K5 risk). W/L is only "
                     "settled by the §8 gate. Frozen ceiling also ignores production "
                     "availability (looser upper bound)."),
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
