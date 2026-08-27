#!/usr/bin/env python3
"""S9 — live read of submission 55726984 (H2 tail-liquidation on the ReCurSiON reconstruction).

Three panels, in the order the ROADMAP's evaluation rules allow them to be read:

  A — volume & the W/L panel.  Every ladder replay of `55726984` (validation and self-play
      excluded): win rate overall, by seat, by chronological block (burst vs post-burst).
  B — win rate against opponent strength.  The replays carry no rating at play time, so the only
      executable substitute is the opponent team's *current* public-board score.  That join is
      valid only where the opponent's `LastSubmissionDate` predates our episode — i.e. the agent
      on the board today is the one that played us.  Both the uncontrolled join and the
      controlled subset are reported, never mixed (s7 leg C, correction #2).
  C — the loss anatomy, with a dedicated cut for STRONG opponents.  Losses are split by
      normalised margin (marginal / mid / blowout), given a divergence day, and priced per
      product: units sold and revenue at the step price, ours vs the winner's.

Read-only.  No `agent/` change, no episode played, no upload.  Output is gitignored derived JSON.

Usage:
    python analysis/s9_live_read_55726984.py run
    python analysis/s9_live_read_55726984.py report
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import load as load_replay, replay_paths  # noqa: E402
from analysis.s9_market_ledger import episode_ledger, step_ledger  # noqa: E402
from engine_reference.kaggriculture import (  # noqa: E402
    CROPS, MARKET_I0, PRICE_FLOOR, SHOPS, TOWN_CENTER_PRODUCTS, market_price,
)
LIVE = ROOT / "data" / "archive" / "raw" / "live_55726984"
EP_CSV = ROOT / "data" / "derived" / "s9_live_55726984_episodes.csv"
DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "s9_live_read_55726984.json"
OUR_TEAM = "STRAF"
SUBMITTED_AT = dt.datetime(2026, 8, 23, 23, 7, 25)

# The strength zones §1 uses, extended upward: the 2.100+ bucket of the 43,4pct baseline is now
# most of the board's mass, so the top of it gets its own row.
ZONES = [("<1500", 0, 1500), ("1500-1700", 1500, 1700), ("1700-1900", 1700, 1900),
         ("1900-2100", 1900, 2100), ("2100-2400", 2100, 2400), ("2400+", 2400, 10 ** 9)]

PRODUCTS = ["STRAWBERRY", "MELON", "WOOL", "MILK", "EGG", "WHEAT", "CARROT", "TOMATO", "FERTILIZER"]


# --------------------------------------------------------------------------- io

def _lb_path():
    cands = sorted(glob.glob(str(ROOT / "data" / "archive" / "raw" / "live_leaderboard_*" / "*.csv")))
    cands += sorted(glob.glob(str(DERIVED / "kaggriculture-publicleaderboard-*.csv")))
    if not cands:
        raise SystemExit("no leaderboard snapshot found")
    return cands[-1]


def load_leaderboard(path=None):
    path = path or _lb_path()
    board = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            board[row["TeamName"]] = {
                "rank": int(row["Rank"]),
                "score": float(row["Score"]),
                "last_sub": dt.datetime.fromisoformat(row["LastSubmissionDate"]),
            }
    return board, Path(path).name


def load_episode_times():
    """episode_id -> createTime, from the `episodes -v` capture (ladder rows only)."""
    times = {}
    if not EP_CSV.exists():
        return times
    with open(EP_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            # The `episodes -v` capture ends with a CLI hint line, which DictReader
            # renders as a row whose later fields are None.  Skip anything malformed.
            if "PUBLIC" not in (row.get("type") or ""):
                continue
            if not (row.get("id") or "").strip().isdigit():
                continue
            times[int(row["id"])] = dt.datetime.fromisoformat(row["createTime"])
    return times


def _tile_days(steps, seat):
    """Crop tile-days and animal head-days, sampled once per game day."""
    crop, animals, seen = Counter(), Counter(), set()
    for st in steps[1:]:
        obs = st[seat]["observation"]
        day = obs["day"]
        if day in seen:
            continue
        seen.add(day)
        farm = obs["farms"][obs["player"]]
        for row in farm["tiles"]:
            for t in row:
                if not t or isinstance(t, str):
                    continue
                if t.get("kind") == "PLANT" and t.get("crop"):
                    crop[t["crop"]] += 1
                elif t.get("kind") == "PASTURE" and t.get("animal"):
                    animals[t["animal"]] += 1
        crop["_quadrants"] += len(farm.get("unlocked_quadrants") or [])
        crop["_hands"] += len(farm.get("hands") or [])
    return crop, animals


def _bank_curve(steps, seat):
    """money at the end of each game day."""
    curve = {}
    for st in steps[1:]:
        obs = st[seat]["observation"]
        curve[obs["day"]] = float(obs["farms"][obs["player"]]["money"])
    return curve


def load_live():
    # One reader for the whole codebase (ROADMAP §3 rule "reuse, do not duplicate"):
    # `s8_replay_io` accepts both `episode-*-replay.json` and `.json.gz`.  The local
    # `*.json` glob this used to carry went blind the moment the archive was gzipped.
    files = replay_paths("55726984")
    if not files:
        raise SystemExit(f"no replays at {LIVE}")
    eps, self_play, skipped = [], 0, 0
    for f in files:
        d = load_replay(f)
        info = d.get("info", {})
        teams = info.get("TeamNames", [None, None])
        if len(teams) != 2 or OUR_TEAM not in teams:
            skipped += 1
            continue
        if teams[0] == teams[1] == OUR_TEAM:
            self_play += 1
            continue
        seat = 1 if teams[1] == OUR_TEAM else 0
        steps = d["steps"]
        led = episode_ledger(d)
        us_rev, op_rev = led["revenue"][seat], led["revenue"][1 - seat]
        us_units, op_units = led["units"][seat], led["units"][1 - seat]
        us_day, op_day = led["by_day"][seat], led["by_day"][1 - seat]
        us_crop, us_anim = _tile_days(steps, seat)
        op_crop, op_anim = _tile_days(steps, 1 - seat)
        bank_us, bank_op = _bank_curve(steps, seat), _bank_curve(steps, 1 - seat)
        bank = float(d["rewards"][seat])
        opp_bank = float(d["rewards"][1 - seat])
        eps.append({
            "episode_id": info.get("EpisodeId"),
            "seed": info.get("seed"),
            "seat": seat,
            "opponent": teams[1 - seat],
            "bank": bank,
            "opp_bank": opp_bank,
            "margin": bank - opp_bank,
            "margin_norm": (bank - opp_bank) / max(bank, opp_bank, 1.0),
            "win": bank > opp_bank,
            "shops": len((steps[-1][seat]["observation"]["town"] or {}).get("unlocked_shops") or []),
            "sales_units": dict(us_units), "sales_rev": dict(us_rev),
            "opp_sales_units": dict(op_units), "opp_sales_rev": dict(op_rev),
            "sales_by_day": dict(us_day), "opp_sales_by_day": dict(op_day),
            "units_ordered": led["units_ordered"][seat],
            "opp_units_ordered": led["units_ordered"][1 - seat],
            "spend": led["spend"][seat], "opp_spend": led["spend"][1 - seat],
            "fill": led["fill"][seat], "opp_fill": led["fill"][1 - seat],
            "crop": dict(us_crop), "anim": dict(us_anim),
            "opp_crop": dict(op_crop), "opp_anim": dict(op_anim),
            "bank_curve": {str(k): v for k, v in bank_us.items()},
            "opp_bank_curve": {str(k): v for k, v in bank_op.items()},
        })
    eps.sort(key=lambda e: e["episode_id"] or 0)
    return eps, self_play, skipped


# --------------------------------------------------------------------------- panels

def _wr(eps):
    return (sum(e["win"] for e in eps) / len(eps)) if eps else None


def _summ(eps):
    return {"n": len(eps), "wins": sum(e["win"] for e in eps), "losses": sum(not e["win"] for e in eps),
            "win_rate": _wr(eps),
            "margin_median": statistics.median([e["margin"] for e in eps]) if eps else None,
            "bank_median": statistics.median([e["bank"] for e in eps]) if eps else None}


def panel_a(eps, times):
    n = len(eps)
    third = max(1, n // 3)
    blocks = [("first", eps[:third]), ("middle", eps[third:2 * third]), ("last", eps[2 * third:])]
    # burst split: the placement burst is the first hours after the upload
    burst, post = [], []
    for e in eps:
        t = times.get(e["episode_id"])
        (burst if (t and (t - SUBMITTED_AT).total_seconds() <= 5 * 3600) else post).append(e)
    by_opp = defaultdict(list)
    for e in eps:
        by_opp[e["opponent"]].append(e)
    return {
        "n_ladder": n,
        "self_play_excluded": None,
        "overall": _summ(eps),
        "by_seat": {str(s): _summ([e for e in eps if e["seat"] == s]) for s in (0, 1)},
        "blocks": [{"block": b, **_summ(v)} for b, v in blocks],
        "burst_vs_post": {"burst<=5h": _summ(burst), "post_burst": _summ(post)},
        "distinct_opponents": len(by_opp),
        "repeat_opponents": {k: len(v) for k, v in sorted(by_opp.items(), key=lambda kv: -len(kv[1])) if len(v) > 1},
        "margin_median_win": statistics.median([e["margin"] for e in eps if e["win"]] or [0]),
        "margin_median_loss": statistics.median([e["margin"] for e in eps if not e["win"]] or [0]),
        "margin_norm_deciles": [round(statistics.quantiles([e["margin_norm"] for e in eps], n=10)[i], 4)
                                for i in range(9)] if n >= 10 else None,
    }


def panel_b(eps, board, times):
    rows_all, rows_ctrl = [], []
    unmatched = []
    for e in eps:
        info = board.get(e["opponent"])
        if not info:
            unmatched.append(e["opponent"])
            continue
        r = dict(e_id=e["episode_id"], opp=e["opponent"], opp_score=info["score"], opp_rank=info["rank"],
                 win=e["win"], margin=e["margin"], margin_norm=e["margin_norm"], seat=e["seat"])
        rows_all.append(r)
        t = times.get(e["episode_id"])
        if t and info["last_sub"] < t:
            rows_ctrl.append(r)

    def zone_table(rows):
        out = []
        for name, lo, hi in ZONES:
            sub = [r for r in rows if lo <= r["opp_score"] < hi]
            out.append({"zone": name, "n": len(sub), "wins": sum(r["win"] for r in sub),
                        "win_rate": (sum(r["win"] for r in sub) / len(sub)) if sub else None,
                        "margin_norm_median": (statistics.median([r["margin_norm"] for r in sub])
                                               if sub else None)})
        return out

    def rank_table(rows):
        cuts = [(1, 100), (101, 300), (301, 800), (801, 2000), (2001, 10 ** 9)]
        out = []
        for lo, hi in cuts:
            sub = [r for r in rows if lo <= r["opp_rank"] <= hi]
            out.append({"rank_band": f"{lo}-{hi if hi < 10**9 else 'end'}", "n": len(sub),
                        "wins": sum(r["win"] for r in sub),
                        "win_rate": (sum(r["win"] for r in sub) / len(sub)) if sub else None})
        return out

    return {
        "leaderboard_matched": len(rows_all), "unmatched_opponents": sorted(set(unmatched)),
        "uncontrolled": {"n": len(rows_all), "by_zone": zone_table(rows_all), "by_rank": rank_table(rows_all)},
        "controlled": {"n": len(rows_ctrl), "by_zone": zone_table(rows_ctrl), "by_rank": rank_table(rows_ctrl),
                       "note": "opponent LastSubmissionDate precedes our episode createTime"},
        "our_rows": sorted(rows_all, key=lambda r: -r["opp_score"]),
    }


def _divergence_day(e):
    """First game day after which the winner's bank stays ahead of the loser's to the end."""
    us, op = e["bank_curve"], e["opp_bank_curve"]
    days = sorted(int(d) for d in us if str(d) in op or d in op)
    lead_is_opp = not e["win"]
    last_flip = None
    for d in days:
        a, b = us[str(d)], op[str(d)]
        ahead_opp = b > a
        if ahead_opp != lead_is_opp:
            last_flip = d
    return (last_flip + 1) if last_flip is not None else 0


def panel_c(eps, board, strong_cut):
    losses = [e for e in eps if not e["win"]]

    def bucket(e):
        m = -e["margin_norm"]
        return "marginal" if m < 0.10 else ("mid" if m < 0.40 else "blowout")

    cats = defaultdict(list)
    for e in losses:
        cats[bucket(e)].append(e)

    def product_ledger(sub):
        rows = []
        for p in PRODUCTS:
            ours = sum(e["sales_rev"].get(p, 0.0) for e in sub)
            theirs = sum(e["opp_sales_rev"].get(p, 0.0) for e in sub)
            u_ours = sum(e["sales_units"].get(p, 0) for e in sub)
            u_theirs = sum(e["opp_sales_units"].get(p, 0) for e in sub)
            rows.append({"product": p, "our_revenue": round(ours), "winner_revenue": round(theirs),
                         "net_to_winner": round(theirs - ours),
                         "our_units": u_ours, "winner_units": u_theirs,
                         "per_episode_net": round((theirs - ours) / len(sub)) if sub else 0})
        return sorted(rows, key=lambda r: -r["net_to_winner"])

    def mix(sub, key):
        c = Counter()
        for e in sub:
            for k, v in e[key].items():
                c[k] += v
        n = max(1, len(sub))
        return {k: round(v / n, 1) for k, v in c.most_common()}

    def sell_phase(sub, key):
        """Revenue share by game-day third: days 0-9 / 10-19 / 20-29."""
        agg = [0.0, 0.0, 0.0]
        for e in sub:
            for d, v in e[key].items():
                agg[min(2, int(d) // 10)] += v
        tot = sum(agg) or 1.0
        return [round(x / tot, 4) for x in agg]

    def fills(sub, key):
        vals = [e[key]["mean_fill"] for e in sub if e[key].get("mean_fill") is not None]
        return round(statistics.median(vals), 4) if vals else None

    def spend_mix(sub, key):
        c = Counter()
        for e in sub:
            for k, v in e[key].items():
                c[k] += v
        n = max(1, len(sub))
        return {k: round(v / n) for k, v in c.most_common()}

    def block(sub, label):
        if not sub:
            return {"label": label, "n": 0}
        return {
            "our_fill_median": fills(sub, "fill"), "winner_fill_median": fills(sub, "opp_fill"),
            "our_spend_per_ep": spend_mix(sub, "spend"),
            "winner_spend_per_ep": spend_mix(sub, "opp_spend"),
            "label": label, "n": len(sub),
            "median_margin_norm": round(statistics.median([e["margin_norm"] for e in sub]), 4),
            "median_margin_abs": statistics.median([e["margin"] for e in sub]),
            "median_bank_us": statistics.median([e["bank"] for e in sub]),
            "median_bank_winner": statistics.median([e["opp_bank"] for e in sub]),
            "median_divergence_day": statistics.median([_divergence_day(e) for e in sub]),
            "product_ledger": product_ledger(sub),
            "our_crop_tiledays": mix(sub, "crop"), "winner_crop_tiledays": mix(sub, "opp_crop"),
            "our_animals": mix(sub, "anim"), "winner_animals": mix(sub, "opp_anim"),
            "our_sell_phase": sell_phase(sub, "sales_by_day"),
            "winner_sell_phase": sell_phase(sub, "opp_sales_by_day"),
        }

    strong_losses = [e for e in losses
                     if (board.get(e["opponent"]) or {}).get("score", 0) >= strong_cut]
    strong_wins = [e for e in eps if e["win"]
                   and (board.get(e["opponent"]) or {}).get("score", 0) >= strong_cut]
    weak_losses = [e for e in losses
                   if (board.get(e["opponent"]) or {}).get("score", 0) < strong_cut]

    def exec_panel(sub, label):
        if not sub:
            return {"label": label, "n": 0}
        our = [e["fill"]["mean_fill"] for e in sub if e["fill"].get("mean_fill") is not None]
        opp = [e["opp_fill"]["mean_fill"] for e in sub if e["opp_fill"].get("mean_fill") is not None]
        lost = [(e["fill"]["revenue_before_scaling"] - e["fill"]["revenue_after_scaling"]) for e in sub]
        lost_o = [(e["opp_fill"]["revenue_before_scaling"] - e["opp_fill"]["revenue_after_scaling"]) for e in sub]
        return {"label": label, "n": len(sub),
                "our_fill_median": round(statistics.median(our), 4) if our else None,
                "opp_fill_median": round(statistics.median(opp), 4) if opp else None,
                "our_dropped_sell_dollars_median": round(statistics.median(lost)) if lost else None,
                "opp_dropped_sell_dollars_median": round(statistics.median(lost_o)) if lost_o else None}

    return {
        "n_losses": len(losses),
        "strong_cut": strong_cut,
        "execution": [exec_panel([e for e in eps if e["win"]], "wins"),
                      exec_panel(losses, "losses"),
                      exec_panel(strong_losses, "losses vs strong"),
                      exec_panel(eps, "all")],
        "by_margin": [block(cats[k], k) for k in ("marginal", "mid", "blowout")],
        "vs_strong": block(strong_losses, f"losses vs opp score >= {strong_cut}"),
        "vs_weak": block(weak_losses, f"losses vs opp score < {strong_cut}"),
        "wins_vs_strong": block(strong_wins, f"wins vs opp score >= {strong_cut}"),
    }


def panel_d_timing(eps):
    """Where the money is left: realised $/unit per product, and the sell-timing split.

    Both halves are needed to tell a *volume* gap (we never grow/collect the good) from a
    *timing* gap (we hold the same units into a price we ourselves crushed).
    """
    rows = []
    for p in PRODUCTS:
        ou = sum(e["sales_units"].get(p, 0) for e in eps)
        orv = sum(e["sales_rev"].get(p, 0.0) for e in eps)
        pu = sum(e["opp_sales_units"].get(p, 0) for e in eps)
        prv = sum(e["opp_sales_rev"].get(p, 0.0) for e in eps)
        if ou + pu == 0:
            continue
        rows.append({
            "product": p,
            "our_units_per_ep": round(ou / len(eps), 1), "opp_units_per_ep": round(pu / len(eps), 1),
            "our_dollars_per_ep": round(orv / len(eps)), "opp_dollars_per_ep": round(prv / len(eps)),
            "our_price_per_unit": round(orv / ou, 1) if ou else None,
            "opp_price_per_unit": round(prv / pu, 1) if pu else None,
            "price_ratio": round((orv / ou) / (prv / pu), 3) if ou and pu else None,
            "dollars_per_ep_gap": round((prv - orv) / len(eps)),
        })
    return sorted(rows, key=lambda r: -r["dollars_per_ep_gap"])


def panel_e_flip(eps):
    """How far a loss actually is: the gap on one product vs the margin that decided the game."""
    losses = [e for e in eps if not e["win"]]
    if not losses:
        return {}
    out = {"n_losses": len(losses),
           "median_abs_margin": statistics.median(-e["margin"] for e in losses),
           "losses_inside": {f"${n}": sum(1 for e in losses if -e["margin"] < n)
                             for n in (1000, 2000, 3000, 5000, 8000, 12000)},
           "close_one_product_gap": [], "keep_units_take_their_price": []}
    for p in PRODUCTS:
        gaps = [e["opp_sales_rev"].get(p, 0.0) - e["sales_rev"].get(p, 0.0) for e in losses]
        out["close_one_product_gap"].append({
            "product": p, "flips": sum(1 for e, g in zip(losses, gaps) if g > -e["margin"]),
            "median_gap": round(statistics.median(gaps)), "mean_gap": round(statistics.mean(gaps))})
        gain, flips = 0.0, 0
        for e in losses:
            ou, orv = e["sales_units"].get(p, 0), e["sales_rev"].get(p, 0.0)
            pu, prv = e["opp_sales_units"].get(p, 0), e["opp_sales_rev"].get(p, 0.0)
            if not ou or not pu:
                continue
            g = ou * (prv / pu) - orv
            gain += g
            if g > -e["margin"]:
                flips += 1
        out["keep_units_take_their_price"].append(
            {"product": p, "mean_dollars_per_ep": round(gain / len(losses)), "flips": flips})
    out["close_one_product_gap"].sort(key=lambda r: -r["flips"])
    out["keep_units_take_their_price"].sort(key=lambda r: -r["flips"])
    return out


def panel_f_profile(eps):
    """What each side actually did, wins vs losses, side by side.

    Our route is a fixed tape, so any win/loss difference on OUR side is either the town or a
    desync — never a decision.  The opponent side is the one that can move, and the delta between
    the two columns is what the ladder is actually rewarding.
    """
    wins = [e for e in eps if e["win"]]
    losses = [e for e in eps if not e["win"]]

    def prof(sub, who):
        n = max(1, len(sub))
        pre = "" if who == "us" else "opp_"
        rev = f"{pre}sales_rev" if who == "us" else "opp_sales_rev"
        uni = "sales_units" if who == "us" else "opp_sales_units"
        rev = "sales_rev" if who == "us" else "opp_sales_rev"
        crop = "crop" if who == "us" else "opp_crop"
        anim = "anim" if who == "us" else "opp_anim"
        spend = "spend" if who == "us" else "opp_spend"
        byday = "sales_by_day" if who == "us" else "opp_sales_by_day"
        fill = "fill" if who == "us" else "opp_fill"
        bank = "bank" if who == "us" else "opp_bank"

        def agg(key):
            c = Counter()
            for e in sub:
                for k, v in e[key].items():
                    c[k] += v
            return {k: round(v / n, 1) for k, v in c.items()}

        phase = [0.0, 0.0, 0.0]
        for e in sub:
            for d, v in e[byday].items():
                phase[min(2, int(d) // 10)] += v
        tot = sum(phase) or 1.0
        fills = [e[fill]["mean_fill"] for e in sub if e[fill].get("mean_fill") is not None]
        units, dollars = agg(uni), agg(rev)
        return {
            "n": len(sub),
            "bank_median": statistics.median([e[bank] for e in sub]) if sub else None,
            "gross_sales_per_ep": round(sum(sum(e[rev].values()) for e in sub) / n),
            "spend_per_ep": round(sum(sum(e[spend].values()) for e in sub) / n),
            "spend_split": agg(spend),
            "crop_tiledays": agg(crop), "animal_headdays": agg(anim),
            "sell_phase_share": [round(x / tot, 3) for x in phase],
            "sell_fill_median": round(statistics.median(fills), 3) if fills else None,
            "units_per_ep": units,
            "price_per_unit": {k: round(dollars[k] / units[k], 1) for k in units if units.get(k)},
        }

    out = {}
    for who in ("us", "opponent"):
        w, l = prof(wins, who), prof(losses, who)
        out[who] = {"wins": w, "losses": l}
    return out


# ------------------------------------------------------------------ S14 MELON panel

MELON_OUT = DERIVED / "s14_melon_rephasing.json"
# Our recorded MELON sell window (the wave-2/3 harvest lands here and is dumped same-day).
MELON_BLOCK_DAYS = (20, 21, 22)
# The town centre eats 1 unit of every TOWN_CENTER_PRODUCT per day and NO shop lists MELON,
# so MELON's only sink is 1 unit/day.  Asserted in `_melon_sink_per_day` so an engine bump
# that gives a shop a melon breaks the panel instead of silently invalidating it.


def _melon_sink_per_day():
    shops = sum(1 for products in SHOPS.values() if "MELON" in products)
    assert shops == 0, f"a shop now consumes MELON ({shops}); the S14 drain model is stale"
    assert "MELON" in TOWN_CENTER_PRODUCTS
    return 1


def _melon_tiles(steps, seat):
    """Every MELON tile the tape ever plants: (x, y, planted_day) -> life history.

    Read off the recorded tile grid rather than the action stream: `planted_day` and
    `yield_units` are carried on the tile itself, so the wave structure is ground truth.
    """
    seen, prev = {}, {}
    for st in steps[1:]:
        o = st[seat]["observation"]
        farm = o["farms"][o["player"]]
        cur = {}
        for y, row in enumerate(farm["tiles"]):
            for x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "MELON":
                    k = (x, y, t["planted_day"])
                    cur[k] = t
                    r = seen.setdefault(k, {"planted_day": t["planted_day"], "xy": (x, y),
                                            "quadrant": _quadrant(x, y, len(farm["tiles"])),
                                            "max_yield": 0})
                    r["max_yield"] = max(r["max_yield"], t["yield_units"])
        for k, t in prev.items():
            if k not in cur and "harvest_day" not in seen[k]:
                seen[k]["harvest_day"] = o["day"]
                seen[k]["harvest_units"] = t["yield_units"]
        prev = cur
    return seen


def _quadrant(x, y, board_size):
    half = board_size // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def _wave_signature(steps, seat):
    waves = defaultdict(Counter)
    for r in _melon_tiles(steps, seat).values():
        waves[r["planted_day"]][
            f'{r["quadrant"]}|harvest_d{r.get("harvest_day")}|units{r.get("harvest_units")}'] += 1
    return json.dumps({str(d): dict(c) for d, c in sorted(waves.items())}, sort_keys=True)


def _land_clock(steps, seat):
    """The two facts that decide whether an earlier wave can be planted at all:
    when each quadrant unlocks, and how much free land / cash exists at that moment."""
    marks, prev = [], 1
    for st in steps[1:]:
        o = st[seat]["observation"]
        farm = o["farms"][o["player"]]
        q = len(farm.get("unlocked_quadrants") or [])
        if q > prev:
            free = sum(1 for row in farm["tiles"] for t in row if t is None)
            marks.append({"n_quadrants": q, "day": o["day"], "hour": o["hour"],
                          "_free_tiles": free, "_money": round(float(farm["money"]))})
            prev = q
    return marks


def _daily_farm(steps, seat):
    """Per game day: free land and cash at the FIRST step and at their best moment in the day.

    The daily peak matters: NE unlocks at day 6 hour 17, so a first-step sample reports the
    pre-unlock farm and hides a real planting window.  Shed stock is read at the first step —
    that is the S12 question (what is carried overnight), not what passes through in a turn.
    """
    out = {}
    for st in steps[1:]:
        o = st[seat]["observation"]
        farm = o["farms"][o["player"]]
        free = sum(1 for row in farm["tiles"] for t in row if t is None)
        money = float(farm["money"])
        r = out.get(o["day"])
        if r is None:
            out[o["day"]] = {
                "free_tiles": free, "free_tiles_max": free,
                "money": money, "money_max": money,
                "melon_seeds": o["private"]["seeds"].get("MELON", 0),
                "shed_melon": o["private"]["shed"].get("MELON", 0),
                "shed_wool": o["private"]["shed"].get("WOOL", 0),
            }
        else:
            r["free_tiles_max"] = max(r["free_tiles_max"], free)
            r["money_max"] = max(r["money_max"], money)
    return out


def _melon_flow(steps, seat):
    """Per game day: our MELON units/revenue, the opponent's, and the recorded market offset.

    Uses `s9_market_ledger.step_ledger` (the one market replayer) against the *recorded*
    pre-step inventory, so every quote is ground truth, and carries the same
    scale-to-recorded-cash correction `episode_ledger` applies for dropped SELLs.
    """
    ours, our_rev, opp, opp_rev, x_start = Counter(), Counter(), Counter(), Counter(), {}
    for t in range(1, len(steps)):
        pre, post = steps[t - 1][0]["observation"], steps[t][0]["observation"]
        day = post["day"]
        x_start.setdefault(day, pre["market"]["inventory"]["MELON"] - MARKET_I0)
        orders = [(steps[t][0].get("action") or {}).get("market") or [],
                  (steps[t][1].get("action") or {}).get("market") or []]
        if not orders[0] and not orders[1]:
            continue
        rev, un, sp, _ = step_ledger(
            pre["market"]["inventory"], orders,
            hires_today=[int(pre["farms"][p].get("hires_today", 0)) for p in (0, 1)],
            quadrants=[len(pre["farms"][p].get("unlocked_quadrants") or ["NW"]) for p in (0, 1)],
        )
        for pid in (0, 1):
            if not un[pid]["MELON"]:
                continue
            sim_rev, sim_spend = sum(rev[pid].values()), sum(sp[pid].values())
            cash = float(post["farms"][pid]["money"]) - float(pre["farms"][pid]["money"])
            scale = min(1.0, max(0.0, (cash + sim_spend) / sim_rev)) if sim_rev > 0 else 1.0
            if pid == seat:
                ours[day] += un[pid]["MELON"] * scale
                our_rev[day] += rev[pid]["MELON"] * scale
            else:
                opp[day] += un[pid]["MELON"] * scale
                opp_rev[day] += rev[pid]["MELON"] * scale
    return dict(ours), dict(our_rev), dict(opp), dict(opp_rev), x_start


def melon_day(x, n_us, n_op):
    """One day of MELON selling, both seats quoted at the SAME pre-commit inventory.

    This is the engine's `_process_market` per-unit lockstep (`kaggriculture.py:612`), not a
    sequential price walk: quoting one seat's whole order before the other's overstates the
    first seat and understates the second whenever the two overlap, which is exactly the
    d20 case this panel models.  Floor units do not raise inventory (`_commit_unit`).
    """
    a, b = int(round(n_us)), int(round(n_op))
    us = op = 0.0
    while a > 0 or b > 0:
        price = market_price("MELON", MARKET_I0 + x)
        committed = 0
        if a > 0:
            us += price
            a -= 1
            committed += 1 if price > PRICE_FLOOR else 0
        if b > 0:
            op += price
            b -= 1
            committed += 1 if price > PRICE_FLOOR else 0
        x += committed
    return us, op, x



def melon_season(ours, opp, x0, first_day=10, last_day=30):
    """Walk the MELON market from `first_day` to `last_day`, draining the town's 1 unit/day."""
    sink = _melon_sink_per_day()
    x = x0
    us_total = op_total = 0.0
    for day in range(first_day, last_day):
        u, o = ours.get(day, 0.0), opp.get(day, 0.0)
        if u or o:
            us, op, x = melon_day(x, u, o)
            us_total += us
            op_total += op
        x -= sink
    return us_total, op_total


