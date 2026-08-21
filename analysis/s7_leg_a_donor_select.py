#!/usr/bin/env python3
"""S7 Leg A — Ship A donor selection (ROADMAP §7.1).

The reconstruction instrument works and was pointed at a #9 donor. The route ships at the donor's
own ceiling — so re-donor to a top-4 route. Four candidates on the 2026-08-20 leaderboard:
Ryo Hasegawa 3.147 · tetsuya 3.095 · Arman Tuganbaev 3.053 · Crop Dusta 3.017.

This module fits §7.1's whole front gate in one script — it's a *time-boxed gate at the front of a
shipping pass* (§3), not its own pass. It runs on the mapping produced by fetching each candidate
submission's most recent public episodes via `kaggle competitions episodes`, so the "one submission"
assignment is EXPLICIT (submission_id, not opening-fingerprint clustering) — cleaner than the S6
Phase 0 pass on ReCurSiON.

The three §7.1 criteria, run in order:
  1. TRACE COUNT — ≥3 traces of one submission (explicit via the CSV mapping)
  2. AGREEMENT — cross-trace prod/market modal share (compare to ReCurSiON's 0.993 / 0.980)
  3. TOWN-CONTROLLED RATIO — realised premium $/u ratio vs the same-town opponent seat,
     straight from the recorded episode (never median reward, which is 99% town luck; §3)

Plus §7.1's 2-medoid check on the market/full stream (never the opening — that's byte-identical
across 87% of live seats), to confirm each candidate is one submission not two.

Selection order: rank by town-controlled ratio (criterion 3, the top-team edge).
Pre-registered "ship anyway": if the best candidate's agreement is materially lower than
ReCurSiON's, ship the highest-agreement above 2.900 regardless, recording the agreement.
Kill: if no top-4 team clears 3 traces of one submission, go straight to §7.2.

Usage:
    python analysis/s7_leg_a_donor_select.py select \
        --mapping /path/to/canonical_donor_traces.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("S6_ARCHIVE_DATE", "2026-08-21")
from analysis.s6_step1_phase0 import (  # noqa: E402
    ARCHIVE, DERIVED, LIVE_ENGINE, PREMIUM,
    _agreement_for_traces, _reload_streams, _realised_premium,
)

# ReCurSiON benchmark for the "ship anyway" rule (§7.1)
RECURSION_PROD_AGR = 0.993
RECURSION_MARKET_AGR = 0.980
# "materially lower" — the pre-registered comparison says "0.95 vs 0.99 is still shippable"; a
# 5 pp drop keeps the ship-anyway branch open when a top-4 candidate is a near-open-loop policy
# that just happens to be slightly noisier than ReCurSiON.
AGR_MATERIAL_DROP = 0.05
# KILL threshold — §7.1 names カワシギ at 0.31 as "town-adaptive, unreconstructible". A candidate
# where the market-vote loses ~10% of its state (market_agr < 0.90) produces a chimera route: the
# calendar and quantities of one town paired with the tactics of another. Halfway between
# ReCurSiON (0.980) and カワシギ (0.31) — anything under this belongs to the KILL branch.
KILL_MARKET_AGR = 0.90

# Team → live-ladder rating on the 2026-08-20 snapshot (for the "ship anyway ≥2.900" gate)
LADDER = {
    "Ryo Hasegawa": 3147.0,
    "tetsuya": 3095.3,
    "Arman Tuganbaev": 3053.1,
    "Crop Dusta": 3017.2,
}


def _pairwise_market_distance(streams: list[list[str]]) -> np.ndarray:
    n, T = len(streams), len(streams[0])
    D = np.zeros((n, n))
    for i, j in combinations(range(n), 2):
        d = sum(1 for t in range(T) if streams[i][t] != streams[j][t]) / T
        D[i, j] = D[j, i] = d
    return D


def _best_2_medoid(D: np.ndarray) -> tuple[tuple[int, int], np.ndarray]:
    """Exhaustive 2-medoid: pick the medoid pair minimising total assignment cost."""
    n = D.shape[0]
    best_cost, best = float("inf"), None
    for m0, m1 in combinations(range(n), 2):
        labels = (D[:, m1] < D[:, m0]).astype(int)
        cost = sum(D[i, (m1 if labels[i] else m0)] for i in range(n))
        if cost < best_cost:
            best_cost, best = cost, (labels.copy(), (m0, m1))
    return best[1], best[0]


def _silhouette(D: np.ndarray, labels: np.ndarray) -> float:
    sils = []
    n = D.shape[0]
    for i in range(n):
        same = [j for j in range(n) if labels[j] == labels[i] and j != i]
        other = [j for j in range(n) if labels[j] != labels[i]]
        if not same or not other:
            continue
        a = statistics.fmean(D[i, j] for j in same)
        b = statistics.fmean(D[i, j] for j in other)
        sils.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return statistics.fmean(sils) if sils else 0.0


def _town_controlled_ratio(members: list[dict]) -> dict:
    """Per-product realised $/u ratio vs the same-town opponent seat (§7.1 criterion 3).
    Median across the candidate's episodes; also returns per-episode ratios for a decisive
    "controlled" claim."""
    ratios = {p: [] for p in PREMIUM}
    vols = {p: [] for p in PREMIUM}
    for m in members:
        d = json.loads((ARCHIVE / f"{m['episode_id']}.json").read_text())
        r0, r1, _ss0, _ss1 = _realised_premium(d["steps"], d["configuration"])
        focal_seat = m["seat"]
        focal = (r0, r1)[focal_seat]
        opp = (r0, r1)[1 - focal_seat]
        for p in PREMIUM:
            if focal.get(p) and opp.get(p) and focal[p]["units"] and opp[p]["units"]:
                ratios[p].append(focal[p]["realised"] / opp[p]["realised"])
            if focal.get(p):
                vols[p].append(focal[p]["units"])
    return {
        "ratio_med": {p: (statistics.median(ratios[p]) if ratios[p] else None) for p in PREMIUM},
        "ratio_n": {p: len(ratios[p]) for p in PREMIUM},
        "ratio_all": {p: ratios[p] for p in PREMIUM},
        "vol_med": {p: (statistics.median(vols[p]) if vols[p] else None) for p in PREMIUM},
    }


def _load_mapping(path: Path) -> dict[tuple[str, int], list[dict]]:
    """{(team, submission_id): [{episode_id, seat, ...}, ...]}"""
    rows = json.loads(path.read_text())
    live = _live_inventory()
    live_map = {(r["episode_id"], r["seat"]): r for r in live}
    grouped: dict = defaultdict(list)
    for r in rows:
        eid, seat = r["episode_id"], r["seat"]
        info = live_map.get((eid, seat))
        if not info:
            continue
        if info["version"] != LIVE_ENGINE or not info["clean"] or info["interval"] != 24:
            continue
        grouped[(r["team"], r["submission_id"])].append(info)
    return dict(grouped)


def _live_inventory() -> list[dict]:
    from analysis.s6_step1_phase0 import _load_inventory
    return _load_inventory()


def cmd_select(args) -> int:
    mapping = _load_mapping(Path(args.mapping))
    if not mapping:
        raise SystemExit("no candidates — is the archive scanned + inventory built?")

    print(f"S7 Leg A donor selection — archive {ARCHIVE.name}\n")
    print(f"benchmark: ReCurSiON prod_agr={RECURSION_PROD_AGR:.3f}, "
          f"market_agr={RECURSION_MARKET_AGR:.3f}\n")

    per_candidate: dict = {}
    print(f"{'candidate':<32}{'sub_id':>10}{'traces':>7}{'prod':>8}{'market':>8}"
          f"{'STR':>7}{'WOOL':>7}{'MILK':>7}{'sil':>6}{'domFrac':>8}")

    for (team, sub_id), members in sorted(mapping.items(), key=lambda kv: -LADDER.get(kv[0][0], 0)):
        n = len(members)
        if n < 3:
            print(f"{team[:31]:<32}{sub_id:>10}{n:>7}  <3 traces — SKIP")
            continue
        traces = []
        for m in members:
            prod, market, _ = _reload_streams(m["episode_id"], m["seat"])
            traces.append((prod, market))
        agr = _agreement_for_traces(traces)

        # 2-medoid check on market stream (§7.1 — reads market/full, not opening)
        market_streams = [t[1] for t in traces]
        T = min(len(s) for s in market_streams)
        market_streams = [s[:T] for s in market_streams]
        D = _pairwise_market_distance(market_streams)
        medoids, labels = _best_2_medoid(D)
        sil = _silhouette(D, labels)
        sizes = (int((labels == 0).sum()), int((labels == 1).sum()))
        dom_frac = max(sizes) / n
        dom_label = 0 if sizes[0] >= sizes[1] else 1
        dom_episodes = [(members[i]["episode_id"], members[i]["seat"])
                        for i in range(n) if labels[i] == dom_label]

        cal = _town_controlled_ratio(members)
        rm = cal["ratio_med"]

        rec = {
            "team": team, "submission_id": sub_id, "n_traces": n,
            "ladder_rating_2026_08_20": LADDER.get(team),
            "agreement": {"prod": agr["prod_agreement"],
                          "market": agr["market_agreement"],
                          "market_premium_steps": agr["market_agreement_premium_steps"],
                          "n_premium_sell_steps": agr["n_premium_sell_steps"]},
            "medoid_2": {"sizes": sizes, "silhouette": sil,
                         "dominant_fraction": dom_frac, "medoids": list(medoids),
                         "dominant_cluster_episodes": dom_episodes},
            "town_controlled": {"ratio_med": rm, "ratio_n": cal["ratio_n"],
                                 "vol_med": cal["vol_med"]},
            "episodes_used": [(m["episode_id"], m["seat"]) for m in members],
        }
        per_candidate[f"{team}|{sub_id}"] = rec

        print(f"{team[:31]:<32}{sub_id:>10}{n:>7}"
              f"{agr['prod_agreement']:>8.3f}{agr['market_agreement']:>8.3f}"
              f"{(rm['STRAWBERRY'] or 0):>7.3f}{(rm['WOOL'] or 0):>7.3f}{(rm['MILK'] or 0):>7.3f}"
              f"{sil:>6.2f}{dom_frac:>8.2f}")

    # ----- selection -----
    def _ratio_score(rec: dict) -> float:
        r = rec["town_controlled"]["ratio_med"]
        vals = [r[p] for p in PREMIUM if r.get(p) is not None]
        return statistics.fmean(vals) if vals else 0.0

    def _one_submission(rec: dict) -> bool:
        # §7.1 "2-medoid check against a two-submission population"
        # Two submissions ⇒ balanced split + clear silhouette + significant medoid distance.
        # A peeled tail (dom_frac ≥ 0.8) is one policy per s6_step1b_cluster's logic.
        m = rec["medoid_2"]
        return not (m["dominant_fraction"] < 0.80 and m["silhouette"] >= 0.5)

    ranked = sorted(per_candidate.values(),
                    key=lambda r: (-_ratio_score(r), -r["agreement"]["market"]))
    if not ranked:
        verdict = "KILL — no candidate cleared 3 traces of one submission. Go to §7.2."
        print(f"\nVERDICT: {verdict}")
        (DERIVED / "s7_leg_a_selection.json").write_text(json.dumps(
            {"per_candidate": per_candidate, "verdict": verdict}, indent=1))
        return 3

    best_ratio = ranked[0]
    best_agr = max(per_candidate.values(), key=lambda r: r["agreement"]["market"])
    material = (RECURSION_MARKET_AGR - best_ratio["agreement"]["market"]) > AGR_MATERIAL_DROP
    single_sub = _one_submission(best_ratio)

    # §7.1's LITERAL KILL condition is trace-count only: "no top-4 team clears 3 traces of one
    # submission". Every candidate here has 15 — so the literal kill does NOT fire. But the numbers
    # measure a strong caveat: every candidate is far below the KILL_MARKET_AGR floor (halfway
    # between ReCurSiON's 0.980 and カワシギ's 0.31), so the reconstruction may be a chimera. That is
    # a judgment call the ladder is the only instrument to settle (§7.1's own wording).
    max_market = max(r["agreement"]["market"] for r in per_candidate.values())
    caveat = None
    if max_market < KILL_MARKET_AGR:
        caveat = (f"CAVEAT — max market_agreement across top-4 is {max_market:.3f} (< advisory "
                  f"threshold {KILL_MARKET_AGR:.2f}). The top-4 population is highly state-adaptive; "
                  f"a majority-vote reconstruction of the chosen candidate is likely a chimera "
                  f"(calendar of one town, tactics of another). §7.1's literal KILL is trace-count "
                  f"only and does not fire; the spirit reading (§5.3(c) state-aliasing) would go "
                  f"straight to §7.2 with both slots. Escalate before upload.")

    print("\n--- selection ---")
    print(f"top by town-controlled ratio: {best_ratio['team']} sub={best_ratio['submission_id']}  "
          f"mean premium ratio={_ratio_score(best_ratio):.3f}  market_agr={best_ratio['agreement']['market']:.3f}  "
          f"single-submission={single_sub}")
    print(f"top by agreement           : {best_agr['team']} sub={best_agr['submission_id']}  "
          f"market_agr={best_agr['agreement']['market']:.3f}  "
          f"mean premium ratio={_ratio_score(best_agr):.3f}")

    if not single_sub:
        note = ("top-by-ratio candidate splits 2-way — the reconstruction must carry the larger "
                "cluster (kill (ii) fires, s6_step1b handling). Proceeding with the candidate.")
    else:
        note = "top-by-ratio candidate is one submission (2-medoid check passed)."
    print(note)

    if material:
        rating = best_agr.get("ladder_rating_2026_08_20") or 0
        if rating >= 2900:
            chosen = best_agr
            rule = ("SHIP ANYWAY — top-by-ratio agreement materially below ReCurSiON's; "
                    "highest-agreement candidate above 2.900 selected.")
        else:
            chosen = best_ratio
            rule = ("SHIP TOP-BY-RATIO — top-by-agreement is under 2.900, so ratio wins by default.")
    else:
        chosen = best_ratio
        rule = ("SHIP TOP-BY-RATIO — best agreement not materially lower than ReCurSiON's.")

    verdict = (f"SELECT {chosen['team']} submission {chosen['submission_id']} "
               f"(rating {chosen['ladder_rating_2026_08_20']}, "
               f"market_agr {chosen['agreement']['market']:.3f}, "
               f"prod_agr {chosen['agreement']['prod']:.3f}, "
               f"mean premium ratio {_ratio_score(chosen):.3f}). {rule}")
    print(f"\nVERDICT: {verdict}")
    if caveat:
        print(f"\n{caveat}")

    restrict_to_cluster = None
    if not single_sub:
        restrict_to_cluster = chosen["medoid_2"]["dominant_cluster_episodes"]

    out = {
        "archive_date": ARCHIVE.name,
        "benchmark": {"prod_agr": RECURSION_PROD_AGR, "market_agr": RECURSION_MARKET_AGR},
        "advisory_kill_threshold": {"market_agr": KILL_MARKET_AGR},
        "per_candidate": per_candidate,
        "chosen": {"team": chosen["team"], "submission_id": chosen["submission_id"]},
        "restrict_to_cluster": restrict_to_cluster,
        "verdict": verdict,
        "notes": note,
        "caveat": caveat,
    }
    (DERIVED / "s7_leg_a_selection.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {DERIVED / 's7_leg_a_selection.json'} (gitignored)")
    if caveat:
        return 4  # select-with-caveat: escalate before upload
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--mapping", required=True,
                   help="canonical_donor_traces.json — list of {episode_id, seat, team, submission_id}")
    args = ap.parse_args()
    return {"select": cmd_select}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
