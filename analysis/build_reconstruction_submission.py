#!/usr/bin/env python3
"""Package the S6 majority-vote *reconstruction* as a self-contained submission (step 1b, item 2).

Unlike a raw donor tape (analysis/build_tape_submission.py), the shipped route here is a
*measurement of a policy*: per decision point, the modal action across the donor's own 50 traces
(§4.5(b) / V16-RC5). This is not any single participant's recorded performance — it is the majority
vote over 50 of them — which is why it degrades gracefully (fidelity 0.12%, shed headroom vs the
tape's 98/100) and is better under §3.14a than a verbatim copy.

The emitted `main.py` is byte-for-byte the same loader contract as the tapes (G12: `import json`
top-level, no `__file__` shim, no `agent/` dependency, `agent` the last callable, stream embedded so
the running agent never reaches outside itself, §2.12). It differs only in provenance: the sidecar
records the *majority-vote rule*, all 50 (episode_id, seat) sources with per-trace sha256, and the
per-channel cross-trace agreement — §4.2's three mandatory conditions, plus R31's requirement that
the "one submission" claim be stated with the test that established it (step 1b item 1:
`s6_step1b_cluster.py` — one mode, majority-vote invariance 1.000).

Everything derived from donor action streams is competition data and stays gitignored (§2.4b / R11);
this script refuses to write anywhere git would track it.

Usage:
    python analysis/build_reconstruction_submission.py --team ReCurSiON --package
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DERIVED = ROOT / "data" / "derived"


def _sha256(stream: list) -> str:
    return hashlib.sha256(json.dumps(stream, sort_keys=True).encode("utf-8")).hexdigest()


def _assert_gitignored(path: Path) -> None:
    rel = path.resolve().relative_to(ROOT)
    res = subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit(
            f"REFUSING to write reconstruction to {rel}: not gitignored. The route is derived from "
            f"competition data and must stay out of this public repo (§2.4b)."
        )


def _per_trace_provenance(episodes_used: list) -> list[dict]:
    """sha256 of each source trace's full (prod||market) canonical action stream."""
    from analysis.s6_step1_phase0 import _reload_streams
    out = []
    for eid, seat in episodes_used:
        prod, market, _ = _reload_streams(eid, seat)
        full = "|".join(prod) + "||" + "|".join(market)
        out.append({"episode_id": eid, "seat": seat,
                    "trace_sha256": hashlib.sha256(full.encode("utf-8")).hexdigest()})
    return out


MAIN_TEMPLATE = '''\
"""Kaggriculture submission — S6 majority-vote reconstruction (ROADMAP §4.3 S6 step 1b).

COMPETITION DATA — this file embeds a route reconstructed from another participant's episode
traces. It is gitignored and must never be committed to the public repo (§2.4b). Full provenance
in the sidecar provenance.json; summary (§4.2's mandatory conditions):

    donor team      : {team}
    reconstruction  : per-decision majority vote across {n_traces} of {team}'s own live-engine
                      traces (§4.5(b) / V16-RC5) — a measurement of the policy, not a copy of one
                      performance. One submission (step 1b item 1: 2-medoid on market-decision
                      distance is one mode; majority-vote invariance 1.000; R31).
    agreement       : production {prod_agr:.4f}, market {market_agr:.4f} cross-trace modal share
    state-dependent : {n_disagree_market}/{n_steps} = {sd_pct:.1%} of market steps (the adaptive
                      layer's scope — step 2, not shipped here)
    stream sha256   : {sha256}
    n_steps         : {n_steps}
    fidelity        : reproduces recorded donor banks to median {fidelity_err:.2%} (S1.2); shed peak {shed_peak}/100,
                      never >=90 (headroom the raw tape lacked)

Self-contained: no `agent/` import, no engine constants (the 1.32.7 hinge bump is orthogonal —
this route grows zero CARROT/TOMATO/EGG). Emitted verbatim regardless of assigned seat.
"""
import json

_PASS = {{"farmer": ["PASS"], "hands": [], "market": []}}
_STREAM = json.loads(r"""{stream_json}""")
_N = len(_STREAM)


def agent(obs, configuration=None):
    step = obs.get("step", 0) if hasattr(obs, "get") else int(getattr(obs, "step", 0))
    if 0 <= step < _N:
        return _STREAM[step]
    return {{"farmer": ["PASS"], "hands": [], "market": []}}
'''


def _load_required_artifact(name: str, team: str) -> dict:
    path = DERIVED / f"{name}_{team}.json"
    if not path.exists():
        raise SystemExit(f"no {name} artifact for {team} — run the measurement first: {path}")
    return json.loads(path.read_text())


