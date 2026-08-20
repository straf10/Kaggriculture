#!/usr/bin/env python3
"""S6 step 2e — the loss tail: why we lose a quarter of our episodes badly (desk, zero episodes).

Five passes (2a, 2b/0.5, 2c, 2d) priced the vote's erasure as a MEAN dollars-per-episode and closed
each below the gate. But the ladder pays in EPISODES WON. A mechanism that costs little on average
but cascades in a few episodes flips those episodes and moves rating.

Measured on every held ladder episode of 55586926 (self-play validation episodes excluded).
First run on 84 (2026-08-18); RE-VALIDATED on 178 (2026-08-20, S7 leg 0) — r(drain,bank) 0,579 ->
0,605, partial r(desync|drain) +0,007 -> -0,029, flippable 2/84 -> 11/178. At the 84-episode read:
our bank spans p05 $53.9k to p90 $125.3k (2.14x), with 22/84 (26%) under $70k and a tail to $36.2k.
This pass asks what separates the tail from the top — and whether 2d's desync or §4.1b's town
composition carries it.

Legs:
  A — un-average the 2d instrument: per-episode decay/weed counters, regressed against bank.
  B — desync depth: walk the vote stream against each episode's actual board; count tile-level
      actions that are no-ops given the real tile state; correlate against bank.
  C — §4.1b control: shop composition → premium drain, how much of bank spread it explains,
      and whether desync adds anything after composition is partialled out.
  D — convert to episodes flipped: of the losses, how many had margin < desync cost?

No agent/ change, no episode, no upload (R27). Derived data gitignored (§2.4b / R11).

Usage:
    python analysis/s6_step2e.py run       # all four legs
    python analysis/s6_step2e.py report    # reprint saved JSON
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s6_step2b_phase05 import DERIVED, LIVE, _pearson

OUT = DERIVED / "s6_step2e.json"

# engine_reference/kaggriculture.py SHOPS — inlined to avoid the kaggle_environments import chain
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
WHEAT_UNIT_PRICE = 40.1
DOLLAR_PER_RATING_PT = 253.0
PREMIUM = {"STRAWBERRY", "WOOL", "MILK"}
TILE_OPS = {"WATER", "PLANT", "DIG", "HARVEST", "FERTILIZE",
            "BUILD_COOP", "BUILD_PASTURE", "FEED", "CARE", "COLLECT_FERTILIZER"}


def _tile_valid(op, tile):
    """True if a tile-level action is effective (not a silent no-op) given the tile."""
    if op == "WATER":
        return isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today")
    if op == "PLANT":
        return tile is None
    if op == "DIG":
        return tile is not None and not (isinstance(tile, dict) and "animal" in tile)
    if op == "HARVEST":
        return isinstance(tile, dict) and tile.get("yield_units", 0) > 0
    if op == "FERTILIZE":
        return isinstance(tile, dict) and tile.get("kind") == "PLANT"
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        return tile is None
    if op == "FEED":
        return isinstance(tile, dict) and "animal" in tile and not tile.get("fed_today")
    if op == "CARE":
        return isinstance(tile, dict) and "animal" in tile and not tile.get("cared_today")
    if op == "COLLECT_FERTILIZER":
        return isinstance(tile, dict) and "animal" in tile and tile.get("fertilizer_available")
    return True


def _tile_label(tile):
    if tile is None:
        return "empty"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, dict):
        k = tile.get("kind", "?")
        if k == "PLANT":
            return "WEED" if False else f"PLANT|{'w' if tile.get('watered_today') else 'd'}"
        if k == "WEED":
            return "WEED"
        if "animal" in tile:
            return f"{k}+{tile['animal']}"
        return k
    return str(tile)


def _premium_drain(shop_list):
    """Total premium-product drain units per shop tick for this town's composition."""
    d = defaultdict(int)
    for s in shop_list:
        prods = SHOPS.get(s, [])
        m = 2 if len(prods) == 1 else 1
        for p in prods:
            d[p] += m
    return sum(d[p] for p in PREMIUM), dict(d)


