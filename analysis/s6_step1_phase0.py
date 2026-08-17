#!/usr/bin/env python3
"""S6 step 1 — Phase 0: donor selection, measured (ROADMAP §4.3 S6 step 1; the whole risk).

Step 0 refuted its own lever (C-A) but *relocated* the target: the edge is **cross-turn sell
timing**, worth ~$2.8k scale (leg 1: Valmorlee realises 1,13-1,25x on the same route class in the
same town). That lever is not reachable on a verbatim tape (T2 shed wall), so step 1's asset is a
*modifiable* route reconstructed by §4.5(b)'s method: per-decision majority vote across ≥3 traces of
one submission. This module does the **selection** that gates that build — and per the brief, if no
donor clears all three criteria it STOPS the pass and redirects S6 to C-C (MELON).

The three criteria, in order (all measured, none assumed):
  1. TRACE COUNT — >=3 episodes attributable to one team *on one submission*. Episodes carry only
     TeamNames, no SubmissionId, so "same submission" is established by **action-stream prefix
     identity**: a fixed policy emits a seed-independent day-0 opening (plant/place/hire), so seats
     of one team sharing an opening fingerprint are one submission; a team that re-uploaded mid-day
     splits into >1 fingerprint cluster.
  2. AGREEMENT — per decision point, the share of a submission's traces agreeing on the action,
     for the farmer/hands (production) channel and the market channel **separately** (they differ:
     production is near-deterministic, market reacts to the town). V16-RC5 reports ~99,91% market
     agreement across its three traces; a donor whose traces agree at ~60% is not reconstructible.
  3. CALENDAR QUALITY — replay the candidate against our three existing donor tapes with the town
     held fixed (step 0's leg-1 instrument) and read its realised premium $/unit ratio; require
     >= the Valmorlee tape's.

This module is Phase 0 = criteria 1 & 2 (inventory + agreement) plus the same-submission clustering.
Criterion 3 (the same-town instrument) is run by analysis/s6_step1_calendar.py on the selected
candidates, reusing analysis/s6_step0_leg1.py's machinery.

Pass 1 (`inventory`) reads all 700 episodes once, extracts per-seat metadata + opening fingerprints,
and writes a compact JSONL — no action streams are held in memory across files. Pass 2 (`agreement`)
re-reads only the episodes of the candidate teams to compute per-channel agreement. Both outputs are
derived from competition action streams and are **gitignored** (§2.4b / R11).

Usage:
    python analysis/s6_step1_phase0.py inventory   # pass 1: scan all 700, write inventory.jsonl
    python analysis/s6_step1_phase0.py cluster      # analyse inventory: teams x submissions x traces
    python analysis/s6_step1_phase0.py agreement     # pass 2: per-channel agreement for candidates
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARCHIVE = ROOT / "data" / "archive" / "raw" / "2026-08-16"
DERIVED = ROOT / "data" / "derived"
INVENTORY = DERIVED / "s6_step1_inventory.jsonl"
CLUSTERS = DERIVED / "s6_step1_clusters.json"
AGREEMENT = DERIVED / "s6_step1_agreement.json"

LIVE_ENGINE = "1.32.7"          # §4.1b: the live engine; stale episodes are excluded
TURNS_PER_DAY = 24
OPEN_STEPS = 48                 # day-0+day-1 opening window for submission-identity fingerprints
PREMIUM = ("STRAWBERRY", "WOOL", "MILK")


def _canon(x) -> str:
    """Stable string form of one channel's action list for a step (order-preserving)."""
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _seat_streams(steps: list, seat: int) -> tuple[list, list, list]:
    """(production, market, status) per active step. production = [farmer]+[hands] canonical
    string per step; market = canonical market string per step. Aligned to s1_extract_donors:
    the action returned when observing obs.step==t is steps[t+1][seat].action, so we read
    steps[1:] as the decision sequence. Inactive/None steps become an explicit PASS token."""
    prod, market, status = [], [], []
    for t in range(1, len(steps)):
        cell = steps[t][seat]
        act = cell.get("action")
        st = cell.get("status")
        status.append(st)
        if not act:
            prod.append("PASS")
            market.append("[]")
            continue
        prod.append(_canon([act.get("farmer", []), act.get("hands", [])]))
        market.append(_canon(act.get("market", [])))
    return prod, market, status