def panel_g_melon(paths, eps_by_id, targets=range(11, 23)):
    """S14 — is the second MELON wave worth its tile-days, and can the waves be re-phased?

    Counterfactual: the whole d20-22 block is moved to a single earlier harvest day, our own
    self-crash is charged by walking the engine's own per-unit price, and the opponent's unit
    schedule is held as a tape.  That last assumption is the known limit and is reported.
    """
    waves, land_marks, flow, daily = Counter(), Counter(), {}, {}
    unlock_state = defaultdict(list)
    for path in paths:
        d = load_replay(path)
        info = d.get("info", {})
        teams = info.get("TeamNames", [None, None])
        if len(teams) != 2 or OUR_TEAM not in teams or teams[0] == teams[1]:
            continue
        seat = 1 if teams[1] == OUR_TEAM else 0
        steps, eid = d["steps"], info.get("EpisodeId")
        waves[_wave_signature(steps, seat)] += 1
        marks = _land_clock(steps, seat)
        land_marks[json.dumps([{k: v for k, v in mk.items() if not k.startswith("_")}
                               for mk in marks], sort_keys=True)] += 1
        for mk in marks:
            unlock_state[(mk["n_quadrants"], mk["day"], mk["hour"])].append(
                (mk["_free_tiles"], mk["_money"]))
        flow[eid] = _melon_flow(steps, seat)
        daily[eid] = _daily_farm(steps, seat)

    n = len(flow)

    # -- G1: the tape's own wave structure -------------------------------------
    top_sig, top_n = waves.most_common(1)[0]
    g1 = {"n_episodes": n, "distinct_signatures": len(waves),
          "dominant_signature": json.loads(top_sig), "dominant_share": round(top_n / n, 4),
          "runner_up_signatures": [{"n": v, "signature": json.loads(k)}
                                   for k, v in waves.most_common(4)[1:]]}

    # -- G2: what the block realises, and what it costs in tile-days -----------
    recorded = {"our_units": [], "our_revenue": [], "opp_units": [], "opp_revenue": [],
                "block_units": [], "block_revenue": []}
    for eid, (ours, our_rev, opp, opp_rev, _x) in flow.items():
        recorded["our_units"].append(sum(ours.values()))
        recorded["our_revenue"].append(sum(our_rev.values()))
        recorded["opp_units"].append(sum(opp.values()))
        recorded["opp_revenue"].append(sum(opp_rev.values()))
        recorded["block_units"].append(sum(ours.get(d, 0.0) for d in MELON_BLOCK_DAYS))
        recorded["block_revenue"].append(sum(our_rev.get(d, 0.0) for d in MELON_BLOCK_DAYS))
    med = {k: round(statistics.median(v), 1) for k, v in recorded.items()}
    wave2 = json.loads(top_sig)
    wave2_tiles = sum(sum(c.values()) for d, c in wave2.items() if int(d) >= 10)
    wave2_tiledays = 0
    for planted, cells in wave2.items():
        if int(planted) < 10:
            continue
        for label, count in cells.items():
            harvest = int(label.split("harvest_d")[1].split("|")[0])
            wave2_tiledays += count * (harvest - int(planted))
    seed_cost = wave2_tiles * CROPS["MELON"]["seed"]
    g2 = {
        "median_per_episode": med,
        "wave2_tiles": wave2_tiles, "wave2_tile_days": wave2_tiledays,
        "wave2_seed_cost": seed_cost,
        "wave2_net_dollars": round(med["block_revenue"] - seed_cost),
        "wave2_dollars_per_tile_day": round((med["block_revenue"] - seed_cost) / wave2_tiledays, 1),
        "note": ("compare against the tape's own realised $/crop-tile-day in "
                 "panel_d_timing + panel_f_profile.crop_tiledays of the same run"),
    }

    # -- G3: can an earlier wave be planted at all? ----------------------------
    top_land, top_land_n = land_marks.most_common(1)[0]
    free_open, free_peak = defaultdict(list), defaultdict(list)
    cash_open, cash_peak, seeds_by_day = defaultdict(list), defaultdict(list), defaultdict(list)
    shed_melon, shed_wool = defaultdict(list), defaultdict(list)
    for rec in daily.values():
        for day, r in rec.items():
            free_open[day].append(r["free_tiles"])
            free_peak[day].append(r["free_tiles_max"])
            cash_open[day].append(r["money"])
            cash_peak[day].append(r["money_max"])
            seeds_by_day[day].append(r["melon_seeds"])
            shed_melon[day].append(r["shed_melon"])
            shed_wool[day].append(r["shed_wool"])
    # Day 0 is excluded: its free land is the untouched opening board and its recorded cash is a
    # POST-spend snapshot of the $3.000 the tape has already committed to herd and hands.
    # Re-allocating the opening buy is a different, larger change than re-phasing a wave.
    earliest = None
    for day in sorted(free_peak):
        if day == 0:
            continue
        land_ok = statistics.median(free_peak[day]) >= wave2_tiles
        cash_ok = statistics.median(cash_peak[day]) >= seed_cost
        if land_ok and cash_ok:
            earliest = day
            break
    g3 = {
        "quadrant_unlocks": json.loads(top_land), "unlock_signature_share": round(top_land_n / n, 4),
        "unlock_free_tiles_and_cash": {
            f"q{q}_d{d}_h{h}": {
                "free_tiles_median": statistics.median([a for a, _ in v]),
                "money_after_purchase_median": statistics.median([b for _, b in v]),
            } for (q, d, h), v in sorted(unlock_state.items())},
        "by_day": [{"day": d,
                    "free_tiles_at_open_median": statistics.median(free_open[d]),
                    "free_tiles_peak_median": statistics.median(free_peak[d]),
                    "free_tiles_peak_max": max(free_peak[d]),
                    "money_at_open_median": round(statistics.median(cash_open[d])),
                    "money_peak_median": round(statistics.median(cash_peak[d])),
                    "melon_seeds_held_median": statistics.median(seeds_by_day[d])}
                   for d in sorted(free_peak) if d <= 22],
        "wave2_tiles_needed": wave2_tiles, "seed_cost": seed_cost,
        "day0_excluded": ("free land at d0 is the opening board and its recorded cash is a "
                          "post-spend snapshot; re-allocating the $3.000 opening buy is a "
                          "different change from re-phasing a wave"),
        "earliest_day_with_land_and_cash": earliest,
        "earliest_feasible_harvest_day": (earliest + CROPS["MELON"]["first_yield_day"])
                                          if earliest is not None else None,
    }

    # -- G4: the self-crash / re-phasing model ---------------------------------
    validation, rows = [], []
    per_target = {t: {"d_us": [], "d_opp": [], "flip_us": 0, "flip_diff": 0} for t in targets}
    n_losses = 0
    for eid, (ours, our_rev, opp, _opp_rev, x_start) in flow.items():
        x0 = x_start.get(10)
        if x0 is None:
            continue
        base_us, base_opp = melon_season(ours, opp, x0)
        validation.append(base_us - sum(our_rev.values()))
        e = eps_by_id.get(eid)
        is_loss = e is not None and not e["win"]
        margin = -e["margin"] if is_loss else None
        if is_loss:
            n_losses += 1
        keep = {d: v for d, v in ours.items() if d not in MELON_BLOCK_DAYS}
        block = sum(ours.get(d, 0.0) for d in MELON_BLOCK_DAYS)
        for t in targets:
            cf = dict(keep)
            cf[t] = cf.get(t, 0.0) + block
            us, op = melon_season(cf, opp, x0)
            per_target[t]["d_us"].append(us - base_us)
            per_target[t]["d_opp"].append(op - base_opp)
            if is_loss:
                per_target[t]["flip_us"] += (us - base_us) > margin
                per_target[t]["flip_diff"] += ((us - base_us) - (op - base_opp)) > margin
        rows.append(eid)
    rec_rev = [sum(f[1].values()) for f in flow.values()]
    g4 = {
        "n_episodes": len(rows), "n_losses": n_losses,
        "validation": {
            "what": ("model revenue for the RECORDED schedule minus the ledger's recorded "
                     "revenue; the model is only trusted to the size of this error"),
            "median_error": round(statistics.median(validation)),
            "mean_error": round(statistics.mean(validation)),
            "episodes_over_5pct": sum(1 for err, rev in zip(validation, rec_rev)
                                      if rev and abs(err) > 0.05 * rev),
        },
        "targets": [{
            "harvest_day": t,
            "d_our_melon_median": round(statistics.median(v["d_us"])),
            "d_our_melon_mean": round(statistics.mean(v["d_us"])),
            "d_opp_melon_median": round(statistics.median(v["d_opp"])),
            "d_margin_median": round(statistics.median([a - b for a, b in zip(v["d_us"], v["d_opp"])])),
            "episodes_positive": sum(1 for z in v["d_us"] if z > 0),
            "loss_flips_our_side_only": v["flip_us"],
            "loss_flips_full_differential": v["flip_diff"],
        } for t, v in per_target.items()],
        "limit": ("the opponent's MELON unit schedule is held fixed while their realised price "
                  "moves — a joint-seat model, ground-truth-only per memory "
                  "`kaggriculture-lockstep-market-quoting`.  `d_our_melon_*` is the defensible "
                  "half; `d_margin_*` additionally spends the opponent's loss and is an upper "
                  "bound, not an estimate."),
    }

    # -- G5: Phase 2b — is WOOL holdable, or production-gated like MELON? ------
    trough = range(12, 16)
    g5 = {
        "question": ("S14 §3: is our own WOOL stock ever non-zero before the d12-15 trough, the "
                     "way MELON's never is before its harvest days?"),
        "shed_melon_by_day": {str(d): {"median": statistics.median(shed_melon[d]),
                                       "max": max(shed_melon[d])} for d in sorted(shed_melon)},
        "shed_wool_by_day": {str(d): {"median": statistics.median(shed_wool[d]),
                                      "max": max(shed_wool[d])} for d in sorted(shed_wool)},
        "wool_days_with_stock": sorted(d for d in shed_wool if max(shed_wool[d]) > 0),
        "wool_stock_in_trough_d12_15": max(
            (max(shed_wool[d]) for d in trough if d in shed_wool), default=0),
        "melon_stock_before_d20": max(
            (max(shed_melon[d]) for d in shed_melon if d < 20), default=0),
    }
    return {"g1_wave_structure": g1, "g2_tile_day_cost": g2, "g3_feasibility": g3,
            "g4_rephasing_model": g4, "g5_wool_holdability": g5}


