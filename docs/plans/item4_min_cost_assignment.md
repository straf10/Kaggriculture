# Item ④ — min-cost assignment, built properly

> **Status:** not started. Written 2026-08-15, after the S3 step 2 STOP.
> **Owner doc:** [ROADMAP.md](../../ROADMAP.md) §4.3 (deferred items ③/④). This file is the
> implementation plan; ROADMAP stays the record of decisions and results.
> **Engine:** `kaggle-environments==1.32.7` (D28). Nothing in this item touches the market, so
> the 1.32.7 bump is orthogonal to it — but every baseline below must be **rebuilt on 1.32.7**,
> because comparing across engine versions is the exact mistake §4.2's B1 correction records.

---

## 0. What this is, and what it is not

`agent/scheduler.py:assign()` decides, every turn, which unit does which task. It is a **greedy
one-at-a-time matcher**: build every (unit, task) candidate, take the single global minimum of a
9-field lexicographic key, commit it, delete that unit and every competing task at that position,
repeat until one side runs out.

Greedy matching has a known worst case of **2× the optimal total cost**, and the shape of the loss
is specific: a unit that is the best fit for two tasks gets consumed by whichever task wins the key
first, and the second task then falls to a much more distant unit. Item ④ replaces that loop with a
**min-cost bipartite matching** (Hungarian / auction) over the full unit × task pool, so all
assignments in a turn are decided jointly.

**What it is not:** a rewrite of what the tasks *are*. `build_tasks()` is untouched. Priorities,
deadlines, urgency tiers, cargo rules and stickiness all stay exactly as they are. This item
changes only *how the same task list is matched to the same units*.

### Why this item, and not another herd/crew retry

Every STOP in ROADMAP §3.3 since v1o.2 lands on the same wall from a different direction:

| Attempt | What it proved |
|---|---|
| v1p.1 / v1p.1b (herd compaction, 3 arms) | the 10 claimed PASTURE slots are already the 10 nearest — geometry has no free move left |
| v1p.2 / v1p.2b (zone assignment, sticky zones) | **"the constraint is not which tasks a unit is offered"** — its own restated kill criterion |
| v1o.3 (feed-round re-tiering, 7 variants) | tier 0 is saturated 100% of the day from d9 ⇒ **reordering inside tier 0 is strictly zero-sum** |
| S3 step 2 (herd 13, 3 arms) | +3 animals at distance 7,7,8 ⇒ either 122 escapes or `crop_tile_days` −36% |

Read together they say: the farm has no spare unit-turns, the spare turns are **being spent
walking**, and the walking is not caused by task *eligibility*. The remaining candidate is the
matching itself. That is item ④, and nothing above it is left untested.

### ⚠️ The honest dependency, stated first

**On the tape path, item ④ is not on the critical path.** A donor tape is a fixed action sequence;
it never calls `assign()`. ④ matters for exactly two things:

1. our **own** planner ever reaching the §4.0 profile (1.316 crop tile-days vs our 574), and
2. the **repair layer** that takes over when a tape desyncs (S2: no-ops start day 4-10).

