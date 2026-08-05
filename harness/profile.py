"""Per-turn timing wrapper for an agent callable. plan.md §2.4.

Budget context: actTimeout is 1s/turn + 60s overage total (MASTERPLAN §1); the submission
runtime is a modest 1.6 vCPU (competition_info.md:528), slower than a dev machine. Local
acceptance rule (conservative until real server timings are available): max_turn * 3 < 1s.
"""
import statistics
import time
from typing import Callable


def timed(agent: Callable) -> tuple:
    """Wrap `agent` so every call's wall time (seconds) is appended to the returned list."""
    times: list = []

    def wrapped(obs):
        start = time.perf_counter()
        try:
            return agent(obs)
        finally:
            times.append(time.perf_counter() - start)

    return wrapped, times


def report(times: list) -> dict:
    """max/median/p99/total, for the CLI and for the ×3 timing-margin acceptance check."""
    if not times:
        return {"max": 0.0, "median": 0.0, "p99": 0.0, "total": 0.0, "n": 0}
    sorted_times = sorted(times)
    p99_idx = min(len(sorted_times) - 1, int(round(0.99 * (len(sorted_times) - 1))))
    return {
        "max": max(times),
        "median": statistics.median(times),
        "p99": sorted_times[p99_idx],
        "total": sum(times),
        "n": len(times),
    }
