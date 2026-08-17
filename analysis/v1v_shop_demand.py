#!/usr/bin/env python3
"""v1v — how much of the top-30's realised-price spread is the *town*, not the *agent*?

ROADMAP §4.1 records a 2,75× / 3,70× / 3,49× spread in realised STRAWBERRY / WOOL / MILK
$/unit across nine top teams whose production is a copied constant, and reads it as a
"three-product timing race". That reading has never been controlled for the one exogenous
variable that also moves realised price: **which shops the town happened to unlock.**

The engine draws shops **with replacement** from the eight `SHOPS` types, one every
`townShopUnlockInterval` (3) days, capped at `MAX_SHOP_INSTANCES` (8)
([kaggriculture.py:886-891](../engine_reference/kaggriculture.py#L886-L891)). Every
`townShopSellInterval` (4) steps each instance consumes `multiplier` units of each product
it lists, where `multiplier` is **2 for single-product shops** and 1 otherwise
([:733-742](../engine_reference/kaggriculture.py#L733-L742)). That drain is the denominator
of realised price, it is drawn per episode, and P(a given product's only shop type is never
drawn) is large — 34,4% for WOOL, whose sole buyer is YARN_STORE.

So: per episode, count the realised per-product shop drain; per seat, measure realised
$/unit; then decompose the spread into a between-town part (exogenous) and a
within-town part (the part an agent can actually contest).

Aggregate only — per-day drain and per-product totals. No per-unit action sequence is read
or emitted, same boundary as `analysis/b1_top5_profile.py` / `b2_current_engine_meta.py`.

Usage:
    python analysis/v1v_shop_demand.py data/archive/raw/2026-08-16 --sample 150
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.metrics import extract_metrics  # noqa: E402

# Mirrored from engine_reference/kaggriculture.py:103-118 — asserted against the installed
# engine by tests/test_v1v_shop_demand.py rather than trusted here.
SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
PRODUCTS = ("STRAWBERRY", "WOOL", "MILK", "MELON", "WHEAT",
            "CARROT", "TOMATO", "EGG", "FERTILIZER")
PRICED = ("STRAWBERRY", "WOOL", "MILK", "MELON", "WHEAT", "FERTILIZER")


def units_per_tick(shops) -> dict[str, int]:
    """Units of each product consumed by one shop-consumption tick, for this town."""
    out: dict[str, int] = defaultdict(int)
    for name in shops:
        products = SHOPS[name]
        multiplier = 2 if len(products) == 1 else 1
        for item in products:
            out[item] += multiplier
    return dict(out)


def expected_units_per_tick() -> dict[str, float]:
    """E[units/tick] over the shop draw, at the full 8 instances, uniform over 8 types."""
    out: dict[str, float] = defaultdict(float)
    for name, products in SHOPS.items():
        multiplier = 2 if len(products) == 1 else 1
        for item in products:
            out[item] += multiplier * 8 / len(SHOPS)
    return dict(out)


def absent_probability() -> dict[str, float]:
    """P(no instance of any shop that lists this product, over 8 draws with replacement)."""
    n = len(SHOPS)
    out = {}
    for item in PRODUCTS:
        carriers = sum(1 for products in SHOPS.values() if item in products)
        out[item] = ((n - carriers) / n) ** 8
    return out


def load(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def profile_episode(replay: dict) -> dict | None:
    steps = replay["steps"]
    if len(steps) < 700:
        return None
    town = steps[-1][0]["observation"]["town"]
    shops = list(town.get("unlocked_shops") or ())
    per_tick = units_per_tick(shops)
    info = replay.get("info") or {}
    teams = info.get("TeamNames") or ["?", "?"]

    seats = []
    for seat in (0, 1):
        revenue: dict[str, float] = defaultdict(float)
        units: dict[str, int] = defaultdict(int)
        try:
            for sale in extract_metrics(replay, seat)["market_sales"]:
                revenue[sale["item"]] += sale["price"]
                units[sale["item"]] += 1
        except Exception as exc:                   # a malformed replay must not kill the run
            print(f"    metrics unavailable ({exc})", file=sys.stderr)
            return None
        seats.append({
            "team": teams[seat] if seat < len(teams) else "?",
            "final_bank": replay["rewards"][seat],
            "units": dict(units),
            "revenue": dict(revenue),
            "realised": {p: (revenue[p] / units[p]) for p in PRICED if units.get(p)},
        })

    final_inventory = steps[-1][0]["observation"]["market"]["inventory"]
    final_prices = steps[-1][0]["observation"]["market"]["prices"]
    return {
        "episode_id": info.get("EpisodeId"),
        "shops": shops,
        "shop_units_per_tick": per_tick,
        "final_inventory": final_inventory,
        "final_prices": final_prices,
        "seats": seats,
    }


def summarise(rows: list[dict]) -> dict:
    """Between-town vs within-town decomposition of realised $/unit."""
    out = {"episodes": len(rows), "seats": 2 * len(rows), "products": {}}
    for product in PRICED:
        pairs = []          # (episode mean, seat value) for seats that sold this product
        by_episode = []
        for row in rows:
            vals = [s["realised"][product] for s in row["seats"] if product in s["realised"]]
            if not vals:
                continue
            mean = statistics.fmean(vals)
            by_episode.append({
                "mean": mean,
                "drain": row["shop_units_per_tick"].get(product, 0),
                "n": len(vals),
            })
            pairs.extend((mean, v) for v in vals)
        if len(by_episode) < 5:
            continue
        seat_vals = [v for _, v in pairs]
        ep_means = [e["mean"] for e in by_episode]
        # Total variance splits into between-episode (town + shared opponent field) and
        # within-episode (the two seats in the *same* town — the contestable part).
        within = [v - m for m, v in pairs]
        entry = {
            "seats_selling": len(seat_vals),
            "episodes_selling": len(by_episode),
            "median_realised": statistics.median(seat_vals),
            "spread_p10_p90": None,
            "sd_total": statistics.pstdev(seat_vals) if len(seat_vals) > 1 else 0.0,
            "sd_between_towns": statistics.pstdev(ep_means) if len(ep_means) > 1 else 0.0,
            "sd_within_town": statistics.pstdev(within) if len(within) > 1 else 0.0,
        }
        srt = sorted(seat_vals)
        if len(srt) >= 10:
            p10 = srt[int(0.10 * (len(srt) - 1))]
            p90 = srt[int(0.90 * (len(srt) - 1))]
            entry["spread_p10_p90"] = [p10, p90, (p90 / p10) if p10 else None]
        total_var = entry["sd_total"] ** 2
        if total_var > 0:
            entry["share_between_towns"] = entry["sd_between_towns"] ** 2 / total_var
            entry["share_within_town"] = entry["sd_within_town"] ** 2 / total_var
        # Realised price by drain bucket — the direct test of the mechanism.
        buckets: dict[int, list[float]] = defaultdict(list)
        for e in by_episode:
            buckets[e["drain"]].append(e["mean"])
        entry["by_drain"] = {
            str(k): {"episodes": len(v), "median_realised": statistics.median(v)}
            for k, v in sorted(buckets.items())
        }
        out["products"][product] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, help="directory of replay .json/.json.gz")
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--out", type=Path,
                    default=Path("data/derived/v1v_shop_demand.json"))
    args = ap.parse_args()

    paths = sorted(p for p in args.source.iterdir()
                   if p.suffix in (".json", ".gz") and p.stem != "manifest")
    if args.sample and len(paths) > args.sample:
        stride = len(paths) / args.sample
        paths = [paths[int(i * stride)] for i in range(args.sample)]

    print(f"engine constants — expected units/tick at 8 shops: "
          f"{ {k: round(v, 2) for k, v in sorted(expected_units_per_tick().items())} }")
    print(f"P(product has no shop at all): "
          f"{ {k: round(v, 4) for k, v in sorted(absent_probability().items()) if v} }")

    rows = []
    for i, path in enumerate(paths, 1):
        try:
            row = profile_episode(load(path))
        except Exception as exc:
            print(f"  [{i}/{len(paths)}] {path.name}: FAILED {exc}", file=sys.stderr)
            continue
        if row:
            rows.append(row)
        if i % 25 == 0:
            print(f"  [{i}/{len(paths)}] {len(rows)} profiled")

    summary = summarise(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1),
                        encoding="utf-8")

    print(f"\n{summary['episodes']} episodes / {summary['seats']} seats\n")
    hdr = f"{'product':<12}{'median $/u':>11}{'p10→p90':>16}{'between towns':>15}{'within town':>13}"
    print(hdr)
    print("-" * len(hdr))
    for product, e in summary["products"].items():
        sp = e["spread_p10_p90"]
        spread = f"{sp[0]:.0f}→{sp[1]:.0f} ({sp[2]:.2f}x)" if sp and sp[2] else "-"
        print(f"{product:<12}{e['median_realised']:>11.1f}{spread:>16}"
              f"{e.get('share_between_towns', 0):>14.0%}{e.get('share_within_town', 0):>13.0%}")

    print("\nrealised $/unit by that town's shop drain (units consumed per 4-step tick):")
    for product, e in summary["products"].items():
        cells = "  ".join(f"{k}u:{v['median_realised']:.0f}(n={v['episodes']})"
                          for k, v in e["by_drain"].items())
        print(f"  {product:<12}{cells}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
