# memory.md — Session Log

> Internal project memory, updated at the end of each working session. Newest entry on top.
> Purpose: let a fresh session (human or assistant) pick up context fast — what changed, why,
> and what's next — without re-reading the whole git history. Strategy/rules live in
> [docs/MASTERPLAN.md](docs/MASTERPLAN.md); the current execution plan lives in [plan.md](plan.md).
> This file only records **what happened**, not decisions that belong in those two.

---

## 2026-08-05 — Session: Βήμα 0 complete (engine ground-truth tests + harness)

**Context:** User joined the Kaggle competition (`kaggriculture`, confirmed via
`kaggle competitions list --group entered` → `userHasEntered: True`, rank 0). This resolves
plan.md's Εκκρεμότητα #1. Kaggle CLI auth also confirmed working with `KAGGLE_API_TOKEN` from
`.env` (plan.md §2.5 — no fallback auth needed, worked on the first try).

**Done — plan.md Βήμα 0, all boxes now checked:**
- `requirements-dev.txt` (pytest 9.1.1 pinned alongside kaggle-environments 1.32.4).
- `tests/test_engine_facts.py` — 32 tests (Tier A + Tier B), covering every §2/§7 finding in
  MASTERPLAN plus Υ3 determinism. Every behavior was empirically verified against the
  installed engine *before* being encoded as an assertion (not just derived by reading source).
  One correction along the way: the initial `test_floor_sales_no_inventory_growth` used WHEAT
  and asserted an exact floor price — WHEAT's curve is too glut-resistant to floor from a
  single sell order, and even MELON (the fragile one) wobbles by a few dollars turn-to-turn
  because town-center demand consumption runs every turn regardless of player actions. Fixed
  by switching to MELON and asserting "near floor + bounded inventory growth" instead of an
  exact number. `pytest tests/` → 32 passed in 1.81s.
- `harness/` package: `play.py`, `compare.py`, `metrics.py`, `profile.py`, `cli.py`. Agent specs
  resolve from callables, built-in names ("pass"/"random"/"starter"), or `.py` file paths (via
  `kaggle_environments.agent.get_last_callable`, the same loading path the server uses).
  `compare("starter", "pass", seeds=range(12), both_seats=True)` at full 720 steps: **12/12
  seed-level wins, mean_diff≈499, significant=True, 73s wall time**, 24 replays written to
  `runs/step0_acceptance/`. Reproducibility spot-checked at 200 steps (identical per-seed diffs
  across two runs) — full determinism is also covered directly by
  `test_determinism_same_seed` in the test suite.
- `.gitignore`: added `runs/`.
- `plan.md` checkboxes updated in place for every completed Βήμα-0 item (§2.1, §2.4, §2.5,
  Εκκρεμότητες).

**Not yet started:** Βήμα 1 (`agent/` — v0 walking skeleton through v1e trickle-selling, per
plan.md §3.3). No `agent/` or `main.py` exists yet.

**Next session should:** start plan.md §3.3 v0 — walking skeleton (`main.py` + `agent/` package,
PASS everywhere, 0 market orders; acceptance: 720 steps no exception on both seats, DONE,
bank untouched at $3.000).
