# Pass brief — S6 step 1b: package, gate and field the reconstruction

> **Read first:** [ROADMAP.md](ROADMAP.md) §4.3 **S6 step 1's result block, the second-read
> evaluation, and the step 1b section** (they are the spec for this pass); §1's new
> **donor-cross-check** row; §3.4's new **R30** lesson; **§6bis** in full — the pre-upload checklist,
> the two slot traps, and the eviction block; **R27 / R28 / R30 / R31**; §4.2's three mandatory
> conditions; §2.1.3-5; the top of [memory.md](memory.md); and
> `baselines/2026-08-17/s6_step1_phase0_report.md`.

## Where we are

Step 1 Phase 0 succeeded: **we own a modifiable route.** A majority-vote reconstruction of **ReCurSiON**
over 50 traces reproduces recorded banks to **0,12%**, carries a calendar **≥ the Valmorlee tape's**
(WOOL +23%, MILK +7%, STRAWBERRY a tie), holds **~28 units of shed headroom** where the tape ran at
98/100, and beats all three incumbent tapes **24-0-0** on SMOKE (+$14.267/ep vs Valmorlee).

Then the evaluation pass ran the one call Phase 0 had not, and it re-ordered the plan:

> **ReCurSiON is #4 on the public leaderboard at 3.004,6.** Our shipped best is **1.621,5**. And the
> tape's donor, **Valmorlee, is #1018 at 1.842,4** — our 1.617,6 tape was already at **88% of a
> ceiling nobody had looked up.** A *pure* frozen tape (Peter Parker, 1 distinct market stream in 12
> traces) holds **#29 / 2.844,2**, so the format was never the limit; **the donor was.**

So the asset built last pass has a surface area of roughly **+1.383 rating points** — the §1 **3000**
gate — and it is **not fielded**. Step 2's entire ceiling is **+$1.912/ep** on top of it. **Shipping
comes first.** That is this pass, and it invents nothing: it puts an existing artefact through the
protocol.

## Surface area, stated up front (§3.4 / R30)

- **Ceiling:** the donor's own **3.004,6**. A faithful reconstruction cannot exceed it.
- **Floor that matters:** the **1.842,4** donor-ceiling class our current product belongs to.
  **1.9k-3.0k is a result. Below ~1.6k it has not beaten the thing it replaces.**
- ⚠️ The 3.004,6 is the *team's* leaderboard score and its `LastSubmissionDate` is **08-14**, which
  precedes the 08-16 episode dataset — so the traces are that generation (this is why the check is
  valid here and would not be for Ueddy/カワシギ/Tschinkel, all 08-17). State that caveat, don't drop it.

## What to do, cheapest-first

