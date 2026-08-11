"""Thin open-loop "tape" agent (ROADMAP.md S2) — replays a recorded action stream.

`make_tape_agent(action_stream)` returns a plain callable(obs, configuration) -> action,
the same shape as any other harness agent (see `harness/bench_agents/meta_route.py`).
It does not import or touch `agent/` at all — it has no policy, it only echoes back
`action_stream[obs["step"]]`, which is the format donor streams are stored in
(`{"farmer": [...], "hands": [...], "market": [...]}`, exactly `replay["steps"][t][seat]
["action"]`). Read-only with respect to `agent/config.CONFIG` by construction: nothing
here imports `agent`.

Used programmatically via `harness.play.play(make_tape_agent(stream_a), ..., seed=...)` —
not file-path-loaded, since each tape agent is parameterised by a specific donor's
action stream loaded at call time, not a fixed module-level constant.
"""
from __future__ import annotations

from typing import Callable

_PASS_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}


def make_tape_agent(action_stream: list) -> Callable:
    """action_stream[t] must be the exact action dict for engine step t (0-indexed,
    matching `obs["step"]`). Steps beyond the recorded stream's length (should not
    happen for a full 720-step donor) fall back to PASS rather than erroring, so a
    short/truncated stream degrades visibly (as no-ops) instead of crashing the episode.
    """
    n = len(action_stream)

    def _tape_agent(obs, configuration=None):
        step = obs["step"]
        if step < n:
            return action_stream[step]
        return dict(_PASS_ACTION)

    _tape_agent.__name__ = f"tape_agent_{n}steps"
    return _tape_agent
