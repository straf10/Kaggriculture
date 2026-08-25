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

from analysis.s9_market_ledger import episode_ledger  # noqa: E402
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
            if "PUBLIC" not in row.get("type", ""):
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
    files = sorted(glob.glob(str(LIVE / "*.json")))
    if not files:
        raise SystemExit(f"no replays at {LIVE}")
    eps, self_play, skipped = [], 0, 0
    for f in files:
        d = json.loads(Path(f).read_text())
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--strong-cut", type=float, default=2100.0)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.strong_cut)
    else:
        print(json.dumps(json.loads(OUT.read_text()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
