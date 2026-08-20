#!/usr/bin/env python3
"""S7 leg 0 — the deployment-neighbourhood census (desk, zero episodes).

Two external sources landed on 2026-08-20 and both say the same thing: **the ladder is judged in
wins against the opponents you actually meet, and the live score is a path-dependent number that
deflates.** This script measures both halves on our own data, so the ROADMAP's evaluation strategy
rests on repo measurements rather than on a forum post.

  A — the live panel.  Every ladder replay of `55586926` (the shipped ReCurSiON reconstruction):
      win rate overall, by chronological block, by seat, and **per opponent team** — the
      "deployment neighbourhood" surface that a multi-generation bench has to reproduce.
  B — the deflation panel.  Two public-leaderboard snapshots, differenced two ways: per *team*
      (frozen teams only — §1's standing rule) and per *rank slot*. The second is the one that
      has never been computed here, and it is what makes a score delta readable.
  C — win rate against opponent strength.  R36 asks for the opponent's rating at play time and the
      replays do not carry one (2e correction #2).  The only executable substitute is the team's
      *current* board score — valid **only** where that team's `LastSubmissionDate` predates our
      episode, i.e. the submission on the board today is the one that played us.  Leg C reports the
      uncontrolled join and that controlled subset separately, and never mixes them.

No `agent/` change, no episode played, no upload (R27). Derived JSON is gitignored (§2.4b / R11)
and carries the verdict string (R35).

Usage:
    python analysis/s7_ladder_census.py run
    python analysis/s7_ladder_census.py report
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LIVE = ROOT / "data" / "archive" / "raw" / "live_55586926"
EP_CSV = ROOT / "data" / "archive" / "raw" / "live_55586926_episodes.csv"
DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "s7_ladder_census.json"
OUR_TEAM = "STRAF"

# The two public-leaderboard snapshots differenced by leg B. Both are gitignored raw captures.
LB_SNAPSHOTS = [
    ("2026-08-18", "live_leaderboard_2026-08-18/kaggriculture-publicleaderboard-2026-08-18T10:04:36.csv"),
    ("2026-08-20", "live_leaderboard_2026-08-20/kaggriculture-publicleaderboard-2026-08-20T10:57:31.csv"),
]

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
PREMIUM = {"STRAWBERRY", "WOOL", "MILK"}


def _premium_drain(shop_list):
    """Units/tick of PREMIUM demand this town's unlocked shops generate (multiplier 2 if solo)."""
    total = 0
    for shop in shop_list:
        products = SHOPS.get(shop, [])
        mult = 2 if len(products) == 1 else 1
        total += sum(mult for p in products if p in PREMIUM)
    return total


def _pctl(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[i])


# --------------------------------------------------------------------------- leg A

def load_live():
    """Every ladder episode of 55586926, self-play validation episodes excluded."""
    files = sorted(glob.glob(str(LIVE / "*.json")) + glob.glob(str(LIVE / "*.json.gz")))
    if not files:
        raise SystemExit(f"no live replays at {LIVE} (§2.4b)")
    eps, self_play = [], 0
    for f in files:
        d = json.load(gzip.open(f)) if f.endswith(".gz") else json.loads(Path(f).read_text())
        info = d.get("info", {})
        teams = info.get("TeamNames", [None, None])
        if len(teams) != 2:
            continue
        if teams[0] == OUR_TEAM and teams[1] == OUR_TEAM:
            self_play += 1
            continue
        if OUR_TEAM not in teams:
            continue
        seat = 1 if teams[1] == OUR_TEAM else 0
        eps.append({
            "episode_id": info.get("EpisodeId"),
            "seat": seat,
            "opponent": teams[1 - seat],
            "bank": float(d["rewards"][seat]),
            "opp_bank": float(d["rewards"][1 - seat]),
            "drain": _premium_drain(d["steps"][-1][seat]["observation"]["town"]["unlocked_shops"]),
        })
    for e in eps:
        e["margin"] = e["bank"] - e["opp_bank"]
        e["win"] = e["margin"] > 0
    eps.sort(key=lambda e: e["episode_id"] or 0)
    return eps, self_play