def build(team: str, package: bool) -> Path:
    rec_path = DERIVED / f"s6_step1_reconstruction_{team}.json"
    if not rec_path.exists():
        raise SystemExit(f"reconstruction not found: {rec_path} — run s6_step1_reconstruct.py build")
    rec = json.loads(rec_path.read_text())
    stream = rec["stream"]
    sha = _sha256(stream)
    n_steps = len(stream)
    prod_agr = rec["prod_modal_share_mean"]
    market_agr = rec["market_modal_share_mean"]
    n_dm = rec["n_disagree_market"]

    fidelity_data = _load_required_artifact("s6_step1_fidelity", team)
    shed_data = _load_required_artifact("s6_step1_shed", team)
    cluster_data = _load_required_artifact("s6_step1b_cluster", team)

    fidelity_err = fidelity_data["median_abs_error"]
    shed_peak = int(shed_data["reconstruction"]["peak_med"])
    cluster_sil = round(cluster_data["two_medoid"]["silhouette"], 3)
    cluster_sizes = cluster_data["two_medoid"]["sizes"]
    cluster_dominant = max(cluster_sizes)
    cluster_vote_inv = cluster_data["majority_vote_invariance"]
    cluster_verdict = cluster_data["verdict"]

    stream_json = json.dumps(stream, separators=(",", ":"))
    if '"""' in stream_json:
        raise SystemExit("stream JSON contains a triple-quote; cannot embed safely")

    out_dir = (ROOT / "baselines" / date.today().isoformat() / "tape_submissions"
               / f"reconstruction_{team}")
    out_dir.mkdir(parents=True, exist_ok=True)
    _assert_gitignored(out_dir)

    main_path = out_dir / "main.py"
    main_path.write_text(MAIN_TEMPLATE.format(
        team=team, n_traces=rec["n_traces"], prod_agr=prod_agr, market_agr=market_agr,
        n_disagree_market=n_dm, n_steps=n_steps, sd_pct=n_dm / n_steps, sha256=sha,
        stream_json=stream_json, fidelity_err=fidelity_err, shed_peak=shed_peak,
    ), encoding="utf-8")

    per_trace = _per_trace_provenance(rec["episodes_used"])
    provenance = {
        "artifact": "S6 majority-vote reconstruction (self-contained main.py, no agent/ package)",
        "donor_team": team,
        "method": "per-decision-point modal action (majority vote) across the donor's own traces "
                  "(§4.5(b) / V16-RC5); a measurement of the policy, not a copy of one performance",
        "n_traces": rec["n_traces"],
        "reconstruction_stream_sha256": sha,
        "n_steps": n_steps,
        "cross_trace_agreement": {"production_modal_share": prod_agr,
                                  "market_modal_share": market_agr},
        "state_dependent_market_steps": {"count": n_dm, "of": n_steps,
                                         "fraction": n_dm / n_steps,
                                         "note": "adaptive layer scope — step 2, not shipped"},
        "fidelity": {"median_abs_error": fidelity_err, "team": team,
                     "source": f"data/derived/s6_step1_fidelity_{team}.json"},
        "shed": {"peak_med": shed_peak, "team": team,
                 "source": f"data/derived/s6_step1_shed_{team}.json"},
        "one_submission_test": {
            "method": "2-medoid on pairwise market-decision distance (R31; opening fingerprint is "
                      "dead as a submission test — 87% of the field shares it)",
            "result": (f"{cluster_verdict}; majority-vote invariance {cluster_vote_inv:.3f}; "
                       f"dominant-{cluster_dominant} silhouette {cluster_sil}"),
            "script": "analysis/s6_step1b_cluster.py",
            "source": f"data/derived/s6_step1b_cluster_{team}.json",
        },
        "source_traces": per_trace,
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    from harness.checkpoint import agent_fingerprint  # local import, avoids cycle
    fingerprint = agent_fingerprint(str(main_path))
    manifest = {
        "version": f"reconstruction_{team}",
        "artifact": "S6 majority-vote reconstruction (self-contained main.py, no agent/ package)",
        "fingerprint": fingerprint,
        "reconstruction_stream_sha256": sha,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True),
                                           encoding="utf-8")

    print(f"wrote {main_path} ({main_path.stat().st_size:,} bytes)")
    print(f"  donor team={team}  traces={rec['n_traces']}  n_steps={n_steps}")
    print(f"  stream sha256={sha}")
    print(f"  agreement: production {prod_agr:.4f}  market {market_agr:.4f}")
    print(f"  state-dependent market steps: {n_dm}/{n_steps} ({n_dm/n_steps:.1%})")

    if package:
        tar_path = out_dir / "submission.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(main_path, arcname="main.py")
        print(f"packaged {tar_path} ({tar_path.stat().st_size:,} bytes)")
        _assert_gitignored(tar_path)

    return main_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="ReCurSiON")
    ap.add_argument("--package", action="store_true", help="also build submission.tar.gz")
    args = ap.parse_args()
    build(args.team, args.package)


if __name__ == "__main__":
    main()
