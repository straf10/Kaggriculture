# Pass brief — S7 legs 1-2: score our own assets against real ladder opponents, in wins

> **Read first:** `baselines/2026-08-20/s7_leg0_report.md` (the census this pass continues) and the
> 178-episode addendum to `s6_step2e_report.md`; [ROADMAP.md](ROADMAP.md) **§1.1** (how to read a
> ladder number — the three corrections this pass operates under), **§2.1.4** (the amended
> acceptance order — *this is the pass that first uses it*), **§4.5(c)** (Kaito v36: the selection
> key, the three surfaces, and the state-aliasing refutation), **§4.3 S6 step 2** (the bench, now
> with **A4**), **§4.3 S7**, **§4.3 S6 step 3** (`harness/ladder.py`, and **R33** — the
> reconstruction's BT rung is still a blank), §3.3's step 2a/2c/2d/2e rows, §2.1.1-5, R21/R27/R32/R35,
> and the top of [memory.md](memory.md).

## Where we are

Six passes closed the question *"what did the majority vote erase?"* — market layer town-invariant
(2c), production residual town-reactive but worth **$597/ep ⇒ +6,2 rating points** (2d/2e), loss
tail owned by the town's shop draw (2e). The vote is a **faithful open-loop copy**.

S7 leg 0 then removed the three remaining ways to explain the gap away:

| escape hatch | measured verdict |
|---|---|
| "our rating is deflating, the donor's isn't" | both deflate; **band-local** rates; our rank *rose* while our score fell |
| "we're underrated — 65% win rate says so" | 65% was the **placement burst**; converged and controlled it is **43,4%** |
| "the copy is lossy" | closed channel-by-channel by 2c/2d/2e |

**So: our reconstruction is a rank-924 agent (1.879,9) copied faithfully from a rank-9 agent
(ReCurSiON, 2.915,8), and it wins 41% against 1.800-2.100 opponents and 38% against 2.100+.**

## The one question

> **Where, against a real ladder opponent, does our route actually lose — and does any bench we can
> build locally reproduce that loss?** Every gate in this repo has scored arms against our own
> lineage, `meta_route`, six reference tiers and three donor tapes. **None of those is an opponent
> we have ever lost to on the ladder.** We now hold 178 replays containing both seats' full action
> streams for **165 distinct opponent teams** in exactly the band where we lose.

## Legs

**Leg 1 — build the deployment-neighbourhood bench (no episodes to acquire; extraction only).**
Extract opponent action streams from the held live replays the way `analysis/donor_streams.py`
extracts the three donor tapes, and register them as fixed-production bench opponents. Requirements:

- **Stratify by the *controlled* opponent score** (§1.1 / R36's replacement: the team's board
  submission must predate our episode). Report the strata sizes; the two that matter are
  **1.800-2.100** and **2.100+**.
- Keep **provenance** per opponent: `(episode_id, seat, team, sha256)`, held **gitignored** (§2.4b).
- **Verify each stream replays**: a tape that desyncs into a no-op parade is not an opponent. Reuse
  `analysis/s2_replay_fidelity.py`'s check and state a retention figure, as S2 did for the donors.
- ⚠️ **Expect attrition and report it honestly.** Many neighbourhood opponents will themselves be
  open-loop tapes that desync against *us*. An opponent that cannot hold its own route is a weak
  sparring partner, and the count of usable ones is a result, not an inconvenience.

**Leg 2 — re-score every asset we already hold, in the amended currency.** Round-robin
Bradley-Terry (`python -m harness.cli ladder --round-robin`, both seats, `--town-pin basket`) over:
the shipped reconstruction · the Valmorlee and Ueddy tapes · `v1h` / `v1i` / `v1o_2` / `v1u_base` ·
reference tiers 0-5 · `meta_route` · leg 1's live opponents. **This closes R33.** Report, in this
order (§2.1.4): **per-opponent W/L per seat → BT rating → `median_bank` → `mean_diff`**, then the
§4.5(c) selection key — *worst panel → worst seat → overall wins → tail log-ratio → margin*.

**R21 binds hard here.** A small seed set is biased in its shop draw (48% wool-dead on seeds 0-3
against a 34% population rate), and §1.3 of leg 0's report shows the draw moves bank by 2,1× while
moving no wins — so **report the realised drain distribution beside the dollars**, and read the W/L
rows, not the bank rows, when they disagree.

## Kills / branches, pre-registered

- **(i) The bench reproduces the ladder ordering** — the reconstruction beats tiers 0-5 and the
  tapes but loses to the 2.100+ stratum, at roughly the live rates (38-41%) ⇒ **we finally have an
  instrument.** Proceed to leg 3 (the one bounded build) with the specific losing matchups named.
- **(ii) The reconstruction sweeps the 2.100+ stratum locally while losing to it live** ⇒ **the
  bench is still not the ladder and S7's premise is wrong.** Say so and stop. Do not tune against a
  bench that does not transfer — that is precisely what §4.3 S6 step 3(ii) caught on our own lineage
  (local BT ranked v1i above v1h; the ladder ordered them the opposite way).
- **(iii) Too few live opponents survive the replay check to form a stratum** ⇒ report the retention
  figure and fall back to A1+A2 with the limitation stated. **Do not pad the bench with our own
  lineage and call it a neighbourhood.**
- **(iv) The BT ordering and the per-opponent W/L ordering disagree** ⇒ that is the finding (it
  already happened once: v1h out-margins v1i and under-rates it). Report both and let the selection
  key arbitrate; do not collapse them into one number.

## Out of scope

- **Leg 3 (any build), including §4.5(c)'s WHEAT market maker.** It is gated on leg 2 and it must be
  surface-area-bounded on paper first (§3.4). This pass ends with a measurement and a named target.
- **Any upload (R27)**, so the eviction is not raised — though it is pre-decided: the next upload
  drops the **Ueddy tape** (older by date) and keeps the reconstruction.
- **Re-opening the "what did the vote erase" family** ⛔ closed across every channel and both
  currencies · **market-layer overlay** ⛔ (2c) · **step 2a's wheat repair** ⛔ on the shelf ·
  **C-A** ⛔ refuted · **a learned continuation rule from replays** ⛔ — §4.5(c) measured that one
  post-freeze and deleted it from their own artifact.

## Standing conditions

**No `agent/` change.** Episodes may be *played locally* by the harness for leg 2 (that is what a BT
round-robin is); **no episodes are played on Kaggle and nothing is uploaded.** Routes, packages,
replays and derived data stay **gitignored** (§2.4b / R11) and carry the **verdict string** (R35).
R32: price every counter you report; list unpriced structural counters as "unpriced". Competitor
notebook source untouched (§2 item 8). Report to `baselines/<date>/`, `memory.md` entry, commit with
no co-author.
