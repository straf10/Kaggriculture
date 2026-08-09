# v1h.2d fourth-submission validation — 2026-08-10

Closes the `v1h.2` metric-restoration increment that had been STOP'd since 2026-08-09 (memory.md
2026-08-09 (ε)) under the old all-hard-zero gate. Under current_phase.md §1 Απόφαση Α (the priced
metric gate adopted this session), the same measured candidate passes.

## Source

`checkpoints/v1h_2d/agent_checkpoint_v1h_2d`, fingerprint
`56c62c302c33f3c5db5896189e8a2fd1a136e13ee97658177a514ede83f7d233`. Built from `agent/` as it
stood at commit `59fe9af` (the "v1h.2d semantic gate + logistics" commit measured by
`gates/gate_v1h2d_feed_slack`) — **not** from the working tree at the time this session started
(`cdcbe62`, "Fixed several bugs"). `cdcbe62` touched `agent/config.py`/`executor.py`/`planner.py`
after the gate that measured this candidate, without a new gate of its own; re-running the total
DEV screen against both arms (`gates/gate_v1h2d_dev_pre` vs `gates/gate_v1h2d_dev_head`) showed
`cdcbe62`'s changes cost **~$2,900/ep** and reintroduce 39 `animals_escaped` against the
`59fe9af` state's 0. `agent/` and `tests/test_agent_guards.py` were reverted to the `59fe9af`
content (`git checkout 59fe9af -- agent/ tests/test_agent_guards.py`) before building this
checkpoint; `cdcbe62` remains in git history for inspection but its `agent/` delta was not
carried forward. `diff -rq` (EOL-insensitive) between the staged `agent/` and the live repo-root
`agent/` showed **no difference** — no unbisected drift.

Archived copy of the exact submitted bytes: `baselines/2026-08-10/submission_v1h_2d.tar.gz`.

## What changed vs the last submitted checkpoint (`v1h`, `55383610`)

Root causes D1 (day-2 watering hole), D3 (liquidation dump), D2 (MILK collapse under the 1.32.6
balance change) plus the v1h.2d EOD product-aware surplus-sell and FEED deadline/slack fix —
full mechanism and rejected variants: memory.md 2026-08-09 (δ)/(ε). This session additionally
fixed a real bug in the harness metric itself (`harness/metrics.py`): the semantic
`unexpected_weeds_lost` exclusion for successful ongoing-crop harvest retirement was being
checked against a *per-transition* harvest set, but the engine retires a harvested-to-zero crop
17-24 steps after the harvest (measured on a real episode), so the exclusion never fired and
every healthy retirement priced as an unexpected loss. Fixed by accumulating the harvested-to-
zero set over the whole episode, keyed by (position, crop, planted_day) so a replanted crop
cannot inherit the exemption (`tests/test_metrics.py::test_v1h2d_retirement_is_expected_even_when_it_lands_turns_after_the_harvest`).

## Upload gate (current_phase.md §Α.3 / §1 Απόφαση Α): directional `IMPROVED` on holdout-confirm

`checkpoints/v1h_2d` vs `checkpoints/v1h_1`, `HOLDOUT_SEEDS` 100-147, both seats, `--metrics`,
**unpinned** (§Πρωτόκολλο rule 3):

    verdict=IMPROVED  mean_diff=+$7,599.7/ep  se=1,266.0  ci95=(5,051.7, 10,147.7)
    wins_a=41/48  episode_wins_a=82/96  sign_test_p≈6.2e-7  errors=0
    water_weeds_lost_a=0  plant_decay_units_lost_a=0  animals_escaped_a=0
    clipped_production_ticks_a=0  shed_overflow_burnt_a=28  weeds_lost_a=768 (diagnostic)
    unexpected_weeds_lost_a=0  units_sold_at_or_below_5_a=22/61,518
    priced_loss=$43.8/ep  budget=$500.0/ep  metric_gate_passed=True  GO=True

Priced-loss mechanism declared for the one non-zero counter (`--metric-mechanism
shed_overflow_burnt=...`): residual burn on peak-production days — the EOD product-aware
surplus sell clears almost all of the shed pressure the raw `v1h_2c` candidate had (1,510 units
on DEV) but a day whose incoming production exceeds the sellable headroom still burns a small
fraction of a unit per episode. $43.8/ep against a $7,599.7/ep gain is 0.6% — far inside both the
10%-of-gain and $500/ep bounds.

Artifacts: `gates/gate_v1h2d_holdout/results.json`, `gates/gate_v1h2d_dev_pre/results.json`
(total DEV screen, `IMPROVED +$7,133.6/ep`), `gates/gate_v1h2d_dev_head/results.json` (the
rejected `cdcbe62` arm, kept for the record), confirm ledger row in `gates/confirm_log.jsonl`
(`repeat_confirm_index=0`).

## Checklist (current_phase.md §Α.2)

- [x] **Format** — `tar -tzf`: `main.py, agent/, agent/*.py` (15 entries, no `__pycache__`),
      `main.py` at archive root. 43,328 bytes.
- [x] **Loader contract (G12)** — `resolve_agent(main.py, entrypoint="agent")` resolves to
      `agent.policy.agent`; it is also the last (only) callable in the executed namespace, i.e.
      exactly what the Kaggle loader would pick. No `__file__` usage.
- [x] **Timing** — 720 steps, both seats: seat 0 `max=50.8ms median=0.8ms p99=4.1ms
      turn1=12.3ms`, seat 1 `max=5.2ms median=0.7ms turn1=0.4ms`. `max*3 < 1s` PASS both seats.
- [x] **Determinism (G13)** — `PYTHONHASHSEED=0` vs `12345`, seed 7, full 720 steps: identical
      `rewards=(22587.0, 22587.0)`.
- [x] **Mirror smoke** — `harness.cli play main.py main.py --seed 0 --steps 720`:
      `rewards=(61184.0, 61184.0) winner=None statuses=('DONE','DONE') clean=True`.
- [x] **Packaged bundle actually plays** — root `main.py` vs `checkpoints/v1h_1/main.py`,
      seed 5: `clean=True rewards=(42849.0, 26768.0)` — wins the previous champion checkpoint.
- [x] **Size** — 43,328 bytes, far under the 100 MiB cap.
- [x] **`pytest tests/`** — 205 passed.
- [x] **`KAGGRI_DEBUG` off by default** — `CONFIG["guards"]["debug"] is False`; no `KAGGRI_*`
      vars set during any gate run.

## Submission

Per current_phase.md §1 Απόφαση Γ (ship as soon as a candidate clears Απόφαση Α + unpinned
holdout — do not wait on the next increment): submitted to replace the currently-active,
measured-broken `v1h` (`55383610`, 198 water weeds / 85 escapes / 2,370 units at <=$5 on the
live 1.32.6 engine). `v1g` (`55324447`, `publicScore 643.7`) stays as champion; `v1h_2d` is the
differentiated challenger (D1/D2/D3 metric restoration + WHEAT/SW under 1.32.6, vs v1g's
pre-1.32.6 profile) per the §Α.3 diversification rule.
