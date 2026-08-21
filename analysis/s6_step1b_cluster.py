#!/usr/bin/env python3
"""S6 step 1b, item 1 — one submission or two? (kill (ii), R31)

The opening fingerprint is dead as a submission test: 87% of the field shares it byte-for-byte,
and ReCurSiON's 50 traces carry 50 distinct `fp_market_full`. So "one submission" must be tested
on the *market decision* stream, not the opening (R31). A majority vote over a population with two
modes is a blend that measures neither policy (kill (ii)): if the 50 traces split, we re-vote per
cluster and carry the larger one forward.

Paper only — no episodes. Method:
  * pairwise market-decision distance between the 50 traces = fraction of the 719 aligned steps on
    which the two traces emit a different market action (a Hamming distance over canonical actions);
  * 2-medoid clustering (exhaustive over medoid pairs — 50 points, trivial), the cheapest honest
    2-cluster; report the mean silhouette. A genuine 2-submission blend shows a clear gap
    (between-cluster >> within-cluster, high silhouette); one town-conditioned policy does not
    (the split is arbitrary, silhouette ~0, the two "clusters" are indistinguishable);
  * the decisive check the kill actually rests on: re-vote the majority stream *within each cluster*
    and measure how much the two cluster-modal routes disagree on the contested market channel. If
    they agree ~as well as the whole population's own cross-trace agreement (0.987), there is one
    policy and the single majority vote is unbiased by the split.

Usage:
    python analysis/s6_step1b_cluster.py --team ReCurSiON
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s6_step1_phase0 import _reload_streams  # noqa: E402
from analysis.s6_step1_reconstruct import _team_members  # noqa: E402

DERIVED = ROOT / "data" / "derived"


def _market_streams(team: str, cap: int) -> tuple[list[list[str]], list[dict]]:
    members = _team_members(team)[:cap]
    streams = []
    for m in members:
        _prod, market, _ = _reload_streams(m["episode_id"], m["seat"])
        streams.append(market)
    T = min(len(s) for s in streams)
    return [s[:T] for s in streams], members


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
        labels = (D[:, m1] < D[:, m0]).astype(int)  # 0 -> m0, 1 -> m1
        cost = sum(D[i, (m1 if labels[i] else m0)] for i in range(n))
        if cost < best_cost:
            best_cost, best = cost, (labels.copy(), (m0, m1))
    return best[1], best[0]


def _silhouette(D: np.ndarray, labels: np.ndarray) -> float:
    n = D.shape[0]
    sils = []
    for i in range(n):
        same = [j for j in range(n) if labels[j] == labels[i] and j != i]
        other = [j for j in range(n) if labels[j] != labels[i]]
        if not same or not other:
            continue
        a = statistics.fmean(D[i, j] for j in same)
        b = statistics.fmean(D[i, j] for j in other)
        sils.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return statistics.fmean(sils) if sils else 0.0


def _cluster_modal(streams: list[list[str]], idx: list[int]) -> list[str]:
    T = len(streams[0])
    return [Counter(streams[i][t] for i in idx).most_common(1)[0][0] for t in range(T)]


def _agreement(a: list[str], b: list[str]) -> float:
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--cap", type=int, default=50)
    args = ap.parse_args()

    streams, members = _market_streams(args.team, args.cap)
    n, T = len(streams), len(streams[0])
    print(f"team={args.team}  traces={n}  aligned market steps={T}")
    print(f"distinct full-market fingerprints: {len({tuple(s) for s in streams})} "
          f"(expected {n} for a town-conditioned policy)")

    D = _pairwise_market_distance(streams)
    off = [D[i, j] for i, j in combinations(range(n), 2)]
    print(f"\npairwise market-decision distance (fraction of {T} steps differing):")
    print(f"  min={min(off):.4f}  median={statistics.median(off):.4f}  "
          f"mean={statistics.fmean(off):.4f}  max={max(off):.4f}  sd={statistics.pstdev(off):.4f}")

    (m0, m1), labels = _best_2_medoid(D)
    sizes = (int((labels == 0).sum()), int((labels == 1).sum()))
    sil = _silhouette(D, labels)
    print(f"\nbest 2-medoid split: sizes {sizes}  medoids=traces[{m0},{m1}]  "
          f"mean silhouette={sil:.3f}")

    within = [D[i, j] for i, j in combinations(range(n), 2) if labels[i] == labels[j]]
    between = [D[i, j] for i, j in combinations(range(n), 2) if labels[i] != labels[j]]
    print(f"  within-cluster  dist: mean={statistics.fmean(within):.4f}")
    print(f"  between-cluster dist: mean={statistics.fmean(between):.4f}  "
          f"(ratio between/within = {statistics.fmean(between)/statistics.fmean(within):.3f})")

    # The decisive check: do the two clusters vote the SAME market route?
    idx0 = [i for i in range(n) if labels[i] == 0]
    idx1 = [i for i in range(n) if labels[i] == 1]
    big_idx, small_idx = (idx0, idx1) if len(idx0) >= len(idx1) else (idx1, idx0)
    mode0, mode1 = _cluster_modal(streams, idx0), _cluster_modal(streams, idx1)
    cross = _agreement(mode0, mode1)
    print(f"\ncluster-modal cross-agreement (market): {cross:.4f}")
    print(f"  (whole-population cross-trace market agreement was 0.987; the smaller cluster's vote")
    print(f"   over {len(small_idx)} traces is itself noisy, so a low number here can be small-n, not two policies)")

    # The check kill (ii) actually rests on: can the minority change the majority vote? A minority of
    # m traces cannot win any modal decision while m < n/2, so if the dominant cluster's own vote
    # equals the whole-population vote, the reconstruction *is* the dominant policy's mode — a blend
    # of two policies is impossible, whatever the split.
    whole_mode = _cluster_modal(streams, list(range(n)))
    big_mode = _cluster_modal(streams, big_idx)
    vote_unchanged = _agreement(whole_mode, big_mode)
    print(f"\nmajority-vote invariance: whole-population vote vs dominant-cluster ({len(big_idx)}) vote "
          f"agree {vote_unchanged:.4f}")
    minority_share = len(small_idx) / n
    print(f"  minority cluster is {len(small_idx)}/{n} = {minority_share:.1%} of traces "
          f"(< 50% ⇒ cannot carry a modal decision)")

    # A genuine two-submission population is a BALANCED, well-separated split whose votes diverge and
    # that actually moves the reconstruction. A peeled tail of outliers (minority << 50%, vote
    # unchanged) is one town-conditioned mode.
    two_submissions = (minority_share >= 0.20 and sil >= 0.5
                       and statistics.fmean(between) > 2 * statistics.fmean(within)
                       and cross < 0.95 and vote_unchanged < 0.98)
    if two_submissions:
        verdict = "TWO SUBMISSIONS — re-vote per cluster, carry the larger (kill (ii) FIRES)"
    elif minority_share < 0.20:
        verdict = (f"ONE MODE + {len(small_idx)}-trace outlier tail — the split is a peeled tail, "
                   f"not a balanced bimodal population; the majority vote is unchanged by it, "
                   f"so kill (ii) does not fire")
    else:
        verdict = "ONE MODE — single majority vote is unbiased; kill (ii) does not fire"
    print(f"\nVERDICT: {verdict}")

    # Who are the outliers? (episode id, seat, reward, mean distance to the dominant cluster)
    if small_idx:
        print("\nminority-cluster traces (the peeled tail):")
        for i in small_idx:
            m = members[i]
            dbar = statistics.fmean(D[i, j] for j in big_idx)
            print(f"  ep {m['episode_id']} s{m['seat']}  reward=${m['reward']:>10,.0f}  "
                  f"mean dist to dominant cluster={dbar:.3f}")

    out = {
        "team": args.team, "n_traces": n, "aligned_steps": T,
        "distinct_market_fp": len({tuple(s) for s in streams}),
        "pairwise": {"min": min(off), "median": statistics.median(off),
                     "mean": statistics.fmean(off), "max": max(off), "sd": statistics.pstdev(off)},
        "two_medoid": {"sizes": sizes, "silhouette": sil,
                       "within_mean": statistics.fmean(within),
                       "between_mean": statistics.fmean(between)},
        "cluster_modal_cross_agreement": cross,
        "majority_vote_invariance": vote_unchanged,
        "minority_share": minority_share,
        "minority_traces": [{"episode_id": members[i]["episode_id"], "seat": members[i]["seat"],
                             "reward": members[i]["reward"],
                             "mean_dist_to_dominant": statistics.fmean(D[i, j] for j in big_idx)}
                            for i in small_idx],
        "two_submissions": bool(two_submissions),
        "verdict": verdict,
    }
    (DERIVED / f"s6_step1b_cluster_{args.team}.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {DERIVED / f's6_step1b_cluster_{args.team}.json'} (gitignored)")
    return 0 if not two_submissions else 2


if __name__ == "__main__":
    raise SystemExit(main())
