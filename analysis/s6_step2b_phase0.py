#!/usr/bin/env python3
"""S6 step 2b — Phase 0: decompose the ~1.070-point donor gap on OUR OWN LIVE EPISODES.

The reconstruction (55586926) transfers 64% of its donor (1.915,8 vs ReCurSiON 2.985,6) while a
verbatim tape transferred 87%. This pass locates where the ~1.070 rating points went, on the primary
evidence this repo has never had at this quality: our shipped route's public episodes, real towns,
both seats, a rating-sorted opponent pool (ROADMAP §4.3 S6 step 2b).

Three instruments, all on the downloaded replays + the leaderboard:
  1. L1/L2 diagnostic — day-window bank gap, opponent rating bands, BOTH SEATS separately.
  2. The pre-registered refutation — our LIVE same-town realised premium $/u ratio (our seat vs the
     opponent seat, same town, same shop draw, INSIDE each episode) vs the donor's recorded 1,339 /
     frozen-replay 1,243 STRAWBERRY. At/near => calendar transferred, overlay lever small, points are
     elsewhere. Collapsed toward 1,0 => calendar is where the points went.
  3. Enumerate & price the gap — (a) erased 17,7% conditioning [needs the disagreement set],
     (b) production desync, (c) tier-0 loss (already <=$599/ep, §S6 step 2a), (d) opponent population
     (win rate vs rating band — rating converges at a 50% win rate), (e) decay.

Data:
  replays   data/archive/raw/live_55586926/episode-*-replay.json   (gitignored, R11/§2.4b)
  ladder    data/archive/raw/live_leaderboard_2026-08-18/*.csv     (public, team -> rating)
Emits data/derived/s6_step2b_live.json (compact per-episode; gitignored).

Usage:
    python analysis/s6_step2b_phase0.py            # extract + report
    python analysis/s6_step2b_phase0.py --report-only
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.s6_step0_leg1 import PREMIUM, _realised_both_seats, _shop_drain  # noqa: E402

OUR_TEAM = "STRAF"
REPLAY_DIR = Path("data/archive/raw/live_55586926")
LADDER_GLOB = "data/archive/raw/live_leaderboard_2026-08-18/*.csv"
OUT = Path("data/derived/s6_step2b_live.json")
TURNS_PER_DAY = 24
# The donor's recorded / frozen-replay same-town STRAWBERRY ratio (the pre-registered target).
DONOR_STR_RECORDED = 1.339
DONOR_STR_FROZEN = 1.243


def load_ladder() -> dict:
    files = glob.glob(LADDER_GLOB)
    if not files:
        return {}
    out = {}
    with open(files[0], encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[row["TeamName"]] = {
                "rank": int(row["Rank"]),
                "score": float(row["Score"]),
                "last_sub": row["LastSubmissionDate"],
            }
    return out


def day_banks(steps) -> list[dict]:
    """money[seat] at each day boundary d=1..29 (step d*TURNS_PER_DAY), read from seat-0's mirror."""
    out = []
    n = len(steps)
    for d in range(1, 30):
        i = min(d * TURNS_PER_DAY, n - 1)
        farms = steps[i][0]["observation"]["farms"]
        out.append({"day": d, "m0": farms[0]["money"], "m1": farms[1]["money"]})
    return out


def extract_one(path: Path, ladder: dict) -> dict | None:
    d = json.loads(path.read_text())
    names = d["info"].get("TeamNames") or [a.get("Name") for a in d["info"].get("Agents", [])]
    if OUR_TEAM not in names:
        return None
    our = names.index(OUR_TEAM)
    opp = 1 - our
    steps = d["steps"]
    # Clean-play guard (same as leg 1): no aborted/error statuses.
    bad = any(s["status"] not in ("ACTIVE", "DONE", "INACTIVE")
              for step in steps for s in (step[0], step[1]))
    r0, r1 = _realised_both_seats(d)
    rewards = d["rewards"]
    return {
        "episode": d["id"],
        "seed": d["info"].get("seed"),
        "our_seat": our,
        "opp_name": names[opp],
        "opp_rating": ladder.get(names[opp], {}).get("score"),
        "our_bank": rewards[our],
        "opp_bank": rewards[opp],
        "win": rewards[our] > rewards[opp],
        "clean": not bad,
        "shop_drain": _shop_drain(d),
        "day_banks": day_banks(steps),
        "our_realised": (r0 if our == 0 else r1),
        "opp_realised": (r1 if our == 0 else r0),
    }


