#!/usr/bin/env python3
"""S6 step 0, leg 2 — the surface area of the C-A rule (ROADMAP §4.3 S6 step 0).

C-A (the Cleo rule) reorders SELL orders **within the slots the plan already used for selling**.
It cannot change quantity, timing, or which slot holds a purchase. So its entire surface is turns
where the tape emits two or more SELL orders, of which at least two are reorderable into a better
queue position.

Measured, per donor tape, directly from the recorded route:

  1. Turn-by-turn histogram of SELL orders per turn — how many turns emit >=2 sells?
  2. Of those, how many mix a premium (STRAWBERRY/WOOL/MILK) with a non-premium, or two premiums
     — i.e. how many are actually reorderable into a better queue position?
  3. The realisable upper bound: for each such turn, price the best legal permutation of the
     tape's SELL orders against the emitted one, using the engine's own market path at that
     turn's recorded inventory (opponent queue + pre-turn state held fixed as recorded). Sum
     over the season.

Part 3 is priced on a *recorded* route — one canonical tape-vs-tape replay per donor, both
seats. This is the T2 lesson applied early: bound the lever before building it.

Usage:
    python analysis/s6_step0_leg2.py --seed 7
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import sys
from collections import Counter, defaultdict
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.donor_streams import DONORS, available, load_donor_stream, make_donor_tape  # noqa: E402
from harness.metrics import _simulate_market, _apply_unit_actions  # noqa: E402
from harness.play import play  # noqa: E402

PREMIUM = ("STRAWBERRY", "WOOL", "MILK")
MAX_PERM_SELLS = 7  # enumerate permutations only up to this many sells/turn (else note & skip)


def _sells(market_orders) -> list:
    return [o for o in market_orders if isinstance(o, list) and o and o[0] == "SELL"]


def route_surface(stream: list) -> dict:
    """Parts 1 & 2 — pure read of the donor's market channel, no episode needed."""
    sells_per_turn = Counter()
    multi_sell_turns = []          # turns emitting >=2 SELL orders
    reorderable_turns = []         # multi-sell turns that mix curve positions
    for t, action in enumerate(stream):
        sells = _sells(action.get("market", []))
        n = len(sells)
        sells_per_turn[n] += 1
        if n >= 2:
            items = [o[1] for o in sells]
            distinct = set(items)
            has_premium = any(i in PREMIUM for i in items)
            has_nonpremium = any(i not in PREMIUM for i in items)
            n_premium = sum(1 for i in items if i in PREMIUM)
            # Reorderable = at least two orders that could sit in a different curve position:
            # two different products (independent pools, but the 10-cap / cross-index channel
            # can still bite), or a premium mixed with a non-premium.
            reorderable = len(distinct) >= 2 and (has_premium)
            row = {"turn": t, "items": items,
                   "mixes_premium_nonpremium": has_premium and has_nonpremium,
                   "two_or_more_premium": n_premium >= 2}
            multi_sell_turns.append(row)
            if reorderable:
                reorderable_turns.append(row)
    over_cap = sum(1 for a in stream if len(a.get("market", []) or []) > 10)
    return {
        "sells_per_turn_hist": dict(sorted(sells_per_turn.items())),
        "turns_with_2plus_sells": len(multi_sell_turns),
        "reorderable_turns": len(reorderable_turns),
        "reorderable_mixing_premium_nonpremium":
            sum(1 for r in reorderable_turns if r["mixes_premium_nonpremium"]),
        "reorderable_two_premium":
            sum(1 for r in reorderable_turns if r["two_or_more_premium"]),
        "turns_over_10_order_cap": over_cap,
        "_multi_sell_turns": multi_sell_turns,
    }


def _legal_sell_permutations(market_orders):
    """Yield permuted queues: sells shuffled only *within* each contiguous inter-purchase run
    of sell slots (so no sell ever crosses a purchase — the Cleo cash-funding invariant).
    Non-sell orders keep their exact positions. Yields the emitted queue first."""
    is_sell = [isinstance(o, list) and o and o[0] == "SELL" for o in market_orders]
    # positions of sells, grouped into runs broken by any non-sell order
    runs = []
    cur = []
    for i, s in enumerate(is_sell):
        if s:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    # each run independently permutes its sells; product of per-run permutations
    run_perms = []
    total = 1
    for run in runs:
        if len(run) > MAX_PERM_SELLS:
            return None  # too many to enumerate
        perms = list(permutations(range(len(run))))
        run_perms.append((run, perms))
        total *= len(perms)
    if total > 20000:
        return None
    from itertools import product as iproduct
    for combo in iproduct(*[p for _, p in run_perms]):
        q = list(market_orders)
        for (run, _), order in zip(run_perms, combo):
            sells = [market_orders[i] for i in run]
            for slot, pick in zip(run, order):
                q[slot] = sells[pick]
        yield q


