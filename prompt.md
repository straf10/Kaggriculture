# Pass brief — T1: ship the tape as the challenger

> **Read first:** [ROADMAP.md](ROADMAP.md) §1 (the 08-15 ladder read), §2 (method), §4.1, **§4.2
> including the 🔴 REVERSED block**, §4.3 S1/S2, §6bis (submission ops); the top two entries of
> [memory.md](memory.md); and [docs/plans/item4_min_cost_assignment.md](docs/plans/item4_min_cost_assignment.md)
> §0 (why ④ is *not* this pass).

The user's direction, verbatim: **"I want the measured path where we copy the tape and if we win we
will figure it out."** §4.2's default is reversed and the decision is settled — do not re-litigate
it, and do not re-raise the §3.14a question as a blocker. It is recorded, it was reaffirmed, and it
resolves at the prize stage.

This pass ships the tape agent as the **challenger**, holding `55414570` (v1i) or `55438252` (v1o.2)
as champion per §6bis.

---

## Why this and not item ④

S2 (2026-08-11) is the only thing this repo has ever measured *above its own floor before building
it*: 3 donor tapes × {`meta_route`, `checkpoints/v1i`, another donor} × 2 seats, **0/18 below the
$57.360 floor**, worst case $57.673, degradation 7-37% against hard opponents, donor home banks
$82-95k. The no-ops are **opponent-independent** (they start day 4-10 because the route drifts off
its own trajectory, not because of market competition) ⇒ the measurement calls for a **light**
repair layer, not a heavy one.

Meanwhile the 08-15 ladder read says the clock is the binding constraint: v1o.2 resolved at **620,4**
on +$5.069/ep of local production, rank **2736/4555** (−518 places with no code change), deadline
**2026-09-30**. Item ④ is an 8-step build that a tape never calls. It is the hedge, not the path.

---

## 0. Step 0 — re-verify the donors on 1.32.7 *(do this before anything else)*

The engine moved to **1.32.7** on 2026-08-15 (D28: the `hinge` curve on CARROT/TOMATO/EGG). Two
facts make the tapes almost certainly safe, and "almost certainly" is not the standard:

- the top-9 profile grows **zero** CARROT/TOMATO/EGG (`data/derived/b3_target_profile.json`,
  `tile_days_per_crop` = MELON/STRAWBERRY/WHEAT only), so the changed curves have nothing to price;
- TOMATO/EGG are a strict no-op below their knee anyway.

**Do:** re-run the S1.2 exact-replay check (donor + opponent tape under the same seed reproduces
the recorded bank) on 1.32.7. It was **0,0000% error, 3/3 donors** on 1.32.6.

- **Still 0,0000%** ⇒ proceed, and record it. The bump is orthogonal.
- **Any drift** ⇒ stop and find it before building anything. A tape whose own fidelity check fails
  is not a tape.

⚠️ Note that `baselines/` is gitignored and **not present in a fresh clone** — the donor JSONs from
2026-08-11 (`baselines/2026-08-11/donors/*.json`) may need re-extraction via
`analysis/s1_extract_donors.py`. Keep the chronological protocol: cutoff `EpisodeId 91476157`,
select from *older* episodes, evaluate on strictly later ones.

⚠️ Also re-run `analysis/v1t_engine_probe.py` against the newest daily dataset at the start of the
pass. As of the 2026-08-14 dataset the ladder was **28/28 on 1.32.6** — the bump has not rolled out.
If it has rolled out by the time you read this, the S2 retention numbers were measured on the old
engine and step 0's verdict decides whether they still hold.

---

## 1. What to build

`analysis/tape_agent.py` already exists and does **not** touch `agent/`. It was written for the S2
diagnostic, not for submission. The work is to make it shippable:

1. **A repair layer, deliberately light.** S2's failure map
   (`baselines/2026-08-11/s2_failure_map.json`) says what breaks and when. Follow the measurement:
   local WEED repair (DIG → retry → short replay) is what every top notebook carries, and S2 says
   the tape *degrades*, it does not collapse. Build the smallest thing the failure map justifies.
   **Do not** build a general adaptive planner behind the tape — that is re-deriving S3 by another
   name, and it is what this pass exists to avoid.
2. **Provenance, non-negotiable (§4.2).** episode id, seat, team, action-stream sha256 in the
   checkpoint ledger *and* in the submission description.
3. **The route stays out of the public repo (§2.4b).** Gitignored, local only. This repo is public.
   Verify with `git status` before committing, not after.
4. **Both seats (§2.1.1).** Donor streams are recorded from one seat; the top farms run the same
   policy in both.

## 2. The gate

Standing protocol, unchanged: SMOKE both seats → DEV acceptance against the **non-mirror**
`meta_route` bench (§3.4 — mirror results have been worthless here twice) → unpinned holdout confirm
→ immutable checkpoint. The floor to beat is the live **$57.360**, and the honest target is the
donors' own $82-95k minus the measured 7-37%.

**Kill:** if a repaired route lands below $57.360 on the acceptance arm, §4.3 S2's own kill clause
fires — open-loop replication is not the path, and the work returns to
[docs/plans/item4_min_cost_assignment.md](docs/plans/item4_min_cost_assignment.md) step 1.

## 3. Submission

Per §6bis, with explicit user approval before the upload — the pair is the user's call, not the
pass's. Auth: `export KAGGLE_API_TOKEN=$(grep KAGGLE_API_TOKEN .env | cut -d= -f2)`; the CLI is
`.venv/bin/kaggle`, not on `PATH`.

---

## Out of scope for this pass

- **Item ④** — has its own plan, 8 steps, first two are diagnostics with no `agent/` change.
- **The D28 carrot opportunity** — real (measured: 18% of episodes drain CARROT past the knee, 54%
  for TOMATO), and it is the first candidate ever for §3.3's standing v1k re-test trigger. It is a
  separate pass with its own Phase 0. Bundling it here would make both unreadable.
- **Anything in `agent/`.** The tape agent lives beside it, not inside it.
