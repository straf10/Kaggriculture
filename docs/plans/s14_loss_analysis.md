# S14 — Loss analysis: is there a real, buildable lever left in 55726984?

> **Type:** implementation brief for a fresh agent. Self-contained — assume nothing from prior
> conversation. **Analysis-only pass. No `agent/` change, no upload, no submission.**
> A follow-up build plan (S15) gets written only if §3 or §4 below survives its own gate.

## Read first — and do not re-derive any of this

`ROADMAP.md` §2 (how to read a ladder number), §3.1 (protocol), §7.2 (the +50-point build
threshold), §9 (submission ops — the CLI recipe you need is here), §10 risk 7 (dropped-SELL fill,
**standing accept, do not reopen**).
`docs/plans/s12_melon_pullforward.md` §0 — **read this in full before touching MELON.** It already
proved the obvious market-side fix (sell the held stock earlier) is not implementable, and it names
the one question it left open. Do not re-run its measurement; start from its conclusion.
`docs/plans/s13_seat_asymmetry.md` — closed, not actionable. Do not reopen.
Memory: `s9-live-read-55726984`, `price-floor-liquidation-sink`, `kaggriculture-lockstep-market-quoting`,
`kaggle-ladder-rating-mechanics`.

**The existing instrument is `analysis/s9_live_read_55726984.py`. It already runs six panels over
every ladder loss of the current shipped agent. Extend it; do not write a second one (plan rule 4
below).** Its current output, `data/derived/s9_live_read_55726984.json`, was generated
**2026-08-25T12:10 UTC on 92 replays** — it is now 2026-08-28, so this is at minimum three days
stale. **Step 1 of this pass is refreshing it, before any new analysis.**

---

## 0. What is already known — do not repeat this work

From the existing six panels (`panel_a` volume/WL, `panel_b` opponent-strength control, `panel_c`
loss severity/margin buckets, `panel_d` per-product $/unit and timing split, `panel_e` the
all-product flip test, `panel_f` wins-vs-losses behavioural profile), on 92 replays:

- **Losses are marginal, not blowouts.** 30/38 marginal, 8 mid, 0 blowouts; median |margin| $3.470;
  25/38 inside $5.000. Equilibrium win rate is **50% at our own 1700-1900 rating band** — matchmaking
  pulling toward 50%, not a regression (§2 rule 2).
- **We are a fixed tape.** HIRE/BUY_SEED/BUY_ANIMAL/BUY_LAND spend is byte-identical across all 92
  episodes regardless of opponent or town. `panel_f`'s own docstring: *"any win/loss difference on
  OUR side is either the town or a desync — never a decision."* Making the agent state-reactive in
  general is **already closed terrain**: S6's town-reactive production layer measured **+2,4 pts**
  for the effort (`s6-erased-conditioning-closed` — do not reopen), and S7 Leg A killed re-donoring
  to any state-adaptive top-4 policy by measurement (state-aliasing, unreconstructible). **Do not
  propose "make it adapt" as a finding — it has a priced, closed answer already.**
- **The all-product flip test is already run — this is the headline table, and it is decisive:**

  | product | flips (of 38 losses) | mean $/ep if we'd sold at their price |
  |---|---:|---:|
  | **MELON** | **13** | **+$4.861** |
  | WOOL | 4 | +$1.182 |
  | MILK | 4 | +$1.235 |
  | FERTILIZER | 4 | +$208 |
  | WHEAT | 2 | +$199 |
  | STRAWBERRY | 1 | −$602 |
  | EGG / CARROT / TOMATO | **0** | $0 |

  **CARROT/TOMATO/EGG give zero flips even under the idealised "sell at their price" counterfactual**
  — our zero participation there is not a rating lever, whatever the raw dollar gap looks like.
  **Do not propose entering these products; it is measured dead.**
- **MELON is the only real candidate, and `s12_melon_pullforward.md` already killed the obvious fix
  for it.** Our own MELON stock is 0 on every day through day 18 (25 replays) — the day-10 (30u) and
  day-20 (60u) blocks are harvest events sold the day they land, not held inventory. A market-side
  "sell earlier" overlay has no degree of freedom. **The `panel_e` flip number above is a price-
  substitution paper bound, exactly like the WHEAT market-maker bound killed in §6 row 30 — it is
  not evidence the lever is buildable.**
- **What S12 left explicitly open, and this pass exists to answer:** *"is the second MELON wave
  worth its tile-days, and can the two waves be re-phased without crashing the day 9-14 window
  against each other."* Context that bears on it, measured just now (2026-08-28) and not yet
  written up anywhere: our own MELON tile-days run **172-179/ep** (wins vs losses), opponents'
  **160-167/ep** — we already plant *more* than they do. The top-4 profile's own MELON tile-day
  band is **110-180** (`analysis/b1_top4_profile_2026_08_21.py`), so we sit at the top of the elite
  range on **volume**. Combined with the harvest-gating finding, this points at a **timing**
  question (which window the harvest lands in), not a volume one — consistent with everything S12
  and this table already show.

**Do not reopen:** CARROT/TOMATO/EGG participation, general adaptivity, dropped-SELL repair
(§10 risk 7 — Δ$1.877 loss-vs-win measured, standing accept), the MELON *market-side* pull-forward
(§12 killed it structurally, not on a threshold).

---

## 1. Phase 1 — refresh, then reproduce (do this first, unconditionally)

