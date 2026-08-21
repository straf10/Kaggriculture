# Pass brief — Ship A: re-donor to a top-4 route, and upload it

> **Read first:** [ROADMAP.md](ROADMAP.md) **§7.1** (this pass), **§1.1** (why re-donoring is the bet),
> **§2** (how to read the ladder — nothing in this pass judges a score before 100 episodes),
> **§3** (the two new standing rules: price the *programme*, and **a pass ends in an upload**),
> **§3.1** (protocol; note the amended acceptance order), **§6 rows 23-27** (why the previous
> programme is closed), **§9** (the checklist and the slot policy). Then the top of
> [memory.md](memory.md).

## Why this pass exists

Seven consecutive desk passes ran 2026-08-17 → 08-20 with **zero uploads**, closing a programme
whose ceiling was **+2,4 rating points** against a **1.036-point** gap — a bound that was computed in
the first of those passes. That is now a standing rule (§3), and this brief is the first pass under
it: **it ends with a submission on the ladder.**

The bet is §7.1. Our reconstruction is a **faithful** copy — market layer, production layer and loss
tail all closed — of a route that is now **#9 / 2.915,8**. It plays at **#924 / 1.879,9** and wins
**38%** against 2.100+ opponents. The standing rule says **a copied route's ceiling is its donor's
own rating**, and we pointed the instrument at a #9. The instrument is built and works
(`analysis/s6_step1_reconstruct.py`, `analysis/build_reconstruction_submission.py`,
`analysis/s6_step1b_cluster.py`).

## The one question

> **Which currently top-4 team is reconstructible, and does its reconstruction clear the gate?**
> Not "is a better donor better" — that is the standing rule. The open question is purely whether a
> top-4 route survives the same instrument that reproduced ReCurSiON at production 0,993 / market
> 0,980.

## Phase 0 — donor selection. Time-boxed: half a pass, hard stop.

Candidates from the 2026-08-20 board: **Ryo Hasegawa 3.147,0 · tetsuya 3.095,3 · Arman Tuganbaev
3.053,1 · Crop Dusta 3.017,2**. カワシギ (#5, 2.988,3) is on the list only to re-confirm its known
agreement 0,31.

Per candidate, from the held daily episode datasets and any needed pulls:

1. **Trace inventory.** How many public traces of **one** submission exist, dated after that team's
   `LastSubmissionDate`? **≥3 required** (ReCurSiON had 50 — do not assume that is available).
2. **Cross-trace agreement**, production and market channels separately, the step-1 instrument
   unchanged. **Report both figures against ReCurSiON's 0,993 / 0,980.**
3. **The 2-medoid check** (`s6_step1b_cluster.py`): is this one policy mode or a two-submission
   population? `two_submissions == False` is required, and the minority share is reported.
   ⚠️ **"Same submission" is tested on the market/full stream, never on the opening.** The 48-step
   opening is byte-identical across **1.219 of 1.398** live seats (87%) — it discriminates nothing,
   and the original Phase 0 provenance check was written against it.
4. **Rank candidates by the town-controlled ratio**, never by median reward — reward is 99% the
   town's shop draw (§5.2), and that error already put ReCurSiON nowhere on a first shortlist (§3).

⚠️ **Do not rank by, or report, the candidates' local bank.** §3.1(4): the acceptance currency is
wins. Bank is a diagnostic here and nothing more.

**Pre-registered "ship anyway" (this is the point of the time box):** if the best candidate's
agreement is materially below ReCurSiON's, **still ship the highest-agreement donor above 2.900**,
recording the agreement figure in the submission description. A #4 route reconstructed at 0,95 is a
better bet than a #9 route reconstructed at 0,99, and **only the ladder can settle which** — that is
this pass's whole thesis. Do not spend a second pass improving the reconstruction instead.

**Kill:** if **no** candidate above 2.900 clears 3 traces of one submission, say so plainly, stop
Ship A, and hand both slots to §7.2 (Ship B). That is a real outcome, not a failure.

## Phase 1 — reconstruct, gate, upload

- **Reconstruct** with the existing instrument. Record the stream sha256, step count, and the
  per-decision modal-vote statistics, exactly as `55586926`'s description does.
- **Gate against the incumbent** (`55586926`, the current reconstruction), in the **§3.1(4) order**:
  **per-opponent W/L per seat first**, then BT over §8's bench (A1 + A2 + A3 + `meta_route`), then
  `median_bank`, then `mean_diff`. Report each opponent as its own row. Apply §3.1(5)'s selection
  key if panels disagree. Report the seed set's **realised drain distribution** beside the dollars
  (§8's closing warning — a few seeds can be one town).
- **SMOKE 0-11 → DEV 0-47 → unpinned holdout 100-147**, both seats. A route-only package has no
  `agent/` mechanism accounting, so a formal `GO=True` is structurally unreachable — say so, and
  report the *differenced* priced loss instead, as step 1b did.
- **§9 checklist before upload**, including the **new two-filename archive-hash check**.
- **Upload.** Eviction is pre-decided and needs no re-upload: it drops **`55575305` (Ueddy tape)**
  and keeps `55586926`. Record the eviction in the description.

## What this pass does NOT do

- **Judge the new submission.** §2 rule 2: nothing is read before ~100 episodes, and the first ~70
  are the placement burst. The pass ends at the upload; the read is a later, separate step.
- **Build Ship B.** It is the *next* pass and the *other* slot (§7.2).
- **Build the deployment-neighbourhood bench** (§7.3) — it is deliberately after both ships.
- **Re-open** the "what did the vote erase" family ⛔ · the market-layer overlay ⛔ · C-A ⛔ · a
  learned continuation rule from replays ⛔ (§5.3(c) measured that one post-freeze and deleted it).

## Standing conditions

`agent/` may be touched only if the package needs it (the reconstruction ships self-contained; prefer
that). Local episodes are played for the gate; **the only Kaggle-side action is the single upload.**
Routes, packages, replays and derived data stay **gitignored** (§3.2) and carry the **verdict
string**. Guards in `tests/`. Report to `baselines/<date>/`, session entry to `memory.md`,
**ROADMAP only if a plan, gate or standing rule changes** (its header block states this). Commit with no co-author.