1. **One submission, or two?** (R31 — the report's one unsupported claim.) The opening fingerprint is
   dead as a submission test: 87% of the field shares it, and ReCurSiON's 50 traces carry **50 distinct**
   `fp_market_full` / **16 distinct** `fp_prod_full`. Paper check, no episodes: 2-cluster the 50 traces
   on pairwise market-decision distance and show **one** mode. If it splits, re-vote per cluster and
   carry the larger one forward — a blend of two policies measures neither.
2. **Package** the majority-vote route as a self-contained `main.py`, exactly as T1/T2 were, under the
   **gitignored** `baselines/2026-08-17/tape_submissions/`. Full provenance (team, all 50 episode ids +
   seats, per-trace sha256, per-channel agreement, the majority-vote rule itself) in the checkpoint
   ledger and in the submission description. §4.2's three mandatory conditions apply unchanged.
3. **BT over the graded bench** (R28's new rung, now measurable because item 2 produces a file path):
   `python -m harness.cli ladder --round-robin --shop-draw` against A1 tiers 0-5 + the three tapes +
   `v1u_base` + `meta_route`. Report the **per-seat split** (§2.1.1) — a route that only wins from seat 0
   has a market-ordering dependency, not a strength.
4. **Gate it properly.** SMOKE 0-11 → **DEV acceptance against the non-mirror bench** → **unpinned
   holdout 100-147** → immutable checkpoint. The incumbent for the comparison is the **raw Valmorlee
   tape**. Two things the last pass owed and this one must pay:
   - **R21 for every seed set, including the bank sweep** — the 24-0-0 headline never had its realised
     shop draw printed, and it is the number the ship decision rests on.
   - **R13/§2.1.5** — declare a mechanism for every counter that *can* be non-zero (the headroom
     predicts `shed_overflow_burnt` ≈ 0 unpinned; verify rather than assume), and price, never floor.
5. **§6bis pre-upload checklist, all of it:** G12 loader contract · cold-process timing both seats
   (`max_turn × 3 < 1s`) · G13 determinism under two `PYTHONHASHSEED` values · mirror smoke
   `clean=True` · size · `pytest tests/` green (**326** now; the 3 `test_v1h2d_*` are the known
   pre-existing failures).
6. ✅ **Ship it — the eviction is already decided (user, 2026-08-17): accept losing Valmorlee
   (1.614,0).** R27 is satisfied; you do not need to re-ask. The resulting active pair is **{Ueddy tape
   `55575305`, ReCurSiON reconstruction}**, differentiated in premium mix (Ueddy the milk specialist,
   ReCurSiON broad) — the only differentiation still available now that 87% of the field shares one
   production line. **Three conditions on that authorisation, all binding:**
   - It is **conditional on the gate**. Kills (i) and (ii) stop the upload. If either fires, report and
     ship nothing — the authorisation covers a package that cleared §2.1.3 and §6bis, and nothing else.
   - **Full provenance in the submission description** (team, majority-vote rule, agreement rate) —
     §4.2's mandatory condition, not optional.
   - After the upload, **read the score on the same day as the Ueddy tape's** (§1's decay caveat) and
     record both, plus the convergence curve — T1 took ~1 day from 600,1. That reading is kill (iii).
   - It does **not** carry to step 2, whose upload evicts the **Ueddy tape** and would leave two
     near-identical actives. Raise that at the *start* of step 2 (§6bis).

## Kill, pre-registered

- **(i)** The reconstruction misses the §2.1.3 gate — DEV acceptance on the non-mirror bench, or the
  unpinned holdout — ⇒ **do not ship; the tape stays the product.** Standing kill, unchanged.
- **(ii)** The trace population is **two** submissions ⇒ stop, re-vote per cluster, re-gate the larger.
- **(iii)** *(after the user's decision, if it ships)* Once converged (~1 day, per T1) it reads **below
  the Ueddy tape's live score** ⇒ the reconstruction method is refuted **on the ladder**, which is a
  stronger result than any local number and is worth having. Record it and return to the tape line.

## Standing conditions

Routes, reconstruction, packaged `main.py` and all derived data stay **gitignored and out of this
public repo** (§2.4b / R11). Competitor notebook source is never opened, decompressed or executed
(§2 item 8). Reference tiers 6-9 are not fetched (R23); CC BY-SA CSVs are not vendored (§4.5).
**No `agent/` change** — this is a route package, not a planner change.

## Out of scope

- **The premium-lead overlay and the adaptive layer** (the 17,7% state-dependent market steps) — that
  is **step 2**, and it gets its own Phase 0 and kill, with the shipped reconstruction as its baseline.
- **A second donor.** boatlee (#10 / 2.945,1, agreement 0,956) is a valid backup and is *recorded*, not
  built. カワシギ (#1) and Thomas Tschinkel (#2) stay rejected on criterion 2 — the anti-correlation is
  the finding, and the leaderboard now confirms it from outside.
- **C-A** ⛔ refuted. **C-B** only after step 2. **C-C (MELON)** still last.
- **Re-running Phase 0.** Its verdict stands; three corrections are logged in §4.3 and are all covered
  above.
