# Pass brief — S6 step 2b, Phase 0: the donor gap

> **Read first:** [ROADMAP.md](ROADMAP.md) §1 (the convergence curve, the closed kill (iii), and the
> **transfer-ratio** row); §4.3 **S6 step 2a's STOP** and the **step 2b** block (the spec for this pass);
> §3.4 in full — especially *bound the lever before building it*, *price the gain in rating points*, and
> *episodes not hours*; §4.1b (the town is 99% of realised price); §4.5(b); §4.4#1 (decay); **R27 / R21 /
> R30 / R32 / R35**; the top of [memory.md](memory.md); and
> `baselines/2026-08-18/s6_step2a_phase0_report.md`.

## Where we are

**The reconstruction is fielded and confirmed on the ladder.** `55586926` reads **1.915,8 on 85
episodes** against the surviving Ueddy tape's **1.392,9 on 78** — same read, comparable play, **+523**.
Kill (iii) is closed and did not fire. New repo best, **rank 940 / 5.123** (up 325 places). BT **3.317,
#1 of 13, 48-0-0** over the graded bench. The curve — (7, 1.125,9) → (15, 1.736,0) → (85, 1.915,8) —
has **plateaued near ~1,9-2,0k**.

**Step 2a is dead and it died correctly**, on paper, for $0 of episodes: the own-farm loss is 100% WHEAT
worth ≤$599/ep with a **$0 free half**, and my $2,8-3,1k strawberry estimate was wrong on both axes.
Phase 0 exists to do that.

## The real loss, and it is not a dollar figure

| route | our ladder score | its donor, same-day | transfer |
|---|---:|---:|---:|
| Valmorlee **verbatim tape** | 1.599,1 | 1.842,4 | **87%** |
| ReCurSiON **majority-vote reconstruction** | 1.915,8 | 2.985,6 | **64%** |

**~1.070 rating points of a #5 donor are on the table, and the majority vote transfers *worse* than a
dumb verbatim tape.** That is the loss this pass exists to locate. For scale, the thing this pass was
originally queued to build — the premium-lead overlay at **+$1.911,9/ep** — is **~+7,6 rating points**
at §3.4's $253/ep. **Two orders of magnitude apart.** §3.4's standing pre-check therefore binds: **do
not build the overlay until the gap is decomposed.** This is not a deferral of 2b — the decomposition is
what sizes the overlay for *our* route rather than for V16-RC5's.

## One mechanism, stated so it can be wrong

> **The majority vote erased the town-conditioning that made the donor #5.** 127/719 (17,7%) of its
> market steps are state-dependent; the vote replaces each with the modal action — optimal in the average
> town and in no particular one. §4.5(b)'s "degrades gracefully" was measured as a *bank margin against
> three fixed tapes*; against 5.123 adaptive teams, a route averaged over 50 towns may be optimal in none.

## ⚠️ Phase 0 — decompose the gap before proposing anything (the whole pass)

Three instruments, all on data already on disk or one API call away. **No new gate, no upload.**

