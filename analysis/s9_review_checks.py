#!/usr/bin/env python3
"""S9 plan review — independent re-derivation of every load-bearing number in
`docs/plans/s9_liquidation_heuristics.md`, from the 253 live replays and the engine.

Nothing here reuses the plan's own arithmetic: sales are re-simulated through
`harness.metrics._transition_events` (the one market meter), prices through the
engine's own `market_price`, drains through the engine's own `_town_consume` rule.

Output: data/derived/s9_review_checks.json  (gitignored)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

import kaggriculture as K  # noqa: E402
from analysis.s8_replay_io import SUBMISSIONS, ladder_episodes, our_seat  # noqa: E402
from harness.metrics import _transition_events  # noqa: E402

OUT = ROOT / "data" / "derived" / "s9_review_checks.json"
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
TPD = 24


def drain_between(shops, t_from, t_to, item):
    """Units of `item` the TOWN removes in steps (t_from, t_to] — engine `_town_consume` :728.

    `shops` is the unlocked_shops list as it stands over that window (shops only ever get
    added at a day boundary, and callers keep t_from/t_to inside one day, so the list is
    constant across the window)."""
    n = 0
    for s in range(t_from + 1, t_to + 1):
        if s % 4 == 0:
            for shop in shops:
                prods = K.SHOPS[shop]
                if item in prods:
                    n += 2 if len(prods) == 1 else 1
        if s % 24 == 0 and item in K.TOWN_CENTER_PRODUCTS:
            n += 1
    return n


def scan_episode(m, seat):
    steps = m["steps"]
    cfg = m["configuration"]
    opp = 1 - seat

    inv_at = []            # step -> market inventory dict as SEEN by the order at that step
    shops_at = []          # step -> unlocked_shops list at that step
    shed_at = [[], []]     # seat -> step -> shed occupancy
    shed_item_at = [[], []]
    money_at = [[], []]
    for t in range(len(steps)):
        o0 = steps[t][0]["observation"]
        inv_at.append(o0["market"]["inventory"])
        shops_at.append(list(o0["town"].get("unlocked_shops", [])))
        for s in (0, 1):
            pv = steps[t][s]["observation"]["private"]
            shed_at[s].append(sum(pv["shed"].values()))
            shed_item_at[s].append(pv["shed"])
            money_at[s].append(o0["farms"][s]["money"])

    # committed sales, per step
    sales_at = []          # step -> [ [ {item,price} ... ] x seat ]
    feed_issued = 0
    buy_wheat_units_issued = 0
    buy_wheat_units_committed = 0
    buy_fert_units_issued = 0
    sell_orders_issued_over_cap = 0
    opp_orders_issued = 0
    for i in range(1, len(steps)):
        acts, _ov, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
        sales_at.append(sales)
        a_us = acts[seat] if isinstance(acts[seat], dict) else {}
        raw = (steps[i][seat].get("action") or {})
        # FEED intents (farmer + hands)
        for u in [raw.get("farmer") or []] + list(raw.get("hands") or []):
            if isinstance(u, list) and u and u[0] == "FEED":
                feed_issued += 1
        mk = list(raw.get("market") or [])
        if len(mk) > 10:
            sell_orders_issued_over_cap += len(mk) - 10
        for od in mk[:10]:
            if isinstance(od, list) and od and od[0] == "BUY_PRODUCT":
                q = int(od[2]) if len(od) > 2 else 1
                if od[1] == "WHEAT":
                    buy_wheat_units_issued += q
                elif od[1] == "FERTILIZER":
                    buy_fert_units_issued += q
        opp_orders_issued += len(list((steps[i][opp].get("action") or {}).get("market") or [])[:10])
    # committed BUY_PRODUCT WHEAT: shed WHEAT increments not explained by sales is hard;
    # instead re-simulate: _transition_events already commits buys inside _simulate_market,
    # but only returns sales. Recover committed buys from market inventory drops beyond drain.
    # Cheaper and exact enough: count via a second targeted pass below.

    return dict(inv_at=inv_at, shops_at=shops_at, shed_at=shed_at, shed_item_at=shed_item_at,
                money_at=money_at, sales_at=sales_at, feed_issued=feed_issued,
                buy_wheat_units_issued=buy_wheat_units_issued,
                buy_fert_units_issued=buy_fert_units_issued,
                sell_orders_over_cap=sell_orders_issued_over_cap,
                opp_orders_issued=opp_orders_issued)


def main(limit=None):
    rows = []
    n = 0
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            sc = scan_episode(m, seat)
            opp = 1 - seat
            inv_at, shops_at = sc["inv_at"], sc["shops_at"]

            hour_units = [defaultdict(int), defaultdict(int)]      # seat_rel -> hour -> units
            prod_day = [defaultdict(lambda: defaultdict(lambda: [0, 0.0])) for _ in (0, 1)]
            # H1 firing counters, our side only
            h1 = dict(events=0, units=0, movable_literal=0, units_literal=0,
                      movable_oracle=0, units_oracle=0, gain_oracle=0.0)
            melon_shed_days = set()
            for i, sales in enumerate(sc["sales_at"], start=1):
                t = i - 1                       # obs step the order priced against
                hour = t % TPD
                day = t // TPD
                for rel, s_idx in ((0, seat), (1, opp)):
                    for s in sales[s_idx]:
                        hour_units[rel][hour] += 1
                        cell = prod_day[rel][s["item"]][day]
                        cell[0] += 1
                        cell[1] += s["price"]
                # H1: for each of OUR sold units, could an earlier step of the same day
                # have priced at least as well?
                day_start = day * TPD
                for s in sales[seat]:
                    item, price = s["item"], s["price"]
                    h1["events"] += 1
                    h1["units"] += 1
                    best_lit = False
                    best_oracle_price = price
                    for tp in range(day_start, t):
                        inv_p = inv_at[tp][item]
                        p_now = K.market_price(item, inv_p)
                        d = drain_between(shops_at[tp], tp, t, item)
                        p_later_known = K.market_price(item, inv_p - d)
                        if p_now >= p_later_known:
                            best_lit = True
                        if p_now > best_oracle_price:
                            best_oracle_price = p_now
                    if best_lit:
                        h1["movable_literal"] += 1
                    if best_oracle_price > price:
                        h1["movable_oracle"] += 1
                        h1["gain_oracle"] += best_oracle_price - price
            for t in range(len(inv_at)):
                if sc["shed_item_at"][seat][t].get("MELON", 0) > 0:
                    melon_shed_days.add(t // TPD)

            # shop unlock days
            unlock_days = []
            prev = 0
            for t in range(len(shops_at)):
                if len(shops_at[t]) > prev:
                    unlock_days.append((t // TPD, len(shops_at[t])))
                    prev = len(shops_at[t])

            shed_us = sc["shed_at"][seat]
            shed_opp = sc["shed_at"][opp]
            rows.append(dict(
                submission=sub, episode_id=eid, seat=seat,
                teams=m["teams"],
                reward_us=m["rewards"][seat], reward_opp=m["rewards"][opp],
                hour_units_us={str(h): v for h, v in hour_units[0].items()},
                hour_units_opp={str(h): v for h, v in hour_units[1].items()},
                prod_day_us={p: {str(d): v for d, v in dd.items()} for p, dd in prod_day[0].items()},
                prod_day_opp={p: {str(d): v for d, v in dd.items()} for p, dd in prod_day[1].items()},
                h1=h1,
                melon_shed_days=sorted(melon_shed_days),
                unlock_days=unlock_days,
                shops_final=shops_at[-1],
                shed_max_us=max(shed_us), shed_max_opp=max(shed_opp),
                shed_max_by_day_us=[max(shed_us[d * TPD:(d + 1) * TPD] or [0]) for d in range(30)],
                shed_end_us=shed_us[-1], shed_end_opp=shed_opp[-1],
                money_us=sc["money_at"][seat], money_opp=sc["money_at"][opp],
                feed_issued=sc["feed_issued"],
                buy_wheat_units_issued=sc["buy_wheat_units_issued"],
                buy_fert_units_issued=sc["buy_fert_units_issued"],
                sell_orders_over_cap=sc["sell_orders_over_cap"],
                opp_orders_issued=sc["opp_orders_issued"],
            ))
            n += 1
            if n % 20 == 0:
                print(f"  {n} episodes", flush=True)
            if limit and n >= limit:
                break
        if limit and n >= limit:
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows))
    print(f"wrote {OUT} ({n} episodes)")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(lim)
