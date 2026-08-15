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

### Step 1 — ③, the travel-ratio diagnostic *(no `agent/` change)* — ✅ **RUN 2026-08-15: PROCEED, re-scoped**

> **Result: greedy regret = 4,30% of moving turns** (5.720 walk-steps / 133.026, ≈159/ep), over 36
> episodes / 25.884 turns, engine 1.32.7, both seats, basket-pinned. Lands in the pre-registered
> **3-8% band ⇒ proceed, re-scoped to the feed round only.** The STOP branch did not fire.
> Report: `baselines/2026-08-15/item4_step1_report.md`. Script:
> [analysis/v1u_travel_ratio.py](../../analysis/v1u_travel_ratio.py).
>
> **The four numbers that now drive everything below:**
> 1. **Forced-walk floor 0,9631** — a perfect per-turn matcher still pays **96,3%** of the commute.
>    **≤3,7% is the hard ceiling ④ can ever return**, forever, by matching alone.
> 2. **Concentration:** 82,8% of absolute regret is in the **feed round**; **86,3% sits in the worst
>    5% of turns**. The prize is a thin slice, not a broad inefficiency.
> 3. **Cardinality gap ≈ 0** — a legal max-cardinality matcher completes **4 more tasks across all
>    36 episodes**. Greedy is already effectively a maximum matching ⇒ **④ buys efficiency, never
>    throughput.** Any hypothesis of the form "greedy strands tasks" is dead.
> 4. **The frame is load-bearing.** A pure-distance optimum reads ~25,7%, but it buys that saving by
>    ignoring the urgency/slack ordering that encodes FEED deadlines — i.e. by missing them. The
>    conservative re-match optimum (same served set, pins preserved, only the pairing changes) is
>    4,30%, and that is the achievable figure.
>
> Two methodological points worth carrying forward: the diagnostic **captured** the per-turn
> `(tasks, snapshot, committed)` triple by wrapping `agent.policy.assign` in-process rather than
> reconstructing it from replays (a bare replay records actions, not the candidate set), and the
> greedy reconstruction was **asserted equal to the real `assign()` on all 25.884 turns, 0 voids**.
> That machinery is reusable and is why step 2 is cheap.

### Step 1 — as originally specified *(kept for the record)*

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

### Step 2 — the offline oracle *(no `agent/` change)* — **revised 2026-08-15 after step 1**

Run the real harness with a *slow but optimal* `assign()` (scipy, no time budget) over SMOKE 0-11,
both seats, `--town-pin basket`, against a `v1u_base` checkpoint **built on 1.32.7**. Too slow to
submit; this step measures the ceiling, not the product.

**Three arms, run in this order, stopping as soon as one settles it:**

| Arm | What it is | Why |
|---|---|---|
| **A — whole-pool optimal** | per-tier min-cost matching over the full pool, every turn | the **strict ceiling**. Every other arm is bounded by it, so if A misses, nothing else can clear |
| **B — greedy + 2-opt repair** | keep greedy, then pairwise-swap task assignments between units, accepting only strict improvements | **possibly the actual product** — see below |
| **C — feed-round only** | arm A restricted to the feed round | step 1's mandated re-scope (82,8% of regret) |

Order matters: **A first.** If A misses the bar, B and C are provably worse and the pass ends there.

> **Why arm B is new, and why it may matter more than A.** Step 1 found the cardinality gap is ≈0
> and 86,3% of regret sits in 5% of turns. A full Hungarian on every one of 720 turns to fix a
> handful is disproportionate. A pairwise-swap pass over greedy's output is O(n²), preserves every
> constraint **by construction** (only swap between two units both eligible for both tasks), is
> trivially deterministic, needs **no solver and no new dependency**, and on a concentrated regret
> distribution typically recovers most of it. **If B lands close to A, steps 5-6 collapse** — no
> vendored Hungarian, no O(n³) budget problem, no candidate cap. Measuring it costs one extra arm in
> a pass that is already set up.

#### The kill criterion — **two-legged**, and the second leg is the point

The original single bar (**+$3.000/ep standalone**) was wrong, and step 1's numbers show why. Bound
the prize from step 1: ≈159 walk-steps/ep ⇒ at most ≈159 extra working turns (+11,6%) ⇒ at our crude
0,42 crop-tile-days per working turn and v1o.3's ~$31/crop-tile-day, **≈+$2.100/ep — already under
the bar before any implementation loss.** A single-leg test would therefore kill ④ almost
regardless of what arm A returns, which makes the pass a formality rather than a measurement.

