# Pass brief — S6 step 1: own a modifiable route (Phase 0 = donor selection, measured)

> **Read first:** [ROADMAP.md](ROADMAP.md) §4.3 **S6 step 0's result and the redefined step 1**,
> **§4.5(b)** (the reconstruction method), §4.1b, §3.3's **T2 row** and the new **C-A row**,
> §3.4's two new lessons (bound the surface area first; the same-town control), §4.4#1 (decay),
> §6bis slot mechanics + **R27**, **R28**; the top entries of [memory.md](memory.md); and
> `baselines/2026-08-17/s6_step0_report.md`.

## Where we are

Step 0 did its job by refuting its own pre-registered lever. **C-A is dead** — against an identical
route in the same town the two seats realise **1,000×**, the best within-turn permutation is worth
**$0-18/ep**, and the engine says why ([kaggriculture.py:544-597](engine_reference/kaggriculture.py#L544-L597):
per-slot lockstep across players, per-product pools). Queue ordering is not where the money is.

But leg 1 **relocated** the target, and that is the finding this pass is built on:

> **Valmorlee realises 1,25× STRAWBERRY and 1,13× WOOL against the other two donor tapes in the
> same town at the same volume — purely from *which turns* it sells on. The 1,05× is cross-turn
> sell timing.**

That lever is worth roughly the $2.826 median gap, it is what separates reference tiers 6-9
($164-$2.617/ep), and §4.5(b) prices a premium-lead overlay at **+$1.911,9/ep, 60-0-0** for an
agent that owns its route. **It is not reachable on a verbatim tape** — T2 already STOPPED there:
metering overflows a shed already at 98/100.

**So the missing asset is a route we can modify.** That is this pass.

## What to build

**§4.5(b)'s method: reconstruct a policy from multiple traces of a single submission** — per
decision point, take the majority action across that submission's own episodes; add worker-count
adaptation and obstruction recovery so it survives drift. This is a *measurement* of a policy
rather than a copy of one performance: it degrades gracefully where a tape desyncs (§4.4#1), it
carries shed headroom we can actually spend, and it is the better answer under §3.14a.

### ⚠️ Phase 0 — donor selection, and it is the whole risk

**Measured, not preferred.** Step 0's own finding names the donor we want (Valmorlee's calendar) —
and while updating the ROADMAP, **Valmorlee did not appear at all in the 150-episode stride sample
of the 08-16 dataset** (39 distinct teams; Ueddy had 17 seats; 27 teams had ≥3). *Do not assume the
donor.* Search the **full 700** episodes of `data/archive/raw/2026-08-16/` (already on disk,
gitignored) and select on three measured criteria, in this order:

1. **Trace count.** ≥3 episodes attributable to one team *on one submission*. Multiple seats of a
   team is **not** the same thing — a team may have changed submissions mid-day. State how you
   established same-submission (action-stream prefix identity is the obvious test, and it is also
   criterion 2's numerator).
2. **Cross-trace agreement.** V16-RC5 reports **~99,91%** market-decision agreement across its three
   traces. Measure ours: per decision point, the share of traces agreeing on the action, for the
   `farmer`/`hands` channel and the `market` channel **separately** (they will differ — production is
   deterministic, market reacts to prices). **A donor whose traces agree at 60% is not
   reconstructible and must be rejected**, however good its rating.
3. **Rating and calendar quality.** Prefer a high-rated team, and cross-check with step 0's
   same-town instrument: replay the candidate against our three existing tapes and read its realised
   premium $/unit ratio. **We now have a measurement that tells us whether a donor's calendar is
   good before we spend a pass on it** — use it. That instrument is `analysis/s6_step0_leg1.py`.

*Gate:* a named donor with ≥3 same-submission traces, a stated per-channel agreement rate, and a
same-town price ratio ≥ the Valmorlee tape's. **If no donor clears all three, STOP and report it** —
that is a real result and it redirects S6 to C-C (MELON) rather than wasting the pass.

### Then

- Build the majority-vote route. Where traces disagree, record **why** (the disagreement set is the
  part that is state-dependent, and it is exactly what the adaptive layer has to cover).
- **Fidelity check first, before any overlay:** the reconstruction must replay against the donor's
  own recorded opponent to within a stated tolerance of the recorded bank — the S1.2 protocol,
  unchanged. A reconstruction that is worse than the raw tape is not a platform.
- **Then measure the headroom the whole pass exists for:** what is the reconstruction's shed
  occupancy curve? T2 measured the Valmorlee tape at **98/100**. If the reconstruction is also at
  98/100, the cross-turn lever is *still* blocked and that must be said plainly rather than
  discovered in step 2.

**Do not build the premium-lead overlay in this pass.** Owning the route and proving it has headroom
is the deliverable. The overlay is step 2, and it gets its own pre-registered kill.

## Gate

Standing protocol (§2.1.3-5): SMOKE 0-11 → DEV acceptance against the **non-mirror** bench →
unpinned holdout 100-147 → immutable checkpoint. **The comparison is against the raw Valmorlee
tape**, not against `v1u_base` — the tape is the incumbent.

- **Both seats on everything** (§2.1.1); `--town-pin basket` for anything touching occupancy.
- **R21 binding**: report the seed set's realised shop draw beside every dollar figure.
- **R22**: report BT via `python -m harness.cli ladder --round-robin --shop-draw` against the bench
  R25/R26 built. ⚠️ **R28** — the tapes already sweep that bench (Valmorlee BT 3008, 56-0-0), so it
  cannot score anything *better* than a tape. The donor family's sibling traces are the natural new
  rung and this pass produces them; add them.
- **§2 item 9**: confirmed mechanism and viable increment stated separately, in that order.
- §3.4's new rule: **state the surface area up front** — what is the maximum the finished
  reconstruction could earn if the overlay later fired perfectly? Step 0 killed C-A with that
  question and an afternoon.

**Kill:** if the reconstruction cannot beat the raw tape on the same-town instrument, the extra
machinery is buying nothing and the tape stays the product. Stop and record.

## Standing conditions

Provenance (episode ids, seat, team, per-trace sha256, **and the agreement rate**) in the checkpoint
ledger and any submission description; extracted routes and the reconstruction stay **gitignored and
out of this public repo** (§2.4b / R11); competitor notebook source is never opened, decompressed or
executed (§2 item 8); reference tiers 6-9 are not fetched (R23) and the CC BY-SA CSVs are not
vendored (§4.5).

**⚠️ R27 — no upload this pass.** Eviction is by submission **date**, not score: any upload drops
**Valmorlee (1.614,0)**, our best. Ueddy is still converging (1.027,8 → **1.398,7** this session),
so which tape is "the top tape" is still not decidable. When step 2 eventually ships something,
the tape must be re-uploaded *first* to survive — and that costs its converged rating (restart at
600,1, ~1 day).

## Out of scope

- **The premium-lead overlay itself** — step 2, with its own Phase 0 and kill.
- **C-A** — ⛔ refuted (§3.3). Not revisited.
- **C-B on a tape** — within-turn it is worth ~$0 (step 0 legs 1-2) and its cross-turn form is the
  same shed-blocked lever. It only becomes interesting *after* this pass proves headroom.
- **C-C (MELON)** — still sequenced last, and it is the fallback if Phase 0 finds no donor.
- **Any `agent/` production change.** Item ④ is closed; the planner is 650-1.300 BT behind the tapes.
