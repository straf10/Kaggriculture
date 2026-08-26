#!/usr/bin/env python3
"""S10 P4 — opponent-inventory estimator (measurement only, no policy).

B2.0 spike: estimate opponent's *floor sells* from public state only.

The money channel for the opponent decomposes as:

    Δmoney_opp = sell_revenue − buy_product_cost − seed_cost − animal_cost
                 − hire_cost − land_cost

    sell_revenue = nonfloor_revenue + floor_units × $1

Rearranging:

    floor_units = Δmoney + costs − nonfloor_revenue

where costs = buy_product + seed + animal + hire + land.

The ΔM identity provides the non-floor sell counts per product (exact for 7
non-buyable products, net-only for WHEAT/FERTILIZER).  Observable farm state
changes provide hire/land/animal/seed costs.  The remaining uncertainty terms
(unplanted seeds, W/F decomposition, day-boundary hires, interleaving revenue)
produce explicit [lower, upper] bounds.

B2.0 gate (plan §B2.0):
  • MAE of per-episode floor_units ≤ 15% (median across ≥20 replays)
  • coverage ≥ 0.80 (truth within [lower, upper])

Read-only.  No `agent/` change, no upload.
CLI:
    python analysis/s10_opponent_inventory.py spike [sub=55726984] [n=20]
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
    ANIMALS, CROPS, LAND_PRICES, PRICE_FLOOR, PRODUCTS, SHOPS,
    TOWN_CENTER_PRODUCTS, _hire_cost, _is_shed_adjacent, market_price,
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


def _our_committed_nb_sells(prev_obs, action, seat, board_size=10, shed_cap=100):
    """Our committed NB sells at one step, via shed + DROP/PLACE simulation.

    Returns {product: (nf_count, floor_count)} for NB products only.
    Uses pre-action observation (the state BEFORE action is applied).
    """
    prev_farm = prev_obs["farms"][seat]
    market_inv = dict(prev_obs["market"]["inventory"])

    shed = dict(prev_obs["private"]["shed"])
    inventories = [
        dict(inv) if isinstance(inv, dict) else {}
        for inv in prev_obs["private"]["inventories"]
    ]

    all_unit_acts = [action.get("farmer") or ["PASS"]] + (
        action.get("hands") or []
    )
    all_positions = [prev_farm["farmer"]] + list(prev_farm["hands"])

    for u_idx, u_act in enumerate(all_unit_acts):
        if not isinstance(u_act, list) or not u_act or u_idx >= len(all_positions):
            continue
        pos = all_positions[u_idx]
        inv = inventories[u_idx] if u_idx < len(inventories) else {}
        op = u_act[0]

        if op == "DROP" and _is_shed_adjacent(pos, board_size):
            for item, n in list(inv.items()):
                if n <= 0:
                    continue
                room = max(0, shed_cap - sum(shed.values()))
                take = min(n, room)
                if take > 0:
                    shed[item] = shed.get(item, 0) + take
                inv[item] = 0

        elif op == "PLACE" and len(u_act) >= 2:
            item = u_act[1]
            if item in ANIMALS:
                continue
            if _is_shed_adjacent(pos, board_size):
                n = int(u_act[2]) if len(u_act) >= 3 else 1
                n = min(n, inv.get(item, 0))
                room = max(0, shed_cap - sum(shed.values()))
                n = min(n, room)
                if n > 0:
                    inv[item] = inv.get(item, 0) - n
                    shed[item] = shed.get(item, 0) + n

    result = {}
    for order in action.get("market") or []:
        if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL":
            continue
        product = order[1]
        qty = int(order[2])
        avail = shed.get(product, 0)
        committed = min(qty, avail)
        shed[product] = shed.get(product, 0) - committed

        if committed > 0 and product in NON_BUYABLE:
            nf = 0
            fl = 0
            for _ in range(committed):
                price = market_price(product, market_inv[product])
                if price > PRICE_FLOOR:
                    nf += 1
                    market_inv[product] += 1
                else:
                    fl += 1
            prev_nf, prev_fl = result.get(product, (0, 0))
            result[product] = (prev_nf + nf, prev_fl + fl)

    return result


# ---------------------------------------------------------------------------
# B2.0 spike — public-info-only floor-units estimator
# ---------------------------------------------------------------------------

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


def spike_estimate(replay, our_seat_idx):
    """B2.0: estimate episode-total opponent floor units from public obs only.

    Reads ONLY obs (public farms/market/town) and our own actions.
    NEVER reads steps[t][1-our_seat_idx]["action"].

    Returns dict with point/lo/hi estimates and diagnostic breakdown.
    """
    opp = 1 - our_seat_idx
    cfg = replay.get("configuration") or {}
    tpd = max(1, int(cfg.get("turnsPerDay", 24)))
    shop_iv = max(1, int(cfg.get("townShopSellInterval", 4)))
    center_iv = max(1, int(cfg.get("townCenterSellInterval", 24)))
    steps = replay["steps"]
    n = len(steps)
    if n < 2:
        return {"point": 0, "lo": 0, "hi": 0}

    cum_delta_money = 0
    cum_hire_lo = 0
    cum_hire_hi = 0
    cum_land = 0
    cum_animal = 0
    cum_seed_vis = 0
    cum_nf_rev_lo = 0
    cum_nf_rev_hi = 0
    cum_wf_net_lo = 0
    cum_wf_net_hi = 0

    obs0 = steps[0][0]["observation"]
    town = obs0.get("town") or {}

    board_size = int(cfg.get("boardSize", 10))
    shed_cap = int(cfg.get("shedCapacity", 100))

    for t in range(1, n):
        pre = steps[t - 1][0]["observation"]
        post = steps[t][0]["observation"]
        engine_step = t - 1
        town = pre.get("town") or town

        inv_pre = pre["market"]["inventory"]
        inv_post = post["market"]["inventory"]

        # Our action and shed-based committed sells
        our_act = steps[t][our_seat_idx].get("action") or {}
        our_prev_obs = steps[t - 1][our_seat_idx]["observation"]
        our_nb = _our_committed_nb_sells(
            our_prev_obs, our_act, our_seat_idx, board_size, shed_cap)
        # Legacy walk for W/F buys (still needed for net revenue)
        _sn_legacy, our_b, _ = _walk_seat_sells_buys(our_act, inv_pre)

        # Opponent money change
        m_pre = int(pre["farms"][opp]["money"])
        m_post = int(post["farms"][opp]["money"])
        cum_delta_money += m_post - m_pre

        # Town consume
        consume = _town_consume_delta(
            town.get("unlocked_shops"), engine_step, shop_iv, center_iv)

        fp = pre["farms"][opp]
        fc = post["farms"][opp]
        day_boundary = ((engine_step + 1) % tpd == 0)

        # --- Hire cost ---
        if day_boundary:
            cum_hire_hi += _hire_cost(fp["hires_today"])
        else:
            h_pre = fp["hires_today"]
            h_post = fc["hires_today"]
            for i in range(max(0, h_post - h_pre)):
                c = _hire_cost(h_pre + i)
                cum_hire_lo += c
                cum_hire_hi += c

        # --- Land cost ---
        q_pre = len(fp.get("unlocked_quadrants", ["NW"]))
        q_post = len(fc.get("unlocked_quadrants", ["NW"]))
        for i in range(max(0, q_post - q_pre)):
            idx = q_pre - 1 + i
            if idx < len(LAND_PRICES):
                cum_land += LAND_PRICES[idx]

        # --- Animal cost (new animals on tiles) ---
        for rp, rc in zip(fp["tiles"], fc["tiles"]):
            for tp, tc in zip(rp, rc):
                if (isinstance(tc, dict) and "animal" in tc
                        and not (isinstance(tp, dict) and "animal" in tp)):
                    cum_animal += ANIMALS[tc["animal"]]["cost"]

        # --- Seed cost (newly planted tiles → lower bound) ---
        for rp, rc in zip(fp["tiles"], fc["tiles"]):
            for tp, tc in zip(rp, rc):
                if (isinstance(tc, dict) and tc.get("kind") == "PLANT"
                        and not (isinstance(tp, dict)
                                 and tp.get("kind") == "PLANT")):
                    crop = tc.get("crop")
                    if crop and crop in CROPS:
                        cum_seed_vis += CROPS[crop]["seed"]

        # --- Non-floor revenue (7 non-buyable products, shed-based) ---
        for p in NON_BUYABLE:
            total_nf = (int(inv_post[p]) - int(inv_pre[p])) + consume[p]
            our_nf = our_nb.get(p, (0, 0))[0]
            opp_nf = max(0, total_nf - our_nf)
            if opp_nf > 0:
                inv_after_our = int(inv_pre[p]) + our_nf
                cum_nf_rev_lo += _nonfloor_revenue_walk(
                    p, opp_nf, inv_after_our)
                cum_nf_rev_hi += _nonfloor_revenue_walk(
                    p, opp_nf, int(inv_pre[p]))

        # --- WHEAT/FERT net revenue (legacy walk — shed sim not needed) ---
        our_sn_wf = {p: _sn_legacy.get(p, 0) for p in ("WHEAT", "FERTILIZER")}
        for p in ("WHEAT", "FERTILIZER"):
            net_opp = ((int(inv_post[p]) - int(inv_pre[p]))
                       + consume[p] + our_b[p] - our_sn_wf[p])
            if net_opp > 0:
                r_lo = _nonfloor_revenue_walk(
                    p, net_opp, int(inv_pre[p]) + our_sn_wf[p])
                r_hi = _nonfloor_revenue_walk(p, net_opp, int(inv_pre[p]))
                cum_wf_net_lo += r_lo
                cum_wf_net_hi += r_hi
            elif net_opp < 0:
                c_lo = _buy_cost_walk(p, abs(net_opp), int(inv_pre[p]))
                c_hi = _buy_cost_walk(
                    p, abs(net_opp),
                    max(0, int(inv_pre[p]) - our_b.get(p, 0)))
                cum_wf_net_lo -= c_hi
                cum_wf_net_hi -= c_lo

    # floor_units = Δmoney − nonfloor_rev − wf_net_rev + costs
    costs_lo = cum_hire_lo + cum_land + cum_animal + cum_seed_vis
    costs_hi = cum_hire_hi + cum_land + cum_animal + cum_seed_vis

    floor_lo = cum_delta_money - cum_nf_rev_hi - cum_wf_net_hi + costs_lo
    floor_hi = cum_delta_money - cum_nf_rev_lo - cum_wf_net_lo + costs_hi
    floor_point = (floor_lo + floor_hi) / 2

    return {
        "point": max(0, round(floor_point)),
        "lo": max(0, round(floor_lo)),
        "hi": max(0, round(floor_hi)),
        "delta_money": cum_delta_money,
        "nf_rev_lo": cum_nf_rev_lo,
        "nf_rev_hi": cum_nf_rev_hi,
        "wf_net_lo": cum_wf_net_lo,
        "wf_net_hi": cum_wf_net_hi,
        "costs_lo": costs_lo,
        "costs_hi": costs_hi,
    }


def _spike_ground_truth(replay, opp_seat_idx):
    """Ground truth opponent floor units from extract_metrics (reads opp actions)."""
    from harness.metrics import extract_metrics
    env_json = {
        "steps": replay["steps"],
        "configuration": replay.get("configuration", {}),
        "rewards": replay.get("rewards") or [
            replay["steps"][-1][s]["reward"]
            for s in range(2)
        ],
        "statuses": [
            replay["steps"][-1][s].get("status", "DONE")
            for s in range(2)
        ],
    }
    m = extract_metrics(env_json, opp_seat_idx)
    return {
        "floor_units": m["floor_units"],
        "floor_units_by_product": m.get("floor_units_by_product", {}),
        "sell_revenue": sum(
            int(s["price"]) for s in m.get("market_sales", [])),
    }


def spike_validate(sub="55726984", n_replays=20):
    """B2.0 gate: validate floor-units estimator on ≥n_replays ladder replays.

    Returns dict with verdict, MAE, coverage, per-episode details.
    """
    episodes = []
    n_used = 0

    for _eid, m in ladder_episodes(sub):
        if n_used >= n_replays:
            break
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        opp = 1 - seat
        replay = {
            "steps": m["steps"],
            "configuration": m["configuration"],
            "rewards": m["rewards"],
        }

        est = spike_estimate(replay, seat)
        gt = _spike_ground_truth(replay, opp)
        true_floor = gt["floor_units"]

        if true_floor > 0:
            mae_pct = abs(est["point"] - true_floor) / true_floor
        else:
            mae_pct = 0.0 if est["point"] == 0 else 1.0

        covered = est["lo"] <= true_floor <= est["hi"]

        episodes.append({
            "episode_id": m["episode_id"],
            "true_floor": true_floor,
            "est_point": est["point"],
            "est_lo": est["lo"],
            "est_hi": est["hi"],
            "mae_pct": round(mae_pct, 4),
            "covered": covered,
            "delta_money": est["delta_money"],
            "nf_rev_lo": est["nf_rev_lo"],
            "nf_rev_hi": est["nf_rev_hi"],
            "wf_net_lo": est["wf_net_lo"],
            "wf_net_hi": est["wf_net_hi"],
            "costs_lo": est["costs_lo"],
            "costs_hi": est["costs_hi"],
            "gt_by_product": gt["floor_units_by_product"],
        })
        n_used += 1

    if not episodes:
        return {"verdict": "NO_DATA", "n_used": 0}

    mae_values = sorted(ep["mae_pct"] for ep in episodes)
    median_mae = mae_values[len(mae_values) // 2]
    coverage = sum(1 for ep in episodes if ep["covered"]) / len(episodes)

    pass_mae = median_mae <= 0.15
    pass_coverage = coverage >= 0.80
    if pass_mae and pass_coverage:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"B2.0 spike {verdict}: "
                    f"median_MAE={median_mae:.3f} (≤0.15), "
                    f"coverage={coverage:.3f} (≥0.80)"),
        "submission": sub,
        "n_used": n_used,
        "median_mae": round(median_mae, 4),
        "coverage": round(coverage, 4),
        "pass_mae": pass_mae,
        "pass_coverage": pass_coverage,
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
