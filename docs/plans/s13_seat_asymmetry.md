# S13 — The seat asymmetry: is it real, and if so where does it come from?

> **Type:** implementation brief. Self-contained — assume nothing from prior conversation.
> **Written:** 2026-08-27. **Desk-only. No `agent/` change, no submission, no slot spent.**
> Phase 2 does not start until Phase 1 passes. **Build nothing** until §4's gate clears.

## Read first

`ROADMAP.md` §2 (how to read a ladder number — rules 3, 7, 9 all bind here), §3.1 (protocol),
§8 (the bench, `by_seat`), §11 (this item).
Memory: `seat1-step-not-a-bug` (the explanation this is *not*), `ladder-readability-test`,
`kaggriculture-lockstep-market-quoting`.
Code that already exists and must be reused, not rewritten: `analysis/board_join.py`
(`board_at`, `rating_zone`, `episode_times` — built in S11 B1), `analysis/s10_replay_bench.py`
(`by_seat` arms), `analysis/s8_replay_io.py` (`ladder_episodes`, `our_seat`).

---

## 1. What is claimed, and what is not

Observed on 97 ladder replays of `55726984` (2026-08-27):

```
seat 0: 30W-16L   WR 0,652   median bank 94.027 vs 89.471
seat 1: 24W-27L   WR 0,471   median bank 90.061 vs 88.186
```

**This is a question, not a finding.** Three reasons to distrust it as it stands:

1. **n = 46/51 ⇒ p ≈ 0,07.** Not significant at any threshold this repo uses.
2. **It was found by looking.** We did not pre-register a seat hypothesis; we sliced the data and
   a gap appeared. §3.1 treats that as a screen, never as a result.
3. **The obvious confounder is untested.** If seat-1 episodes happened to be drawn against
   stronger opponents — because seat assignment correlates with *when* an episode ran, and
   opponent strength climbs with our own rating — the whole gap is an artifact.

Two explanations are **already ruled out** and must not be re-tested:
- **Not the `step` field.** `obs["step"]` is delivered correctly to seat 1 at runtime; only the
  serialised replay omits it (ROADMAP §4, memory `seat1-step-not-a-bug`).
- **Not MELON timing.** Both seats sell 114 units at a weighted mean day of **17,68**, identically.

---

## 2. Phase 1 — is it real?

**🔴 Pre-registration. Declare every threshold in this section, in the output JSON, BEFORE running
anything.** We already peeked once; a second look with post-hoc thresholds is worthless.

### Available sample

| submission | ladder eps | note |
|---|---:|---|
| `55726984` | 97 | where the gap was seen — **the screen, not evidence** |
| `55586926` | 293 | independent |
| `55675634` | 119 | independent |
| **total** | **509** | seat balance **248 / 261** — assignment is not itself skewed |

Opponent joins to a leaderboard snapshot for **379/509 (74,5%)** episodes via `board_join`.

**Power** (two-proportion, α=0,05, n≈250/seat): ~98% for an 18-point gap, ~61% for 10 points,
~24% for 5. So 509 episodes **settles the observed effect** and is honestly underpowered for a
small one. Say so in the output; do not report "no effect" when the answer is "no effect this
large".

🔴 **The pooling assumption.** These are **three different agents**. Pooling them tests a seat
effect that is *common to all three* (an engine or harness property). It does **not** test an
agent-specific one. **Report all four numbers — per submission and pooled — and never quote the
pooled figure alone.** If the three disagree in sign, pooling is invalid and Phase 1 fails.

### 1a — Replication on the independent corpus

Recompute W/L by seat on `55586926` and `55675634` **before** touching `55726984` again.
Report per submission: `nW-nL` per seat, WR, two-sided Fisher exact p, and a 95% CI on the
difference.

### 1b — The opponent-strength control (the one that matters)

For each episode, join the opponent's team name to its rating at that episode's timestamp
(`board_at(episode_times(sub)[eid])`) and bucket with `rating_zone`.

1. **Is there a confound at all?** Compare the opponent-rating distribution between our seat-0 and
   seat-1 episodes (median, and a Mann-Whitney U). If the distributions match, the confound is dead
   and 1a's raw number stands.
2. **Controlled comparison.** Recompute the seat gap **within each rating zone**, and pool with a
   Cochran-Mantel-Haenszel test stratified by zone. **CMH is the headline number of Phase 1.**
3. Carry an explicit `unmatched` row for the 130 unjoined episodes — never silently drop them, and
   report whether their seat split differs from the matched ones.

### 1c — The temporal / burst control

Seat assignment could correlate with episode order, and §2 rule 2 says the burst is where the win
rate lies. Recompute the gap **excluding each submission's first 70 episodes**, and separately
regress outcome on `(seat, episode_index)` to check the seat term survives the time term.

### 1d — The town control

