#!/usr/bin/env python3
"""S10 P4 / S11 B2 — per-step, leakage-safe opponent inventory instrument.

B2.0' spike (DONE, do not redo — see docs/plans/s11_instrument_completion.md §1):
for each step, compute the residual R(t) from the money-channel identity and
classify it as EXACT_ZERO / EXACT / MOD10 / AMBIGUOUS_WF.  Gate PASSED
2026-08-27 on 20 replays of 55726984: exact_rate=0.982, signal_coverage=0.571,
bracket_coverage=0.967.

B2.1-B2.5 (this file, 2026-08-27 pass):
  B2.1 — shed_ub[p](t): a per-product upper bound on the opponent's total
    stock (shed + carried inventory), built from the engine's OWN decay/
    daily-refresh functions applied to the opponent's PUBLIC tiles — never a
    reimplementation of those rules.
  B2.2 — outflow: (a) exact non-floor per-product unit counts (opp_buy≡0 for
    the seven non-WHEAT/FERTILIZER products, so ΔM identifies them exactly);
    (γ) floor-unit attribution from the public price vector.
  B2.3 — per-step, per-product output fields (opponent_total / lower_bound /
    upper_bound / uncertainty_width / floor_risk / private_loss_risk /
    classification).
  B2.4 — validation against ground truth (private.shed + private.inventories),
    kept in a SEPARATE function that never feeds the estimator.
  B2.5 — a leakage-safe dump predictor (obs + our own action only, verified by
    a PASS-replay bit-identical test) plus its kill criterion.

Leakage discipline (binds every function above _step_identity): the estimator
never reads `steps[t][1-our_seat]["action"]`. `harness.metrics._transition_events`
simulates BOTH seats jointly (opponent orders interleave with ours and can shift
our own committed sale prices by $1-2 within a step — confirmed empirically
2026-08-27), so it is used ONLY inside ground-truth/scoring functions, never
inside the estimator core. Our own committed sells are walked in isolation via
`_walk_seat_sells_buys(our_action, market_inventory_pre)` instead.

No agent/ change, no upload.

CLI:
    python analysis/s10_opponent_inventory.py spike [sub] [n]     # B2.0' (unchanged)
    python analysis/s10_opponent_inventory.py b2 [sub] [n]        # B2.1-B2.5 full report
"""
from __future__ import annotations

import copy
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
    TOWN_CENTER_PRODUCTS, _daily_refresh_animals, _daily_refresh_plants,
    _decay_plants, _hire_cost, market_price,
)
from analysis.s8_replay_io import ladder_episodes, our_seat  # noqa: E402

DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)
PREMIUM = ("MELON", "STRAWBERRY")
DUMP_UNITS = 20
DUMP_HORIZON_TURNS = 24
NON_BUYABLE = frozenset(PRODUCTS) - frozenset(("WHEAT", "FERTILIZER"))
# B2.5's predictor window/threshold — carried over unchanged from the S10 P4.3
# heuristic (72-step trailing window, half the dump threshold as trigger).
# Not tuned against the kill gate (plan rule 3).
DUMP_PREDICT_WINDOW = 72
DUMP_PREDICT_THRESHOLD = DUMP_UNITS // 2
# B2.4: a step's estimate counts as "non-identifiable" when its uncertainty
# width exceeds this many units — declared up front, per plan.
WIDTH_NONIDENTIFIABLE = 20


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


_PASS_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}


def _our_committed_sales_isolated(prev_step, cur_step, cfg, our_seat_idx):
    """Our own committed SELL units this step, computed via the REAL engine
    simulator (`harness.metrics._transition_events`) with the OPPONENT's
    action always synthetically replaced by PASS — never reads the
    opponent's actual action, so this is leakage-safe BY CONSTRUCTION (the
    PASS-replay test is then a no-op for this component by design). This is
    more accurate than a hand-walked price curve: DROP-before-SELL ordering,
    the shed cap, and same-turn HARVEST all come from the engine itself
    (plan rule 4 — call the engine, don't reimplement)."""
    from harness.metrics import _transition_events
    opp = 1 - our_seat_idx
    cur_isolated = copy.deepcopy(cur_step)
    cur_isolated[opp]["action"] = dict(_PASS_ACTION)
    tr = _transition_events(prev_step, cur_isolated, cfg)
    return tr[2][our_seat_idx]  # [{"item","price","order_index"}, ...]


