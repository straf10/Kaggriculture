#!/usr/bin/env python3
"""S10 P1 — the replay bench (Instrument A framework, reusable).

Every ladder episode of a live submission is a `(seed, teams, seat_0_stream,
seat_1_stream, recorded_rewards)` tuple.  A *bench* run recomposes that episode
in `harness.play.play`:

  α-control (P1.2):    both seats are `make_tape_agent(<recorded stream>)`.
                        The engine is deterministic given seed+actions; the
                        replay must reproduce the recorded rewards bit-exactly.
                        Death if <95% bit-exact.
  H2 calibration (P1.4): candidate seat runs `agent.tape_overlay.TapeOverlay`
                        in `mode="liquidate"` with the frozen H2 parameters
                        (F=25, first_day=22, h_max=12, d_days=4, force_step=686);
                        opponent seat is a tape.  The overlay is imported
                        read-only — no `agent/` change is made here.
  Recovery calibration (S16 §2.1/§2.3): candidate seat runs `TapeOverlay` in
                        `mode="augment"` with the shipped 55675634 params
                        (RECOVERY_PARAMS — market pull-forward + tile recovery).
                        UNLIKE H2 this is an occupancy arm: tile recovery
                        changes farmer/hand actions, which re-rolls the shop-
                        unlock RNG for both farms while the opponent tape stays
                        fixed — a bias FOR this arm, quantified (not corrected)
                        by `recovery_alpha_bias` and reported alongside the gate.

  Base arm, both calibrations (S16 task 1, corrected 2026-08-28): the base is the
                        BARE reconstruction stream replayed via `make_tape_agent`, not
                        each episode's own recorded reward and not that episode's own
                        recorded action stream. For 55675634, the recorded stream already
                        carries the shipped overlay's output — wrapping it in a fresh
                        overlay finds nothing left to fix and silently compares the
                        recovery arm to itself. See the comment above
                        `RECONSTRUCTION_PATH` below for the full mechanism and the
                        `bare_base_correctness_check` field every output now carries.

The bench is INSTRUMENT A, not the seed harness.  Live seeds must NOT enter
`harness/seeds.py::NAMED_SEED_SETS` (plan §P1.7) — they would corrupt the
screen→confirm ledger semantics.  Bench inputs are (episode, seed) pairs
loaded from `data/archive/raw/live_<sub>/`, never from `--seed-set`.

Zero foresight (plan §P1.1):  the candidate reads only the current `obs` — no
peek at recorded post-state, no read of the opponent's stream.  The
`TapeOverlay` obeys that contract by construction (its inputs are seat-local).

Manifest (P1.3):  `data/derived/s10_bench_manifest.json` — per episode, the
seed, our seat, opponent, and (if resolvable) opponent's public-board rank/
score.  Written once by `manifest`; the calibration outputs join on
`episode_id`.

CLI:
    python analysis/s10_replay_bench.py manifest [<sub> ...]
    python analysis/s10_replay_bench.py alpha [<sub> ...]           # P1.2
    python analysis/s10_replay_bench.py h2_calibration              # P1.4 (55586926+55675634)
    python analysis/s10_replay_bench.py recovery_calibration        # S16 §2.3 (55586926+55675634)
    python analysis/s10_replay_bench.py recovery_alpha_bias         # S16 §2.2 (all live subs)

Workers are pinned at 4 (plan §Πάγιοι Κανόνες 5), overridable via
`S10_BENCH_WORKERS`.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine_reference"))

from analysis.s8_replay_io import (SUBMISSIONS, ladder_episodes, load,  # noqa: E402
                                    meta, replay_paths, our_seat)
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}

# P1.5 — the constraint every bench report must carry, in the report itself and not only
# in this file. Tape opponents replay a fixed action stream: they do not react. For a timing
# change the price coupling is therefore reproduced to FIRST ORDER only (their orders stay
# fixed, the prices those orders meet do move). That is enough to screen a candidate; it is
# not proof.
BENCH_CONSTRAINT = (
    "Tape opponents do not react. Their action streams are fixed, so a timing change is "
    "priced to FIRST ORDER only: their orders stay put and only the prices those orders "
    "meet move. Sufficient for a screen; NOT a proof."
)

# S16 task 6 — the market-only constraint above assumes a market-only arm: the town is
# bit-identical, so "their orders stay put and only the prices those orders meet move" is
# the right frame. An OCCUPANCY arm (recovery_calibration, recovery_alpha_bias) does not
# just fail to react to a price shift — ROADMAP §3.1 rule 1 (corrected) means changing which
# tiles are occupied re-rolls the shared per-day RNG's remaining shop-unlock draws for BOTH
# farms, so the town itself diverges. The opponent's fixed tape then plays out in a town
# that no longer exists, not merely against orders it can't respond to. Stronger and
# different in kind from the market-only constraint, not a variant of it.
OCCUPANCY_BENCH_CONSTRAINT = (
    "The candidate seat is an occupancy arm: it changes which tiles are None on our farm, "
    "which re-rolls the shared per-day RNG's remaining shop-unlock draws for BOTH farms "
    "(ROADMAP §3.1 rule 1). The recorded opponent tape is not just static against a price "
    "shift it can't react to — it is replaying a town that has diverged from the one it was "
    "recorded in. Quantified, not corrected, by recovery_fires / the alpha-bias bit-exact "
    "share; never tuned toward zero. Sufficient for a screen; NOT a proof."
)
DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)
DEFAULT_WORKERS = int(os.environ.get("S10_BENCH_WORKERS", "4"))

# P3.3: same semantics as gates/confirm_log.jsonl — one line per bench "look" so
# repeated tuning-driven readings of the confirm set are visible in git.
BENCH_LEDGER = ROOT / "gates" / "s10_bench_ledger.jsonl"


def _append_bench_ledger(entry: dict) -> None:
    BENCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with BENCH_LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")

# H2 frozen parameters — must match agent/tape_overlay.py defaults exactly.
H2_PARAMS = dict(mode="liquidate", liq_floor_price=25, liq_first_day=22,
                 liq_h_max=12, liq_d_days=4, liq_force_step=686)

# S16 §2.1 — the shipped 55675634 overlay (market augment + tile recovery), pinned
# explicitly to match TapeOverlay's defaults AND analysis/build_tape_overlay_submission.py's
# MAIN_TEMPLATE constants (test_s16_recovery_bit_equivalence.py asserts the two agree).
RECOVERY_PARAMS = dict(mode="augment", shed_guard=90, liquidate_step=690,
                       overlay_products=("STRAWBERRY",), pull_forward_before_step=336)

# P3.3: screen/confirm split.  Screen = 55726984 (the current-generation
# submission whose stream is H2-augmented already — cannot be used for H2
# calibration).  Confirm = 55586926 + 55675634 (412 eps, plan §P1.4 dataset).
SCREEN_SUBS = ("55726984",)
CONFIRM_SUBS = ("55586926", "55675634")

# S16 task 1 (2026-08-28 correction) — ONE base for every arm.  `55675634`'s recorded
# per-episode stream (`streams[seat]` extracted from its own steps) is not the backbone:
# it already has tile recovery + market pull-forward baked in from having been PLAYED
# with the shipped overlay.  Wrapping that already-corrected stream in a fresh TapeOverlay
# finds nothing left to recover (0 fires on all 246 `55675634` confirm episodes) and
# reproduces the recorded reward trivially — the "recovery" arm was silently being
# compared to itself.  The correct base — for H2 *and* recovery alike — is the bare
# 719-action reconstruction (`data/derived/s6_step1_reconstruction_ReCurSiON.json`, the
# same stream `tests/test_s16_recovery_bit_equivalence.py` loads; both live submissions'
# descriptions carry `stream sha256 1d9e0efd…` against it), replayed via `make_tape_agent`
# with NO overlay as the base arm, and wrapped in `TapeOverlay(bare, **PARAMS)` as the
# candidate arm — for every episode of every confirm submission, not just 55586926's.
# On 55586926 episodes this changes nothing (55586926 IS the bare reconstruction with no
# overlay at all) — verified below via `bare_base_correctness_check`, not assumed.
# Constraint, same for every arm built this way: the opponent is still a fixed tape, and
# that tape was recorded against OUR overlay-equipped seat playing live — so replaying it
# against a bare-stream base or an overlay candidate is off by whatever the opponent would
# have done differently facing a different seat. That mismatch is symmetric across H2 and
# recovery (both now share the identical base and the identical opponent tape per episode),
# so it does not favour either arm over the other, unlike §2.2's occupancy bias below.
RECONSTRUCTION_PATH = ROOT / "data" / "derived" / "s6_step1_reconstruction_ReCurSiON.json"
_BARE_STREAM_CACHE = None


def _bare_stream():
    """The bare 719-action ReCurSiON reconstruction, no overlay. Cached per worker process
    (ProcessPoolExecutor forks/spawns fresh processes; each loads it at most once)."""
    global _BARE_STREAM_CACHE
    if _BARE_STREAM_CACHE is None:
        if not RECONSTRUCTION_PATH.exists():
            raise SystemExit(
                f"missing {RECONSTRUCTION_PATH} — h2_calibration and recovery_calibration "
                "both require the bare reconstruction stream as their shared base (S16 task 1)."
            )
        rec = json.loads(RECONSTRUCTION_PATH.read_text())
        _BARE_STREAM_CACHE = rec["stream"]
    return _BARE_STREAM_CACHE


def _extract_streams(steps):
    """Per-seat action stream indexed by obs["step"].  Mirrors
    `analysis/s9_h2_k10.py::_streams` and the alignment convention verified in
    `analysis/s8_replay_io.py` (stream[k] == steps[k+1][seat]["action"])."""
    return [[(steps[i + 1][seat].get("action") or dict(PASS))
             for i in range(len(steps) - 1)] for seat in (0, 1)]


# ---------------------------------------------------------------------------
# Job scheduling
# ---------------------------------------------------------------------------
# The full 55586926+55675634+55726984 corpus is ~500 replays x 5-30 MB.  Building
# a list of `(steps=...)` jobs pickles ~2-3 GB into worker queues and stalls the
# pool.  Workers load their replay from disk instead — jobs are just paths.
def _enum_jobs(submissions, limit=None):
    n = 0
    for sub in submissions:
        for p in replay_paths(sub):
            eid = int(p.name.split("-")[1])
            yield (sub, eid, str(p))
            n += 1
            if limit and n >= limit:
                return


def _load_meta_and_streams(path_str):
    d = load(Path(path_str))
    m = meta(d)
    return m


# ---------------------------------------------------------------------------
# α-control (P1.2)
# ---------------------------------------------------------------------------
def _alpha_one(job):
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    # Skip mirror/validation — the enumerator does not (it just walks disk); the
    # α/H2 semantics only make sense on ladder eps.  Same filter as
    # `ladder_episodes`.
    from analysis.s8_replay_io import is_excluded
    excl, _r = is_excluded(m)
    if excl:
        return None
    streams = _extract_streams(m["steps"])
    a = make_tape_agent(streams[0])
    b = make_tape_agent(streams[1])
    r = play(a, b, seed=m["seed"], record=False, metrics=False, strict=False)
    exact_0 = abs(float(r.rewards[0]) - float(m["rewards"][0])) < 1e-6
    exact_1 = abs(float(r.rewards[1]) - float(m["rewards"][1])) < 1e-6
    return dict(submission=sub, episode_id=eid, seed=m["seed"],
                teams=list(m["teams"]),
                recorded=[float(m["rewards"][0]), float(m["rewards"][1])],
                replayed=[float(r.rewards[0]), float(r.rewards[1])],
                bit_exact=(exact_0 and exact_1),
                bit_exact_seat0=exact_0, bit_exact_seat1=exact_1,
                clean=r.clean)


def run_alpha(submissions, workers=DEFAULT_WORKERS, limit=None):
    jobs = list(_enum_jobs(submissions, limit=limit))
    print(f"alpha: {len(jobs)} disk replays across {list(submissions)}, workers={workers}",
          flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_alpha_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    n = len(rows)
    exact = sum(1 for r in rows if r["bit_exact"])
    share = exact / max(n, 1)
    verdict = "PASSED" if share >= 0.99 else ("DEATH" if share < 0.95 else "WARN")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": f"alpha {verdict}: {exact}/{n} bit-exact ({share:.4f})",
        "constraint": BENCH_CONSTRAINT,
        "workers": workers,
        "n": n,
        "n_bit_exact": exact,
        "share_bit_exact": share,
        "submissions": list(submissions),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# H2 calibration (P1.4)
# ---------------------------------------------------------------------------
def _h2_one(job):
    # Deferred import in the worker — TapeOverlay pulls in agent.config which
    # touches package-level state; keeping it worker-local also lets us avoid
    # importing agent/ in the parent process.
    from agent.tape_overlay import TapeOverlay
    from analysis.s8_replay_io import is_excluded
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    excl, _r = is_excluded(m)
    if excl:
        return None
    seat = our_seat(m["teams"])
    if seat is None:
        return None
    streams = _extract_streams(m["steps"])
    opponent_agent = make_tape_agent(streams[1 - seat])
    bare = _bare_stream()
    # Base arm: the bare reconstruction, no overlay (S16 task 1) — NOT the recorded
    # reward and NOT this episode's own recorded stream (see the comment above
    # RECONSTRUCTION_PATH: for 55675634 that stream is already overlay-augmented).
    base_agent = make_tape_agent(bare)
    overlay = TapeOverlay(bare, **H2_PARAMS)
    if seat == 0:
        r_base = play(base_agent, opponent_agent, seed=m["seed"],
                       record=False, metrics=False, strict=False)
        r = play(overlay.act, opponent_agent, seed=m["seed"],
                  record=False, metrics=False, strict=False)
    else:
        r_base = play(opponent_agent, base_agent, seed=m["seed"],
                       record=False, metrics=False, strict=False)
        r = play(opponent_agent, overlay.act, seed=m["seed"],
                  record=False, metrics=False, strict=False)
    base_us = float(r_base.rewards[seat])
    base_opp = float(r_base.rewards[1 - seat])
    new_us = float(r.rewards[seat])
    new_opp = float(r.rewards[1 - seat])
    recorded_us = float(m["rewards"][seat])
    recorded_opp = float(m["rewards"][1 - seat])
    return dict(submission=sub, episode_id=eid, seed=m["seed"],
                seat=seat, opponent=m["teams"][1 - seat],
                base_us=base_us, base_opp=base_opp,
                new_us=new_us, new_opp=new_opp,
                base_win=base_us > base_opp,
                new_win=new_us > new_opp,
                d_bank=new_us - base_us,
                recorded_us=recorded_us, recorded_opp=recorded_opp,
                bare_equals_recorded=(abs(base_us - recorded_us) < 1e-6
                                       and abs(base_opp - recorded_opp) < 1e-6),
                clean=(r.clean and r_base.clean))


# ---------------------------------------------------------------------------
# Recovery calibration (S16 §2.1/§2.3) — the occupancy overlay, market-only H2's
# counterpart. Unlike H2, this arm changes farmer/hand actions, which the plan's §2
# warning says re-rolls tile occupancy and therefore the remaining shop-unlock RNG
# for BOTH farms — the bench is not neutral between the two arms, and that bias must
# be quantified (§2.2), never tuned away.
# ---------------------------------------------------------------------------
class _CountingOverlay:
    """Wraps TapeOverlay.act to count how many steps `_recover_tile_actions` actually
    changes an action (vs. how many it merely passes through), without duplicating its
    policy (plan §4 rule 2 / ROADMAP §3 'reuse, do not duplicate')."""

    def __init__(self, stream, **kwargs):
        from agent.tape_overlay import TapeOverlay
        self._overlay = TapeOverlay(stream, **kwargs)
        self.n_steps = 0
        self.n_fires = 0
        orig = TapeOverlay._recover_tile_actions

        def _counting_recover(snapshot, farmer_a, hands_a):
            self.n_steps += 1
            before = [list(farmer_a)] + [list(h) for h in hands_a]
            new_farmer, new_hands = orig(snapshot, farmer_a, hands_a)
            after = [list(new_farmer)] + [list(h) for h in new_hands]
            if before != after:
                self.n_fires += 1
            return new_farmer, new_hands

        self._overlay._recover_tile_actions = _counting_recover

    @property
    def act(self):
        return self._overlay.act


def _recovery_one(job):
    from analysis.s8_replay_io import is_excluded
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    excl, _r = is_excluded(m)
    if excl:
        return None
    seat = our_seat(m["teams"])
    if seat is None:
        return None
    streams = _extract_streams(m["steps"])
    opponent_agent = make_tape_agent(streams[1 - seat])
    bare = _bare_stream()
    # Base arm: the bare reconstruction, no overlay (S16 task 1) — same base H2 uses, so
    # both arms are read against an identical, non-overlay-contaminated backbone. Feeding
    # this episode's OWN recorded stream to the overlay (the pre-fix behaviour) is what
    # produced 55675634's 246/246 zero-fire, 0/246 d_bank!=0 result: that stream is already
    # the shipped overlay's own output, so recovery found nothing left to recover.
    base_agent = make_tape_agent(bare)
    overlay = _CountingOverlay(bare, **RECOVERY_PARAMS)
    if seat == 0:
        r_base = play(base_agent, opponent_agent, seed=m["seed"],
                       record=False, metrics=False, strict=False)
        r = play(overlay.act, opponent_agent, seed=m["seed"],
                  record=False, metrics=False, strict=False)
    else:
        r_base = play(opponent_agent, base_agent, seed=m["seed"],
                       record=False, metrics=False, strict=False)
        r = play(opponent_agent, overlay.act, seed=m["seed"],
                  record=False, metrics=False, strict=False)
    base_us = float(r_base.rewards[seat])
    base_opp = float(r_base.rewards[1 - seat])
    new_us = float(r.rewards[seat])
    new_opp = float(r.rewards[1 - seat])
    recorded_us = float(m["rewards"][seat])
    recorded_opp = float(m["rewards"][1 - seat])
    return dict(submission=sub, episode_id=eid, seed=m["seed"],
                seat=seat, opponent=m["teams"][1 - seat],
                base_us=base_us, base_opp=base_opp,
                new_us=new_us, new_opp=new_opp,
                base_win=base_us > base_opp,
                new_win=new_us > new_opp,
                d_bank=new_us - base_us,
                n_steps=overlay._overlay.n,
                n_recovery_fires=overlay.n_fires,
                recorded_us=recorded_us, recorded_opp=recorded_opp,
                bare_equals_recorded=(abs(base_us - recorded_us) < 1e-6
                                       and abs(base_opp - recorded_opp) < 1e-6),
                clean=(r.clean and r_base.clean))


def run_recovery_calibration(workers=DEFAULT_WORKERS, limit=None):
    jobs = list(_enum_jobs(CONFIRM_SUBS, limit=limit))
    print(f"recovery_calibration: {len(jobs)} disk replays (confirm={CONFIRM_SUBS}), "
          f"workers={workers}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_recovery_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    base_w = sum(1 for r in rows if r["base_win"])
    base_l = len(rows) - base_w
    new_w = sum(1 for r in rows if r["new_win"])
    new_l = len(rows) - new_w
    c = sum(1 for r in rows if (not r["base_win"]) and r["new_win"])
    b = sum(1 for r in rows if r["base_win"] and (not r["new_win"]))
    p = _mcnemar_binomial_p(b, c)
    same_direction = (c > 0) and (b == 0)
    significant = p < 0.001
    if same_direction and significant:
        verdict_txt = "PASSED"
    elif b > c or not significant:
        verdict_txt = "DEATH"
    else:
        verdict_txt = "WARN"

    # Per-seat McNemar — plan §2.3 asks for this explicitly, not only the pooled figure.
    by_seat_mcnemar = {}
    for seat in (0, 1):
        srows = [r for r in rows if r["seat"] == seat]
        sc = sum(1 for r in srows if (not r["base_win"]) and r["new_win"])
        sb = sum(1 for r in srows if r["base_win"] and (not r["new_win"]))
        by_seat_mcnemar[str(seat)] = {
            "n": len(srows), "c": sc, "b": sb, "p": _mcnemar_binomial_p(sb, sc),
        }

    fires = [r["n_recovery_fires"] for r in rows]
    import statistics as _stats
    bare_check = _bare_base_correctness_check(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"recovery_calibration {verdict_txt}: base {base_w}-{base_l} "
                    f"→ new {new_w}-{new_l}; McNemar c={c} b={b} p={p:.2e}"),
        "constraint": OCCUPANCY_BENCH_CONSTRAINT,
        "bare_base_correctness_check": bare_check,
        "occupancy_bias_warning": (
            "This arm changes farmer/hand tile actions, which re-rolls the remaining "
            "shop-unlock RNG for BOTH farms (plan §2 preamble). The recorded opponent tape "
            "stays fixed while the town it was recorded against no longer exists once "
            "recovery fires. The bias runs IN FAVOUR of this arm and is not corrected here "
            "— see recovery_fires below and s16_bench_three_arm.json's §2.2 quantification."
        ),
        "workers": workers,
        "n": len(rows),
        "confirm_subs": list(CONFIRM_SUBS),
        "recovery_params": RECOVERY_PARAMS,
        "base_wins": base_w, "base_losses": base_l,
        "new_wins": new_w, "new_losses": new_l,
        "mcnemar_c": c, "mcnemar_b": b, "mcnemar_p": p,
        "mcnemar_by_seat": by_seat_mcnemar,
        "same_direction_and_significant": (same_direction and p < 0.001),
        "recovery_fires": {
            "median_per_episode": _stats.median(fires) if fires else None,
            "total": sum(fires),
            "n_episodes_with_zero_fires": sum(1 for f in fires if f == 0),
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Recovery alpha-bias (S16 §2.2) — how much does the recorded reward diverge once
# recovery is active on OUR seat only, in the alpha-control (both-tape) setting?
# A large divergence is the EXPECTED, correct behaviour of an occupancy arm (it is
# not a bug and must not be tuned away) — this measures its size as the error bar
# the three-arm gate (§2.3/§2.4) must be read against.
# ---------------------------------------------------------------------------
def _recovery_alpha_one(job):
    from analysis.s8_replay_io import is_excluded
    sub, eid, path = job
    m = _load_meta_and_streams(path)
    excl, _r = is_excluded(m)
    if excl:
        return None
    streams = _extract_streams(m["steps"])
    seat = our_seat(m["teams"])
    if seat is None:
        return None
    overlay = _CountingOverlay(streams[seat], **RECOVERY_PARAMS)
    if seat == 0:
        a, b = overlay.act, make_tape_agent(streams[1])
    else:
        a, b = make_tape_agent(streams[0]), overlay.act
    r = play(a, b, seed=m["seed"], record=False, metrics=False, strict=False)
    exact_0 = abs(float(r.rewards[0]) - float(m["rewards"][0])) < 1e-6
    exact_1 = abs(float(r.rewards[1]) - float(m["rewards"][1])) < 1e-6
    return dict(submission=sub, episode_id=eid, seed=m["seed"], seat=seat,
                teams=list(m["teams"]),
                recorded=[float(m["rewards"][0]), float(m["rewards"][1])],
                replayed=[float(r.rewards[0]), float(r.rewards[1])],
                bit_exact=(exact_0 and exact_1),
                n_recovery_fires=overlay.n_fires,
                clean=r.clean)


def run_recovery_alpha_bias(workers=DEFAULT_WORKERS, limit=None):
    """Same corpus as alpha (all live submissions, P1.2), but with recovery active
    on our seat only. Unlike alpha, bit-exactness is NOT expected — this measures the
    divergence rate, not a gate."""
    subs = tuple(SUBMISSIONS.keys())
    jobs = list(_enum_jobs(subs, limit=limit))
    print(f"recovery_alpha_bias: {len(jobs)} disk replays across {subs}, workers={workers}",
          flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_recovery_alpha_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    n = len(rows)
    exact = sum(1 for r in rows if r["bit_exact"])
    share = exact / max(n, 1)
    fired = sum(1 for r in rows if r["n_recovery_fires"] > 0)
    # S16 task 3 — the informative rate is bit-exact-AMONG-episodes-that-fired, not
    # bit-exact-overall. 55675634's 246 confirm-set episodes fire ZERO times against
    # `streams[seat]` here (see s10_bench_recovery_calibration.json before the task-1 fix):
    # those are bit-exact BY DEFINITION (recovery had nothing to touch), not evidence the
    # arm is well-behaved. Folding them into the numerator inflates 68,1% to a misleading
    # 79,4%. This report's `share_bit_exact` is retained for continuity with prior runs but
    # is NOT the number to read; `share_fired_and_bit_exact` is.
    fired_and_exact = sum(1 for r in rows if r["n_recovery_fires"] > 0 and r["bit_exact"])
    zero_fire_and_exact = sum(1 for r in rows if r["n_recovery_fires"] == 0 and r["bit_exact"])
    share_fired_and_exact = fired_and_exact / max(fired, 1)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"recovery_alpha_bias: {exact}/{n} still bit-exact ({share:.4f}) overall "
                    f"once recovery is active on our seat only, but {zero_fire_and_exact}/{exact} "
                    "of those never fired at all (bit-exact by definition, not a signal). Among "
                    f"the {fired}/{n} episodes that DID fire, only {fired_and_exact}/{fired} "
                    f"({share_fired_and_exact:.4f}) stayed bit-exact — that is the number this "
                    "arm's error bar should be read against, not the inflated overall share. "
                    "Non-bit-exactness here is the EXPECTED signature of an occupancy arm "
                    "(plan §2.2), not a failure — do not tune it toward 1.0."),
        "constraint": OCCUPANCY_BENCH_CONSTRAINT,
        "workers": workers,
        "n": n,
        "n_bit_exact": exact,
        "share_bit_exact": share,
        "n_fired": fired,
        "n_fired_and_bit_exact": fired_and_exact,
        "share_fired_and_bit_exact": share_fired_and_exact,
        "n_zero_fire_and_bit_exact_by_definition": zero_fire_and_exact,
        "n_episodes_recovery_fired": fired,
        "submissions": list(subs),
        "recovery_params": RECOVERY_PARAMS,
        "rows": rows,
    }


def _bare_base_correctness_check(rows):
    """S16 task 1 correctness invariant: 55586926 carries no overlay at all, so it IS the
    bare reconstruction — replaying the bare stream (this job's new base arm) against its
    recorded opponent tape must reproduce its own recorded reward exactly. Checked, not
    assumed; a non-zero mismatch count means the base-arm change has a bug."""
    checked = [r for r in rows if r["submission"] == "55586926"]
    mismatches = [r["episode_id"] for r in checked if not r["bare_equals_recorded"]]
    return {
        "submission_checked": "55586926",
        "n_checked": len(checked),
        "n_mismatches": len(mismatches),
        "mismatch_episode_ids": mismatches[:20],
    }


def _mcnemar_binomial_p(b, c):
    """Two-sided exact binomial McNemar test.  For b + c ≤ 1000 use scipy-free
    Clopper–Pearson-style two-sided binomial.  For small b (0-5) and any c the
    exact tail is closed-form."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    # Two-sided p = 2 * P(X ≤ m | X ~ Binom(n, 0.5)), capped at 1.
    tail = sum(comb(n, k) for k in range(m + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def run_h2_calibration(workers=DEFAULT_WORKERS, limit=None):
    jobs = list(_enum_jobs(CONFIRM_SUBS, limit=limit))
    print(f"h2_calibration: {len(jobs)} disk replays (confirm={CONFIRM_SUBS}), "
          f"workers={workers}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, row in enumerate(ex.map(_h2_one, jobs, chunksize=1), 1):
            if row is not None:
                rows.append(row)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    base_w = sum(1 for r in rows if r["base_win"])
    base_l = len(rows) - base_w
    new_w = sum(1 for r in rows if r["new_win"])
    new_l = len(rows) - new_w
    # McNemar: c = base_loss → new_win (flipped to a win), b = base_win → new_loss.
    c = sum(1 for r in rows if (not r["base_win"]) and r["new_win"])
    b = sum(1 for r in rows if r["base_win"] and (not r["new_win"]))
    p = _mcnemar_binomial_p(b, c)
    # Same-direction check: recorded 232-180 → 255-157 in the s9-phase2-gate memory.
    same_direction = (c > 0) and (b == 0)
    # Plan §P1.4 draws two separate lines and they must not be collapsed:
    #   acceptance = c > 0 AND b == 0 AND p < 0,001
    #   death      = b > c  OR  not significant
    # A result like b=1, c=30, p≈1e-8 fails acceptance but is nowhere near death — calling
    # that DEATH would retire a working bench on a good reading.
    significant = p < 0.001
    if same_direction and significant:
        verdict_txt = "PASSED"
    elif b > c or not significant:
        verdict_txt = "DEATH"
    else:
        verdict_txt = "WARN"
    bare_check = _bare_base_correctness_check(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": (f"h2_calibration {verdict_txt}: base {base_w}-{base_l} "
                    f"→ new {new_w}-{new_l}; McNemar c={c} b={b} p={p:.2e}"),
        "constraint": BENCH_CONSTRAINT,
        "bare_base_correctness_check": bare_check,
        "workers": workers,
        "n": len(rows),
        "confirm_subs": list(CONFIRM_SUBS),
        "h2_params": H2_PARAMS,
        "base_wins": base_w, "base_losses": base_l,
        "new_wins": new_w, "new_losses": new_l,
        "mcnemar_c": c, "mcnemar_b": b, "mcnemar_p": p,
        "same_direction_and_significant": (same_direction and p < 0.001),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Manifest (P1.3)
# ---------------------------------------------------------------------------
def build_manifest(submissions):
    from analysis.board_join import board_at, episode_times, rating_zone

    ep_times = {}
    for sub in submissions:
        ep_times[sub] = episode_times(sub)

    rows = []
    n_unmatched = 0
    for sub in submissions:
        times = ep_times[sub]
        for eid, m in ladder_episodes(sub):
            seat = our_seat(m["teams"])
            opp = m["teams"][1 - seat] if seat is not None else None
            ep_time = times.get(eid)
            board = board_at(ep_time) if ep_time else {}
            opp_entry = board.get(opp) if opp else None
            if opp_entry is not None:
                opp_rank, opp_score, opp_last_sub = opp_entry
                controlled = opp_last_sub <= ep_time if ep_time else None
                last_sub_str = opp_last_sub.isoformat() if opp_last_sub else None
            else:
                opp_rank, opp_score, last_sub_str, controlled = None, None, None, None
                n_unmatched += 1
            rows.append({
                "submission": sub,
                "episode_id": eid,
                "seed": m["seed"],
                "our_seat": seat,
                "opponent": opp,
                "board_score": opp_score,
                "board_rank": opp_rank,
                "last_submission_date": last_sub_str,
                "controlled": controlled,
                "rating_zone": rating_zone(opp_score),
            })
    n_matched = len(rows) - n_unmatched
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": f"manifest {len(rows)} rows, {n_matched} matched, {n_unmatched} unmatched",
        "constraint": BENCH_CONSTRAINT,
        "n": len(rows),
        "n_matched": n_matched,
        "n_unmatched": n_unmatched,
        "rows": rows,
    }


def _write(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2))
    print(f"wrote {path} ({obj.get('verdict', '')})", flush=True)


# ---------------------------------------------------------------------------
# P3.2 reporter — W/L by seat / generation / opponent
# ---------------------------------------------------------------------------
def report_h2(path: Path = DERIVED / "s10_bench_h2_calibration.json",
              manifest_path: Path = DERIVED / "s10_bench_manifest.json"):
    d = json.loads(path.read_text())
    rows = d["rows"]

    manifest_index = {}
    if manifest_path.exists():
        md = json.loads(manifest_path.read_text())
        for mr in md.get("rows", []):
            manifest_index[mr["episode_id"]] = mr

    by_seat = {0: [0, 0, 0, 0], 1: [0, 0, 0, 0]}
    by_gen = {}
    by_zone = {}
    by_zone_controlled = {}
    flipped = {"c_win": [], "b_loss": []}

    for r in rows:
        s = r["seat"]
        by_seat[s][0] += 1 if r["base_win"] else 0
        by_seat[s][1] += 0 if r["base_win"] else 1
        by_seat[s][2] += 1 if r["new_win"] else 0
        by_seat[s][3] += 0 if r["new_win"] else 1
        by_gen.setdefault(r["submission"], [0, 0, 0, 0])
        by_gen[r["submission"]][0] += 1 if r["base_win"] else 0
        by_gen[r["submission"]][1] += 0 if r["base_win"] else 1
        by_gen[r["submission"]][2] += 1 if r["new_win"] else 0
        by_gen[r["submission"]][3] += 0 if r["new_win"] else 1

        mrow = manifest_index.get(r["episode_id"], {})
        zone = mrow.get("rating_zone") or "unmatched"
        by_zone.setdefault(zone, [0, 0, 0, 0])
        by_zone[zone][0] += 1 if r["base_win"] else 0
        by_zone[zone][1] += 0 if r["base_win"] else 1
        by_zone[zone][2] += 1 if r["new_win"] else 0
        by_zone[zone][3] += 0 if r["new_win"] else 1
        if mrow.get("controlled"):
            by_zone_controlled.setdefault(zone, [0, 0, 0, 0])
            by_zone_controlled[zone][0] += 1 if r["base_win"] else 0
            by_zone_controlled[zone][1] += 0 if r["base_win"] else 1
            by_zone_controlled[zone][2] += 1 if r["new_win"] else 0
            by_zone_controlled[zone][3] += 0 if r["new_win"] else 1

        if (not r["base_win"]) and r["new_win"]:
            flipped["c_win"].append({"episode_id": r["episode_id"],
                                     "opponent": r["opponent"], "seat": s,
                                     "submission": r["submission"]})
        elif r["base_win"] and (not r["new_win"]):
            flipped["b_loss"].append({"episode_id": r["episode_id"],
                                      "opponent": r["opponent"], "seat": s,
                                      "submission": r["submission"]})
    report = {
        "verdict": d["verdict"],
        "constraint": d.get("constraint", BENCH_CONSTRAINT),
        "n": d["n"],
        "mcnemar": {"c": d["mcnemar_c"], "b": d["mcnemar_b"], "p": d["mcnemar_p"]},
        "by_seat": {str(k): {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                    for k, v in by_seat.items()},
        "by_generation": {k: {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                          for k, v in by_gen.items()},
        "by_rating_zone": {k: {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                           for k, v in sorted(by_zone.items())},
        "by_rating_zone_controlled": {k: {"base_w_l": [v[0], v[1]], "new_w_l": [v[2], v[3]]}
                                      for k, v in sorted(by_zone_controlled.items())},
        "flipped": flipped,
    }
    out = DERIVED / "s10_bench_h2_calibration_report.json"
    _write(out, report)
    return report


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: python analysis/s10_replay_bench.py "
              "{manifest|alpha|h2_calibration|report_h2|"
              "recovery_calibration|recovery_alpha_bias} [args]")
        sys.exit(2)
    mode, rest = args[0], args[1:]

    if mode == "manifest":
        subs = tuple(rest) or tuple(SUBMISSIONS.keys())
        out = build_manifest(subs)
        _write(DERIVED / "s10_bench_manifest.json", out)
        return

    if mode == "alpha":
        subs = tuple(rest) or tuple(SUBMISSIONS.keys())
        out = run_alpha(subs)
        _write(DERIVED / "s10_bench_alpha.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "alpha", "submissions": list(subs),
            "dataset": "confirm" if any(s in CONFIRM_SUBS for s in subs) else "screen",
            "n": out["n"], "n_bit_exact": out["n_bit_exact"],
            "share_bit_exact": out["share_bit_exact"], "verdict": out["verdict"],
            "constraint": BENCH_CONSTRAINT,
        })
        return

    if mode == "h2_calibration":
        limit = int(rest[0]) if rest else None
        out = run_h2_calibration(limit=limit)
        _write(DERIVED / "s10_bench_h2_calibration.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "h2_calibration",
            "dataset": "confirm", "submissions": list(CONFIRM_SUBS),
            "n": out["n"], "c": out["mcnemar_c"], "b": out["mcnemar_b"],
            "p": out["mcnemar_p"], "verdict": out["verdict"],
            "constraint": BENCH_CONSTRAINT,
        })
        return

    if mode == "report_h2":
        report_h2()
        return

    if mode == "recovery_calibration":
        limit = int(rest[0]) if rest else None
        out = run_recovery_calibration(limit=limit)
        _write(DERIVED / "s10_bench_recovery_calibration.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "recovery_calibration",
            "dataset": "confirm", "submissions": list(CONFIRM_SUBS),
            "n": out["n"], "c": out["mcnemar_c"], "b": out["mcnemar_b"],
            "p": out["mcnemar_p"], "mcnemar_by_seat": out["mcnemar_by_seat"],
            "recovery_fires": out["recovery_fires"], "verdict": out["verdict"],
            "constraint": OCCUPANCY_BENCH_CONSTRAINT,
        })
        return

    if mode == "recovery_alpha_bias":
        limit = int(rest[0]) if rest else None
        out = run_recovery_alpha_bias(limit=limit)
        _write(DERIVED / "s10_bench_recovery_alpha_bias.json", out)
        _append_bench_ledger({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "recovery_alpha_bias",
            "dataset": "all", "submissions": out["submissions"],
            "n": out["n"], "n_bit_exact": out["n_bit_exact"],
            "share_bit_exact": out["share_bit_exact"],
            "n_episodes_recovery_fired": out["n_episodes_recovery_fired"],
            "share_fired_and_bit_exact": out["share_fired_and_bit_exact"],
            "verdict": out["verdict"],
            "constraint": OCCUPANCY_BENCH_CONSTRAINT,
        })
        return

    print(f"unknown mode: {mode}")
    sys.exit(2)


if __name__ == "__main__":
    main()
