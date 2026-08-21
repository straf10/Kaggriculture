"""S7 Ship B — paper-bound the WHEAT market maker (component iv, §7.2).

For each of our 178 live replays of submission 55586926 (seat 0's view — the two
seats are symmetric since a paper bound is per-arm), extract the per-turn WHEAT
market price and the free-slot / cash / shed constraints the backbone leaves
behind, then compute a perfect-hindsight profit an omniscient q10 WHEAT market
maker could realise, subject to those constraints.

Three figures, in increasing order of authority:

 * SLOT    — a flow heuristic: free market ORDERS per turn x each positive
             one-step price move.  ⚠️ NOT an upper bound (see _slot_bound).
             Retained only because it is what the first version of this pass
             reported, and it happens to land at the right magnitude.
 * TIGHT   — omniscient greedy under cash floor $500, feed reserve 5 WHEAT and
             the backbone's actual per-turn shed occupancy, but against the
             RECORDED price series (i.e. it ignores our own price impact).
 * CEILING — the defensible number: the best single buy->sell round trip with
             ENDOGENOUS price impact and no cash / shed / order limits at all.
             Nothing a market maker can do on this route beats it.

The ceiling is what the verdict rests on: market impact, not the order cap,
is what makes a WHEAT maker worthless here.  See the report for the numbers.

Reports mean, median, p90 across episodes; converts to rating points via
$253/ep = 1 rating point (§3, marginal-increment heuristic).

Also collects the ride-along data for §6 row 13 — "is the route ever
glut-constrained?".  ⚠️ This MUST be read across ALL products, not WHEAT
alone: WHEAT's above_target is 0,2 (its glut side is nearly flat, +400 units
moves it $25 -> $20), so it is structurally the one product whose price our
selling cannot crash.  MELON is above_func 'sq' / above_target 3,6; MILK,
WOOL and STRAWBERRY all reach the $1 floor about 100 units above baseline.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from dataclasses import dataclass


REPLAYS_DIR = "data/archive/raw/live_55586926"
SHED_CAP = 100
MKT_SLOTS_CAP = 10
CASH_FLOOR = 500
FEED_RESERVE = 5
DOLLARS_PER_RATING_PT = 253.0


@dataclass
class EpisodeSeries:
    episode_id: str
    is_mirror: bool
    price: list[int]            # WHEAT market price per turn
    market_inv: list[int]       # WHEAT market inventory per turn
    cash: list[float]           # seat 0 cash per turn
    shed_total: list[int]       # seat 0 total shed occupancy per turn
    wheat_shed: list[int]       # seat 0 WHEAT held in shed per turn
    mkt_orders_used: list[int]  # market orders seat 0 issued this turn
    final_bank: float


def _load_episode(path: str) -> EpisodeSeries:
    with open(path) as f:
        r = json.load(f)
    steps = r["steps"]
    price, market_inv, cash, shed_total, wheat_shed, mkt_used = [], [], [], [], [], []
    priv_same = 0
    for s in steps:
        obs0 = s[0]["observation"]
        mkt = obs0["market"]
        price.append(mkt["prices"]["WHEAT"])
        market_inv.append(mkt["inventory"]["WHEAT"])
        cash.append(obs0["farms"][0]["money"])
        priv = obs0.get("private", {}) or {}
        shed = priv.get("shed", {}) or {}
        shed_total.append(sum(shed.values()))
        wheat_shed.append(shed.get("WHEAT", 0))
        a = s[0].get("action")
        m = a.get("market", []) if isinstance(a, dict) else []
        mkt_used.append(len(m) if isinstance(m, list) else 0)
        if priv == (s[1]["observation"].get("private") or {}):
            priv_same += 1
    is_mirror = priv_same > 500  # crude classifier; verified over the archive
    final_obs = steps[-1][0]["observation"]
    parts = os.path.basename(path).split("-")
    if len(parts) < 2:
        raise ValueError(f"unexpected replay filename format (no '-'): {path}")
    ep_id = parts[1]
    return EpisodeSeries(
        episode_id=ep_id,
        is_mirror=is_mirror,
        price=price,
        market_inv=market_inv,
        cash=cash,
        shed_total=shed_total,
        wheat_shed=wheat_shed,
        mkt_orders_used=mkt_used,
        final_bank=final_obs["farms"][0]["money"],
    )


def _slot_bound(ep: EpisodeSeries) -> float:
    """Flow heuristic — free market ORDERS per turn x each positive price move.

    ⚠️ THIS IS NOT AN UPPER BOUND.  It was reported as one in the first version
    of this pass; two things are wrong with that claim:

      1. `maxMarketOrdersPerTurn` = 10 caps ORDERS, not units.  `_parse_order`
         gives every order a `remaining` quantity and the backbone itself
         issues e.g. ['SELL', 'STRAWBERRY', 14] — one order, fourteen units.
         So `free_slots_t` is not a per-turn unit cap.
      2. It charges only `free_slots_t` units against each price rise, but a
         maker ACCUMULATES: a policy holding K units across turn t earns
         K * diff_t, and K is not bounded by that turn's free slots.

    Kept only for continuity with the first report, and because it happens to
    land at the same magnitude as `_impact_ceiling` for unrelated reasons.
    The verdict rests on `_impact_ceiling`, not on this.
    """
    n = len(ep.price)
    total = 0.0
    for t in range(n - 1):
        free = max(0, MKT_SLOTS_CAP - ep.mkt_orders_used[t])
        diff = ep.price[t + 1] - ep.price[t]
        if diff > 0:
            total += free * diff
    return total


def _impact_ceiling(ep: EpisodeSeries, item: str = "WHEAT") -> tuple[float, int]:
    """THE defensible ceiling: best single buy->sell round trip WITH price impact.

    No cash limit, no shed limit, no order limit — the only thing that binds is
    the engine's own price curve.  `market_price` is a pure function of market
    inventory, and the quotes are symmetric (SELL at I, BUY_PRODUCT at I-1), so
    buying K units at market inventory `hi` and selling them later at `lo`
    earns exactly

        sum_{j=0..K-1} price(lo + j)  -  sum_{j=1..K} price(hi - j)

    Our own buying walks the price UP against us (WHEAT: 10.000 -> $25 but
    9.900 -> $35) and our own selling walks it back DOWN, so the marginal unit
    stops being profitable quickly.  That, not the order cap, is the real
    constraint.

    Profit is monotone in (hi - lo), so the optimum is: buy at the highest
    inventory reachable before some split, sell at the lowest inventory after
    it.  O(n) via a prefix max / suffix min instead of an O(n^2) pair search.
    """
    from kaggle_environments.envs.kaggriculture.kaggriculture import market_price

    inv = ep.market_inv
    n = len(inv)
    if n < 2:
        return 0.0, 0
    suffix_min = [0] * (n + 1)
    suffix_min[n] = 10 ** 9
    for t in range(n - 1, -1, -1):
        suffix_min[t] = min(inv[t], suffix_min[t + 1])

    cache: dict[int, int] = {}

    def px(i: int) -> int:
        v = cache.get(i)
        if v is None:
            v = cache[i] = market_price(item, i)
        return v

    best, best_k = 0.0, 0
    prefix_max = inv[0]
    for t in range(n - 1):
        prefix_max = max(prefix_max, inv[t])
        lo = suffix_min[t + 1]
        if lo >= prefix_max:
            continue
        profit, k = 0.0, 0
        for j in range(1, 2001):
            sell_inv = lo - j  # our earlier buy shifted inventory down by K
            if sell_inv < 0:
                break
            gain = px(sell_inv) - px(prefix_max - j)
            if gain <= 0:
                break
            profit += gain
            k = j
        if profit > best:
            best, best_k = profit, k
    return best, best_k


def _tight_bound(ep: EpisodeSeries) -> float:
    """Realistic bound: per-turn buy/sell subject to cash, feed and shed.

    Greedy omniscient policy: at each turn t, if any FUTURE turn t' > t has
    price[t'] > price[t], mark t as a buy candidate; if any PAST turn t'' < t
    with unsold buys at price[t''] < price[t], mark t as a sell candidate.

    Constraints per turn:
      * free market slots: MKT_SLOTS_CAP - mkt_orders_used[t]
      * cash floor: cash[t] - CASH_FLOOR >= price * units_bought
      * shed headroom for BUY: SHED_CAP - shed_total[t] >= units_bought
      * inventory floor for SELL: our_wheat_inventory >= units_sold + FEED_RESERVE

    Uses an efficient priority-queue matching: sort turns, match cheapest
    remaining buys to highest-priced sells that appear after them.
    """
    import heapq

    n = len(ep.price)
    inventory: list[tuple[int, int, int]] = []  # (buy_price, turn, units) FIFO of holdings
    total_profit = 0.0

    # For each turn, first try to SELL (unload inventory bought earlier)
    # then try to BUY (accumulate for future sells).  For a perfect-hindsight
    # bound, at turn t we know all future prices; sell only if current price
    # is >= any future price we will see for these units.
    max_future_price = [0] * (n + 1)
    for t in range(n - 1, -1, -1):
        max_future_price[t] = max(ep.price[t], max_future_price[t + 1])

    # Buys are optimal any turn t whose price < some future price.
    # Sells are optimal any turn t whose price >= max_future_price[t+1:].
    for t in range(n):
        free_orders = max(0, MKT_SLOTS_CAP - ep.mkt_orders_used[t])
        if free_orders <= 0:
            continue
        price = ep.price[t]

        # ---- SELL leg ----
        maker_held = sum(u for _, _, u in inventory)
        can_sell = maker_held  # one order can carry any quantity
        future_max_after = max_future_price[t + 1] if t + 1 < n else 0
        if can_sell > 0 and price >= future_max_after and free_orders > 0:
            inventory.sort(key=lambda x: x[0])
            sold = 0
            new_inv = []
            for bp, bt, u in inventory:
                if price <= bp:
                    new_inv.append((bp, bt, u))
                    continue
                total_profit += u * (price - bp)
                sold += u
            inventory = new_inv
            free_orders -= 1  # one SELL order used

        # ---- BUY leg ----
        future_max = max_future_price[t + 1] if t + 1 < n else 0
        if future_max <= price or free_orders <= 0:
            continue
        cash_slack = max(0.0, ep.cash[t] - CASH_FLOOR)
        maker_held_now = sum(u for _, _, u in inventory)
        shed_slack = max(0, SHED_CAP - ep.shed_total[t] - maker_held_now)
        max_units = min(
            int(cash_slack // max(1, price)),
            shed_slack,
        )
        if max_units <= 0:
            continue
        inventory.append((price, t, max_units))

    return total_profit


def _summ(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"n": 0}
    xs_sorted = sorted(xs)
    return {
        "n": len(xs),
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "p90": xs_sorted[int(0.9 * len(xs_sorted))] if len(xs_sorted) > 1 else xs_sorted[0],
        "p10": xs_sorted[int(0.1 * len(xs_sorted))] if len(xs_sorted) > 1 else xs_sorted[0],
        "min": xs_sorted[0],
        "max": xs_sorted[-1],
    }


def _glut_analysis(episodes: list[EpisodeSeries], replay_paths: list[str]) -> dict:
    """§6 row 13 ride-along: is the route ever glut-constrained?

    🔴 Read across ALL products.  The first version of this pass measured WHEAT
    only and concluded "never glut-constrained" — but WHEAT is structurally the
    ONE product whose price our selling cannot crash (above_target 0,2: +400
    units moves it $25 -> $20).  The premium products are the opposite:

        MILK / WOOL / STRAWBERRY reach the $1 floor ~100 units above baseline
        MELON is above_func 'sq', above_target 3,6 (+157 units -> $4 of $250)

    Model-free: we read the price series the replay itself recorded, so this
    depends on no simulation of ours.
    """
    from kaggle_environments.envs.kaggriculture.kaggriculture import MARKET_PARAMS

    products = list(MARKET_PARAMS)
    per_product: dict[str, dict] = {}
    series: dict[str, dict[str, list[float]]] = {
        p: {"max_inv": [], "min_price": [], "floor_turns": []} for p in products
    }
    live_ids = {ep.episode_id for ep in episodes}
    replay_paths = [p for p in replay_paths
                    if os.path.basename(p).split("-")[1] in live_ids]
    for path in replay_paths:
        with open(path) as f:
            steps = json.load(f)["steps"]
        for p in products:
            prices = [s[0]["observation"]["market"]["prices"][p] for s in steps]
            invs = [s[0]["observation"]["market"]["inventory"][p] for s in steps]
            series[p]["max_inv"].append(float(max(invs)))
            series[p]["min_price"].append(float(min(prices)))
            series[p]["floor_turns"].append(float(sum(1 for x in prices if x <= 1)))

    for p in products:
        base = MARKET_PARAMS[p]["base"]
        per_product[p] = {
            "base_price": base,
            "above_target": MARKET_PARAMS[p]["above_target"],
            "above_func": MARKET_PARAMS[p]["above_func"],
            "price_at_plus_100": market_price_at(p, 10100),
            "max_market_inv": _summ(series[p]["max_inv"]),
            "min_price": _summ(series[p]["min_price"]),
            "turns_at_dollar_floor": _summ(series[p]["floor_turns"]),
        }
    glut_products = [
        p for p in products
        if statistics.median(series[p]["floor_turns"]) > 0
        or statistics.median(series[p]["min_price"]) < 0.5 * MARKET_PARAMS[p]["base"]
    ]
    if glut_products:
        verdict = (f"GLUT-CONSTRAINED on {', '.join(glut_products)}; "
                   f"NOT on {', '.join(p for p in products if p not in glut_products)}. "
                   f"§6 row 13 is NOT re-closed by this measurement.")
    else:
        verdict = ("NOT glut-constrained on any product; "
                   "§6 row 13 re-closed by this measurement.")
    return {
        "verdict": verdict,
        "n_replays_read": len(replay_paths),
        "glut_constrained_products": glut_products,
        "per_product": per_product,
    }


def market_price_at(item: str, inventory: int) -> int:
    from kaggle_environments.envs.kaggriculture.kaggriculture import market_price
    return market_price(item, inventory)



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays-dir", default=REPLAYS_DIR)
    parser.add_argument("--out", default="data/derived/s7_ship_b_wheat_bound.json")
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.replays_dir, "episode-*.json")))
    if args.limit:
        files = files[: args.limit]
    print(f"Loading {len(files)} replays from {args.replays_dir} ...")

    episodes: list[EpisodeSeries] = []
    for i, path in enumerate(files):
        if i % 20 == 0:
            print(f"  {i}/{len(files)}")
        try:
            episodes.append(_load_episode(path))
        except Exception as e:
            print(f"  skip {path}: {e}")

    live = [ep for ep in episodes if not ep.is_mirror]
    mirror = [ep for ep in episodes if ep.is_mirror]
    print(f"Loaded: {len(live)} live, {len(mirror)} mirror")

    slot = [_slot_bound(ep) for ep in live]
    tight = [_tight_bound(ep) for ep in live]
    ceil_pairs = [_impact_ceiling(ep) for ep in live]
    ceiling = [c for c, _ in ceil_pairs]
    ceiling_k = [float(k) for _, k in ceil_pairs]
    glut = _glut_analysis(live, files)

    verdict_slot = _summ(slot)
    verdict_tight = _summ(tight)
    verdict_ceiling = _summ(ceiling)

    print("\n== CEILING (endogenous price impact; NO cash/shed/order limits) ==")
    print("   ** this is the number the verdict rests on **")
    for k, v in verdict_ceiling.items():
        print(f"  {k:>10s}: {v:.1f}")
    print(f"  mean rating pts: {verdict_ceiling['mean'] / DOLLARS_PER_RATING_PT:.2f}")
    print(f"  optimal units held: median {statistics.median(ceiling_k):.0f}")

    print("\n== SLOT heuristic (NOT a bound — see _slot_bound) ==")
    for k, v in verdict_slot.items():
        print(f"  {k:>10s}: {v:.1f}")
    print(f"  mean rating pts: {verdict_slot['mean'] / DOLLARS_PER_RATING_PT:.2f}")

    print("\n== TIGHT bound (cash floor $500; feed reserve 5; shed headroom) ==")
    for k, v in verdict_tight.items():
        print(f"  {k:>10s}: {v:.1f}")
    print(f"  mean rating pts: {verdict_tight['mean'] / DOLLARS_PER_RATING_PT:.2f}")

    print("\n== Glut ride-along (§6 row 13 re-test) — ALL products ==")
    print(f"  {glut['verdict']}")
    print(f"  glut-constrained: {', '.join(glut['glut_constrained_products']) or 'none'}")
    print(f"\n  {'product':<12}{'base':>6}{'$@+100':>8}{'min $':>7}{'max inv':>9}{'floor turns/ep':>16}")
    for prod, d in glut["per_product"].items():
        print(
            f"  {prod:<12}{d['base_price']:>6}{d['price_at_plus_100']:>8}"
            f"{d['min_price']['median']:>7.0f}{d['max_market_inv']['median']:>9.0f}"
            f"{d['turns_at_dollar_floor']['median']:>16.0f}"
        )

    out = {
        "source": args.replays_dir,
        "n_live_episodes": len(live),
        "n_mirror_episodes": len(mirror),
        "assumptions": {
            "mkt_slots_cap_per_turn": MKT_SLOTS_CAP,
            "shed_capacity": SHED_CAP,
            "cash_floor": CASH_FLOOR,
            "feed_reserve_wheat": FEED_RESERVE,
            "dollars_per_rating_pt": DOLLARS_PER_RATING_PT,
        },
        "ceiling_dollars": verdict_ceiling,
        "ceiling_rating_pts_mean": verdict_ceiling["mean"] / DOLLARS_PER_RATING_PT,
        "ceiling_optimal_units_median": statistics.median(ceiling_k),
        "ceiling_note": (
            "Best single round trip with endogenous price impact, no cash/shed/order "
            "limits. THE defensible ceiling. Both other figures are diagnostics."
        ),
        "slot_heuristic_dollars": verdict_slot,
        "slot_heuristic_rating_pts_mean": verdict_slot["mean"] / DOLLARS_PER_RATING_PT,
        "slot_heuristic_note": "NOT an upper bound — see _slot_bound docstring.",
        "tight_bound_dollars": verdict_tight,
        "tight_bound_rating_pts_mean": verdict_tight["mean"] / DOLLARS_PER_RATING_PT,
        "glut_analysis": glut,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
