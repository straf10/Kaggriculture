# Pass brief — T2: the market overlay on the tape's production

> **Read first:** [ROADMAP.md](ROADMAP.md) §1 (the 2026-08-16 ladder read), **§4.1** (where the
> top-30's remaining spread lives), §4.2 (the tape decision + its three standing conditions), §4.3
> S3 step 3, §3.2(7)-(8) (our own realised prices), §6bis (submission ops); the top two entries of
> [memory.md](memory.md); and the T1 pass's own report.

## Where we are

T1 shipped the raw donor tape and it scored **1.091,1** — rank **1719/4690**, **+438,6 over our
best-ever hand-built agent** and **+447,2 over its own pairmate**. The tape decision is settled by
measurement, not argument.

T1 also produced the finding that defines this pass. The premised WEED repair layer was **refuted**:
the farm runs **byte-identically against every opponent (0 collisions)**, the shed ends empty, and
the **entire 7-37% degradation is realised-price competition** — **STRAWBERRY −61%**.

So the tape's physical trajectory is robust and its *only* measured exposure is price. That is
exactly the thing §4.1 says decides the top of this ladder ("production at the top is a copied
constant; the entire remaining spread is realised price", on STRAWBERRY/WOOL/MILK), and exactly the
thing we already have built, gated and idle: `agent/sell_ahead.py`, `agent/demand.py`,
`checkpoints/v1i` (holdout `GO=True`), whose §3.2(8) realised prices — MILK **$210,62**, WOOL
**$196,81** at 1,7× the opponent's volume — already match or beat the top-30.

## What to build

**A hybrid: open-loop production, closed-loop market.**

The engine's action is `{"farmer": [...], "hands": [[...]], "market": [[...]]}`. Keep the donor's
`farmer` and `hands` **verbatim** — that is the half T1 proved byte-identical and it is what buys
the $117k production. Replace the `market` list with our own sell logic driven by the live
observation.

This targets the measured −61% directly, changes nothing about the trajectory that was just proven
robust, and reuses code that already passed an unpinned holdout.

### ⚠️ Phase 0 — mandatory, and it is the whole risk

**The tape's production is coupled to its cash curve.** Its `farmer`/`hands` stream contains PLANT
and PLACE actions that depend on seeds and animals bought by *its own* market orders. Change the
sells and you change money; a BUY that silently fails is a desync — and D15 says invalid actions are
**silent no-ops**, so it will not announce itself.

Before building the overlay, measure:

1. The donor's full **purchase schedule** (turn, item, qty, price, money before/after).
2. The **minimum cash trajectory** — how close does the donor ever come to being unable to afford
   its next purchase? That margin is the entire safety budget for changing sells.
3. Whether our overlay can be constrained to **never sell below the donor's own cumulative cash
   curve** at any turn (a floor, not a target).

*Gate:* if the donor's cash margin is thin at any purchase, the overlay must be **cash-constrained**
(never let money at turn *t* fall below the donor's own money at turn *t*). If that constraint makes
the overlay a no-op, say so and stop — that is a real result.

### Then

- Overlay our existing `sell_ahead` + `demand` logic on the market channel only.
- Keep `maxMarketOrdersPerTurn = 10` in view: the donor already spends orders, and §3.3's v1j lesson
  is that the engine **silently drops** the rest.
- **Both seats** (§2.1.1).

## Gate

Standing protocol: SMOKE → DEV acceptance against the **non-mirror** bench → unpinned holdout →
immutable checkpoint. The comparison is **against the raw T1 tape**, not against `v1o.2`.

⚠️ T1 recorded that a formal `GO=True` is **structurally unreachable** for a receipt-less tape (the
metric gate needs `agent/` accounting). The hybrid re-introduces our own market code, so part of the
accounting comes back — establish up front which legs can now be scored and which cannot, and say so
in the report rather than letting an unreachable `GO` look like a failure.

**Kill:** if the overlay does not beat the raw tape on realised STRAWBERRY $/unit, it has missed the
one thing it was built for — stop and record, rather than tuning.

## Also worth doing in this pass (cheap)

**Ship a second donor as the other half of the pair.** `55438252` (v1o.2, 643,9) is now the weak
half by ~450 points, and §4.4#1 says a frozen tape **decays** (v27 measured its own frozen v26 going
87/90 → 14/27). Two independent tapes decay independently and double our read on donor robustness.
Kaito and Ueddy were already extracted under the S1.2 chronological protocol.

## Standing conditions (§4.2) — unchanged, and they are what keep this option open

Provenance (episode id, seat, team, sha256) in the checkpoint ledger **and** the submission
description; the route stays **gitignored and out of this public repo** (§2.4b — T1's
`build_tape_submission.py` already refuses to write to a tracked path; keep it that way); §3.14a /
§2.5 resolve with the Sponsor **only if we finish top-10**. At rank 1719 that is not yet live, but
this pass is aimed at making it live, so do not let the discipline slip now.

## Out of scope

- **Item ④** — ⛔ closed and refuted (steps 3-8 never start). See `docs/plans/item4_min_cost_assignment.md`.
- **Any `agent/` production change.** The planner is not the product; T1 settled that.
- **The D28 carrot opportunity** — still a separate pass with its own Phase 0.