def scan_episode(path: Path) -> list[dict]:
    d = json.loads(path.read_text())
    version = d.get("module_version")
    cfg = d.get("configuration", {})
    info = d.get("info", {})
    steps = d["steps"]
    teams = info.get("TeamNames") or [None, None]
    rewards = d.get("rewards") or [None, None]
    eid = info.get("EpisodeId")
    seed = info.get("seed")
    out = []
    for seat in (0, 1):
        prod, market, status = _seat_streams(steps, seat)
        active = sum(1 for s in status if s == "ACTIVE")
        clean = set(status) <= {"ACTIVE", "DONE", "INACTIVE"}
        out.append({
            "episode_id": eid,
            "seat": seat,
            "team": teams[seat],
            "opponent_team": teams[1 - seat],
            "reward": rewards[seat],
            "seed": seed,
            "version": version,
            "interval": cfg.get("townCenterSellInterval"),
            "n_active": active,
            "clean": clean,
            # submission-identity fingerprints. NB (Phase 0 finding): the opening is shared
            # field-wide (the crowded meta line, §4.4#7), so fp_*_open does NOT discriminate
            # submissions — everyone shares it. The full-stream fingerprints do the work.
            "fp_prod_open": _sha("|".join(prod[:OPEN_STEPS])),
            "fp_prod_full": _sha("|".join(prod)),
            "fp_market_open": _sha("|".join(market[:OPEN_STEPS])),
            "fp_market_full": _sha("|".join(market)),
        })
    return out


def cmd_inventory(args) -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    files = sorted(ARCHIVE.glob("*.json"))
    if not files:
        raise SystemExit(f"no episodes under {ARCHIVE}")
    print(f"scanning {len(files)} episodes from {ARCHIVE}")
    n = 0
    with INVENTORY.open("w", encoding="utf-8") as fh:
        for i, path in enumerate(files):
            try:
                rows = scan_episode(path)
            except Exception as e:  # noqa: BLE001
                print(f"  {path.name}: SKIP ({e})", file=sys.stderr)
                continue
            for r in rows:
                fh.write(json.dumps(r) + "\n")
                n += 1
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(files)} files, {n} seats")
    print(f"wrote {INVENTORY} ({n} seat-rows)")
    return 0


def _load_inventory() -> list[dict]:
    if not INVENTORY.exists():
        raise SystemExit(f"{INVENTORY} missing — run `inventory` first")
    return [json.loads(line) for line in INVENTORY.read_text().splitlines() if line.strip()]


