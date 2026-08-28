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

from analysis.s8_replay_io import load as load_replay, replay_paths, meta as replay_meta, is_excluded  # noqa: E402
from analysis.s9_market_ledger import episode_ledger, step_ledger  # noqa: E402
from engine_reference.kaggriculture import (  # noqa: E402
    CROPS, MARKET_I0, PRICE_FLOOR, SHOPS, TOWN_CENTER_PRODUCTS, market_price,
)
DERIVED = ROOT / "data" / "derived"
RAW = ROOT / "data" / "archive" / "raw"
OUR_TEAM = "STRAF"

# The only submission-bound constants (S16 Phase 1: generalised from a single
# hard-coded submission so this instrument can read either live slot without a
# second copy of it — ROADMAP §3 "reuse, do not duplicate"). `submitted_at` is
# each submission's own EPISODE_TYPE_VALIDATION createTime (the upload instant).
SUBMISSION_META = {
    "55726984": {
        "ep_csv": DERIVED / "s9_live_55726984_episodes.csv",
        "submitted_at": dt.datetime(2026, 8, 23, 23, 7, 25),
    },
    "55675634": {
        "ep_csv": RAW / "live_55675634_episodes.csv",
        "submitted_at": dt.datetime(2026, 8, 21, 19, 6, 14),
    },
}

SUBMISSION = "55726984"
LIVE = RAW / f"live_{SUBMISSION}"
EP_CSV = SUBMISSION_META[SUBMISSION]["ep_csv"]
OUT = DERIVED / f"s9_live_read_{SUBMISSION}.json"
SUBMITTED_AT = SUBMISSION_META[SUBMISSION]["submitted_at"]


def set_submission(submission: str):
    """Point every submission-bound global at `submission`. Call before run()/load_live()."""
    global SUBMISSION, LIVE, EP_CSV, OUT, SUBMITTED_AT
    meta = SUBMISSION_META[submission]
    SUBMISSION = submission
    LIVE = RAW / f"live_{submission}"
    EP_CSV = meta["ep_csv"]
    OUT = DERIVED / f"s9_live_read_{submission}.json"
    SUBMITTED_AT = meta["submitted_at"]

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


def load_live(submission=None):
    # One reader for the whole codebase (ROADMAP §3 rule "reuse, do not duplicate"):
    # `s8_replay_io` accepts both `episode-*-replay.json` and `.json.gz`.  The local
    # `*.json` glob this used to carry went blind the moment the archive was gzipped.
    # `submission` defaults to the module-global SUBMISSION (set via `set_submission`)
    # so every existing call site is unaffected; S15 gate 1 passes each confirm-set
    # submission explicitly instead of routing through SUBMISSION_META.
    files = replay_paths(submission or SUBMISSION)
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
        "pass": f"S9 live read {SUBMISSION}",
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


GATE1_OUT = DERIVED / "s15_gate1_confirm_replication.json"