1. `source .env` (Kaggle token), then pull whatever ladder episodes exist for `55726984` beyond
   what's cached: `kaggle competitions episodes 55726984 -v`, then
   `kaggle competitions replay <EPISODE_ID> -p data/archive/raw/live_55726984/` for each new id.
   Same recipe for `55586926`/`55675634` if Phase 2 below ends up needing the larger corpus.
2. Re-run `python analysis/s9_live_read_55726984.py run` **unmodified** first, to get a clean
   before/after. Do not edit the script until you have this baseline.
3. **Report whether the picture changed** with the extra days of data: does `panel_e`'s ranking
   hold (MELON still clearly first), does any of the ≤4-flip products move enough to matter, does
   `panel_b`'s zone-level win rate still read as an equilibrium at 50%.
4. 🔴 **If MELON is no longer the top flip lever after refresh, stop and re-scope §2 around
   whatever now ranks first** — do not execute §2's MELON-specific plan against stale evidence.

---

## 2. Phase 2 — the MELON tile-day/re-phasing question (only if §1 confirms MELON still leads)

**Goal:** turn "is the second wave worth its tile-days" into a number, using the real engine, not a
price-substitution shortcut.

1. **Extract the tape's actual PLANT/HARVEST orders for MELON.** The stream is
   `analysis/s9_h2_k10.py`'s donor stream (or read directly from a `55726984` replay's own action
   log — `steps[t][our_seat]["action"]`). For each wave: planted day, tile count, quadrant, and the
   resulting harvest day/units. Confirm the two-wave structure (~day 0 → harvest d10 = 30u; ~day 10
   → harvest d20 = 60u) against several replays, not one.
2. **Quantify the tile-day cost of wave 2** on its own terms: tiles committed × days held, versus
   what those same tiles would have produced if left to their next-best alternative use (read from
   the tape itself — what would otherwise occupy that land/those hands in that window). This is a
   **displaced-opportunity** number, not a hypothetical.
3. **Model re-phasing, not pull-forward.** The question is whether planting wave 2 *earlier* (so its
   harvest lands inside d10-19 instead of d20-29) is land/hand-feasible under the tape's own
   schedule, and if so, what it does to price. Compute the self-crash cost with the engine's own
   per-unit lockstep quote (`market_price` in `engine_reference/kaggriculture.py`, reused not
   reimplemented — memory `kaggriculture-lockstep-market-quoting` — since dumping both waves into
   the same 10-day window is exactly the overlap case where the sequential price-walk shortcut is
   wrong): does 90+ units landing in d10-19 (both waves combined) crash the price below what the
   current split realises, net of avoiding the d20-29 collapse?
4. **State a verdict, not a recommendation:** either (a) re-phasing nets a positive, feasible $/ep
   gain after the self-crash cost — in which case scope a build plan (S15) gated the same way S12
   was (α-control, both-seat McNemar p<0,01 on the confirm set, ≥50-pt threshold before upload); or
   (b) it doesn't — in which case this closes the same way S12 did, as one more `ROADMAP` §6 row,
   and MELON is **done, permanently**, across both the market-side and production-side attempts.

---

## 3. Phase 2b — WOOL, only if time remains after §2 (lower priority, bounded)

WOOL is the only other product with a *plausible* mechanism, because SHEEP produce it on an
interval (continuous), unlike MELON's single harvest — so it may genuinely be holdable rather than
forced to sell same-day. **Check that before anything else**: is our own WOOL stock ever non-zero
in the days before the trough (d12-15) the way MELON's is never non-zero before its harvest days?
If WOOL is also harvest/production-gated with no held stock, it dies the same way MELON did and the
existing 4/38 flip number was already a paper bound — say so and stop. If it genuinely holds stock,
the flip count (4/38) is weak enough on its own that this is a **report, not a build proposal** —
note it for later, do not spend a build pass on a 4-flip lever without a much larger confirm sample
first.

---

## 4. Standing rules

1. **No `agent/` change, no upload, no submission.** This pass spends no slot.
2. **Reuse, do not duplicate.** Extend `analysis/s9_live_read_55726984.py` and call
   `engine_reference/kaggriculture.py` functions directly — this is the same rule that caught the
   off-by-one in S10 P4 and the leakage bug in S11 B2.0′. One implementation per concept.
3. Pre-register any new threshold before running against it; report every product/stratum, not the
   best one.
4. Do not tune a parameter or move a threshold to manufacture a pass. Hit a kill criterion →
   **STOP and ask**, do not widen the window.
5. Every derived JSON gets a `verdict` string and a generation date; every code fix ships with a
   test that reddens on the pre-fix version (verify by reverting).
6. Do not touch `harness/seeds.py::NAMED_SEED_SETS`; do not pass live seeds as `--seed-set`.
7. If §2 produces a positive, feasible verdict, **do not build it in this pass** — write it up as
   the input to a new `docs/plans/s15_*.md`, scoped and gated the way S12/S13 were.

## 5. Deliverables

| task | files |
|---|---|
| Phase 1 | refreshed `data/derived/s9_live_read_55726984.json`, a short delta note (old vs new panel_e ranking) |
| Phase 2 | `data/derived/s14_melon_rephasing.json` (verdict, tile-day accounting, self-crash model, feasibility call) |
| Phase 2b (if reached) | one paragraph appended to the same JSON — WOOL holdability, feasibility, and whether it's worth a future look |
| Either outcome | one `ROADMAP.md` §6 row (dead) or a new `docs/plans/s15_*.md` stub (feasible) |
