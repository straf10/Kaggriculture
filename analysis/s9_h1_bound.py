#!/usr/bin/env python3
"""S9 review — the H1 "sell earlier in the same day" ceiling, WITH our own price impact.

Two questions the plan does not answer with reproducible code:

  (1) Can the literal H1 rule (§3, condition 2 — known town drain only, no opponent
      assumption) ever move a sale to a STRICTLY better price?  `market_price` is
      non-increasing in inventory and `drain >= 0`, so the answer should be "never".
      Counted here, not argued.

  (2) What is the ceiling of "move the whole day's batch of product p to the single
      best hour of that same day", priced unit-by-unit against the RECORDED inventory
      at that hour, so our own impact is charged?  This is an ORACLE ceiling (it needs
      the opponent's within-day sales known in advance) and is therefore an upper bound
      on any implementable version of H1.

Output: data/derived/s9_h1_bound.json
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

OUT = ROOT / "data" / "derived" / "s9_h1_bound.json"
TPD = 24


def drain_between(shops, t_from, t_to, item):
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


def batch_revenue(item, inv0, n):
    """Revenue of selling n units starting at market inventory inv0, engine rules:
    price quoted at current inventory, inventory += 1 only when price > 1 (:652)."""
    inv = inv0
    tot = 0
    for _ in range(n):
        p = K.market_price(item, inv)
        tot += p
        if p > 1:
            inv += 1
    return tot


def main(limit=None):
    rows = []
    n_ep = 0
    strict_fires = 0
    tie_fires = 0
    total_units = 0
    for sub in SUBMISSIONS:
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            if seat is None:
                continue
            steps, cfg = m["steps"], m["configuration"]
            inv_at = [steps[t][0]["observation"]["market"]["inventory"] for t in range(len(steps))]
            shed_at = [steps[t][seat]["observation"]["private"]["shed"] for t in range(len(steps))]
            shops_at = [list(steps[t][0]["observation"]["town"].get("unlocked_shops", []))
                        for t in range(len(steps))]
            # our committed sales: (day, item) -> list of (step, price)
            byb = defaultdict(list)
            for i in range(1, len(steps)):
                _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
                t = i - 1
                for s in sales[seat]:
                    byb[(t // TPD, s["item"])].append((t, s["price"]))

            gain = 0.0
            gain_cons = 0.0
            gain_by_item = defaultdict(float)
            gain_cons_by_item = defaultdict(float)
            gain_cons_feas = 0.0
            gain_cons_feas_by_item = defaultdict(float)
            n_batches_all = [0]
            n_batches_feas = [0]
            moved_batches = 0
            for (day, item), lst in byb.items():
                total_units += len(lst)
                actual = sum(p for _t, p in lst)
                # (1) literal-rule firing test, per unit
                for t, price in lst:
                    for tp in range(day * TPD, t):
                        inv_p = inv_at[tp][item]
                        p_now = K.market_price(item, inv_p)
                        d = drain_between(shops_at[tp], tp, t, item)
                        p_lat = K.market_price(item, inv_p - d)
                        if p_now > p_lat:
                            strict_fires += 1
                        elif p_now == p_lat:
                            tie_fires += 1
                # (2) whole-batch best-hour oracle, own impact charged
                first = min(t for t, _p in lst)
                consolidated = batch_revenue(item, inv_at[first][item], len(lst))
                best = max(actual, consolidated)
                for h in range(day * TPD, first + 1):
                    r = batch_revenue(item, inv_at[h][item], len(lst))
                    if r > best:
                        best = r
                if best > actual:
                    moved_batches += 1
                gain += best - actual
                gain_by_item[item] += best - actual
                gain_cons += consolidated - actual
                gain_cons_by_item[item] += consolidated - actual
                # Shed feasibility (engine :653 — SELL reads private["shed"] ONLY; a unit in a
                # worker basket cannot be sold). The whole day's batch can be consolidated at
                # `first` only if the shed already holds it there.
                n_batches_all[0] += 1
                if shed_at[first].get(item, 0) >= len(lst):
                    n_batches_feas[0] += 1
                    gain_cons_feas += consolidated - actual
                    gain_cons_feas_by_item[item] += consolidated - actual
            rows.append(dict(submission=sub, episode_id=eid,
                             gain=gain, gain_by_item=dict(gain_by_item),
                             gain_cons=gain_cons, gain_cons_by_item=dict(gain_cons_by_item),
                             gain_cons_feas=gain_cons_feas,
                             gain_cons_feas_by_item=dict(gain_cons_feas_by_item),
                             n_batches_all=n_batches_all[0], n_batches_feas=n_batches_feas[0],
                             moved_batches=moved_batches, n_batches=len(byb)))
            n_ep += 1
            if n_ep % 25 == 0:
                print(f"  {n_ep}", flush=True)
            if limit and n_ep >= limit:
                break
        if limit and n_ep >= limit:
            break
    out = dict(episodes=rows, literal_rule=dict(strict_fires=strict_fires, tie_fires=tie_fires,
                                                total_units=total_units))
    OUT.write_text(json.dumps(out))
    print("literal rule: strict fires =", strict_fires, " tie fires =", tie_fires,
          " units =", total_units)
    print("wrote", OUT)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
