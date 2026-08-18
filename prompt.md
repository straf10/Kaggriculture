# Pass brief — S6 step 2b: restore the sell-timing the vote erased

> **Read first:** [ROADMAP.md](ROADMAP.md) §4.3 **S6 step 2b's Phase-0 GO and the second read below it**
> (the spec for this pass); §1 (the converged curve, the transfer ratio); **S6 step 0 leg 3** — the town
> *readability* measurement, which bounds this build and is not in the Phase-0 report; §4.1b **and** the
> Phase-0 report's reconciliation of it; §3.3's **T2 STOP** (the last time we tried to meter a premium
> product); §3.4; **R21 / R27 / R32 / R17 / R36**; §2.1.1-5; the top of [memory.md](memory.md); and
> `baselines/2026-08-18/s6_step2b_phase0_report.md`.

## Where we are

**Phase 0 cleared its gate and located the whole gap in one number.** On 85 of our own live episodes,
both seats, real towns: our same-town STRAWBERRY realised-price ratio is **1,010** against the donor's
recorded **1,339**. With town-drain matched (4,0 = 4,0), opponent quality matched ($89,5 ≈ $89,9) and
**volume identical (286 = 286)**, ReCurSiON extracted **$117,4/u where we get $90,1/u** — the modal field
price. We copied the production whole and lost the sell-timing. **Lever: ~+$7.833/ep on strawberry
alone**, against a median winning margin of **+$1.076** in the band we contest.

The route itself is healthy: 57-28, and unlike the v1h agent §3.2 profiled it **does not shut down** —
the bank gap grows all season to +$4.515 by d28. Production desync is ~$0. Tier-0 loss is ≤$599/ep, ~13×
smaller. Decay is now measurable but small: the curve reads (85, 1.915,8) → (88, **1.906,5**),
`LastSubmissionDate` unchanged — **converged and drifting down slightly.**

**Two Phase-0 claims were deflated on second read and you should not build on them:** the
"many hundreds of rating points" figure is a guess (the dollars are measured, the conversion is not), and
the opponent-rating band table mislabels its axis (R36), so *"the lever opens the 2500-3000 band"* rests
on n=3. Quote dollars; let the ladder price the points.

## The one mechanism

> **The majority vote replaced ReCurSiON's town-conditioned strawberry sell-timing with the modal
> action at the 127/719 (17,7%) state-dependent market steps, reverting our realised price to the field
> median.** Restoring conditioning at those steps is the increment.

## ⚠️ Phase 0.5 — recover the donor's actual rule before designing one (paper, no episodes)

**Do not invent a metering heuristic.** We hold the 50 traces *and* their observations, and the
disagreement set is already computed — so the rule can be **recovered** rather than guessed. This is the
single highest-value step in the pass and it is free.

1. **At each of the 127 state-dependent market steps, what predicts the donor's deviation from modal?**
   Regress / tabulate the donor's action against observables available *at that step*: own inventory and
   its age, the product's current realised price and the price it just cleared at, cumulative units sold,
   the opponent's recent sells, day/turn index, bank, and `obs.town.unlocked_shops`. Report which features
   carry it and how much of the 127 steps each explains.
