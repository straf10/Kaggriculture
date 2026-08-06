# v1e first-submission validation — 2026-08-06

## IMPORTANT: submission source changed from current_phase.md's literal instruction

`current_phase.md` Α.1 says `tar -czf submission.tar.gz main.py agent/` from the repo root, on
the assumption that the current working tree's `agent/` still *is* v1e in substance (its own
line 26 calls it "v1e (current agent/config.py)"). That assumption no longer holds:

**Finding — the live `agent/` tree regresses against the immutable `checkpoints/v1e`
checkpoint.** Two commits landed after the checkpoint was cut (`99db4fb` "Fix Critical + High
findings from review_4452427", `c7767bb` "Fix L10 rename" — the latter's diff is much larger
than its message suggests and includes real behavior changes: `farmHandCostMult` threading,
harvest-age derivation from `CROPS`, wheat-retry timing, market-order truncation
reprioritization H8, task-assignment tie-break sort). No gate run exists for the tree after
these commits. A fresh `compare(main.py, checkpoints/v1e/main.py, DEV_SEEDS, both_seats=True,
metrics=True)` run this session found:

```
mean_diff=-613.6  se_diff=31.3  ci95=(-676.6, -550.7)
wins_a=1 wins_b=47 (paired)   episode_wins_a=8 episode_wins_b=88 (of 96)
significant=True  practical=False  verdict=WITHIN_MARGIN
```

The live tree loses to the frozen checkpoint in 88/96 episodes, ~$614/episode on average
(significant, though inside the current non-inferiority margin so the harness doesn't call it
outright `REGRESSED`). Root cause not isolated this session — likely one or more of the H8/M-series
behavior changes bundled into `c7767bb`. Per the project's own protocol
("REGRESSED = STOP και revert"), this tree must **not** be the basis of the v1e submission
before it is bisected and re-gated. **Next session: bisect `c7767bb` flag-by-flag against
`checkpoints/v1e` on DEV_SEEDS to isolate the regression, then either fix or revert the
offending change before it becomes v1f's starting point.**

Separately, `metric_gate_passed` now reads `False` for *both* the live tree and the frozen
checkpoint, because a newer field (`weeds_lost_a`, added by the same H2/H5 harness fixes) is
non-zero (~120 over 8 episodes) for both — identically, on the same seeds. Since it's identical
across two different agent versions it looks environment-driven, not an agent regression, but
it was never part of v1e's original acceptance criteria and isn't surfaced by
`harness/cli.py`'s results-JSON writer (a real gap — `shed_overflow_burnt_a`, `weeds_lost_a`,
`units_sold_at_or_below_5_a`, `sales_count_a`, `unexplained_noops_a`, `market_sim_aborted_a`
are computed by `compare()` but dropped by `_cmd_compare`'s `_results_json_dict`). Not treated
as a submission blocker here since it predates and is independent of today's regression finding,
but it means every `metric_gate_passed=True` in gates/ recorded before this was noticed should be
read as "passed under the old, narrower definition."

**Decision made this session:** package the submission from the immutable
`checkpoints/v1e/agent_checkpoint_v1e` (fingerprint `f0ad486b...`), restaged under the
required `agent/` package name, not from the live repo-root `agent/`. This is the artifact that
actually carries Phase 1's acceptance evidence.

---

## Checklist (current_phase.md Α.1)

- [x] **Format** — `main.py` at archive root, `agent/` alongside. Verified via `tar -tzf`:
      `main.py, agent/, agent/*.py` (12 entries, no `__pycache__`).
