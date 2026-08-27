# S15 — MELON wave-2 re-phasing (stub, scoped by S14)

> **Type:** scope stub produced by `docs/plans/s14_loss_analysis.md` §2.4(a).  **Nothing here is
> built yet.**  S14 was analysis-only and spent no slot; this plan is what a build pass would have
> to do, and the first thing it must do is try to kill the result on the confirm set.
> **Written:** 2026-08-28.  Evidence: `data/derived/s14_melon_rephasing.json`,
> `baselines/2026-08-28/s14_phase1_delta.md`.

## Read first

`ROADMAP.md` §2 (ladder numbers), §3.1 (protocol — this is an **occupancy** change, rule 2),
§6 rows 30/31 (what a paper bound is worth), §7.2 (the +50-point build threshold), §8 (Instrument A,
screen/confirm split), §9 (submission ops).
`docs/plans/s12_melon_pullforward.md` §0 — the market-side pull-forward is dead and stays dead.
`docs/plans/s14_loss_analysis.md` §0 — what is already closed and must not be re-proposed.
Memory: `kaggriculture-lockstep-market-quoting`, `price-floor-liquidation-sink`,
`s9-phase2-gate`, `kaggle-ladder-rating-mechanics`.

---

## 1. What S14 established (input data — do not re-derive)

144 ladder replays of `55726984`, our own seat, `analysis/s9_live_read_55726984.py melon`.

**The tape's MELON schedule is fixed and now fully described** (126/144 byte-identical, the other 18
differ by ≤1 tile):

| wave | planted | tiles | quadrant | harvest | units |
|---|---:|---:|---|---:|---:|
| 1 | d0 | 4 | NW | d10 | 24 |
| 2 | d10 | 12 | 5 NW + 7 SW | d20 | 72 |
| 3 | d11 | 2 | SW | d21 | 12 |

Every tile reaches `max_yield` 6 and is harvested at age exactly 10 (`CROPS["MELON"]`
`first_yield_day` 10 / `max_yield_day` 12), then sold within a day or two.  Shed MELON is **0 on
every day through d20** across all 144 replays — S12 §0's finding, replicated on 5,8× the sample.

**Wave 2 is worth its tile-days** (S12's first open question, answered): 140 tile-days and $1.120 of
seed return a median $9.175 → **$57,5/tile-day net of seed**, against the tape's own realised
$/crop-tile-day of **MELON $80,7 · STRAWBERRY $48,2 · WHEAT $29,9**.  Even at its crashed price the
melon block out-earns the next-best thing the tape grows.  **Do not propose deleting wave 2** —
the same model prices that at **−$9.044/ep**, its worst counterfactual by a wide margin.

**MELON's only sink is 1 unit/day.**  No entry in `SHOPS` lists MELON; `_town_consume` takes 1 of
every `TOWN_CENTER_PRODUCTS` item per day.  So MELON inventory is effectively monotone and the price
is a function of *cumulative* supply, not of the calendar.

**Where the gain comes from — and it is not "sell earlier" in the naive sense.**  Selling four days
earlier *forfeits* four days of drain and would be worth **−$300** on its own.  The whole effect is
that our d20-22 dump currently shares its window with the opponent's own late melon block (36,7% of
their supply lands after d19, mean 22,4 units on d20 alone), and the engine quotes **both seats at
the same pre-commit inventory** — so we pay half of a crash we did not cause.  Moving our block to a
window the opponent is not selling in removes that.

**The re-phasing model** (`g4_rephasing_model`, per-episode, engine per-unit lockstep, our own
self-crash charged, town drain applied):

| harvest day | Δ our MELON $/ep (median) | Δ margin (median) | loss flips (our side only) |
|---:|---:|---:|---:|
| d11-d15 | +$4.189 … +$4.774 | +$9.855 … +$10.286 | 32/65 |
| **d16 (earliest feasible)** | **+$3.918** | +$8.434 | **32/65** |
| d17 | +$1.326 | +$3.056 | 28/65 |
| d20-d22 (recorded) | ~$0 / negative | — | 0-2/65 |

**Feasibility** (`g3_feasibility`, 144/144 identical): NE unlocks **d6 h17** with 26 free tiles and
$2.863 of peak cash that day; SW unlocks **d10 h01**.  14 MELON seeds cost $1.120.  So the earliest
day a 14-tile wave has both land and cash is **d6 → harvest d16**; d7 (22 free tiles, a full day)
gives d17 as the safe fallback.  d11-d15 harvests need a d1-d5 planting, where free land is 7-11
tiles and peak cash is $32-$767 — **infeasible on both counts, so the top of the table is out of
reach and must not be quoted as the prize.**

---

## 2. Why this is a candidate and not a result

