"""Per-turn timing. plan.md §2.4.

Budget context: actTimeout is 1s/turn + 60s overage total (MASTERPLAN §1); the submission
runtime is a modest 1.6 vCPU (competition_info.md:528), slower than a dev machine. Local
acceptance rule (conservative until real server timings are available): max_turn * 3 < 1s.

Inside `play()`, per-turn timing comes from env.logs (harness.play._turn_durations) — that is
what the framework itself measures, including first-turn import/exec cost for lazily-loaded
path agents, which is the actual cost the Kaggle server charges against actTimeout on turn 1.
`timed()` below is for ad-hoc timing of a bare callable outside a full play() episode.
"""
import functools
import statistics
import time
from typing import Callable


def timed(agent: Callable) -> tuple:
    """Wrap `agent` so every call's wall time (seconds) is appended to the returned list."""
    times: list = []

    @functools.wraps(agent)
    def wrapped(obs):
        start = time.perf_counter()
        try:
            return agent(obs)
        finally:
            times.append(time.perf_counter() - start)

    return wrapped, times


def report(times: list, *, act_timeout: float = 1.0) -> dict:
    """max/median/p99/total/turn1/overage_used, for the CLI and the ×3 timing-margin check.

    turn1 is the first call's duration (import/exec cost lands here for path agents).
    overage_used is the cumulative overage the engine would charge against the 60s
    remainingOverageTime budget (duration - act_timeout, summed over turns where positive).
    """
    if not times:
        return {"max": 0.0, "median": 0.0, "p99": 0.0, "total": 0.0, "n": 0,
                 "turn1": 0.0, "overage_used": 0.0}
    sorted_times = sorted(times)
    p99_idx = min(len(sorted_times) - 1, int(round(0.99 * (len(sorted_times) - 1))))
    return {
        "max": max(times),
        "median": statistics.median(times),
        "p99": sorted_times[p99_idx],
        "total": sum(times),
        "n": len(times),
        "turn1": times[0],
        "overage_used": sum(max(0.0, t - act_timeout) for t in times),
    }