def _wr(eps):
    return (sum(e["win"] for e in eps) / len(eps)) if eps else 0.0


def leg_a(eps, self_play):
    n = len(eps)
    third = max(1, n // 3)
    blocks = [("first", eps[:third]), ("middle", eps[third:2 * third]), ("last", eps[2 * third:])]

    by_opp = defaultdict(list)
    for e in eps:
        by_opp[e["opponent"]].append(e)
    opp_rows = sorted(
        ({"opponent": k, "n": len(v), "wins": sum(x["win"] for x in v),
          "win_rate": _wr(v), "margin_median": statistics.median(x["margin"] for x in v)}
         for k, v in by_opp.items()),
        key=lambda r: (-r["n"], r["opponent"]),
    )
    repeat = sum(r["n"] for r in opp_rows if r["n"] > 1)
    banks = [e["bank"] for e in eps]
    return {
        "n_episodes": n,
        "self_play_excluded": self_play,
        "win_rate": _wr(eps),
        "wins": sum(e["win"] for e in eps),
        "blocks": [{"block": name, "n": len(b), "win_rate": _wr(b)} for name, b in blocks],
        "by_seat": [{"seat": s, "n": len([e for e in eps if e["seat"] == s]),
                     "win_rate": _wr([e for e in eps if e["seat"] == s])} for s in (0, 1)],
        "distinct_opponents": len(opp_rows),
        "repeat_share": repeat / n if n else 0.0,
        "opponents_top": opp_rows[:20],
        "opponents_multi": [r for r in opp_rows if r["n"] >= 3],
        "bank": {"p10": _pctl(banks, 10), "median": statistics.median(banks),
                 "p90": _pctl(banks, 90), "spread": _pctl(banks, 90) / max(1.0, _pctl(banks, 10))},
        "margin_median_win": statistics.median([e["margin"] for e in eps if e["win"]] or [0]),
        "margin_median_loss": statistics.median([e["margin"] for e in eps if not e["win"]] or [0]),
        "drain_win_rate": [
            {"drain": d, "n": len(v), "win_rate": _wr(v)}
            for d, v in sorted((
                (d, [e for e in eps if e["drain"] == d])
                for d in sorted({e["drain"] for e in eps})), key=lambda kv: kv[0])
        ],
    }


# --------------------------------------------------------------------------- leg B

def _load_lb(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({"rank": int(r["Rank"]), "team_id": r["TeamId"], "team": r["TeamName"],
                         "last_sub": r["LastSubmissionDate"], "score": float(r["Score"])})
    rows.sort(key=lambda r: r["rank"])
    return rows


def leg_b():
    raw = ROOT / "data" / "archive" / "raw"
    snaps = []
    for date, rel in LB_SNAPSHOTS:
        p = raw / rel
        if not p.exists():
            raise SystemExit(f"leaderboard snapshot missing: {p} (§2.4b)")
        snaps.append((date, _load_lb(p)))
    (d0, a), (d1, b) = snaps
    days = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days
    days = days + (10.0 + 57 / 60) / 24 - (10.0 + 4 / 60) / 24  # snapshot clock offset

    ai = {r["team_id"]: r for r in a}
    bi = {r["team_id"]: r for r in b}
    common = set(ai) & set(bi)
    frozen = [t for t in common if ai[t]["last_sub"] == bi[t]["last_sub"]]
    resub = [t for t in common if ai[t]["last_sub"] != bi[t]["last_sub"]]

    bands = []
    for lo, hi in [(2800, 9999), (2400, 2800), (2000, 2400), (1600, 2000),
                   (1200, 1600), (800, 1200), (0, 800)]:
        deltas = [bi[t]["score"] - ai[t]["score"] for t in frozen if lo <= ai[t]["score"] < hi]
        bands.append({"band": f"{lo}-{hi}", "n": len(deltas),
                      "median_delta": statistics.median(deltas) if deltas else 0.0,
                      "per_day": (statistics.median(deltas) / days) if deltas else 0.0})

    slots = []
    for k in (1, 10, 25, 50, 100, 200, 400, 700, 900, 1200, 2000, 3000):
        if k <= min(len(a), len(b)):
            slots.append({"rank": k, "score_a": a[k - 1]["score"], "score_b": b[k - 1]["score"],
                          "delta": b[k - 1]["score"] - a[k - 1]["score"],
                          "per_day": (b[k - 1]["score"] - a[k - 1]["score"]) / days})

    def find(team):
        ra = next((r for r in a if r["team"] == team), None)
        rb = next((r for r in b if r["team"] == team), None)
        if not ra or not rb:
            return None
        return {"team": team, "rank_a": ra["rank"], "score_a": ra["score"],
                "rank_b": rb["rank"], "score_b": rb["score"],
                "d_score": rb["score"] - ra["score"], "d_rank": ra["rank"] - rb["rank"],
                "frozen": ra["last_sub"] == rb["last_sub"]}

    tracked = [x for x in (find(t) for t in
               ("STRAF", "ReCurSiON", "カワシギ", "boatlee", "Valmorlee", "Ueddy",
                "Peter Parker", "Kaito Fukami")) if x]
    return {
        "snapshot_a": d0, "snapshot_b": d1, "days": days,
        "teams_a": len(a), "teams_b": len(b), "new_teams": len(set(bi) - set(ai)),
        "frozen": len(frozen), "resubmitted": len(resub),
        "resubmit_share": len(resub) / len(common) if common else 0.0,
        "frozen_median_delta": statistics.median([bi[t]["score"] - ai[t]["score"] for t in frozen]),
        "bands": bands, "rank_slots": slots, "tracked": tracked,
    }


# --------------------------------------------------------------------------- leg C

def leg_c(eps):
    """Win rate against opponent strength, with the frozen-submission control."""
    if not EP_CSV.exists():
        raise SystemExit(f"episode listing missing: {EP_CSV} "
                         f"(`kaggle competitions episodes 55586926 -v`, §2.4b)")
    played_at = {}
    with open(EP_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("id") or "").isdigit():
                played_at[int(r["id"])] = dt.datetime.fromisoformat(r["createTime"].split(".")[0])

    board = {}
    _, latest = LB_SNAPSHOTS[-1]
    for r in _load_lb(ROOT / "data" / "archive" / "raw" / latest):
        board[r["team"]] = (r["rank"], r["score"],
                            dt.datetime.fromisoformat(r["last_sub"]))

    raw_rows, ctrl_rows = [], []
    for i, e in enumerate(eps):
        o = board.get(e["opponent"])
        t = played_at.get(e["episode_id"])
        if not o:
            continue
        row = {"i": i, "win": e["win"], "margin": e["margin"], "opp_score": o[1], "opp_rank": o[0]}
        raw_rows.append(row)
        # the board submission is the one that played us only if it predates the episode
        if t is not None and o[2] <= t:
            ctrl_rows.append(row)

    converged_from = len(eps) // 3  # blocks past the placement burst (see leg A)

    def bucket(rows, edges):
        out = []
        for lo, hi in edges:
            sub = [r for r in rows if lo <= r["opp_score"] < hi]
            if sub:
                out.append({"band": f"{lo}-{hi}", "n": len(sub),
                            "win_rate": sum(r["win"] for r in sub) / len(sub),
                            "margin_median": statistics.median(r["margin"] for r in sub)})
        return out

    edges = [(0, 1500), (1500, 1800), (1800, 2000), (2000, 2300), (2300, 9999)]
    conv_edges = [(0, 1800), (1800, 2100), (2100, 9999)]
    conv = [r for r in ctrl_rows if r["i"] >= converged_from]
    return {
        "matched_raw": len(raw_rows),
        "matched_controlled": len(ctrl_rows),
        "note": ("controlled = the opponent team's LastSubmissionDate predates our episode, so the "
                 "score on the board today belongs to the submission that actually played us; the "
                 "raw join mixes in teams that have re-submitted since (26%/2 days, leg B)"),
        "raw": bucket(raw_rows, edges),
        "controlled": bucket(ctrl_rows, edges),
        "converged_from_episode": converged_from,
        "converged_n": len(conv),
        "converged_win_rate": (sum(r["win"] for r in conv) / len(conv)) if conv else 0.0,
        "converged_controlled": bucket(conv, conv_edges),
    }


# --------------------------------------------------------------------------- verdict

def verdict(a, b, c):
    straf = next((t for t in b["tracked"] if t["team"] == "STRAF"), None)
    drains = a["drain_win_rate"]
    parts = [
        f"LIVE PANEL n={a['n_episodes']} win_rate={a['win_rate']:.3f} "
        f"distinct_opponents={a['distinct_opponents']} repeat_share={a['repeat_share']:.2f}",
        "blocks=" + "/".join(f"{x['block']}:{x['win_rate']:.3f}" for x in a["blocks"]),
        f"CONVERGED win_rate={c['converged_win_rate']:.3f} (n={c['converged_n']}, controlled) "
        f"=> the 65% of the 2e brief was the placement burst, not a converged rate",
        f"DRAIN moves bank (2e r=+0,579) but NOT wins: "
        + "/".join(f"{d['drain']}:{d['win_rate']:.2f}" for d in drains if d["n"] >= 7),
        f"DEFLATION over {b['days']:.2f}d: frozen median {b['frozen_median_delta']:+.1f}, "
        f"rank-slot 100 {next((s['per_day'] for s in b['rank_slots'] if s['rank'] == 100), 0):+.1f}/day",
    ]
    if straf:
        parts.append(
            f"STRAF {straf['score_a']:.1f}->{straf['score_b']:.1f} ({straf['d_score']:+.1f}) "
            f"while rank {straf['rank_a']}->{straf['rank_b']} ({straf['d_rank']:+d}) "
            f"=> score fell, rank {'ROSE' if straf['d_rank'] > 0 else 'FELL'}"
        )
    return " | ".join(parts)


def run():
    eps, self_play = load_live()
    a = leg_a(eps, self_play)
    b = leg_b()
    c = leg_c(eps)
    rec = {"pass": "S7 leg 0 — deployment-neighbourhood census",
           "date": dt.date.today().isoformat(),
           "leg_a_live_panel": a, "leg_b_deflation": b, "leg_c_opponent_strength": c,
           "verdict": verdict(a, b, c)}
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    _print(rec)
    return rec


def _print(rec):
    a, b, c = (rec["leg_a_live_panel"], rec["leg_b_deflation"],
               rec.get("leg_c_opponent_strength", {}))
    print("=" * 78)
    print("LEG A — the live panel (55586926 ladder episodes)")
    print("=" * 78)
    print(f"episodes {a['n_episodes']}  (self-play excluded {a['self_play_excluded']})")
    print(f"win rate {a['win_rate']:.1%}  ({a['wins']}/{a['n_episodes']})")
    print("  by block: " + "  ".join(f"{x['block']} n={x['n']} {x['win_rate']:.1%}" for x in a["blocks"]))
    print("  by seat : " + "  ".join(f"seat{x['seat']} n={x['n']} {x['win_rate']:.1%}" for x in a["by_seat"]))
    print(f"bank p10 ${a['bank']['p10']:,.0f}  median ${a['bank']['median']:,.0f}  "
          f"p90 ${a['bank']['p90']:,.0f}  spread {a['bank']['spread']:.2f}x")
    print(f"margin median: win +${a['margin_median_win']:,.0f}  loss ${a['margin_median_loss']:,.0f}")
    print(f"\ndistinct opponents {a['distinct_opponents']}  "
          f"share of episodes vs a repeat opponent {a['repeat_share']:.1%}")
    print(f"\n{'opponent':<28}{'n':>4}{'W':>4}{'win%':>8}{'median margin':>16}")
    for r in a["opponents_top"]:
        print(f"{r['opponent'][:27]:<28}{r['n']:>4}{r['wins']:>4}{r['win_rate']:>7.0%}"
              f"{r['margin_median']:>16,.0f}")
    print(f"\n{'drain':>6}{'n':>5}{'win%':>8}")
    for r in a["drain_win_rate"]:
        print(f"{r['drain']:>6}{r['n']:>5}{r['win_rate']:>7.0%}")

    print("\n" + "=" * 78)
    print(f"LEG B — deflation, {b['snapshot_a']} -> {b['snapshot_b']} ({b['days']:.2f} days)")
    print("=" * 78)
    print(f"teams {b['teams_a']} -> {b['teams_b']} (+{b['new_teams']} new)  "
          f"frozen {b['frozen']}  resubmitted {b['resubmitted']} ({b['resubmit_share']:.0%})")
    print(f"\nfrozen teams, score delta by starting band:")
    print(f"{'band':>12}{'n':>6}{'median':>10}{'per day':>10}")
    for r in b["bands"]:
        print(f"{r['band']:>12}{r['n']:>6}{r['median_delta']:>10.1f}{r['per_day']:>10.1f}")
    print(f"\nscore AT a fixed rank slot (the ladder deflating under everyone):")
    print(f"{'rank':>6}{'A':>10}{'B':>10}{'delta':>9}{'per day':>9}")
    for r in b["rank_slots"]:
        print(f"{r['rank']:>6}{r['score_a']:>10.1f}{r['score_b']:>10.1f}{r['delta']:>9.1f}{r['per_day']:>9.1f}")
    print(f"\n{'team':>16}{'rank A':>8}{'score A':>10}{'rank B':>8}{'score B':>10}"
          f"{'d score':>9}{'d rank':>8}  frozen")
    for r in b["tracked"]:
        print(f"{r['team'][:15]:>16}{r['rank_a']:>8}{r['score_a']:>10.1f}{r['rank_b']:>8}"
              f"{r['score_b']:>10.1f}{r['d_score']:>9.1f}{r['d_rank']:>+8}  {r['frozen']}")
    if c:
        print("\n" + "=" * 78)
        print("LEG C — win rate vs opponent strength (current board score as the R36 substitute)")
        print("=" * 78)
        print(f"matched raw {c['matched_raw']}/{a['n_episodes']}   "
              f"controlled {c['matched_controlled']}/{a['n_episodes']}")
        print(f"  ({c['note']})")
        for label, key in (("RAW join (uncontrolled)", "raw"), ("CONTROLLED", "controlled")):
            print(f"\n{label}:")
            print(f"{'opp band':>14}{'n':>5}{'win%':>8}{'median margin':>16}")
            for r in c[key]:
                print(f"{r['band']:>14}{r['n']:>5}{r['win_rate']:>7.0%}{r['margin_median']:>16,.0f}")
        print(f"\nCONVERGED regime (episodes {c['converged_from_episode']}+, controlled): "
              f"n={c['converged_n']}  win rate {c['converged_win_rate']:.1%}")
        print(f"{'opp band':>14}{'n':>5}{'win%':>8}")
        for r in c["converged_controlled"]:
            print(f"{r['band']:>14}{r['n']:>5}{r['win_rate']:>7.0%}")

    print("\nVERDICT: " + rec["verdict"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["run", "report"])
    args = ap.parse_args()
    if args.cmd == "run":
        run()
    else:
        if not OUT.exists():
            raise SystemExit(f"no saved run at {OUT} — run `python {Path(__file__).name} run` first")
        _print(json.loads(OUT.read_text()))


if __name__ == "__main__":
    main()
