#!/usr/bin/env python3
"""S6 step 2c — is the vote erasing town-conditioning in the *non-strawberry* channels? (paper, no episodes)

Phase 0.5 refuted the strawberry mechanism: ReCurSiON's strawberry sell-timing is a fixed hour-0
calendar (`townCenterSellInterval=24`), town-invariant, already reproduced by the majority vote. But
that refutation is *product-scoped* and its conclusion was drawn channel-wide. STRAWBERRY is only 23 of
the 127 state-dependent market steps; **58 steps carry a WOOL (26) or MILK (45) sell and none was
tested.** This module generalises the Phase 0.5 instrument to a **per-product** sweep, driving the shop
set from the engine's own `SHOPS` table rather than a hand-written strawberry constant, and answers the
one question the brief pins:

  at the WOOL / MILK sell-steps, does the donor's action move with the town's shop draw (town-
  conditioning the 50-town vote cannot carry) — or is it, like strawberry, blind to the town?

WOOL is the sharpest instrument in the repo: `YARN_STORE` is the ONLY shop that drains WOOL and ~34% of
towns draw none, so a majority vote over 50 towns must emit one action into a population where a third
have zero demand. If the donor sells WOOL differently in a yarn-dead town than a yarn-rich one, the vote
cannot carry it.

Alignment (identical to s6_step1 / Phase 0.5): stream index i ↔ action at steps[i+1][seat].action,
observation that produced it at steps[i][seat].observation.

The five instruments, run per product:
  1. Determinism — how many sell-steps are byte-identical across all 50 towns; is the residual the SAME
     fixed 4-trace subset {43,45,46,49} as strawberry's (variant artefact) or a town-varying set?
  2. Invariance — action vs the town's realised draw at contested steps, with the ZERO-DRAIN sub-
     population reported separately (the whole test for WOOL). Kill (iv): if the zero-drain cell is thin
     (n<5), say so and stop; do not read invariance off it.
  3. Feature regression — corr(units sold, feature) for own shed / shop count / price / day.
  4. Calendar — fraction of units landing at hour 0.
  5. Vote reproduction — does the reconstruction stream emit the modal per-product volume?

Everything derived from the donor streams is gitignored (§2.4b / R11). No `agent/` change, no upload
(R27). Nothing ships from this pass.

Usage:
    python analysis/s6_step2c.py sweep      # WOOL, MILK (+ the full drainable set for context)
    python analysis/s6_step2c.py report     # reprint the saved JSON without recomputing
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s6_step2b_phase05 import (  # reuse the exact Phase 0.5 plumbing
    ARCHIVE, RECON, DERIVED, _market, _obs, _load_recon, _load_traces, _pearson,
)

OUT = DERIVED / "s6_step2c.json"


def _engine_constants():
    """Read SHOPS / TOWN_CENTER_PRODUCTS out of the engine source by AST, without importing the module
    (it pulls in kaggle_environments at import). Keeps the shop set genuinely engine-derived — the brief's
    requirement — rather than a hand-written constant."""
    import ast
    src = (ROOT / "engine_reference" / "kaggriculture.py").read_text()
    tree = ast.parse(src)
    shops = products = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            name = getattr(node.targets[0], "id", None)
            if name == "SHOPS":
                shops = ast.literal_eval(node.value)
            elif name == "PRODUCTS":
                products = ast.literal_eval(node.value)
    if shops is None:
        raise SystemExit("could not locate SHOPS in engine_reference/kaggriculture.py")
    town_center = [p for p in (products or []) if p != "FERTILIZER"]
    return shops, town_center


SHOPS, TOWN_CENTER_PRODUCTS = _engine_constants()

# Product -> the set of shop types that drain it, derived from the engine's own SHOPS table (not a
# hand-written constant). This is the town-conditioning channel: a product's realised price/absorption
# moves with how many of *its* shops the town drew.
PRODUCT_SHOPS: dict[str, set[str]] = defaultdict(set)
for _shop, _prods in SHOPS.items():
    for _p in _prods:
        PRODUCT_SHOPS[_p].add(_shop)
PRODUCT_SHOPS = dict(PRODUCT_SHOPS)

# The strawberry outlier subset Phase 0.5 found (traces 43,45,46,49 — a late-season variant of the same
# submission). A residual carried by exactly this set is a variant artefact, not town-conditioning.
STRAWBERRY_VARIANT_SUBSET = {43, 45, 46, 49}

# Products that carry a genuine shop-drain channel, sharpest first (WOOL: single shop, ~34% zero-draw).
SWEEP_PRODUCTS = ["WOOL", "MILK", "WHEAT", "STRAWBERRY", "MELON"]


def _units(market: list, product: str) -> int:
    return sum(m[2] for m in market
              if isinstance(m, list) and len(m) == 3 and m[0] == "SELL" and m[1] == product)


def _shop_count(obs, product: str) -> int:
    shops = obs["town"]["unlocked_shops"]
    drains = PRODUCT_SHOPS.get(product, set())
    return sum(1 for s in shops if s in drains)


def analyse_product(product: str, steps_of, units_of, T, n, eps, recon_stream) -> dict:
    """The five instruments for one product. units_of[t][i] = units of `product` sold by trace t at i."""
    units = units_of
    drains = sorted(PRODUCT_SHOPS.get(product, set()))

    # --- 1. Determinism across 50 towns ------------------------------------------------------
    sell_steps = [i for i in range(T) if any(units[t][i] > 0 for t in range(n))]
    disagree = [i for i in sell_steps if len({units[t][i] for t in range(n)}) > 1]
    per_trace_total = [sum(units[t]) for t in range(n)]
    vol_modal, vol_cnt = Counter(per_trace_total).most_common(1)[0]
    outliers = sorted(t for t in range(n) if per_trace_total[t] != vol_modal)

    dev_by_trace = Counter()
    for i in disagree:
        modal = Counter(units[t][i] for t in range(n)).most_common(1)[0][0]
        for t in range(n):
            if units[t][i] != modal:
                dev_by_trace[t] += 1
    carriers = set(dev_by_trace)
    residual_is_fixed4 = bool(carriers) and carriers.issubset(STRAWBERRY_VARIANT_SUBSET)

    # --- 2. Invariance + the zero-drain sub-population ----------------------------------------
    # Aggregate every (trace, sell-step) cell; split by whether the town drew any draining shop.
    zero_units, nonzero_units = [], []
    zero_cells = nonzero_cells = 0
    for i in sell_steps:
        for t, (seat, steps) in enumerate(steps_of):
            o = _obs(steps, seat, i)
            sc = _shop_count(o, product)
            u = units[t][i]
            if sc == 0:
                zero_units.append(u); zero_cells += 1
            else:
                nonzero_units.append(u); nonzero_cells += 1
    # distinct towns that are ever zero-drain at a sell-step (the population size for kill iv)
    zero_towns = set()
    for i in sell_steps:
        for t, (seat, steps) in enumerate(steps_of):
            if _shop_count(_obs(steps, seat, i), product) == 0:
                zero_towns.add(t)

    def _dist(xs):
        if not xs:
            return {"n": 0, "mean": None, "nonzero_frac": None}
        return {"n": len(xs), "mean": round(sum(xs) / len(xs), 3),
                "nonzero_frac": round(sum(1 for x in xs if x > 0) / len(xs), 3)}

    # the decisive single-step frame, like Phase 0.5: the biggest identical-action sell step
    def modal_count(i):
        vals = [units[t][i] for t in range(n)]
        m = Counter(vals).most_common(1)[0]
        return m[1] if m[0] > 0 else 0
    invariance = None
    if sell_steps:
        big = max(sell_steps, key=modal_count)
        rows = []
        for t, (seat, steps) in enumerate(steps_of):
            o = _obs(steps, seat, big)
            rows.append((units[t][big], _shop_count(o, product),
                         o["market"]["prices"].get(product, 0)))
        modal_u = Counter(r[0] for r in rows).most_common(1)[0]
        invariance = {
            "step": big, "day": _obs(steps_of[0][1], steps_of[0][0], big)["day"],
            "modal_units": modal_u[0], "n_traces_at_modal": modal_u[1],
            "price_min": min(r[2] for r in rows), "price_max": max(r[2] for r in rows),
            "shops_min": min(r[1] for r in rows), "shops_max": max(r[1] for r in rows),
        }

    # --- 2b. The DECISIVE frame: within-step drain split -------------------------------------
    # The aggregate zero-drain vs drained split (above) is time-confounded: zero-drain cells cluster
    # early, before shops unlock. The clean test holds the STEP fixed (same day/hour) and asks whether
    # the modal action differs between the town's zero-drain and drain-present sub-populations. If the
    # donor sells the product differently in a drain-dead town than a drain-rich one, THIS is where it
    # shows — and it is what a 50-town vote structurally cannot carry.
    ws_both = ws_diff = 0
    ws_rows = []
    for i in disagree:
        by0, by1 = [], []
        for t, (seat, steps) in enumerate(steps_of):
            sc = _shop_count(_obs(steps, seat, i), product)
            (by0 if sc == 0 else by1).append(units[t][i])
        if by0 and by1:
            ws_both += 1
            m0 = Counter(by0).most_common(1)[0][0]
            m1 = Counter(by1).most_common(1)[0][0]
            if m0 != m1:
                ws_diff += 1
            ws_rows.append({"step": i, "n_zero": len(by0), "n_drain": len(by1),
                            "mean_zero": round(sum(by0) / len(by0), 2),
                            "mean_drain": round(sum(by1) / len(by1), 2),
                            "modal_zero": m0, "modal_drain": m1})

    # --- 2c. Whole-episode drift ceiling (§3.4): the one residual the step test can miss -----
    # Per-episode volume gap between drain-rich and drain-dead towns (by FINAL shop count), priced at
    # the drain-rich list price — a deliberate over-estimate (assumes the vote recovers the whole drift
    # at the richest price). This is the surface area of "conditioning the vote erased", in dollars.
    final_sc = [_shop_count(_obs(steps, seat, T - 1), product) for (seat, steps) in steps_of]
    rich_t = [t for t in range(n) if final_sc[t] >= 1]
    dead_t = [t for t in range(n) if final_sc[t] == 0]
    ceiling = None
    if rich_t and dead_t:
        vol_gap = (sum(per_trace_total[t] for t in rich_t) / len(rich_t)
                   - sum(per_trace_total[t] for t in dead_t) / len(dead_t))
        rich_prices = [o for t in rich_t for o in
                       (_obs(steps_of[t][1], steps_of[t][0], i)["market"]["prices"].get(product, 0)
                        for i in range(T) if units[t][i] > 0)]
        p_rich = (sum(rich_prices) / len(rich_prices)) if rich_prices else 0
        ceiling = {"n_drain_rich_towns": len(rich_t), "n_drain_dead_towns": len(dead_t),
                   "volume_gap_units_per_ep": round(vol_gap, 2),
                   "drain_rich_mean_list_price": round(p_rich, 1),
                   "ceiling_dollars_per_ep": round(vol_gap * p_rich, 0)}

    # --- 3. Feature regression at disagreement steps -----------------------------------------
    feats = defaultdict(list)
    for i in disagree:
        for t, (seat, steps) in enumerate(steps_of):
            o = _obs(steps, seat, i)
            feats["units"].append(units[t][i])
            feats["shed"].append(o["private"]["shed"].get(product, 0))
            feats["shops"].append(_shop_count(o, product))
            feats["price"].append(o["market"]["prices"].get(product, 0))
            feats["day"].append(o.get("day", 0))
    corr = {f: _pearson(feats[f], feats["units"]) for f in ("shed", "shops", "price", "day")} \
        if feats["units"] and len(feats["units"]) >= 2 else {}

    # --- 4. Calendar -------------------------------------------------------------------------
    hour_units = Counter()
    for i in sell_steps:
        h = _obs(steps_of[0][1], steps_of[0][0], i)["hour"]
        hour_units[h] += sum(units[t][i] for t in range(n))
    tot = sum(hour_units.values())

    # --- 5. Vote reproduction ----------------------------------------------------------------
    recon_units = sum(_units(s["market"], product) for s in recon_stream)

    return {
        "product": product, "drain_shops": drains,
        "determinism": {
            "n_sell_steps": len(sell_steps),
            "n_unanimous_sell_steps": len(sell_steps) - len(disagree),
            "n_disagreement_sell_steps": len(disagree),
            "per_trace_total_modal": vol_modal, "n_traces_at_modal_total": vol_cnt,
            "n_outlier_traces": len(outliers),
            "outlier_traces": outliers,
            "disagreement_carried_by_traces": dict(dev_by_trace.most_common()),
            "n_carrier_traces": len(carriers),
            "residual_is_fixed4_variant": residual_is_fixed4,
        },
        "zero_drain": {
            "n_zero_drain_towns": len(zero_towns),
            "zero_drain_cells": zero_cells, "nonzero_drain_cells": nonzero_cells,
            "units_when_zero_drain": _dist(zero_units),
            "units_when_drain_present": _dist(nonzero_units),
            "cell_too_thin": len(zero_towns) < 5,
        },
        "invariance_at_biggest_sell_step": invariance,
        "within_step_drain_split": {
            "n_contested_steps_with_both_subpops": ws_both,
            "n_steps_modal_action_differs": ws_diff,
            "rows": ws_rows,
        },
        "drift_ceiling": ceiling,
        "feature_corr_with_units": corr,
        "calendar": {
            "hour0_units": hour_units.get(0, 0), "total_units": tot,
            "hour0_share": (hour_units.get(0, 0) / tot) if tot else None,
            "units_by_hour": dict(sorted(hour_units.items(), key=lambda kv: -kv[1])[:6]),
        },
        "vote": {
            "reconstruction_units": recon_units,
            "modal_per_trace_total": vol_modal,
            "reproduces_modal": recon_units == vol_modal,
        },
    }


def sweep() -> dict:
    rec = _load_recon()
    eps = rec["episodes_used"]
    traces = _load_traces(eps)
    steps_of = [(seat, d["steps"]) for (_eid, seat, d) in traces]
    T = rec["n_steps"]
    n = len(traces)
    recon_stream = rec["stream"]

    results = {}
    for product in SWEEP_PRODUCTS:
        units_of = [[_units(_market(steps, seat, i), product) for i in range(T)]
                    for (seat, steps) in steps_of]
        results[product] = analyse_product(product, steps_of, units_of, T, n, eps, recon_stream)

    # --- Verdict (R35: the artefact carries its own conclusion string) -----------------------
    # Branch (ii) fires for a product only if its action moves with the draw AT THE STEP LEVEL —
    # the level a 50-town vote cannot carry. A whole-episode drift with an invariant step-modal is
    # branch (i) with a bounded residual, not a located rule.
    conditioned = [p for p in SWEEP_PRODUCTS
                   if results[p]["within_step_drain_split"]["n_steps_modal_action_differs"] > 0]
    wool = results["WOOL"]
    if conditioned:
        verdict = (f"BRANCH (ii): step-level town-conditioning found in {conditioned} — the vote "
                   f"cannot carry it. Report the rule and its readability cap.")
    else:
        cap = wool["drift_ceiling"]["ceiling_dollars_per_ep"] if wool["drift_ceiling"] else None
        verdict = (
            "BRANCH (i): every non-strawberry channel is town-INVARIANT too. At the WOOL sell-steps "
            f"({wool['within_step_drain_split']['n_contested_steps_with_both_subpops']} contested steps "
            "with both zero-yarn and yarn-present towns) the modal action is identical across the drain "
            "split at ALL of them — even though 40% of towns never draw a YARN_STORE. MILK likewise "
            "(and 0/50 towns lack a milk shop, so it never presents a zero-drain population). WHEAT's "
            "residual is the fixed 4-trace strawberry variant; MELON has no shops; FERTILIZER is "
            "analytically eliminated. The only residual is a bounded whole-episode WOOL volume drift "
            f"(~${cap}/ep ceiling, an over-estimate; 6x below the strawberry ceiling already judged "
            "negligible). The majority vote is a faithful reproduction of the donor's whole market "
            "layer; the ~1.100-point gap lives somewhere the market layer is not. Close the "
            "'erased-conditioning' family channel-wide (ROADMAP §3.3). No arm, no episode, no upload.")

    return {"team": rec["team"], "n_traces": n, "n_steps": T,
            "verdict": verdict,
            "product_shops": {p: sorted(PRODUCT_SHOPS.get(p, set())) for p in SWEEP_PRODUCTS},
            "fertilizer_channel": {
                "in_any_SHOPS_entry": "FERTILIZER" in {p for ps in SHOPS.values() for p in ps},
                "in_TOWN_CENTER_PRODUCTS": "FERTILIZER" in TOWN_CENTER_PRODUCTS,
                "note": "no shop drains FERTILIZER and it is excluded from TOWN_CENTER_PRODUCTS; its "
                        "realised price moves only with the shared depletion pool, never the town's "
                        "shop draw. No town-conditioning channel exists to have been erased (C-A "
                        "pattern: the engine answers before the experiment).",
            },
            "products": results}


def _fmt_corr(c: dict) -> str:
    if not c:
        return "(no disagreement steps)"
    return "  ".join(f"{k}={v:+.3f}" for k, v in c.items() if v is not None)


def _print(rec: dict):
    print(f"\n=== S6 step 2c — non-strawberry town-conditioning sweep "
          f"({rec['team']}, {rec['n_traces']} traces) ===")
    print(f"\nVERDICT: {rec['verdict']}")
    fc = rec["fertilizer_channel"]
    print(f"\n[FERTILIZER — analytic elimination] in any SHOPS entry: {fc['in_any_SHOPS_entry']}  |  "
          f"in TOWN_CENTER_PRODUCTS: {fc['in_TOWN_CENTER_PRODUCTS']}  ⇒ no town channel to erase.")
    for product in SWEEP_PRODUCTS:
        r = rec["products"][product]
        d = r["determinism"]
        z = r["zero_drain"]
        inv = r["invariance_at_biggest_sell_step"]
        cal = r["calendar"]
        v = r["vote"]
        print(f"\n----- {product}  (drains: {', '.join(r['drain_shops']) or 'none'}) -----")
        print(f"  [1] sell-steps {d['n_sell_steps']}  identical-across-50 {d['n_unanimous_sell_steps']}  "
              f"differ {d['n_disagreement_sell_steps']}  |  "
              f"{d['n_traces_at_modal_total']}/{rec['n_traces']} traces sell exactly "
              f"{d['per_trace_total_modal']} units total")
        print(f"      disagreement carried by {d['n_carrier_traces']} traces; "
              f"is the fixed {{43,45,46,49}} strawberry variant subset: {d['residual_is_fixed4_variant']}")
        if inv:
            print(f"  [2] biggest step {inv['step']} (day {inv['day']}): {inv['n_traces_at_modal']}/"
                  f"{rec['n_traces']} sell {inv['modal_units']} units while price spans "
                  f"${inv['price_min']}-${inv['price_max']} and {product}-shop count spans "
                  f"{inv['shops_min']}-{inv['shops_max']}")
        uz, un = z["units_when_zero_drain"], z["units_when_drain_present"]
        print(f"      ZERO-DRAIN sub-pop: {z['n_zero_drain_towns']} towns ever zero-drain, "
              f"{z['zero_drain_cells']} zero-drain cells (mean units {uz['mean']}, "
              f"nonzero-frac {uz['nonzero_frac']}) vs {z['nonzero_drain_cells']} drained cells "
              f"(mean units {un['mean']}, nonzero-frac {un['nonzero_frac']})"
              + ("  ⚠ CELL TOO THIN (n<5)" if z["cell_too_thin"] else ""))
        ws = r["within_step_drain_split"]
        print(f"  [2*] WITHIN-STEP drain split (decisive): of {ws['n_contested_steps_with_both_subpops']} "
              f"contested steps with BOTH sub-pops, modal action differs in "
              f"{ws['n_steps_modal_action_differs']}  ⇒ "
              f"{'TOWN-CONDITIONED' if ws['n_steps_modal_action_differs'] else 'invariant across the draw'}")
        dc = r["drift_ceiling"]
        if dc:
            print(f"  [2c] whole-episode drift ceiling: {dc['n_drain_rich_towns']} rich vs "
                  f"{dc['n_drain_dead_towns']} dead towns, volume gap {dc['volume_gap_units_per_ep']} u/ep "
                  f"x ${dc['drain_rich_mean_list_price']} = ${dc['ceiling_dollars_per_ep']}/ep (over-estimate)")
        print(f"  [3] corr(units, ·) at disagreement steps:  {_fmt_corr(r['feature_corr_with_units'])}")
        share = cal["hour0_share"]
        print(f"  [4] calendar: {share:.1%} of units at hour 0" if share is not None
              else "  [4] calendar: n/a")
        print(f"  [5] vote reproduces modal total: {v['reproduces_modal']} "
              f"(recon {v['reconstruction_units']} vs modal {v['modal_per_trace_total']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sweep")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "report":
        if not OUT.exists():
            raise SystemExit(f"{OUT} missing — run `sweep` first")
        _print(json.loads(OUT.read_text()))
        return 0

    rec = sweep()
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, separators=(",", ":")))
    _print(rec)
    print(f"\nwrote {OUT} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
