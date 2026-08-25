"""compare(): paired-seed A-vs-B comparison. Methodology from MASTERPLAN §6
(viz cells 46-50) — same seeds for both agents.

Go/no-go needs directional confidence and a practical margin:
- `significant`: the paired-seed mean diff clears a t-distribution confidence bound (not the
  z-approximation 2*SE, which is anti-conservative below ~30 seeds; None if se_diff==0, since a
  perfectly constant diff is not "infinitely significant" — it usually means a deterministic,
  seed-independent difference, not a real effect).
- `practical`: the mean diff also clears an absolute-$ floor, so a statistically "significant"
  but trivial $1 diff doesn't read as a real result.
- `verdict`: IMPROVED/NON_INFERIOR/WITHIN_MARGIN/REGRESSED/INCONCLUSIVE/INCOMPLETE. A negative
  practical result can never be approved by taking `abs(mean_diff)`. WITHIN_MARGIN (review.md
  H2) is NON_INFERIOR's confirmed-regression sibling: the paired-seed CI is entirely negative
  (not straddling zero — that's genuine equivalence, still NON_INFERIOR) but still inside the
  margin. It reads as a different claim ("regressed, but not by much" vs "didn't regress") and
  a GO built on it requires `accept_within_margin=True`, never silently.
"""
import concurrent.futures
import json
import math
import multiprocessing
import os
import pickle
import platform as platform_module
import statistics
import subprocess
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from harness.checkpoint import agent_fingerprint
from harness.play import play
from harness.seeds import CONFIRM_SEED_SETS, DEV_SEEDS, NAMED_SEED_SETS
from harness.town_pin import PIN_MODES, pinned_town, schedule_for_mode

# Two-sided 95% t-critical value by degrees of freedom (df = n-1). Exact through df=30,
# then a handful of anchor points with linear interpolation, 1.96 (normal) beyond df=120 —
# avoids a hard scipy dependency for what is a small, well-known table (review.md M5).
MIN_N_FOR_NON_INFERIOR = 12  # review_89d99f0_2026-08-05.md M3

# review_89d99f0_2026-08-05.md §5 check #5: a $-verdict alone can hide a regression that just
# happens to net positive (e.g. more aggressive selling offsetting worse water discipline).
# stage tags which decision a report may be used for: dev-screen (tuning) reports must never
# be read as a GO by themselves — only holdout-confirm, checked exactly once, can be.
VALID_STAGES = ("dev-screen", "holdout-confirm")

# Απόφαση Δ (2026-08-10): which question a comparison is being asked.
#   "acceptance"  — vs the §Β.2 meta bench: the arm that decides whether an increment is taken.
#                   The priced leg applies here, on the *difference* between the two sides.
#   "regression"  — vs our own baseline (mirror): a regression detector under Απόφαση Β. The
#                   $-verdict and the structural leg apply; the priced budget never does.
# Default "acceptance": a run that does not say which question it asks is held to the stricter
# of the two, so the looser regime is always an explicit, recorded choice.
ARM_ROLES = ("acceptance", "regression")

# review.md H5: the only durable, git-tracked evidence that a gate ran and what it decided.
# runs/ (replays, per-episode jsonl) stays gitignored — this is deliberately small.
GATES_DIR = Path("gates")
DEFAULT_CONFIRM_LEDGER = GATES_DIR / "confirm_log.jsonl"

# Απόφαση Α (2026-08-10): the hard-zero gate is split in two.
#
# Counters that indicate a *logic fault* stay hard zero — there is no price at which a clipped
# production tick or an unexplained no-op is acceptable, because it means the agent did
# something it did not intend. Counters that are *losses* get priced, because a loss is a
# number of dollars and has to be compared against the dollars the change earns. The old
# all-hard-zero gate rejected +$3,019.3/ep for 84 burnt units and 34 lost tiles across 96
# episodes (memory.md 2026-08-09 (ε)) — that is a $237/ep objection to a $3,019/ep gain, and
# three sessions were spent on it while the ladder rating stood still.
#
# Prices are deliberately conservative (they over-state the loss, so the gate errs towards
# rejecting):
#   escape           $1,000  — $400-500 purchase price plus the rest of the season's output
#   burnt shed unit    $150  — under the measured premium average ($200-270), over wheat ($25-54)
#   lost crop tile     $300  — the tile's remaining yield plus the DIG needed to reclaim it
METRIC_UNIT_PRICES = {
    "animals_escaped": 1000.0,
    "shed_overflow_burnt": 150.0,
    "lost_crop_tiles": 300.0,
}
# The raw counters a run may have to explain. `lost_crop_tiles` above is derived from the last
# two of these rather than being a counter of its own — see priced_metric_counts().
PRICED_SOURCE_METRICS = (
    "animals_escaped", "shed_overflow_burnt", "unexpected_weeds_lost", "water_weeds_lost",
)
# Both bounds bind. The fraction keeps a loss proportionate to what the change actually earns;
# the absolute cap stops a large mean_diff from buying an unlimited amount of breakage.
PRICED_LOSS_GAIN_FRACTION = 0.10
PRICED_LOSS_ABSOLUTE_CAP = 500.0


def priced_metric_counts(counts) -> dict:
    """Collapse the raw counters into the quantities that actually get priced."""
    return {
        "animals_escaped": counts.get("animals_escaped") or 0,
        "shed_overflow_burnt": counts.get("shed_overflow_burnt") or 0,
        # unexpected_weeds_lost and water_weeds_lost fire on the *same* PLANT->WEED transition
        # (harness/metrics.py:315-341): a tile that died of thirst is also an unexpected weed,
        # so the two overlap almost completely (34/34 in gate_v1h2d_feed_slack). Summing them
        # would charge the same lost tile twice; the priced quantity is their union, which is
        # bounded below by each of them and never under-prices either one.
        "lost_crop_tiles": max(
            counts.get("unexpected_weeds_lost") or 0, counts.get("water_weeds_lost") or 0
        ),
    }


def priced_metric_loss(counts, episodes: int) -> tuple:
    """Return (loss_per_episode, {priced quantity: $/episode}) for raw counters `counts`.

    `counts` maps the bare metric name (no `_a` suffix) to its summed count over `episodes`
    episodes. Counters outside PRICED_SOURCE_METRICS are ignored — they are either hard-zero
    structural checks or diagnostics (raw `weeds_lost`).
    """
    if not episodes:
        return 0.0, {}
    priced = priced_metric_counts(counts)
    breakdown = {
        metric: priced[metric] * price / episodes
        for metric, price in METRIC_UNIT_PRICES.items()
    }
    return sum(breakdown.values()), breakdown


def priced_loss_budget(mean_diff: float) -> float:
    """The most $/episode of priced loss a change earning `mean_diff` is allowed to cause."""
    return min(PRICED_LOSS_ABSOLUTE_CAP, PRICED_LOSS_GAIN_FRACTION * max(mean_diff, 0.0))


def priced_loss_delta(loss_a: float, loss_b: float) -> float:
    """Απόφαση Δ: what the candidate *introduces*, not what it inherits.

    Clamped at zero — a candidate that breaks *less* than the arm it is measured against does
    not earn a negative loss it can spend on breaking something else.
    """
    return max(0.0, loss_a - loss_b)

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


def _sign_test_p(k: int, n: int) -> Optional[float]:
    """Two-sided exact binomial sign-test p-value for `k` (the less frequent outcome) out of
    `n` non-tied trials under H0: p=0.5 (review.md H2) — same no-scipy-dependency reasoning
    as `_t_crit`'s vendored table. None when there are no non-tied trials to test."""
    if n <= 0:
        return None
    k = min(k, n - k)
    cumulative = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * cumulative)


def _seed_set_label(seeds: Sequence[int]) -> str:
    """A stable, human-readable name for a seed collection, used in provenance fields and
    the confirm ledger key (review.md C2/H5). Exact-matches a registered harness.seeds range
    first; falls back to a descriptive range string for ad-hoc subsets so the ledger key still
    means something instead of colliding across genuinely different seed lists."""
    seeds_set = set(seeds)
    for name, registered in NAMED_SEED_SETS.items():
        if seeds_set == set(registered):
            return name
    if not seeds_set:
        return "custom[empty]"
    return f"custom[{min(seeds_set)}-{max(seeds_set)},n={len(seeds_set)}]"


_HARNESS_GIT_SHA_CACHE: Optional[str] = None


