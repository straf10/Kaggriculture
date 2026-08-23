#!/usr/bin/env python3
"""S8 Leg 1 — disagreement onset profiling.

Question: is the 83-94% top-4 disagreement 600 independent adaptive decisions,
or one early divergence that cascades into permanent desync? If the latter,
every step-aligned instrument in this repo (including K2) measured the shift,
not the policy.

Measures per player, across all trace pairs within a submission:
  - first_disagree_step
  - post_onset_disagree_frac
  - n_resyncs (>=5 consecutive agreeing steps after a disagreement)
  - longest_agreement_run_post_onset

Runs on top-4 (2026-08-21 archive) + ReCurSiON (2026-08-16 archive) as calibration.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s6_step1_phase0 import _seat_streams

DERIVED = ROOT / "data" / "derived"
RESYNC_WINDOW = 5


def load_inventory(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r["episode_id"], r["seat"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def filter_live(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["version"] == "1.32.7" and r["clean"] and r["interval"] == 24]


def cluster_by_submission(members: list[dict]) -> dict[str, list[dict]]:
    """Cluster by production opening fingerprint to separate re-uploads."""
    by_fp = defaultdict(list)
    for m in members:
        by_fp[m["fp_prod_open"]].append(m)
    return dict(by_fp)


def load_prod_stream(archive: Path, episode_id: int, seat: int) -> list[str]:
    path = archive / f"{episode_id}.json"
    d = json.loads(path.read_text())
    prod, _, _ = _seat_streams(d["steps"], seat)
    return prod


def onset_metrics(stream_a: list[str], stream_b: list[str]) -> dict:
    T = min(len(stream_a), len(stream_b))
    first_disagree = None
    for t in range(T):
        if stream_a[t] != stream_b[t]:
            first_disagree = t
            break

    if first_disagree is None:
        return {
            "first_disagree_step": None,
            "post_onset_disagree_frac": 0.0,
            "n_resyncs": 0,
            "longest_agreement_run_post_onset": T,
        }

    post = T - first_disagree
    disagree_count = 0
    agree_run = 0
    longest_run = 0
    n_resyncs = 0
    in_resync = False

    for t in range(first_disagree, T):
        if stream_a[t] != stream_b[t]:
            disagree_count += 1
            if in_resync and agree_run >= RESYNC_WINDOW:
                n_resyncs += 1
            in_resync = False
            agree_run = 0
        else:
            agree_run += 1
            longest_run = max(longest_run, agree_run)
            if agree_run == 1:
                in_resync = True

    if in_resync and agree_run >= RESYNC_WINDOW:
        n_resyncs += 1

    return {
        "first_disagree_step": first_disagree,
        "post_onset_disagree_frac": disagree_count / post if post > 0 else 0.0,
        "n_resyncs": n_resyncs,
        "longest_agreement_run_post_onset": longest_run,
    }


def analyse_group(archive: Path, members: list[dict], label: str) -> dict:
    streams = {}
    for m in members:
        key = (m["episode_id"], m["seat"])
        streams[key] = load_prod_stream(archive, m["episode_id"], m["seat"])

    keys = list(streams.keys())
    pair_results = []
    for (k1, k2) in combinations(keys, 2):
        metrics = onset_metrics(streams[k1], streams[k2])
        pair_results.append(metrics)

    if not pair_results:
        return {"label": label, "n_traces": len(keys), "n_pairs": 0}

    n = len(pair_results)
    has_disagree = [p for p in pair_results if p["first_disagree_step"] is not None]
    no_disagree = n - len(has_disagree)

    def median(xs):
        xs = sorted(xs)
        mid = len(xs) // 2
        return xs[mid] if len(xs) % 2 == 1 else (xs[mid - 1] + xs[mid]) / 2

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    result = {
        "label": label,
        "n_traces": len(keys),
        "n_pairs": n,
        "n_identical_pairs": no_disagree,
    }

    if has_disagree:
        fds = [p["first_disagree_step"] for p in has_disagree]
        podf = [p["post_onset_disagree_frac"] for p in has_disagree]
        nrs = [p["n_resyncs"] for p in has_disagree]
        lars = [p["longest_agreement_run_post_onset"] for p in has_disagree]

        result.update({
            "first_disagree_step_median": median(fds),
            "first_disagree_step_min": min(fds),
            "first_disagree_step_max": max(fds),
            "post_onset_disagree_frac_median": round(median(podf), 4),
            "post_onset_disagree_frac_mean": round(mean(podf), 4),
            "n_resyncs_median": median(nrs),
            "n_resyncs_mean": round(mean(nrs), 2),
            "n_resyncs_max": max(nrs),
            "longest_agreement_run_post_onset_median": median(lars),
            "longest_agreement_run_post_onset_max": max(lars),
        })
    return result


def main():
    TOP4 = ["Crop Dusta", "Arman Tuganbaev", "Ryo Hasegawa", "tetsuya"]
    ARCHIVE_21 = ROOT / "data" / "archive" / "raw" / "2026-08-21"
    ARCHIVE_16 = ROOT / "data" / "archive" / "raw" / "2026-08-16"

    inv_21 = filter_live(dedupe(load_inventory(DERIVED / "s6_step1_inventory_2026-08-21.jsonl")))
    inv_16 = filter_live(dedupe(load_inventory(DERIVED / "s6_step1_inventory.jsonl")))

    print(f"2026-08-21: {len(inv_21)} seat-rows (deduped+filtered)")
    print(f"2026-08-16: {len(inv_16)} seat-rows (deduped+filtered)")
    print()

    results = []

    for team in TOP4:
        members = [r for r in inv_21 if r["team"] == team]
        clusters = cluster_by_submission(members)
        if len(clusters) > 1:
            largest_fp = max(clusters, key=lambda fp: len(clusters[fp]))
            cluster = clusters[largest_fp]
            print(f"{team}: {len(members)} traces, {len(clusters)} submissions, "
                  f"using largest ({len(cluster)} traces)")
        else:
            cluster = members
            print(f"{team}: {len(cluster)} traces, 1 submission")
        r = analyse_group(ARCHIVE_21, cluster, team)
        results.append(r)
        _print_result(r)
        print()

    rc_members = [r for r in inv_16 if r["team"] == "ReCurSiON"]
    rc_clusters = cluster_by_submission(rc_members)
    if len(rc_clusters) > 1:
        largest_fp = max(rc_clusters, key=lambda fp: len(rc_clusters[fp]))
        rc_cluster = rc_clusters[largest_fp]
        print(f"ReCurSiON: {len(rc_members)} traces, {len(rc_clusters)} submissions, "
              f"using largest ({len(rc_cluster)} traces)")
    else:
        rc_cluster = rc_members
        print(f"ReCurSiON: {len(rc_cluster)} traces, 1 submission")
    r = analyse_group(ARCHIVE_16, rc_cluster, "ReCurSiON")
    results.append(r)
    _print_result(r)

    out_path = DERIVED / "s8_leg1_onset.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")


def _print_result(r: dict):
    print(f"  {r['label']}: {r['n_traces']} traces, {r['n_pairs']} pairs, "
          f"{r.get('n_identical_pairs', 0)} identical")
    if "first_disagree_step_median" in r:
        print(f"  first_disagree_step: median={r['first_disagree_step_median']}, "
              f"min={r['first_disagree_step_min']}, max={r['first_disagree_step_max']}")
        print(f"  post_onset_disagree_frac: median={r['post_onset_disagree_frac_median']}, "
              f"mean={r['post_onset_disagree_frac_mean']}")
        print(f"  n_resyncs: median={r['n_resyncs_median']}, "
              f"mean={r['n_resyncs_mean']}, max={r['n_resyncs_max']}")
        print(f"  longest_agreement_run_post_onset: median={r['longest_agreement_run_post_onset_median']}, "
              f"max={r['longest_agreement_run_post_onset_max']}")


if __name__ == "__main__":
    main()
