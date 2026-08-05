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
import concurrent.futures
import json
import pickle
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
MIN_N_FOR_NON_INFERIOR = 12  # review.md M3

# plan.md §1.5.3 / review.md §5 check #5: a $-verdict alone can hide a regression that just
# happens to net positive (e.g. more aggressive selling offsetting worse water discipline).
# stage tags which decision a report may be used for: dev-screen (tuning) reports must never
# be read as a GO by themselves — only holdout-confirm, checked exactly once, can be.
VALID_STAGES = ("dev-screen", "holdout-confirm")

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


def _play_orientation(agent_first, agent_second, seed, steps, run_dir, record, strict, metrics):
    """Module-level (picklable) unit of work for the ProcessPoolExecutor path (plan.md
    §1.5.1): exactly one `play()` call, returning the raw (bank_first, bank_second) rewards
    plus the per-seat metrics dict a single orientation needs. Kept at module scope — a
    nested closure isn't picklable and would silently break the Windows spawn start method."""
    result = play(agent_first, agent_second, seed, steps=steps, run_dir=run_dir, record=record,
                  strict=strict, metrics=metrics)
    return result.rewards, result.metrics


def _is_picklable(obj) -> bool:
    try:
        pickle.dumps(obj)
        return True
    except Exception:
        return False


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
    stage: Optional[str] = None  # "dev-screen" | "holdout-confirm" | None (plan.md §1.5.3)
    metrics_checked: bool = False  # whether the metrics param was on for this run
    water_weeds_lost_a: int = 0  # summed over agent_a's seat across all played orientations
    plant_decay_units_lost_a: int = 0
    metric_gate_passed: Optional[bool] = None  # None unless metrics_checked
    go: bool = False  # True only for stage="holdout-confirm" + IMPROVED/NON_INFERIOR + metric gate passed


