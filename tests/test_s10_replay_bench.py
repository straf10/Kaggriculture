"""S10 P1 — pin the replay bench's stream extraction and McNemar helper.

The full α-control and H2 runs need real replays and process pools; here we cover
just the pieces that can regress silently without live data.  The two live runs
are deferred to the CLI (P1.2 and P1.4 acceptance in the plan).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.s10_replay_bench import _extract_streams, _mcnemar_binomial_p  # noqa: E402


def test_extract_streams_matches_alignment_convention():
    """`stream[k]` must equal `steps[k+1][seat]["action"]` (verified in s8_replay_io)."""
    # Three-step fake replay: steps[1] and steps[2] are the two decisions.
    steps = [
        [{"action": None}, {"action": None}],
        [{"action": {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 3]]}},
         {"action": {"farmer": ["MOVE_N"], "hands": [], "market": []}}],
        [{"action": {"farmer": ["HARVEST"], "hands": [], "market": []}},
         {"action": {"farmer": ["PASS"], "hands": [], "market": []}}],
    ]
    streams = _extract_streams(steps)
    assert streams[0][0]["market"] == [["SELL", "MELON", 3]]
    assert streams[1][0]["farmer"] == ["MOVE_N"]
    assert streams[0][1]["farmer"] == ["HARVEST"]


def test_extract_streams_defaults_to_pass_on_missing_action():
    """A missing `action` key must serialize as PASS, not raise or vanish."""
    steps = [
        [{"action": None}, {"action": None}],
        [{}, {"action": None}],
    ]
    streams = _extract_streams(steps)
    assert streams[0][0] == {"farmer": ["PASS"], "hands": [], "market": []}
    assert streams[1][0] == {"farmer": ["PASS"], "hands": [], "market": []}


def test_mcnemar_p_matches_h2_calibration_result():
    """The frozen H2 result was c=23, b=0 with p ≈ 2,4·10⁻⁷ (s9-phase2-gate)."""
    p = _mcnemar_binomial_p(b=0, c=23)
    assert 2.0e-7 < p < 3.0e-7, p


def test_mcnemar_p_no_flips_is_one():
    assert _mcnemar_binomial_p(0, 0) == 1.0


def test_mcnemar_p_symmetric_in_b_and_c():
    assert _mcnemar_binomial_p(3, 5) == _mcnemar_binomial_p(5, 3)


def test_mcnemar_p_death_signal_when_b_greater_than_c():
    """A regressive candidate (b > c) still yields a small p — the caller reads the
    direction (b > c) separately, but the p value itself is symmetric."""
    p_regression = _mcnemar_binomial_p(b=8, c=0)  # every flip goes the wrong way
    assert p_regression < 0.01