# --------------------------------------------------------------------------- driver

def run(strong_cut):
    eps, self_play, skipped = load_live()
    board, lb_name = load_leaderboard()
    times = load_episode_times()
    a = panel_a(eps, times)
    a["self_play_excluded"] = self_play
    res = {
        "pass": "S9 live read 55726984",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "leaderboard_snapshot": lb_name,
        "replays_read": len(eps), "files_skipped": skipped,
        "panel_a_volume_wl": a,
        "panel_b_strength": panel_b(eps, board, times),
        "panel_c_losses": panel_c(eps, board, strong_cut),
        "panel_d_timing": panel_d_timing(eps),
        "panel_e_flip": panel_e_flip(eps),
        "panel_f_profile": panel_f_profile(eps),
        "episodes": [{k: e[k] for k in ("episode_id", "seed", "seat", "opponent", "bank", "opp_bank",
                                        "margin", "margin_norm", "win", "shops")} for e in eps],
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"wrote {OUT}  ({len(eps)} ladder episodes)")
    return res


def run_melon():
    """S14 Phase 2/2b.  Writes its own artefact; leaves the S9 panels untouched."""
    eps, _self_play, _skipped = load_live()
    res = panel_g_melon(replay_paths("55726984"), {e["episode_id"]: e for e in eps})
    feasible = res["g3_feasibility"]["earliest_feasible_harvest_day"]
    best = max(res["g4_rephasing_model"]["targets"], key=lambda r: r["d_our_melon_median"])
    at_feasible = next((r for r in res["g4_rephasing_model"]["targets"]
                        if r["harvest_day"] == feasible), None)
    res["verdict"] = _melon_verdict(res, at_feasible)
    res.update({
        "pass": "S14 MELON tile-day / re-phasing (docs/plans/s14_loss_analysis.md §2-§3)",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "screen_set": "55726984 ladder replays only — the confirm set (55586926 + 55675634) "
                      "is untouched by this pass (ROADMAP §8)",
        "best_target_by_median": best["harvest_day"],
        "earliest_feasible_harvest_day": feasible,
    })
    DERIVED.mkdir(parents=True, exist_ok=True)
    MELON_OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"wrote {MELON_OUT}")
    return res


