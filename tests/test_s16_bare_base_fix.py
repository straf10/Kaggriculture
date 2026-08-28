"""S16 task 1 fix (docs/plans/s16_slot_comparison.md correction, 2026-08-28) — the base
arm in `analysis/s10_replay_bench.py`'s `h2_calibration`/`recovery_calibration` must be the
BARE reconstruction stream, not the episode's own recorded reward/stream.

Pre-fix, `_recovery_one` wrapped `TapeOverlay` around `streams[seat]` — this episode's OWN
recorded action stream. For every `55675634` episode that stream already IS the shipped
overlay's own output (it was recorded playing WITH tile recovery + market pull-forward), so
wrapping it in a fresh `TapeOverlay` finds nothing left to recover: verified independently
against `data/derived/s10_bench_recovery_calibration.json` before this fix — all 246/246
`55675634` confirm-set episodes fired zero times and read `d_bank == 0`. The recovery arm was
silently being compared to itself.

`test_recovery_fires_against_the_bare_stream_not_its_own_recorded_stream` pins the fixed
behaviour on one concrete `55675634` episode (96207048) and is confirmed to redden under the
pre-fix function body: a standalone reimplementation of the old `_recovery_one` (wrapping
`streams[seat]` instead of the bare stream) was run by hand against this same episode and
read `n_fires=0, d_bank=0.0` — see this pass's summary. Reverting the fix reproduces that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s8_replay_io import replay_paths  # noqa: E402

RECONSTRUCTION = ROOT / "data" / "derived" / "s6_step1_reconstruction_ReCurSiON.json"

pytestmark = pytest.mark.skipif(
    not RECONSTRUCTION.exists(),
    reason="reconstruction stream not on disk (gitignored competition data)",
)

# 55675634 — fires 27x and d_bank=-19975 against the bare stream; 0/0 pre-fix (see docstring).
RECOVERY_EPISODE = 96207048
# 55586926 — ships NO overlay at all, so it IS the bare reconstruction.
BARE_SUBMISSION_EPISODE = 94042607


def _job(sub, eid):
    for p in replay_paths(sub):
        if int(p.name.split("-")[1]) == eid:
            return (sub, eid, str(p))
    pytest.skip(f"episode {eid} not on disk for {sub}")


def test_recovery_fires_against_the_bare_stream_not_its_own_recorded_stream():
    from analysis.s10_replay_bench import _recovery_one
    row = _recovery_one(_job("55675634", RECOVERY_EPISODE))
    assert row is not None
    assert row["n_recovery_fires"] > 0, (
        "recovery must fire when wrapped around the BARE stream — 0 here means the overlay "
        "input regressed back to this episode's own (already-recovered) recorded stream"
    )
    assert row["d_bank"] != 0


def test_bare_base_equals_recorded_reward_on_the_unoverlaid_submission():
    """S16 task 1's explicit correctness check: 55586926 ships no overlay, so replaying the
    bare stream against its recorded opponent tape must reproduce its own recorded reward."""
    from analysis.s10_replay_bench import _h2_one
    row = _h2_one(_job("55586926", BARE_SUBMISSION_EPISODE))
    assert row is not None
    assert row["bare_equals_recorded"] is True
    assert row["base_us"] == row["recorded_us"]
    assert row["base_opp"] == row["recorded_opp"]