1. **Our own live episodes are the primary evidence, and we have never had them at this quality.** Pull
   `55586926`'s ~85+ public episodes (`kaggle competitions episodes` → `competitions replay`) and run the
   §3.2 L1/L2 diagnostic on them: which day-window the bank gap opens in, against which opponent rating
   bands, on **both seats** separately — plus the thing L2 never had, **§4.1b's same-town control inside
   every episode** (our seat vs the opponent's seat, same town, same shop draw). Report our **realised
   premium $/u ratio against the same-town opponent** per product.
2. **The refutation, pre-registered.** The donor's recorded same-town STRAWBERRY ratio was **1,339**, and
   the frozen-replay estimate **1,243**. **If our live ratio is at or near those numbers, the calendar
   transferred intact** — the vote did *not* cost the market layer, the overlay's lever is small on our
   route too, and the ~1.070 points are somewhere else entirely. **That kills the overlay before it is
   built.** If instead our live ratio has collapsed toward 1,0, the calendar is where the points went and
   the overlay (or restoring the conditioning) is the right build, now with a size measured on our route.
3. **Where else the gap could be — enumerate and price, do not assume.** Rank these by measured
   contribution rather than picking one: (a) the **erased 17,7%** market conditioning; (b) **production
   desync** in foreign towns (the fidelity outlier was 11,8%; how often does that shape occur live?);
   (c) **tier-0 loss** already priced at ≤$599/ep, so it cannot be much of 1.070 points — use it as a
   *scale check* on your own arithmetic; (d) **the opponent population** — at 1,9k we meet different teams
   than the donor meets at 3,0k, so verify the gap is a strength gap and not a pool artefact (rating
   converges at a 50% win rate, which is the argument that it *is* real — confirm it, don't assert it);
   (e) **decay** — §4.4#1, see below.

**Gate:** state, in rating points, what the largest single component is worth. **If no component
plausibly accounts for >200 points, say so plainly** — that is a real result and it means the honest next
move is a *better donor* (カワシギ #1 / 3.188,2 and Thomas Tschinkel #2 / 3.154,3 were both rejected on
reconstructibility, R29/R30) rather than another layer on this one.

## ⚠️ And a clock is running on the asset itself

**A frozen route decays, measured on someone else this week:** Peter Parker — the *pure* frozen tape
cited as evidence that open-loop holds up — fell **#29 / 2.844,2 → #383 / 2.364,7 in ~23 hours**. Our own
donor slipped 3.004,6 → 2.985,6 while frozen since 08-14. `55586926` is a frozen route with **~6 weeks to
2026-09-30**, and the final Bradley-Terry runs on *post-deadline* episodes. **Report `55586926`'s own
(episode, score) curve in this pass** and say whether it has started to decay. If it has, that is a
finding that outranks both the overlay and the gap, because it prices the whole open-loop strategy.

## If Phase 0 clears — build, but only then

One mechanism per arm, no bundling. Both seats on everything. `--town-pin basket` for anything touching
occupancy. **SMOKE 0-11 → DEV acceptance against the non-mirror bench → unpinned holdout 100-147.**
**R21**: print the realised shop draw for every seed set — this is a market-layer change and §4.1b makes
the town the dominant confounder. **R17**: absolute `worker_turns_working` with `crop_tile_days` within
±3%. **R32**: a per-episode loss ledger (counter → count → unit price → $) in the gate summary, unpriced
structural counters listed as "unpriced" rather than omitted.

**Kill, pre-registered:** (i) Phase 0 finds no component worth >200 rating points ⇒ STOP, report, and the
next question is the donor, not the layer. (ii) An arm moves its target metric but not `median_bank` ⇒
confirmed mechanism, not a viable increment (§2 item 9) — record and reject, as v1o.3's variant E was.
(iii) Any structural hard-zero counter breaks ⇒ STOP. (iv) The arm's realised premium $/u does not move
**against the same-town control** ⇒ it has missed the only thing it was built for; stop, do not tune.

## Chores, both small

- **R35 — the step-2a artefact contradicts its own verdict.** `data/derived/s6_step2a_phase0.json` still
  holds `gate_value: 840,5` / **`gate_clears: true`** from the pre-correction pricing basis, while the
  corrected script prints `$241 (on_tile $0) ⇒ STOP`. `--report-only` re-prints but does not rewrite it.
  **Re-run the script in full, and make the artefact carry the verdict string** so no future grep reads GO
  off a superseded flag.
- **R34 — confirm the approval.** `.gitignore` now tracks `gates/*/results.json` and its comment reads
  "user-approved 2026-08-18". If that approval happened, say where; if not, ask. The change itself is
  verified safe (660K, no action streams, no §2.4b exposure) and matches R14's precedent.

## Standing conditions

**No upload (R27).** The next upload evicts the **Ueddy tape** and would leave {reconstruction,
reconstruction + layer} — two near-identical actives, the pattern §6bis warns kills both on a meta shift.
That decision is the user's and belongs at the **start** of the pass that ships. Routes, packages and
derived data stay **gitignored** (§2.4b / R11). Competitor notebook source is never opened (§2 item 8).
Write the report to `baselines/<date>/`, **write a `memory.md` entry** (the last two passes did not), and
commit with no co-author.

## Out of scope

- **Building the premium-lead overlay in this pass.** Phase 0 decides whether it is worth building at all.
- **Step 2a's wheat repair** — ⛔ on the shelf, $0 free half on a tape (§3.3's wall).
- **A donor swap** — named as Phase 0's fallback, not this pass's work.
- **`agent/` production changes** · **C-A** ⛔ refuted · **C-C (MELON)** still last.
