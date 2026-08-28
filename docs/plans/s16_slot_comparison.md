# S16 — Which of the two live overlays is stronger?

> **Type:** implementation brief for a fresh agent. Self-contained — assume nothing from prior
> conversation. **Measurement-only pass. No `agent/` change, no upload, no submission.**
> Its product is a **decision**: which slot the next upload evicts, with a number behind it.
> **Written:** 2026-08-28.

## Why this pass exists

ROADMAP §9 rule 3 currently pre-decides that the next upload drops **`55675634`**. That decision
rests on **its score being the lower of the two by 11,9 points** — which §2 rule 2 classifies as
noise. We have never compared the two live agents against each other. This pass fixes that, and it
is the cheapest high-value measurement left: it spends no slot and it gates every future upload.

## Read first — and do not re-derive any of this

`ROADMAP.md` §1 (the active pair), §2 rules 2/3/**9** (the readability test and its corollary —
this pass is built on that corollary), §3.1 rules 1/2/4/5 (both seats · occupancy classification ·
the four acceptance numbers · the selection key), §6 rows 26-27 (what tile recovery was bounded at),
§7.2 (the components table and the **thin-differentiation** flag), §8 (Instrument A, screen/confirm
split), §9 (submission ops + slot policy).
`docs/plans/s13_seat_asymmetry.md` — read §Phase 1's **power** discussion before pre-registering
anything here. It is the same sample-size regime and it is the trap this pass will otherwise fall
into.
Memory: `s9-phase2-gate`, `s7-ship-b-tile-recovery`, `s9-live-read-55726984`,
`kaggriculture-active-pair-mechanics`, `kaggle-ladder-rating-mechanics`.

---

## 0. What is already known — input data, do not re-measure

**The two live agents share a byte-identical backbone.** Both submission descriptions carry
`stream sha256 1d9e0efd…`: the same 719-action ReCurSiON reconstruction. They differ **only** in the
overlay, and the two overlays are mutually exclusive by construction
(`TapeOverlay.act()` returns early on `mode=="liquidate"`, `agent/tape_overlay.py:270`).

| | `55726984` (slot A) | `55675634` (slot B) |
|---|---|---|
| uploaded | 2026-08-23 23:07 | 2026-08-21 19:06 |
| public score (board 08-27 21:14) | **1.633,7** | **1.621,8** |
| public episodes | 159 | **244** |
| replays on disk | 145 | **119** |
| overlay | H2 STRAWBERRY tail-liquidation (`mode="liquidate"`, F=25 / first_day=22 / h_max=12 / d_days=4 / force_step=686) | market overlay + **tile recovery**, 6 rules on WATER/PLANT/DIG/HARVEST desync, 88/719 eligible steps |
| class (§3.1 rule 2) | **market-only** | **occupancy** |
| evidence it shipped on | Instrument A, 412 episodes: `232-180 → 255-157`, McNemar **c=23 b=0 p=2,4e-7**; dev-screen 43-0-5, unpinned holdout 39-0-9 | **SMOKE 336-0-0 vs the §8 bench** — never gated on Instrument A, never read on live episodes |

🔴 **The evidence behind the two slots is not of equal strength**, and that asymmetry — not the
score gap — is the real reason this pass is worth running.

**What the raw live numbers say, and why they do not settle it** (measured 2026-08-28 off the
cached replays; **input datum, do not re-derive**):

| submission | all episodes | **after its first 70** |
|---|---|---|
| `55726984` | 79-65 · 0,549 | **34-40 · 0,459** (n=74) |
| `55675634` | 86-33 · 0,723 | **29-20 · 0,592** (n=49) |
| `55586926` *(inactive, the shared base)* | 146-147 · 0,498 | 100-123 · 0,448 (n=223) |

The 0,723 is placement burst (§2 rule 2). The post-70 columns look decisive for slot B — **and they
are not comparable**: B's 119 cached replays end at episode `97703521` (2026-08-21/22) while A's run
to 2026-08-27. Different calendar window ⇒ different field ⇒ §2 rule 9's corollary says these two
readings compare nothing. **Fixing exactly that is Phase 1.**

**Do not reopen:** the H2 rule or its parameters (frozen, shipped) · re-donoring (§6 row 29) ·
whether tile recovery is worth building at all (§6 rows 26-27 bounded it at +6,2 points and it is
already shipped) · the seat-asymmetry question (§6 row 33).

---

## 1. Phase 1 — read both agents in the SAME window (primary method)

§2 rule 9's corollary: *"to compare two of our own agents, field both and read them in the same
window."* **Both are fielded right now.** This is the cleanest comparison available and it needs no
bench at all.

1. **Complete the archive.** `source .env`, then for each submission
   `kaggle competitions episodes <SUB> -v`, diff against
   `data/archive/raw/live_<SUB>/`, and pull the missing ids with
   `kaggle competitions replay <ID> -p data/archive/raw/live_<SUB>/`.
   **gzip each file immediately after download** — they arrive at ~31 MB and store at ~1,3 MB, so
   the ~125 missing `55675634` replays cost ~165 MB on disk but ~4 GB if left uncompressed.
   Every reader in the repo (`analysis/s8_replay_io`) accepts both forms.
   ⚠️ The `episodes -v` capture ends with a CLI hint line; strip it or parse defensively.
2. **Define the window before looking at any outcome.** The overlap is
   `[max(A_upload, A's 70th episode createTime), now]` intersected with B's episodes in the same
   date range — i.e. **drop A's placement burst, then take the same dates from B**. Report the
   resulting n for each side. If either side has n < 40 in the window, say so and go to §2;
   do not widen the window to manufacture a sample.
3. **Build the comparison with the panels that already exist.** Generalise
   `analysis/s9_live_read_55726984.py` from a hard-coded submission to a `--submission` argument
   (`LIVE`, `EP_CSV`, `OUT`, `SUBMITTED_AT` are the only submission-bound constants) and run it for
   both. **Do not write a second instrument** — that is the rule that caught the off-by-one in
   S10 P4 and the leakage bug in S11 B2.0′.
4. **Report, in §3.1 rule 4's order:**
   1. **per-opponent W/L per seat** — a row per opponent, never a pooled figure. Any opponent both
      agents met inside the window is the strongest evidence in this pass; list those separately.
   2. **win rate by opponent-strength zone** (`panel_b`'s controlled join: opponent
      `LastSubmissionDate` must precede our episode's `createTime`), and a **CMH** stratified by
      zone. The two agents sit 12 points apart, so matchmaking hands them slightly different
      opponents — the zone stratification is not optional.
   3. `median_bank` and margin — diagnostics only.
5. 🔴 **Pre-register the gate, and state its power first.** Compute the minimum detectable
   difference in win rate at the actual n **before** running the test, the way S13 §Phase 1 does.
   Declare a winner only if **CMH p < 0,05 *and* the zone-stratified gap ≥ 0,10**. Otherwise the
   verdict is **"not separable at this sample size"** — which is a real result, not a failure, and
   sends the pass to §2. **Do not report a direction as a finding when the test does not clear.**

---

## 2. Phase 2 — Instrument A, only if Phase 1 is not separable

`analysis/s10_replay_bench.py` recomposes every recorded ladder episode with our seat substituted
and the opponent held as a tape. Its α-control reproduces **509/509** episodes bit-exactly, and its
`h2_calibration` mode reproduces the frozen S9 result on the 412-episode confirm set.

🔴 **Read this before writing any code: the bench is not neutral between these two arms.**
H2 is **market-only**, so the town is bit-identical and the recorded opponent tape stays valid.
Tile recovery is **occupancy** — it changes which tiles are occupied, and `_end_of_day` spends one
per-day RNG on `_spawn_weeds` for player 0 then player 1 **before** drawing the shop unlock
(§3.1 rule 1), so a single recovered tile re-rolls the remaining shop sequence for **both** farms.
The opponent's fixed action stream then keeps playing a town that no longer exists, while our arm
recovers from its own desync. **That bias runs in favour of the tile-recovery arm**, and it must be
declared, not discovered.

1. **Add a `recovery_calibration` mode** beside `h2_calibration`, driving the same
   `agent/tape_overlay.py` path (`_tile_valid` / `_tile_recovery` / `_recover_tile_actions`,
   lines 36-190). ⚠️ The shipped `55675634` carries its **own inlined copy** in
   `analysis/build_tape_overlay_submission.py` (§9's G13 bit-equivalence requirement). **Assert the
   two agree before trusting any bench number** — if they have drifted, the bench is measuring an
   agent we never shipped, and that is a STOP.
2. **Quantify the bias before using the result.** Report, per episode, how many steps the arm
   actually fires on (the ship note says 88/719 eligible) and how many of the 509 α-control episodes
   still reproduce the recorded rewards **with the recovery arm active on our seat only**. A large
   divergence is the expected, correct behaviour of an occupancy arm — record the figure and carry
   it as the error bar. Do not tune anything to shrink it.
3. **Run three arms on the same 412-episode confirm set** (`55586926` + `55675634`; screen stays
   `55726984`, never mixed): base (bare reconstruction) · base+H2 · base+recovery. Report **McNemar
   per seat** for each overlay against the shared base, then the two deltas side by side.
4. **Gate:** an overlay wins only if it beats the shared base at **p < 0,01 on both seats** — the
   bar H2 already cleared. If the recovery arm cannot clear it once the §2.2 bias is stated, the
   honest reading is *"B shipped on a SMOKE and still has no gated evidence"*, and that decides the
   eviction on its own.
5. 🔴 **§7.4 binds here.** If this bench ranks the two agents in the order the live window of §1
   reversed, **say so and stop tuning against it.** A local instrument that contradicts the ladder
   is not an instrument. That has already happened once in this repo (v1i above v1h).

---

## 3. Phase 3 — the decision, written down

Whatever §1 and §2 return, the pass ends by rewriting **ROADMAP §9 rule 3's pre-decided eviction**
with the number behind it, in one of three forms:

- **"B is weaker (evidence X) ⇒ the next upload drops `55675634`"** — the current default, now earned.
- **"A is weaker (evidence X) ⇒ the next upload drops `55726984`"** — and then §7.2's differentiation
  argument has to be re-made from scratch, because H2 is the only market-side differentiation the
  pair has.
- **"Not separable (power Y at n=Z) ⇒ the eviction stays with `55675634` on the *evidence-asymmetry*
  ground: A carries a McNemar-gated edge over the shared base, B carries only a SMOKE."**

And it records the second finding this pass cannot avoid producing: **§7.2's thin-differentiation
flag is now measurable**. Two overlays on one byte-identical backbone is exactly the *"two
near-identical active submits"* pattern §9 rule 2 warns kills both on a meta shift. State whether
the measured behavioural difference between the two arms is large enough to call them differentiated
at all, or whether the next upload should deliberately buy differentiation instead of strength.

---

## 4. Standing rules

1. **No `agent/` change, no upload, no submission.** This pass spends no slot.
2. **Reuse, do not duplicate.** Generalise `s9_live_read_55726984.py` and extend
   `s10_replay_bench.py`; read replays only through `analysis/s8_replay_io`; call
   `engine_reference/kaggriculture.py` rather than restating its arithmetic.
3. **Pre-register every threshold before running against it**, and state the minimum detectable
   effect at the real n first (S13's lesson). Report every stratum, not the best one.
4. Do not tune a parameter or move a threshold to manufacture a separation. A kill criterion is a
   **STOP and ask**, never a wider window.
5. Every derived JSON carries a `verdict` string and a generation date; every code fix ships with a
   test that reddens on the pre-fix version (verify by reverting).
6. Do not touch `harness/seeds.py::NAMED_SEED_SETS`; live seeds never enter it.
7. Every bench "look" writes one line to `gates/s10_bench_ledger.jsonl` (§8).
8. **A direction is not a finding.** If the test does not clear its pre-registered bar, the verdict
   is "not separable", stated with its power — not the sign of the point estimate.

## 5. Deliverables

| task | files |
|---|---|
| Phase 1 | completed `data/archive/raw/live_55675634/` (+ `live_55726984/`), `data/derived/s16_slot_window.json` (window definition, per-opponent rows, zone table, CMH, power, verdict), a short note in `baselines/2026-08-28/` |
| Phase 2 (if reached) | `recovery_calibration` mode in `analysis/s10_replay_bench.py` + its inline-vs-shipped equivalence test, `data/derived/s16_bench_three_arm.json`, one line in `gates/s10_bench_ledger.jsonl` |
| Either outcome | rewritten **ROADMAP §9 rule 3** eviction pre-decision, and a §7.2 note on whether the pair is genuinely differentiated |