If the tape ships and holds, ④ is what stops it from being a depreciating asset (§4.4#1). It is
the right next build, but it should not block the tape submission. Sequencing is in §6.

---

## 1. Ground rules this item must not break

These are not style preferences. Each one was paid for with a measured failure, and any of them
silently violated turns ④ into another STOP that teaches nothing.

| # | Invariant | Where it comes from |
|---|---|---|
| **G-1** | **`priority` is a hard constraint, never a cost term.** A tier-0 FEED may never be traded for two tier-1 WATERs at any exchange rate | v1o.3: reallocation toward animals loses at our production level *however cleanly implemented* |
| **G-2** | **`committed` stickiness is preserved exactly.** A unit walking toward a still-live task keeps it | pre-C1 oscillation: two units stepping between the same pair of tiles indefinitely, watering nothing |
| **G-3** | **Full determinism (G13).** Same inputs ⇒ byte-identical actions, every run, both seats. Ties broken by the existing `(y, x, unit_index, task.id)` chain, never by dict/set order | the whole gate protocol is paired-seed A/B; nondeterminism voids every comparison |
| **G-4** | **Cargo eligibility is hard.** FEED needs WHEAT in *that unit's* inventory; PLACE needs the animal. Ineligible pairs are absent from the matching, not merely expensive | plan.md §5.1 v1d / G5 — an ineligible unit that "wins" wastes a whole walk |
| **G-5** | **Seed budget is a joint constraint.** *n* PLANT tasks for a crop cannot exceed seeds on hand. The greedy loop enforced this by decrementing mid-loop; a matching decides all at once and must enforce it explicitly | `seeds_remaining` in the current loop |
| **G-6** | **Position exclusivity.** Two units never get tasks at the same tile, except `allowed_unit` tasks which dedup by `id` | review.md M2 |
| **G-7** | **The turn budget is ~1s for the whole submission.** Matching runs 720×/episode | §4.4#6 |
| **G-8** | **Success metric is absolute `worker_turns_working` with `crop_tile_days` flat (±3%).** `worker_turns_moving` is reported, explains, and never decides | §3.4 — v1p1b arm A1 hit the best-ever commute ratio by *doing less work* |

---

## 2. The steps

Eight steps. Each is independently runnable, independently revertible, and ends in a
**decision** — including "stop, this is refuted". Do **one per pass**. Do not start a step before
the one above it has a recorded result.

Steps 1-2 involve **no `agent/` change at all** and can kill the item for the price of two short
passes. That ordering is the whole point: the last five passes each built something first.

---

### Step 1 — ③, the travel-ratio diagnostic *(no `agent/` change)*

**The question this answers, precisely:** of the unit-turns we spend not working, how many are
walks that a *better matching* could have avoided, versus walks that are geometrically forced?

Build `analysis/v1u_travel_ratio.py` on the template of `analysis/v1o3_visit_efficiency.py`. From
existing replays against `meta_route` and `checkpoints/v1o_2`, per episode and per day:

1. `worker_turns_working` / `moving` / `idle`, absolute counts (R17 already puts the first in every
   gate artefact).
2. **The greedy regret.** At each turn, recompute the assignment the greedy loop produced, then
   compute the min-cost matching over the *same* candidate set, and record
   `Σ distance(greedy) − Σ distance(optimal)`. This is offline analysis, not agent code — it is
   allowed to be slow.
3. The distribution of that regret: per turn, per day, and concentrated where? (feed round vs
   crop round; early vs late season.)
4. **Forced-walk floor:** for each turn, the min-cost matching's own total distance. Even a perfect
   matcher pays this. `optimal_total / greedy_total` is the ceiling on what ④ can ever return.

**Pre-registered decision (write it into the report before running the first number):**

- **Regret ≥ 8% of total moving turns** ⇒ proceed to step 2.
- **Regret 3-8%** ⇒ proceed, but the expected return is small; re-scope ④ to the feed round only
  (the subset with the deepest regret) rather than the whole task pool.
- **Regret < 3%** ⇒ ⛔ **STOP item ④.** The commute is a geometric floor, not a matching loss.
  Record it in §3.3 and move the work to territory/tour construction (a different item), or accept
  the tape as the production path and stop trying to reach the profile with this planner.

That last branch is a real outcome and it must be allowed to fire. v1p.2b already said the
constraint is not eligibility; if it is not matching either, the answer is worth more than another
increment.

---

### Step 2 — the offline oracle *(no `agent/` change)*

Only if step 1 passed. Before writing production code, bound the prize.

Take the step-1 regret trace and replay it forward: **what would the episode have looked like** if
every turn had used the optimal matching? Two cheap approximations, both honest about being
approximations:

- **Lower bound:** turns saved = regret / average travel distance ⇒ extra `worker_turns_working`
  ⇒ at the measured ~$1.180 per 574 crop tile-days exchange rate from v1o.3, dollars.
- **Upper bound:** run the real harness with a *slow but optimal* `assign()` (scipy or a plain
  O(n³) Hungarian, no time budget) over SMOKE 0-11, both seats, `--town-pin basket`. This is the
  actual number. It is too slow to submit, and that is fine — this step is measuring the ceiling,
  not shipping it.

**Pre-registered decision:** the oracle must clear **+$3.000/ep** on SMOKE with `crop_tile_days`
flat or up. Below that, ④ cannot survive a real acceptance arm (v1o.2's own accepted increment was
+$4.145 and still failed the priced gate) ⇒ ⛔ STOP.

> This step is what the last five passes skipped. An oracle run costs one pass and tells you
> whether the mechanism is worth *any* engineering. Do not skip it because step 1 looked good.

---

### Step 3 — the cost model, alone, provably inert

First `agent/` change, and it must measure **byte-identical** to `checkpoints/v1o_2`.

Extract the current 9-field lexicographic key into an explicit `_pair_cost(unit, task)` function
and have the existing greedy loop call it. No behaviour change, no new algorithm. Split the key
into the two parts the matching will need:

- **hard fields** — `priority`, cargo eligibility, `allowed_unit`, seeds, position exclusivity
  (G-1, G-4, G-5, G-6). These become *constraints*, never costs.
- **soft fields** — `switching`, `urgency_tier`, `task_slack`, `distance`, and the `(y, x, unit,
  id)` determinism tail. These become the *cost*.

**Gate:** SMOKE 0-11, both seats, basket, vs `checkpoints/v1o_2` — `mean_diff` exactly $0,00, CI
[0,0], ties 12/12, every counter equal. Exactly the byte-inert proof S3 step 2 §1.2 ran for the C2
cleanup. If it is not byte-inert, the refactor changed semantics and the bug is here, where it is
cheap, not three steps later where it is not.

---

### Step 4 — scalarising the cost, alone, still inert-by-construction

A matching needs one number per pair, not a tuple. Turn the soft tuple into a scalar without
changing any decision.

Lexicographic order is preserved by a positional-weight encoding as long as each field's weight
exceeds the maximum total of all lower fields. Bound every field first (distance ≤ 18 on a 10×10
board, `urgency_tier` ∈ {0,1}, `switching` ∈ {0,1}, slack bounded by `episode_steps`), then derive
the weights from those bounds **in code**, with an assertion — a hand-tuned magic constant here is a
silent correctness bug the tests will not catch.

Use integers. Floats reintroduce the tie-ordering nondeterminism G-3 forbids.

**Gate:** same byte-inert proof as step 3, plus a property test asserting
`scalar(a) < scalar(b) ⇔ tuple(a) < tuple(b)` over randomised pairs across the full bounded domain.

---

### Step 5 — the matching itself, behind an off-by-default flag

Now the algorithm. `zone_assignment_enabled` is the precedent: `min_cost_assignment_enabled:
False`, shipped inert, with the live `main.py` re-verified behaviour-identical to its checkpoint.

Implementation notes that follow from §1:

- **Priority is a constraint (G-1).** Do **not** put priority in the cost. Solve **per priority
  tier, highest first**: match tier 0 over all units, remove the matched units, then tier 1 over
  what is left. This makes G-1 structural instead of a weight nobody can audit.
- **Stickiness (G-2).** A committed, still-live pair gets its cost reduced by more than the maximum
  possible distance term — or, cleaner and preferred, is **pinned** before the solve and removed
  from the pool, the same "pin first" shape `_zone_partition` already uses.
- **Seeds (G-5).** Cap PLANT tasks per crop at `seeds_remaining` *before* the solve by keeping only
  the *k* best-keyed PLANT tasks for that crop. Do not try to express it inside the matching.
- **Rectangular pools.** Units and tasks are rarely equal in number; pad to a square with a
  sentinel "no task" of cost strictly above every real pair.
- **Determinism (G-3).** Hungarian is *not* unique under ties, and this is the single most likely
  way to break the gate protocol without noticing. Because step 4's scalar embeds the full
  `(y, x, unit_index, task.id)` tail, exact ties cannot occur between distinct pairs — assert that
  invariant rather than trusting it.
- **No new dependency.** scipy is fine for the step-2 oracle; the submission must stay pure-Python.
  Vendor a ~120-line Hungarian into `agent/matching.py`, or use auction with an integer epsilon.

**Gate:** with the flag **off**, byte-inert vs step 4's checkpoint. With it **on**, nothing yet —
step 5 ships no measurement, only the mechanism. Splitting "the algorithm works" from "the
algorithm pays" is what keeps the next step's result readable.

---

### Step 6 — performance, before any screen

`assign()` runs 720× per episode against a ~1s budget (G-7). Hungarian is O(n³).

Measure worst-case n first (peak simultaneous tasks × units — with 14 hands and a full task list
this is not small), then the per-turn wall clock at that n, on the season's worst turn, not the
average one. If it does not fit:

- solve per priority tier (already the design — each tier's n is much smaller than the total);
- cap the candidate pool to the *k* nearest tasks per unit, with `k` a config knob, and **re-run
  step 3's byte-inert proof at k = ∞** so the cap is a measured approximation with a known cost,
  not an unexamined default;
- auction with integer epsilon-scaling instead of Hungarian.

**Gate:** p99 turn latency inside budget with the flag on, measured, recorded. A submission that
times out scores zero and no local gate can see it coming.

---

### Step 7 — the screen, on the pre-registered criteria

Only now is a number worth reading. The standing protocol, unchanged:

- SMOKE 0-11, both seats, `--town-pin basket` (this changes occupancy), vs a `v1u_base` checkpoint
  **rebuilt on 1.32.7**, regression arm in mirror.
- Pre-register criteria in the report **before the first compare** (§3.1 rule 4).

**Criteria, from §3.4's standing lesson (G-8):**

1. `worker_turns_working` **up in absolute terms**;
2. `crop_tile_days` flat or up, within ±3% at worst;
3. `animals_escaped` inside the ±5 noise floor;
4. `plant_decay_units_lost` still 0 (structural);
5. dollars: IMPROVED or NON_INFERIOR.

**Kill:** any of 1-4 the wrong way ⇒ STOP and record. Note that criterion 1 is the one v1p.2b failed
and v1p1b arm A1 gamed; it is deliberately absolute, and `worker_turns_moving` is reported beside it
without a vote.

---

### Step 8 — acceptance, and only then the profile retry

If step 7 passes: DEV acceptance arm against the **non-mirror** `meta_route` bench (§3.4 — v1o.3
passed mirror at p=3,3e-6 and was worth nothing), then unpinned holdout confirm, then an immutable
checkpoint.

**Only after ④ is accepted** do the things it was supposed to unblock get retested, in this order,
one per pass, each against the new baseline and not against the old one:

1. **herd 13 (9C+4S)** — the S3 step 2 STOP is explicitly conditional on routing throughput, and C2
   (`feed_reserve_horizon="target"`) is already built and sitting inert in `checkpoints/v1s_B0`
   waiting for it.
2. **crew > 10** (deferred item ⑤) — v1o.2's `sw_hands_target` 12 was the best dollars ever measured
   here and died on escapes; more throughput per hand is exactly its precondition.
3. **v1k late-season replant** — §3.3 records it as "on the shelf, not disproved: mandatory re-test
   with the first increment that introduces a crop >$50/tile-day." **D28 may have just created
   one** (§5 below).

---

## 3. Step-by-step summary

| Step | Touches `agent/` | Ends in | Can kill the item |
|---|---|---|---|
| 1 — travel-ratio diagnostic | no | regret %, forced-walk floor | ✅ (<3% regret) |
| 2 — offline oracle | no | $/ep ceiling | ✅ (<+$3k/ep) |
| 3 — cost model extracted | yes, inert | byte-inert proof | — |
| 4 — scalar cost | yes, inert | byte-inert + order property test | — |
| 5 — matching behind a flag | yes, inert when off | mechanism, no measurement | — |
| 6 — performance | yes | p99 latency in budget | ✅ (cannot fit) |
| 7 — screen | yes, on | pre-registered 5 criteria | ✅ (any of 1-4) |
| 8 — acceptance + retries | yes, on | checkpoint, then herd 13 / crew / v1k | — |

---

## 4. What would make me abandon this item

Written now, while it is cheap to be honest:

- step 1 regret < 3%;
- step 2 oracle < +$3.000/ep;
- step 6 cannot fit the turn budget at realistic n even with tiering and a candidate cap;
- **or** the tape (§6) ships and holds above ~2.800, at which point our own planner's production
  ceiling stops being the thing that decides the season, and ④ drops from "the blocker" to "the
  hedge against tape decay."

---

## 5. D28 side-effect: CARROT may now be a real crop *(separate item, do not bundle)*

Engine 1.32.7 moved CARROT's scarcity curve from `log`/0,20 to `hinge`/1,00, and TOMATO/EGG's tails
with it. Measured on **28 live episodes** from `kaggriculture-episodes-2026-08-14`
(`analysis/v1t_engine_probe.py`, results in `data/derived/v1t_engine_probe-2026-08-14.json`):

| Product | median max depletion | p90 | max | price at that max, 1.32.6 → 1.32.7 | episodes draining past the knee |
|---|---:|---:|---:|---|---:|
| CARROT | 228 | 498 | 645 | $42 → **$138** | 5/28 = **18%** (announced 26%) |
| TOMATO | 237 | 336 | 534 | $124 → **$660** | 15/28 = **54%** (announced 50%) |
| EGG | 201 | 390 | 660 | $90 → **$246** | 7/28 = **25%** (announced 22%) |

Two of the three announced rates reproduce almost exactly on our own sample; CARROT reads low at
n=28, which is inside sampling noise, not a contradiction. So the change is real, it bites in a
large minority of episodes, and the top-9 teams grow **zero** of all three — confirmed in
`data/derived/b3_target_profile.json`, whose `tile_days_per_crop` contains only MELON, STRAWBERRY
and WHEAT. We already hold 3 carrot tiles and already sell carrot ($4.709/ep).

That combination — a product where we have supply, the field has none, and the price curve just
went convex — is the first candidate in this repo's history for §3.3's standing v1k re-test
trigger. **It is also not item ④,** and bundling the two would make both unreadable. It gets its own
pass, its own Phase 0, and its own gate, after the tape ships. Recorded here only so it is not lost.

Two things to check in that pass before anything else:
1. selling **into** the spike pushes inventory back up the convex branch, so the price collapses
   faster than it did under the old near-flat curve — the batch-size rule (`sell_ahead.average_rule`)
   matters far more for carrot now than it did;
2. `sell_floor_price["CARROT"] = 5` was sized against a curve that topped out at $42. It is now
   meaningless as a floor. Harmless, but it protects nothing.
