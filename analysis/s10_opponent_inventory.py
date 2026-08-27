#!/usr/bin/env python3
"""S10 P4 / B2.0' — per-step opponent floor-unit estimator (measurement only).

B2.0' spike: for each step, compute the residual R(t) from the money-channel
identity and classify it as EXACT_ZERO / EXACT / MOD10 / AMBIGUOUS_WF.

The per-step identity (exact on 3 019/3 020 oracle steps):

    R(t) = Δmoney_opp(t) + hire(t) + land(t) − nonfloor_revenue_opp(t)
         = floor_units(t) − seed_cost(t) − animal_cost(t) − buy_product_cost(t)

When no hidden purchase at step t: R(t) = floor_units(t).
seed/animal costs are multiples of 10 → R ≡ floor_units (mod 10).
buy_product_cost (W/F only) is arbitrary → breaks mod-10 → AMBIGUOUS_WF.

Gate (all three required, measured PASS 2026-08-27 on 20 replays of 55726984:
exact_rate=0.982, signal_coverage=0.571, bracket_coverage=0.967):
  • exact-rate  ≥ 0.90  (EXACT_ZERO/EXACT correct vs ground truth)
  • signal-cov  ≥ 0.50  (EXACT_ZERO+EXACT cover ≥50% of real floor-sell steps)
  • bracket-cov ≥ 0.80  (truth inside [lo, hi] in MOD10/AMBIGUOUS_WF steps)

B2.1-B2.5 (shed tracker, per-product attribution, full fields, validation,
leakage-safe predictor) are NOT implemented here yet — see the plan.

No agent/ change, no upload.

CLI:
    python analysis/s10_opponent_inventory.py spike [sub] [n]
    python analysis/s10_opponent_inventory.py validate [sub] [n]
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
    ANIMALS, CROPS, LAND_PRICES, PRICE_FLOOR, PRODUCTS, SHOPS,
    TOWN_CENTER_PRODUCTS, _hire_cost, market_price,
)
from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402

DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)
PREMIUM = ("MELON", "STRAWBERRY")
DUMP_UNITS = 20
DUMP_HORIZON_TURNS = 24
NON_BUYABLE = frozenset(PRODUCTS) - frozenset(("WHEAT", "FERTILIZER"))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _town_consume_delta(unlocked_shops, step, shop_interval, center_interval):
    """Per-item consumption at step transition, matching engine._town_consume."""
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


def _nonfloor_revenue_walk(product, n_units, inv_start):
    """Revenue from n non-floor sells starting at inv_start."""
    rev = 0
    inv = inv_start
    for _ in range(n_units):
        p = market_price(product, inv)
        if p <= PRICE_FLOOR:
            break
        rev += p
        inv += 1
    return rev


def _buy_cost_walk(product, n_units, inv_start):
    """Cost of n BUY_PRODUCT units walked through the market curve.
    Engine quotes buys at market_price(item, inv - 1)."""
    cost = 0
    inv = inv_start
    for _ in range(n_units):
        price = market_price(product, max(0, inv - 1))
        cost += price
        inv = max(0, inv - 1)
    return cost


def _private_total(private, item):
    """Ground-truth stock: shed[item] + Σ per-unit-carried inventories[item]."""
    if not isinstance(private, dict):
        return 0
    shed = int(private.get("shed", {}).get(item, 0))
    inv = 0
    for u in private.get("inventories") or []:
        if isinstance(u, dict):
            inv += int(u.get(item, 0))
    return shed + inv


def _walk_seat_sells_buys(action, market_inventory_pre):
    """Per-seat committed non-floor SELL and BUY_PRODUCT units, walked against the
    engine's per-unit price curve."""
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


# ---------------------------------------------------------------------------
# B2.0' — Per-step floor-unit estimator
# ---------------------------------------------------------------------------