def run_melon_confirm():
    """S15 Phase 1, gate 1 (docs/plans/s15_melon_rephasing.md §3.1).

    Replicates panel_g_melon on the CONFIRM set (55586926 + 55675634, ROADMAP §8) —
    the set S14 deliberately left untouched.  One execution at the pre-registered
    threshold; no window widening, no parameter search.  Reuses
    `analysis.s10_replay_bench.CONFIRM_SUBS` rather than restating that split.
    """
    from analysis.s10_replay_bench import CONFIRM_SUBS
    eps_all, paths_all = [], []
    for sub in CONFIRM_SUBS:
        eps, _self_play, _skipped = load_live(sub)
        eps_all.extend(eps)
        paths_all.extend(replay_paths(sub))
    eps_by_id = {e["episode_id"]: e for e in eps_all}
    res = panel_g_melon(paths_all, eps_by_id)

    screen = json.loads(MELON_OUT.read_text())
    screen_day = screen["earliest_feasible_harvest_day"]
    screen_target = next(t for t in screen["g4_rephasing_model"]["targets"]
                         if t["harvest_day"] == screen_day)
    screen_gain = screen_target["d_our_melon_median"]
    screen_flip_share = screen_target["loss_flips_our_side_only"] / screen["g4_rephasing_model"]["n_losses"]

    feasible = res["g3_feasibility"]["earliest_feasible_harvest_day"]
    at_feasible = next((t for t in res["g4_rephasing_model"]["targets"]
                        if t["harvest_day"] == feasible), None)

    if at_feasible is None:
        verdict = ("STOP — gate 1 (confirm-set replication) FAILS: no harvest day on the "
                    "confirm set is both land/cash-feasible and modelled.")
        passed = False
        confirm_gain = confirm_flip_share = None
    else:
        confirm_gain = at_feasible["d_our_melon_median"]
        n_losses = res["g4_rephasing_model"]["n_losses"]
        confirm_flip_share = (at_feasible["loss_flips_our_side_only"] / n_losses) if n_losses else None
        gain_ok = confirm_gain > 0 and confirm_gain >= 0.6 * screen_gain
        flip_ok = (confirm_flip_share is not None
                   and abs(confirm_flip_share - screen_flip_share) <= 0.08)
        passed = gain_ok and flip_ok
        verdict = (
            f"{'PASS' if passed else 'STOP'} — gate 1 (confirm-set replication, plan §3.1.1): "
            f"screen d{screen_day} d_our_melon_median=${screen_gain:+,} flips {screen_target['loss_flips_our_side_only']}/"
            f"{screen['g4_rephasing_model']['n_losses']} ({screen_flip_share:.4f}); "
            f"confirm d{feasible} d_our_melon_median=${confirm_gain:+,} "
            f"({confirm_gain / screen_gain:.3f}x screen, need >=0.60x and >0) "
            f"flips {at_feasible['loss_flips_our_side_only']}/{n_losses} ({confirm_flip_share:.4f}, "
            f"need within 0.08 of {screen_flip_share:.4f})."
        )

    res["verdict"] = verdict
    res.update({
        "pass": "S15 Phase 1 gate 1 — confirm-set replication (docs/plans/s15_melon_rephasing.md §3.1.1)",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "confirm_subs": list(CONFIRM_SUBS),
        "confirm_set_note": ("55586926 + 55675634, untouched by S14; one execution at the "
                             "pre-registered threshold, no exploratory variants (ROADMAP §8)"),
        "gate_1_passed": passed,
        "screen_reference": {"day": screen_day, "d_our_melon_median": screen_gain,
                             "loss_flip_share": screen_flip_share},
        "confirm_result": {"day": feasible, "d_our_melon_median": confirm_gain,
                           "loss_flip_share": confirm_flip_share},
        "earliest_feasible_harvest_day": feasible,
    })
    DERIVED.mkdir(parents=True, exist_ok=True)
    GATE1_OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"wrote {GATE1_OUT}")
    print(verdict)
    return res


GATE2_OUT = DERIVED / "s15_gate2_hand_routing.json"
GATE2_SUBS = ("55586926", "55675634", "55726984")  # all live subs share this early-game window
GATE2_WAVE2_TILES = 14  # plan §1: 14 MELON seeds / tiles for the re-phased wave 2


def _gate2_window_steps(day_hour_pairs, n_steps):
    """`steps[idx]['observation']` carries `day`/`hour` == `divmod(idx, 24)` exactly, and
    `steps[idx]['action']` is the action decided WHILE OBSERVING that same `steps[idx]`
    (verified against real replays in `tests/test_s15_gate2_hand_routing.py` — every
    `idx = day*24+hour` sampled reads back that identical day/hour). So `idx = day*24+hour`
    is the one correct index for both fields; `+1` reads the FOLLOWING hour's decision."""
    for day, hour in day_hour_pairs:
        idx = day * 24 + hour
        if idx < n_steps:
            yield day, hour, idx