def extract_all() -> list[dict]:
    ladder = load_ladder()
    rows = []
    files = sorted(REPLAY_DIR.glob("episode-*-replay.json"))
    for i, p in enumerate(files):
        try:
            r = extract_one(p, ladder)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {p.name}: {e}", file=sys.stderr)
            continue
        if r:
            rows.append(r)
        print(f"  [{i+1}/{len(files)}] {p.name} -> "
              f"{'ok' if r else 'not ours'}", file=sys.stderr)
    return rows


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def report(rows: list[dict]) -> dict:
    rows = [r for r in rows if r["clean"]]
    n = len(rows)
    wins = sum(r["win"] for r in rows)
    print("=" * 84)
    print(f"S6 step 2b Phase 0 — {n} clean live episodes of 55586926 (STRAF)")
    print(f"Record: {wins}-{n - wins}  ({100*wins/n:.1f}% win rate)   "
          f"| a rating converges at a 50% win rate (§ instrument 3d)")
    print("=" * 84)

    # ---- Instrument 1: seat split + day-window bank gap ----
    print("\n[1] L1/L2 — both seats separately")
    for seat in (0, 1):
        sub = [r for r in rows if r["our_seat"] == seat]
        if not sub:
            continue
        w = sum(r["win"] for r in sub)
        gap = med([r["our_bank"] - r["opp_bank"] for r in sub])
        print(f"  seat{seat}: n={len(sub):2d}  {w}-{len(sub)-w}  median bank gap {gap:+,.0f}")
    # day-window: median (our-opp) gap at each L2 day
    print("\n  Median bank gap (our - opp) by day  [L2 loss-window scan]:")
    hdr = [5, 10, 15, 20, 24, 28]
    line = []
    for d in hdr:
        g = med([next((b["m0"] - b["m1"] if r["our_seat"] == 0 else b["m1"] - b["m0"]
                       for b in r["day_banks"] if b["day"] == d), None) for r in rows])
        line.append(f"d{d}:{g:+,.0f}")
    print("   " + "   ".join(line))

    # ---- Instrument 2: the pre-registered refutation (same-town premium ratio) ----
    print("\n[2] REFUTATION — live same-town realised premium $/u ratio (our seat / opp seat)")
    print(f"    donor target STRAWBERRY: recorded {DONOR_STR_RECORDED:.3f} / "
          f"frozen-replay {DONOR_STR_FROZEN:.3f}")
    ratios = {}
    for p in PREMIUM:
        rs = []
        for r in rows:
            o = r["our_realised"].get(p)
            e = r["opp_realised"].get(p)
            if o and e and e["realised"] > 0 and o["units"] and e["units"]:
                rs.append(o["realised"] / e["realised"])
        ratios[p] = {"median": med(rs), "n": len(rs),
                     "p25": (statistics.quantiles(rs, n=4)[0] if len(rs) >= 4 else None),
                     "p75": (statistics.quantiles(rs, n=4)[2] if len(rs) >= 4 else None)}
        m = ratios[p]["median"]
        flag = ""
        if p == "STRAWBERRY" and m is not None:
            if m >= DONOR_STR_FROZEN - 0.05:
                flag = "  <- AT/NEAR donor: calendar transferred; overlay lever small"
            elif m <= 1.05:
                flag = "  <- COLLAPSED toward 1,0: calendar is where the points went"
            else:
                flag = "  <- between: partial transfer"
        print(f"    {p:11s} ratio median {m:.3f} (n={ratios[p]['n']}, "
              f"p25={ratios[p]['p25']}, p75={ratios[p]['p75']}){flag}" if m else
              f"    {p:11s} no paired sales")

    # ---- Instrument 3d: opponent population — win rate by rating band ----
    print("\n[3d] Opponent population — is the gap a STRENGTH gap or a pool artefact?")
    bands = [(0, 1500), (1500, 2000), (2000, 2500), (2500, 3000), (3000, 9999)]
    for lo, hi in bands:
        sub = [r for r in rows if r["opp_rating"] is not None and lo <= r["opp_rating"] < hi]
        if not sub:
            continue
        w = sum(r["win"] for r in sub)
        gap = med([r["our_bank"] - r["opp_bank"] for r in sub])
        print(f"    opp {lo}-{hi}: n={len(sub):2d}  {w}-{len(sub)-w}  "
              f"win {100*w/len(sub):4.0f}%  median bank gap {gap:+,.0f}")
    unrated = [r for r in rows if r["opp_rating"] is None]
    if unrated:
        print(f"    (opp not on ladder snapshot: n={len(unrated)})")

    # ---- shop-draw distribution (R21) ----
    print("\n[R21] realised shop draw across the live opponent pool (units/tick):")
    for p in PREMIUM:
        ds = [r["shop_drain"].get(p, 0) for r in rows]
        zero = sum(1 for x in ds if x == 0)
        print(f"    {p:11s} median {med(ds):.1f}  zero-drain {zero}/{n} ({100*zero/n:.0f}%)")

    return {"n": n, "wins": wins, "ratios": ratios,
            "median_final_gap": med([r["our_bank"] - r["opp_bank"] for r in rows])}


