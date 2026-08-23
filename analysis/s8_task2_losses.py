#!/usr/bin/env python3
"""S8 Task 2 — loss analysis AGAINST THE WINNER (docs/plans/... §3).

§6 row 27 already closed the "what did WE do wrong" side (decay counters r=-0,029; desync
r=-0,085; shop draw R²=0,366; 11/178 flippable). This asks the never-asked reverse: *what did
the winner do that we didn't?* Both seats share seed/town/shop-draw/calendar (§3.2), so any
difference is a DECISION, not town luck — the intra-town dispute §5.2 isolated.

🔴 The trap (§3.2): do NOT rank losses by bank difference — the shop draw is common-mode and
explains R²=0,366 of the bank, so that ranks luck. We rank by margin WITHIN the town:
    margin_norm = (bank_opp - bank_us) / max(bank_opp, bank_us).

Two categories that must be separated (§3.4): marginal (<~10% — where the points live) and
blowouts (>50% — structural, look for a COMMON pattern).

Deliverable (§3.5): NOT a list of losses — a RANKING OF CAUSES, each priced
$/episode ÷ $253 = points (marginal-increment heuristic; does NOT hold for a change that alters
*whom* we beat). A cause below ~1% of the gap (≈10 pts) gets no arm.

Output: data/derived/s8_task2_losses.json (gitignored).
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis import s8_replay_io as io  # noqa: E402
from analysis.s6_step1_phase0 import _realised_premium  # noqa: E402
from harness.metrics import _transition_events  # noqa: E402

OUT = ROOT / "data" / "derived" / "s8_task2_losses.json"
GAP = 253.0            # $/episode ÷ this = points (§3)
POINT_FLOOR_DOLLARS = 0.01 * 10 * GAP  # ~1% of gap ≈ 10 pts → $ threshold for an arm

PREMIUM = ("STRAWBERRY", "WOOL", "MILK")


def _flatten_tiles(tiles):
    """farms[seat]['tiles'] is a nested board (list of rows of tiles); yield the tile dicts,
    skipping 'LOCKED' strings and any non-dict."""
    stack = [tiles]
    while stack:
        x = stack.pop()
        if isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, dict):
            yield x


def _revenue_by_product(steps, cfg):
    """Full realised sale revenue + units per product for BOTH seats, from recorded transitions
    (same _transition_events path as _realised_premium, but not filtered to PREMIUM). Returns
    [dict_seat0, dict_seat1] with product -> {'revenue','units'}."""
    rev = [defaultdict(float), defaultdict(float)]
    units = [defaultdict(int), defaultdict(int)]
    for i in range(1, len(steps)):
        _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
        for seat in (0, 1):
            for s in sales[seat]:
                rev[seat][s["item"]] += s["price"]
                units[seat][s["item"]] += 1
    out = []
    for seat in (0, 1):
        out.append({p: {"revenue": rev[seat][p], "units": units[seat][p]} for p in rev[seat]})
    return out


def _per_day_farms(steps):
    """day -> [farm0, farm1] using the LAST populated observation seen in that day (end of day).
    Both farms are public in any populated obs, so we read from whichever seat's cell is live."""
    by_day = {}
    for t in range(1, len(steps)):
        obs = None
        for seat in (0, 1):
            o = steps[t][seat].get("observation") or {}
            if o.get("farms"):
                obs = o
                break
        if obs is None:
            continue
        by_day[obs["day"]] = obs["farms"]
    return by_day


def _production_profile(steps, seat):
    """Crop tile-days, animal peak, hands@d10/d20, quadrant-unlock day, final shops — for one seat.
    Sampled once per day (end of day)."""
    by_day = _per_day_farms(steps)
    crop_tile_days = defaultdict(int)
    animal_peak = 0
    hands_d10 = hands_d20 = None
    quad_unlock_day = {}
    final_shops = None
    for day in sorted(by_day):
        farm = by_day[day][seat]
        animals = 0
        for tile in _flatten_tiles(farm.get("tiles", [])):
            k = tile.get("kind")
            if k == "PLANT" and tile.get("crop"):
                crop_tile_days[tile["crop"]] += 1
            elif k == "PASTURE" and tile.get("animal"):
                crop_tile_days["ANIMAL:" + tile["animal"]] += 1
                animals += 1
        animal_peak = max(animal_peak, animals)
        for q in farm.get("unlocked_quadrants", []):
            quad_unlock_day.setdefault(q, day)
        if day == 10:
            hands_d10 = len(farm.get("hands", []))
        if day == 20:
            hands_d20 = len(farm.get("hands", []))
    # last day's shops (town is shared, so seat-independent; read once)
    if by_day:
        last = by_day[max(by_day)]
        # town lives on obs, not farm; re-read the last populated obs's town
        for t in range(len(steps) - 1, 0, -1):
            for s in (0, 1):
                o = steps[t][s].get("observation") or {}
                if o.get("town"):
                    final_shops = o["town"].get("unlocked_shops")
                    break
            if final_shops is not None:
                break
    return {
        "crop_tile_days": dict(crop_tile_days),
        "animal_peak": animal_peak,
        "hands_d10": hands_d10,
        "hands_d20": hands_d20,
        "quad_unlock_day": quad_unlock_day,
        "final_shops": final_shops,
    }


