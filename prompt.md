# Pass brief — S6 step 0: bound the lever before building anything

> **Read first:** [ROADMAP.md](ROADMAP.md) **§4.1b** (the whole basis of this pass), §4.3 **S6**
> steps 0-2, §4.5 (what the two new sources are for), §3.3's **T2 row** and its 2026-08-17 widening,
> §3.4 (the cross-entity-comparison lesson), **§6bis slot mechanics**, R21/R25/R26; the top two
> entries of [memory.md](memory.md); and `baselines/2026-08-17/v1v_shop_demand_report.md`.

## Where we are

§4.1b measured, on 150 top-ladder episodes / 300 seats at engine 1.32.7, that **99-100% of the
realised-price spread on STRAWBERRY / WOOL / MILK is the town's random shop draw**, not the agent.
That withdrew S5. What replaced it is the thing the same measurement found: **the top of the ladder
is a mirror match** — both seats sell the same basket in the same volume in 150/150 episodes — and
the winner's entire edge is a **1,04-1,06× realised price**, worth a median **$2.826** bank gap.
A **+5%** premium edge is **+$3.596/ep** and reaches **52,7%** of currently-lost episodes.

We field two verbatim donor tapes with **no market layer of our own**. S6 proposes to build one.
**This pass does not build it.** It measures whether there is anything to build.

## The one mechanism, stated so it can be refuted

> **Our shipped tape's market queue is frozen at its donor's ordering, so its per-turn SELL slot
> order is whatever the donor happened to emit, and it cannot condition on the town. If that costs
> realised price, the tape sits *below* 1,0× against a same-town opponent running the same route.**

T2 spent a whole pass on a lever whose size it never bounded first. That is the mistake this brief
exists to not repeat.

## What to measure — three legs, in this order

### Leg 1 (mandatory, and it can end the pass) — the same-town control

§4.1b's central finding is that comparing realised $/unit **across** episodes measures the town.
The controlled comparison is **the two seats inside one episode**. So:

Replay each tape against a same-route opponent, **both seats**, and for each episode record both
seats' realised $/unit on STRAWBERRY / WOOL / MILK **and that episode's shop drain**. Report the
tape's ratio against its same-town opponent, per product, with the distribution — not just a median.

The opponent must be **another meta-line agent**, because the 1,04-1,06× figure was measured between
two agents both running the meta line. That is **R26** and it is part of this pass: wrap the three
extracted donor tapes as bench opponents with `analysis/tape_agent.py::make_tape_agent` (already
built — a parameterised callable, so it is used programmatically, not file-path-loaded). The routes
are already on disk, gitignored, at **`baselines/2026-08-16/tape_submissions/{91456307,90999409,
90891564}_seat0`** (Valmorlee / Ueddy / Kaito). They stay there (§2.4b / R11).

*Also* run against `meta_route` and `checkpoints/v1u_base` so the figure is not one pairing.

**Kill:** if a tape already sits at **≥1,05×** against same-town opponents on all three products,
the mechanism above is **refuted** — the queue ordering is not costing us realised price. Stop,
write it up, and do not build C-A or C-B. That is a real result and the pass succeeds by producing
it.

### Leg 2 (mandatory) — the surface area of the C-A rule

C-A (the Cleo rule) reorders SELL orders **within the slots the plan already used for selling**. It
cannot change quantity, timing, or which slot holds a purchase. So its entire surface is turns where
the tape emits **two or more SELL orders**, of which at least two are different products with
different curve positions.

Measure, per tape, directly from the route:

1. Turn-by-turn histogram of SELL orders per turn. **How many turns emit ≥2 sells?**
2. Of those, how many mix a **premium** product (STRAWBERRY / WOOL / MILK) with a non-premium one,
   or two premiums — i.e. how many are actually reorderable into a better queue position?
3. The **realisable** upper bound: for each such turn, price the best legal permutation against the
   emitted one, using the engine's own curve at that turn's inventory. Sum over the season.

**This is a paper calculation on a recorded route — no episodes needed, and it is cheap.** If the
answer is "the tape emits ≥2 sells on 11 turns and the best permutation is worth $180/ep", C-A is
dead before a line of it is written, and we learn that for an afternoon rather than a pass.

⚠️ Do **not** let leg 2's upper bound stand in as leg 1's answer. Leg 2 bounds *one candidate
rule*; leg 1 asks whether there is a deficit at all. Both are needed and they can disagree.

### Leg 3 (cheap, and it de-risks C-B) — is the town readable in time?

C-B conditions on `obs.town.unlocked_shops`. Shops unlock one every 3 days, capped at 8, so the
town is **not** fully known until ~day 24 (§4.1b), while the sell calendar starts on day 2-6 (§4.0).
Measure when the draw becomes decision-relevant: per episode, at which day is the *rank order* of
STRAWBERRY / WOOL / MILK drain stable for the rest of the season? `agent/planner.py` already gates
on `shop_evidence_min_unlocks` (default 5) — check whether that threshold is early enough to matter
or so late that C-B can only act on the last third of the season.

## Gate and reporting

No `agent/` change. No submission. `pytest tests/` green (304, plus the 3 known
artefact-dependent `test_v1h2d_*`).

- **Both seats on everything** (§2.1.1).
- **R21 is binding**: report the seed set's realised shop-draw distribution next to every dollar
  figure. The first `ladder` run already found seeds 0-3 sampling WOOL zero-drain in **27/56**
  episodes (48% against the population's 34%) — a small-seed screen here is confounded by default.
  Use enough seeds to span the draw, and say which draws you got.
- **Report in the ladder's currency too**: `python -m harness.cli ladder` (R22), with the A2 tape
  bench and `--round-robin`, so the result is comparable to the thing we are judged on.
- **§2 item 9**: state the confirmed mechanism and the viable increment **separately**, in that
  order. A measured deficit is not an increment.
- Price any claimed gain against §4.1b's own scale — **+1% premium price = +$719/ep**, median gap
  **$2.826** — and **do not** apply the $253/ep marginal rate (§3.4's amendment: this is a change
  to *which* episodes you win, which is the regime the rate explicitly does not cover).

## Also worth doing in this pass (cheap)

**R25** — fetch the six tier-0-5 reference agents into a **gitignored** local bench directory and
add them to the bench resolution path. MIT, original work, and they are the graded regression rungs
S6 step 2 needs. **Do not** fetch tiers 6-9 (R23: skipped by decision) and **do not** vendor the
dataset's CSVs (CC BY-SA, §4.5).

## Standing conditions

Provenance (episode id, seat, team, sha256) stays in the checkpoint ledger and any submission
description; extracted routes stay **gitignored and out of this public repo** (§2.4b / R11);
competitor notebook source is still never opened, decompressed or executed (§2 item 8).

**⚠️ R27 — do not upload anything this pass.** Eviction is by submission **date**, not score: any
upload today drops **Valmorlee (1.617,6)**, our best. And Ueddy is still converging (7 episodes from
600,1), so which tape is "the top tape" is not yet decidable — it needs a same-day read.

## Out of scope

- **Building C-A, C-B or C-C.** This pass decides whether they are worth building.
- **Any `agent/` production change.** Item ④ is closed; the planner is not the product.
- **The herd-13 / routing family** (§3.3) — closed, and none of it is on S6's path.
- **MELON (C-C).** It is a production change, it rides behind a route we control, and it is
  deliberately sequenced last.