🔴 **It is a paper bound of the same species as §6 row 30.**  It is a better one — it walks the
engine's own per-unit price and charges our own self-crash, which the WHEAT market-maker bound and
`panel_e`'s price substitution do not — but the opponent's **unit schedule is held fixed while their
realised price collapses** (`d_opp_melon_median` ≈ −$4.500).  That is a joint-seat model, which
memory `kaggriculture-lockstep-market-quoting` admits as ground truth only, never as estimator
input.  **`d_our_melon_*` is the defensible half; `d_margin_*` additionally spends the opponent's
loss and is an upper bound.**  The one thing arguing the fixed schedule is not absurd: MELON is
harvest-gated for them too (their melon tile-days are 154-162/ep, same two-wave shape), so their
*supply* cannot move within an episode even if their selling could.

🔴 **The model's own error bar is not small.**  Replaying the *recorded* schedule through the same
model misses the ledger's recorded revenue by a median −$122 / mean +$444, and **46 of 144 episodes
are off by more than 5%**.  Any gate must be read against that, not against zero.

🔴 **It is a production-side change to the tape, not an overlay.**  Every shipped change so far has
been additive (`agent/tape_overlay.py`).  This one moves 14 plantings, their waterings and the
hands' routing from NW/SW to NE and shifts ~12 STRAWBERRY tiles the other way.  Under §3.1 rule 2 it
is unambiguously **occupancy** — `--town-pin basket` on both arms, holdout unpinned.

🔴 **It collides with the shipped H2 rule.**  `55726984` is `mode="liquidate"` with frozen params
(F=25 / first_day=22 / h_max=12 / d_days=4 / force_step=686) fitted to the *current* STRAWBERRY
calendar.  Displacing the d7 NE strawberry block into SW at d10 moves that calendar three days
later, straight through H2's window.  H2 must be re-validated, not assumed.

🔴 **The d6 planting window is 7 turns long** (NE unlocks at h17).  14 tiles in 7 turns needs the
farmer plus several hands already positioned, and S14 did not check hand routing.  If it does not
fit, the arm is the d7/d16→d17 variant, worth a median **+$1.326**, not +$3.918.

---

## 3. Phase 1 — try to kill it before writing any `agent/` code

Pre-registered, in this order.  **Any one failing is a STOP, not a re-scope.**

1. **Confirm-set replication.**  Re-run `analysis/s9_live_read_55726984.py melon`, re-pointed at the
   confirm set (`55586926` + `55675634`, 412 episodes, ROADMAP §8) — **which S14 deliberately did
   not touch**.  Gate: `d_our_melon_median` at the feasible harvest day is **positive and ≥ 60% of
   the screen-set figure**, and the loss-flip share is within ±0,08 of 32/65.
2. **Hand-routing feasibility, on the tape.**  Replay the tape and check that 14 PLANT actions fit
   in d6 h17-h23 (or d7) given where the farmer and hands actually stand, and that the melons can be
   watered on ages 6-10 without dropping a watering elsewhere (2 consecutive unwatered days = weed
   death).  Gate: a concrete action schedule, or drop to the d7/d17 variant and re-run gate 1.
3. **Opponent-reaction sensitivity.**  Re-run the model with the opponent's late block moved
   *earlier* by the same amount (they react perfectly).  Gate: `d_our_melon_median` stays positive.
   This is the honest test of the fixed-schedule assumption and the cheapest way to fail fast.
4. **Threshold.**  §7.2 needs **+50 rating points**.  The only calibrated $→points conversion in the
   repo is row 30's **$2.009/ep = 7,9 pts** ⇒ ~$254/ep per point, which puts +$3.918/ep at **≈15
   points — three times under the bar.**  🔴 **So the dollar case does not clear §7.2 on its own and
   must not be argued on dollars.**  The case, if there is one, is the **W/L** case (§3.1 rule 4:
   wins first, dollars are diagnostic), and it has to be made on Instrument A, not on this model.

## 4. Phase 2 — only if all four gates pass

Build on `analysis/s10_replay_bench.py` (Instrument A), which substitutes our seat's action stream
into every recorded ladder episode and has an α-control that reproduces 509/509 episodes bit-exactly.
Screen on `55726984`; **confirm on the 412-episode set with both-seat McNemar p<0,01**, the same gate
H2 passed (`232-180 → 255-157`, c=23 b=0, p=2,4e-7).  Then ROADMAP §9's upload checklist.
Pre-decided eviction (§9 rule 3) is currently **`55675634`**; that decision is made *before* the
upload or not at all.

## 5. Standing rules for this plan

1. No parameter is tuned to a gate; a kill criterion is a STOP, not a wider window (§3.1).
2. One implementation per concept: extend `analysis/s9_live_read_55726984.py` and Instrument A;
   call `engine_reference/kaggriculture.py` rather than restating its arithmetic.
3. Report every harvest day tried, not the best one.
4. Every derived JSON carries a `verdict` and a generation date; every fix ships a test that reddens
   on the pre-fix version.
5. Do not touch `harness/seeds.py::NAMED_SEED_SETS`; live seeds never enter it.