def _harness_git_sha() -> Optional[str]:
    """review.md H5: which harness/agent commit produced this result — best-effort, None
    (not raised) outside a git checkout or without git installed, since compare() must keep
    working in either case."""
    global _HARNESS_GIT_SHA_CACHE
    if _HARNESS_GIT_SHA_CACHE is None:
        try:
            _HARNESS_GIT_SHA_CACHE = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
                cwd=Path(__file__).resolve().parent.parent,
            ).stdout.strip()
        except Exception:
            _HARNESS_GIT_SHA_CACHE = ""
    return _HARNESS_GIT_SHA_CACHE or None


def _kaggri_env() -> dict:
    """review.md H7: every KAGGRI_* env var currently set, recorded so a gate artefact never
    looks 'clean' while having actually run under debug instrumentation or (for older
    checkpoints that still read it) an ablation override."""
    return {k: v for k, v in sorted(os.environ.items()) if k.startswith("KAGGRI_")}


def _agent_spec_label(agent_spec) -> str:
    return agent_spec if isinstance(agent_spec, str) else repr(agent_spec)


def _warn_if_not_checkpoint(agent_spec, label: str) -> Optional[str]:
    """review.md H5 point 3: a go=True from stage='holdout-confirm' should run on immutable
    checkpointed code (has a manifest.json next to it), not live main.py, so the result can
    be reproduced later. Warn, don't raise — dev workflows legitimately compare live code.
    Returns the warning message (review.md L7: so compare() can also collect it onto
    CompareResult.warnings), or None if no warning was raised."""
    if not isinstance(agent_spec, str):
        return None
    path = Path(agent_spec)
    if path.suffix == ".py" and path.exists() and not (path.parent / "manifest.json").exists():
        message = (
            f"compare(): {label}={agent_spec!r} has no manifest.json next to it — a GO from "
            "stage='holdout-confirm' should run on checkpointed code (harness.checkpoint."
            "create_checkpoint), not live main.py, so the result can be reproduced later "
            "(review.md H5)"
        )
        warnings.warn(message, stacklevel=3)
        return message
    return None