def _divergence_day(steps, our_seat):
    """First day the end-of-day MONEY gap (opp-us) reaches 25% of its final value.
    ⚠️ money is NOT final bank — unsold shed is not liquidated (§3.3); if the money curve never
    shows the loss (shed-hidden), returns None."""
    by_day = _per_day_farms(steps)
    days = sorted(by_day)
    if not days:
        return None, None
    gap = {d: by_day[d][1 - our_seat][ "money"] - by_day[d][our_seat]["money"] for d in days}
    final_gap = gap[days[-1]]
    if final_gap <= 0:
        return None, final_gap
    thresh = 0.25 * final_gap
    for d in days:
        if gap[d] >= thresh:
            return d, final_gap
    return days[-1], final_gap


def analyse_submission(submission: str) -> dict:
    losses = []
    n_ladder = 0
    for eid, m in io.ladder_episodes(submission):
        n_ladder += 1
        seat = io.our_seat(m["teams"])
        us, opp = m["rewards"][seat], m["rewards"][1 - seat]
        if us >= opp:
            continue  # only losses (ties handled by >=, recorded nowhere as loss)
        steps, cfg = m["steps"], m["configuration"]
        margin_abs = opp - us
        margin_norm = margin_abs / max(opp, us) if max(opp, us) else 0.0
        rev = _revenue_by_product(steps, cfg)
        prem0, prem1, _ss0, _ss1 = _realised_premium(steps, cfg)
        div_day, final_money_gap = _divergence_day(steps, seat)
        # winner-advantage by product ($): revenue_opp - revenue_us
        prod_adv = {}
        for p in set(rev[seat]) | set(rev[1 - seat]):
            adv = rev[1 - seat].get(p, {}).get("revenue", 0.0) - rev[seat].get(p, {}).get("revenue", 0.0)
            prod_adv[p] = adv
        losses.append({
            "episode_id": eid, "seat": seat,
            "bank_us": us, "bank_opp": opp,
            "margin_abs": margin_abs, "margin_norm": margin_norm,
            "category": ("marginal" if margin_norm < 0.10 else
                         ("blowout" if margin_norm > 0.50 else "mid")),
            "divergence_day": div_day, "final_money_gap": final_money_gap,
            "product_advantage_dollars": prod_adv,
            "realised_premium_us": prem0 if seat == 0 else prem1,
            "realised_premium_opp": prem1 if seat == 0 else prem0,
            "profile_us": _production_profile(steps, seat),
            "profile_opp": _production_profile(steps, 1 - seat),
        })

    return _rank_causes(submission, n_ladder, losses)