def _walk_seat_sells_buys(action, market_inventory_pre, shed_pre=None, money_pre=None):
    """Single-seat committed non-floor SELL and BUY_PRODUCT UNIT COUNTS, walked
    against the engine's per-unit price curve in isolation (no opponent input —
    this is what makes it leakage-safe; the tradeoff is that a same-step,
    same-product sell by the opponent that interleaves with ours is not
    modelled, per B2.2(a)'s documented 95.4%-of-steps caveat).

    `shed_pre`/`money_pre` are OUR OWN pre-step private state (never the
    opponent's — always legitimate to read), used to cap a SELL/BUY_PRODUCT
    order at what could actually commit. Without this cap, a raw order queue
    that requests more than our own shed holds (measured 37% of steps on
    55726984) silently over-counts our own committed units, corrupting the
    opponent-side ΔM decomposition downstream — this is NOT a leakage
    concern, just an accuracy one."""
    sell_non = {p: 0 for p in PRODUCTS}
    sell_floor = {p: 0 for p in PRODUCTS}
    buy = {p: 0 for p in PRODUCTS}
    if not isinstance(action, dict):
        return sell_non, buy, sell_floor
    inv = dict(market_inventory_pre)
    shed = dict(shed_pre) if shed_pre else None
    money = money_pre
    for order in action.get("market") or []:
        if not (isinstance(order, list) and len(order) >= 3):
            continue
        op, item, qty = order[0], order[1], int(order[2])
        if op == "SELL" and item in PRODUCTS:
            if shed is not None:
                qty = min(qty, max(0, shed.get(item, 0)))
            for _ in range(qty):
                if shed is not None:
                    if shed.get(item, 0) <= 0:
                        break
                    shed[item] -= 1
                price = market_price(item, inv[item])
                if price == PRICE_FLOOR:
                    sell_floor[item] += 1
                else:
                    sell_non[item] += 1
                    inv[item] += 1
        elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
            for _ in range(qty):
                price = market_price(item, max(0, inv[item] - 1))
                if money is not None:
                    if money < price:
                        break
                    money -= price
                buy[item] += 1
                inv[item] = max(0, inv[item] - 1)
    return sell_non, buy, sell_floor


# ---------------------------------------------------------------------------
# B2.0' / shared core — R(t), classification (leakage-safe)
# ---------------------------------------------------------------------------

def _step_identity(prev_step, cur_step, cfg, our_seat_idx):
    """The one implementation of the money-channel identity + classification.
    Reads only `obs` (both seats' PUBLIC fields) and our own action
    (cur_step[our_seat_idx]['action']) — never the opponent's action."""
    opp = 1 - our_seat_idx
    pre = prev_step[0]["observation"]
    post = cur_step[0]["observation"]

    shop_iv = max(1, int(cfg.get("townShopSellInterval", 4)))
    center_iv = max(1, int(cfg.get("townCenterSellInterval", 24)))
    turns_per_day = max(1, int(cfg.get("turnsPerDay", 24)))
    shed_cap = int(cfg.get("shedCapacity", 100))

    engine_step = int(pre.get("step", 0))
    is_day_boundary = (engine_step + 1) % turns_per_day == 0

    our_action = cur_step[our_seat_idx].get("action") or {}
    inv_pre = pre["market"]["inventory"]
    inv_post = post["market"]["inventory"]
    town = pre.get("town") or {}
    consume = _town_consume_delta(town.get("unlocked_shops"), engine_step, shop_iv, center_iv)

    our_money_pre = int(pre["farms"][our_seat_idx]["money"])
    # BUY_PRODUCT count: money-capped walk only (BUY_PRODUCT commits aren't
    # exposed by _transition_events's return tuple, only SELLs are).
    _walk_sell_non, our_buy, _walk_sell_floor = _walk_seat_sells_buys(
        our_action, inv_pre, money_pre=our_money_pre)
    # SELL count + exact revenue: the real engine simulator, opponent PASSed.
    our_sales_isolated = _our_committed_sales_isolated(
        prev_step, cur_step, cfg, our_seat_idx)
    our_nf = {p: 0 for p in PRODUCTS}
    our_rev = {p: 0 for p in PRODUCTS}
    for sale in our_sales_isolated:
        if sale["price"] > PRICE_FLOOR:
            our_nf[sale["item"]] += 1
            our_rev[sale["item"]] += sale["price"]

    dm_money = int(post["farms"][opp]["money"]) - int(pre["farms"][opp]["money"])

    hands_pre = pre["farms"][opp].get("hands") or []
    hands_post = post["farms"][opp].get("hands") or []
    n_new_hands = max(0, len(hands_post) - len(hands_pre))
    hires_pre = int(pre["farms"][opp].get("hires_today", 0))
    hire = sum(_hire_cost(hires_pre + k) for k in range(n_new_hands))

    quads_pre = pre["farms"][opp].get("unlocked_quadrants") or ["NW"]
    quads_post = post["farms"][opp].get("unlocked_quadrants") or ["NW"]
    n_new_q = max(0, len(quads_post) - len(quads_pre))
    land = 0
    for i in range(n_new_q):
        idx = len(quads_pre) - 1 + i
        if idx < len(LAND_PRICES):
            land += LAND_PRICES[idx]

    products = {}
    opp_nf_revenue = 0
    wf_activity = False
    for p in PRODUCTS:
        dm = int(inv_post[p]) - int(inv_pre[p])
        our_nf_p = our_nf[p]
        our_buy_p = our_buy[p]
        our_rev_p = our_rev[p]

        if p in NON_BUYABLE:
            total_nf = dm + consume[p]
            opp_nf_p = total_nf - our_nf_p
            products[p] = {"opp_sell_nonfloor": opp_nf_p, "opp_net_wf": None}
        else:
            net_opp_p = dm + consume[p] - our_nf_p + our_buy_p
            if net_opp_p < 0:
                wf_activity = True
            total_nf = dm + consume[p] + our_buy_p
            products[p] = {"opp_sell_nonfloor": None, "opp_net_wf": net_opp_p}

        if total_nf > 0 and not wf_activity:
            total_rev = _nonfloor_revenue_walk(p, total_nf, int(inv_pre[p]))
            opp_nf_revenue += total_rev - our_rev_p

    R = dm_money + hire + land - opp_nf_revenue

    if wf_activity:
        cls = "AMBIGUOUS_WF"
        bracket_lo, bracket_hi = 0, shed_cap
    elif R == 0:
        cls = "EXACT_ZERO"
        bracket_lo = bracket_hi = 0
    elif 0 < R < 10:
        cls = "EXACT"
        bracket_lo = bracket_hi = R
    else:
        cls = "MOD10"
        bracket_lo = R % 10
        bracket_hi = shed_cap

    floor_est = R if cls in ("EXACT_ZERO", "EXACT") else None

    return {
        "engine_step": engine_step,
        "is_day_boundary": is_day_boundary,
        "R": R,
        "classification": cls,
        "bracket_lo": bracket_lo,
        "bracket_hi": bracket_hi,
        "floor_units_est": floor_est,
        "products": products,
        "prices_pre": dict(pre["market"]["prices"]),
        "wf_activity": wf_activity,
    }