def _load_live():
    """Load every held ladder episode, excluding the STRAF-vs-STRAF validation episode."""
    files = sorted(glob.glob(str(LIVE / "*.json")) + glob.glob(str(LIVE / "*.json.gz")))
    if not files:
        raise SystemExit(f"no live replays at {LIVE} (§2.4b)")
    eps = []
    skipped = 0
    for f in files:
        d = json.load(gzip.open(f)) if f.endswith(".gz") else json.loads(Path(f).read_text())
        teams = d.get("info", {}).get("TeamNames", [None, None])
        if len(teams) == 2 and teams[0] == "STRAF" and teams[1] == "STRAF":
            skipped += 1
            continue
        seat = 1 if (len(teams) > 1 and teams[1] == "STRAF" and teams[0] != "STRAF") else 0
        eps.append((d, seat))
    assert skipped == 1, f"expected 1 STRAF-vs-STRAF validation episode, got {skipped}"
    return eps


def _extract(replay, seat):
    """Extract per-episode data for all four legs."""
    from harness.metrics import extract_metrics

    steps = replay["steps"]
    n_actions = len(steps) - 1
    player = steps[0][seat]["observation"]["player"]
    m = extract_metrics(replay, seat)

    bank = replay["rewards"][seat]
    opp_bank = replay["rewards"][1 - seat]
    margin = bank - opp_bank

    last_obs = steps[-1][seat]["observation"]
    shops = last_obs["town"]["unlocked_shops"]
    prem_drain, drain_map = _premium_drain(shops)

    # --- desync scan ---
    desyncs = []
    for i in range(n_actions):
        obs = steps[i][seat]["observation"]
        farm = obs["farms"][player]
        action = steps[i + 1][seat].get("action") or {}
        farmer_a = action.get("farmer", ["PASS"])
        hands_a = action.get("hands", [])
        if not isinstance(hands_a, list):
            hands_a = []

        all_actions = [farmer_a] + list(hands_a)
        positions = [farm.get("farmer", [0, 0])] + list(farm.get("hands", []))
        for u, ua in enumerate(all_actions):
            if u >= len(positions):
                break
            if not (isinstance(ua, list) and ua):
                continue
            op = ua[0]
            if op not in TILE_OPS:
                continue
            x, y = positions[u][0], positions[u][1]
            tile = farm["tiles"][y][x]
            if not _tile_valid(op, tile):
                desyncs.append({"step": i, "unit": u, "op": op, "tile": _tile_label(tile),
                                "day": obs.get("day", 0)})

    n_ds = len(desyncs)
    half = n_actions // 2
    first_half = sum(1 for d in desyncs if d["step"] < half)
    max_streak = 0
    if desyncs:
        streak = 1
        for j in range(1, n_ds):
            if desyncs[j]["step"] <= desyncs[j - 1]["step"] + 1:
                streak += 1
            else:
                max_streak = max(max_streak, streak)
                streak = 1
        max_streak = max(max_streak, streak)

    eid = replay.get("info", {}).get("EpisodeId", 0)
    return {
        "episode_id": eid, "seat": seat,
        "final_bank": bank, "opp_bank": opp_bank, "margin": margin,
        "outcome": "win" if margin > 0 else ("loss" if margin < 0 else "tie"),
        "plant_decay_units_lost": m.get("plant_decay_units_lost", 0),
        "unexpected_weeds_lost": m.get("unexpected_weeds_lost", 0),
        "water_weeds_lost": m.get("water_weeds_lost", 0),
        "decay_loss_dollars": round(m.get("plant_decay_units_lost", 0) * WHEAT_UNIT_PRICE, 1),
        "desync_total": n_ds,
        "desync_first_step": desyncs[0]["step"] if desyncs else None,
        "desync_first_half": first_half,
        "desync_front_frac": round(first_half / n_ds, 3) if n_ds else None,
        "desync_max_streak": max_streak,
        "desync_types": dict(Counter(f"{d['op']}→{d['tile']}" for d in desyncs).most_common(10)),
        "shops": dict(Counter(shops)),
        "premium_drain": prem_drain,
        "drain_by_product": drain_map,
        "realized_ppu": {k: round(v, 1) for k, v in m.get("realized_price_per_unit", {}).items()},
    }


