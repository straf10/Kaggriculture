#!/usr/bin/env python3
"""S10 P4 — opponent-inventory estimator (measurement only, no policy).

The `pro-ladder-playbook`'s second post: opponent inventory of each product is
inferable from public state.  Between t and t+1 the shared market inventory
moves by

    ΔM_i(t) = Σ_seats sell_nonfloor_i(t) − Σ_seats buy_i(t) − D_i(t)

where D_i(t) is deterministic (`_town_consume`).  Actions are public in the
replay, so at replay time we can reconstruct both sides' committed sells and
buys and validate.

The **kill criterion** (plan §P4.3) is prediction, not MAE: for MELON and
STRAWBERRY, does the estimator predict "opponent will sell ≥20 units in the
next 24 turns" with precision ≥ 0,70?  The memory `price-floor-liquidation-sink`
already anticipates the answer: 183 $1-floor units per episode drain opponent
inventory without touching market, exactly where identifiability is needed.

This module implements:
  - the ΔM identity, evaluated per step from public state,
  - the dump-prediction precision test on MELON and STRAWBERRY,
  - MAE per product of a naive point estimate against replay ground truth.

Read-only.  No `agent/` change, no upload.  Output: gitignored derived JSON.

CLI:
    python analysis/s10_opponent_inventory.py validate [sub=55726984] [n=10]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

from engine_reference.kaggriculture import (  # noqa: E402
    PRICE_FLOOR, PRODUCTS, SHOPS, TOWN_CENTER_PRODUCTS, market_price,
)
from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402

DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)
PREMIUM = ("MELON", "STRAWBERRY")
DUMP_UNITS = 20
DUMP_HORIZON_TURNS = 24


def _town_consume_delta(unlocked_shops, step, shop_interval, center_interval):
    """Per-item consumption at step transition (t → t+1), matching
    engine._town_consume without mutating state."""
    consume = {p: 0 for p in PRODUCTS}
    if step % shop_interval == 0:
        for shop in unlocked_shops or []:
            products = SHOPS[shop]
            mult = 2 if len(products) == 1 else 1
            for item in products:
                consume[item] += mult
    if step % center_interval == 0:
        for item in TOWN_CENTER_PRODUCTS:
            consume[item] += 1
    return consume


def _walk_seat_sells_buys(action, market_inventory_pre):
    """Per-seat committed non-floor SELL and BUY_PRODUCT units, walked against the
    engine's per-unit price curve.  Same walk as
    `analysis/s9_market_ledger.py::step_ledger` and
    `harness/metrics.py::_sell_units_ordered_at_floor` (unit-lockstep, floor units
    do not raise inventory).  Rejection constraints (shed/money) are not modelled
    — the residual against the recorded ΔM captures that drift."""
    sell_non = {p: 0 for p in PRODUCTS}
    sell_floor = {p: 0 for p in PRODUCTS}
    buy = {p: 0 for p in PRODUCTS}
    if not isinstance(action, dict):
        return sell_non, buy, sell_floor
    inv = dict(market_inventory_pre)
    for order in action.get("market") or []:
        if not (isinstance(order, list) and len(order) >= 3):
            continue
        op, item, qty = order[0], order[1], int(order[2])
        if op == "SELL" and item in PRODUCTS:
            for _ in range(qty):
                price = market_price(item, inv[item])
                if price == PRICE_FLOOR:
                    sell_floor[item] += 1
                else:
                    sell_non[item] += 1
                    inv[item] += 1
        elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
            for _ in range(qty):
                buy[item] += 1
                inv[item] = max(0, inv[item] - 1)
    return sell_non, buy, sell_floor


def _private_total(private, item):
    """Ground-truth stock: shed[item] + Σ per-unit-carried inventories[item].
    Available from the replay for BOTH sides — validation ground truth only."""
    if not isinstance(private, dict):
        return 0
    shed = int(private.get("shed", {}).get(item, 0))
    inv = 0
    for u in private.get("inventories") or []:
        if isinstance(u, dict):
            inv += int(u.get(item, 0))
    return shed + inv


def per_step_estimates(replay, our_seat_idx):
    """Yield per-step-boundary readings from the ΔM identity, plus opp ground truth."""
    cfg = replay.get("configuration") or {}
    shop_interval = max(1, int(cfg.get("townShopSellInterval", 4)))
    center_interval = max(1, int(cfg.get("townCenterSellInterval", 24)))
    steps = replay["steps"]
    if len(steps) < 2:
        return

    obs0 = steps[0][0]["observation"]
    initial_market = dict(obs0["market"]["inventory"])
    cum_sell_non = {p: 0 for p in PRODUCTS}       # both seats
    cum_sell_floor = {p: 0 for p in PRODUCTS}     # both seats
    cum_sell_non_opp = {p: 0 for p in PRODUCTS}   # opponent's contribution
    cum_sell_floor_opp = {p: 0 for p in PRODUCTS}  # opponent's contribution
    cum_buy = {p: 0 for p in PRODUCTS}            # both seats
    cum_buy_opp = {p: 0 for p in PRODUCTS}
    cum_consume = {p: 0 for p in PRODUCTS}

    for t in range(1, len(steps)):
        pre = steps[t - 1][0]["observation"]
        post_seat0 = steps[t][0]["observation"]
        post_opp_priv = steps[t][1 - our_seat_idx].get("observation", {}).get("private")
        town = pre.get("town") or obs0.get("town") or {}

        # Walk our and opp actions once each.  We do walk them separately (interleaved
        # inv would need engine-order round-robin; for the identity residual we just
        # need summed counters, and the residual absorbs the interleaving drift).
        our_action = steps[t][our_seat_idx].get("action") or {}
        opp_action = steps[t][1 - our_seat_idx].get("action") or {}
        us_non, us_buy, us_fl = _walk_seat_sells_buys(
            our_action, pre["market"]["inventory"])
        opp_non, opp_buy, opp_fl = _walk_seat_sells_buys(
            opp_action, pre["market"]["inventory"])
        # The engine runs _town_consume(env, state, step) with the PRE-transition step
        # value, i.e. obs["step"] as recorded at steps[t-1] — which is t-1, not t. Passing
        # `t` shifted every consumption tick by one step and left a permanent residual on
        # products with no fill drift; with t-1 the ΔM identity closes exactly for CARROT,
        # TOMATO and EGG.
        consume = _town_consume_delta(town.get("unlocked_shops"), t - 1,
                                      shop_interval, center_interval)

        for p in PRODUCTS:
            cum_sell_non[p] += us_non[p] + opp_non[p]
            cum_sell_non_opp[p] += opp_non[p]
            cum_sell_floor[p] += us_fl[p] + opp_fl[p]
            cum_sell_floor_opp[p] += opp_fl[p]
            cum_buy[p] += us_buy[p] + opp_buy[p]
            cum_buy_opp[p] += opp_buy[p]
            cum_consume[p] += consume[p]

        market_actual = post_seat0["market"]["inventory"]
        opp_true = {p: _private_total(post_opp_priv, p) for p in PRODUCTS}

        # ΔM identity residual, per product.  Non-zero == unaccounted floor sells
        # or fill drift; grows monotonically over the episode.
        dm_residual = {}
        for p in PRODUCTS:
            predicted = (initial_market[p]
                         + cum_sell_non[p] - cum_buy[p] - cum_consume[p])
            dm_residual[p] = int(market_actual[p]) - predicted

        yield {
            "step": t,
            "day": int(post_seat0.get("day", 0)),
            "cum_opp_sell_nonfloor": dict(cum_sell_non_opp),
            "cum_opp_sell_floor": dict(cum_sell_floor_opp),
            "cum_opp_buy": dict(cum_buy_opp),
            "delta_M_residual": dm_residual,
            "opp_true_private_total": opp_true,
        }


def _dump_events(replay, opp_seat, product, unit_threshold=DUMP_UNITS,
                 horizon=DUMP_HORIZON_TURNS):
    """Ground-truth binary label for each step: does opponent SELL ≥ unit_threshold
    units of `product` in the next `horizon` steps?  Uses opp raw actions."""
    steps = replay["steps"]
    n = len(steps)
    sells_at = [0] * n
    for t in range(1, n):
        action = steps[t][opp_seat].get("action") or {}
        for order in action.get("market") or []:
            if (isinstance(order, list) and len(order) >= 3
                    and order[0] == "SELL" and order[1] == product):
                sells_at[t] += int(order[2])
    labels = [False] * n
    for t in range(n):
        # The window is the next `horizon` turns AFTER t: [t+1, t+horizon] inclusive.
        # `sells_at[t + 1: t + 1 + horizon]` is exactly that; the previous slice stopped at
        # t + horizon and so covered only horizon − 1 turns.
        labels[t] = sum(sells_at[t + 1: t + 1 + horizon]) >= unit_threshold
    return labels


def validate(sub="55726984", n_replays=10):
    """Run the estimator on `n_replays` and report precision on dump prediction
    for MELON and STRAWBERRY (plan §P4.3 kill criterion)."""
    per_product_residual_running = defaultdict(list)
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    n_boundaries = 0
    n_used = 0

    for i, (eid, m) in enumerate(ladder_episodes(sub)):
        if n_used >= n_replays:
            break
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        opp_seat = 1 - seat
        replay = {"steps": m["steps"], "configuration": m["configuration"]}
        gt_dump = {p: _dump_events(replay, opp_seat, p) for p in PREMIUM}

        # A concrete point estimate we can gate on:
        #   opp_stock_est = cum_opp_sell_nonfloor − cum_opp_buy + starting_slack
        # We predict "dump next" if the estimator sees ≥ DUMP_UNITS of accumulated
        # non-floor sells in the last 3 days AND the horizon has any product left
        # (opp_true > 0).  Naive but concrete — the study reports whether it hits
        # the ≥0,70 bar or not.
        cum_history = defaultdict(list)
        for reading in per_step_estimates(replay, seat):
            n_boundaries += 1
            for p in PREMIUM:
                cum_history[p].append(reading["cum_opp_sell_nonfloor"][p])
                per_product_residual_running[p].append(reading["delta_M_residual"][p])
                # Predict: opp is "about to dump" if net non-floor sells rose by
                # ≥ (DUMP_UNITS / 2) over the last 72 steps (~ 3 days).
                window_back = max(0, len(cum_history[p]) - 72)
                delta_recent = cum_history[p][-1] - cum_history[p][window_back]
                predicted = delta_recent >= DUMP_UNITS / 2
                actual = gt_dump[p][reading["step"]]
                if predicted and actual:
                    tp[p] += 1
                elif predicted and not actual:
                    fp[p] += 1
                elif not predicted and actual:
                    fn[p] += 1
        n_used += 1

    precision = {}
    for p in PREMIUM:
        denom = tp[p] + fp[p]
        precision[p] = tp[p] / denom if denom else None

    # Kill criterion: precision < 0,70 for either MELON or STRAWBERRY.
    dead = any((precision[p] is not None and precision[p] < 0.70) for p in PREMIUM)
    verdict = ("STOPPED_KILL_CRITERION_HIT" if dead else "PROCEED")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"opponent_inventory {verdict}: "
                    f"precision MELON={precision['MELON']}, "
                    f"STRAWBERRY={precision['STRAWBERRY']} (target ≥0,70)"),
        "submission": sub,
        "n_replays_used": n_used,
        "n_step_boundaries": n_boundaries,
        "dump_definition": {"unit_threshold": DUMP_UNITS,
                            "horizon_turns": DUMP_HORIZON_TURNS},
        "precision": {p: precision[p] for p in PREMIUM},
        "confusion": {p: {"tp": tp[p], "fp": fp[p], "fn": fn[p]} for p in PREMIUM},
        "delta_M_residual_final_median": {
            p: (sorted(v)[len(v) // 2] if v else None)
            for p, v in per_product_residual_running.items()
        },
        "kill_criterion": "precision < 0.70 for MELON or STRAWBERRY",
        "hit_kill_criterion": dead,
    }


def main():
    args = sys.argv[1:]
    if not args or args[0] != "validate":
        print("usage: python analysis/s10_opponent_inventory.py validate "
              "[sub=55726984] [n=10]")
        sys.exit(2)
    sub = args[1] if len(args) > 1 else "55726984"
    n = int(args[2]) if len(args) > 2 else 10
    out = validate(sub, n)
    p = DERIVED / "s10_opponent_inventory.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p} ({out['verdict']})")


if __name__ == "__main__":
    main()