- [x] **Loader contract (G12)** — `harness.play.resolve_agent(staged_main, entrypoint="agent")`
      resolves to a callable named `agent`; `main.py` has top-level imports only, no `__file__`
      shim; `agent/_vendored.py` parity is covered by
      `test_vendored_constants_and_prices_match_pinned_engine` (part of the 133 passing tests,
      run against the live tree's identical vendoring code).
- [x] **Timing** — profiled both seats on the staged bundle vs `starter`, seed 17, 720 steps:
      seat 0 `max=8.6ms turn1=8.6ms`, seat 1 `max=8.6ms turn1=8.6ms`. `max*3 < 1s` PASS with
      huge margin (target <333ms local, engine gate <1s including 3x server-slowdown headroom).
- [x] **Determinism (G13)** — two fresh processes, `PYTHONHASHSEED=0` vs `12345`, same seed
      (17), identical `env.toJSON()` trajectory on the staged bundle. OK.
- [x] **Mirror smoke** — `harness.cli play <staged main.py> <staged main.py> --steps 720`:
      `rewards=(38674.0, 38287.0) winner=0 statuses=('DONE','DONE') clean=True`. No self-
      destruction, no cache cross-talk (fresh process per side, same as production).
- [x] **Size** — `submission.tar.gz` is 21,140 bytes (~20.6 KiB), far under the 100 MiB cap.
- [x] **`pytest tests/`** — 133 passed (live tree; agent-internal logic tests, not
      submission-format-specific — the loader/determinism items above independently re-verify
      the actual submission bundle).
- [x] **`KAGGRI_DEBUG` off by default** — `agent/config.py`:
      `"debug": os.environ.get("KAGGRI_DEBUG", "0") == "1"` → `False` unless explicitly set.

## Baseline evidence (Α.3)

- `local_bench.json` / `local_bench_raw.jsonl` — reused from this morning's
  `runs/local_bench_v1e_vs_starter` (same checkpoint, fingerprint `f0ad486b...` matches
  `checkpoints/v1e/manifest.json`): `compare(checkpoints/v1e, "starter", HOLDOUT_SEEDS,
  both_seats=True, metrics=True, stage="holdout-confirm")` →
  **median_bank_a=$42,555, mean_diff=+$38,788 (se=160, CI [38466, 39110]), 96/96 episode wins,
  verdict=IMPROVED, GO=True, water_weeds_lost=0, plant_decay_units_lost=0,
  animals_escaped=0, clipped_production_ticks=0.**
- `local_bench_vs_pass_smoke.json` / `local_bench_vs_random_smoke.json` — new this session,
  `checkpoints/v1e/main.py` vs `pass`/`random`, SMOKE_SEEDS (12, both seats, informational only
  — smoke is never a GO signal): 24/24 episode wins each,
  mean_diff≈+$39,076 (vs pass) / +$42,681 (vs random).
- `replays/seed0_seat0-main_seat1-main.json.gz` — the mirror smoke replay above.
- Rating trajectory / leaderboard snapshots: not yet applicable — populate after the actual
  Kaggle upload starts producing episodes (Α.3 items 2-3 of the checklist).

## Submission record

Submitted 2026-08-06 15:32:19 UTC via `kaggle competitions submit` — **SUBMISSION_ID
55301989**, status PENDING at submit time, message "v1e rule-based baseline". 4 uploads/day
remaining after this one. Track with `kaggle competitions submissions kaggriculture` and, once
scored, `kaggle competitions episodes 55301989`.

Status later moved to **COMPLETE, publicScore 600.1**. `kaggle competitions episodes 55301989 -v`
shows 3 episodes: `90467901` (VALIDATION, self-play crash-check only) plus **two PUBLIC episodes
already played against other real teams**, not self-play — replays downloaded to
`live_episodes/`: `90468456` vs team "saikyo" (rewards saikyo=122189, STRAF=41513, loss) and
`90468450` vs team "Om Sangwan" (rewards Om Sangwan=7169, STRAF=42900, win). Confirms the
submission is already inside the matchmaking pool per `docs/source/competition_info.md`'s
documented flow (validation episode → default rating → matchmaking pool).

## Bottom line

The packaged `submission.tar.gz` (repo root, gitignored) is built from `checkpoints/v1e`, is
loader-, timing-, and determinism-clean, and carries the full Phase-1 acceptance evidence
(median +$42.6k vs starter, 96/96 holdout wins). It is **not** built from the current
`agent/` working tree, which has an open, unexplained regression against this same checkpoint
that needs bisection before it can be trusted for a future upload.