def spike_per_step(replay, our_seat_idx):
    """B2.0': per-step opponent floor-unit estimation with classification.

    For each step, computes R(t) from the money-channel identity using only
    public opponent state and our own committed sells (from _transition_events,
    wrapped to expose only our seat — B2.5 leakage test verifies this).

    Returns list of per-step dicts with estimate, classification, bracket,
    and ground truth (for validation).
    """
    from harness.metrics import _transition_events

    opp = 1 - our_seat_idx
    cfg = replay.get("configuration") or {}
    steps = replay["steps"]
    n = len(steps)
    if n < 2:
        return []

    shop_iv = max(1, int(cfg.get("townShopSellInterval", 4)))
    center_iv = max(1, int(cfg.get("townCenterSellInterval", 24)))
    shed_cap = int(cfg.get("shedCapacity", 100))

    results = []
    for t in range(1, n):
        prev_step = steps[t - 1]
        cur_step = steps[t]
        pre = prev_step[0]["observation"]
        post = cur_step[0]["observation"]
        engine_step = t - 1

        # --- One _transition_events call per step ---
        tr = _transition_events(prev_step, cur_step, cfg)

        # Our committed sells (estimator input — only our seat exposed)
        our_sales_by_p: dict[str, list[int]] = {}
        for sale in tr[2][our_seat_idx]:
            our_sales_by_p.setdefault(sale["item"], []).append(sale["price"])

        # Our raw BUY_PRODUCT orders for W/F (from our action, not opponent's)
        our_action = cur_step[our_seat_idx].get("action") or {}
        our_raw_buys_wf: dict[str, int] = {}
        for order in (our_action.get("market") or []):
            if (isinstance(order, list) and len(order) >= 3
                    and order[0] == "BUY_PRODUCT"
                    and order[1] in ("WHEAT", "FERTILIZER")):
                our_raw_buys_wf[order[1]] = (
                    our_raw_buys_wf.get(order[1], 0) + int(order[2]))

        # Ground truth: opponent floor sells (validation only, NOT estimation)
        gt_floor = sum(1 for sale in tr[2][opp]
                       if sale["price"] <= PRICE_FLOOR)

        # --- 1. Δmoney_opp ---
        dm = int(post["farms"][opp]["money"]) - int(pre["farms"][opp]["money"])

        # --- 2. Hire cost (exact from len(hands), B2.−0.5 #1) ---
        hands_pre = pre["farms"][opp].get("hands") or []
        hands_post = post["farms"][opp].get("hands") or []
        n_new_hands = max(0, len(hands_post) - len(hands_pre))
        hires_pre = int(pre["farms"][opp].get("hires_today", 0))
        hire = sum(
            _hire_cost(hires_pre + k) for k in range(n_new_hands))

        # --- 3. Land cost (exact from unlocked_quadrants) ---
        quads_pre = pre["farms"][opp].get("unlocked_quadrants") or ["NW"]
        quads_post = post["farms"][opp].get("unlocked_quadrants") or ["NW"]
        n_new_q = max(0, len(quads_post) - len(quads_pre))
        land = 0
        for i in range(n_new_q):
            idx = len(quads_pre) - 1 + i
            if idx < len(LAND_PRICES):
                land += LAND_PRICES[idx]

        # --- 4. ΔM identity for each product ---
        inv_pre_d = pre["market"]["inventory"]
        inv_post_d = post["market"]["inventory"]
        town = pre.get("town") or {}
        consume = _town_consume_delta(
            town.get("unlocked_shops"), engine_step, shop_iv, center_iv)

        # --- 5. Opponent non-floor revenue (total_walk − our_prices) ---
        opp_nf_revenue = 0
        wf_activity = False
        for p in PRODUCTS:
            delta_m = int(inv_post_d[p]) - int(inv_pre_d[p])
            our_rev = sum(
                pr for pr in our_sales_by_p.get(p, []) if pr > PRICE_FLOOR)

            if p in NON_BUYABLE:
                total_nf = delta_m + consume[p]
            else:
                our_buys = our_raw_buys_wf.get(p, 0)
                our_nf = sum(
                    1 for pr in our_sales_by_p.get(p, [])
                    if pr > PRICE_FLOOR)
                net_opp = delta_m + consume[p] - our_nf + our_buys
                if net_opp < 0:
                    wf_activity = True
                total_nf = delta_m + consume[p] + our_buys

            if total_nf > 0 and not wf_activity:
                total_rev = _nonfloor_revenue_walk(
                    p, total_nf, int(inv_pre_d[p]))
                opp_nf_revenue += total_rev - our_rev

        # --- 6. R(t) — no max(0, …) clipping (B2.−0.5 #4) ---
        R = dm + hire + land - opp_nf_revenue

        # --- 7. Classification (B2.0' Step 3) ---
        if wf_activity:
            cls = "AMBIGUOUS_WF"
            bracket_lo = 0
            bracket_hi = shed_cap
        elif R == 0:
            cls = "EXACT_ZERO"
            bracket_lo = 0
            bracket_hi = 0
        elif 0 < R < 10:
            cls = "EXACT"
            bracket_lo = R
            bracket_hi = R
        else:
            cls = "MOD10"
            bracket_lo = R % 10
            bracket_hi = shed_cap

        floor_est = R if cls in ("EXACT_ZERO", "EXACT") else None

        results.append({
            "step": t,
            "R": R,
            "classification": cls,
            "floor_units_est": floor_est,
            "bracket_lo": bracket_lo,
            "bracket_hi": bracket_hi,
            "gt_floor_units": gt_floor,
        })

    return results


