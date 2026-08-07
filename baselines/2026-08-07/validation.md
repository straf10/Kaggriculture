# v1g second-submission validation — 2026-08-07

## Source

Packaged from the immutable `checkpoints/v1g/agent_checkpoint_v1g` (fingerprint
`087f4dee56f6083bf67640f3bc34f327a2f8127da7acc6b1ebc5554aec7f7830`, `checkpoints/v1g/manifest.json`),
restaged under the required `agent/` package name — same convention as the v1e submission
(`baselines/2026-08-06/validation.md`), not a literal `main.py agent/` tar from the repo root.

`diff -rq checkpoints/v1g/agent_checkpoint_v1g agent/` showed **no difference** (only a stray
`__pycache__` in the live tree) before staging, i.e. the live repo-root `agent/` and the frozen
checkpoint are behaviorally identical right now — no unbisected drift like the one found before
the v1e submission. Root `main.py` (the actual submission entrypoint, `sys.path` shim +
`from agent.policy import agent`) is unchanged since v1e and was reused as-is; the
`checkpoints/v1g/main.py` (`from agent_checkpoint_v1g.policy import agent`) is a local-bench-only
stub, not a submission entrypoint, per its own docstring.

Staged at `<scratchpad>/submit_v1g/`: `main.py` + `agent/` (12 files, `agent_checkpoint_v1g/*.py`
copied and renamed to `agent/`, no self-referential absolute imports found, so the rename is
transparent). Archived copy of the exact submitted bytes: `baselines/2026-08-07/submission_v1g.tar.gz`.

## Checklist (current_phase.md Α.1)

- [x] **Format** — `tar -tzf` on the staged bundle: `main.py, agent/, agent/*.py` (13 entries,
      no `__pycache__`). `main.py` at archive root.
- [x] **Loader contract (G12)** — loaded the staged `main.py` via `importlib`, confirmed `agent`
      resolves to a callable (last name bound in the module); no `__file__` usage anywhere in
      `agent/` or `main.py`; `agent/_vendored.py` parity already covered by
      `test_vendored_constants_and_prices_match_pinned_engine` (part of the 139 passing tests).
- [x] **Timing** — `harness.cli profile` on the staged bundle vs `starter`, seed 17, 720 steps,
      both seats: seat 0 `max=33.9ms turn1=11.0ms`, seat 1 `max=34.3ms turn1=13.8ms`.
      `max*3 < 1s` PASS with large margin (worst-case ~103ms vs 1s budget).
- [x] **Determinism (G13)** — two fresh processes, `PYTHONHASHSEED=0` vs `12345`, same seed
      (17), 720 steps: identical `rewards=(70648.0, 3456.0)`; decompressed replay JSON identical
      on every field except the per-run `id` (a stamped UUID) — all 720 `steps` entries
      byte-identical between the two runs. OK.
- [x] **Mirror smoke** — `harness.cli play <staged main.py> <staged main.py> --steps 720`:
      `rewards=(44452.0, 44452.0) winner=None statuses=('DONE', 'DONE') clean=True`. No
      self-destruction, no cache cross-talk.
- [x] **Size** — `submission.tar.gz` is 27,291 bytes (~26.7 KiB), far under the 100 MiB cap.
- [x] **`pytest tests/`** — 139 passed (live tree, which is behaviorally identical to the staged
      checkpoint per the diff above).
- [x] **`KAGGRI_DEBUG` off by default** — `agent/config.py`:
      `"debug": os.environ.get("KAGGRI_DEBUG", "0") == "1"` → `False` unless explicitly set.

## Baseline evidence (Α.3 / Β acceptance criterion)

Reused from the v1g gate (`memory.md` 2026-08-07 "v1g υλοποιήθηκε και κλείδωσε"), not re-run here
since the checkpoint is unchanged:

- `HOLDOUT_SEEDS` confirm vs `checkpoints/v1f`: verdict `IMPROVED`, **+$25,343/ep** (se=594.65),
  **96/96 episode wins**, 0 errors, metric gate clean (0 on all 4 hard-gate metrics:
  `water_weeds_lost`, `plant_decay_units_lost`, `animals_escaped`, `clipped_production_ticks`).
- Satisfies current_phase.md Α.4's upload gate: "κάθε επόμενο upload μόνο με directional
  `IMPROVED` σε holdout-confirm" — this is the first upload since v1e for which that condition is
  met (v1f alone was not submitted; v1g rolls up both v1f crew scale-up and the animal mass
  scale-up).

## Note: an unrelated failed attempt preceded this one

`kaggle competitions submissions kaggriculture` showed a submission **55324338** ("main.py",
2026-08-07 12:12, status `ERROR`, description "2nd attempt") already present before this
session's upload — made outside this session/repo tooling (no `tar.gz`, wrong format: raw
`main.py` without the bundled `agent/` package). Not investigated further since it predates and
is unrelated to this submission; noted here only so the submissions list is explained. It used
one of the 5 daily upload slots.

## Submission record

Submitted 2026-08-07 12:18:34 UTC via `kaggle competitions submit` (`.venv/Scripts/kaggle.exe`,
credentials from repo-root `.env`) — **SUBMISSION_ID 55324447**, status PENDING at submit time,
message "v1g animal mass scale-up (10 animals: 6 COW + 4 SHEEP)". 4 uploads/day remaining after
this one (5 total, 1 consumed by the pre-existing errored attempt above).

Track with `kaggle competitions submissions kaggriculture` and, once scored,
`kaggle competitions episodes 55324447 -v`.

## Bottom line

`baselines/2026-08-07/submission_v1g.tar.gz` (also live at repo-root, gitignored, as
`submission.tar.gz`) is built from the immutable `checkpoints/v1g`, is loader-, timing-, and
determinism-clean, and carries the v1g holdout-confirm acceptance evidence (+$25,343/ep, 96/96
wins vs `checkpoints/v1f`). Submitted to Kaggle as SUBMISSION_ID **55324447**, status PENDING.