def _pctl(vals, p):
    s = sorted(vals)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def _partial_r(x, y, z):
    """Partial Pearson r(x, y | z)."""
    rxz = _pearson(x, z)
    ryz = _pearson(y, z)
    rxy = _pearson(x, y)
    denom_sq = (1 - rxz ** 2) * (1 - ryz ** 2)
    if denom_sq <= 0:
        return None
    return (rxy - rxz * ryz) / denom_sq ** 0.5


def _ols_r2(x, y):
    """Simple linear R² and slope."""
    n = len(x)
    if n < 3:
        return None, None
    r = _pearson(x, y)
    if r is None:
        return None, None
    mx, my = sum(x) / n, sum(y) / n
    sx2 = sum((a - mx) ** 2 for a in x)
    if sx2 == 0:
        return 0.0, 0.0
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sx2
    return round(r ** 2, 4), round(slope, 2)


def _distrib(vals):
    s = sorted(vals)
    n = len(s)
    return {
        "n": n,
        "mean": round(statistics.fmean(vals), 2),
        "median": round(statistics.median(vals), 1),
        "stdev": round(statistics.stdev(vals), 2) if n > 1 else 0,
        "min": s[0], "max": s[-1],
        "p05": s[max(0, int(n * 0.05))],
        "p10": s[max(0, int(n * 0.10))],
        "p25": s[max(0, int(n * 0.25))],
        "p75": s[min(n - 1, int(n * 0.75))],
        "p90": s[min(n - 1, int(n * 0.90))],
        "p95": s[min(n - 1, int(n * 0.95))],
    }


