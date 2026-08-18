# Pass brief — S6 step 2d (Track 2): the verbatim trace vs our majority vote

> **Read first:** `baselines/2026-08-18/s6_step2c_report.md` (branch (i), the pass that unblocked this
> one) and `baselines/2026-08-18/s6_step2b_phase05_report.md`; [ROADMAP.md](ROADMAP.md) §3.3's **step 2c
> row** (family closed channel-wide) and its **T2 STOP**; §1 (the **transfer-ratio** row — this pass's
> whole subject — and the converged/decaying curve); **§4.5(b)** (the V16-RC5 method we copied, *including
> the two components we did not ship*); §4.1b; §3.4; **R21 / R27 / R32 / R36**; §2.1.1-5; §6bis; the top
> of [memory.md](memory.md).

## Where we are — and why this pass is a Phase 0, not a ship

**Track 2 is unblocked and correctly selected.** Step 2c fired **branch (i)**: WOOL (0/20 within-step
splits, across a 40%-of-towns zero-yarn population), MILK (0/2, no zero-drain population exists), WHEAT
(fixed-4 variant), MELON (no shop), FERTILIZER (analytically eliminated). The donor's **entire market
layer is a town-invariant schedule the vote already reproduces** — every product's modal volume matches
byte-for-byte (WOOL 200, MILK 296, WHEAT 457, STRAWBERRY 290, MELON 114). The "erased town-conditioning"
family is closed. Under the queued branch, that selects the **verbatim trace** as the challenger.

**But branch (i) also lowers this pass's expected effect size, and the brief has to say so up front.**
If the market layer is faithfully reproduced *and* production transferred whole (Phase 0: volume
286 = 286), then a verbatim trace and the vote differ **only** at the disagreement steps — 127 market +
88 production of 719 — and 2c showed most of the market residual is a **fixed 4-trace submission variant**
{43,45,46,49}, not town conditioning. **A full §2.1.3-5 ladder plus a ship, on a lever whose surface area
has never been bounded, is precisely the T2 error the last four passes have avoided.** So: bound it
first, on the cheapest instrument that can, and ship only if the bound clears.

**And there is a named, documented, never-tested alternative that this pass must not step over.** §4.5(b)
records that the method we copied takes the per-decision majority vote **and then adds worker-count
adaptation and an obstruction-recovery step**. Our own submission description for `55586926` says it
plainly: *"adaptive layer = step 2, **not shipped**"*. We shipped the vote core without the two adaptive
components its source method treats as part of it. Meanwhile **`n_disagree_prod = 88` production steps
have never been examined by any pass** — 2a, 2b, 2b-0.5 and 2c all looked at the market channel. That is
the standing rival hypothesis for the ~1.100 points, and leg A tests it for free.

## The one question

> **Does the majority vote's averaging cost anything measurable against the donor's own actions — and if
> so, is the cost in the stream at all, or in the adaptive layer we never shipped?**

## Phase 0 — four legs, cheapest first, each with its own exit

**Leg A — the 88 production disagreement steps (free, desk, zero episodes).** Run the step 2c instrument
(`analysis/s6_step2c.py`) on the **production** channel: `farmer`/`hands` actions at the 88 steps where
the 50 traces disagree. Same five instruments. The question is the same one WOOL answered for the market
side: is the residual the **fixed 4-trace variant**, or does it move with something the town does —
**weed spawns, obstruction, harvest timing, worker count**? Note the engine gives `weedSpawnChance` a real
per-town realisation, and our live route carries `unexpected_weeds` 5/ep and `plant_decay` 15/ep (R32,
~$2,8-3,1k/ep summed) — so a town-reactive production rule is *mechanically plausible here in a way it
was not for a hour-0 market calendar.* **If the 88 steps are town-reactive, the vote erased an adaptive
production rule and this pass has found the thing four passes have been looking for.**

**Leg B — price the gap in dollars, drain-matched, from replays already on disk (free, desk).** Nobody
has ever decomposed the **total bank** gap; Phase 0 did it only for strawberry $/u. The donor's recorded
final bank is in every replay (`replay["rewards"]`, both seats). Compare the donor's 50 traces against our
85 live `55586926` episodes, **matched on observed drain** the way Phase 0 matched it (4,0 = 4,0), and
decompose the difference into: per-product units × realised $/u, and the R32 loss ledger (weeds, decay,
overflow, escapes) priced per counter. **State where the donor is ahead of us in dollars, in a comparable
town.** ⚠️ Two caveats to carry, not bury: the opponents differ (match opponent quality as Phase 0 did,
and say so), and **`configuration.seed` is `None` in every replay** — verified this session — so *the
donor's town cannot be re-run*. Drain-matching is the only same-town-*like* control available at the desk;
a true same-town control needs leg C's both-seats design.

