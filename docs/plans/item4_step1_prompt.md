# Pass brief — item ④ step 1: the travel-ratio diagnostic (③)

> **This pass changes no `agent/` code, no `main.py`, no `submission.tar.gz`, and makes no Kaggle
> submission.** It is a measurement whose job is to decide whether item ④ gets built at all. A pass
> that ends in "⛔ STOP, item ④ is refuted" is a **successful** pass, not a failed one.

> **Read first, in this order:**
> 1. [docs/plans/item4_min_cost_assignment.md](item4_min_cost_assignment.md) — §0 (what ④ is and
>    is not), §1 (invariants **G-1…G-8**), §2 step 1, §3 (the step table). This is the spec.
> 2. [ROADMAP.md](../../ROADMAP.md) §2 + §2.1 (method: both seats, classify the knob), **§3.3**
>    (the measured STOPs), **§3.4** (standing lessons).
> 3. [memory.md](../journal/memory.md) — the top two entries.
>
> **§3.4 contains the single most load-bearing sentence for this pass:** *"A ratio is a
> diagnostic, never a target."* v1p1b arm A1 achieved the largest commute reduction ever measured
> in this repo (`worker_turns_moving` 46,0%) by doing **fewer** working turns and shedding 30% of
> `crop_tile_days` into idle. If your diagnostic reports a ratio without the absolute count beside
> it, it is reproducing that error.

---

## 1. Why this pass exists

`agent/scheduler.py:assign()` is a **greedy one-at-a-time matcher**. Every turn it builds all
(unit, task) candidate pairs, takes the single global minimum of a 9-field lexicographic key,
commits it, removes that unit and every competing task at the same position, and repeats.

Greedy matching has a known worst case of 2× optimal total cost. Item ④ proposes replacing it with
min-cost bipartite matching over the whole unit × task pool.

**Before building that, this pass answers one question:**

> Of the unit-turns we spend moving rather than working, how many are walks that a better
> *matching* could have avoided, and how many are geometrically forced?

The reason this question comes first is the measured history. Four consecutive attempts have died
against the same wall from different directions:

| Attempt | What it established |
|---|---|
| v1p.1 / v1p.1b (3 arms) | the 10 claimed PASTURE slots are already the 10 nearest — geometry has no free move |
| v1p.2 / **v1p.2b** | **"the constraint genuinely is not which tasks a unit is offered"** — its own kill criterion |
| v1o.3 (7 variants) | tier 0 is saturated 100% of the day from d9 ⇒ reordering inside tier 0 is strictly zero-sum |
| S3 step 2 (3 arms) | herd 13 ⇒ either 122 escapes or `crop_tile_days` −36% |

Matching is the last untested candidate. If it is also not the constraint, that is a real and
valuable answer — record it and stop, rather than building for three more passes.

---

## 2. What to build

One script: **`analysis/v1u_travel_ratio.py`**, on the template of
[analysis/v1o3_visit_efficiency.py](../../analysis/v1o3_visit_efficiency.py). Read
[analysis/v1r_feed_reserve.py](../../analysis/v1r_feed_reserve.py) for how to work from *existing*
replays instead of re-running episodes, and [analysis/v1t_engine_probe.py](../../analysis/v1t_engine_probe.py)
for the "state explicitly what your measurement cannot conclude" discipline this one also needs.

Source replays: whatever is under `gates/` (currently `v1q_onboarding_escape`, `v1r_feed_reserve`,
`v1s_inert`, `v1s_phase0`) plus fresh runs against `harness/bench_agents/meta_route*.py` and
`checkpoints/v1o_2`. **Both seats** (§2.1.1 — seat 0 and seat 1 are not symmetric even on the same
seed).

Measure, per episode and per day:

1. **`worker_turns_working` / `_moving` / `_idle`, absolute counts.** These already exist in
   [harness/compare.py](../../harness/compare.py) around [:300](../../harness/compare.py:300) —
   read R15's comment there before defining anything new.
2. **Greedy regret.** At each turn, reconstruct the assignment `assign()` actually produced, then
   compute the min-cost matching over the **same candidate set under the same constraints**, and
   record `Σ distance(greedy) − Σ distance(optimal)`.
3. **The distribution of that regret** — per turn, per day; feed round vs crop round; early vs late
   season. A regret total that is concentrated in 5% of turns implies a different fix than one
   spread evenly.
4. **The forced-walk floor** — the optimal matching's own total distance. Even a perfect matcher
   pays this. `optimal_total / greedy_total` is the hard ceiling on what item ④ can ever return.

This is offline analysis. It is allowed to be slow, and it may use scipy.

### ⚠️ The one way to get this measurement wrong