2. **🔴 The crux, and it decides whether the lever is reachable at all:** does the rule condition on
   **shop identity** (the town's drain) or on **own observable state** (inventory/price/day)? Step 0's
   **leg 3** measured that a town's premium drain rank is stable only from **median day 15**, that all 8
   shops are known only by **day 24**, and that STRAWBERRY's rank is readable by its first-sell day (14)
   in **only 43% of episodes**. So:
   - shop-identity conditioning ⇒ the achievable fraction of $7.833 is **capped near ~43-60%**, and the
     brief must say so before any arm is built;
   - own-state conditioning ⇒ observable from step 0, no readability cap, and the lever is fully
     reachable. **Report which it is, with the measurement.**
3. **State the surface area you will actually claim** (§3.4): $7.833/ep × the reachable fraction, and note
   it is a ceiling *against the pool we currently meet* — the skim is **zero-sum**, so opponents who also
   condition will not concede it (see the second read's point 3).

**Gate:** if the recovered rule turns out to need state we cannot observe in time, say so and report the
capped figure — that is a result, and it reshapes the arms rather than stopping the pass.

## Build — one mechanism per arm, and expect to reject most

Candidate arms, each a single mechanism, ordered by what Phase 0.5 finds:

- **A — restore the recovered rule at the 127 steps**, verbatim from the donor's own decision function.
  The primary arm: it is the measured policy, not a designed one.
- **B — strawberry-only metering into the observable demand window** (the §4.5b premium-lead shape),
  as the fallback if A's rule needs unobservable state.
- **C — the same rule gated to fire only when its conditioning state is actually readable** (leg 3's 43%).
  The control that separates "the rule works" from "firing it blind is harmful".

⚠️ **§3.3's T2 STOP is the named prior risk and it is not hypothetical.** The last attempt to meter
strawberry on a route overflowed the shed (`shed_overflow_burnt` 0→31-89), burnt WOOL, and starved FEED
(`animals_escaped` 0→11) for a **−$3-4k/ep** net. This route has the headroom T2's tape lacked (peak
72/100, never ≥90) — **but that was measured on the *unmetered* route.** Metering re-adds inventory.
**Re-measure shed occupancy on every arm and treat a rise toward 90 as a kill, not a cost.**

**Test discipline (§2.1.1-5):** both seats on everything · `--town-pin basket` for anything touching
occupancy (metering changes harvest/hold timing — treat as occupancy) · **SMOKE 0-11 → DEV acceptance vs
the non-mirror bench → unpinned holdout 100-147** · **R21** realised shop draw printed per seed set (this
is a market-layer change and §4.1b makes the town the dominant confounder; the draw must span the ~34-41%
WOOL zero-drain population) · **R32** per-episode loss ledger with unpriced structural counters listed ·
**R17** absolute `worker_turns_working` with `crop_tile_days` within ±3%.

**And measure the lever against strong opponents specifically**, not only the tapes: the reference-ladder
top rungs plus the reconstruction itself as a mirror opponent. If the gain evaporates against an opponent
that also skims, that is the most important number in the pass.

## Kill, pre-registered per arm

- **(i)** Realised strawberry $/u does not move **against the same-town control** ⇒ the arm has missed the
  only thing it was built for. **Stop, do not tune.**
- **(ii)** `shed_overflow_burnt` rises off zero, or shed occupancy approaches 90/100 ⇒ T2's wall; reject.
- **(iii)** The arm moves realised $/u but not `median_bank` ⇒ confirmed mechanism, **not** a viable
  increment (§2 item 9). Record it as v1o.3's variant E was, and reject.
- **(iv)** Any structural hard-zero counter breaks (`clipped_production_ticks`, market-sim aborts,
  unexplained no-ops), or `crop_tile_days` falls >3% ⇒ STOP.

## Freeze, then the endgame

At most **one** arm survives to an immutable checkpoint. Then, in order: **S6 step 4** — re-validate on
the strictly later 08-18+ daily datasets (never run, and non-optional for anything we freeze until 09-30);
then the upload decision.

⏸️ **The upload is the user's call and it is a prerequisite, not a consequence (R27).** The next upload
evicts the **Ueddy tape** and leaves {reconstruction, reconstruction + overlay} — two near-identical
actives, the pattern §6bis warns kills both on a meta shift. **Raise it at the start of the shipping pass
with the numbers, and stop for the answer.** Note the calendar: **43 days to 2026-09-30**, ~1 day per
upload to converge, and the prize is decided by a Bradley-Terry tournament over **post-deadline** episodes.

## Standing conditions

No `agent/` production change beyond the market layer this pass targets. Routes, packages, the 2,5 GB of
live replays and all derived data stay **gitignored** (§2.4b / R11). Competitor notebook source is never
opened (§2 item 8). Write the report to `baselines/<date>/`, add a `memory.md` entry, commit with no
co-author.

## Out of scope

- **A donor swap.** カワシギ (#1) and Tschinkel (#2) stay rejected on reconstructibility — and the transfer
  evidence now says the better the donor the *less* copyable it is.
- **C-C (MELON)** — still last · **C-A** ⛔ refuted · **step 2a's wheat repair** ⛔ on the shelf ($0 free).
- **RL and planner refinement** — both refuted for this competition on the calendar and on BT 1.952 vs
  3.317 respectively; see the §5 trigger's ≥3-weeks clause.