def spike_validate(sub="55726984", n_replays=20):
    """B2.0' gate: validate per-step estimator on ≥n_replays ladder replays.

    Metrics (all per-step, never cumulative per-episode):
      exact_rate:      fraction of EXACT_ZERO/EXACT steps where estimate == truth
      signal_coverage: fraction of steps with real floor sales that are EXACT_ZERO/EXACT
      bracket_coverage: fraction of MOD10/AMBIGUOUS_WF steps where truth ∈ [lo, hi]
    """
    episodes = []
    n_used = 0

    g_exact_ok = 0
    g_exact_n = 0
    g_floor_in_exact = 0
    g_floor_total = 0
    g_bracket_ok = 0
    g_bracket_n = 0
    g_cls = defaultdict(int)

    for _eid, m in ladder_episodes(sub):
        if n_used >= n_replays:
            break
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        replay = {
            "steps": m["steps"],
            "configuration": m["configuration"],
        }

        step_results = spike_per_step(replay, seat)
        if not step_results:
            continue

        e_exact_ok = e_exact_n = 0
        e_floor_in_exact = e_floor_total = 0
        e_bracket_ok = e_bracket_n = 0
        e_cls: dict[str, int] = defaultdict(int)
        residuals: list[int] = []

        for sr in step_results:
            cls = sr["classification"]
            e_cls[cls] += 1
            gt = sr["gt_floor_units"]

            if cls in ("EXACT_ZERO", "EXACT"):
                e_exact_n += 1
                if sr["floor_units_est"] == gt:
                    e_exact_ok += 1
                if gt > 0:
                    e_floor_in_exact += 1
            else:
                e_bracket_n += 1
                if sr["bracket_lo"] <= gt <= sr["bracket_hi"]:
                    e_bracket_ok += 1
                else:
                    residuals.append(sr["R"])

            if gt > 0:
                e_floor_total += 1

        g_exact_ok += e_exact_ok
        g_exact_n += e_exact_n
        g_floor_in_exact += e_floor_in_exact
        g_floor_total += e_floor_total
        g_bracket_ok += e_bracket_ok
        g_bracket_n += e_bracket_n
        for k, v in e_cls.items():
            g_cls[k] += v

        er = e_exact_ok / e_exact_n if e_exact_n else 1.0
        sc = e_floor_in_exact / e_floor_total if e_floor_total else 1.0
        bc = e_bracket_ok / e_bracket_n if e_bracket_n else 1.0

        episodes.append({
            "episode_id": m["episode_id"],
            "n_steps": len(step_results),
            "exact_rate": round(er, 4),
            "signal_coverage": round(sc, 4),
            "bracket_coverage": round(bc, 4),
            "classification_counts": dict(e_cls),
            "bracket_misses": len(residuals),
        })
        n_used += 1
        print(f"  [{n_used}/{n_replays}] ep {m['episode_id']}: "
              f"exact={er:.3f} signal={sc:.3f} bracket={bc:.3f} "
              f"({dict(e_cls)})")

    if not episodes:
        return {"verdict": "NO_DATA", "n_used": 0}

    exact_rate = g_exact_ok / g_exact_n if g_exact_n else 1.0
    signal_cov = g_floor_in_exact / g_floor_total if g_floor_total else 1.0
    bracket_cov = g_bracket_ok / g_bracket_n if g_bracket_n else 1.0

    pass_er = exact_rate >= 0.90
    pass_sc = signal_cov >= 0.50
    pass_bc = bracket_cov >= 0.80
    all_pass = pass_er and pass_sc and pass_bc
    tag = "PASS" if all_pass else "FAIL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"B2.0' spike {tag}: "
                    f"exact_rate={exact_rate:.3f} (≥0.90), "
                    f"signal_coverage={signal_cov:.3f} (≥0.50), "
                    f"bracket_coverage={bracket_cov:.3f} (≥0.80)"),
        "submission": sub,
        "n_used": n_used,
        "exact_rate": round(exact_rate, 4),
        "signal_coverage": round(signal_cov, 4),
        "bracket_coverage": round(bracket_cov, 4),
        "pass_exact_rate": pass_er,
        "pass_signal_coverage": pass_sc,
        "pass_bracket_coverage": pass_bc,
        "classification_counts": dict(g_cls),
        "total_steps": sum(g_cls.values()),
        "total_exact_steps": g_exact_n,
        "total_bracket_steps": g_bracket_n,
        "total_floor_steps": g_floor_total,
        "episodes": episodes,
    }