def _melon_verdict(res, at_feasible):
    g2, g3 = res["g2_tile_day_cost"], res["g3_feasibility"]
    if at_feasible is None:
        return ("KILL — no harvest day is both land/cash-feasible and modelled; "
                "MELON is closed on the production side as well as the market side.")
    gain = at_feasible["d_our_melon_median"]
    flips = at_feasible["loss_flips_our_side_only"]
    n_losses = res["g4_rephasing_model"]["n_losses"]
    head = (f"wave 2 earns ${g2['wave2_dollars_per_tile_day']}/tile-day net of seed over "
            f"{g2['wave2_tile_days']} tile-days; the earliest land- and cash-feasible harvest "
            f"day is d{g3['earliest_feasible_harvest_day']}, worth a median "
            f"${gain:+,} of our own MELON revenue and {flips}/{n_losses} loss flips.")
    if gain <= 0:
        return "KILL — " + head + "  Re-phasing is non-positive at every feasible day."
    return ("POSITIVE ON THE SCREEN SET, NOT BUILT — " + head +
            "  This is a screen-set paper bound with a non-reacting opponent (see "
            "g4_rephasing_model.limit); it is scoped into docs/plans/s15_melon_rephasing.md "
            "and must be confirmed on Instrument A (analysis/s10_replay_bench.py) against the "
            "412-episode confirm set before any agent/ change.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report", "melon"])
    ap.add_argument("--strong-cut", type=float, default=2100.0)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.strong_cut)
    elif args.cmd == "melon":
        run_melon()
    else:
        print(json.dumps(json.loads(OUT.read_text()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