def _gate2_episode(steps, seat, n_steps):
    """Actions actually taken by our farmer/hands from d6h17 through d7h23 (the window
    S15 g3_feasibility names as the earliest land+cash-feasible planting window), plus
    the free-NE-tile count once the window's last action (d7h23) has taken effect — read
    one index past the window's last action, since `steps[idx]['observation']` is the
    state the d7h23 decision was made FROM, not the state it produces."""
    window = [(6, h) for h in range(17, 24)] + [(7, h) for h in range(24)]
    cnt_strawberry = cnt_wheat = cnt_pasture = cnt_other_plant = 0
    hand_pass = farmer_pass = hand_turns = farmer_turns = hand_move = 0
    last_idx = None
    for day, hour, idx in _gate2_window_steps(window, n_steps):
        a = steps[idx][seat].get("action") or {}
        fa = a.get("farmer")
        farmer_turns += 1
        if fa and fa[0] == "PASS":
            farmer_pass += 1
        if fa and fa[0] == "PLANT":
            if fa[1] == "STRAWBERRY":
                cnt_strawberry += 1
            elif fa[1] == "WHEAT":
                cnt_wheat += 1
            else:
                cnt_other_plant += 1
        if fa and fa[0] == "BUILD_PASTURE":
            cnt_pasture += 1
        for h in (a.get("hands") or []):
            hand_turns += 1
            if not h:
                continue
            if h[0] == "PASS":
                hand_pass += 1
            elif h[0] in ("NORTH", "SOUTH", "EAST", "WEST"):
                hand_move += 1
            elif h[0] == "PLANT":
                if h[1] == "STRAWBERRY":
                    cnt_strawberry += 1
                elif h[1] == "WHEAT":
                    cnt_wheat += 1
                else:
                    cnt_other_plant += 1
            elif h[0] == "BUILD_PASTURE":
                cnt_pasture += 1
        last_idx = idx
    close_idx = min(last_idx + 1, n_steps - 1)
    o = steps[close_idx][seat]["observation"]
    farm = o["farms"][o["player"]]
    free_at_close = sum(1 for row in farm["tiles"] for t in row if t is None)
    idle = hand_pass + farmer_pass
    return dict(cnt_strawberry=cnt_strawberry, cnt_wheat=cnt_wheat, cnt_pasture=cnt_pasture,
                cnt_other_plant=cnt_other_plant, hand_pass=hand_pass, farmer_pass=farmer_pass,
                idle=idle, hand_turns=hand_turns, farmer_turns=farmer_turns, hand_move=hand_move,
                free_tiles_at_window_close=free_at_close)


