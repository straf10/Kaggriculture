# v1h third-submission validation — 2026-08-09

`SUBMISSION_ID 55383610` · message *"v1h SW quadrant planted with WHEAT + crew 6->10 during the
SW work window"* · status PENDING at upload · 4 uploads remaining today.

This is the **third** live submission. Kaggle keeps only the last two active, so v1h replaces
**v1e** (`55301989`, `publicScore 557.0`); the active pair is now **v1g** (`55324447`,
`publicScore 643.7` — converged well above v1e, so the 508.3 recorded on 08-07 was indeed the
2-episode sample it looked like) and **v1h**.

## Source

Packaged from the immutable `checkpoints/v1h/agent_checkpoint_v1h` (fingerprint
`c9b14e53335431adc6f8a17f21852a6fb1f1d8a717d60b94ed6d78e24f5ef560`,
`checkpoints/v1h/manifest.json`), restaged under the required `agent/` package name — same
convention as v1e/v1g (`baselines/2026-08-06`, `baselines/2026-08-07`).

`diff -rq` between the staged `agent/` and the live repo-root `agent/` showed **no difference**
(excluding `__pycache__`) — no unbisected drift. Root `main.py` (the actual entrypoint:
`sys.path` shim + `from agent.policy import agent`) is unchanged since v1e and was reused as-is.

Archived copy of the exact submitted bytes: `baselines/2026-08-09/submission_v1h.tar.gz`.

## Upload gate (current_phase.md §Α.3): directional `IMPROVED` on holdout-confirm

`checkpoints/v1h` vs `checkpoints/v1g_1`, `HOLDOUT_SEEDS` 100-147, both seats, `--metrics`,
**unpinned** (§Πρωτόκολλο rule 3 — a pinned result only holds for the pinned towns):

    verdict=IMPROVED  mean_diff=+$2,835.1/ep  se=63.8  ci95=(2706.7, 2963.5)
    wins_a=48/48  episode_wins_a=96/96  sign_test_p≈7e-15  errors=0

Artifacts: `gates/gate_v1h_holdout/results.json`, confirm ledger row in
`gates/confirm_log.jsonl` (`repeat_confirm_index=0` — first confirm for this agent_b/seed set).

## Checklist (current_phase.md §Α.2)

- [x] **Format** — `tar -tzf`: `main.py, agent/, agent/*.py` (15 entries, no `__pycache__`),
      `main.py` at archive root.
- [x] **Loader contract (G12)** — `resolve_agent(<staged main.py>, entrypoint="agent")` resolves
      to `agent.policy.agent` *and* confirms it is the last callable in the executed namespace,
      i.e. exactly what the Kaggle loader would pick. No `__file__` usage. `agent/_vendored.py`
      parity against the installed 1.32.5 covered by
      `test_vendored_constants_and_prices_match_pinned_engine` (part of the 177 passing tests).
- [x] **Timing** — `harness.cli profile main.py --opponent main.py`, 720 steps, both seats:
      seat 0 `max=12.2ms median=0.7ms p99=4.2ms turn1=12.2ms`, seat 1 `max=56.5ms median=0.7ms
      turn1=0.4ms`. `max*3 < 1s` PASS (worst case ~170ms vs the 1s budget). ⚠️ Worth noting for
      future increments: this is the first version running **11 units** (farmer + 10 hands)
      through `scheduler.assign()` while SW is being worked, and seat 1's max is ~1.6× v1g's
      34.3ms. Still an order of magnitude inside budget, but the margin is no longer 30×.
- [x] **Determinism (G13)** — two fresh processes, `PYTHONHASHSEED=0` vs `12345`, seed 7, full
      720 steps: identical `rewards=(37394.0, 37394.0)`. The cross-process trajectory check is
      also covered by `test_g13_cross_process_hashseed_determinism` in the suite.
- [x] **Mirror smoke** — `harness.cli play main.py main.py --seed 0 --steps 720`:
      `rewards=(47429.0, 47429.0) winner=None statuses=('DONE','DONE') clean=True`.
- [x] **Packaged bundle actually plays** — the staged `main.py` (not the repo copy) vs
      `checkpoints/v1g_1/main.py`, seed 5: `clean=True rewards=(57163.0, 54238.0)`.
- [x] **Size** — 38,546 bytes (~37.6 KiB), far under the 100 MiB cap.
- [x] **`pytest tests/`** — 177 passed.
- [x] **`KAGGRI_DEBUG` off by default** — `CONFIG["guards"]["debug"] is False` in a clean
      process; no `KAGGRI_*` vars set during any gate run (`env={}` in the results.json).

## Known residual, disclosed rather than buried

The holdout run reports `metric_gate_passed=False`, as every gate since v1f has, and the reason
is **almost** the same pre-existing `weeds_lost=768` (random weed spawns on empty tiles, present
identically in `checkpoints/v1e` — see `docs/reviews/review_4452427_2026-08-06.md` finding M1).
The one genuinely new term is **`shed_overflow_burnt = 20` across 96 episodes (0.2 units per
episode)**, which was 0 in v1g: home-grown WHEAT now shares the 100-slot shed with everything
else, and on a handful of end-of-day drops the shed is briefly full. It is ~$20/ep of burnt
value against +$2,835/ep, and the increment's own hard gates (`water_weeds_lost`,
`plant_decay_units_lost`, `animals_escaped`, `clipped_production_ticks`) are all **0**. It is
recorded here because it is the first thing to look at if `sw_wheat_tiles` is ever raised — the
16-tile variant burnt **3,100** units over the same episode count, which is what disqualified it.