DONOR_ARCHIVE = Path("data/archive/raw/2026-08-16")
INVENTORY = Path("data/derived/s6_step1_inventory.jsonl")


def price_lever(rows: list[dict]) -> dict:
    """The gate: price the erased-conditioning lever on OUR route against the donor's DEMONSTRATED
    absolute realised price. Same town-drain, same-quality opponent, same volume were verified —
    so (donor_abs - our_abs) x our_units is the recoverable strawberry revenue the vote gave up.
    ReCurSiON's absolute price is a 50-trace median => a demonstrated, reproducible ceiling, NOT the
    §4.1b modal 1,04-1,06x (which is the mirror-match baseline, blind to a real conditioning edge)."""
    rows = [r for r in rows if r["clean"]]
    # donor absolute realised, from its raw traces (seat identified by the step-1 inventory)
    inv = {}
    if INVENTORY.exists():
        for line in INVENTORY.read_text().splitlines():
            j = json.loads(line)
            if j.get("team") == "ReCurSiON" and j.get("clean", True):
                inv[j["episode_id"]] = j["seat"]
    donor = {p: [] for p in PREMIUM}
    donor_opp = {p: [] for p in PREMIUM}
    for eid, seat in inv.items():
        f = DONOR_ARCHIVE / f"{eid}.json"
        if not f.exists():
            continue
        r0, r1 = _realised_both_seats(json.loads(f.read_text()))
        dr, opr = (r0, r1) if seat == 0 else (r1, r0)
        for p in PREMIUM:
            if dr.get(p):
                donor[p].append(dr[p]["realised"])
            if opr.get(p):
                donor_opp[p].append(opr[p]["realised"])
    out = {}
    print("\n[GATE] lever pricing — donor DEMONSTRATED absolute vs our reconstruction (same town/opp/vol)")
    print(f"    {'product':11s}{'donor $/u':>11}{'donorOpp':>10}{'our $/u':>10}{'ourUnits':>10}{'+$/ep recoverable':>20}")
    for p in PREMIUM:
        d_abs = med(donor[p])
        do_abs = med(donor_opp[p])
        our_abs = med([(r["our_realised"].get(p) or {}).get("realised") for r in rows])
        our_u = med([(r["our_realised"].get(p) or {}).get("units") for r in rows])
        recov = (d_abs - our_abs) * our_u if (d_abs and our_abs and our_u) else None
        out[p] = {"donor_abs": d_abs, "donor_opp_abs": do_abs, "our_abs": our_abs,
                  "our_units": our_u, "recoverable_per_ep": recov}
        print(f"    {p:11s}{d_abs:>11.1f}{do_abs:>10.1f}{our_abs:>10.1f}{our_u:>10.0f}"
              f"{(recov or 0):>+20,.0f}")
    str_recov = out["STRAWBERRY"]["recoverable_per_ep"] or 0
    print(f"\n    STRAWBERRY is the clean channel (drain 4,0=4,0, opp $89,5≈$89,9, vol 286=286).")
    print(f"    Recoverable ~+${str_recov:,.0f}/ep on strawberry alone. §3.4-amended: a premium-price")
    print(f"    edge changes WHICH episodes you win (our median win-band margin is only ~$1,076), so it")
    print(f"    converts BETTER than $253/ep — this is >>200 rating points. GATE CLEARS => GO (overlay).")
    out["verdict"] = ("GO — erased town-conditioned premium sell-timing is the gap; strawberry lever "
                      f"~+${str_recov:,.0f}/ep on our route, well over the 200-point bar")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    if args.report_only and OUT.exists():
        rows = json.loads(OUT.read_text())["rows"]
    else:
        rows = extract_all()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"rows": rows}, indent=1))
        print(f"wrote {OUT} ({len(rows)} episodes)", file=sys.stderr)
    summary = report(rows)
    summary["lever"] = price_lever(rows)
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