def _rank_causes(submission, n_ladder, losses):
    n = len(losses)
    cats = {"marginal": [], "mid": [], "blowout": []}
    for L in losses:
        cats[L["category"]].append(L)

    # ranked priced cause = product on which the winner NET out-earned us. SIGNED sum: in one loss
    # we beat them on some products and lose on others, so a one-sided (adv>0 only) sum double-counts
    # and the "points" would exceed the real margin. Signed net sums reconcile against the margin.
    prod_net = defaultdict(float)   # sum of (rev_opp - rev_us) with sign
    prod_pos = defaultdict(int)     # losses where the winner was ahead on this product
    for L in losses:
        for p, adv in L["product_advantage_dollars"].items():
            prod_net[p] += adv
            if adv > 0:
                prod_pos[p] += 1
    causes = []
    for p in sorted(prod_net, key=lambda x: -prod_net[x]):
        per_ep = prod_net[p] / n if n else 0.0
        causes.append({
            "cause": f"winner net out-earned us on {p}",
            "net_advantage_dollars": round(prod_net[p], 1),
            "losses_winner_ahead": prod_pos[p],
            "mean_net_dollars_per_loss": round(prod_net[p] / n, 1) if n else None,
            "priced_points": round(per_ep / GAP, 2),
            "gets_arm": per_ep >= POINT_FLOOR_DOLLARS,
        })
    # reconciliation: total sale-revenue margin vs the actual bank margin (rest = non-sale bank:
    # starting money, unliquidated shed, care/hire costs — not decomposable from sales alone).
    total_net_sales = sum(prod_net.values())
    total_bank_margin = sum(L["margin_abs"] for L in losses)

    def med(xs):
        return statistics.median(xs) if xs else None

    def cat_summary(name):
        ls = cats[name]
        div_days = [L["divergence_day"] for L in ls if L["divergence_day"] is not None]
        # dominant winning crop in this category (winner's tile-days share)
        opp_crops = defaultdict(int)
        for L in ls:
            for c, td in L["profile_opp"]["crop_tile_days"].items():
                opp_crops[c] += td
        return {
            "n": len(ls),
            "median_margin_norm": med([L["margin_norm"] for L in ls]),
            "median_margin_abs": med([L["margin_abs"] for L in ls]),
            "median_divergence_day": med(div_days),
            "n_shed_hidden_curve": sum(1 for L in ls if L["divergence_day"] is None),
            "winner_top_crops_tiledays": dict(sorted(opp_crops.items(), key=lambda x: -x[1])[:5]),
        }

    return {
        "submission": submission,
        "n_ladder": n_ladder,
        "n_losses": n,
        "categories": {k: cat_summary(k) for k in cats},
        "ranked_causes": causes,
        "reconciliation": {
            "sum_net_sale_revenue_advantage": round(total_net_sales, 1),
            "sum_bank_margin": round(total_bank_margin, 1),
            "sales_share_of_margin": round(total_net_sales / total_bank_margin, 3) if total_bank_margin else None,
            "note": ("Sum of signed per-product sale advantages vs the summed bank margin. The "
                     "remainder is non-sale bank (unliquidated shed valuation, starting money, "
                     "hire/care spend) and is NOT attributable to any single sale."),
        },
        "pricing_note": (
            "priced_points = mean $/loss ÷ $253 (marginal-increment heuristic, §3). It does NOT "
            "hold for a change that alters WHICH opponents we beat. An arm requires ≥ ~1% of the "
            "gap (≈10 pts). Row 27 found 11/178 flippable (+6,2 pts); compare marginal-loss count."),
        "trap_note": (
            "Ranked by margin_norm within the shared town, NOT by bank difference — the shop draw "
            "is common-mode (R²=0,366, §5.2) and ranking by $ would rank town luck."),
        "money_caveat": (
            "divergence_day is from farms[seat]['money'], which excludes unliquidated shed; "
            "n_shed_hidden_curve losses never show the deficit in the money curve."),
        "losses": losses,
    }


def main() -> int:
    result = {}
    for sub in io.SUBMISSIONS:
        r = analyse_submission(sub)
        result[sub] = r
        print(f"\n=== {sub}: {r['n_losses']} losses / {r['n_ladder']} ladder ===")
        for k, c in r["categories"].items():
            print(f"  {k:8s} n={c['n']:3d}  med|margin|={c['median_margin_norm']}  "
                  f"divDay={c['median_divergence_day']}  shedHidden={c['n_shed_hidden_curve']}")
            print(f"           winner top crops (tile-days): {c['winner_top_crops_tiledays']}")
        rc = r["reconciliation"]
        print(f"  reconciliation: net sale adv ${rc['sum_net_sale_revenue_advantage']:,.0f} / "
              f"bank margin ${rc['sum_bank_margin']:,.0f} = {rc['sales_share_of_margin']}")
        print("  ranked causes (winner NET advantage $):")
        for c in r["ranked_causes"][:8]:
            arm = "ARM" if c["gets_arm"] else "—"
            print(f"    {c['cause']:42s} net ${c['net_advantage_dollars']:>11,.0f}  "
                  f"${c['mean_net_dollars_per_loss']:>8,.0f}/loss  {c['priced_points']:>7} pts  [{arm}]")
    OUT.write_text(json.dumps(result, indent=1))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