def cmd_cluster(args) -> int:
    """Team-centric view. The opening is shared field-wide (§4.4#7), so submissions are separated
    not by the opening but by the *market* channel — the contested layer. For each live-engine team
    with >=3 clean seats, report: distinct opening fingerprints (a proxy for how many production
    variants / re-uploads), distinct full-production and full-market fingerprints (how self-identical
    the traces are), and median/max reward (the rating proxy). Same-submission clustering of the
    market channel and true agreement rates are computed by `agreement` on the reloaded streams."""
    import statistics
    rows = _load_inventory()
    live = [r for r in rows if r["version"] == LIVE_ENGINE and r["interval"] == 24 and r["clean"]]
    stale = [r for r in rows if r["version"] != LIVE_ENGINE]
    print(f"{len(rows)} seat-rows  |  live {LIVE_ENGINE}: {len(live)}  |  stale/other: {len(rows) - len(live)}")

    # Field-wide opening concentration: how crowded is the shared meta line?
    open_counts = defaultdict(int)
    for r in live:
        open_counts[r["fp_prod_open"]] += 1
    top_open = sorted(open_counts.values(), reverse=True)[:5]
    print(f"distinct openings among {len(live)} live seats: {len(open_counts)}  "
          f"(top clusters: {top_open})")

    by_team: dict[str, list] = defaultdict(list)
    for r in live:
        by_team[r["team"]].append(r)

    teams = []
    for team, members in by_team.items():
        rewards = [m["reward"] for m in members if m["reward"] is not None]
        teams.append({
            "team": team,
            "n_traces": len(members),
            "n_open_fp": len({m["fp_prod_open"] for m in members}),
            "n_prod_full_fp": len({m["fp_prod_full"] for m in members}),
            "n_market_full_fp": len({m["fp_market_full"] for m in members}),
            "median_reward": statistics.median(rewards) if rewards else None,
            "max_reward": max(rewards) if rewards else None,
            "episodes": sorted((m["episode_id"], m["seat"]) for m in members),
            "seeds": sorted({m["seed"] for m in members}),
        })

    teams.sort(key=lambda t: (-t["n_traces"], -(t["median_reward"] or 0)))
    eligible = [t for t in teams if t["n_traces"] >= 3]
    CLUSTERS.write_text(json.dumps(
        {"n_live_seats": len(live), "n_stale": len(stale), "n_teams": len(by_team),
         "n_distinct_openings": len(open_counts), "eligible": eligible, "all_teams": teams}, indent=1))

    print(f"\n{len(by_team)} distinct live teams; {len(eligible)} with >=3 clean live traces\n")
    print(f"{'team':<22}{'traces':>7}{'openFP':>7}{'prodFP':>7}{'mktFP':>6}"
          f"{'med_reward':>12}{'max_reward':>12}")
    for t in eligible[:45]:
        print(f"{(t['team'] or '?')[:21]:<22}{t['n_traces']:>7}{t['n_open_fp']:>7}"
              f"{t['n_prod_full_fp']:>7}{t['n_market_full_fp']:>6}"
              f"{(t['median_reward'] or 0):>12,.0f}{(t['max_reward'] or 0):>12,.0f}")
    print(f"\nwrote {CLUSTERS}")
    return 0


def _reload_streams(episode_id: int, seat: int) -> tuple[list, list, list]:
    d = json.loads((ARCHIVE / f"{episode_id}.json").read_text())
    return _seat_streams(d["steps"], seat)


def _premium_sold_at(market_canon: str) -> bool:
    return any(p in market_canon for p in PREMIUM) and "SELL" in market_canon


def _agreement_for_traces(traces: list[tuple[list, list]]) -> dict:
    """traces = [(prod_stream, market_stream), ...] aligned by step index. Per step, the share of
    traces emitting the modal action, for production and market separately; plus the same restricted
    to steps where >=1 trace sells a premium product (the contested calendar)."""
    from collections import Counter
    n = len(traces)
    T = min(len(p) for p, _ in traces)
    prod_share, mkt_share, mkt_prem_share = [], [], []
    prod_unanimous = mkt_unanimous = 0
    disagree_prod, disagree_mkt = [], []
    for t in range(T):
        pc = Counter(traces[i][0][t] for i in range(n))
        mc = Counter(traces[i][1][t] for i in range(n))
        ps = pc.most_common(1)[0][1] / n
        ms = mc.most_common(1)[0][1] / n
        prod_share.append(ps)
        mkt_share.append(ms)
        prod_unanimous += (ps == 1.0)
        mkt_unanimous += (ms == 1.0)
        if ps < 1.0:
            disagree_prod.append(t)
        if ms < 1.0:
            disagree_mkt.append(t)
        if any(_premium_sold_at(traces[i][1][t]) for i in range(n)):
            mkt_prem_share.append(ms)
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None  # noqa: E731
    return {
        "n_traces": n, "n_steps": T,
        "prod_agreement": mean(prod_share),
        "market_agreement": mean(mkt_share),
        "market_agreement_premium_steps": mean(mkt_prem_share),
        "n_premium_sell_steps": len(mkt_prem_share),
        "prod_unanimous_frac": prod_unanimous / T,
        "market_unanimous_frac": mkt_unanimous / T,
        "n_disagree_prod": len(disagree_prod),
        "n_disagree_market": len(disagree_mkt),
    }


