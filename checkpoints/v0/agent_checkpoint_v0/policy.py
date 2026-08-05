"""Submission policy glue."""
from dataclasses import dataclass

from .state import Snapshot, parse


@dataclass
class RuntimeContext:
    last_step: int = -1
    day: int = -1


_RUNTIME_BY_PLAYER: dict[int, RuntimeContext] = {}


def reset_or_get_runtime(snapshot: Snapshot) -> RuntimeContext:
    """Return a seat-local context and reset it at an episode boundary."""
    runtime = _RUNTIME_BY_PLAYER.get(snapshot.player)
    if runtime is None or snapshot.step == 0 or snapshot.step < runtime.last_step:
        runtime = RuntimeContext()
        _RUNTIME_BY_PLAYER[snapshot.player] = runtime
    runtime.last_step = snapshot.step
    runtime.day = snapshot.day
    return runtime


def agent(obs):
    """v0 walking skeleton: parse the observation and pass everywhere."""
    snapshot = parse(obs)
    reset_or_get_runtime(snapshot)
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in snapshot.hand_positions],
        "market": [],
    }
