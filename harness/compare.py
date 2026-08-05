"""compare(): paired-seed A-vs-B comparison. plan.md §2.4, methodology from MASTERPLAN §6
(viz cells 46-50) — same seeds for both agents.

Go/no-go needs directional confidence and a practical margin:
- `significant`: the paired-seed mean diff clears a t-distribution confidence bound (not the
  z-approximation 2*SE, which is anti-conservative below ~30 seeds; None if se_diff==0, since a
  perfectly constant diff is not "infinitely significant" — it usually means a deterministic,
  seed-independent difference, not a real effect).
- `practical`: the mean diff also clears an absolute-$ floor, so a statistically "significant"
  but trivial $1 diff doesn't read as a real result.
- `verdict`: IMPROVED/NON_INFERIOR/REGRESSED/INCONCLUSIVE/INCOMPLETE. A negative practical
  result can never be approved by taking `abs(mean_diff)`.
"""
import json
import statistics
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from harness.checkpoint import agent_fingerprint
from harness.play import play

# Two-sided 95% t-critical value by degrees of freedom (df = n-1). Exact through df=30,
# then a handful of anchor points with linear interpolation, 1.96 (normal) beyond df=120 —
# avoids a hard scipy dependency for what is a small, well-known table (review.md M5).
_T_TABLE = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990, 100: 1.984, 120: 1.980,
}