def run_gate2_hand_routing():
    """S15 Phase 1, gate 2 (docs/plans/s15_melon_rephasing.md §3.1.2).

    Replays the tape's OWN recorded action stream (not a model) over d6h17-d7h23 — the
    window g3_feasibility names as earliest land+cash-feasible — and checks whether 14
    MELON PLANT actions (plus the movement to reach 14 distinct NE tiles, plus the
    same-day WATER every newly planted tile needs to survive the day-boundary weed-death
    rule: `consecutive_unwatered>=2` — `engine_reference/kaggriculture.py:769-784`) fit
    without disturbing what the tape already does there.  No `agent/` code: this reads
    the recorded stream, it does not construct or play a modified one.
    """
    rows = []
    for sub in GATE2_SUBS:
        for p in replay_paths(sub):
            d = load_replay(p)
            m = replay_meta(d)
            excl, _r = is_excluded(m)
            if excl:
                continue
            teams = m["teams"]
            if OUR_TEAM not in teams:
                continue
            seat = 0 if teams[0] == OUR_TEAM else 1
            steps = m["steps"]
            if len(steps) <= 7 * 24 + 23 + 1:  # need idx 192 (the window's closing observation)
                continue
            r = _gate2_episode(steps, seat, len(steps))
            r["submission"] = sub
            r["episode_id"] = m["episode_id"]
            rows.append(r)

    sig_counts = Counter((r["cnt_strawberry"], r["cnt_wheat"], r["cnt_pasture"],
                          r["cnt_other_plant"], r["hand_pass"], r["farmer_pass"])
                         for r in rows)
    idle_vals = [r["idle"] for r in rows]
    free_vals = [r["free_tiles_at_window_close"] for r in rows]
    max_idle = max(idle_vals)
    min_free_at_close = min(free_vals)

    # Lower bound only: 1 move + 1 PLANT + 1 same-day WATER per new tile, ignoring travel
    # beyond the first hop and ignoring that idle turns are clustered at the window's very
    # end (day7 h18-23 in every sampled episode), by which point most of NE is already
    # spoken for. A real schedule needs at least this many free unit-turns; if even this
    # floor is not met the fit question is already closed.
    min_unit_turns_needed = 3 * GATE2_WAVE2_TILES

    plant_fits = max_idle >= min_unit_turns_needed
    land_fits = min_free_at_close >= GATE2_WAVE2_TILES
    passed = plant_fits and land_fits

    if passed:
        verdict = (f"PASS — gate 2 (hand-routing feasibility, plan §3.1.2): worst-case idle "
                   f"capacity {max_idle} unit-turns >= floor {min_unit_turns_needed}; worst-case "
                   f"free NE tiles at window close {min_free_at_close} >= {GATE2_WAVE2_TILES} needed.")
    else:
        reasons = []
        if not plant_fits:
            reasons.append(f"idle capacity tops out at {max_idle} unit-turns across "
                           f"{len(rows)} episodes, short of the {min_unit_turns_needed}-turn floor "
                           f"for {GATE2_WAVE2_TILES} tiles (1 move + 1 PLANT + 1 same-day WATER each, "
                           "no travel beyond the first hop)")
        if not land_fits:
            reasons.append(f"only {min_free_at_close} NE tiles remain free at window close "
                           f"(worst case), short of the {GATE2_WAVE2_TILES} needed, because the "
                           "recorded tape already spends the newly-unlocked land on "
                           f"{sig_counts.most_common(1)[0][0][0]} STRAWBERRY + "
                           f"{sig_counts.most_common(1)[0][0][1]} WHEAT + "
                           f"{sig_counts.most_common(1)[0][0][2]} PASTURE plantings in the same "
                           "window, and idle hand-turns only appear after that land is spoken for")
        verdict = ("STOP — gate 2 (hand-routing feasibility, plan §3.1.2) FAILS on the tape as "
                  "recorded: " + "; ".join(reasons) + ". The d7/d17 fallback does not rescue this "
                  "— the recorded STRAWBERRY block plants straight through d7h22, so the same "
                  "conflict holds inside the fallback window too.")

    res = {
        "pass": "S15 Phase 1 gate 2 — hand-routing feasibility (docs/plans/s15_melon_rephasing.md §3.1.2)",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "gate_2_passed": passed,
        "window": "d6h17 - d7h23 (31 turns), the earliest land+cash-feasible window per g3_feasibility",
        "submissions_checked": list(GATE2_SUBS),
        "n_episodes": len(rows),
        "n_distinct_signatures": len(sig_counts),
        "dominant_signature": {
            "strawberry_plants": sig_counts.most_common(1)[0][0][0],
            "wheat_plants": sig_counts.most_common(1)[0][0][1],
            "pasture_builds": sig_counts.most_common(1)[0][0][2],
            "other_plants": sig_counts.most_common(1)[0][0][3],
            "hand_pass": sig_counts.most_common(1)[0][0][4],
            "farmer_pass": sig_counts.most_common(1)[0][0][5],
            "n": sig_counts.most_common(1)[0][1],
        },
        "wave2_tiles_needed": GATE2_WAVE2_TILES,
        "min_unit_turns_needed_floor": min_unit_turns_needed,
        "idle_unit_turns": {"min": min(idle_vals), "median": sorted(idle_vals)[len(idle_vals) // 2],
                            "max": max_idle},
        "free_tiles_at_window_close": {"min": min_free_at_close, "median": sorted(free_vals)[len(free_vals) // 2],
                                       "max": max(free_vals)},
        "plant_fit_check_passed": plant_fits,
        "land_fit_check_passed": land_fits,
        "note": ("This checks fit against the tape AS RECORDED — it does not model hiring "
                "additional hands or displacing the recorded STRAWBERRY/WHEAT/PASTURE block, "
                "either of which would be a wider change than 'given where the farmer and hands "
                "actually stand' and is out of gate 2's scope (plan §3.1, rule 1: a kill "
                "criterion is a STOP, not a wider window)."),
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    GATE2_OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"wrote {GATE2_OUT}")
    print(verdict)
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
    ap.add_argument("cmd", choices=["run", "report", "melon", "melon_confirm", "gate2_hand_routing"])
    ap.add_argument("--strong-cut", type=float, default=2100.0)
    ap.add_argument("--submission", choices=sorted(SUBMISSION_META), default=SUBMISSION)
    args = ap.parse_args()
    set_submission(args.submission)
    if args.cmd == "run":
        run(args.strong_cut)
    elif args.cmd == "melon":
        run_melon()
    elif args.cmd == "melon_confirm":
        run_melon_confirm()
    elif args.cmd == "gate2_hand_routing":
        run_gate2_hand_routing()
    else:
        print(json.dumps(json.loads(OUT.read_text()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
