# Pass brief — S6 step 2a: the route is blind to its own farm

> **Read first:** [ROADMAP.md](ROADMAP.md) §4.3 **S6 step 1b's result block and the step 2a block**
> (the spec for this pass); §1's active-submissions + early-signal rows; §3.4's **three new lessons**
> (episodes-not-hours · sum the loss counters · read the donor's LB score); **R32 / R33 / R27 / R21 /
> R13 / R17**; §3.3's **crop/animal equilibrium** table (the reason this pass can fail); §2.1.3-5;
> §4.5(b); §6bis; the top of [memory.md](memory.md); and
> `baselines/2026-08-17/s6_step1b_report.md`.

## Where we are

**The reconstruction is shipped and climbing.** `55586926`, uploaded 2026-08-17 22:29 UTC, read 22
minutes later at **1.125,9 on 7 episodes** (from 600,0) against the surviving Ueddy tape's **1.375,9 on
72**. Valmorlee is evicted and frozen at 1.599,1/111. It cleared DEV (+$15.276) and the unpinned
holdout (+$12.212, 48-0-0 both seats) against the raw Valmorlee tape, with zero escapes and zero shed
overflow.

**Kill (iii) is open and its instrument was mis-specified** — it was written in wall-clock ("~1 day")
and a rating is a function of **episodes played**. Do not resolve it against today's numbers.

## 1. Real losses — measure them, do not assume them

Two sources, in this order. Both are cheap and neither needs a new gate.

**(a) Our own live episodes.** `55586926` is playing public episodes right now, in real towns, against
a rating-sorted opponent pool, on both seats. Pull them (`kaggle competitions episodes` →
`competitions replay`) and run the §3.2 L1/L2 diagnostic on them: where in the season does the bank gap
open, against which opponent bands, and — the part L2 never had — **the §4.1b same-town control inside
every episode**, so realised premium $/u is comparable without a replay. This is the best "where does
this agent lose" data this repo has ever held. Report it against the reconstruction's *predicted*
behaviour: recorded-episode STRAWBERRY was 1,339 and the frozen replay 1,243 — **which is it live?**

**(b) The loss ledger the gate artefacts already contained (R32).** From
`gates/s6_step1b_gate_holdout/results.json` (96 eps, unpinned, both seats), per episode:

| counter | recon | tape | price | ≈$/ep |
|---|---:|---:|---|---:|
| `unexpected_weeds_lost` | **5,0** | 5,5 | $300/tile | **$1.500** |
| `plant_decay_units_lost` | **15,0** | 14,9 | *unpriced* | **~$1.300-1.600** ⚠️ |

The first row is 100% of the route's priced loss. The second has never been priced — **decompose it by
product before quoting a dollar figure; do not inherit my strawberry assumption.** Together ≈
**$2,8-3,1k/ep**, against step 2b's entire ceiling of +$1.912/ep. Both are ~equal on the incumbent tape,
so this is inherent to open-loop replay in a foreign town.

## 2. One failure mechanism, stated so it can be wrong

> **The reconstruction is blind to its own farm state.** It plays a stream calibrated to the donor's
> town, so when *this* town's weeds spawn on a planted tile the stream does not clear, or a crop passes
> its max-yield tick (D6) the stream does not harvest, the loss is taken silently — on every episode,
> on both seats, on every tape we have ever shipped.

## 3. ⚠️ Phase 0 — bound the surface area on paper, before building anything (§3.4)

**This is the whole risk of the pass and it needs no new episodes.** A repair inserts an action the
route did not emit. If a unit is **idle** at that step it is nearly free; if it **displaces** a route
action, §3.3's crop/animal equilibrium — five independent mechanisms, one wall — says it loses more than
it earns. So measure, on the recorded replays and the reconstruction's own stream:

1. **Where and when** do the 5,0 weed-tile and 15,0 decay-unit events occur — which step, which tile,
   **which product**, which day-window?
2. **Is a unit idle at that step?** Per event, is there a unit emitting a no-op/idle turn that could
   take the repair without displacing anything?
3. **Maximum recoverable if every repair fired perfectly**, split into the free (idle-unit) and the
   displacing (costly) halves.

**Gate:** if the *free* half is **< $500/ep**, the lever does not exist at this route's occupancy —
**STOP, record it, and the pass becomes step 2b (the premium-lead overlay)** with its own Phase 0. That
is a real result, not a wasted pass: it would say the equilibrium binds on a tape exactly as it binds on
our planner, which nothing has yet tested.

## 4. Build challengers — plural, and expect to reject most

If Phase 0 clears, screen **separate** arms; do not bundle, and do not tune. Suggested set, each one
mechanism:

- **A — harvest repair:** insert HARVEST when a tile is at/past max-yield age and the stream does not
  collect it. Targets `plant_decay_units_lost` 15 → 0.
- **B — weed repair:** clear/replant a weeded planted tile the stream ignores. Targets
  `unexpected_weeds_lost` 5,0 → 0.
- **C — idle-only variant of whichever of A/B looks larger:** fires *only* when Phase 0 says a unit is
  idle. This is the control that separates "the repair works" from "the displacement is affordable" —
  and per §3.3's history it is the arm most likely to be the only survivor.

**Test discipline (§2.1.1-5):** both seats on everything · `--town-pin basket` for anything touching
occupancy (a repair changes tile occupancy — treat it as occupancy, not market-only) · SMOKE 0-11 →
**DEV acceptance against the non-mirror bench** → **unpinned holdout 100-147** · **R21 draw printed for
every seed set** · **R17: `worker_turns_working` absolute with `crop_tile_days` held within ±3%** — a
repair that "wins" by shedding tile-days into idle is the exact trap v1p1b arm A1 sprang.

## 5. Kill, pre-registered per arm

- **(i)** Phase 0's free half < $500/ep ⇒ STOP, go to step 2b.
- **(ii)** `crop_tile_days` falls **>3%** against the paired baseline, or `priced_loss_delta` exceeds
  `min($500, 10% × mean_diff)` ⇒ the repair is displacing productive work; reject the arm (this is the
  §3.3 equilibrium firing, and it is the single most likely outcome).
- **(iii)** An arm fixes its target counter and does **not** move `median_bank` ⇒ confirmed mechanism,
  **not** a viable increment (§2 item 9). Record it as v1o.3's variant E was recorded and reject it.
- **(iv)** Any structural hard-zero counter breaks (`clipped_production_ticks`, market-sim aborts,
  unexplained no-ops) ⇒ STOP.

## 6. Freeze the winner, then test on strictly later episodes

At most **one** arm survives to a checkpoint. Then §4.3 **S6 step 4**, which is now runnable and was
never run: the **08-18+ daily datasets** are strictly later than the 08-16 episodes the route was fitted
on. Re-measure fidelity and calendar there. §4.4#1 (a frozen policy decays: 87/90 → 14/27) makes this
the test that matters most for a route we intend to freeze until 09-30.

## 7. Two loose ends to close in passing, both one command

- **R33 / R28:** the reconstruction's **Bradley-Terry rating is still unmeasured** — step 1b's item 3
  has an unfilled `<!-- BT_LADDER_RESULT -->` placeholder and reports a challenger-only sweep, which
  cannot produce a rating. Run `python -m harness.cli ladder --round-robin --shop-draw` over the bench
  (A1 tiers 0-5 + three tapes + `v1u_base` + `meta_route`) and report the table with the per-seat split.
- **R34 (ask the user first, one line of `.gitignore`):** `gates/` is ignored wholesale, so step 1b's
  DEV and holdout `results.json` — the evidence for shipping `55586926` — are on one laptop only. This is
  R14 repeating one directory over, and R14's fix was the user's call. Propose `track gates/*/results.json
  only` (aggregates only, no action streams, no §2.4b exposure) and act on the answer.
- **Kill (iii), correctly instrumented:** log **(episode count, publicScore)** pairs for `55586926`
  *and* `55575305` on every read, and only compare once the reconstruction has **≥72 episodes** (Ueddy's
  count). Report the curve. Below Ueddy *at comparable episode counts* ⇒ the method is refuted on the
  ladder, which is a stronger result than any local number — record it and return to the tape line.

## Standing conditions

**No upload this pass (R27).** The next upload evicts the **Ueddy tape** and would leave
{reconstruction, reconstruction + repair} — two near-identical actives, the pattern §6bis warns kills
both on a meta shift. That decision is the user's and belongs at the *start* of the pass that ships,
not at its end. Routes, packages and derived data stay **gitignored** (§2.4b / R11). Competitor notebook
source is never opened (§2 item 8). Reference tiers 6-9 not fetched (R23).

## Out of scope

- **Step 2b (the premium-lead overlay)** — next, or immediately if Phase 0's gate stops this pass.
- **The 17,7% state-dependent market-step adaptive layer** — that is a *market* layer and belongs with
  2b; this pass is production/farm-state only. Do not blend them: one mechanism per arm.
- **`agent/` production changes.** Item ④ is closed; the planner is ~650-1.300 BT behind the tapes.
- **A second donor** (boatlee #10 / 2.945,1 is recorded, not built) · **C-A** ⛔ refuted · **C-C
  (MELON)** still last.