def compare(agent_a, agent_b, seeds: Sequence[int], *,
            both_seats: bool = True,
            steps: Optional[int] = None,
            run_dir: Optional[Path] = None,
            record: bool = False,
            strict: bool = True,
            min_effect: Optional[float] = None,
            non_inferiority_margin: Optional[float] = None,
            resume: bool = False,
            require_distinct_versions: bool = True,
            workers: int = 1,
            metrics: bool = False,
            stage: Optional[str] = None) -> CompareResult:
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

    workers>1 runs one (seed, orientation) play() per ProcessPoolExecutor job (plan.md
    §1.5.1); per-seed diffs are identical to workers=1 for the same seeds/agents — only
    wall time changes. A non-picklable agent_a/agent_b (e.g. a lambda) falls back to
    workers=1 with a warning instead of raising.

    metrics=True (plan.md §1.5.3 / review.md §5 check #5) additionally extracts
    water_weeds_lost/plant_decay_units_lost for agent_a's seat in every orientation played,
    exposed as `water_weeds_lost_a`/`plant_decay_units_lost_a` (summed) and
    `metric_gate_passed` (both counters exactly 0). Off by default — extract_metrics() is not
    free (review.md L5) and most calls (e.g. ablation sweeps) only need `rewards`.

    stage tags which decision this report may back: "dev-screen" (tuning/screening — never a
    GO by itself) or "holdout-confirm" (the one-shot final check). `go` is only ever True for
    stage="holdout-confirm" with verdict IMPROVED/NON_INFERIOR *and* metrics_checked with the
    metric gate passed — a $-verdict computed without metrics never counts as a GO (plan.md
    §1.5.3: "το $-gate δεν μετράει αν τα metric gates δεν έχουν τρέξει").
    """
    if stage is not None and stage not in VALID_STAGES:
        raise ValueError(f"compare(): stage must be one of {VALID_STAGES} or None, got {stage!r}")
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

    # review.md M2: rows used to carry no version identity, so `--resume` after changing the
    # agent under test silently mixed seeds from two different code versions into one verdict
    # that still looked complete. The first line of results.jsonl now records the
    # code_fingerprints this run was started with; resuming checks it matches.
    done = {}
    if resume and jsonl_path is not None and jsonl_path.exists():
        lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines and json.loads(lines[0]).get("_meta"):
            recorded = tuple(json.loads(lines[0]).get("code_fingerprints", ()))
            if recorded != code_fingerprints:
                raise ValueError(
                    f"compare(): --resume run_dir {run_dir_path} was recorded with code "
                    f"fingerprints {recorded}, but this call is comparing {code_fingerprints} "
                    f"— delete {jsonl_path} or use a different run_dir instead of mixing "
                    "results from two different agent versions"
                )
            data_lines = lines[1:]
        elif lines:
            raise ValueError(
                f"compare(): --resume run_dir {run_dir_path} has a results.jsonl with no "
                f"recorded code fingerprints (predates this check) — delete {jsonl_path} or "
                "use a different run_dir; resuming into it could silently mix agent versions"
            )
        else:
            data_lines = []
        for line in data_lines:
            row = json.loads(line)
            done[row["seed"]] = row
    elif jsonl_path is not None:
        run_dir_path.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text(
            json.dumps({"_meta": True, "code_fingerprints": list(code_fingerprints)}) + "\n",
            encoding="utf-8",
        )

    def _persist(row: dict) -> None:
        if jsonl_path is not None:
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    def _finalize(seed, orientations) -> dict:
        for orientation in orientations:
            orientation["diff"] = orientation["bank_a"] - orientation["bank_b"]
            orientation["winner"] = (
                "a" if orientation["diff"] > 0 else ("b" if orientation["diff"] < 0 else "tie")
            )
        bank_a = statistics.mean(o["bank_a"] for o in orientations)
        bank_b = statistics.mean(o["bank_b"] for o in orientations)
        diff = bank_a - bank_b
        winner = "a" if diff > 0 else ("b" if diff < 0 else "tie")
        return {
            "seed": seed,
            "seat_layout": [o["layout"] for o in orientations],
            "orientations": orientations,
            "bank_a": bank_a,
            "bank_b": bank_b,
            "diff": diff,
            "winner": winner,
            # plan.md §1.5.3: summed (not averaged) over every orientation played this seed —
            # a defect that shows up in one orientation but not the other must still fail the
            # gate, not get diluted into a mean.
            "water_weeds_lost_a": sum(o.get("water_weeds_lost_a", 0) for o in orientations),
            "plant_decay_units_lost_a": sum(o.get("plant_decay_units_lost_a", 0) for o in orientations),
        }

    # review.md M2/M6 fields above already guard resume; a callable agent_spec (lambda,
    # nested function) can't cross a spawned worker process, so workers>1 degrades to
    # sequential rather than raising (plan.md §1.5.1 (a)).
    effective_workers = workers
    if workers > 1 and not (_is_picklable(agent_a) and _is_picklable(agent_b)):
        warnings.warn(
            "compare(): agent_a/agent_b is not picklable (e.g. a lambda or nested function) "
            "— ProcessPoolExecutor requires picklable arguments, so falling back to workers=1 "
            "(sequential). Use a file path, built-in name, or a top-level function to get "
            "parallel speedup.",
            stacklevel=2,
        )
        effective_workers = 1

    computed = {seed: done[seed] for seed in seeds if seed in done}
    pending_seeds = [seed for seed in seeds if seed not in done]

    if effective_workers > 1 and pending_seeds:
        # plan.md §1.5.1 (β): one ProcessPoolExecutor job per (seed, orientation) — the
        # parent is the only writer of results.jsonl/computed, futures never touch it.
        jobs = []
        for seed in pending_seeds:
            jobs.append((seed, False))
            if both_seats:
                jobs.append((seed, True))

        raw_results = {}
        job_errors = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=effective_workers) as executor:
            future_to_job = {}
            for seed, swap in jobs:
                first, second = (agent_b, agent_a) if swap else (agent_a, agent_b)
                fut = executor.submit(_play_orientation, first, second, seed, steps, run_dir,
                                       record, strict, metrics)
                future_to_job[fut] = (seed, swap)
            for fut in concurrent.futures.as_completed(future_to_job):
                seed, swap = future_to_job[fut]
                try:
                    raw_results[(seed, swap)] = fut.result()
                except Exception as e:  # per-future try/except — one bad seed doesn't kill the pool
                    job_errors.setdefault(seed, repr(e))

        for seed in pending_seeds:
            if seed in job_errors:
                err_row = {"seed": seed, "error": job_errors[seed]}
                computed[seed] = err_row
                _persist(err_row)
                continue
            rewards0, metrics0 = raw_results[(seed, False)]
            orientation0 = {"layout": "A@0/B@1", "bank_a": rewards0[0], "bank_b": rewards0[1]}
            if metrics:
                m0 = metrics0.get(0, {})
                orientation0["water_weeds_lost_a"] = m0.get("water_weeds_lost", 0)
                orientation0["plant_decay_units_lost_a"] = m0.get("plant_decay_units_lost", 0)
            orientations = [orientation0]
            if both_seats:
                rewards1, metrics1 = raw_results[(seed, True)]
                orientation1 = {"layout": "B@0/A@1", "bank_a": rewards1[1], "bank_b": rewards1[0]}
                if metrics:
                    m1 = metrics1.get(1, {})
                    orientation1["water_weeds_lost_a"] = m1.get("water_weeds_lost", 0)
                    orientation1["plant_decay_units_lost_a"] = m1.get("plant_decay_units_lost", 0)
                orientations.append(orientation1)
            row = _finalize(seed, orientations)
            computed[seed] = row
            _persist(row)
    else:
        for seed in pending_seeds:
            try:
                orientations = []
                r_a0 = play(agent_a, agent_b, seed, steps=steps, run_dir=run_dir, record=record,
                            strict=strict, metrics=metrics)
                orientation0 = {
                    "layout": "A@0/B@1",
                    "bank_a": r_a0.rewards[0],
                    "bank_b": r_a0.rewards[1],
                }
                if metrics:
                    m0 = r_a0.metrics.get(0, {})
                    orientation0["water_weeds_lost_a"] = m0.get("water_weeds_lost", 0)
                    orientation0["plant_decay_units_lost_a"] = m0.get("plant_decay_units_lost", 0)
                orientations.append(orientation0)

                if both_seats:
                    r_b0 = play(agent_b, agent_a, seed, steps=steps, run_dir=run_dir, record=record,
                                strict=strict, metrics=metrics)
                    orientation1 = {
                        "layout": "B@0/A@1",
                        "bank_a": r_b0.rewards[1],
                        "bank_b": r_b0.rewards[0],
                    }
                    if metrics:
                        m1 = r_b0.metrics.get(1, {})
                        orientation1["water_weeds_lost_a"] = m1.get("water_weeds_lost", 0)
                        orientation1["plant_decay_units_lost_a"] = m1.get("plant_decay_units_lost", 0)
                    orientations.append(orientation1)

                row = _finalize(seed, orientations)
                computed[seed] = row
                _persist(row)
            except Exception as e:
                err_row = {"seed": seed, "error": repr(e)}
                computed[seed] = err_row
                _persist(err_row)

    # Sorted by seed regardless of completion order (plan.md §1.5.1): future completion
    # order must not change the output, or criterion (i) — identical workers=1 vs
    # workers=N per-seed diffs — becomes flaky by design.
    per_seed = []
    errors = []
    for seed in sorted(computed):
        row = computed[seed]
        if "error" in row:
            errors.append(row)
        else:
            per_seed.append(row)

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
    elif (
        ci95[0] >= -effective_non_inferiority_margin
        and n >= MIN_N_FOR_NON_INFERIOR
        and se_diff > 0
    ):
        # review.md M3: a degenerate CI (n=1, or se_diff==0 with n>1) let a single lucky seed
        # or a coincidentally-constant diff pass as NON_INFERIOR with no statistical basis.
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

    water_weeds_lost_a = sum(row["water_weeds_lost_a"] for row in per_seed)
    plant_decay_units_lost_a = sum(row["plant_decay_units_lost_a"] for row in per_seed)
    metric_gate_passed = (
        (water_weeds_lost_a == 0 and plant_decay_units_lost_a == 0) if metrics else None
    )
    # plan.md §1.5.3: a GO is only real from stage="holdout-confirm", with a directional
    # verdict, AND the metric gate having actually run and passed — an unmeasured metric
    # gate must never silently count as passed.
    go = bool(
        stage == "holdout-confirm"
        and verdict in ("IMPROVED", "NON_INFERIOR")
        and metrics
        and metric_gate_passed
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
        stage=stage,
        metrics_checked=metrics,
        water_weeds_lost_a=water_weeds_lost_a,
        plant_decay_units_lost_a=plant_decay_units_lost_a,
        metric_gate_passed=metric_gate_passed,
        go=go,
    )
