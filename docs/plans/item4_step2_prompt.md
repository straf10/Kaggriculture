# Pass brief — item ④ step 2: the offline oracle

> **This pass changes no `agent/` code, no `main.py`, no `submission.tar.gz`, and makes no Kaggle
> submission.** It measures a ceiling. A result of "⛔ STOP, item ④ refuted" is a **successful**
> pass — and on the arithmetic below it is a likely one. Do not treat it as a failure to avoid.

> **Read first, in this order:**
> 1. `baselines/2026-08-15/item4_step1_report.md` — the previous pass. Its §2.1-2.4 (capture
>    method, greedy validation, the optimal frame, why regret does not double-count) is the
>    machinery this pass reuses.
> 2. [analysis/v1u_travel_ratio.py](../../analysis/v1u_travel_ratio.py) — the working code for that
>    machinery. **Read it before writing anything**; the `agent.policy.assign` wrapper and the
>    per-tier legal-optimal solver are both directly reusable and re-deriving them would waste the
>    pass.
> 3. [docs/plans/item4_min_cost_assignment.md](item4_min_cost_assignment.md) — §1 (invariants
>    **G-1…G-8**), the step 1 result block, and **§2 step 2 as revised on 2026-08-15** (three arms,
>    two-legged kill). That section is the spec; this brief is its operational form.
> 4. [ROADMAP.md](../../ROADMAP.md) §3.3 (the STOPs — especially **herd 13** and **v1o.3**), §3.4.

---

## 1. Where this stands

Step 1 measured greedy regret at **4,30%** of moving turns (≈159 walk-steps/episode), inside the
pre-registered 3-8% "proceed, re-scope to the feed round" band. Four findings now constrain
everything:

1. **Forced-walk floor 0,9631** — a perfect per-turn matcher still pays 96,3% of the commute.
   **≤3,7% is the permanent ceiling** for matching alone.
2. **82,8% of regret is in the feed round; 86,3% is in the worst 5% of turns.** Thin and
   concentrated, not broad.
3. **Cardinality gap ≈ 0** (4 extra tasks across 36 episodes) — greedy is already effectively a
   maximum matching. **④ buys efficiency, never throughput.**
4. The achievable frame is the **conservative re-match** optimum. A pure-distance optimum reads
   ~25,7% but buys it by missing FEED deadlines; it is a mirage and must not reappear in this pass.

## 2. The arithmetic you are testing against — read this before choosing a method

From step 1: ≈159 walk-steps/ep ⇒ at most ≈159 extra working turns (+11,6% on 1.365/ep) ⇒ at ~0,42
crop-tile-days per working turn and v1o.3's ~$31/crop-tile-day, **≈+$2.100/ep as a naive ceiling,
before any implementation loss.**

So the standalone dollar leg is **expected to be marginal at best**. That is not a reason to skip
the pass, and it is not a reason to massage the number upward. It is the reason the kill criterion
has a second leg (§4), and the reason arm ordering matters (§3).

---

## 3. What to build and run

Extend `analysis/v1u_travel_ratio.py` (or add `analysis/v1u_oracle.py` beside it, reusing its
wrapper) so that instead of *measuring* the optimal, it **substitutes** it: swap
`agent.policy.assign` for a slow, legal, optimal matcher and let the episode actually play out
under it. scipy is allowed; there is no time budget in this pass.

**SMOKE 0-11, both seats, `--town-pin basket`** (routing is an occupancy change, §2.1.2), against a
`v1u_base` checkpoint **built on 1.32.7**. Build that baseline first — every existing checkpoint is
1.32.6 and cross-engine comparison is exactly the §4.2 B1 error.

> ⚠️ **Seat note from step 1:** the two seats of a (seed, opponent) returned *identical* regret
> vectors, because regret is a pure routing quantity. **That does not carry over to this pass** —
> step 2 measures *dollars*, and banks differ by seat through occupancy coupling. Both seats are
> load-bearing here.

### Three arms, in this order

| Arm | What | Stop rule |
|---|---|---|
| **A — whole-pool optimal** | per-tier legal min-cost matching over the full pool, every turn | **run first.** It is the strict ceiling; B and C are bounded by it. If A misses both legs of §4, **end the pass** — B and C cannot clear what A could not |
| **B — greedy + 2-opt repair** | keep greedy, then pairwise-swap assignments between units, accepting only strict improvements | run if A clears. **This may be the actual product** |
| **C — feed-round only** | arm A restricted to feed-round tasks | run if A clears; this is step 1's mandated re-scope |