def _focal_sell_revenue(env_json, seat, turn, market_orders, configuration):
    """Simulate ONE turn's market for `seat` with `market_orders` substituted, on the recorded
    pre-turn state (previous step). Opponent action + pre-turn farms/privates/market are the
    recorded ones. Returns total focal SELL revenue for the turn."""
    steps = env_json["steps"]
    prev = steps[turn - 1]
    cur = steps[turn]
    farms = copy.deepcopy(prev[0]["observation"]["farms"])
    market = copy.deepcopy(prev[0]["observation"]["market"])
    privates = [copy.deepcopy(prev[s]["observation"]["private"]) for s in (0, 1)]

    def _act(step, s):
        a = step[s].get("action")
        return a if isinstance(a, dict) else {"farmer": ["PASS"], "hands": [], "market": []}

    actions = [_act(cur, 0), _act(cur, 1)]
    actions[seat] = {**actions[seat], "market": market_orders}
    prev_day = int(prev[0]["observation"].get("day", 0))
    # apply unit actions first (harvest/pickup feed the shed the sells draw on), exactly as the
    # engine turn order and metrics._transition_events do
    _apply_unit_actions(farms, privates, actions, configuration, prev_day)
    sales, _ = _simulate_market(farms, privates, market, actions, configuration)
    return sum(s["price"] for s in sales[seat])


def priced_upper_bound(env_json, seat, surface, configuration) -> dict:
    """Part 3 — for each reorderable turn, max focal SELL revenue over legal permutations minus
    the emitted revenue. Sum over the season."""
    steps = env_json["steps"]
    total_gain = 0.0
    turns_with_gain = 0
    skipped = 0
    per_turn = []
    reorderable_turns = {r["turn"] for r in surface["_multi_sell_turns"]
                         if len(set(r["items"])) >= 2 and any(i in PREMIUM for i in r["items"])}
    for turn in sorted(reorderable_turns):
        if turn >= len(steps):
            continue
        emitted_orders = steps[turn][seat].get("action")
        emitted_orders = (emitted_orders or {}).get("market", []) if isinstance(emitted_orders, dict) else []
        emitted_rev = _focal_sell_revenue(env_json, seat, turn, emitted_orders, configuration)
        perms = _legal_sell_permutations(emitted_orders)
        if perms is None:
            skipped += 1
            continue
        best = emitted_rev
        for q in perms:
            rev = _focal_sell_revenue(env_json, seat, turn, q, configuration)
            if rev > best:
                best = rev
        gain = best - emitted_rev
        if gain > 1e-9:
            turns_with_gain += 1
            total_gain += gain
            per_turn.append({"turn": turn, "gain": round(gain, 2)})
    return {"season_gain": round(total_gain, 2), "turns_with_any_gain": turns_with_gain,
            "reorderable_turns_priced": len(reorderable_turns) - skipped,
            "turns_skipped_too_many_perms": skipped, "per_turn_gains": per_turn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="3,7,19,31", help="seeds for the canonical tape-vs-tape replays")
    ap.add_argument("--out", type=Path, default=Path("data/derived/s6_step0_leg2.json"))
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]

    for eid in DONORS:
        if not available(eid):
            raise SystemExit(f"donor {eid} absent — leg 2 needs the gitignored tapes locally")

    teams = list(DONORS.values())
    tapes = {t: make_donor_tape(e) for e, t in DONORS.items()}
    run_dir = Path("runs/s6_leg2")

    results = {}
    for eid, team in DONORS.items():
        stream = load_donor_stream(eid)
        surface = route_surface(stream)
        opp = teams[(teams.index(team) + 1) % len(teams)]  # this tape vs the next tape
        bounds = []  # (seed, seat, season_gain)
        for seed in seeds:
            res = play(tapes[team], tapes[opp], seed=seed, steps=None,
                       record=True, run_dir=run_dir, strict=False, metrics=False)
            with gzip.open(res.replay_path, "rt", encoding="utf-8") as fh:
                env_json = json.load(fh)
            configuration = env_json.get("configuration", {})
            b0 = priced_upper_bound(env_json, 0, surface, configuration)
            res2 = play(tapes[opp], tapes[team], seed=seed, steps=None,
                        record=True, run_dir=run_dir, strict=False, metrics=False)
            with gzip.open(res2.replay_path, "rt", encoding="utf-8") as fh:
                env_json2 = json.load(fh)
            b1 = priced_upper_bound(env_json2, 1, surface, configuration)
            bounds.append({"seed": seed, "seat0": b0, "seat1": b1})
        surface.pop("_multi_sell_turns", None)
        gains = [b["seat0"]["season_gain"] for b in bounds] + [b["seat1"]["season_gain"] for b in bounds]
        results[team] = {"surface": surface, "canonical_opponent": opp, "seeds": seeds,
                         "bounds_by_seed": bounds,
                         "upper_bound_min": min(gains), "upper_bound_max": max(gains),
                         "upper_bound_mean": round(sum(gains) / len(gains), 2)}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")

    print(f"\n{'='*72}\nLEG 2 — surface area of the C-A rule\n{'='*72}")
    for team, r in results.items():
        s = r["surface"]
        print(f"\n{team}:")
        print(f"  sells/turn histogram: {s['sells_per_turn_hist']}")
        print(f"  turns emitting >=2 sells:            {s['turns_with_2plus_sells']}")
        print(f"  of those, reorderable (mix curves):  {s['reorderable_turns']}")
        print(f"     mixing premium + non-premium:     {s['reorderable_mixing_premium_nonpremium']}")
        print(f"     two-or-more premium:              {s['reorderable_two_premium']}")
        print(f"  turns exceeding the 10-order cap:     {s['turns_over_10_order_cap']}")
        print(f"  realisable upper bound over seeds {r['seeds']} (both seats, vs {r['canonical_opponent']}):")
        print(f"     ${r['upper_bound_min']}–${r['upper_bound_max']}/ep  (mean ${r['upper_bound_mean']}/ep)")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