def _read_confirm_ledger(path: Path) -> list:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_confirm_ledger(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _has_prior_dev_screen(root: Path, candidate_fingerprint: str) -> bool:
    """Whether durable gate evidence shows this exact candidate was screened before confirm."""
    if not root.exists():
        return False
    for results_path in root.rglob("results.json"):
        try:
            payload = json.loads(results_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        fingerprints = payload.get("code_fingerprints", ())
        if (
            payload.get("stage") == "dev-screen"
            and fingerprints
            and fingerprints[0] == candidate_fingerprint
            and not payload.get("incomplete", False)
        ):
            return True
    return False


def _play_orientation(agent_first, agent_second, seed, steps, run_dir, record, strict, metrics,
                      town_pin=None, town_schedule=None):
    """Module-level (picklable) unit of work for the ProcessPoolExecutor path:
    exactly one `play()` call, returning the raw (bank_first, bank_second) rewards
    plus the per-seat metrics dict a single orientation needs. Kept at module scope — a
    nested closure isn't picklable and would silently break the Windows spawn start method.

    §Β.0′: the town pin is applied **here**, inside the worker, from the
    picklable `(town_pin, town_schedule)` pair — a context manager cannot cross a process
    boundary, and under the spawn start method the parent's monkeypatch does not exist in the
    child at all. Both orientations of a seed get the same pair, so both arms of a comparison
    play the same town."""
    with pinned_town(town_pin, town_schedule):
        result = play(agent_first, agent_second, seed, steps=steps, run_dir=run_dir, record=record,
                      strict=strict, metrics=metrics)
    return result.rewards, result.metrics


_V1K_REPORT_METRICS = (
    "crop_tile_days",
    "worker_turns_idle",
    "worker_turns_total",
    # R15 (ROADMAP §6): worker_turns_idle/_total were aggregated here but worker_turns_moving
    # was not, so the commute share — the number ROADMAP §4.3 S3 step 1c's throughput work is
    # judged on (57-62% of every unit-turn) — was invisible in every gate artefact ever produced.
    # analysis/v1o3_visit_efficiency.py had to recover it per episode with its own separate
    # play() calls because of this gap.
    "worker_turns_moving",
    # R17 (ROADMAP §1.1, S3 step 1d race): v1p1b arm A1 hit 46,0%
    # worker_turns_moving — the largest commute cut ever measured here — by doing *fewer*
    # working turns than baseline and shedding 30% of crop_tile_days into idle. A ratio
    # threshold on worker_turns_moving alone is satisfiable by shrinking the farm; the
    # absolute working-turn count has to be read alongside it so that can't pass unnoticed.
    "worker_turns_working",
    "animals_underfed_days",
    "crop_revenue",
)

# R20 (ROADMAP §6, S3 step 2): per-product units + realised revenue in
# every gate artefact. v1m emitted only the MELON pair; every herd-13 economic risk (§0.2 of the
# step-2 brief) is a MILK/WOOL realised-price question (§4.1), and that number could not be read
# from a gate artefact at all. Generalised over this tuple, emitting `{product.lower()}_units_{arm}`
# and `{product.lower()}_revenue_{arm}`. MELON is first so its keys are byte-for-byte identical to
# the longhand v1m emission — older artefacts and tests keep reading unchanged.
_V1K_REPORT_PRODUCTS = ("MELON", "MILK", "WOOL")


def _attach_v1k_diagnostics(
    orientation: dict,
    metrics_by_seat: dict,
    *,
    a_seat: int,
    b_seat: int,
) -> None:
    """Attach mandatory occupancy/feed reporting for both comparison arms."""
    for arm, seat in (("a", a_seat), ("b", b_seat)):
        seat_metrics = metrics_by_seat.get(seat, {})
        for metric in _V1K_REPORT_METRICS:
            orientation[f"{metric}_{arm}"] = int(seat_metrics.get(metric, 0))
        # v1m: MELON race gate needs units + realized $/u, not just crop_revenue sum.
        # R20: generalised over _V1K_REPORT_PRODUCTS (MELON + MILK + WOOL).
        units = seat_metrics.get("units_sold_by_product") or {}
        revenue = seat_metrics.get("revenue_by_product") or {}
        for product in _V1K_REPORT_PRODUCTS:
            key = product.lower()
            orientation[f"{key}_units_{arm}"] = int(units.get(product, 0))
            orientation[f"{key}_revenue_{arm}"] = int(revenue.get(product, 0))


# Απόφαση Δ point 4: the raw counters of *both* arms are reported. Δ changes
# the criterion, not the transparency — so every counter that gets priced on agent_a's side is
# also read off agent_b's seat, plus the raw `weeds_lost` diagnostic for symmetry.
_ARM_B_COUNTER_METRICS = (*PRICED_SOURCE_METRICS, "weeds_lost")


# S10 P2.1/P2.3: differential market counters that must be reported as Δ (A−B), not only
# as absolutes. An overlay that cuts our floor units by the same amount it cuts the
# opponent's is common-mode (K5) and does not move W/L (see the price-floor liquidation-
# sink memory). Every counter here is emitted as `<name>_a`, `<name>_b`, and `<name>_delta`.
_S10_DIFFERENTIAL_METRICS = (
    "floor_units",
    "floor_units_ordered",
    "sell_units_ordered",
    "sell_units_committed",
    "shed_peak",
)

# `shed_peak` is an episode MAXIMUM, not a count. Summing it across orientations and seeds
# produces a "total of peaks", which is not a peak of anything and reads as a much larger
# shed than any episode ever held. Aggregate these with max(), and recompute the delta from
# the aggregated sides rather than summing per-episode deltas.
_S10_MAX_METRICS = frozenset({"shed_peak"})


def _aggregate_s10_counters(rows) -> dict:
    """Fold per-episode/per-seed rows into one {metric}_{a,b,delta} block.

    Counts fold with sum; peaks fold with max. `delta` is always recomputed as a − b of the
    folded sides, so it stays consistent with the two sides it is reported next to.
    """
    rows = list(rows)
    out: dict = {}
    for metric in _S10_DIFFERENTIAL_METRICS:
        fold = max if metric in _S10_MAX_METRICS else sum
        va = fold((row.get(f"{metric}_a", 0) or 0) for row in rows) if rows else 0
        vb = fold((row.get(f"{metric}_b", 0) or 0) for row in rows) if rows else 0
        out[f"{metric}_a"] = va
        out[f"{metric}_b"] = vb
        out[f"{metric}_delta"] = va - vb
    return out


def _attach_metric_fields(orientation: dict, metrics_by_seat: dict, *, a_seat: int, b_seat: int) -> None:
    """Copy every gate counter and diagnostic out of one episode's per-seat metrics.

    agent_a occupies seat 0 in the "A@0/B@1" orientation and seat 1 in the swapped one, so
    which seat is read has to follow the arm, not a constant. Kept in one
    place because it is applied at four call sites (two orientations x sequential/parallel);
    the four inline copies it replaced were where a new counter got forgotten.
    """
    seat_a = metrics_by_seat.get(a_seat, {}) or {}
    orientation["water_weeds_lost_a"] = seat_a.get("water_weeds_lost", 0)
    orientation["plant_decay_units_lost_a"] = seat_a.get("plant_decay_units_lost", 0)
    orientation["animals_escaped_a"] = seat_a.get("animals_escaped", 0)
    orientation["clipped_production_ticks_a"] = seat_a.get("clipped_production_ticks", 0)
    orientation["shed_overflow_burnt_a"] = seat_a.get("shed_overflow_burnt", 0)
    orientation["weeds_lost_a"] = seat_a.get("weeds_lost", 0)
    orientation["unexpected_weeds_lost_a"] = seat_a.get("unexpected_weeds_lost", 0)
    orientation["units_sold_at_or_below_5_a"] = seat_a.get("units_sold_at_or_below_5", 0)
    orientation["sales_count_a"] = len(seat_a.get("market_sales", []))
    orientation["unexplained_noops_a"] = seat_a.get("unexplained_noops")
    orientation["market_sim_aborted_a"] = bool(seat_a.get("market_sim_aborted", False))

    seat_b = metrics_by_seat.get(b_seat, {}) or {}
    for metric in _ARM_B_COUNTER_METRICS:
        orientation[f"{metric}_b"] = seat_b.get(metric, 0)

    # S10 P2.3: floor/fill counters as Δ (A−B). Common-mode reductions do not move W/L.
    for metric in _S10_DIFFERENTIAL_METRICS:
        va = int(seat_a.get(metric, 0))
        vb = int(seat_b.get(metric, 0))
        orientation[f"{metric}_a"] = va
        orientation[f"{metric}_b"] = vb
        orientation[f"{metric}_delta"] = va - vb

    _attach_v1k_diagnostics(orientation, metrics_by_seat, a_seat=a_seat, b_seat=b_seat)


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
    t_crit: Optional[float] = None  # review.md L8: None (not NaN) — NaN doesn't survive to JSON
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
    sign_test_p: Optional[bool] = None  # review.md H2: exact binomial sign test on wins_a/wins_b
    verdict: str = "INCONCLUSIVE"
    incomplete: bool = False  # True if any seed errored or was otherwise skipped
    code_fingerprints: tuple = ("", "")
    stage: Optional[str] = None  # "dev-screen" | "holdout-confirm" | None
    # §Β.0′: which town-pin regime both arms played under (None = the engine's
    # own draw), and the exact per-seed schedule that produced it — a pinned verdict is only
    # valid for the towns actually pinned, so the towns are part of the result, not a setting.
    town_pin: Optional[str] = None
    town_schedules: dict = field(default_factory=dict)  # {seed: [shop names]} — {} when unpinned
    metrics_checked: bool = False  # whether the metrics param was on for this run
    water_weeds_lost_a: Optional[int] = None  # None unless metrics_checked (review.md C3)
    plant_decay_units_lost_a: Optional[int] = None
    animals_escaped_a: Optional[int] = None  # G5/v1d
    clipped_production_ticks_a: Optional[int] = None  # G8/v1d
    # review.md M1: four more signals extract_metrics() already computes but the gate ignored.
    shed_overflow_burnt_a: Optional[int] = None  # hard gate, same as the four above
    weeds_lost_a: Optional[int] = None  # raw diagnostic; includes successful retirement
    unexpected_weeds_lost_a: Optional[int] = None  # corrected semantic hard gate
    units_sold_at_or_below_5_a: Optional[int] = None  # budget (<=2% of sales_count_a), not ==0
    sales_count_a: Optional[int] = None  # denominator for the units_sold_at_or_below_5_a budget
    unexplained_noops_a: Optional[int] = None  # None unless diagnostics were collected (KAGGRI_DEBUG)
    market_sim_aborted_a: Optional[bool] = None  # review.md M11: True fails the gate
    # v1k: mandatory per-gate diagnostics, totals across all raw episodes.
    crop_tile_days_a: Optional[int] = None
    crop_tile_days_b: Optional[int] = None
    worker_turns_idle_a: Optional[int] = None
    worker_turns_idle_b: Optional[int] = None
    worker_turns_total_a: Optional[int] = None
    worker_turns_total_b: Optional[int] = None
    worker_turns_moving_a: Optional[int] = None  # R15 (ROADMAP §6)
    worker_turns_moving_b: Optional[int] = None
    worker_turns_working_a: Optional[int] = None  # R17 (ROADMAP §6)
    worker_turns_working_b: Optional[int] = None
    animals_underfed_days_a: Optional[int] = None
    animals_underfed_days_b: Optional[int] = None
    crop_revenue_a: Optional[int] = None
    crop_revenue_b: Optional[int] = None
    # v1m: MELON race reporting (totals across raw episodes).
    melon_units_a: Optional[int] = None
    melon_units_b: Optional[int] = None
    melon_revenue_a: Optional[int] = None
    melon_revenue_b: Optional[int] = None
    # R20 (ROADMAP §6): MILK + WOOL units/revenue, same shape as the MELON pair. Realised price
    # is revenue/units per product — the §4.1 currency, and the number the herd-13 MILK-saturation
    # risk (§3.3) is decided on.
    milk_units_a: Optional[int] = None
    milk_units_b: Optional[int] = None
    milk_revenue_a: Optional[int] = None
    milk_revenue_b: Optional[int] = None
    wool_units_a: Optional[int] = None
    wool_units_b: Optional[int] = None
    wool_revenue_a: Optional[int] = None
    wool_revenue_b: Optional[int] = None
    # Απόφαση Δ: the same four priced counters, read off agent_b's seat.
    # Reported unconditionally (Δ point 4) — the criterion changed, the transparency did not.
    animals_escaped_b: Optional[int] = None
    shed_overflow_burnt_b: Optional[int] = None
    unexpected_weeds_lost_b: Optional[int] = None
    water_weeds_lost_b: Optional[int] = None
    weeds_lost_b: Optional[int] = None  # raw diagnostic, same status as weeds_lost_a
    # S10 P2.3: differential market counters reported as A/B/Δ. None unless metrics_checked.
    # An overlay that cuts *our* floor_units by the same amount as the opponent's is common-
    # mode and does not move W/L — read the Δ, not the absolute.
    # Counts are summed over episodes; `shed_peak` is folded with max (see
    # _aggregate_s10_counters) because a sum of per-episode peaks is not a peak.
    floor_units_a: Optional[int] = None
    floor_units_b: Optional[int] = None
    floor_units_delta: Optional[int] = None
    floor_units_ordered_a: Optional[int] = None
    floor_units_ordered_b: Optional[int] = None
    floor_units_ordered_delta: Optional[int] = None
    sell_units_ordered_a: Optional[int] = None
    sell_units_ordered_b: Optional[int] = None
    sell_units_ordered_delta: Optional[int] = None
    sell_units_committed_a: Optional[int] = None
    sell_units_committed_b: Optional[int] = None
    sell_units_committed_delta: Optional[int] = None
    shed_peak_a: Optional[int] = None
    shed_peak_b: Optional[int] = None
    shed_peak_delta: Optional[int] = None
    # Απόφαση Α/Δ: what the surviving losses cost per episode on each side,
    # what the *difference* was allowed to cost, and the written mechanism for each non-zero
    # candidate counter. `priced_loss_per_episode` is agent_a's absolute loss and keeps its name
    # for compatibility with every gate artefact written before Δ; it is also emitted as
    # `priced_loss_a` in results.json so the JSON reads as a matched pair with `priced_loss_b`.
    priced_loss_per_episode: Optional[float] = None
    priced_loss_b: Optional[float] = None
    priced_loss_delta: Optional[float] = None
    priced_loss_budget_used: Optional[float] = None
    priced_loss_breakdown: dict = field(default_factory=dict)
    priced_loss_breakdown_b: dict = field(default_factory=dict)
    arm_role: str = "acceptance"  # which question this comparison answers (ARM_ROLES)
    metric_mechanisms: dict = field(default_factory=dict)
    unexplained_metrics: tuple = ()  # non-zero priced counters with no declared mechanism
    metric_gate_passed: Optional[bool] = None  # None unless metrics_checked
    prior_dev_screen_found: bool = False
    min_effect_used: float = 0.0  # review.md H1: the actual $ floor this verdict was judged against
    non_inferiority_margin_used: float = 0.0
    go: bool = False  # True only for stage="holdout-confirm" + IMPROVED/NON_INFERIOR + metric gate passed
    repeat_confirm_index: int = 0  # review.md C2: 0 = first confirm for this (agent_b, seed set)
    agent_a_spec: str = ""  # review.md H5: raw spec strings, seed set name, and run provenance
    agent_b_spec: str = ""
    seed_set_name: str = ""
    harness_git_sha: Optional[str] = None
    platform: str = ""
    python_version: str = ""
    env: dict = field(default_factory=dict)  # every KAGGRI_* env var set during this run
    warnings: list = field(default_factory=list)  # review.md L7: warnings.warn() messages raised


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
            stage: Optional[str] = None,
            town_pin: Optional[str] = None,
            accept_within_margin: bool = False,
            allow_repeat_confirm: bool = False,
            confirm_ledger_path: Optional[Path] = None,
            metric_mechanisms: Optional[dict] = None,
            arm_role: str = "acceptance",
            screen_evidence_dir: Optional[Path] = None) -> CompareResult:
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
    skipped rather than losing every seed played before it. Resuming re-checks the full run
    contract recorded in the first line of results.jsonl (code_fingerprints, metrics,
    both_seats, steps) and raises on any mismatch (review.md C3) — an unmeasured metric gate
    or a single-seat run must never silently launder into a "complete" both-seats/metrics
    report just because --resume skipped every seed as already done.

    min_effect is the absolute-$ floor for `practical` (default max($200, 2% of mean bank_b)).
    non_inferiority_margin defaults to the same value; both are exposed on the result as
    `min_effect_used`/`non_inferiority_margin_used` (review.md H1) since the percentage
    default drifts as bank_b grows. Directional verdicts are: IMPROVED, NON_INFERIOR,
    WITHIN_MARGIN, REGRESSED, INCONCLUSIVE, or INCOMPLETE.

    workers>1 runs one (seed, orientation) play() per ProcessPoolExecutor job;
    per-seed diffs are identical to workers=1 for the same seeds/agents — only
    wall time changes. A non-picklable agent_a/agent_b (e.g. a lambda) falls back to
    workers=1 with a warning instead of raising. Results are persisted (when run_dir is
    given) as soon as each seed's orientation(s) all land, not only after the whole pool
    finishes (review.md H6) — a run killed partway through still leaves a resumable
    results.jsonl. As today, if any orientation for a seed errors, the whole seed is recorded
    as errored — a lone successful sibling orientation is discarded, not silently kept.

    metrics=True additionally extracts every hard-loss counter, the semantic unexpected-weed
    counter, low-price-sale budget, diagnostics no-ops, and market-simulation health for
    agent_a's seat in every orientation. Raw `weeds_lost` remains diagnostic because
    successful ongoing-crop retirement also produces a PLANT->WEED transition. Off by
    default — extract_metrics() is not free. When metrics=False gate fields are None, not 0:
    absence of measurement is not proof of zero loss.

    The metric gate itself is Απόφαση Α as amended by Απόφαση Δ
    (2026-08-10), in three parts:
      - structural faults stay hard zero, on agent_a's counters, in *both* arm roles:
        plant_decay_units_lost, clipped_production_ticks, unexplained no-ops,
        market-simulation abort, and the <=2% low-price sale budget;
      - every non-zero priced counter of agent_a must have a declared mechanism in
        `metric_mechanisms` ({metric name without the _a suffix: one-line explanation}), in
        both arm roles. An undeclared non-zero counter fails the gate: pricing buys tolerance
        for *understood* loss, never for unexplained loss, which is exactly the bug-detector
        role the old hard-zero gate had, and it is what still rejects v1m Δ3;
      - the priced leg is judged on the *difference* between the arms,
        priced_loss_delta = max(0, priced_loss_a - priced_loss_b), against
        priced_loss_budget(mean_diff) — both <=10% of the measured gain and <=$500/episode —
        and only when arm_role="acceptance".

    arm_role (Απόφαση Δ point 3) says which question the comparison asks. "acceptance" (the
    default) is a run against the §Β.2 meta bench: it decides whether an increment is taken, so
    the priced leg applies. "regression" is a mirror run against our own baseline, which under
    Απόφαση Β is a regression detector: the $-verdict and the structural/mechanism legs apply,
    the priced budget never does. Under Α the mirror was held to 10% of a mean_diff that a
    correct market-only fix drives to ~0 — a $6.49 budget no candidate could ever meet
    (memory.md 2026-08-10 (ι)). Both arms' raw counters are reported
    either way; Δ changed the criterion, not the transparency.

    Two points where the written rule needed an interpretation, recorded here and in
    Απόφαση Δ interpretation:
      - `priced_loss_b` is the loss of *this comparison's arm B*. In an acceptance run that is
        the bench opponent, not our own previous baseline — the rule is written per-arm
        ("follow the crop_tile_days_a/_b pattern"), so that is what it measures.
      - "the structural leg is unchanged and absolute in both arms" is read as: unchanged, i.e.
        still agent_a's counters, and applied under both arm roles. A bench's own structural
        faults are not the candidate's bug and do not fail our gate.

    stage tags which decision this report may back: "dev-screen" (tuning/screening — never a
    GO by itself, seeds must be a subset of harness.seeds.DEV_SEEDS) or "holdout-confirm"
    (the one-shot final check, seeds must exactly match one complete registered
    harness.seeds.CONFIRM_SEED_SETS entry) — any other seeds for either stage raises.
    A stage="holdout-confirm" call also checks+appends a tracked confirm ledger
    (confirm_ledger_path, default harness.compare.DEFAULT_CONFIRM_LEDGER): a repeat confirm
    for the same (agent_b fingerprint, seed set) raises unless allow_repeat_confirm=True, in
    which case it's recorded as `repeat_confirm_index` (review.md C1/C2) instead of silently
    picking the best of several pulls. It also raises if KAGGRI_ABLATION is set in the
    environment, and warns if KAGGRI_DEBUG is (review.md H7) — both are recorded either way
    in the `env` field.

    town_pin (§Β.0′, harness.town_pin) pins which shops the town unlocks, so
    both arms of an *occupancy* comparison play the same town on a given seed. Shop unlock and
    weed spawning share one per-day RNG stream (MASTERPLAN §2 #7), so any change to how many
    tiles are occupied at night — crew size, planting, BUY_LAND, animal placement — re-rolls the
    whole shop sequence, and an unpinned occupancy gate silently compares two different towns.
    Modes: "schedule" (a per-seed permutation of the 8 types — today's engine), "basket" (a
    per-seed draw *with replacement* — the announced balance change), "no_shops" (town centre
    only, the robustness floor). The pin is a function of the seed, never a constant: a constant
    schedule samples one town n times instead of reducing noise. Three limits, all load-bearing:
    it reduces (~19% of noise sd) rather than removes noise, it does not touch the weed stream,
    and a pinned result only holds for the pinned towns — which is why a stage="holdout-confirm"
    run with a pin raises: the GO must survive the real town distribution, not the pinned one.
    The chosen mode and the exact per-seed schedules are recorded on the result and in
    results.jsonl's `_meta` row, and --resume refuses to mix a pinned run with an unpinned one.

    `go` is only ever True for stage="holdout-confirm" with verdict IMPROVED or NON_INFERIOR
    (or WITHIN_MARGIN with accept_within_margin=True) *and* both seats, metrics_checked with
    the metric gate passed, an unpinned town distribution, and no sign-test-confirmed
    regression (review.md H2: wins_b > wins_a at p<0.01 blocks go unless
    accept_within_margin=True) — a $-verdict computed without metrics never counts as a GO
    .
    """
    if stage is not None and stage not in VALID_STAGES:
        raise ValueError(f"compare(): stage must be one of {VALID_STAGES} or None, got {stage!r}")
    if arm_role not in ARM_ROLES:
        raise ValueError(
            f"compare(): arm_role must be one of {ARM_ROLES}, got {arm_role!r} "
            "(Απόφαση Δ)"
        )
    if town_pin is not None and town_pin not in PIN_MODES:
        raise ValueError(
            f"compare(): town_pin must be one of {PIN_MODES} or None, got {town_pin!r}"
        )
    if stage == "holdout-confirm" and town_pin is not None:
        raise ValueError(
            "compare(): stage='holdout-confirm' must run with town_pin=None so the final "
            "decision covers the engine's real town distribution. Use town_pin only with "
            "stage='dev-screen'."
        )

    collected_warnings: list = []

    def _warn(message: str) -> None:
        # review.md L7: results.json used to have no trace that a warning was ever raised —
        # stacklevel=3 here matches the stacklevel=2 the inlined warnings.warn() calls below
        # used to have (one extra frame for this wrapper) so the warning still points at
        # compare()'s caller, not at this function.
        warnings.warn(message, stacklevel=3)
        collected_warnings.append(message)

    if town_pin == "schedule":
        _warn(
            "compare(): town_pin='schedule' represents a no-replacement permutation that is "
            "now rare under engine 1.32.6. Prefer town_pin='basket' for occupancy screens; "
            "'schedule' is retained only for historical reproduction."
        )

    seeds = list(seeds)
    deduped_seeds = list(dict.fromkeys(seeds))
    if len(deduped_seeds) != len(seeds):
        # review.md M8: a duplicate seed in --seeds used to be played and persisted twice,
        # silently shrinking n_effective below the requested seed count with no signal.
        _warn(
            f"compare(): seeds contained {len(seeds) - len(deduped_seeds)} duplicate(s) — "
            "deduplicated. Pass distinct seeds to avoid wasted compute."
        )
    seeds = deduped_seeds

    # review.md C2(a): stage and seeds used to be entirely uncross-checked — a --seed-set dev
    # --stage holdout-confirm combination (or any ad-hoc seed list) could produce a GO from
    # seeds that were just tuned on. A final confirm must consume one complete registered set:
    # accepting proper subsets enables repeated, overlapping looks at the holdout under distinct
    # custom ledger labels.
    if stage == "holdout-confirm":
        if not any(
            len(seeds) == len(registered) and set(seeds) == set(registered)
            for registered in CONFIRM_SEED_SETS
        ):
            raise ValueError(
                "compare(): stage='holdout-confirm' requires one complete seed set registered "
                "in harness.seeds.CONFIRM_SEED_SETS (HOLDOUT_SEEDS/CONFIRM2_SEEDS/...). "
                "Subsets, overlapping slices, dev seeds, and ad-hoc seeds cannot back a final "
                "decision."
            )
    elif stage == "dev-screen":
        if not set(seeds) <= set(DEV_SEEDS):
            raise ValueError(
                "compare(): stage='dev-screen' requires seeds drawn from harness.seeds."
                "DEV_SEEDS — got seeds outside it, which could silently mix confirm-set seeds "
                "into what's supposed to be a tuning-only report (review.md C2)."
            )

    code_fingerprints = (agent_fingerprint(agent_a), agent_fingerprint(agent_b))
    if require_distinct_versions and code_fingerprints[0] == code_fingerprints[1]:
        raise ValueError(
            "compare(): A and B have identical code fingerprints; use immutable checkpoints "
            "with unique package namespaces and compare genuinely different versions"
        )
    evidence_root = Path(screen_evidence_dir) if screen_evidence_dir is not None else GATES_DIR
    prior_dev_screen_found = (
        _has_prior_dev_screen(evidence_root, code_fingerprints[0])
        if stage == "holdout-confirm"
        else False
    )
    if stage == "holdout-confirm" and not prior_dev_screen_found:
        _warn(
            "compare(): no prior complete tracked dev-screen artefact was found for agent_a's "
            "fingerprint. This confirm may run for diagnostics, but it cannot produce GO=True."
        )
    if len(seeds) < 24:
        _warn(
            f"compare(): {len(seeds)} seeds — MASTERPLAN §6 asks for 24-48 for a final go/no-go "
            "decision; fewer is fine only for catching large, obvious regressions early."
        )

    # review.md H7: an ablated/debug-instrumented environment must never produce a "clean"
    # confirm artefact with no trace of it.
    env_snapshot = _kaggri_env()
    if stage == "holdout-confirm" and "KAGGRI_ABLATION" in env_snapshot:
        raise ValueError(
            "compare(): KAGGRI_ABLATION is set in the environment during a stage="
            "'holdout-confirm' run — a confirm gate must never run under an ablation "
            f"override (got {env_snapshot['KAGGRI_ABLATION']!r}); unset it before confirming "
            "(review.md H7)."
        )
    if env_snapshot.get("KAGGRI_DEBUG") not in (None, "0"):
        _warn(
            f"compare(): KAGGRI_DEBUG={env_snapshot['KAGGRI_DEBUG']!r} is set — this adds "
            "per-turn debug work and receipt emission to every agent call, which will skew "
            "timing; unset it for a clean gate/timing run (review.md H7)."
        )

    if stage == "holdout-confirm":
        collected_warnings.extend(
            message for message in (
                _warn_if_not_checkpoint(agent_a, "agent_a"),
                _warn_if_not_checkpoint(agent_b, "agent_b"),
            )
            if message is not None
        )
    # §Β.0′ point 1: the pin must be a function of the seed, so a run samples a *range* of
    # towns rather than one town n times — and both orientations of a seed get the same one.
    town_schedules = (
        {seed: schedule_for_mode(town_pin, seed) for seed in seeds} if town_pin is not None else {}
    )

    # review.md C1/C2: a confirm seed set is checked exactly once per (agent_b, seed set)
    # question. Checked up front (before playing anything) so a disallowed repeat fails fast.
    ledger_path = Path(confirm_ledger_path) if confirm_ledger_path is not None else DEFAULT_CONFIRM_LEDGER
    seed_set_name = _seed_set_label(seeds)
    repeat_confirm_index = 0
    if stage == "holdout-confirm":
        prior_entries = _read_confirm_ledger(ledger_path)
        repeat_confirm_index = sum(
            1 for row in prior_entries
            if row.get("agent_b_fp") == code_fingerprints[1]
            and row.get("seed_set_name") == seed_set_name
        )
        if repeat_confirm_index > 0 and not allow_repeat_confirm:
            raise ValueError(
                f"compare(): stage='holdout-confirm' already has {repeat_confirm_index} "
                f"recorded confirm(s) for agent_b fingerprint {code_fingerprints[1][:12]}... "
                f"on seed set {seed_set_name!r} in {ledger_path} — a confirm set is checked "
                "exactly once per question (review.md C1). Pass "
                "allow_repeat_confirm=True only if this repeat is deliberate; it will be "
                "recorded as repeat_confirm_index in the ledger and the result."
            )

    run_dir_path = Path(run_dir) if run_dir is not None else None
    jsonl_path = run_dir_path / "results.jsonl" if run_dir_path is not None else None

    # review_89d99f0_2026-08-05.md M2: rows used to carry no version identity, so `--resume` after changing the
    # agent under test silently mixed seeds from two different code versions into one verdict
    # that still looked complete. review.md C3: the meta line now records the *whole* run
    # contract (not just fingerprints) — metrics/both_seats/steps — and resuming into a
    # results.jsonl recorded under a different contract raises, instead of silently averaging
    # an unmeasured metric gate or a single-seat run into what looks like a complete report.
    # §Β.0′ point 2: the pinned town is part of the run contract, recorded alongside the
    # fingerprints so a results.jsonl says which towns produced it (G15) instead of being
    # indistinguishable from an unpinned run.
    meta_row = {
        "_meta": True,
        "code_fingerprints": list(code_fingerprints),
        "metrics": metrics,
        "both_seats": both_seats,
        "steps": steps,
        "town_pin": town_pin,
        "town_schedules": {str(seed): schedule for seed, schedule in town_schedules.items()},
    }

    done = {}
    if resume and jsonl_path is not None and jsonl_path.exists():
        lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines and json.loads(lines[0]).get("_meta"):
            meta = json.loads(lines[0])
            recorded_fingerprints = tuple(meta.get("code_fingerprints", ()))
            if recorded_fingerprints != code_fingerprints:
                raise ValueError(
                    f"compare(): --resume run_dir {run_dir_path} was recorded with code "
                    f"fingerprints {recorded_fingerprints}, but this call is comparing "
                    f"{code_fingerprints} — delete {jsonl_path} or use a different run_dir "
                    "instead of mixing results from two different agent versions"
                )
            for contract_field, current_value in (
                ("metrics", metrics), ("both_seats", both_seats), ("steps", steps),
            ):
                recorded_value = meta.get(contract_field, "<missing, predates this check>")
                if contract_field not in meta or recorded_value != current_value:
                    raise ValueError(
                        f"compare(): --resume run_dir {run_dir_path} was recorded with "
                        f"{contract_field}={recorded_value!r}, but this call passes "
                        f"{contract_field}={current_value!r} — delete {jsonl_path} or use a "
                        "different run_dir instead of resuming with different run parameters "
                        "(review.md C3: an unmeasured metric gate or a single-seat run must "
                        "never silently launder into a measured GO just because every seed "
                        "looks 'done')"
                    )
            # Checked separately from the loop above, with a None default: a results.jsonl
            # written before §Β.0′ existed has no town_pin key and is an unpinned run, so it
            # must still resume as one — while resuming it *with* a pin (or vice versa) mixes
            # two different town distributions into one mean_diff and has to raise.
            recorded_town_pin = meta.get("town_pin")
            if recorded_town_pin != town_pin:
                raise ValueError(
                    f"compare(): --resume run_dir {run_dir_path} was recorded with "
                    f"town_pin={recorded_town_pin!r}, but this call passes town_pin="
                    f"{town_pin!r} — delete {jsonl_path} or use a different run_dir instead of "
                    "mixing pinned and unpinned towns (or two different pin modes) into one "
                    "verdict (§Β.0′)"
                )
            recorded_town_schedules = meta.get("town_schedules", {})
            current_town_schedules = meta_row["town_schedules"]
            if town_pin is not None and (
                "town_schedules" not in meta
                or recorded_town_schedules != current_town_schedules
            ):
                raise ValueError(
                    f"compare(): --resume run_dir {run_dir_path} has different town_schedules "
                    "for the same town_pin mode. The schedule generator or seed mapping "
                    "changed; use a new run_dir instead of mixing town distributions."
                )
            data_lines = lines[1:]
        elif lines:
            raise ValueError(
                f"compare(): --resume run_dir {run_dir_path} has a results.jsonl with no "
                f"recorded code fingerprints (predates this check) — delete {jsonl_path} or "
                "use a different run_dir; resuming into it could silently mix results from "
                "two different agent versions or run contracts"
            )
        else:
            # review.md L3: an empty results.jsonl (a run that died before its first _persist)
            # used to fall through here with no meta line ever written — the *next* --resume
            # would then see a non-empty file with ordinary seed rows and raise the wrong
            # diagnosis ("no recorded code fingerprints"). Write the meta line now, same as the
            # fresh-run branch below, so this behaves like the fresh run it actually is.
            data_lines = []
            jsonl_path.write_text(json.dumps(meta_row) + "\n", encoding="utf-8")
        for line in data_lines:
            row = json.loads(line)
            done[row["seed"]] = row
    elif jsonl_path is not None:
        run_dir_path.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text(json.dumps(meta_row) + "\n", encoding="utf-8")

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
        # Summed (not averaged) over every orientation played this seed — a
        # defect that shows up in one orientation but not the other must still fail the gate,
        # not get diluted into a mean. review.md C3: None (not 0) when metrics wasn't on for
        # this run — a metric that was never measured must never read as "measured, zero".
        if metrics:
            water_weeds_lost_a = sum(o.get("water_weeds_lost_a", 0) for o in orientations)
            plant_decay_units_lost_a = sum(o.get("plant_decay_units_lost_a", 0) for o in orientations)
            animals_escaped_a = sum(o.get("animals_escaped_a", 0) for o in orientations)
            clipped_production_ticks_a = sum(o.get("clipped_production_ticks_a", 0) for o in orientations)
            # review.md M1/M11: same summed-not-averaged pattern as the four counters above.
            shed_overflow_burnt_a = sum(o.get("shed_overflow_burnt_a", 0) for o in orientations)
            weeds_lost_a = sum(o.get("weeds_lost_a", 0) for o in orientations)
            unexpected_weeds_lost_a = sum(
                o.get("unexpected_weeds_lost_a", 0) for o in orientations
            )
            units_sold_at_or_below_5_a = sum(o.get("units_sold_at_or_below_5_a", 0) for o in orientations)
            sales_count_a = sum(o.get("sales_count_a", 0) for o in orientations)
            noop_values = [o.get("unexplained_noops_a") for o in orientations]
            unexplained_noops_a = None if any(v is None for v in noop_values) else sum(noop_values)
            market_sim_aborted_a = any(o.get("market_sim_aborted_a", False) for o in orientations)
            v1k_diagnostics = {
                f"{metric}_{arm}": sum(
                    o.get(f"{metric}_{arm}", 0) for o in orientations
                )
                for metric in _V1K_REPORT_METRICS
                for arm in ("a", "b")
            }
            for arm in ("a", "b"):
                for product in _V1K_REPORT_PRODUCTS:
                    key = product.lower()
                    v1k_diagnostics[f"{key}_units_{arm}"] = sum(
                        o.get(f"{key}_units_{arm}", 0) for o in orientations
                    )
                    v1k_diagnostics[f"{key}_revenue_{arm}"] = sum(
                        o.get(f"{key}_revenue_{arm}", 0) for o in orientations
                    )
            # Απόφαση Δ: same summed-not-averaged rule as the _a counters above.
            arm_b_counters = {
                f"{metric}_b": sum(o.get(f"{metric}_b", 0) for o in orientations)
                for metric in _ARM_B_COUNTER_METRICS
            }
            # S10 P2.3: fold the orientations for this seed (counts sum, peaks max).
            s10_diff_counters = _aggregate_s10_counters(orientations)
        else:
            water_weeds_lost_a = plant_decay_units_lost_a = None
            animals_escaped_a = clipped_production_ticks_a = None
            shed_overflow_burnt_a = weeds_lost_a = unexpected_weeds_lost_a = None
            units_sold_at_or_below_5_a = None
            sales_count_a = unexplained_noops_a = None
            market_sim_aborted_a = None
            v1k_diagnostics = {
                f"{metric}_{arm}": None
                for metric in _V1K_REPORT_METRICS
                for arm in ("a", "b")
            }
            for arm in ("a", "b"):
                for product in _V1K_REPORT_PRODUCTS:
                    key = product.lower()
                    v1k_diagnostics[f"{key}_units_{arm}"] = None
                    v1k_diagnostics[f"{key}_revenue_{arm}"] = None
            arm_b_counters = {f"{metric}_b": None for metric in _ARM_B_COUNTER_METRICS}
            s10_diff_counters = {
                f"{metric}_{suf}": None
                for metric in _S10_DIFFERENTIAL_METRICS for suf in ("a", "b", "delta")
            }
        return {
            "seed": seed,
            "seat_layout": [o["layout"] for o in orientations],
            "orientations": orientations,
            "bank_a": bank_a,
            "bank_b": bank_b,
            "diff": diff,
            "winner": winner,
            "water_weeds_lost_a": water_weeds_lost_a,
            "plant_decay_units_lost_a": plant_decay_units_lost_a,
            "animals_escaped_a": animals_escaped_a,
            "clipped_production_ticks_a": clipped_production_ticks_a,
            "shed_overflow_burnt_a": shed_overflow_burnt_a,
            "weeds_lost_a": weeds_lost_a,
            "unexpected_weeds_lost_a": unexpected_weeds_lost_a,
            "units_sold_at_or_below_5_a": units_sold_at_or_below_5_a,
            "sales_count_a": sales_count_a,
            "unexplained_noops_a": unexplained_noops_a,
            "market_sim_aborted_a": market_sim_aborted_a,
            **arm_b_counters,
            **s10_diff_counters,
            **v1k_diagnostics,
        }

    # review_89d99f0_2026-08-05.md M2 / review.md M6 fields above already guard resume; a callable agent_spec (lambda,
    # nested function) can't cross a spawned worker process, so workers>1 degrades to
    # sequential rather than raising.
    effective_workers = workers
    if workers > 1 and not (_is_picklable(agent_a) and _is_picklable(agent_b)):
        _warn(
            "compare(): agent_a/agent_b is not picklable (e.g. a lambda or nested function) "
            "— ProcessPoolExecutor requires picklable arguments, so falling back to workers=1 "
            "(sequential). Use a file path, built-in name, or a top-level function to get "
            "parallel speedup."
        )
        effective_workers = 1

    computed = {seed: done[seed] for seed in seeds if seed in done}
    pending_seeds = [seed for seed in seeds if seed not in done]

    if effective_workers > 1 and pending_seeds:
        # One ProcessPoolExecutor job per (seed, orientation) — the
        # parent is the only writer of results.jsonl/computed, futures never touch it.
        jobs = []
        for seed in pending_seeds:
            jobs.append((seed, False))
            if both_seats:
                jobs.append((seed, True))

        # review.md H6: finalize+persist as soon as a seed's orientation(s) all land, instead
        # of waiting for every future in the whole pool — a run killed partway (Ctrl-C, OOM,
        # reboot) at seed 47/48 used to lose all 47 already-finished seeds because nothing was
        # written until the pool closed. If any orientation for a seed errors, the whole seed
        # is recorded as errored immediately and a later-arriving sibling orientation for the
        # same seed is discarded (existing policy, now made explicit in code, not just timing).
        partial: dict = {}
        errored_seeds: set = set()
        try:
            # review.md M6: default start method is fork on Linux — a forked worker inherits
            # the parent's already-imported agent.config, so an env-var-based override never
            # gets re-read (the H4 failure mode). spawn always re-imports from scratch.
            mp_context = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=effective_workers, mp_context=mp_context,
            ) as executor:
                future_to_job = {}
                for seed, swap in jobs:
                    first, second = (agent_b, agent_a) if swap else (agent_a, agent_b)
                    fut = executor.submit(_play_orientation, first, second, seed, steps, run_dir,
                                           record, strict, metrics, town_pin,
                                           town_schedules.get(seed))
                    future_to_job[fut] = (seed, swap)
                for fut in concurrent.futures.as_completed(future_to_job):
                    seed, swap = future_to_job[fut]
                    if seed in errored_seeds:
                        continue
                    try:
                        rewards, seat_metrics = fut.result()
                    except Exception as e:  # per-future try/except — one bad seed doesn't kill the pool
                        errored_seeds.add(seed)
                        partial.pop(seed, None)
                        err_row = {"seed": seed, "error": repr(e)}
                        computed[seed] = err_row
                        _persist(err_row)
                        continue
                    partial.setdefault(seed, {})[swap] = (rewards, seat_metrics)
                    needed = {False, True} if both_seats else {False}
                    if not needed <= partial[seed].keys():
                        continue
                    rewards0, metrics0 = partial[seed][False]
                    orientation0 = {"layout": "A@0/B@1", "bank_a": rewards0[0], "bank_b": rewards0[1]}
                    if metrics:
                        _attach_metric_fields(orientation0, metrics0, a_seat=0, b_seat=1)
                    orientations = [orientation0]
                    if both_seats:
                        rewards1, metrics1 = partial[seed][True]
                        orientation1 = {"layout": "B@0/A@1", "bank_a": rewards1[1], "bank_b": rewards1[0]}
                        if metrics:
                            _attach_metric_fields(orientation1, metrics1, a_seat=1, b_seat=0)
                        orientations.append(orientation1)
                    row = _finalize(seed, orientations)
                    computed[seed] = row
                    _persist(row)
                    del partial[seed]
        except Exception as e:
            # review.md M9: a pool-level failure (e.g. BrokenProcessPool from OOM during
            # submit) used to propagate straight out of compare() and lose every in-memory
            # result. H6 already persists each seed as soon as its orientation(s) land, so the
            # only gap left is whatever never got that far — record those explicitly instead of
            # losing the whole run silently.
            already_done = sum(1 for seed in pending_seeds if seed in computed)
            _warn(
                f"compare(): worker pool failed ({e!r}) — {already_done}/{len(pending_seeds)} "
                "pending seeds had already completed and were persisted; the rest are recorded "
                "as errored."
            )
            for seed in pending_seeds:
                if seed not in computed:
                    err_row = {"seed": seed, "error": f"pool failure: {e!r}"}
                    computed[seed] = err_row
                    _persist(err_row)
    else:
        for seed in pending_seeds:
            try:
                orientations = []
                # Both orientations of this seed inside ONE `with`: the pin has to be identical
                # across the two arms, or the comparison is between two different towns —
                # exactly the failure §Β.0′ exists to remove.
                with pinned_town(town_pin, town_schedules.get(seed)):
                    r_a0 = play(agent_a, agent_b, seed, steps=steps, run_dir=run_dir, record=record,
                                strict=strict, metrics=metrics)
                    if both_seats:
                        r_b0 = play(agent_b, agent_a, seed, steps=steps, run_dir=run_dir,
                                    record=record, strict=strict, metrics=metrics)
                orientation0 = {
                    "layout": "A@0/B@1",
                    "bank_a": r_a0.rewards[0],
                    "bank_b": r_a0.rewards[1],
                }
                if metrics:
                    _attach_metric_fields(orientation0, r_a0.metrics, a_seat=0, b_seat=1)
                orientations.append(orientation0)

                if both_seats:
                    orientation1 = {
                        "layout": "B@0/A@1",
                        "bank_a": r_b0.rewards[1],
                        "bank_b": r_b0.rewards[0],
                    }
                    if metrics:
                        _attach_metric_fields(orientation1, r_b0.metrics, a_seat=1, b_seat=0)
                    orientations.append(orientation1)

                row = _finalize(seed, orientations)
                computed[seed] = row
                _persist(row)
            except Exception as e:
                err_row = {"seed": seed, "error": repr(e)}
                computed[seed] = err_row
                _persist(err_row)

    # Sorted by seed regardless of completion order: future completion
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
    # review.md L8: NaN isn't valid JSON — kept as float("nan") for the n>1-only arithmetic
    # below (significant/ci95), reported as None on CompareResult instead.
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
        # review_89d99f0_2026-08-05.md M3: a degenerate CI (n=1, or se_diff==0 with n>1) let a single lucky seed
        # or a coincidentally-constant diff pass as NON_INFERIOR with no statistical basis.
        # review.md H2: an entirely-negative CI (confirmed regression, just a small one) is a
        # different claim from a CI straddling zero (genuine equivalence) — split it out as
        # WITHIN_MARGIN so it can never silently read as "didn't get worse".
        verdict = "WITHIN_MARGIN" if ci95[1] < 0 else "NON_INFERIOR"
    else:
        verdict = "INCONCLUSIVE"

    wins_a = sum(1 for row in per_seed if row["winner"] == "a")
    wins_b = sum(1 for row in per_seed if row["winner"] == "b")
    ties = sum(1 for row in per_seed if row["winner"] == "tie")
    # review.md H2: a paired-seed sign test — independent of the $-magnitude verdict above —
    # catches a directionally-consistent regression (e.g. 5/43 wins) that nets under the
    # margin. wins_a/wins_b (not episode_wins_*) since those are the actual paired trials.
    sign_trials = wins_a + wins_b
    sign_test_p = _sign_test_p(min(wins_a, wins_b), sign_trials) if sign_trials else None
    sign_test_blocks_go = bool(
        sign_test_p is not None and wins_b > wins_a and sign_test_p < 0.01 and not accept_within_margin
    )
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

    if metrics:
        water_weeds_lost_a = sum(row["water_weeds_lost_a"] for row in per_seed)
        plant_decay_units_lost_a = sum(row["plant_decay_units_lost_a"] for row in per_seed)
        animals_escaped_a = sum(row.get("animals_escaped_a", 0) for row in per_seed)
        clipped_production_ticks_a = sum(row.get("clipped_production_ticks_a", 0) for row in per_seed)
        # review.md M1: shed_overflow_burnt/weeds_lost are hard gates (same pattern as the four
        # above); units_sold_at_or_below_5 is a budget against total sales, not a ==0 gate,
        # since some floor-price selling is expected. review.md M11: market_sim_aborted means
        # these metrics themselves are incomplete for at least one episode — fail the gate.
        shed_overflow_burnt_a = sum(row.get("shed_overflow_burnt_a", 0) for row in per_seed)
        weeds_lost_a = sum(row.get("weeds_lost_a", 0) for row in per_seed)
        unexpected_weeds_lost_a = sum(
            row.get("unexpected_weeds_lost_a", 0) for row in per_seed
        )
        units_sold_at_or_below_5_a = sum(row.get("units_sold_at_or_below_5_a", 0) for row in per_seed)
        sales_count_a = sum(row.get("sales_count_a", 0) for row in per_seed)
        noop_rows = [row.get("unexplained_noops_a") for row in per_seed]
        unexplained_noops_a = None if any(v is None for v in noop_rows) else sum(noop_rows)
        market_sim_aborted_a = any(row.get("market_sim_aborted_a", False) for row in per_seed)
        v1k_diagnostics = {
            f"{metric}_{arm}": sum(
                row.get(f"{metric}_{arm}", 0) for row in per_seed
            )
            for metric in _V1K_REPORT_METRICS
            for arm in ("a", "b")
        }
        for arm in ("a", "b"):
            for product in _V1K_REPORT_PRODUCTS:
                key = product.lower()
                v1k_diagnostics[f"{key}_units_{arm}"] = sum(
                    row.get(f"{key}_units_{arm}", 0) for row in per_seed
                )
                v1k_diagnostics[f"{key}_revenue_{arm}"] = sum(
                    row.get(f"{key}_revenue_{arm}", 0) for row in per_seed
                )
        arm_b_counters = {
            f"{metric}_b": sum(row.get(f"{metric}_b", 0) or 0 for row in per_seed)
            for metric in _ARM_B_COUNTER_METRICS
        }
        # S10 P2.3: fold across seeds, same rule (counts sum, peaks max).
        s10_diff_counters = _aggregate_s10_counters(per_seed)
        units_sold_budget_ok = (
            sales_count_a == 0 or (units_sold_at_or_below_5_a / sales_count_a) <= 0.02
        )
        # Απόφαση Α. Structural faults first — no price applies to these.
        structural_ok = (
            plant_decay_units_lost_a == 0
            and clipped_production_ticks_a == 0
            and units_sold_budget_ok
            and (unexplained_noops_a is None or unexplained_noops_a == 0)
            and not market_sim_aborted_a
        )
        priced_counts = {
            "animals_escaped": animals_escaped_a,
            "shed_overflow_burnt": shed_overflow_burnt_a,
            "unexpected_weeds_lost": unexpected_weeds_lost_a,
            "water_weeds_lost": water_weeds_lost_a,
        }
        priced_counts_b = {
            metric: arm_b_counters[f"{metric}_b"] for metric in PRICED_SOURCE_METRICS
        }
        priced_loss_per_episode, priced_loss_breakdown = priced_metric_loss(
            priced_counts, len(raw_orientations)
        )
        priced_loss_b_value, priced_loss_breakdown_b = priced_metric_loss(
            priced_counts_b, len(raw_orientations)
        )
        priced_loss_delta_value = priced_loss_delta(
            priced_loss_per_episode, priced_loss_b_value
        )
        priced_loss_budget_used = priced_loss_budget(mean_diff)
        declared = {
            metric: text
            for metric, text in (metric_mechanisms or {}).items()
            if str(text).strip()
        }
        # Deliberately agent_a's counters only, and deliberately *not* relaxed by Δ: pricing —
        # differenced or absolute — buys tolerance for understood loss, never for unexplained
        # loss. This is what still rejects v1m Δ3's 28 escapes (Απόφαση Δ point 2).
        unexplained_metrics = tuple(
            metric for metric, count in sorted(priced_counts.items())
            if (count or 0) > 0 and metric not in declared
        )
        # Απόφαση Δ point 3: the priced budget is an *acceptance* instrument. In a mirror
        # (role="regression") the $-verdict and the structural leg are the whole gate — a
        # market-only fix correctly measures ~0 there, which under Α made the budget ~$6 and
        # the gate mathematically unreachable (memory.md 2026-08-10 (ι)).
        # 1e-9 absorbs float division only; it is far below one cent per episode.
        priced_leg_ok = arm_role == "regression" or (
            priced_loss_delta_value <= priced_loss_budget_used + 1e-9
        )
        metric_gate_passed = structural_ok and not unexplained_metrics and priced_leg_ok
    else:
        water_weeds_lost_a = plant_decay_units_lost_a = None
        animals_escaped_a = clipped_production_ticks_a = None
        shed_overflow_burnt_a = weeds_lost_a = unexpected_weeds_lost_a = None
        units_sold_at_or_below_5_a = None
        sales_count_a = unexplained_noops_a = None
        market_sim_aborted_a = None
        priced_loss_per_episode = priced_loss_budget_used = None
        priced_loss_b_value = priced_loss_delta_value = None
        priced_loss_breakdown = {}
        priced_loss_breakdown_b = {}
        declared = {}
        unexplained_metrics = ()
        metric_gate_passed = None
        arm_b_counters = {f"{metric}_b": None for metric in _ARM_B_COUNTER_METRICS}
        s10_diff_counters = {
            f"{metric}_{suf}": None
            for metric in _S10_DIFFERENTIAL_METRICS for suf in ("a", "b", "delta")
        }
        v1k_diagnostics = {
            f"{metric}_{arm}": None
            for metric in _V1K_REPORT_METRICS
            for arm in ("a", "b")
        }
        for arm in ("a", "b"):
            for product in _V1K_REPORT_PRODUCTS:
                key = product.lower()
                v1k_diagnostics[f"{key}_units_{arm}"] = None
                v1k_diagnostics[f"{key}_revenue_{arm}"] = None

    # A GO is only real from stage="holdout-confirm", with a directional
    # verdict, AND the metric gate having actually run and passed — an unmeasured metric
    # gate must never silently count as passed. review.md H2: WITHIN_MARGIN (a confirmed
    # regression under the margin) only counts toward go with an explicit override, same as
    # a sign-test-confirmed regression.
    verdict_allows_go = verdict in ("IMPROVED", "NON_INFERIOR") or (
        verdict == "WITHIN_MARGIN" and accept_within_margin
    )
    go = bool(
        stage == "holdout-confirm"
        and verdict_allows_go
        and prior_dev_screen_found
        and both_seats
        and town_pin is None
        and metrics
        and metric_gate_passed
        and not sign_test_blocks_go
    )

    # Only a measured, complete confirm consumes the one-shot ledger slot. An unmetered or
    # incomplete diagnostic is not evidence for acceptance and must not block the real gate.
    if stage == "holdout-confirm" and metrics and not incomplete:
        _append_confirm_ledger(ledger_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_a_fp": code_fingerprints[0],
            "agent_b_fp": code_fingerprints[1],
            "seed_set_name": seed_set_name,
            "town_pin": town_pin,  # §Β.0′: a pinned confirm must be legible as such in the ledger
            "arm_role": arm_role,  # §1 Δ: which gate regime this confirm was judged under
            "both_seats": both_seats,
            "metrics": metrics,
            "incomplete": incomplete,
            "counted_look": True,
            "prior_dev_screen_found": prior_dev_screen_found,
            "verdict": verdict,
            "go": go,
            "repeat_confirm_index": repeat_confirm_index,
        })

    return CompareResult(
        per_seed=per_seed,
        errors=errors,
        mean_diff=mean_diff,
        se_diff=se_diff,
        n_effective=n,
        t_crit=t_crit if n > 1 else None,
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
        sign_test_p=sign_test_p,
        verdict=verdict,
        incomplete=incomplete,
        code_fingerprints=code_fingerprints,
        stage=stage,
        town_pin=town_pin,
        town_schedules={str(seed): schedule for seed, schedule in town_schedules.items()},
        metrics_checked=metrics,
        water_weeds_lost_a=water_weeds_lost_a,
        plant_decay_units_lost_a=plant_decay_units_lost_a,
        animals_escaped_a=animals_escaped_a,
        clipped_production_ticks_a=clipped_production_ticks_a,
        shed_overflow_burnt_a=shed_overflow_burnt_a,
        weeds_lost_a=weeds_lost_a,
        unexpected_weeds_lost_a=unexpected_weeds_lost_a,
        units_sold_at_or_below_5_a=units_sold_at_or_below_5_a,
        sales_count_a=sales_count_a,
        unexplained_noops_a=unexplained_noops_a,
        market_sim_aborted_a=market_sim_aborted_a,
        **arm_b_counters,
        **s10_diff_counters,
        **v1k_diagnostics,
        priced_loss_per_episode=priced_loss_per_episode,
        priced_loss_b=priced_loss_b_value,
        priced_loss_delta=priced_loss_delta_value,
        priced_loss_budget_used=priced_loss_budget_used,
        priced_loss_breakdown=priced_loss_breakdown,
        priced_loss_breakdown_b=priced_loss_breakdown_b,
        arm_role=arm_role,
        metric_mechanisms=dict(declared),
        unexplained_metrics=unexplained_metrics,
        metric_gate_passed=metric_gate_passed,
        prior_dev_screen_found=prior_dev_screen_found,
        min_effect_used=effective_min_effect,
        non_inferiority_margin_used=effective_non_inferiority_margin,
        go=go,
        repeat_confirm_index=repeat_confirm_index,
        agent_a_spec=_agent_spec_label(agent_a),
        agent_b_spec=_agent_spec_label(agent_b),
        seed_set_name=seed_set_name,
        harness_git_sha=_harness_git_sha(),
        platform=platform_module.platform(),
        python_version=platform_module.python_version(),
        env=env_snapshot,
        warnings=collected_warnings,
    )
