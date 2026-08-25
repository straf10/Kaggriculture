#!/usr/bin/env python3
"""Exact realised sale revenue per product, replayed from a live replay.

The engine prices a market turn **per unit** (`_process_market`): each unit of a SELL is quoted at
`market_price(item, inventory)` for the inventory *at that moment*, and every committed sell raises
the inventory by one, so a bulk dump walks its own price down.  Pricing a whole order at the step's
quoted price therefore overstates a dump badly — which is why this module re-runs the lockstep
against `engine_reference.kaggriculture.market_price` instead.

Constraints that can reject a unit (empty shed, no money, full shed) are not simulated; the
`validate` path checks how much that costs by comparing the replayed money delta against the
recorded one on every step, and the caller is expected to report the mismatch.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine_reference.kaggriculture import (  # noqa: E402
    ANIMALS, CROPS, FARM_HAND_COST_MULT, LAND_ORDER, LAND_PRICES, PRICE_FLOOR, PRODUCTS,
    _hire_cost, market_price,
)

MAX_ORDERS = 10


def _parse(order):
    if not isinstance(order, list) or not order:
        return None
    op = order[0]
    if op in ("HIRE", "BUY_LAND"):
        return {"type": op}
    if op in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"):
        if len(order) < 3:
            return None
        try:
            n = int(order[2])
        except (TypeError, ValueError):
            return None
        return {"type": op, "item": order[1], "remaining": n} if n > 0 else None
    return None


def step_ledger(inventory, orders_by_player, hires_today=(0, 0), quadrants=(1, 1)):
    """Replay one market turn.  Returns (revenue, units, spend, inventory) with per-player dicts."""
    inv = dict(inventory)
    revenue = [Counter(), Counter()]
    units = [Counter(), Counter()]
    spend = [Counter(), Counter()]
    hires = list(hires_today)
    quads = list(quadrants)

    queues = [[_parse(o) for o in (q or [])[:MAX_ORDERS]] for q in orders_by_player]
    max_len = max((len(q) for q in queues), default=0)
    for i in range(max_len):
        ostates = [q[i] if i < len(q) else None for q in queues]
        for pid, st in enumerate(ostates):
            if st is None:
                continue
            if st["type"] == "HIRE":
                spend[pid]["HIRE"] += _hire_cost(hires[pid], FARM_HAND_COST_MULT)
                hires[pid] += 1
            elif st["type"] == "BUY_LAND":
                extra = quads[pid] - 1
                if extra < len(LAND_ORDER):
                    spend[pid]["BUY_LAND"] += LAND_PRICES[extra]
                    quads[pid] += 1
        ostates = [None if (s and s["type"] in ("HIRE", "BUY_LAND")) else s for s in ostates]
        while True:
            quoted = [None, None]
            for pid, st in enumerate(ostates):
                if st is None or st["remaining"] <= 0:
                    continue
                op, item = st["type"], st["item"]
                if op == "SELL" and item in PRODUCTS:
                    quoted[pid] = (op, item, market_price(item, inv[item]))
                elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                    quoted[pid] = (op, item, market_price(item, inv[item] - 1))
                elif op == "BUY_SEED" and item in CROPS:
                    quoted[pid] = (op, item, CROPS[item]["seed"])
                elif op == "BUY_ANIMAL" and item in ANIMALS:
                    quoted[pid] = (op, item, ANIMALS[item]["cost"])
                else:
                    ostates[pid] = None
            if all(q is None for q in quoted):
                break
            for pid, q in enumerate(quoted):
                if q is None:
                    continue
                op, item, price = q
                if op == "SELL":
                    revenue[pid][item] += price
                    units[pid][item] += 1
                    if price > PRICE_FLOOR:
                        inv[item] += 1
                else:
                    spend[pid][op if op != "BUY_PRODUCT" else item] += price
                    if op == "BUY_PRODUCT":
                        inv[item] -= 1
                ostates[pid]["remaining"] -= 1
    return revenue, units, spend, inv


def episode_ledger(replay):
    """Per-seat realised revenue/units/spend over the whole episode.

    The per-step simulation assumes every submitted order commits.  It cannot: a SELL against an
    empty shed is dropped, and an open-loop tape drops a lot of them.  The exact cash flow *is*
    recorded (money is only touched by the market), so each step's simulated revenue is rescaled
    to the recorded money delta and the per-product split is carried through that scale.  The
    unscaled totals and the scale distribution are reported so the correction stays visible.
    """
    steps = replay["steps"]
    revenue = [Counter(), Counter()]
    units = [Counter(), Counter()]
    ordered = [Counter(), Counter()]
    spend = [Counter(), Counter()]
    by_day = [Counter(), Counter()]
    raw_rev = [0.0, 0.0]
    scales = [[], []]
    # The recorded observation at index t is the state *after* step t's action, so a step t order
    # is quoted against the market recorded at t-1 (verified on money deltas).
    for t in range(1, len(steps)):
        pre = steps[t - 1][0]["observation"]
        post = steps[t][0]["observation"]
        orders = [(steps[t][0].get("action") or {}).get("market") or [],
                  (steps[t][1].get("action") or {}).get("market") or []]
        if not orders[0] and not orders[1]:
            continue
        rev, un, sp, _ = step_ledger(
            pre["market"]["inventory"], orders,
            hires_today=[int(pre["farms"][p].get("hires_today", 0)) for p in (0, 1)],
            quadrants=[len(pre["farms"][p].get("unlocked_quadrants") or ["NW"]) for p in (0, 1)],
        )
        day = post["day"]
        for pid in (0, 1):
            sim_rev = sum(rev[pid].values())
            sim_spend = sum(sp[pid].values())
            cash = float(post["farms"][pid]["money"]) - float(pre["farms"][pid]["money"])
            raw_rev[pid] += sim_rev
            if sim_rev > 0:
                scale = (cash + sim_spend) / sim_rev
                scale = min(1.0, max(0.0, scale))
                scales[pid].append(scale)
            else:
                scale = 1.0
            for item, v in rev[pid].items():
                revenue[pid][item] += v * scale
                units[pid][item] += un[pid][item] * scale
                ordered[pid][item] += un[pid][item]
            by_day[pid][day] += sim_rev * scale
            spend[pid] += sp[pid]
    return {
        "revenue": [{k: round(v, 1) for k, v in r.items()} for r in revenue],
        "units": [{k: round(v, 1) for k, v in u.items()} for u in units],
        "units_ordered": [dict(u) for u in ordered],
        "spend": [{k: round(v, 1) for k, v in s.items()} for s in spend],
        "by_day": [{str(k): round(v, 1) for k, v in d.items()} for d in by_day],
        "fill": [{"steps_with_sales": len(s),
                  "mean_fill": (sum(s) / len(s)) if s else None,
                  "full_fill_share": (sum(1 for x in s if x > 0.999) / len(s)) if s else None,
                  "revenue_before_scaling": round(raw_rev[p]),
                  "revenue_after_scaling": round(sum(revenue[p].values()))}
                 for p, s in enumerate(scales)],
    }
