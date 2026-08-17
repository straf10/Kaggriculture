#!/usr/bin/env python3
"""Load the gitignored donor tapes as programmatic bench opponents (ROADMAP R26 / A2).

The three donor action streams live, self-contained, inside the `main.py` of each
`baselines/2026-08-16/tape_submissions/<episode_id>_seat0/` package — baked as a JSON
`_STREAM` literal. They are **competition data**: gitignored, never committed to this
public repo (§2.4b / R11). This module reads them locally, verifies each against the
`action_stream_sha256` recorded in the sibling `provenance.json`/`manifest.json`, and wraps
them with `analysis.tape_agent.make_tape_agent` so an S6 market-layer A/B has a
**fixed-production** opponent — the production is held constant by construction, so any
difference in realised price *is* the market layer (S6 step 2, A2).

Nothing here is importable by a submission: it reads files under `baselines/`, which never
ship. The sha256 rule is `hashlib.sha256(json.dumps(stream, sort_keys=True))`, exactly the
one `analysis/build_tape_submission.py::_sha256` wrote, so a silently corrupted or
re-encoded tape fails loudly instead of scoring as a valid opponent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from analysis.tape_agent import make_tape_agent

# episode_id -> team, the three donors S1 extracted (ROADMAP §4.3 S1 / R26).
DONORS = {
    91456307: "Valmorlee",
    90999409: "Ueddy",
    90891564: "Kaito",
}

_TAPE_ROOT = Path(__file__).resolve().parent.parent / "baselines" / "2026-08-16" / "tape_submissions"


def _sha256(stream: list) -> str:
    """Identical to analysis/build_tape_submission.py::_sha256 — the provenance hash."""
    return hashlib.sha256(json.dumps(stream, sort_keys=True).encode("utf-8")).hexdigest()


def tape_dir(episode_id: int, seat: int = 0) -> Path:
    return _TAPE_ROOT / f"{episode_id}_seat{seat}"


def available(episode_id: int, seat: int = 0) -> bool:
    """True when the gitignored donor package is present on this machine."""
    return (tape_dir(episode_id, seat) / "main.py").exists()


def load_donor_stream(episode_id: int, seat: int = 0) -> list:
    """Return the donor's action stream (list of per-step action dicts), sha256-verified.

    Execs the self-contained donor `main.py` in an isolated namespace to recover `_STREAM`
    (the file imports only `json`, so this is safe and side-effect-free), then checks the
    recovered stream's sha256 against the recorded provenance. Raises if the package is
    absent or the hash disagrees — a tape that does not match its provenance is not a valid
    opponent.
    """
    d = tape_dir(episode_id, seat)
    main_py = d / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(
            f"donor tape {episode_id} seat{seat} not found at {main_py} — it is gitignored "
            f"competition data (§2.4b); it must be present locally to run this analysis."
        )
    namespace: dict = {}
    exec(compile(main_py.read_text(encoding="utf-8"), str(main_py), "exec"), namespace)  # noqa: S102
    stream = namespace.get("_STREAM")
    if not isinstance(stream, list):
        raise ValueError(f"{main_py}: no _STREAM list found")

    recorded = json.loads((d / "provenance.json").read_text(encoding="utf-8"))["action_stream_sha256"]
    computed = _sha256(stream)
    if computed != recorded:
        raise ValueError(f"{main_py}: sha256 mismatch {computed} != recorded {recorded}")
    return stream


def make_donor_tape(episode_id: int, seat: int = 0) -> Callable:
    """A bench-agent callable(obs, configuration) that replays the donor verbatim (R26)."""
    agent = make_tape_agent(load_donor_stream(episode_id, seat))
    agent.__name__ = f"tape_{DONORS.get(episode_id, episode_id)}"
    return agent


def all_donor_tapes(seat: int = 0) -> dict[str, Callable]:
    """{team_name: tape_agent} for every donor present locally (R26 / A2 mirror bench)."""
    out = {}
    for episode_id, team in DONORS.items():
        if available(episode_id, seat):
            out[team] = make_donor_tape(episode_id, seat)
    return out


if __name__ == "__main__":
    for eid, team in DONORS.items():
        if not available(eid):
            print(f"{team:<12} {eid}  ABSENT (gitignored)")
            continue
        stream = load_donor_stream(eid)
        print(f"{team:<12} {eid}  {len(stream)} steps  sha256 OK  {_sha256(stream)[:16]}…")