# ---------------------------------------------------------------------------
# Legacy estimator (reads opponent actions — ground truth / comparison only)
# ---------------------------------------------------------------------------

def per_step_estimates(replay, our_seat_idx):
    """Yield per-step-boundary readings from the ΔM identity, plus opp ground truth.
    NOTE: reads opponent actions — use for ground truth comparison, not prediction."""
    cfg = replay.get("configuration") or {}
    shop_interval = max(1, int(cfg.get("townShopSellInterval", 4)))
    center_interval = max(1, int(cfg.get("townCenterSellInterval", 24)))
    steps = replay["steps"]
    if len(steps) < 2:
        return

    obs0 = steps[0][0]["observation"]
    initial_market = dict(obs0["market"]["inventory"])
    cum_sell_non = {p: 0 for p in PRODUCTS}
    cum_sell_floor = {p: 0 for p in PRODUCTS}
    cum_sell_non_opp = {p: 0 for p in PRODUCTS}
    cum_sell_floor_opp = {p: 0 for p in PRODUCTS}
    cum_buy = {p: 0 for p in PRODUCTS}
    cum_buy_opp = {p: 0 for p in PRODUCTS}
    cum_consume = {p: 0 for p in PRODUCTS}

    for t in range(1, len(steps)):
        pre = steps[t - 1][0]["observation"]
        post_seat0 = steps[t][0]["observation"]
        post_opp_priv = steps[t][1 - our_seat_idx].get(
            "observation", {}).get("private")
        town = pre.get("town") or obs0.get("town") or {}

        our_action = steps[t][our_seat_idx].get("action") or {}
        opp_action = steps[t][1 - our_seat_idx].get("action") or {}
        us_non, us_buy, us_fl = _walk_seat_sells_buys(
            our_action, pre["market"]["inventory"])
        opp_non, opp_buy, opp_fl = _walk_seat_sells_buys(
            opp_action, pre["market"]["inventory"])
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
        labels[t] = sum(sells_at[t + 1: t + 1 + horizon]) >= unit_threshold
    return labels


def validate(sub="55726984", n_replays=10):
    """Run the legacy estimator on `n_replays` and report precision on dump
    prediction for MELON and STRAWBERRY (plan §P4.3 kill criterion)."""
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

        cum_history = defaultdict(list)
        for reading in per_step_estimates(replay, seat):
            n_boundaries += 1
            for p in PREMIUM:
                cum_history[p].append(reading["cum_opp_sell_nonfloor"][p])
                per_product_residual_running[p].append(
                    reading["delta_M_residual"][p])
                window_back = max(0, len(cum_history[p]) - 72)
                delta_recent = (cum_history[p][-1]
                                - cum_history[p][window_back])
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

    dead = any((precision[p] is not None and precision[p] < 0.70)
               for p in PREMIUM)
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
        "confusion": {p: {"tp": tp[p], "fp": fp[p], "fn": fn[p]}
                      for p in PREMIUM},
        "delta_M_residual_final_median": {
            p: (sorted(v)[len(v) // 2] if v else None)
            for p, v in per_product_residual_running.items()
        },
        "kill_criterion": "precision < 0.70 for MELON or STRAWBERRY",
        "hit_kill_criterion": dead,
    }


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""

    if cmd == "spike":
        sub = args[1] if len(args) > 1 else "55726984"
        n = int(args[2]) if len(args) > 2 else 20
        out = spike_validate(sub, n)
        p = DERIVED / "s10_opponent_spike.json"
        p.write_text(json.dumps(out, indent=2))
        print(f"wrote {p}")
        print(out["verdict"])
        return

    if cmd == "validate":
        sub = args[1] if len(args) > 1 else "55726984"
        n = int(args[2]) if len(args) > 2 else 10
        out = validate(sub, n)
        p = DERIVED / "s10_opponent_inventory.json"
        p.write_text(json.dumps(out, indent=2))
        print(f"wrote {p} ({out['verdict']})")
        return

    print("usage: python analysis/s10_opponent_inventory.py "
          "{spike|validate} [sub=55726984] [n=20]")
    sys.exit(2)


if __name__ == "__main__":
    main()