**Why arm B matters more than its position suggests.** Cardinality gap ≈0 and 86,3% of regret in 5%
of turns means a full Hungarian on all 720 turns is disproportionate. A pairwise swap pass is
O(n²), preserves every constraint **by construction** (only swap where both units are eligible for
both tasks), is trivially deterministic, and needs **no solver and no new dependency**. If B lands
close to A, plan steps 5-6 collapse — no vendored Hungarian, no O(n³) budget problem, no candidate
cap. Report `B/A` explicitly as a headline number.

### Constraints the optimal must honour (G-1…G-6)

Identical to step 1, and step 1's implementation is correct — reuse it rather than rewriting:
priority is a **hard constraint solved per tier, highest first, never a cost**; cargo eligibility
and `allowed_unit` restrict the matrix rather than penalising it; positions collapse to one node;
seeds are feasible by construction from `build_tasks()`; `committed` pairs are **pinned before the
solve**. Padding with idle columns must keep max cardinality — never buy distance by leaving legal
work undone (§3.4 anti-pattern).

---

## 4. Pre-registered decision — write into the report **before the first number**

ROADMAP §3.1 rule 4.

**PROCEED to step 3 if EITHER leg clears:**

- **Leg 1 — standalone value.** Arm A or B returns **≥ +$2.000/ep** on SMOKE, with
  `crop_tile_days` flat or up (±3%) and `animals_escaped` inside the ±5 noise floor.
- **Leg 2 — the unblock.** The oracle measurably relieves the feed round:
  **feed-round saturation** (share of day-hours with ≥1 animal `fed_today=False`, currently **100%
  from d9**) drops below **90%** on the median day from d9, **or** `animals_underfed_days` falls
  **≥15%**.

**⛔ STOP if BOTH miss.** Record in ROADMAP §3.3: the commute is a 96,3% geometric floor, the
residual is real but too thin to pay, herd 13 stays blocked, and reaching the §4.0 profile with this
planner is **refuted** — which makes the tape (§4.2) the only production route and closes ④.

> **Leg 2 is the one that matters.** ④'s value was never mostly its own dollars — it is a
> precondition. The nearest blocked thing is **herd 13, −$15-21k/ep purely on feed logistics**, and
> step 1 found 82,8% of recoverable regret is in the feed round: the same currency. If leg 2 clears,
> **re-run the existing S3 step 2 arm `checkpoints/v1s_H2R` under the oracle.** That is the direct
> test of the only claim that makes ④ worth building, the arm already exists, and it is cheap.

---

## 5. Deliverables

1. The oracle script (extend `analysis/v1u_travel_ratio.py` or add `analysis/v1u_oracle.py`).
2. `baselines/2026-08-15/item4_step2_report.md` (or today's date) — pre-registration at the top,
   then arms A/B/C, then the two-leg decision. `baselines/` is gitignored; intended.
3. `data/derived/v1u_oracle-<date>.json`.
4. Tests for any non-trivial helper. `pytest tests/` stays at **275 passed** plus what you add; the
   3 pre-existing failures in `test_v1h2d_priced_gate_decides_the_three_measured_arms` are expected
   — do not "fix" them here.
5. ROADMAP §4.3 + §7 updated; new `memory.md` entry on top; the plan doc's step 2 marked with its
   result the way step 1 now is.

## 6. Environment

- Engine **`kaggle-environments==1.32.7`** (D28). Python is `.venv/bin/python` (not on `PATH`).
- `gates/` and `baselines/` are **gitignored and absent from a fresh clone**.
- `checkpoints/` packages are gitignored (manifests are tracked) — `v1u_base` must be built locally.
- Kaggle auth if needed: `export KAGGLE_API_TOKEN=$(grep KAGGLE_API_TOKEN .env | cut -d= -f2)`;
  CLI is `.venv/bin/kaggle`.

## 7. Out of scope

- **Any `agent/` change.** Steps 3-5 do that, each gated separately. The oracle lives in `analysis/`.
- **The tape (T1)** — primary path, lived in the rolling `prompt.md` (retired — see [RETIRED_DOCS](../journal/RETIRED_DOCS.md)), independent of this pass.
- **The D28 carrot opportunity** — separate pass with its own Phase 0.
- **Herd/crew/land retries** — except the single `v1s_H2R`-under-oracle probe in §4, which is a
  measurement, not an increment.

## 8. How to report back

Lead with the decision and the two leg results. State `B/A` explicitly. If the pass stops the item,
say so in the first line — do not soften a STOP into "further investigation needed". This repo's
method depends on rejections being legible.
