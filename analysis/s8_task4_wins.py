#!/usr/bin/env python3
"""S8 Task 4 — the WIN analysis, and the win-vs-loss discriminant.

Task 2 asked *what did the winner do that we didn't* on our 97 losses. This asks the
symmetric question the plan needs before any heuristic touches `agent/`:

    **When we beat a rated opponent (>=1500), what exactly are we doing better —
    and is it the same axis we lose on?**

Why it must exist before the heuristic: Task 2's directional finding ("we lose on bulk
volume, we win on STRAWBERRY") is a recipe for destroying the thing that already works.
A heuristic that buys volume with premium timing is only an improvement if the win side
does not depend on that timing. This pass measures the win side on the *same* features,
with the *same* code path, so the two are comparable.

Method (three properties that make it town-controlled):
  * Both seats share seed / town / shop draw / calendar, so every quantity is reported as a
    PAIRED DIFFERENTIAL `us - opp` inside one episode (§5.2: 99-100% of realised $/u variance
    is between-town; a differential cancels it).
  * Bank is exactly `startingMoney + sale_revenue - expenses` (engine: `reward = farm.money`,
    kaggriculture.py:963), so `margin = d_revenue - d_expenses` closes with no residual. That
    identity is asserted per episode — it is what lets the pass say whether a win was EARNED
    (revenue) or SAVED (spend).
  * Separation is reported as AUC = P(differential in a win > differential in a loss), which is
    rank-based and immune to the town's dollar scale.

Ratings are TEAM ratings from a leaderboard snapshot (§2 rule 5) — diagnostic, not a decision,
and the band cut is re-run under BOTH snapshots as a sensitivity check.

Output: data/derived/s8_task4_wins.json (gitignored).
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
from analysis.s8_task1_matched import SNAP_A, SNAP_B, load_snapshot  # noqa: E402
from analysis.s8_task2_losses import _flatten_tiles, _per_day_farms  # noqa: E402
from harness.metrics import _transition_events  # noqa: E402

OUT = ROOT / "data" / "derived" / "s8_task4_wins.json"

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
CROPS_SEED = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_PRICES = [1000, 2000, 4000]
TURNS_PER_DAY = 24
MILESTONE_DAYS = (5, 10, 15, 20, 24, 29)

# The band cut the brief asks for. 1500 is the "a rated opponent, not a placement bye" line.
BANDS = ((0, 1500, "<1500"), (1500, 1800, "1500-1800"), (1800, 2100, "1800-2100"), (2100, 1e9, "2100+"))


def band_of(score: float | None) -> str:
    if score is None:
        return "unknown"
    for lo, hi, name in BANDS:
        if lo <= score < hi:
            return name
    return "unknown"


def _fib(n: int) -> int:
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _hire_cost_for_n(n: int) -> int:
    """Cost of hiring n hands in one day: sum of _hire_cost(0..n-1) (engine :698)."""
    return sum(_fib(i) for i in range(n))


def _sales_pass(steps, cfg):
    """One transition sweep -> per seat: product -> {revenue, units, sell_days[list]}.

    Same `_transition_events` path as `_realised_premium` (§1.2: one market meter in the repo),
    but kept over all nine products and carrying the DAY of each unit so sell timing is
    measurable, which the premium meter does not retain. `daily` additionally keeps
    (units, revenue) per (product, day) per seat — the metering profile: WHO sold into WHOSE
    depressed inventory, on which day. The market inventory is SHARED and drains only through
    town absorption, so a same-day batch prices every later unit, ours and theirs."""
    rev = [defaultdict(float), defaultdict(float)]
    units = [defaultdict(int), defaultdict(int)]
    days = [defaultdict(list), defaultdict(list)]
    daily = [defaultdict(lambda: defaultdict(lambda: [0, 0.0])),
             defaultdict(lambda: defaultdict(lambda: [0, 0.0]))]
    for i in range(1, len(steps)):
        _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
        day = int(steps[i - 1][0]["observation"].get("day", 0))
        for seat in (0, 1):
            for s in sales[seat]:
                rev[seat][s["item"]] += s["price"]
                units[seat][s["item"]] += 1
                days[seat][s["item"]].append(day)
                cell = daily[seat][s["item"]][day]
                cell[0] += 1
                cell[1] += s["price"]
    daily = [{p: {d: v for d, v in dd.items()} for p, dd in seat_d.items()} for seat_d in daily]
    return rev, units, days, daily


def _order_intents(steps, seat):
    """Counts of ISSUED market orders (not necessarily committed) by op and item, plus units.

    Intents are the POLICY signature — what the route asked for. Committed spend is recovered
    exactly as a residual below; the two are labelled apart and never mixed."""
    n_orders = defaultdict(int)
    n_units = defaultdict(int)
    for t in range(1, len(steps)):
        act = steps[t][seat].get("action") or {}
        for order in (act.get("market") or [])[:10]:
            if not isinstance(order, list) or not order:
                continue
            op = order[0]
            item = order[1] if len(order) > 1 and isinstance(order[1], str) else ""
            qty = order[2] if len(order) > 2 and isinstance(order[2], (int, float)) else 1
            key = f"{op}:{item}" if item else op
            n_orders[key] += 1
            n_units[key] += int(qty)
    return dict(n_orders), dict(n_units)


def _daily_profile(by_day, seat):
    """Per-day farm-state profile for one seat: money curve, tile-days, herd, hands, land."""
    crop_tile_days = defaultdict(int)
    animals_by_day = {}
    hands_by_day = {}
    money_by_day = {}
    occupied_by_day = {}
    quad_unlock_day = {}
    plants_new = defaultdict(int)      # day-over-day increase in tiles of a crop -> seed spend proxy
    prev_crop_counts = defaultdict(int)
    for day in sorted(by_day):
        farm = by_day[day][seat]
        counts = defaultdict(int)
        animals = defaultdict(int)
        occupied = 0
        for tile in _flatten_tiles(farm.get("tiles", [])):
            kind = tile.get("kind")
            if kind == "PLANT" and tile.get("crop"):
                counts[tile["crop"]] += 1
                occupied += 1
            elif tile.get("animal"):
                animals[tile["animal"]] += 1
                occupied += 1
        for crop, c in counts.items():
            crop_tile_days[crop] += c
            plants_new[crop] += max(0, c - prev_crop_counts[crop])
        prev_crop_counts = counts
        animals_by_day[day] = dict(animals)
        hands_by_day[day] = len(farm.get("hands", []))
        money_by_day[day] = farm.get("money")
        occupied_by_day[day] = occupied
        for q in farm.get("unlocked_quadrants", []):
            quad_unlock_day.setdefault(q, day)
    return {
        "crop_tile_days": dict(crop_tile_days),
        "animals_by_day": animals_by_day,
        "hands_by_day": hands_by_day,
        "money_by_day": money_by_day,
        "occupied_by_day": occupied_by_day,
        "quad_unlock_day": quad_unlock_day,
        "plants_new": dict(plants_new),
    }


def _spend_breakdown(prof, expenses_total):
    """Split total spend into what farm state can prove, plus a labelled residual.

    Exact from state: hires (fib cost of that day's hand count — hands are wiped nightly, so the
    end-of-day count IS that day's hires), land (LAND_PRICES by unlock order), animals (day-over-day
    herd increases x cost). Estimated: seeds (day-over-day crop-tile increases x seed price —
    undercounts intra-day plant/harvest churn). The remainder is BUY_PRODUCT (animal feed WHEAT +
    FERTILIZER) plus that churn, and is reported as `residual_buy_product_and_churn`, never as a
    clean category."""
    hires = sum(_hire_cost_for_n(n) for n in prof["hands_by_day"].values())
    n_extra_quads = max(0, len(prof["quad_unlock_day"]) - 1)
    land = sum(LAND_PRICES[:n_extra_quads])
    animals = 0.0
    prev = defaultdict(int)
    for day in sorted(prof["animals_by_day"]):
        cur = prof["animals_by_day"][day]
        for a, c in cur.items():
            animals += max(0, c - prev[a]) * ANIMAL_COST.get(a, 0)
        prev = defaultdict(int, cur)
    seeds = sum(n * CROPS_SEED.get(c, 0) for c, n in prof["plants_new"].items())
    known = hires + land + animals + seeds
    return {
        "hires": hires, "land": land, "animals": animals, "seeds_est": seeds,
        "residual_buy_product_and_churn": expenses_total - known,
        "total": expenses_total,
    }


def _seat_features(steps, cfg, seat, rev, units, days, by_day):
    prof = _daily_profile(by_day, seat)
    money_curve = {f"money_d{d}": prof["money_by_day"].get(d) for d in MILESTONE_DAYS}
    start_money = float(cfg.get("startingMoney", 3000))
    end_money = prof["money_by_day"][max(prof["money_by_day"])] if prof["money_by_day"] else None
    total_rev = sum(rev[seat].values())
    expenses_total = start_money + total_rev - (end_money or 0.0)
    n_orders, n_units = _order_intents(steps, seat)

    per_product = {}
    for p in PRODUCTS:
        u = units[seat].get(p, 0)
        if not u:
            continue
        d = days[seat][p]
        per_product[p] = {
            "revenue": rev[seat][p],
            "units": u,
            "price": rev[seat][p] / u,
            "first_sell_day": min(d),
            "median_sell_day": statistics.median(d),
            "units_before_d20": sum(1 for x in d if x < 20),
        }
    return {
        "total_revenue": total_rev,
        "expenses_total": expenses_total,
        "end_money": end_money,
        "spend": _spend_breakdown(prof, expenses_total),
        "products": per_product,
        "crop_tile_days": prof["crop_tile_days"],
        "animal_peak": max((sum(v.values()) for v in prof["animals_by_day"].values()), default=0),
        "animals_end": prof["animals_by_day"].get(max(prof["animals_by_day"]), {}) if prof["animals_by_day"] else {},
        "hands_d10": prof["hands_by_day"].get(10),
        "hands_d20": prof["hands_by_day"].get(20),
        "occupied_d10": prof["occupied_by_day"].get(10),
        "occupied_d20": prof["occupied_by_day"].get(20),
        "n_quadrants": len(prof["quad_unlock_day"]),
        "order_counts": n_orders,
        "order_units": n_units,
        **money_curve,
    }


def scan_episode(submission, eid, m, snapshots):
    seat = io.our_seat(m["teams"])
    steps, cfg = m["steps"], m["configuration"]
    us, opp = m["rewards"][seat], m["rewards"][1 - seat]
    if not io.opponent_clean(steps, 1 - seat):
        return None  # a crashed opponent is not a real opponent (§4 Task 3)
    rev, units, days, daily = _sales_pass(steps, cfg)
    by_day = _per_day_farms(steps)
    f_us = _seat_features(steps, cfg, seat, rev, units, days, by_day)
    f_opp = _seat_features(steps, cfg, 1 - seat, rev, units, days, by_day)
    f_us["daily_sales"] = daily[seat]
    f_opp["daily_sales"] = daily[1 - seat]
    opp_team = m["teams"][1 - seat]
    return {
        "submission": submission, "episode_id": eid, "seat": seat, "opponent": opp_team,
        "result": "W" if us > opp else ("L" if us < opp else "D"),
        "bank_us": us, "bank_opp": opp,
        "margin_norm": (us - opp) / max(us, opp) if max(us, opp) else 0.0,
        "opp_score_snapA": snapshots["A"].get(opp_team),
        "opp_score_snapB": snapshots["B"].get(opp_team),
        "us": f_us, "opp": f_opp,
    }


# ---------------------------------------------------------------------------- differentials

def differentials(ep) -> dict:
    """Every scalar as a paired `us - opp` inside the shared town."""
    u, o = ep["us"], ep["opp"]
    d = {
        "d_revenue": u["total_revenue"] - o["total_revenue"],
        "d_expenses": u["expenses_total"] - o["expenses_total"],
        "d_spend_seeds": u["spend"]["seeds_est"] - o["spend"]["seeds_est"],
        "d_spend_animals": u["spend"]["animals"] - o["spend"]["animals"],
        "d_spend_residual": (u["spend"]["residual_buy_product_and_churn"]
                             - o["spend"]["residual_buy_product_and_churn"]),
        "d_animal_peak": u["animal_peak"] - o["animal_peak"],
        "d_occupied_d10": (u["occupied_d10"] or 0) - (o["occupied_d10"] or 0),
        "d_occupied_d20": (u["occupied_d20"] or 0) - (o["occupied_d20"] or 0),
        "d_hands_d20": (u["hands_d20"] or 0) - (o["hands_d20"] or 0),
    }
    for day in MILESTONE_DAYS:
        k = f"money_d{day}"
        if u.get(k) is not None and o.get(k) is not None:
            d[f"d_{k}"] = u[k] - o[k]
    for p in PRODUCTS:
        pu, po = u["products"].get(p), o["products"].get(p)
        d[f"d_rev_{p}"] = (pu or {}).get("revenue", 0.0) - (po or {}).get("revenue", 0.0)
        d[f"d_units_{p}"] = (pu or {}).get("units", 0) - (po or {}).get("units", 0)
        if pu and po:
            d[f"d_price_{p}"] = pu["price"] - po["price"]
            d[f"d_firstsell_{p}"] = pu["first_sell_day"] - po["first_sell_day"]
            d[f"d_medsell_{p}"] = pu["median_sell_day"] - po["median_sell_day"]
            d[f"d_unitsbefore20_{p}"] = pu["units_before_d20"] - po["units_before_d20"]
    for c in CROPS_SEED:
        d[f"d_tiledays_{c}"] = u["crop_tile_days"].get(c, 0) - o["crop_tile_days"].get(c, 0)
        # conversion: sold units per tile-day — is our production worth more per tile?
        tu, to = u["crop_tile_days"].get(c, 0), o["crop_tile_days"].get(c, 0)
        if tu and to:
            d[f"d_units_per_tileday_{c}"] = (u["products"].get(c, {}).get("units", 0) / tu
                                             - o["products"].get(c, {}).get("units", 0) / to)
    return d


METER_PRODUCTS = ("STRAWBERRY", "MELON", "MILK", "WOOL", "WHEAT")


def metering(ep, side, product):
    """Per-episode metering signature of one seat on one product.

    `top_day_share` — share of the seat's units dumped on its single heaviest day (batch
    concentration). `n_days` — how many distinct days it spread over. `lead_units` — units this
    seat sold BEFORE the other seat's first unit of the product (the race into an empty pool).
    `late_share` — share of units sold after the market has already taken >=60% of the episode's
    combined volume, i.e. into the depressed pool."""
    other = "opp" if side == "us" else "us"
    mine = ep[side]["daily_sales"].get(product, {})
    theirs = ep[other]["daily_sales"].get(product, {})
    tot = sum(v[0] for v in mine.values())
    if not tot:
        return None
    first_other = min((int(d) for d, v in theirs.items() if v[0]), default=None)
    lead = sum(v[0] for d, v in mine.items() if first_other is None or int(d) < first_other)
    combined = defaultdict(int)
    for src in (mine, theirs):
        for d, v in src.items():
            combined[int(d)] += v[0]
    combined_total = sum(combined.values())
    running = 0
    late_cut = None
    for d in sorted(combined):
        running += combined[d]
        if running >= 0.6 * combined_total:
            late_cut = d
            break
    late = sum(v[0] for d, v in mine.items() if late_cut is not None and int(d) > late_cut)
    return {
        "units": tot,
        "revenue": sum(v[1] for v in mine.values()),
        "price": sum(v[1] for v in mine.values()) / tot,
        "top_day_share": max(v[0] for v in mine.values()) / tot,
        "n_days": sum(1 for v in mine.values() if v[0]),
        "lead_units": lead,
        "late_share": late / tot,
    }


def metering_view(eps, label) -> dict:
    """Us-vs-opp metering contrast per product, split by outcome."""
    out = {"label": label, "n": len(eps), "products": {}}
    for p in METER_PRODUCTS:
        row = {}
        for res in ("W", "L"):
            sub = [e for e in eps if e["result"] == res]
            for side in ("us", "opp"):
                sigs = [metering(e, side, p) for e in sub]
                sigs = [s for s in sigs if s]
                if not sigs:
                    continue
                row[f"{res}_{side}"] = {
                    k: round(statistics.median([s[k] for s in sigs]), 3)
                    for k in ("units", "price", "top_day_share", "n_days", "lead_units", "late_share")
                } | {"n": len(sigs)}
        out["products"][p] = row
    return out


def robustness_view(eps, label) -> dict:
    """Whose revenue survives a poor town draw.

    Both seats sit in the SAME town, so a spread comparison is a like-for-like test of how much
    of each route's revenue the shop draw owns. `q10/q90` are over episodes; a route whose q90-q10
    band is narrow is town-robust."""
    def spread(vals):
        vals = sorted(v for v in vals if v is not None)
        if len(vals) < 5:
            return None
        q10 = vals[int(0.10 * (len(vals) - 1))]
        q90 = vals[int(0.90 * (len(vals) - 1))]
        return {"n": len(vals), "median": round(statistics.median(vals), 1),
                "q10": round(q10, 1), "q90": round(q90, 1), "q90_minus_q10": round(q90 - q10, 1),
                "stdev": round(statistics.pstdev(vals), 1)}
    out = {"label": label, "n": len(eps)}
    for side in ("us", "opp"):
        out[f"revenue_{side}"] = spread([e[side]["total_revenue"] for e in eps])
        out[f"expenses_{side}"] = spread([e[side]["expenses_total"] for e in eps])
        for p in METER_PRODUCTS:
            out[f"price_{p}_{side}"] = spread([e[side]["products"][p]["price"]
                                               for e in eps if p in e[side]["products"]])
    # split by town richness, proxied by the episode's COMBINED strawberry price (common-mode)
    rich = []
    for e in eps:
        ps = [e[s]["products"].get("STRAWBERRY", {}).get("price") for s in ("us", "opp")]
        ps = [x for x in ps if x]
        rich.append((statistics.fmean(ps) if ps else None, e))
    known = sorted([(r, e) for r, e in rich if r is not None], key=lambda x: x[0])
    if len(known) >= 20:
        half = len(known) // 2
        for name, part in (("poor_town_half", known[:half]), ("rich_town_half", known[half:])):
            sub = [e for _r, e in part]
            w = sum(1 for e in sub if e["result"] == "W")
            l = sum(1 for e in sub if e["result"] == "L")
            out[name] = {
                "n": len(sub), "W": w, "L": l,
                "win_rate": round(w / (w + l), 3) if (w + l) else None,
                "median_strawberry_price": round(statistics.median([r for r, _e in part]), 1),
                "median_revenue_us": round(statistics.median([e["us"]["total_revenue"] for e in sub]), 0),
                "median_revenue_opp": round(statistics.median([e["opp"]["total_revenue"] for e in sub]), 0),
            }
    return out


def auc(pos: list[float], neg: list[float]) -> float | None:
    """P(random pos > random neg) + 0.5 P(tie). Rank-based, dollar-scale free."""
    if not pos or not neg:
        return None
    gt = tie = 0
    for a in pos:
        for b in neg:
            if a > b:
                gt += 1
            elif a == b:
                tie += 1
    return (gt + 0.5 * tie) / (len(pos) * len(neg))


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "median": round(statistics.median(vals), 2),
        "mean": round(statistics.fmean(vals), 2),
        "share_positive": round(sum(1 for v in vals if v > 0) / len(vals), 3),
    }


def summarise(eps, label) -> dict:
    """Win/loss contrast over one episode subset: per-feature stats + AUC(win vs loss)."""
    wins = [e for e in eps if e["result"] == "W"]
    losses = [e for e in eps if e["result"] == "L"]
    keys = sorted({k for e in eps for k in e["diff"]})
    rows = []
    for k in keys:
        w = [e["diff"].get(k) for e in wins if e["diff"].get(k) is not None]
        l = [e["diff"].get(k) for e in losses if e["diff"].get(k) is not None]
        a = auc(w, l)
        rows.append({
            "feature": k, "wins": _stats(w), "losses": _stats(l),
            "auc_win_vs_loss": round(a, 3) if a is not None else None,
            "separation": round(abs(a - 0.5), 3) if a is not None else None,
        })
    rows.sort(key=lambda r: -(r["separation"] or 0))
    return {
        "label": label, "n": len(eps), "n_wins": len(wins), "n_losses": len(losses),
        "win_rate": round(len(wins) / (len(wins) + len(losses)), 3) if (wins or losses) else None,
        "features": rows,
    }


def main() -> int:
    snapshots = {"A": load_snapshot(SNAP_A), "B": load_snapshot(SNAP_B)}
    print(f"snapshots: A(08-18) {len(snapshots['A'])} teams · B(08-23) {len(snapshots['B'])} teams")

    episodes = []
    dropped = 0
    for sub in io.SUBMISSIONS:
        for i, (eid, m) in enumerate(io.ladder_episodes(sub), start=1):
            ep = scan_episode(sub, eid, m, snapshots)
            if ep is None:
                dropped += 1
                continue
            ep["index_in_submission"] = i
            ep["diff"] = differentials(ep)
            episodes.append(ep)
            if len(episodes) % 25 == 0:
                print(f"  ... {len(episodes)} episodes scanned", flush=True)

    # identity check: margin must equal d_revenue - d_expenses (both start at $3.000)
    worst = 0.0
    for e in episodes:
        resid = (e["bank_us"] - e["bank_opp"]) - (e["diff"]["d_revenue"] - e["diff"]["d_expenses"])
        worst = max(worst, abs(resid))

    # primary rating read = the SAME-AGE snapshot each submission was matched with in Task 1
    for e in episodes:
        e["opp_score"] = e["opp_score_snapA"] if e["submission"] == "55586926" else e["opp_score_snapB"]
        e["band"] = band_of(e["opp_score"])
        e["band_sensitivity"] = band_of(e["opp_score_snapB"] if e["submission"] == "55586926"
                                        else e["opp_score_snapA"])

    rated = [e for e in episodes if e["opp_score"] is not None and e["opp_score"] >= 1500]
    views = {
        "all": summarise(episodes, "all ladder episodes, both submissions"),
        "rated_1500plus": summarise(rated, "opponent team rating >= 1500 (primary snapshot)"),
        "rated_1500plus_sensitivity": summarise(
            [e for e in episodes if (e["opp_score_snapB"] if e["submission"] == "55586926"
                                     else e["opp_score_snapA"]) is not None
             and (e["opp_score_snapB"] if e["submission"] == "55586926"
                  else e["opp_score_snapA"]) >= 1500],
            "opponent rating >= 1500 under the OTHER snapshot (deflation sensitivity)"),
    }
    for _lo, _hi, name in BANDS:
        sub = [e for e in episodes if e["band"] == name]
        if sub:
            views[f"band_{name}"] = summarise(sub, f"band {name}")
    for sub in io.SUBMISSIONS:
        s = [e for e in episodes if e["submission"] == sub and e["opp_score"] is not None
             and e["opp_score"] >= 1500]
        if s:
            views[f"rated_1500plus_{sub}"] = summarise(s, f"{sub}, opponent >= 1500")

    # absolute (not differential) signature of the strong wins — what the route DOES there
    strong_wins = [e for e in rated if e["result"] == "W"]
    strong_losses = [e for e in rated if e["result"] == "L"]

    def abs_sig(eps, side):
        out = {}
        for k in ("total_revenue", "expenses_total", "animal_peak", "hands_d20", "occupied_d20"):
            out[k] = _stats([e[side].get(k) for e in eps])
        for p in PRODUCTS:
            out[f"units_{p}"] = _stats([e[side]["products"].get(p, {}).get("units", 0) for e in eps])
            out[f"price_{p}"] = _stats([e[side]["products"][p]["price"] for e in eps
                                        if p in e[side]["products"]])
            out[f"firstsell_{p}"] = _stats([e[side]["products"][p]["first_sell_day"] for e in eps
                                            if p in e[side]["products"]])
        return out

    meter = {
        "rated_1500plus": metering_view(rated, "opponent >= 1500"),
        "all": metering_view(episodes, "all ladder episodes"),
    }
    robust = {
        "rated_1500plus": robustness_view(rated, "opponent >= 1500"),
        "all": robustness_view(episodes, "all ladder episodes"),
    }

    def compact(e):
        keep = ("total_revenue", "expenses_total", "end_money", "animal_peak", "hands_d20",
                "occupied_d10", "occupied_d20", "n_quadrants", "spend")
        out = {k: v for k, v in e.items() if k not in ("us", "opp")}
        for side in ("us", "opp"):
            out[side] = {k: e[side][k] for k in keep}
            out[side]["products"] = e[side]["products"]
            out[side]["crop_tile_days"] = e[side]["crop_tile_days"]
            out[side]["daily_sales"] = {p: e[side]["daily_sales"].get(p, {}) for p in METER_PRODUCTS}
            out[side].update({f"money_d{d}": e[side].get(f"money_d{d}") for d in MILESTONE_DAYS})
        return out

    result = {
        "captions": {
            "rating_is_team": ("Opponent rating is a TEAM rating from a leaderboard snapshot, not a "
                               "per-submission or per-episode rating (§2 rule 5). Bands are "
                               "diagnostic; `rated_1500plus_sensitivity` re-cuts under the other "
                               "snapshot so a deflation artefact cannot carry a conclusion."),
            "paired_differential": ("Every feature is `us - opp` INSIDE one episode. Both seats share "
                                    "seed/town/shop draw/calendar, so the town — which owns 99-100% of "
                                    "realised $/u variance (§5.2) — cancels."),
            "identity": ("bank = startingMoney + sale_revenue - expenses exactly (reward = farm.money, "
                         "kaggriculture.py:963), so margin = d_revenue - d_expenses closes. "
                         f"Worst per-episode residual across the scan: ${worst:.2f}."),
            "auc": ("auc_win_vs_loss = P(differential in a win > differential in a loss). 0,50 = the "
                    "feature does not separate outcomes at all; it is rank-based, so the town's dollar "
                    "scale cannot inflate it."),
            "spend_split": ("hires/land/animals are exact from farm state; seeds are ESTIMATED from "
                            "day-over-day crop-tile increases (undercounts intra-day churn); the "
                            "remainder is BUY_PRODUCT (feed WHEAT + FERTILIZER) plus that churn and is "
                            "never presented as a clean category."),
        },
        "scan": {"n_episodes": len(episodes), "dropped_unclean_opponent": dropped,
                 "identity_worst_residual_dollars": round(worst, 2)},
        "views": views,
        "metering": meter,
        "town_robustness": robust,
        "strong_win_signature": {
            "n_wins": len(strong_wins), "n_losses": len(strong_losses),
            "us_in_wins": abs_sig(strong_wins, "us"),
            "opp_in_wins": abs_sig(strong_wins, "opp"),
            "us_in_losses": abs_sig(strong_losses, "us"),
            "opp_in_losses": abs_sig(strong_losses, "opp"),
        },
        "episodes": [compact(e) for e in episodes],
    }
    OUT.write_text(json.dumps(result, indent=1))

    print(f"\nscanned {len(episodes)} episodes (dropped {dropped} unclean-opponent); "
          f"identity worst residual ${worst:.2f}")
    for name in ("all", "rated_1500plus", "rated_1500plus_sensitivity"):
        v = views[name]
        print(f"\n=== {v['label']}: n={v['n']}  W-L {v['n_wins']}-{v['n_losses']}  wr={v['win_rate']}")
        for r in v["features"][:14]:
            w, l = r["wins"], r["losses"]
            if not w or not l:
                continue
            print(f"  {r['feature']:28s} AUC {r['auc_win_vs_loss']:.3f}  "
                  f"win med {w['median']:>11,.1f} (+{w['share_positive']:.2f})  "
                  f"loss med {l['median']:>11,.1f} (+{l['share_positive']:.2f})")

    print("\n=== metering (opp >= 1500), medians: units / price / top-day share / days / lead / late")
    for p, row in meter["rated_1500plus"]["products"].items():
        print(f"  {p}")
        for k in ("W_us", "W_opp", "L_us", "L_opp"):
            r = row.get(k)
            if r:
                print(f"    {k:6s} n={r['n']:3d}  u={r['units']:6.0f}  ${r['price']:7.1f}  "
                      f"top={r['top_day_share']:.2f}  days={r['n_days']:4.1f}  "
                      f"lead={r['lead_units']:5.0f}  late={r['late_share']:.2f}")
    rv = robust["rated_1500plus"]
    print("\n=== town robustness (opp >= 1500)")
    for k in ("revenue_us", "revenue_opp", "expenses_us", "expenses_opp"):
        s = rv.get(k)
        if s:
            print(f"  {k:14s} med {s['median']:>10,.0f}  q10 {s['q10']:>10,.0f}  q90 {s['q90']:>10,.0f}"
                  f"  band {s['q90_minus_q10']:>10,.0f}  sd {s['stdev']:>9,.0f}")
    for k in ("poor_town_half", "rich_town_half"):
        s = rv.get(k)
        if s:
            print(f"  {k:16s} n={s['n']:3d}  W-L {s['W']}-{s['L']} (wr {s['win_rate']})  "
                  f"straw ${s['median_strawberry_price']}  rev us {s['median_revenue_us']:,.0f} "
                  f"vs opp {s['median_revenue_opp']:,.0f}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