**`task.priority` is a hard constraint, not a cost term (G-1).** If you compute the "optimal"
matching by throwing every pair into one cost matrix, you will get a large regret number that is
**not achievable** — it will have bought its distance saving by trading a tier-0 FEED for tier-1
WATERs, which v1o.3 measured as losing at roughly a 10:1 exchange rate however cleanly implemented.

So the optimal baseline must be computed the way a legal implementation would: **per priority tier,
highest first** — match tier 0 across all units, remove the matched units, then tier 1 over what
remains. Likewise honour the constraints that already exist in `assign()`:

- **cargo (G-4)** — FEED requires WHEAT in *that unit's* inventory, PLACE requires the animal.
  Ineligible pairs must be **absent** from the matrix, not merely expensive.
- **`allowed_unit`** — restricts a task to exactly one unit.
- **seeds (G-5)** — *n* PLANT tasks for a crop cannot exceed seeds on hand.
- **position exclusivity (G-6)** — two units never get tasks at the same tile, except `allowed_unit`
  tasks which dedup by `id`.
- **`committed` stickiness (G-2)** — a unit already walking toward a still-live task keeps it.
  Model this the way step 5 will: **pin committed pairs before the solve and remove them from the
  pool.**

A regret number computed without these is worse than no number, because it will pass the threshold
and send the next four passes down a road that cannot be built.

---

## 3. Pre-registered decision — write this into the report **before** the first number

ROADMAP §3.1 rule 4. Do not run a measurement and then choose a threshold.

| Regret, as % of total moving turns | Decision |
|---|---|
| **≥ 8%** | proceed to step 2 (the offline oracle) |
| **3 – 8%** | proceed, but re-scope ④ to the **feed round only** — the subset with the deepest regret — not the whole task pool |
| **< 3%** | ⛔ **STOP item ④.** The commute is a geometric floor, not a matching loss |

If it stops: record it as a new row in ROADMAP §3.3 with the mechanism, note in §4.3 that both ③
and ④ are closed, and say plainly that reaching the §4.0 profile with this planner is refuted —
which makes the tape (§4.2, now the chosen path) the production route rather than a hedge.

---

## 4. Deliverables

1. `analysis/v1u_travel_ratio.py`.
2. `baselines/<today>/item4_step1_report.md` — pre-registered criteria at the top, then the four
   measurements, then the decision. (`baselines/` is gitignored; that is intended.)
3. A machine-readable `data/derived/v1u_travel_ratio-<date>.json`.
4. Tests for any non-trivial helper, in the existing style. `pytest tests/` must stay at
   **268 passed** plus whatever you add (3 pre-existing failures in
   `tests/test_harness.py::test_v1h2d_priced_gate_decides_the_three_measured_arms` are expected —
   do not "fix" them in this pass).
5. ROADMAP §4.3 + §7 updated with the result; a new `memory.md` entry on top.

---

## 5. Environment

- Engine **`kaggle-environments==1.32.7`** (D28 — the `hinge` curve on CARROT/TOMATO/EGG).
  Python is `.venv/bin/python`; the venv is not on `PATH`.
- ⚠️ **Existing replays under `gates/` were produced on 1.32.6.** For *this* measurement that is
  acceptable — regret is a routing quantity and D28 touched only market prices — but **state the
  assumption in the report** rather than leaving it implicit. Anything you generate fresh will be
  on 1.32.7 and must not be pooled with 1.32.6 replays in the same aggregate.
- ⚠️ `gates/` and `baselines/` are **gitignored and absent from a fresh clone**. Run `ls gates/`
  first; if empty, generate replays before analysing.
- Kaggle auth, if needed: `export KAGGLE_API_TOKEN=$(grep KAGGLE_API_TOKEN .env | cut -d= -f2)`;
  the CLI is `.venv/bin/kaggle`.

---

## 6. Out of scope — do not do these in this pass

- **Any change to `agent/`, `main.py`, or `submission.tar.gz`.** Step 1 is measurement only.
- **Implementing the matching in the agent.** That is steps 3-5, and each is gated separately.
- **The tape work (T1).** It is the primary path and it lived in `prompt.md` (a rolling brief, now
  retired — see [RETIRED_DOCS](../journal/RETIRED_DOCS.md)); it is independent of this pass and the two
  can run in parallel. Ignore the tape work this pass.
- **The D28 carrot opportunity.** Real (18% of episodes drain CARROT past the knee, 54% for TOMATO)
  and it is the first-ever candidate for §3.3's standing v1k re-test trigger — but it is a separate
  pass with its own Phase 0.
- **Any herd, crew, or land retry.** All of them are explicitly gated behind ④ being accepted
  (plan §2 step 8).

---

## 7. How to report back

Lead with the decision and the number that drove it, then the measurements, then what you did *not*
establish. If the pass stops the item, say so in the first line. Do not soften a STOP into "further
investigation needed" — this repo's whole method depends on rejections being legible.