A fixed seed fixes the shop draw (§8's warning). Report the realised shop-draw distribution per
seat; if they differ materially, add town composition as a CMH stratum.

### Phase 1 decision rule — declared now

| outcome | action |
|---|---|
| CMH p < 0,01 **and** same sign in all three submissions | **real** → Phase 2 |
| CMH p ≥ 0,05, or sign disagrees across submissions | **dead** — one `ROADMAP` §6 row, close §11 item, **stop** |
| 0,01 ≤ p < 0,05 | **underpowered, not established.** Do **not** proceed to Phase 2 and do **not** build. Record the CI and stop |

🔴 Do not widen a window, drop a submission, or move a threshold to get across this gate.

---

## 3. Phase 2 — localisation (only if §2 passes)

Ordered cheapest-and-most-decisive first. Stop as soon as one explains the effect.

### 2a — Mirror self-play: does the **engine** favour seat 0?

**The decisive control, and it has no confounders at all.** Run one fixed agent against a copy of
itself across ≥200 seeds, both seats, and measure seat-0 win rate. Identical policy, identical
starting state — any deviation from 50% is the engine.

`_initialize` builds both farms with the same `_new_farm(board_size, starting_money)` and
`_new_private()`, so the *starting* state is symmetric. Known places where the engine is **not**
seat-symmetric, to be read against whatever this measures:

- **`_end_of_day` shares one RNG across both farms, seat 0 first.**
  `rng = random.Random((seed * 1_000_003) ^ day)`, then weeds are spawned for farm 0, then farm 1,
  from the *same* stream. Worse: `_spawn_weeds` calls `rng.random()` **only on empty tiles**
  (`if farm["tiles"][y][x] is None and rng.random() < …` short-circuits), so the number of draws
  seat 0 consumes depends on **its own tile occupancy** — which shifts both seat 1's weed draws and
  the subsequent `rng.choice(sorted(SHOPS))` shop unlock. Same distribution, different realisation,
  and coupled across seats.
- **`_process_market` handles atomic orders (`HIRE`, `BUY_LAND`) "in player order"** — seat 0 first.
- **`interpreter` applies unit actions for seat 0's units before seat 1's.**

Against those: the per-unit lockstep quote is symmetric (both seats priced at the same pre-commit
inventory, memory `kaggriculture-lockstep-market-quoting`), so the market channel itself is not a
candidate.

**If seat-0 WR deviates from 0,50 at p<0,01** → the effect is the engine, it is not fixable by us,
and the conclusion is a `ROADMAP` §4 entry plus a note that any future A/B must balance seats.
**Stop there** — there is nothing to build.

### 2b — Agent × seat interaction

Only if 2a comes back symmetric. Then the effect is *our agent behaving differently by seat*, and
the question is **where the trajectories diverge**. On seat-matched episode pairs, report:

- the **first day** the bank curves diverge, and the day-wise bank gap;
- the existing per-seat diagnostics the bench already computes — dropped SELL fill, floor units,
  `crop_tile_days`, harvest counts, unexplained no-ops;
- MELON/STRAWBERRY units and $ by day (already known to be seat-identical — a negative control that
  must stay negative).

**Deliverable is a localisation, not a fix:** name the day and the channel, or report that the
trajectories do not diverge and the effect lives entirely in the *opponent's* behaviour.

### 2c — The tape-calibration hypothesis

Our agent is an open-loop tape replay. §8/B4 records that tapes are **seat-bound** (`stream[0]`
points at seat 0's tiles, positions and money). Check which seat the shipped `_STREAM` was recorded
from, and whether replaying it in the other seat desynchronises measurably — this is the one
hypothesis with a plausible mechanism *and* a cheap fix (record or mirror a per-seat tape).

---

## 4. Acceptance, and what counts as a result

**Phase 1 gate:** CMH p < 0,01 stratified by rating zone, same sign in all three submissions.
**Phase 2 gate:** one named channel, reproduced on ≥200 seeds (2a) or ≥300 episodes (2b/2c).

🔴 **Nothing is built in this pass.** A localisation is the deliverable. Any repair is a *separate*
pass with its own bench gate, and only if the located channel is worth ≥50 rating points (§7.2).

**A negative result is a result.** "The gap dissolves under rating control" closes §11 and is worth
the pass — it stops us building on noise.

---

## 5. Standing rules

1. **No `agent/` change, no submission.** This pass spends no slot.
2. Pre-register every threshold before running; report every stratum, not the best one.
3. Do not tune a parameter or move a threshold to pass a gate. Hit a kill criterion → **STOP and ask**.
4. One implementation per concept — reuse `board_join`, the bench and `s8_replay_io`. Call engine
   rules, never re-implement them.
5. Derived artifacts to `data/derived/` (gitignored) with a `verdict` string and a generation date.
6. Every correction ships with a test that **reddens on the pre-fix code** — verify by reverting.
7. Do not change `harness/seeds.py::NAMED_SEED_SETS`; do not pass live seeds as `--seed-set`.

## 6. Deliverables and sequencing

| task | files |
|---|---|
| Phase 1 | `analysis/s13_seat_asymmetry.py`, `data/derived/s13_seat_phase1.json` |
| Phase 2a | mirror self-play arm on the existing harness, `data/derived/s13_seat_mirror.json` |
| Phase 2b/2c | extends the same script + report |
| Either outcome | one `ROADMAP` §6 row (if dead) or §4/§11 update (if real) |

| by | |
|---|---|
| 08-29 | Phase 1 complete — the gap is real, dead, or underpowered |
| 09-01 | Phase 2a (mirror) if Phase 1 passed |
| 09-04 | Phase 2b/2c localisation, or stop |
| 09-05 | **decision point** — is there a repair worth a separate pass before the ~09-23 freeze? |
