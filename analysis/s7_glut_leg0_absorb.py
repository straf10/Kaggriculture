"""S7 glut-metering — Phase 0 / Leg 0 (§4.1): absorption capacity vs our own
supply, per premium product.  DESK ONLY, no episodes, runs FIRST (K0).

The plan's whole premise is "WOOL sits at $1 for a median 30 turns because we
push more units than the town can consume before its buyer even unlocks".  Leg 0
tests the *structural* half of that with pure arithmetic on the recorded tapes:

    absorb(p) = 30                                       # town centre, 1/day * 30
              + Σ_instances rate(shop, p) * (30 - unlock_day)
                                                         # rate = 6/day, x2 single-product

    U(p)      = units WE (seat 0) actually SELL into the market this episode
                (recorded ['SELL', p, q] orders — the units we push onto the pool)

Verdict per product, per §4.1 / K0:

  * U(p) ≲ absorb(p)   there IS a schedule that clears the supply near base.
                       Metering has a lever.  Pass.
  * U(p) ≫ absorb(p)   the excess sells at $1 no matter the timing.  This is a
                       STRUCTURAL surplus, not a timing error — no rate rule
                       saves it; the only lever is producing less (a different
                       arm; §6 row 14 says fewer sheep cost -$5,093).  => K0 KILL
                       for that product, and §11 row 31 must be corrected where
                       it reads the glut as a timing lever.

The absorption schedule is read from each replay's OWN `unlocked_shops`
progression (the day each instance first appears), so it depends on no model of
the unlock RNG — exactly the runtime-visible signal the plan (§2, §2.1) says the
arm would read.  We report the realised WOOL zero-drain fraction alongside the
34,4% / 34,0% / 40% population figures the ROADMAP carries, without adopting any
of them.

Retention (§7.3): reports files-on-disk, files passing the integrity check, and
the count actually used — declared, not assumed (neither 178 nor 179).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from collections import Counter
from dataclasses import dataclass, field

REPLAYS_DIR = "data/archive/raw/live_55586926"
SEASON_DAYS = 30
DOLLARS_PER_RATING_PT = 253.0

# Premium products the plan cares about (§1 red rows + MELON).  We compute all
# nine but the verdict headline is WOOL (the K0 trigger, §9).
PREMIUM = ["WOOL", "STRAWBERRY", "MILK", "MELON"]


@dataclass
class Episode:
    episode_id: str
    is_mirror: bool
    n_steps: int
    turns_per_day: int
    shop_sell_interval: int
    center_interval: int
    # unlock_day per shop INSTANCE, in order of appearance
    shop_unlocks: list[tuple[str, int]] = field(default_factory=list)
    our_sell_units: Counter = field(default_factory=Counter)     # seat 0
    opp_sell_units: Counter = field(default_factory=Counter)      # seat 1


def _shops_and_center():
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        SHOPS, TOWN_CENTER_PRODUCTS,
    )
    return SHOPS, set(TOWN_CENTER_PRODUCTS)


def _load(path: str) -> Episode:
    with open(path) as f:
        r = json.load(f)
    steps = r["steps"]
    cfg = r.get("configuration", {})
    tpd = int(cfg.get("turnsPerDay", 24) or 24)
    ssi = int(cfg.get("townShopSellInterval", 4) or 4)
    cci = int(cfg.get("townCenterSellInterval", 24) or 24)

    parts = os.path.basename(path).split("-")
    if len(parts) < 2:
        raise ValueError(f"unexpected replay filename (no '-'): {path}")
    ep_id = parts[1]

    our_sell: Counter = Counter()
    opp_sell: Counter = Counter()
    priv_same = 0
    prev_len = 0
    shop_unlocks: list[tuple[str, int]] = []
    prev_shops: list[str] = []

    for s in steps:
        obs0 = s[0]["observation"]
        # --- shop unlock progression (read the tape, not the RNG) ---
        town = obs0.get("town", {}) or {}
        shops = list(town.get("unlocked_shops", []) or [])
        if len(shops) > prev_len:
            day = int(obs0.get("day", obs0.get("step", 0) // tpd))
            # the newly appended instances (drawn-with-replacement, appended)
            for name in shops[prev_len:]:
                shop_unlocks.append((name, day))
            prev_len = len(shops)
        prev_shops = shops

        # --- our / opponent SELL volume ---
        for seat, bag in ((0, our_sell), (1, opp_sell)):
            a = s[seat].get("action")
            m = a.get("market", []) if isinstance(a, dict) else []
            if not isinstance(m, list):
                continue
            for order in m:
                if isinstance(order, list) and order and order[0] == "SELL" and len(order) >= 3:
                    try:
                        bag[order[1]] += int(order[2])
                    except (ValueError, TypeError):
                        pass

        # mirror classifier (same convention as s7_ship_b bound)
        if (obs0.get("private") or {}) == (s[1]["observation"].get("private") or {}):
            priv_same += 1

    is_mirror = priv_same > len(steps) * 0.7
    return Episode(
        episode_id=ep_id,
        is_mirror=is_mirror,
        n_steps=len(steps),
        turns_per_day=tpd,
        shop_sell_interval=ssi,
        center_interval=cci,
        shop_unlocks=shop_unlocks,
        our_sell_units=our_sell,
        opp_sell_units=opp_sell,
    )


def absorb(ep: Episode, product: str, SHOPS, CENTER: set) -> float:
    """Total units of `product` the town can consume this season, from THIS
    episode's recorded unlock schedule."""
    ticks_per_day = ep.turns_per_day / ep.shop_sell_interval        # 24/4 = 6
    center_per_day = ep.turns_per_day / ep.center_interval          # 24/24 = 1
    total = 0.0
    if product in CENTER:
        total += center_per_day * SEASON_DAYS
    for name, unlock_day in ep.shop_unlocks:
        products = SHOPS.get(name, [])
        if product not in products:
            continue
        mult = 2 if len(products) == 1 else 1
        days_active = max(0, SEASON_DAYS - unlock_day)
        total += mult * ticks_per_day * days_active
    return total