# Shortlist for criterion 2/3 — trace-rich and/or high-reward teams, plus the frozen-tape extremes
# (Peter Parker, Manu) and the incumbent Ueddy for calibration. Chosen from `cluster` output.
CANDIDATE_TEAMS = [
    "Matteo123383iend", "GUGUGAGA", "Junichiro Morita", "shiggriculture", "Victor @ Tufa Labs",
    "カワシギ", "Ueddy", "Peter Parker", "Manu Nicholas Jacob", "ИТМОНИ АНАЛЬНИКИ AI B",
    "Kostiantyn Isaienkov", "Dmitry Larko", "One-For-All", "Jeki Wan Taufik", "Yubo WANG",
]


def cmd_agreement(args) -> int:
    """Per-channel cross-trace agreement (criterion 2) for the shortlist. Reloads each team's
    episodes (capped) and reports production vs market agreement separately."""
    rows = _load_inventory()
    live = [r for r in rows if r["version"] == LIVE_ENGINE and r["interval"] == 24 and r["clean"]]
    by_team: dict[str, list] = defaultdict(list)
    for r in live:
        by_team[r["team"]].append(r)

    teams = args.teams or CANDIDATE_TEAMS
    cap = args.cap
    out = {}
    print(f"{'team':<22}{'used':>5}{'prodAgr':>9}{'mktAgr':>8}{'mktPrem':>8}"
          f"{'prodUnan':>9}{'mktUnan':>8}{'premSteps':>10}")
    for team in teams:
        members = by_team.get(team)
        if not members or len(members) < 3:
            print(f"{team[:21]:<22}  <3 traces — skip")
            continue
        members = sorted(members, key=lambda m: (m["episode_id"], m["seat"]))[:cap]
        traces = []
        for m in members:
            prod, market, _ = _reload_streams(m["episode_id"], m["seat"])
            traces.append((prod, market))
        a = _agreement_for_traces(traces)
        a["episodes_used"] = [(m["episode_id"], m["seat"]) for m in members]
        out[team] = a
        print(f"{team[:21]:<22}{a['n_traces']:>5}{a['prod_agreement']:>9.3f}"
              f"{a['market_agreement']:>8.3f}{(a['market_agreement_premium_steps'] or 0):>8.3f}"
              f"{a['prod_unanimous_frac']:>9.3f}{a['market_unanimous_frac']:>8.3f}"
              f"{a['n_premium_sell_steps']:>10}")
    AGREEMENT.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {AGREEMENT}")
    return 0


CALENDAR = DERIVED / "s6_step1_calendar.json"


def _realised_premium(steps: list, cfg: dict) -> tuple[dict, dict, list, list]:
    """Realised premium $/u + units for both seats from recorded transitions, plus the set of
    step indices on which each seat sold a premium product (the metering signature). Uses the same
    _transition_events path as s6_step0_leg1 — exact, no replay."""
    from collections import defaultdict as dd
    from harness.metrics import _transition_events
    rev = [dd(float), dd(float)]
    units = [dd(int), dd(int)]
    sell_steps = [set(), set()]
    for i in range(1, len(steps)):
        _a, _o, sales, _ab, _h = _transition_events(steps[i - 1], steps[i], cfg)
        for seat in (0, 1):
            for s in sales[seat]:
                if s["item"] in PREMIUM:
                    rev[seat][s["item"]] += s["price"]
                    units[seat][s["item"]] += 1
                    sell_steps[seat].add(i)
    out = []
    for seat in (0, 1):
        out.append({p: {"realised": rev[seat][p] / units[seat][p], "units": units[seat][p]}
                    for p in PREMIUM if units[seat].get(p)})
    return out[0], out[1], sorted(sell_steps[0]), sorted(sell_steps[1])


