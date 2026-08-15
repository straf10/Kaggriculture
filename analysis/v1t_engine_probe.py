#!/usr/bin/env python3
"""v1t — decide which engine a replay ran on, from the replay itself.

The 1.32.6 bump was detectable from `configuration.townCenterSellInterval` (12 -> 24). The
1.32.7 bump is **not**: the hinge change lives in `MARKET_PARAMS`, a module constant, and the
replay's configuration only carries `marketParams` when an override was set (it never is on
the live ladder). So the version has to be read off *behaviour*.

The observation carries both `market.inventory` and `market.prices` every step, and the engine
recomputes prices from inventory each turn. That makes every step a labelled sample of the price
curve. For CARROT, TOMATO and EGG the 1.32.6 and 1.32.7 curves disagree over most of the
below-I0 range, so a single step with a drained pool settles it.

Caveat this script handles rather than hides: the two curves **agree** wherever the pool is
undrained (all three products at depletion 0, and TOMATO/EGG everywhere down to their knee).
Agreement is therefore not evidence of 1.32.6 — it is evidence of nothing. Only a disagreeing
sample is informative, so the verdict is UNDECIDED until one appears.

Usage:
    python analysis/v1t_engine_probe.py data/archive/raw/2026-08-14/*.json
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import sys
from pathlib import Path

PRICE_FLOOR = 1
MARKET_I0 = 10000

# The three products whose below-I0 curve moved in 1.32.7, with both parameterisations.
CURVES = {
    "CARROT": {"base": 35, "T": 450,
               "old": ("log", 0.20), "new": ("hinge", 1.00)},
    "TOMATO": {"base": 60, "T": 200,
               "old": ("linear", 0.40), "new": ("hinge", 0.40)},
    "EGG": {"base": 50, "T": 332,
            "old": ("linear", 0.40), "new": ("hinge", 0.40)},
}


def _shape(func: str, x: float, capacity: float) -> float:
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "hinge":
        u = x / capacity
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    raise ValueError(func)


def price(product: str, inventory: int, era: str) -> int:
    """Below-I0 price under `era` in {"old", "new"}. Only the scarcity side is modelled —
    the glut side is byte-identical across the bump, so it carries no signal."""
    spec = CURVES[product]
    func, target = spec[era]
    base, capacity = spec["base"], spec["T"]
    amp = target * base / _shape(func, capacity, capacity)
    raw = base + amp * _shape(func, MARKET_I0 - inventory, capacity)
    return max(PRICE_FLOOR, int(round(raw)))


def _load(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def probe(path: Path) -> dict:
    replay = _load(path)
    steps = replay.get("steps") or []
    cfg = replay.get("configuration") or {}

    votes = {"old": 0, "new": 0}
    disagreeing = 0
    total = 0
    deepest = {p: 0 for p in CURVES}
    first_witness = None

    for t, step in enumerate(steps):
        if not step:
            continue
        obs = (step[0] or {}).get("observation") or {}
        market = obs.get("market") or {}
        inv, prices = market.get("inventory") or {}, market.get("prices") or {}
        for product in CURVES:
            if product not in inv or product not in prices:
                continue
            inventory, observed = int(inv[product]), int(prices[product])
            if inventory >= MARKET_I0:
                continue  # glut side: identical across the bump
            total += 1
            deepest[product] = max(deepest[product], MARKET_I0 - inventory)
            p_old, p_new = price(product, inventory, "old"), price(product, inventory, "new")
            if p_old == p_new:
                continue  # curves agree here — carries no information
            disagreeing += 1
            if observed == p_new:
                votes["new"] += 1
                if first_witness is None:
                    first_witness = (t, product, MARKET_I0 - inventory, observed, p_old, p_new)
            elif observed == p_old:
                votes["old"] += 1
                if first_witness is None:
                    first_witness = (t, product, MARKET_I0 - inventory, observed, p_old, p_new)

    if disagreeing == 0:
        verdict = "UNDECIDED"
    elif votes["new"] and not votes["old"]:
        verdict = "1.32.7"
    elif votes["old"] and not votes["new"]:
        verdict = "1.32.6"
    else:
        verdict = "MIXED"

    return {
        "episode": path.stem,
        "verdict": verdict,
        "town_center_sell_interval": cfg.get("townCenterSellInterval"),
        "below_i0_samples": total,
        "informative_samples": disagreeing,
        "votes": votes,
        "deepest_depletion": deepest,
        "first_witness": first_witness,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)

    rows = []
    for path in args.paths:
        try:
            rows.append(probe(path))
        except Exception as exc:  # noqa: BLE001 — a bad file must not sink the sweep
            rows.append({"episode": path.stem, "verdict": f"ERROR: {exc}"})

    print(f"{'episode':<12} {'verdict':<10} {'tcsi':>5} {'below':>7} {'informative':>12}  deepest depletion")
    for r in rows:
        if r["verdict"].startswith("ERROR"):
            print(f"{r['episode']:<12} {r['verdict']}")
            continue
        dd = " ".join(f"{k}={v}" for k, v in r["deepest_depletion"].items())
        print(f"{r['episode']:<12} {r['verdict']:<10} {str(r['town_center_sell_interval']):>5} "
              f"{r['below_i0_samples']:>7} {r['informative_samples']:>12}  {dd}")
        if r["first_witness"]:
            t, product, dep, obs, po, pn = r["first_witness"]
            print(f"{'':<12}   witness: step {t} {product} depletion {dep} -> observed ${obs} "
                  f"(1.32.6 says ${po}, 1.32.7 says ${pn})")

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\nverdicts:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(rows, indent=1))
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
