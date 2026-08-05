"""compare(): paired-seed A-vs-B comparison. plan.md §2.4, methodology from MASTERPLAN §6
(viz cells 46-50) — same seeds for both agents, |mean(diff)| > 2*SE(diff) as the go/no-go bar.
"""
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from harness.play import play


@dataclass
class CompareResult:
    per_seed: list = field(default_factory=list)  # [{seed, seat_layout, bank_a, bank_b, diff, winner}]
    mean_diff: float = 0.0
    se_diff: float = 0.0
    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    significant: bool = False  # |mean_diff| > 2*se_diff


def compare(agent_a, agent_b, seeds: Sequence[int], *,
            both_seats: bool = True,
            steps: int = 720,
            run_dir: Optional[Path] = None) -> CompareResult:
    """Paired-seed protocol: A and B play the same seeds. With both_seats=True (default),
    each seed is played twice — A@seat0/B@seat1 and B@seat0/A@seat1 — since the weed-RNG
    seat coupling (MASTERPLAN §2#6) means seat 0/1 are not interchangeable. A seed's diff is
    the mean of (bank_a - bank_b) across both orientations."""
    per_seed = []
    for seed in seeds:
        orientations = []  # list of (bank_a, bank_b)

        r_a0 = play(agent_a, agent_b, seed, steps=steps, run_dir=run_dir)
        orientations.append((r_a0.rewards[0], r_a0.rewards[1]))

        if both_seats:
            r_b0 = play(agent_b, agent_a, seed, steps=steps, run_dir=run_dir)
            orientations.append((r_b0.rewards[1], r_b0.rewards[0]))  # (bank_a, bank_b)

        bank_a = statistics.mean(b for b, _ in orientations)
        bank_b = statistics.mean(b for _, b in orientations)
        diff = bank_a - bank_b
        winner = "a" if diff > 0 else ("b" if diff < 0 else "tie")
        per_seed.append({
            "seed": seed,
            "seat_layout": ["A@0/B@1", "B@0/A@1"][:len(orientations)],
            "bank_a": bank_a,
            "bank_b": bank_b,
            "diff": diff,
            "winner": winner,
        })

    diffs = [row["diff"] for row in per_seed]
    n = len(diffs)
    mean_diff = statistics.mean(diffs) if n else 0.0
    se_diff = (statistics.stdev(diffs) / (n ** 0.5)) if n > 1 else 0.0
    significant = abs(mean_diff) > 2 * se_diff if n > 1 else False

    wins_a = sum(1 for row in per_seed if row["winner"] == "a")
    wins_b = sum(1 for row in per_seed if row["winner"] == "b")
    ties = sum(1 for row in per_seed if row["winner"] == "tie")

    return CompareResult(
        per_seed=per_seed,
        mean_diff=mean_diff,
        se_diff=se_diff,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        significant=significant,
    )