That is the wrong test, because **④'s value was never mostly its own dollars.** §0 says it plainly:
④ exists to make the §4.0 profile reachable, and the nearest blocked thing is **herd 13, which is
−$15-21k/ep purely on feed logistics** (S3 step 2) — and step 1 just measured that 82,8% of the
recoverable regret is *in the feed round*. That is the same currency the herd-13 STOP is denominated
in. So:

**PROCEED to step 3 if EITHER leg clears:**

- **Leg 1 — standalone value:** arm A (or B) returns **≥ +$2.000/ep** on SMOKE with `crop_tile_days`
  flat or up (±3%) and `animals_escaped` inside the ±5 noise floor. *(Lowered from +$3.000 because
  the bar's job is to detect a real effect, not to demand that a routing fix pay for itself twice —
  ④ is a precondition, not a standalone increment.)*
- **Leg 2 — the unblock:** the oracle measurably relieves the feed round. Pre-register the metric
  before running: **feed-round saturation** (share of day-hours with ≥1 animal `fed_today=False`,
  currently **100% from d9** — §3.3) and **`animals_underfed_days`**. Leg 2 clears if saturation
  drops below **90%** on the median day from d9, *or* `animals_underfed_days` falls ≥15%.

**⛔ STOP item ④ if BOTH legs miss.** Then the honest conclusion is recorded in §3.3: the commute is
a geometric floor (96,3%), the residual is real but too thin to pay, herd 13 stays blocked, and
reaching the §4.0 profile with this planner is **refuted** — which promotes the tape (§4.2) from the
production route to the *only* route, and ④ closes for good.

> **Optional, cheap, and worth it if leg 2 clears:** re-run the herd-13 arm H2R from S3 step 2
> *under the oracle*. That is the direct test of the only claim that makes ④ worth building, and the
> arm already exists at `checkpoints/v1s_H2R`.

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
- **Build whichever arm won step 2.** If arm B (greedy + 2-opt) landed close to arm A, build **B** —
  it needs no solver, no vendored Hungarian and no candidate cap, and its constraint-safety is
  structural rather than encoded. Do not build the more impressive mechanism because it is the more
  impressive mechanism.
- **Hot-turn gating (from step 1's concentration finding).** 86,3% of regret sits in 5% of turns, so
  the matcher does not need to run every turn. Gate it on a cheap predictor — e.g. more than *k*
  units idle-or-switching, or a tier-0 task whose nearest eligible unit is beyond distance *d* — and
  fall back to plain greedy otherwise. This is the main lever for G-7, and it is measured, not
  guessed: the gate's own recall against the step-1 regret trace can be checked offline before any
  agent code runs.

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
| 1 — travel-ratio diagnostic ✅ **DONE** | no | **4,30% regret, 0,963 floor ⇒ PROCEED, feed-round re-scope** | ✅ (<3%) — did not fire |
| 2 — offline oracle (arms A/B/C) | no | $/ep ceiling **and** feed-round relief | ✅ (both legs miss) |
| 3 — cost model extracted | yes, inert | byte-inert proof | — |
| 4 — scalar cost | yes, inert | byte-inert + order property test | — |
| 5 — matching behind a flag | yes, inert when off | mechanism, no measurement | — |
| 6 — performance | yes | p99 latency in budget | ✅ (cannot fit) |
| 7 — screen | yes, on | pre-registered 5 criteria | ✅ (any of 1-4) |
| 8 — acceptance + retries | yes, on | checkpoint, then herd 13 / crew / v1k | — |

---

## 4. What would make me abandon this item

Written now, while it is cheap to be honest:

- ~~step 1 regret < 3%~~ — **did not fire: 4,30%**, in the 3-8% "proceed but small" band;
- step 2: **both** legs miss (< +$2.000/ep standalone **and** no measurable feed-round relief).
  On step 1's arithmetic the standalone leg is the more likely of the two to miss — the naive
  ceiling is ≈+$2.100/ep before implementation loss — so **leg 2, the herd-13 unblock, is where this
  item actually lives or dies**;
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