def spike_per_step(replay, our_seat_idx):
    """B2.0' (DONE): per-step opponent floor-unit estimation with classification.
    Thin wrapper over `_step_identity` (shared core) + ground truth for the
    already-shipped spike gate — output shape unchanged from the shipped version."""
    from harness.metrics import _transition_events

    opp = 1 - our_seat_idx
    cfg = replay.get("configuration") or {}
    steps = replay["steps"]
    n = len(steps)
    if n < 2:
        return []

    results = []
    for t in range(1, n):
        prev_step = steps[t - 1]
        cur_step = steps[t]
        ident = _step_identity(prev_step, cur_step, cfg, our_seat_idx)

        # Ground truth only (ok to read both actions here — not the estimator).
        tr = _transition_events(prev_step, cur_step, cfg)
        gt_floor = sum(1 for sale in tr[2][opp] if sale["price"] <= PRICE_FLOOR)

        results.append({
            "step": t,
            "R": ident["R"],
            "classification": ident["classification"],
            "floor_units_est": ident["floor_units_est"],
            "bracket_lo": ident["bracket_lo"],
            "bracket_hi": ident["bracket_hi"],
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
# B2.1 — shed upper/lower bounds from the opponent's PUBLIC tiles
# ---------------------------------------------------------------------------

def _tile_key(tile):
    if not isinstance(tile, dict):
        return None
    if tile.get("kind") == "PLANT":
        return ("PLANT", tile.get("crop"), tile.get("planted_day"))
    if "animal" in tile:
        return ("ANIMAL", tile.get("animal"), tile.get("placed_day"))
    return None


def _tile_product(tile):
    if tile.get("kind") == "PLANT":
        return tile.get("crop")
    return ANIMALS[tile["animal"]]["product"]


def _apply_observed_water_bonus(tile, real_tile, pre_day):
    """WATER is the one unit action B2.1 cannot treat as absent: it is public
    (watered_today is a public tile field) and, for a NON-ongoing crop, adds a
    yield bonus with no corresponding harvest — so a plain "zero unit actions"
    counterfactual misreads a watered-not-harvested tile as a harvest (measured
    2026-08-27: MELON, watered_today False->True, yield_units 1->2, no harvest
    at all). Since the transition is exactly observable and the bonus formula
    is a public-data function (engine._apply_unit_action's WATER branch, for
    non-ongoing crops only — ongoing crops get no yield bonus from WATER),
    replicate it narrowly here rather than leaving it as a blind spot; this is
    the one unit-action rule not covered by the four named engine functions
    (plan rule 4 names those four; there is no separate helper for this one
    branch to call instead). Mutates `tile` in place."""
    if not (isinstance(tile, dict) and tile.get("kind") == "PLANT"):
        return
    if not (isinstance(real_tile, dict) and real_tile.get("kind") == "PLANT"):
        return
    if tile.get("watered_today") or not real_tile.get("watered_today"):
        return
    cd = CROPS.get(tile.get("crop"))
    if not cd or cd["ongoing"]:
        return
    age_days = pre_day - tile.get("planted_day", pre_day)
    window_start = (cd["max_yield_day"] + 1) // 2
    if not (window_start <= age_days <= cd["max_yield_day"]):
        return
    bonus = 2 if tile.get("fertilized_until_day", -1) >= pre_day else 1
    tile["watered_today"] = True
    tile["yield_units"] = min(cd["max_yield"], tile.get("yield_units", 0) + bonus)


def _counterfactual_tiles(pre_tiles, real_post_tiles, engine_step, pre_day,
                           turns_per_day, is_day_boundary):
    """What the opponent's tiles would look like with a possible WATER but
    ZERO harvest/other unit actions this step — natural decay (+ daily
    refresh at a day boundary) on top of the observed WATER bonus (see
    `_apply_observed_water_bonus`). Calls the engine's own `_decay_plants` /
    `_daily_refresh_plants` / `_daily_refresh_animals` for everything else —
    never reimplements them (plan rule 4). WATER, matching engine turn order,
    is applied before decay/refresh."""
    farm = {"tiles": copy.deepcopy(pre_tiles)}
    board = len(pre_tiles)
    for y in range(board):
        for x in range(board):
            _apply_observed_water_bonus(farm["tiles"][y][x], real_post_tiles[y][x], pre_day)
    _decay_plants(farm, engine_step)
    if is_day_boundary:
        _daily_refresh_plants(farm, pre_day, turns_per_day)
        _daily_refresh_animals(farm, pre_day)
    return farm["tiles"]


def _opp_harvest_inflow(pre_tiles, real_post_tiles, sim_tiles):
    """Per-product harvest inflow, HI and LO.

    HARVEST always runs before decay/refresh in engine turn order (S11 plan
    §B2.1), and it always zeroes the tile's yield_units. So `sim_tiles` (decay
    + refresh applied to the UNTOUCHED pre-step yield — the "nothing happened"
    counterfactual) is the exact trajectory the tile follows when no harvest
    occurs; whenever the REAL observed tile — same identity — ends up at a
    DIFFERENT yield than the sim, a harvest must have happened, and (since
    HARVEST always fires first, before either trajectory's decay/refresh can
    touch the tile) the amount taken is always exactly the PRE-step yield —
    never `sim_yield - real_yield`, which under-counts whenever growth added
    by a day-boundary refresh AFTER a hypothetical harvest gets clamped to
    max_yield differently in the two trajectories (measured 2026-08-27: this
    is common, not a rare edge case, since a well-run ongoing crop is often
    harvested right at its yield cap).

    When identity breaks (tile removed/dug/replanted, or decays to WEED for
    real while the sim also would have — genuinely nothing collected) the
    causal story is ambiguous; HI still attributes the pre-step yield (safe
    over-count for an upper bound), LO does not (safe under-count for a lower
    bound) unless BOTH trajectories keep the identity and merely disagree on
    yield, which is the one unambiguous case."""
    harvest_hi = {p: 0 for p in PRODUCTS}
    harvest_lo = {p: 0 for p in PRODUCTS}
    board = len(pre_tiles)
    for y in range(board):
        for x in range(board):
            pre_t = pre_tiles[y][x]
            key = _tile_key(pre_t)
            pre_yield = pre_t.get("yield_units", 0) if key else 0
            if key is None or pre_yield <= 0:
                continue
            product = _tile_product(pre_t)
            sim_t = sim_tiles[y][x]
            real_t = real_post_tiles[y][x]
            sim_key = _tile_key(sim_t)
            real_key = _tile_key(real_t)

            if real_key == key and sim_key == key:
                if real_t.get("yield_units", 0) == sim_t.get("yield_units", 0):
                    continue  # matches the natural no-harvest trajectory exactly
                harvest_hi[product] += pre_yield
                harvest_lo[product] += pre_yield
            else:
                # identity broke on at least one side -> ambiguous; HI only.
                harvest_hi[product] += pre_yield
    return harvest_hi, harvest_lo


def _opp_flow_flags(pre_tiles, real_post_tiles, is_day_boundary):
    """FEED outflow (-1 WHEAT), FERTILIZE outflow (-1 FERTILIZER, via
    fertilized_until_day advancing), COLLECT_FERTILIZER inflow (+1 FERTILIZER,
    HI only — see below).

    All three are transient public flags reset unconditionally by the
    day-boundary refresh. For the two OUTFLOWs (feed_out, fertilize_out) that
    makes the day-boundary step a safe blind spot: attributing 0 only makes
    the upper bound more conservative, never violates it. For the INFLOW
    (fert_in) attributing 0 is UNSAFE — it would under-count stock and could
    push the upper bound below the truth (measured 2026-08-27: real
    violation). So at a day boundary we instead return the upper bound on
    that turn's possible collections: one per animal tile that started the
    turn with fertilizer_available=True (a tile can collect at most once
    before the flag resets)."""
    feed_out = 0
    fertilize_out = 0
    fert_in_hi = 0
    fert_in_lo = 0
    if is_day_boundary:
        board = len(pre_tiles)
        for y in range(board):
            for x in range(board):
                pre_t = pre_tiles[y][x]
                if (isinstance(pre_t, dict) and "animal" in pre_t
                        and pre_t.get("fertilizer_available")):
                    fert_in_hi += 1
        return feed_out, fertilize_out, fert_in_hi, fert_in_lo
    board = len(pre_tiles)
    for y in range(board):
        for x in range(board):
            pre_t = pre_tiles[y][x]
            real_t = real_post_tiles[y][x]
            if not (isinstance(pre_t, dict) and isinstance(real_t, dict)):
                continue
            if ("animal" in pre_t and "animal" in real_t
                    and pre_t.get("animal") == real_t.get("animal")
                    and pre_t.get("placed_day") == real_t.get("placed_day")):
                if not pre_t.get("fed_today") and real_t.get("fed_today"):
                    feed_out += 1
                if pre_t.get("fertilizer_available") and not real_t.get("fertilizer_available"):
                    fert_in_hi += 1
                    fert_in_lo += 1
            elif (pre_t.get("kind") == "PLANT" and real_t.get("kind") == "PLANT"
                    and pre_t.get("crop") == real_t.get("crop")
                    and pre_t.get("planted_day") == real_t.get("planted_day")):
                if real_t.get("fertilized_until_day", -1) > pre_t.get("fertilized_until_day", -1):
                    fertilize_out += 1
    return feed_out, fertilize_out, fert_in_hi, fert_in_lo


# ---------------------------------------------------------------------------
# B2.1-B2.3 — the combined leakage-safe per-step, per-product ledger
# ---------------------------------------------------------------------------

def per_step_ledger(replay, our_seat_idx):
    """B2.1-B2.3: leakage-safe per-step, per-product opponent inventory ledger.
    Reads only `obs` (both seats' public fields) and our own action — verified
    by `tests/test_s11_b25_leakage.py`'s PASS-replay bit-identical check.

    Returns a list of per-step dicts:
      step, engine_step, classification, R, day_boundary,
      floor_candidates (products priced at PRICE_FLOOR this step),
      floor_identity_error (bool — nonzero residual with no floor candidate),
      private_loss_risk (upper bound on this step's shed-overflow burn, 0
        except at day boundaries),
      products: {product: {opp_sell_nonfloor, opp_net_wf, floor_lower,
        floor_upper, lower_bound, upper_bound, uncertainty_width,
        opponent_total, floor_risk}}
    """
    opp = 1 - our_seat_idx
    cfg = replay.get("configuration") or {}
    steps = replay["steps"]
    n = len(steps)
    if n < 2:
        return []

    turns_per_day = max(1, int(cfg.get("turnsPerDay", 24)))
    shed_cap = int(cfg.get("shedCapacity", 100))

    raw_cum_hi = {p: 0 for p in PRODUCTS}
    raw_cum_lo = {p: 0 for p in PRODUCTS}

    results = []
    for t in range(1, n):
        prev_step = steps[t - 1]
        cur_step = steps[t]
        pre = prev_step[0]["observation"]
        post = cur_step[0]["observation"]

        ident = _step_identity(prev_step, cur_step, cfg, our_seat_idx)
        engine_step = ident["engine_step"]
        is_day_boundary = ident["is_day_boundary"]
        pre_day = int(pre.get("day", 0))

        pre_tiles = pre["farms"][opp]["tiles"]
        real_post_tiles = post["farms"][opp]["tiles"]
        sim_tiles = _counterfactual_tiles(
            pre_tiles, real_post_tiles, engine_step, pre_day, turns_per_day, is_day_boundary)
        harvest_hi, harvest_lo = _opp_harvest_inflow(pre_tiles, real_post_tiles, sim_tiles)
        feed_out, fertilize_out, fert_in_hi, fert_in_lo = _opp_flow_flags(
            pre_tiles, real_post_tiles, is_day_boundary)

        # --- B2.2(γ): floor attribution ---
        prices = ident["prices_pre"]
        C_t = [p for p in PRODUCTS if int(prices.get(p, 0)) == PRICE_FLOOR]
        cls = ident["classification"]
        if cls in ("EXACT_ZERO", "EXACT"):
            r_lo = r_hi = ident["floor_units_est"]
        else:
            r_lo, r_hi = ident["bracket_lo"], ident["bracket_hi"]
        floor_identity_error = bool(len(C_t) == 0 and (r_lo != 0 or r_hi != 0))

        floor_attr = {}
        for p in PRODUCTS:
            if p not in C_t:
                floor_attr[p] = (0, 0)
            elif len(C_t) == 1:
                floor_attr[p] = (r_lo, r_hi)
            else:
                floor_attr[p] = (0, r_hi)

        # --- B2.1: shed bounds, per product ---
        products_out = {}
        for p in PRODUCTS:
            inflow_hi = harvest_hi.get(p, 0)
            inflow_lo = harvest_lo.get(p, 0)
            if p == "FERTILIZER":
                inflow_hi += fert_in_hi
                inflow_lo += fert_in_lo

            prod = ident["products"][p]
            if p in NON_BUYABLE:
                net_delta = -prod["opp_sell_nonfloor"]
            else:
                net_delta = -prod["opp_net_wf"]

            floor_lo, floor_hi = floor_attr[p]
            outflow_extra = 0
            if p == "WHEAT":
                outflow_extra = feed_out
            elif p == "FERTILIZER":
                outflow_extra = fertilize_out

            # Upper bound never subtracts a floor amount, even the "guaranteed
            # minimum" floor_lo: floor_lo is only a valid lower bound on units
            # sold IF the step's MOD10/EXACT classification is itself correct,
            # and the B2.0' gate measures that at ~92% (bracket_coverage),
            # not 100% — subtracting on the other ~8% pushes the running sum
            # below true stock and violates the upper-bound invariant (measured
            # 2026-08-27: WOOL truth=4 vs a false floor_lo=6 charge). The lower
            # bound has no such risk: over-subtracting floor_hi only makes it
            # more conservative, never unsafe.
            raw_cum_hi[p] += inflow_hi + net_delta - outflow_extra
            raw_cum_lo[p] += inflow_lo + net_delta - floor_hi - outflow_extra

            # NOT clamped to shed_cap: shed_cap bounds the SHED total across
            # ALL products (_drop_inventories_to_shed), not any one product's
            # total private stock — farmer-held (not-yet-dropped) inventory is
            # uncapped between drops, so ground truth (_private_total = shed +
            # inventories) can exceed 100 for a single product intra-day
            # (measured 2026-08-27: WHEAT truth=105 mid-day). private_loss_risk
            # captures the shed-specific overflow-burn separately.
            upper_bound = max(0, raw_cum_hi[p])
            lower_bound = max(0, raw_cum_lo[p])
            if lower_bound > upper_bound:
                lower_bound = upper_bound
            width = upper_bound - lower_bound
            opponent_total = upper_bound if width == 0 else None

            products_out[p] = {
                "opp_sell_nonfloor": prod["opp_sell_nonfloor"],
                "opp_net_wf": prod["opp_net_wf"],
                "floor_lower": floor_lo,
                "floor_upper": floor_hi,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "uncertainty_width": width,
                "opponent_total": opponent_total,
                "floor_risk": p in C_t,
            }

        total_upper_raw = sum(max(0, raw_cum_hi[p]) for p in PRODUCTS)
        private_loss_risk = max(0, total_upper_raw - shed_cap) if is_day_boundary else 0

        results.append({
            "step": t,
            "engine_step": engine_step,
            "classification": cls,
            "R": ident["R"],
            "day_boundary": is_day_boundary,
            "floor_candidates": C_t,
            "floor_identity_error": floor_identity_error,
            "private_loss_risk": private_loss_risk,
            "products": products_out,
        })

    return results


# ---------------------------------------------------------------------------
# B2.4 — ground-truth validation (separate function, never fed to the estimator)
# ---------------------------------------------------------------------------

def _ground_truth_step(cur_step, opp_seat, item):
    """Ground truth ONLY: opponent's true post-step private stock. Reads
    `steps[t][opp_seat]['observation']['private']` — legitimate here because
    this is the scoring function, not the estimator (plan §B2.4/§B2.5)."""
    private = (cur_step[opp_seat].get("observation") or {}).get("private")
    return _private_total(private, item)


def validate_b21_b24(sub="55726984", n_replays=20, width_threshold=WIDTH_NONIDENTIFIABLE):
    """B2.1 acceptance (shed_ub always ≥ ground truth) + B2.4 (MAE / %
    non-identifiable / coverage, all per-step, never cumulative per-episode)."""
    n_used = 0
    upper_violations = []
    lower_violations = []
    mae_sum = defaultdict(float)
    mae_n = defaultdict(int)
    covered = defaultdict(int)
    coverage_n = defaultdict(int)
    nonident = defaultdict(int)
    mod10_widths = []
    mod10_over_shed_cap = None

    for eid, m in ladder_episodes(sub):
        if n_used >= n_replays:
            break
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        opp = 1 - seat
        shed_cap = int((m["configuration"] or {}).get("shedCapacity", 100))
        mod10_over_shed_cap = shed_cap
        replay = {"steps": m["steps"], "configuration": m["configuration"]}
        ledger = per_step_ledger(replay, seat)
        if not ledger:
            continue
        steps = replay["steps"]

        for rec in ledger:
            t = rec["step"]
            cur_step = steps[t]
            if rec["classification"] == "MOD10":
                mod10_widths.append(rec["products"])  # unused per-field; width computed below

            for p in PRODUCTS:
                truth = _ground_truth_step(cur_step, opp, p)
                po = rec["products"][p]
                lo, hi = po["lower_bound"], po["upper_bound"]
                if truth > hi:
                    upper_violations.append(
                        {"episode_id": eid, "step": t, "product": p,
                         "upper_bound": hi, "truth": truth})
                if truth < lo:
                    lower_violations.append(
                        {"episode_id": eid, "step": t, "product": p,
                         "lower_bound": lo, "truth": truth})

                coverage_n[p] += 1
                if lo <= truth <= hi:
                    covered[p] += 1
                if po["uncertainty_width"] > width_threshold:
                    nonident[p] += 1
                if po["opponent_total"] is not None:
                    mae_sum[p] += abs(po["opponent_total"] - truth)
                    mae_n[p] += 1
        n_used += 1
        print(f"  [{n_used}/{n_replays}] ep {eid}: "
              f"{len(ledger)} steps, upper_violations={len(upper_violations)}")

    if n_used == 0:
        return {"verdict": "NO_DATA", "n_used": 0}

    mae = {p: (round(mae_sum[p] / mae_n[p], 3) if mae_n[p] else None) for p in PRODUCTS}
    pct_nonident = {p: (round(nonident[p] / coverage_n[p], 4) if coverage_n[p] else None)
                     for p in PRODUCTS}
    coverage = {p: (round(covered[p] / coverage_n[p], 4) if coverage_n[p] else None)
                for p in PRODUCTS}
    total_covered = sum(covered.values())
    total_n = sum(coverage_n.values())
    overall_coverage = total_covered / total_n if total_n else None

    b21_pass = len(upper_violations) == 0
    b24_dead = overall_coverage is not None and overall_coverage < 0.80

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "submission": sub,
        "n_used": n_used,
        "b21": {
            "verdict": ("PASS: shed_ub never violated"
                        if b21_pass else
                        f"FAIL: {len(upper_violations)} upper-bound violations (bug)"),
            "upper_bound_violations": upper_violations[:20],
            "n_upper_bound_violations": len(upper_violations),
            "n_lower_bound_violations": len(lower_violations),
        },
        "b24": {
            "verdict": ("STOPPED_KILL_CRITERION_HIT: coverage < 0.80"
                        if b24_dead else "PASS"),
            "overall_coverage": round(overall_coverage, 4) if overall_coverage is not None else None,
            "coverage_by_product": coverage,
            "mae_by_product": mae,
            "pct_nonidentifiable_by_product": pct_nonident,
            "width_threshold": width_threshold,
            "hit_kill_criterion": b24_dead,
        },
    }


# ---------------------------------------------------------------------------
# B2.5 — leakage-safe dump predictor + kill criterion
# ---------------------------------------------------------------------------

def predict_dump_events(ledger, product, window=DUMP_PREDICT_WINDOW,
                         threshold=DUMP_PREDICT_THRESHOLD):
    """Leakage-safe predictor: at each step, predicts a dump (opponent sells
    ≥DUMP_UNITS non-floor units of `product` within the next DUMP_HORIZON_TURNS
    turns) from the TRAILING `window`-step sum of the exact opp_sell_nonfloor
    signal (B2.2(a) — exact for MELON/STRAWBERRY since opp_buy≡0 there).
    Takes only `ledger` — itself computed from obs + our own action only."""
    n = len(ledger)
    series = [rec["products"][product]["opp_sell_nonfloor"] or 0 for rec in ledger]
    preds = [False] * n
    for i in range(n):
        lo = max(0, i - window + 1)
        trailing = sum(series[lo:i + 1])
        preds[i] = trailing >= threshold
    return preds


def _dump_events(replay, opp_seat, product, unit_threshold=DUMP_UNITS,
                 horizon=DUMP_HORIZON_TURNS):
    """Ground-truth binary label for each step: does opponent SELL ≥ unit_threshold
    units of `product` in the next `horizon` steps? Reads opp raw actions —
    the separate scoring function (B2.5), never fed to the predictor."""
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


def evaluate_dump_predictor(sub="55726984", n_replays=20,
                             window=DUMP_PREDICT_WINDOW,
                             threshold=DUMP_PREDICT_THRESHOLD):
    """B2.5 kill criterion: precision ≥0.70 on MELON AND STRAWBERRY -> PROCEED
    (policy design moves to S12); else -> the idea dies, permanently."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    n_used = 0
    n_steps = 0

    for eid, m in ladder_episodes(sub):
        if n_used >= n_replays:
            break
        seat = our_seat(m["teams"])
        if seat is None:
            continue
        opp = 1 - seat
        replay = {"steps": m["steps"], "configuration": m["configuration"]}
        ledger = per_step_ledger(replay, seat)
        if not ledger:
            continue
        n_steps += len(ledger)

        for p in PREMIUM:
            preds = predict_dump_events(ledger, p, window, threshold)
            gt = _dump_events(replay, opp, p)
            for rec, pred in zip(ledger, preds):
                actual = gt[rec["step"]]
                if pred and actual:
                    tp[p] += 1
                elif pred and not actual:
                    fp[p] += 1
                elif not pred and actual:
                    fn[p] += 1
        n_used += 1

    precision = {}
    recall = {}
    for p in PREMIUM:
        denom = tp[p] + fp[p]
        precision[p] = round(tp[p] / denom, 4) if denom else None
        rdenom = tp[p] + fn[p]
        recall[p] = round(tp[p] / rdenom, 4) if rdenom else None

    dead = any((precision[p] is not None and precision[p] < 0.70) for p in PREMIUM)
    verdict = "STOPPED_KILL_CRITERION_HIT" if dead else "PROCEED"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"B2.5 {verdict}: precision MELON={precision['MELON']}, "
                    f"STRAWBERRY={precision['STRAWBERRY']} (target ≥0.70). "
                    f"Path run: NON-FLOOR channel only (B2.2(a) exact signal); "
                    f"floor channel not a precondition."),
        "submission": sub,
        "n_replays_used": n_used,
        "n_step_boundaries": n_steps,
        "dump_definition": {"unit_threshold": DUMP_UNITS, "horizon_turns": DUMP_HORIZON_TURNS},
        "predictor_params": {"window": window, "threshold": threshold,
                              "signal": "opp_sell_nonfloor (exact, leakage-safe)"},
        "precision": precision,
        "recall": recall,
        "confusion": {p: {"tp": tp[p], "fp": fp[p], "fn": fn[p]} for p in PREMIUM},
        "kill_criterion": "precision < 0.70 for MELON or STRAWBERRY",
        "hit_kill_criterion": dead,
    }


# ---------------------------------------------------------------------------
# B2 full report
# ---------------------------------------------------------------------------

def b2_full_report(sub="55726984", n_replays=20):
    b21_b24 = validate_b21_b24(sub, n_replays)
    b25 = evaluate_dump_predictor(sub, n_replays)

    b21_pass = b21_b24.get("b21", {}).get("n_upper_bound_violations", 1) == 0
    b24_dead = b21_b24.get("b24", {}).get("hit_kill_criterion", True)
    b25_dead = b25.get("hit_kill_criterion", True)

    if b24_dead:
        overall = "STOPPED_KILL_CRITERION_HIT (B2.4: coverage < 0.80 — estimator is WRONG)"
    elif b25_dead:
        overall = "STOPPED_KILL_CRITERION_HIT (B2.5: dump-predictor precision < 0.70)"
    elif not b21_pass:
        overall = "FAIL (B2.1: shed_ub upper-bound invariant violated — bug)"
    else:
        overall = "PROCEED (B2.1-B2.5 all pass — policy design moves to S12)"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": f"B2 (B2.1-B2.5) {overall}",
        "submission": sub,
        "n_replays": n_replays,
        "b21": b21_b24["b21"],
        "b24": b21_b24["b24"],
        "b25": b25,
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

    if cmd == "b2":
        sub = args[1] if len(args) > 1 else "55726984"
        n = int(args[2]) if len(args) > 2 else 20
        out = b2_full_report(sub, n)
        p = DERIVED / "s10_opponent_inventory.json"
        p.write_text(json.dumps(out, indent=2))
        print(f"wrote {p}")
        print(out["verdict"])
        return

    print("usage: python analysis/s10_opponent_inventory.py "
          "{spike|b2} [sub=55726984] [n=20]")
    sys.exit(2)


if __name__ == "__main__":
    main()