def _summ(xs):
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    n = len(xs)
    return {
        "n": n,
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "p10": xs[int(0.1 * n)] if n > 1 else xs[0],
        "p90": xs[int(0.9 * n)] if n > 1 else xs[0],
        "min": xs[0],
        "max": xs[-1],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays-dir", default=REPLAYS_DIR)
    ap.add_argument("--out", default="data/derived/s7_glut_leg0_absorb.json")
    ap.add_argument("--surplus-ratio", type=float, default=2.0,
                    help="U/absorb above this counts as '≫' (structural surplus) for K0")
    args = ap.parse_args()

    SHOPS, CENTER = _shops_and_center()
    files = sorted(glob.glob(os.path.join(args.replays_dir, "episode-*.json")))
    n_disk = len(files)

    episodes: list[Episode] = []
    n_bad = 0
    for path in files:
        try:
            ep = _load(path)
            if ep.n_steps < 2:
                raise ValueError(f"only {ep.n_steps} steps")
            episodes.append(ep)
        except Exception as e:
            n_bad += 1
            print(f"  SKIP {os.path.basename(path)}: {e}")

    live = [e for e in episodes if not e.is_mirror]
    mirror = [e for e in episodes if e.is_mirror]

    print("\n== RETENTION (§7.3) ==")
    print(f"  on disk           : {n_disk}")
    print(f"  passed integrity  : {len(episodes)}")
    print(f"  failed integrity  : {n_bad}")
    print(f"  live / mirror     : {len(live)} / {len(mirror)}")
    print(f"  USED for verdict  : {len(live)} live episodes")

    # WOOL zero-drain (no YARN_STORE ever) realised fraction, live episodes
    def has_yarn(ep):
        return any(name == "YARN_STORE" for name, _ in ep.shop_unlocks)
    n_no_yarn = sum(1 for e in live if not has_yarn(e))
    frac_no_yarn = n_no_yarn / len(live) if live else 0.0
    print("\n== WOOL zero-drain (no YARN_STORE) — realised vs population ==")
    print(f"  realised (live)   : {n_no_yarn}/{len(live)} = {100*frac_no_yarn:.1f}%")
    print(f"  ROADMAP carries   : 34,4% (machine §4) / 34,0% (measured §5.2) / 40% (§6 row 25)")

    out_products = {}
    print("\n== Leg 0: U(p) [our sell units] vs absorb(p) [town capacity], live ==")
    header = f"  {'product':<11}{'U med':>7}{'U p90':>7}{'absorb med':>12}{'U/abs med':>11}{'≫ eps':>8}"
    print(header)

    # iterate the products we care about, then the rest
    all_products = PREMIUM + [q for q in sorted(CENTER) if q not in PREMIUM]
    for p in all_products:
        Us = [ep.our_sell_units.get(p, 0) for ep in live]
        Abs = [absorb(ep, p, SHOPS, CENTER) for ep in live]
        ratios = [ (u / a) if a > 0 else float("inf") for u, a in zip(Us, Abs) ]
        finite_ratios = [r for r in ratios if r != float("inf")]
        n_surplus = sum(1 for r in ratios if r > args.surplus_ratio)
        u_s = _summ([float(u) for u in Us])
        a_s = _summ(Abs)
        r_med = statistics.median(finite_ratios) if finite_ratios else float("inf")
        out_products[p] = {
            "U_units": u_s,
            "absorb_units": a_s,
            "ratio_U_over_absorb_median": r_med,
            "n_episodes_surplus": n_surplus,
            "surplus_ratio_threshold": args.surplus_ratio,
            "frac_surplus": n_surplus / len(live) if live else 0.0,
        }
        print(f"  {p:<11}{u_s['median']:>7.0f}{u_s['p90']:>7.0f}"
              f"{a_s['median']:>12.0f}{r_med:>11.2f}{n_surplus:>8d}")

    # ---- K0 verdict on WOOL ----
    wool = out_products["WOOL"]
    k0_kill = wool["ratio_U_over_absorb_median"] > args.surplus_ratio
    print("\n== K0 VERDICT (WOOL) ==")
    print(f"  median U/absorb   : {wool['ratio_U_over_absorb_median']:.2f}  "
          f"(threshold ≫ = {args.surplus_ratio})")
    print(f"  episodes in surplus: {wool['n_episodes_surplus']}/{len(live)} "
          f"({100*wool['frac_surplus']:.0f}%)")
    if k0_kill:
        print("  >>> K0 TRIGGERED: WOOL supply STRUCTURALLY exceeds absorption.")
        print("      The glut is not a timing error — no rate rule saves it.")
        print("      Per §9/§10: STOP the pass, and correct §11 row 31 (reads it as a lever).")
    else:
        print("  >>> K0 NOT triggered on WOOL: supply is within a clearable schedule.")
        print("      Metering has a structural lever; proceed to Phase 0 attribution (§4).")

    out = {
        "source": args.replays_dir,
        "retention": {
            "on_disk": n_disk,
            "passed_integrity": len(episodes),
            "failed_integrity": n_bad,
            "n_live": len(live),
            "n_mirror": len(mirror),
            "used_for_verdict": len(live),
        },
        "season_days": SEASON_DAYS,
        "surplus_ratio_threshold": args.surplus_ratio,
        "wool_zero_drain": {
            "realised_frac_live": frac_no_yarn,
            "n_no_yarn": n_no_yarn,
            "n_live": len(live),
            "roadmap_population_values": {"machine_s4": 0.344, "measured_s52": 0.340, "row25": 0.40},
        },
        "per_product": out_products,
        "k0": {
            "product": "WOOL",
            "median_ratio_U_over_absorb": wool["ratio_U_over_absorb_median"],
            "triggered": k0_kill,
            "verdict": ("STRUCTURAL SURPLUS — STOP, correct row 31" if k0_kill
                        else "within clearable schedule — proceed to Phase 0 attribution"),
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