def _t_crit(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df in _T_TABLE:
        return _T_TABLE[df]
    keys = sorted(_T_TABLE)
    if df > keys[-1]:
        return 1.96
    lo = max(k for k in keys if k < df)
    hi = min(k for k in keys if k > df)
    frac = (df - lo) / (hi - lo)
    return _T_TABLE[lo] + frac * (_T_TABLE[hi] - _T_TABLE[lo])


@dataclass
class CompareResult:
    per_seed: list = field(default_factory=list)  # paired rows with raw orientation results
    errors: list = field(default_factory=list)  # [{seed, error}] — seeds that raised, skipped
    mean_diff: float = 0.0
    se_diff: float = 0.0
    n_effective: int = 0
    t_crit: float = 0.0
    ci95: tuple = (0.0, 0.0)
    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    episode_wins_a: int = 0
    episode_wins_b: int = 0
    episode_ties: int = 0
    median_bank_a: float = 0.0
    significant: Optional[bool] = False  # None when se_diff==0 (undefined, not "infinitely true")
    practical: Optional[bool] = False
    verdict: str = "INCONCLUSIVE"
    incomplete: bool = False  # True if any seed errored or was otherwise skipped
    code_fingerprints: tuple = ("", "")


def compare(agent_a, agent_b, seeds: Sequence[int], *,
            both_seats: bool = True,
            steps: Optional[int] = None,
            run_dir: Optional[Path] = None,
            record: bool = False,
            strict: bool = True,
            min_effect: Optional[float] = None,
            non_inferiority_margin: Optional[float] = None,
            resume: bool = False,
            require_distinct_versions: bool = True) -> CompareResult:
    """Paired-seed protocol: A and B play the same seeds. With both_seats=True (default),
    each seed is played twice — A@seat0/B@seat1 and B@seat0/A@seat1 — since the weed-RNG
    seat coupling (MASTERPLAN §2#6) means seat 0/1 are not interchangeable. A seed's diff is
    the mean of (bank_a - bank_b) across both orientations.

    record=False by default (each replay is several MB; a 24-seed both_seats run at
    record=True was measured at 105MB — review.md M3). Pass run_dir to also get incremental
    append-only `results.jsonl` there; resume=True skips seeds already present in it, so a
    run that dies partway (an errored seed, a crashed process) can continue instead of
    restarting (review.md M6). strict is forwarded to `play()`; a per-seed exception (from a
    strict violation or anything else) is caught, recorded in `errors`, and that seed is
    skipped rather than losing every seed played before it.

    min_effect is the absolute-$ floor for `practical` (default max($200, 2% of mean bank_b)).
    non_inferiority_margin defaults to the same value. Directional verdicts are:
    IMPROVED, NON_INFERIOR, REGRESSED, INCONCLUSIVE, or INCOMPLETE.
    """
    seeds = list(seeds)
    code_fingerprints = (agent_fingerprint(agent_a), agent_fingerprint(agent_b))
    if require_distinct_versions and code_fingerprints[0] == code_fingerprints[1]:
        raise ValueError(
            "compare(): A and B have identical code fingerprints; use immutable checkpoints "
            "with unique package namespaces and compare genuinely different versions"
        )
    if len(seeds) < 24:
        warnings.warn(
            f"compare(): {len(seeds)} seeds — MASTERPLAN §6 asks for 24-48 for a final go/no-go "
            "decision; fewer is fine only for catching large, obvious regressions early.",
            stacklevel=2,
        )

    run_dir_path = Path(run_dir) if run_dir is not None else None
    jsonl_path = run_dir_path / "results.jsonl" if run_dir_path is not None else None

    done = {}
    if resume and jsonl_path is not None and jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            done[row["seed"]] = row
    elif jsonl_path is not None:
        run_dir_path.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text("", encoding="utf-8")

    def _persist(row: dict) -> None:
        if jsonl_path is not None:
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    per_seed = []
    errors = []
    for seed in seeds:
        cached = done.get(seed)
        if cached is not None:
            if "error" in cached:
                errors.append(cached)
            else:
                per_seed.append(cached)
            continue

        try:
            orientations = []
            r_a0 = play(agent_a, agent_b, seed, steps=steps, run_dir=run_dir, record=record,
                        strict=strict, metrics=False)
            orientations.append({
                "layout": "A@0/B@1",
                "bank_a": r_a0.rewards[0],
                "bank_b": r_a0.rewards[1],
            })

            if both_seats:
                r_b0 = play(agent_b, agent_a, seed, steps=steps, run_dir=run_dir, record=record,
                            strict=strict, metrics=False)
                orientations.append({
                    "layout": "B@0/A@1",
                    "bank_a": r_b0.rewards[1],
                    "bank_b": r_b0.rewards[0],
                })

            for orientation in orientations:
                orientation["diff"] = orientation["bank_a"] - orientation["bank_b"]
                orientation["winner"] = (
                    "a" if orientation["diff"] > 0 else ("b" if orientation["diff"] < 0 else "tie")
                )

            bank_a = statistics.mean(row["bank_a"] for row in orientations)
            bank_b = statistics.mean(row["bank_b"] for row in orientations)
            diff = bank_a - bank_b
            winner = "a" if diff > 0 else ("b" if diff < 0 else "tie")
            row = {
                "seed": seed,
                "seat_layout": [orientation["layout"] for orientation in orientations],
                "orientations": orientations,
                "bank_a": bank_a,
                "bank_b": bank_b,
                "diff": diff,
                "winner": winner,
            }
            per_seed.append(row)
            _persist(row)
        except Exception as e:
            err_row = {"seed": seed, "error": repr(e)}
            errors.append(err_row)
            _persist(err_row)

    diffs = [row["diff"] for row in per_seed]
    n = len(diffs)
    mean_diff = statistics.mean(diffs) if n else 0.0
    stdev = statistics.stdev(diffs) if n > 1 else 0.0
    se_diff = (stdev / (n ** 0.5)) if n > 1 else 0.0
    t_crit = _t_crit(n - 1) if n > 1 else float("nan")

    if n <= 1 or se_diff == 0:
        significant = None
    else:
        significant = abs(mean_diff) > t_crit * se_diff

    if min_effect is None:
        bank_bs = [row["bank_b"] for row in per_seed]
        effective_min_effect = max(200.0, 0.02 * statistics.mean(bank_bs)) if bank_bs else 200.0
    else:
        effective_min_effect = min_effect
    practical = (abs(mean_diff) > effective_min_effect) if n else None
    effective_non_inferiority_margin = (
        effective_min_effect if non_inferiority_margin is None else non_inferiority_margin
    )

    ci95 = (mean_diff - t_crit * se_diff, mean_diff + t_crit * se_diff) if n > 1 else (mean_diff, mean_diff)

    incomplete = bool(errors)
    if incomplete:
        verdict = "INCOMPLETE"
    elif not n:
        verdict = "INCONCLUSIVE"
    elif mean_diff < -effective_non_inferiority_margin and (
        se_diff == 0 or ci95[1] < -effective_non_inferiority_margin
    ):
        verdict = "REGRESSED"
    elif (
        mean_diff > effective_min_effect
        and se_diff > 0
        and ci95[0] > 0
    ):
        verdict = "IMPROVED"
    elif ci95[0] >= -effective_non_inferiority_margin:
        verdict = "NON_INFERIOR"
    else:
        verdict = "INCONCLUSIVE"

    wins_a = sum(1 for row in per_seed if row["winner"] == "a")
    wins_b = sum(1 for row in per_seed if row["winner"] == "b")
    ties = sum(1 for row in per_seed if row["winner"] == "tie")
    raw_orientations = [
        orientation
        for row in per_seed
        for orientation in row.get("orientations", [])
    ]
    episode_wins_a = sum(1 for row in raw_orientations if row["winner"] == "a")
    episode_wins_b = sum(1 for row in raw_orientations if row["winner"] == "b")
    episode_ties = sum(1 for row in raw_orientations if row["winner"] == "tie")
    median_bank_a = (
        statistics.median(row["bank_a"] for row in raw_orientations)
        if raw_orientations
        else 0.0
    )

    return CompareResult(
        per_seed=per_seed,
        errors=errors,
        mean_diff=mean_diff,
        se_diff=se_diff,
        n_effective=n,
        t_crit=t_crit,
        ci95=ci95,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        episode_wins_a=episode_wins_a,
        episode_wins_b=episode_wins_b,
        episode_ties=episode_ties,
        median_bank_a=median_bank_a,
        significant=significant,
        practical=practical,
        verdict=verdict,
        incomplete=incomplete,
        code_fingerprints=code_fingerprints,
    )