**Leg C — the head-to-head, SMOKE only (cheap, ~24 episodes).** Play **tape(verbatim trace) at one seat
against the vote at the other, in the same episode, both seats, SMOKE 0-11** —
[analysis/tape_agent.py](analysis/tape_agent.py) plus the 50 traces under `data/archive/raw/2026-08-16/`.
This is the only exact same-town control that exists here, and it is the direct measurement the §1
transfer-ratio row has been asking for since 08-18. Run **two** tapes: one drawn from the **46-trace modal
set**, and one from the **{43,45,46,49} variant** — the variant is the single known behavioural difference
in the donor population, so it is the free contrast. **Stop at SMOKE.** Do not proceed to DEV or holdout
inside this leg.

**Leg D — the ladder and the ship.** The original Track 2: full §2.1.3-5 (DEV vs the non-mirror bench →
unpinned holdout 100-147, both seats) and the §6bis checklist. **Gated on leg C, and not started
otherwise.**

## Kills / branches, pre-registered before any leg runs

- **(i) Leg C's SMOKE margin is within noise** (no consistent sign across both seats, |mean_diff| below
  the bench's own seat-to-seat spread) ⇒ **the stream is excluded as the location of the gap.** That is a
  real result, not a null: combined with 2c it says neither the market layer nor the vote's averaging
  costs us the 1.100 points. **Do not ship the tape. Stop, and the next brief is the adaptive layer**
  (§4.5b's worker-count adaptation + obstruction recovery, informed by leg A).
- **(ii) The verbatim tape beats the vote consistently at SMOKE, both seats** ⇒ the averaging *is* the
  loss. Proceed to leg D, and report leg A's finding alongside — if the win concentrates at production
  steps, the shippable thing may be the adaptive rule rather than a frozen trace.
- **(iii) The vote beats the verbatim tape** ⇒ the vote is doing its job and the 50-town mode is an
  asset, not a lossy average. Close Track 2, keep `55586926`, and go to the adaptive layer.
- **(iv) Leg A finds the 88 production steps town-reactive** ⇒ that outranks legs C/D regardless of their
  outcome. **Report it and re-brief; do not build it this pass** (the Phase 0.5 discipline: recover and
  bound, then stop).
- **(v) Leg B's drain-matched decomposition puts the dollar gap in a channel legs C/D cannot reach**
  (e.g. entirely in loss counters, or entirely in opponent quality) ⇒ say so plainly and let it redirect
  the pass; a measured redirection is the point of running the cheap legs first.

## Standing conditions

**No `agent/` change.** Legs A and B run **zero episodes**; leg C runs SMOKE only. **No upload unless leg
D is reached and the user says so — the upload is the user's call and a prerequisite, not a consequence
(R27).** Routes, packages, replays and derived data stay **gitignored** (§2.4b / R11); derived artefacts
carry the **verdict string** (R35). Guards in `tests/`. Competitor notebook source untouched (§2 item 8).
R21 (realised shop draw per seed set) and R32 (per-episode loss ledger, unpriced counters listed) apply to
every episode-running leg. Report to `baselines/<date>/`, `memory.md` entry, commit with no co-author.

**If leg D is reached, the upload economics:** eviction is by date and the oldest active is `55575305`
(Ueddy, **1.372,6**) — our weakest, so the eviction is near-free; the pair would become
{vote `55586926`, verbatim tape}. §6bis warns against two near-identical actives, and after 2c we know
these two differ only at the disagreement steps — **raise that with the numbers before uploading.**

**The clock, stated correctly.** The final ranking is one Bradley-Terry tournament over **post-deadline**
episodes, so today's drifting **1.886,8** (1.915,8 → 1.906,5 → 1.886,8, `LastSubmissionDate` unchanged) is
a **predictor, not the score**. What is scored is the strength of the active pair on **2026-09-30** — 43
days out. Re-uploading the same route does not undo the drift; a fresh submission simply re-converges to
its current fair value. Budget roughly 2-3 days per converge-and-read, two active slots, eviction by date.

## The standing unexplained fact (R36, submission-level)

Leaderboard **2026-08-18 14:36 UTC**: **ReCurSiON 2.989,4**, `LastSubmissionDate` frozen **08-14 14:14**
— the exact submission we reconstructed — against our **55586926 at 1.886,8**. ~1.100 points, live, same
pool, between the donor's route and our 50-town average of it. Both sides are the rating of one specific
submission, so this is quoted at submission level and **no band-crossing conclusion is drawn from it**
(R36). Two passes have now excluded the market layer as its location. Carry it into the report whichever
branch fires.

## Out of scope

- **Any market-layer overlay.** ⛔ Closed channel-wide by 2c (§3.3). Strawberry, WOOL and MILK included —
  WOOL's ~$1.202/ep whole-episode drift is **bounded and shelved**, not a lever to revisit this pass.
- **Arms A/B/C of step 2b** ⛔ refuted · **step 2a's wheat repair** ⛔ on the shelf · **C-A** ⛔ refuted ·
  **C-C (MELON)** still last.
- **Building the adaptive layer.** If leg A points there, this pass **reports and re-briefs**. Recovering
  and bounding a mechanism, then stopping, is what the last four passes got right.
- **A donor swap**, **RL**, **planner refinement** — unchanged.