def cmd_calendar(args) -> int:
    """Criterion 3 (exact, town-controlled, replay-free): for each candidate team's recorded
    episodes, realised premium $/u ratio vs the SAME-TOWN opponent seat (§4.1b's control). A ratio
    >1 means the team beats its same-town opponents on realised price = a good calendar. Reports
    median ratio per product, premium volume, and the metering spread (distinct premium sell-steps).
    `--split-open` keys candidates by (team, opening fingerprint) to separate a team's submissions."""
    import statistics
    rows = _load_inventory()
    live = [r for r in rows if r["version"] == LIVE_ENGINE and r["interval"] == 24 and r["clean"]]
    key = (lambda r: (r["team"], r["fp_prod_open"][:8])) if args.split_open else (lambda r: r["team"])
    by_key: dict = defaultdict(list)
    for r in live:
        by_key[key(r)].append(r)

    if getattr(args, "all", False):
        teams = [t["team"] for t in json.loads(CLUSTERS.read_text())["eligible"]]
    else:
        teams = args.teams or CANDIDATE_TEAMS
    want = set(teams)
    cands = [k for k in by_key if (k[0] if isinstance(k, tuple) else k) in want and len(by_key[k]) >= 3]
    out = {}
    print(f"{'candidate':<30}{'eps':>4}{'STR':>8}{'WOOL':>8}{'MILK':>8}"
          f"{'strVol':>8}{'sellSteps':>10}")
    for k in cands:
        members = sorted(by_key[k], key=lambda m: (m["episode_id"], m["seat"]))[:args.cap]
        ratios = {p: [] for p in PREMIUM}
        vols = {p: [] for p in PREMIUM}
        sell_step_counts = []
        for m in members:
            d = json.loads((ARCHIVE / f"{m['episode_id']}.json").read_text())
            r0, r1, ss0, ss1 = _realised_premium(d["steps"], d["configuration"])
            fs, os_ = (m["seat"], 1 - m["seat"])
            focal = (r0, r1)[fs]
            opp = (r0, r1)[os_]
            ss = (ss0, ss1)[fs]
            sell_step_counts.append(len(ss))
            for p in PREMIUM:
                if focal.get(p) and opp.get(p) and focal[p]["units"] and opp[p]["units"]:
                    ratios[p].append(focal[p]["realised"] / opp[p]["realised"])
                if focal.get(p):
                    vols[p].append(focal[p]["units"])
        name = f"{k[0]} [{k[1]}]" if isinstance(k, tuple) else k
        rec = {
            "candidate": name, "n_eps": len(members),
            "ratio_med": {p: (statistics.median(ratios[p]) if ratios[p] else None) for p in PREMIUM},
            "ratio_n": {p: len(ratios[p]) for p in PREMIUM},
            "vol_med": {p: (statistics.median(vols[p]) if vols[p] else None) for p in PREMIUM},
            "sell_steps_med": statistics.median(sell_step_counts) if sell_step_counts else None,
        }
        out[name] = rec
        rm = rec["ratio_med"]
        print(f"{name[:29]:<30}{rec['n_eps']:>4}"
              f"{(rm['STRAWBERRY'] or 0):>8.3f}{(rm['WOOL'] or 0):>8.3f}{(rm['MILK'] or 0):>8.3f}"
              f"{(rec['vol_med']['STRAWBERRY'] or 0):>8.0f}{(rec['sell_steps_med'] or 0):>10.0f}")
    CALENDAR.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {CALENDAR}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory")
    sub.add_parser("cluster")
    ag = sub.add_parser("agreement")
    ag.add_argument("--teams", nargs="*", help="override the shortlist")
    ag.add_argument("--cap", type=int, default=30, help="max traces per team")
    cal = sub.add_parser("calendar")
    cal.add_argument("--teams", nargs="*", help="override the shortlist")
    cal.add_argument("--cap", type=int, default=40, help="max episodes per candidate")
    cal.add_argument("--split-open", action="store_true", help="key by (team, opening fp)")
    cal.add_argument("--all", action="store_true", help="scan every eligible team from clusters.json")
    args = ap.parse_args()
    return {"inventory": cmd_inventory, "cluster": cmd_cluster,
            "agreement": cmd_agreement, "calendar": cmd_calendar}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