def leg_a(data):
    banks = [e["final_bank"] for e in data]
    decay = [e["plant_decay_units_lost"] for e in data]
    weeds = [e["unexpected_weeds_lost"] for e in data]

    sub70k = [e for e in data if e["final_bank"] < 70000]
    top_q = sorted(data, key=lambda e: e["final_bank"], reverse=True)[:len(data) // 4]
    wins = [e for e in data if e["outcome"] == "win"]
    losses = [e for e in data if e["outcome"] == "loss"]

    r2_decay, slope_decay = _ols_r2(decay, banks)
    r2_weeds, slope_weeds = _ols_r2(weeds, banks)

    return {
        "decay_units_distrib": _distrib(decay),
        "weeds_distrib": _distrib(weeds),
        "sub70k": {
            "n": len(sub70k),
            "decay_mean": round(statistics.fmean([e["plant_decay_units_lost"] for e in sub70k]), 2) if sub70k else None,
            "weeds_mean": round(statistics.fmean([e["unexpected_weeds_lost"] for e in sub70k]), 2) if sub70k else None,
            "bank_mean": round(statistics.fmean([e["final_bank"] for e in sub70k])) if sub70k else None,
        },
        "top_quartile": {
            "n": len(top_q),
            "decay_mean": round(statistics.fmean([e["plant_decay_units_lost"] for e in top_q]), 2),
            "weeds_mean": round(statistics.fmean([e["unexpected_weeds_lost"] for e in top_q]), 2),
            "bank_mean": round(statistics.fmean([e["final_bank"] for e in top_q])),
        },
        "wins_vs_losses": {
            "wins_decay_mean": round(statistics.fmean([e["plant_decay_units_lost"] for e in wins]), 2) if wins else None,
            "losses_decay_mean": round(statistics.fmean([e["plant_decay_units_lost"] for e in losses]), 2) if losses else None,
        },
        "r_decay_bank": round(_pearson(decay, banks), 4) if _pearson(decay, banks) is not None else None,
        "r2_decay_bank": r2_decay,
        "slope_decay_bank": slope_decay,
        "r_weeds_bank": round(_pearson(weeds, banks), 4) if _pearson(weeds, banks) is not None else None,
        "r2_weeds_bank": r2_weeds,
        "uniform": "YES" if (max(decay) - min(decay)) <= 5 else "NO",
    }


def leg_b(data):
    banks = [e["final_bank"] for e in data]
    ds = [e["desync_total"] for e in data]
    first = [e["desync_first_step"] for e in data if e["desync_first_step"] is not None]
    streaks = [e["desync_max_streak"] for e in data]
    front = [e["desync_front_frac"] for e in data if e["desync_front_frac"] is not None]

    all_types = Counter()
    for e in data:
        for k, v in e["desync_types"].items():
            all_types[k] += v

    sub70k = [e for e in data if e["final_bank"] < 70000]
    top_q = sorted(data, key=lambda e: e["final_bank"], reverse=True)[:len(data) // 4]

    r_ds_bank = _pearson(ds, banks)
    r2, slope = _ols_r2(ds, banks)

    return {
        "desync_distrib": _distrib(ds),
        "first_step_distrib": _distrib(first) if first else None,
        "max_streak_distrib": _distrib(streaks),
        "front_frac_mean": round(statistics.fmean(front), 3) if front else None,
        "desync_types_total": dict(all_types.most_common(10)),
        "sub70k": {
            "n": len(sub70k),
            "desync_mean": round(statistics.fmean([e["desync_total"] for e in sub70k]), 2) if sub70k else None,
            "streak_mean": round(statistics.fmean([e["desync_max_streak"] for e in sub70k]), 2) if sub70k else None,
        },
        "top_quartile": {
            "n": len(top_q),
            "desync_mean": round(statistics.fmean([e["desync_total"] for e in top_q]), 2),
            "streak_mean": round(statistics.fmean([e["desync_max_streak"] for e in top_q]), 2),
        },
        "r_desync_bank": round(r_ds_bank, 4) if r_ds_bank is not None else None,
        "r2_desync_bank": r2,
        "slope_desync_bank": slope,
        "n_zero_desync": sum(1 for d in ds if d == 0),
    }


def leg_c(data):
    banks = [e["final_bank"] for e in data]
    drains = [e["premium_drain"] for e in data]
    ds = [e["desync_total"] for e in data]

    r_drain_bank = _pearson(drains, banks)
    r2_drain, slope_drain = _ols_r2(drains, banks)
    r_desync_bank = _pearson(ds, banks)
    r2_desync, _ = _ols_r2(ds, banks)
    r_drain_desync = _pearson(drains, ds)
    partial = _partial_r(banks, ds, drains)
    partial_drain = _partial_r(banks, drains, ds)

    drain_vals = sorted(set(drains))
    dose = {}
    for dv in drain_vals:
        eps = [e for e in data if e["premium_drain"] == dv]
        dose[dv] = {"n": len(eps),
                    "bank_median": round(statistics.median([e["final_bank"] for e in eps]))}

    per_product = {}
    for prod in PREMIUM:
        prod_drain = [e["drain_by_product"].get(prod, 0) for e in data]
        prod_ppu = [e["realized_ppu"].get(prod, 0) for e in data if prod in e["realized_ppu"]]
        r_pd = _pearson(prod_drain, banks) if len(prod_drain) == len(banks) else None
        per_product[prod] = {
            "drain_distrib": _distrib(prod_drain),
            "ppu_distrib": _distrib(prod_ppu) if len(prod_ppu) >= 3 else None,
            "r_drain_bank": round(r_pd, 4) if r_pd is not None else None,
        }

    return {
        "premium_drain_distrib": _distrib(drains),
        "r_drain_bank": round(r_drain_bank, 4) if r_drain_bank is not None else None,
        "r2_drain_bank": r2_drain,
        "slope_drain_bank": slope_drain,
        "r_desync_bank_raw": round(r_desync_bank, 4) if r_desync_bank is not None else None,
        "r2_desync_bank_raw": r2_desync,
        "r_drain_desync": round(r_drain_desync, 4) if r_drain_desync is not None else None,
        "partial_r_desync_given_drain": round(partial, 4) if partial is not None else None,
        "partial_r_drain_given_desync": round(partial_drain, 4) if partial_drain is not None else None,
        "dose_response": dose,
        "per_product": per_product,
    }


def leg_d(data):
    losses = [e for e in data if e["outcome"] == "loss"]
    n_total = len(data)
    n_loss = len(losses)

    flipped = 0
    details = []
    for e in losses:
        abs_margin = abs(e["margin"])
        cost = e["decay_loss_dollars"]
        would_flip = abs_margin < cost
        if would_flip:
            flipped += 1
        details.append({
            "episode_id": e["episode_id"],
            "margin": round(e["margin"]),
            "decay_cost": round(cost, 1),
            "would_flip": would_flip,
        })

    details.sort(key=lambda x: abs(x["margin"]))
    return {
        "n_total": n_total,
        "n_losses": n_loss,
        "n_flippable": flipped,
        "flipped_share_of_total": round(flipped / n_total, 4) if n_total else 0,
        "rating_upper_bound_pts": round(flipped / n_total * 100, 1) if n_total else 0,
        "note": ("upper bound: assumes every recovered dollar converts to a win; "
                 "stated beside $597/ep mean, not replacing it"),
        "closest_losses": details[:10],
    }


def _verdict(a, b, c, d):
    """Build the verdict string (R35)."""
    uniform = a["uniform"] == "YES"
    r_drain = c.get("r_drain_bank") or 0
    r_desync_raw = c.get("r_desync_bank_raw") or 0
    partial_desync = c.get("partial_r_desync_given_drain") or 0
    n_flip = d["n_flippable"]
    n_total = d["n_total"]
    dd = a["decay_units_distrib"]

    if uniform and abs(r_drain) > 0.4 and abs(partial_desync) < 0.15:
        branch = "(i)+(iv)"
        reading = (
            f"BOTH branches fire in the same direction. "
            f"(iv): decay counters are UNIFORM (range {dd['min']}-{dd['max']}, stdev {dd['stdev']}); "
            f"the own-farm loss is a fixed ~${dd['mean']*WHEAT_UNIT_PRICE:.0f}/ep cost of the open-loop "
            f"stream, not a variable — leg B's hypothesis (desync cascades in the tail) is dead before "
            f"leg B runs. (i): the tail IS the town's shop composition — "
            f"r(drain, bank)={r_drain:.3f} (R²={c['r2_drain_bank']}), each tick of premium drain worth "
            f"~${c['slope_drain_bank']:,.0f}; r(desync, bank)={r_desync_raw:.3f} (zero); "
            f"partial r(desync|drain)={partial_desync:.3f} — desync adds NOTHING after composition. "
            f"2d's shelving stands; the bank spread is §4.1b operating as measured."
        )
    elif abs(r_drain) > 0.4 and abs(partial_desync) < 0.15:
        branch = "(i)"
        reading = (f"The tail IS the town's shop composition. r(drain, bank)={r_drain:.3f} "
                   f"(R²={c['r2_drain_bank']}); partial r(desync|drain)={partial_desync:.3f} "
                   f"— desync adds NOTHING after composition. 2d's shelving stands.")
    elif abs(partial_desync) > 0.2:
        branch = "(ii)"
        reading = (f"Desync depth CARRIES the tail after composition is controlled: "
                   f"partial r={partial_desync:.3f}. 2d's bound was priced in the wrong currency. "
                   f"Flipped episodes: {n_flip}/{n_total}.")
    elif uniform:
        branch = "(iv)"
        reading = (f"Decay counters are UNIFORM (range {dd['min']}-{dd['max']}); no tail in "
                   f"weeds/decay. Leg B's desync hypothesis is dead before it runs.")
    else:
        branch = "(iii)"
        reading = (f"NEITHER explains the tail fully. r(drain,bank)={r_drain:.3f}, "
                   f"r(desync,bank)={r_desync_raw:.3f}, partial r(desync|drain)={partial_desync:.3f}. "
                   f"A third owner (opponent, seat, unmeasured counter) likely.")

    return (f"BRANCH {branch}. {reading} "
            f"Episodes flippable by full recovery: {n_flip}/{n_total} (upper bound, +{d['rating_upper_bound_pts']:.1f} pts). "
            f"No agent/ change, no episode, no upload (R27).")


def run():
    print("loading ladder episodes...")
    eps = _load_live()
    print(f"  {len(eps)} ladder episodes loaded (1 STRAF-vs-STRAF excluded)")

    print("extracting per-episode data (metrics + desync scan)...")
    data = [_extract(d, seat) for d, seat in eps]

    print(f"  banks: median ${statistics.median(e['final_bank'] for e in data):,.0f}, "
          f"range ${min(e['final_bank'] for e in data):,.0f}-${max(e['final_bank'] for e in data):,.0f}")

    a = leg_a(data)
    b = leg_b(data)
    c = leg_c(data)
    d = leg_d(data)
    v = _verdict(a, b, c, d)

    # corrections the brief requires
    corrections = [
        ("opponent_pool_circular",
         "Leg B of 2d attributes most of the $4,718/ep bank gap to the donor's opponents banking "
         "$88.0k vs our $79.3k. Kaggle pairs by rating, so opponent strength is a CONSEQUENCE of "
         "the rating difference, not a cause. The causal gloss is circular; the margin comparison stands."),
        ("R36_no_rating_field",
         "R36 prescribes reading opponent rating from episode metadata. Verified across all 85 live "
         "replays: info carries Agents, EpisodeId, LiveVideoPath, TeamNames, seed — NO rating field. "
         "The team-name proxy it warns against is the only axis that exists. Amend R36."),
        ("set_is_84_not_85",
         "The 85th live file is STRAF-vs-STRAF validation. Every per-episode average computed over "
         "'85 live episodes' (2d's $597/ep, leg B's $85,468 median) includes it. The set is 84."),
    ]

    rec = {
        "n_episodes": len(data),
        "legA": a, "legB": b, "legC": c, "legD": d,
        "verdict": v,
        "corrections": corrections,
        "bank_distrib": _distrib([e["final_bank"] for e in data]),
        "margin_distrib": _distrib([e["margin"] for e in data]),
        "win_rate": round(sum(1 for e in data if e["outcome"] == "win") / len(data), 4),
        "per_episode": data,
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, separators=(",", ":")))
    _print(rec)
    print(f"\nwrote {OUT} (gitignored)")
    return rec


def _print(rec):
    a, b, c, d = rec["legA"], rec["legB"], rec["legC"], rec["legD"]
    bd = rec["bank_distrib"]
    print(f"\n{'='*80}")
    print(f"S6 step 2e — the loss tail ({rec['n_episodes']} ladder episodes)")
    print(f"{'='*80}")
    print(f"\nVERDICT: {rec['verdict']}")

    print(f"\nBank: median ${bd['median']:,.0f} · p10 ${bd['p10']:,.0f} · p90 ${bd['p90']:,.0f} · "
          f"range ${bd['min']:,.0f}-${bd['max']:,.0f} · p90/p10 = {bd['p90']/bd['p10']:.2f}x")
    print(f"Win rate: {rec['win_rate']:.1%} ({sum(1 for e in rec['per_episode'] if e['outcome']=='win')}"
          f"W / {sum(1 for e in rec['per_episode'] if e['outcome']=='loss')}L)")

    print(f"\n--- Leg A: decay/weed counters (un-averaged) ---")
    dd = a["decay_units_distrib"]
    wd = a["weeds_distrib"]
    print(f"  decay units/ep: mean {dd['mean']:.1f} · median {dd['median']:.0f} · "
          f"range {dd['min']}-{dd['max']} · stdev {dd['stdev']:.1f}")
    print(f"  weeds/ep:       mean {wd['mean']:.1f} · median {wd['median']:.0f} · "
          f"range {wd['min']}-{wd['max']} · stdev {wd['stdev']:.1f}")
    print(f"  UNIFORM? {a['uniform']} (range {dd['max']-dd['min']})")
    s7, tq = a["sub70k"], a["top_quartile"]
    print(f"  sub-$70k ({s7['n']} ep): decay {s7['decay_mean']:.1f}/ep, weeds {s7['weeds_mean']:.1f}/ep")
    print(f"  top-Q    ({tq['n']} ep): decay {tq['decay_mean']:.1f}/ep, weeds {tq['weeds_mean']:.1f}/ep")
    print(f"  r(decay, bank)={a['r_decay_bank']} (R²={a['r2_decay_bank']})")

    print(f"\n--- Leg B: desync depth ---")
    dsd = b["desync_distrib"]
    print(f"  desyncs/ep: mean {dsd['mean']:.1f} · median {dsd['median']:.0f} · "
          f"range {dsd['min']}-{dsd['max']} · stdev {dsd['stdev']:.1f}")
    print(f"  zero-desync episodes: {b['n_zero_desync']}")
    print(f"  max streak mean: {b['max_streak_distrib']['mean']:.1f}")
    print(f"  front-loaded fraction: {b['front_frac_mean']}")
    print(f"  top desync types: {b['desync_types_total']}")
    s7b, tqb = b["sub70k"], b["top_quartile"]
    print(f"  sub-$70k ({s7b['n']} ep): desync {s7b['desync_mean']:.1f}/ep, streak {s7b['streak_mean']:.1f}")
    print(f"  top-Q    ({tqb['n']} ep): desync {tqb['desync_mean']:.1f}/ep, streak {tqb['streak_mean']:.1f}")
    print(f"  r(desync, bank)={b['r_desync_bank']} (R²={b['r2_desync_bank']})")

    print(f"\n--- Leg C: §4.1b control (shop composition) ---")
    pd = c["premium_drain_distrib"]
    print(f"  premium drain/tick: mean {pd['mean']:.1f} · range {pd['min']}-{pd['max']}")
    print(f"  r(drain, bank)={c['r_drain_bank']} (R²={c['r2_drain_bank']}; slope=${c['slope_drain_bank']}/tick)")
    print(f"  r(desync, bank) raw={c['r_desync_bank_raw']}")
    print(f"  r(drain, desync)={c['r_drain_desync']}")
    print(f"  partial r(desync | drain)={c['partial_r_desync_given_drain']}")
    print(f"  partial r(drain | desync)={c['partial_r_drain_given_desync']}")
    print(f"  dose-response: {c['dose_response']}")
    for prod in sorted(c["per_product"]):
        pp = c["per_product"][prod]
        print(f"    {prod}: r(drain,bank)={pp['r_drain_bank']}, "
              f"drain range {pp['drain_distrib']['min']}-{pp['drain_distrib']['max']}")

    print(f"\n--- Leg D: episodes flipped ---")
    print(f"  losses: {d['n_losses']} of {d['n_total']}")
    print(f"  flippable by full recovery: {d['n_flippable']}/{d['n_total']} "
          f"({d['flipped_share_of_total']:.1%})")
    print(f"  rating upper bound: ~{d['rating_upper_bound_pts']:.1f} pts")
    print(f"  closest losses (margin vs cost):")
    for cl in d["closest_losses"][:5]:
        print(f"    ep {cl['episode_id']}: margin ${cl['margin']:+,} vs cost ${cl['decay_cost']:,.0f} "
              f"→ {'FLIP' if cl['would_flip'] else 'no'}")

    print(f"\n--- Corrections ---")
    for tag, text in rec["corrections"]:
        print(f"  [{tag}] {text[:120]}...")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "report":
        if not OUT.exists():
            raise SystemExit(f"{OUT} missing — run `run` first")
        _print(json.loads(OUT.read_text()))
        return 0

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
