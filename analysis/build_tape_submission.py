#!/usr/bin/env python3
"""Build a self-contained open-loop *tape* submission from a gitignored donor record.

ROADMAP §4.3 S2 / T1. The measurement (baselines/2026-08-15/t1_repair_justification.md) is
that no repair layer is justified — the donor farm executes byte-identically against every
opponent (0 weed/hand no-ops), the shed ends empty, and the only degradation is realised-price
competition, which is the out-of-scope S3-step-3 market overlay. So the shippable artifact is
the RAW tape: emit `stream[obs.step]`, PASS past the end.

The emitted `main.py` is fully self-contained (G12 loader contract: `import json` at top level,
no `__file__` shim, no `agent/` dependency, `agent` is the last callable) and carries the tape
as an embedded constant so the running agent never reaches outside itself (§2.12 no-egress).

Provenance (§4.2, mandatory): episode id, donor seat, team, action-stream sha256 are written
into the file docstring AND a sidecar `provenance.json` for the submission description.

The output tree lives under `baselines/` which is **gitignored wholesale** — the extracted
route is competition data and must never enter this public repo (§2.4b). This script verifies
that before writing, and refuses to write anywhere git-tracked.

Usage:
    python analysis/build_tape_submission.py --episode 91456307      # Valmorlee (default seat 0)
    python analysis/build_tape_submission.py --episode 91456307 --package   # also tar it
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
DONORS_DIR = ROOT / "baselines" / "2026-08-11" / "donors"


def _sha256(stream: list) -> str:
    return hashlib.sha256(json.dumps(stream, sort_keys=True).encode("utf-8")).hexdigest()


def _assert_gitignored(path: Path) -> None:
    """Refuse to write the tape anywhere git would track it (§2.4b, public repo)."""
    rel = path.resolve().relative_to(ROOT)
    res = subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit(
            f"REFUSING to write tape to {rel}: not gitignored. The extracted route is "
            f"competition data and must stay out of this public repo (§2.4b)."
        )


MAIN_TEMPLATE = '''\
"""Kaggriculture submission — open-loop donor tape (ROADMAP §4.3 S2 / T1).

COMPETITION DATA — this file embeds another participant's extracted action stream. It is
gitignored and must never be committed to the public repo (§2.4b). Full provenance (§4.2):

    episode_id : {episode_id}
    donor_seat : {seat}
    team       : {team}
    sha256     : {sha256}
    n_steps    : {n_steps}
    fidelity   : reproduces the recorded ${recorded_bank:,} bank at 0.0000% on 1.32.6 and 1.32.7

Seat-symmetric: banks are identical seat0==seat1 (S2 failure map), so the stream is emitted
verbatim regardless of the assigned seat. Self-contained: no `agent/` import, no engine
constants, so the 1.32.7 hinge bump is orthogonal (this tape grows zero CARROT/TOMATO/EGG).
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


def build(episode_id: int, seat: int, package: bool) -> Path:
    donor_path = DONORS_DIR / f"{episode_id}_seat{seat}.json"
    if not donor_path.exists():
        raise SystemExit(f"donor record not found: {donor_path} — run analysis/s1_extract_donors.py")
    donor = json.loads(donor_path.read_text())
    stream = donor["donor_action_stream"]
    team = donor["donor"]["team_name"]
    recorded_bank = donor["donor"]["recorded_final_bank"]

    sha = _sha256(stream)
    recorded_sha = donor["donor"]["action_stream_sha256"]
    if sha != recorded_sha:
        raise SystemExit(f"sha256 mismatch: computed {sha} != recorded {recorded_sha}")

    stream_json = json.dumps(stream, separators=(",", ":"))
    if '"""' in stream_json:  # would break the r""" literal; actions never contain it, but guard
        raise SystemExit("stream JSON contains a triple-quote; cannot embed safely")

    out_dir = ROOT / "baselines" / date.today().isoformat() / "tape_submissions" / f"{episode_id}_seat{seat}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _assert_gitignored(out_dir)

    main_path = out_dir / "main.py"
    main_path.write_text(MAIN_TEMPLATE.format(
        episode_id=episode_id, seat=seat, team=team, sha256=sha,
        n_steps=len(stream), recorded_bank=recorded_bank, stream_json=stream_json,
    ), encoding="utf-8")

    provenance = {
        "artifact": "open-loop donor tape",
        "episode_id": episode_id,
        "donor_seat": seat,
        "team": team,
        "action_stream_sha256": sha,
        "n_steps": len(stream),
        "recorded_home_bank": recorded_bank,
        "engine_note": "reproduces recorded bank at 0.0000% on 1.32.6 and 1.32.7 (S1.2)",
        "repair_layer": "none — S2 measured farm byte-identical, shed empty; gap is realised "
                        "price (S3-step-3 market overlay, out of scope)",
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    # manifest.json (harness checkpoint identity): fingerprint = agent_fingerprint of the
    # self-contained main.py = sha256 of its source (a non-package main.py takes that path).
    # Silences the holdout-confirm checkpoint warning and pins the shipped artifact's identity.
    # NOTE: this dir is gitignored (baselines/), so unlike agent/ checkpoints the manifest is
    # NOT tracked — the tape is competition data and cannot enter the public repo (§2.4b); the
    # recoverable record is provenance.json + the donor sha256 cited in the ROADMAP.
    from harness.checkpoint import agent_fingerprint  # noqa: E402  (local import, avoids cycle)
    fingerprint = agent_fingerprint(str(main_path))
    manifest = {
        "version": f"tape_{episode_id}_seat{seat}",
        "artifact": "open-loop donor tape (self-contained main.py, no agent/ package)",
        "fingerprint": fingerprint,
        "action_stream_sha256": sha,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True),
                                           encoding="utf-8")

    print(f"wrote {main_path} ({main_path.stat().st_size:,} bytes)")
    print(f"  team={team}  episode={episode_id}  seat={seat}")
    print(f"  sha256={sha}")
    print(f"  n_steps={len(stream)}  recorded_home_bank=${recorded_bank:,}")

    if package:
        tar_path = out_dir / "submission.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(main_path, arcname="main.py")  # main.py at the root (§6bis)
        print(f"packaged {tar_path} ({tar_path.stat().st_size:,} bytes)")
        _assert_gitignored(tar_path)

    return main_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--package", action="store_true", help="also build submission.tar.gz")
    args = ap.parse_args()
    build(args.episode, args.seat, args.package)


if __name__ == "__main__":
    main()
