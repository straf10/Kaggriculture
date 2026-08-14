# Pass brief — ROADMAP §4.3 S3 step 1e: the feed-cash reserve, run as a race

> **Read first:** [ROADMAP.md](ROADMAP.md) §2 (method — note item 9, added last pass), §3.3, §3.4,
> §4.0, §4.3 S3 (especially the **step 1d** subsection), §6 (R12–R18); the top **two** entries of
> [memory.md](memory.md); and last pass's report,
> [baselines/2026-08-14/s3_step1d_report.md](baselines/2026-08-14/s3_step1d_report.md).
>
> Previous brief is in git at the commit before this one.

Step 1d did the right thing: it ran its mandatory Phase 0 diagnostic, found none of its three
anticipated branches, and stopped instead of building arms against an unverified mechanism. Its
trace of the *downstream* chain — zero shed WHEAT ⇒ no feed ⇒ escape at the day 1→2 boundary — is
correct and reproduced in 3 seeds × both orientations. **Keep it.**

Its *upstream* attribution is wrong, and its recommended next step ("trace the hour-1 HIRE
settlement") would burn a pass on a dead end. §1 corrects that. §2 gives the located defect. §3 is
the race.

---

## 0. Preconditions — what actually holds now

Step 1d's report already corrected the previous brief's §0, and its corrections stand:

| Fact | Consequence |
|---|---|
| **Every `checkpoints/*/` package is on disk** (`main.py` + `agent_checkpoint_*/`), not just manifests | You can `compare` against `checkpoints/v1o_2`, `v1p1b_armA1`, `v1p1b_armB`, `v1q_base` directly. `v1p1b_armA1`'s fingerprint `e9dd026478b00ffe…` matches its manifest — it is the package that was actually screened |
| `checkpoints/v1q_base` exists, fingerprint `a22cd401aa0cf691…` ≡ live `main.py` | This is the baseline for every `compare` this pass. Do not screen against live `main.py` (R16) |
| `gates/v1q_onboarding_escape/` holds last pass's replays and `diagnosis.json` | Re-usable. Do not overwrite it; write this pass's artefacts to new paths |
| `.env` has a populated `KAGGLE_API_TOKEN` | Irrelevant — no submission this pass (§5) |
| `pytest tests/` → **245 passed, 3 failed** | The 3 are `test_v1h2d_priced_gate_decides_the_three_measured_arms[*]`, which read gitignored `gates/gate_v1h2*/` artefacts. Pre-existing. Report your delta against 245/3 |

Use `.venv/bin/python` throughout.

---

## 1. First: correct two factual errors in the step 1d record

Both are load-bearing — one of them is the recommended next step — and both are checkable in about
thirty seconds against the replay that pass already recorded. **Re-verify them yourself before
editing anything.** Do not take this brief's word for it any more than the last one's.

```bash
.venv/bin/python - <<'PY'
import gzip, json
env=json.load(gzip.open('gates/v1q_onboarding_escape/replays/A@0_B@1/seed0_seat0-main_seat1-main.json.gz'))
steps=env['steps']
for seat,label in ((0,'CAND(armA1)'),(1,'BASE')):
    print('===',label)
    for i in range(1,12):
        f=steps[i][0]['observation']['farms'][seat]
        mk=[o for o in (steps[i][seat]['action'].get('market') or []) if o and o[0]!='SELL']
        placed=sum(1 for r in f['tiles'] for t in r if isinstance(t,dict) and 'animal' in t)
        print(f"  step {i}: money {f['money']:7.1f} hands {len(f['hands'])} placed {placed} orders {mk}")
PY
```

Note the indexing convention this reveals, and record it next to R18: **the action logged at
`steps[i]` is the action that *produced* `steps[i]`'s observation**, not the one applied to it.
Pairing an order at step *i* with the money at step *i+1* shifts every purchase one turn and is
what makes the settlement look lagged. It is not.

### 1.1 The HIRE settlement is identical. There is no hour-1 gap.

At step 1, **both agents are at exactly $2.980,0, with 6 hands and `hires_today = 6`.** $3.000 −
$20 (`_hire_cost` = `mult × _fib(hires_today)`, Fibonacci-summed over 6 hires) on both sides. The
"~$40 gap at the very first HIRE settlement" does not exist.

The $40 first appears at **step 2**, and it is the **CARROT seed order**: candidate emits
`BUY_SEED CARROT 1`, baseline `BUY_SEED CARROT 3` — two seeds at $20, exactly $40, and it leaves
the candidate **$40 richer**, not poorer. That is `carrot_tiles: 3 → 1` doing precisely what it
says, with no anomaly in it at all.

Correct this in the §4.3 S3 step 1d subsection and in §7's hand-off bullet. Do not delete the
step 1d record — amend it in place, in the same 🔴-marked style the pass itself used for its own
corrections.

### 1.2 The agents do **not** buy the same animals at the same steps.

The report states the PLACE sequence is "step-for-step identical between candidate and baseline".
The steps it lists (3/4/5/6…) are **purchase** turns, not PLACE turns, and they are not identical:

| Turn | Candidate (arm A1) | Baseline |
|---|---|---|
| 3 | `BUY_ANIMAL COW 1` | — |
| 4 | `BUY_ANIMAL COW 1` | `BUY_ANIMAL COW 1` |
| 5 | `BUY_ANIMAL COW 1` | `BUY_ANIMAL COW 2` |
| 6 | `BUY_ANIMAL COW 1` + **`BUY_ANIMAL SHEEP 1`** | — |
| 7 | — | `BUY_SEED STRAWBERRY 2` + `BUY_ANIMAL COW 1` |
| 8 | `BUY_SEED STRAWBERRY 2` | — |
| **Money at step 8** | **$60,0** | **$520,0** |

The entire $460 divergence is **one extra early SHEEP purchase ($500) minus the carrot-seed saving
($40)**. Both agents hold `placed = 0` for this whole window — the animals are bought and sitting
in the shed or carried, not yet on tiles.

The purchase schedule *is* the divergence. That is not a footnote to the mechanism; it is the
mechanism.

---

## 2. The located defect

`agent/executor.py:482-506` — the v1g feed-cash reserve, added after a trace found "5 animals
bought in one hour, ~$0 for wheat, the whole batch escaped":

```python
FEED_RESERVE_DAYS = 2
total_placed = sum(placed_count(snapshot, name) for name in plan.animal_purchases)
for name, target in plan.animal_purchases.items():
    placed = placed_count(snapshot, name)
    carried = sum(inv.get(name, 0) for inv in snapshot.inventories)
    shed_have = int(snapshot.shed.get(name, 0))
    in_flight = carried + shed_have          # <-- computed here
    ...
    reserve = (total_placed + buy_target) * wheat_price_est * FEED_RESERVE_DAYS
```

**`in_flight` is computed and never used in `reserve`.** The reserve counts animals already
standing on tiles plus the ones this single order would add — it does not count the animals already
bought on *previous* turns and still in the shed or in a unit's hands. Every one of those eats one
WHEAT per day the moment it is placed.

Against the trace: at steps 3-8 the candidate has `placed = 0` on every turn while 1, 2, 3, 4, 5
animals accumulate in flight. The reserve on each of those turns is
`(0 + 1) × 25 × 2 = $50` against a COW at $400 — it never binds once. The real day-1 feed liability
by step 8 is `5 × $25 × 2 = $250`. The guard built to prevent exactly this failure is bypassed by
spreading the purchases across consecutive turns instead of bunching them into one hour, which is
what arm A1's geometry causes: its PASTURE reorder opens a near slot earlier, `open_animal_slots`
reports headroom sooner, and the next `BUY_ANIMAL` is emitted a turn earlier each time.

**Three things follow, and the third is why this pass is worth running:**

1. This is a defect in the **shipped** agent, not an artefact of arm A1. The baseline computes the
   same wrong reserve; it survives only because it happens to buy one fewer animal in the window
   and keeps $520.
2. It is the first mechanism in this family that is *located* rather than inferred — a single
   expression, with a trace showing it evaluating to $50 when it should have been $250.
3. It scales with herd size. **Herd 13 (9C+4S), the §4.0 profile item this whole line of work is
   blocked behind, is 3 more animals in flight against the same near-zero reserve.** Fixing this is
   a precondition for that item, not a detour around it.

⚠️ **What is *not* established**, and must not be asserted: that fixing the reserve makes arm A1
viable. Arm A1 is REGRESSED −$7.711,5 and stays STOPPED (§3.3). Arm A1 is being used here purely as
a **deterministic reproducer** — the only 100%-reproducing failure in the repo. §2 item 9 applies:
confirming this mechanism and taking an increment are different claims, and this pass must report
both separately.

---

## 3. The race

### 3.1 Framework rules (unchanged from last pass — they worked)

1. All arms built and checkpointed **before** any arm is screened. No arm added, edited or dropped
   after another arm's result is visible.
2. One hypothesis per arm, behind its own config flag, defaulting to the inert value.
3. Same baseline (`checkpoints/v1q_base`), seeds, pin, seats for every arm: SMOKE **0-11**, **both
   seats**, `--town-pin basket`, `--arm-role regression`, `--metrics`.
4. Criteria in §3.3 are **pre-registered** — written into the report before the first `compare`,
   never edited afterwards. A criterion found to be wrong gets fixed for the *next* pass.
5. **Arm 0 runs first and is not a candidate.**
6. A STOP is final only once its own mechanism has no untested implication left (§2's STOP
   protocol). Arm X below exists to satisfy this in advance.

### 3.2 Phase 0 — confirm the reserve arithmetic before building anything

Cheaper than last pass's Phase 0, because the replay already exists. Extend
`analysis/v1q_onboarding_escape.py` (or add `analysis/v1r_feed_reserve.py`; keep last pass's script
working either way) to print, for each turn of days 0-2 on both agents:

`money` · `placed` · `in_flight` · `buy_target` · the **reserve as the code computes it** · the
**reserve as a `placed + in_flight + buy_target` liability would compute it** · the order actually
emitted.

**Gate:** the code-computed reserve must be visibly smaller than the liability-based one on the
turns where the candidate buys, and the two must converge on turns where nothing is in flight. If
they do not diverge as described, §2 is wrong — stop, say so, and do not build arms. Same
discipline as last pass, and last pass is why it is here.

### 3.3 The arms

All three are `agent/executor.py` only. None touches the scheduler, `assign()`, or any tile config.

**Arm 0 — noise floor (mandatory, not a candidate).** `checkpoints/v1q_base` against itself, SMOKE
0-11, both seats, pinned, `--metrics`. This pass's own paired-baseline `animals_escaped`,
`worker_turns_working`, `worker_turns_moving`, `crop_tile_days`, and placed-herd-by-day. Every later
number is a delta against *this*, never against a figure quoted from an earlier session (§3.3's ±5
escape noise floor is exactly why). `mean_diff` should be ≈ $0,00; if it is not, stop and find out
why first.

**Arm C1 — the minimal fix** (`checkpoints/v1r_armC1`). In-flight animals count toward the reserve:

```python
reserve = (total_placed + total_in_flight + buy_target) * wheat_price_est * FEED_RESERVE_DAYS
```

where `total_in_flight` is summed across **all** names in `plan.animal_purchases` once, before the
loop, exactly as `total_placed` is. Config flag `executor.feed_reserve_counts_in_flight`, default
**False**.

**Arm C2 — reserve against the herd the plan intends** (`checkpoints/v1r_armC2`). Same shape, but
the liability is the full target herd rather than what happens to be bought or placed yet:
`reserve = min(target_total, placed + in_flight + buy_target + lookahead) × wheat_price_est ×
FEED_RESERVE_DAYS`. Config flag `executor.feed_reserve_horizon` (`"in_flight"` | `"target"`,
default `"in_flight"` so C2 is inert until chosen). This is the variant that matters for herd 13 —
it is the one that keeps working when the target is 13 instead of 10.

**Arm X — the discriminating control** (`checkpoints/v1r_armX`). `FEED_RESERVE_DAYS` **2 → 3
alone**, leaving `total_placed` exactly as wrong as it is today. Config flag
`executor.feed_reserve_days`, default **2**, arm value **3**. If arm X also kills the escapes, then
the defect is "the reserve is too small", not "the liability is undercounted", and C1/C2's framing
is wrong — that is a materially different finding and it must be possible to detect it. Run it even
if C1 works.

Every arm is screened **twice**:

- **A1-stacked** — the arm's flag on top of `checkpoints/v1p1b_armA1`'s config. This is the defect
  test: does it kill the deterministic 48?
- **Normal config** — the arm's flag on top of `v1q_base`. This is the price: what does the fix cost
  in the world we actually ship, where the defect is latent?

### 3.4 Pre-registered criteria — copy into the report before running

| # | Criterion | Threshold |
|---|---|---|
| 1 | **Defect killed**, A1-stacked | `animals_escaped_a` ≤ arm 0's paired baseline **+5** |
| 2 | **The herd is not suppressed**, both runs | Placed animals reach the config target (**10**) no later than baseline's day, and end-of-episode placed count ≥ baseline's. **An arm that prevents escapes by not buying animals has not fixed anything** — this is §3.4's ratio lesson applied to this race, and it is the trap this arm family is most likely to fall into |
| 3 | **No structural break**, both runs | `plant_decay_units_lost`, `clipped_production_ticks`, unexplained no-ops, market-sim aborts all hard-zero (§2.1.5). Immediate kill |
| 4 | **Work is not shed**, normal run | `worker_turns_working` ≥ arm 0's, `crop_tile_days` within **±3%** of arm 0's (R17 puts both in the artefact) |
| 5 | **Dollars**, normal run | `mean_diff` not REGRESSED. INCONCLUSIVE is acceptable at SMOKE |
| 6 | **Winner** | Of the arms clearing 1-5, the largest escape reduction at flat tile-days and flat herd. Ties break to the smaller diff |

**Kill conditions, stated up front.** If no arm clears criterion 1, the reserve undercount is *not*
what starves the animals — record it as a refuted mechanism, name the remaining untested
implication, and stop. If an arm clears 1 but fails 2, the reserve is simply throttling the herd and
is not takeable — say that plainly rather than reporting the escape number alone. If **arm X**
clears 1, report the size-vs-count finding as the headline, above C1/C2, whatever they did.

---

## 4. Phase 2 — promotion (only if §3 produces a winner)

Unchanged protocol: DEV **0-47** both seats, `--town-pin basket`, `--arm-role acceptance` against
`harness/bench_agents/meta_route.py` (§2.1.4's three numbers in order: `median_bank` → W/L →
`mean_diff`); mirror DEV vs `v1q_base` at `--arm-role regression`; **unpinned** holdout **100-147**
at `--stage holdout-confirm --metrics`, both seats; final config comment written **before** the
checkpoint (R12); mechanism declared for every counter that *can* be non-zero, not only those the
pinned screen exposed (R13).

**Then** herd 13 (9C+4S on a 6/12/13 ramp) becomes screenable as its own increment with its own
brief. Not in this pass. Say so in the report; do not start it.

---

## 5. Out of scope

- **No Kaggle submission.** A token is present in `.env`; that changes nothing — S4 is not this pass.
- **Do not re-open arm A1 as a candidate.** It is REGRESSED −$7.711,5 and STOPPED. It is a
  reproducer here, nothing more.
- **Do not build Arm P / Arm F / Arm R** from the previous brief. Step 1d's trace ruled out
  PLACE-timing and FEED-contention, and §1/§2 do not reinstate them.
- Deferred items ③ (travel-ratio diagnostic, with §3.4's corrected metric) and ④ (min-cost matching)
  stay queued behind this.
- Herd 13, crew 12-14, MELON — all downstream.

---

## 6. Deliverables

1. §1's two corrections in `ROADMAP.md` (§4.3 S3 step 1d subsection and §7's hand-off bullet), plus
   the action-indexing note appended to R18 — each re-verified with the snippet in §1, not copied
   from this brief.
2. The Phase 0 reserve-arithmetic trace, quoted in the report.
3. `checkpoints/v1r_armC1`, `_armC2`, `_armX` — created before screening, fingerprints recorded.
4. `baselines/<date>/s3_step1e_report.md`: pre-registered criteria first, then arm 0's noise floor,
   then each arm's two runs, then verdicts. One table with `animals_escaped`, **placed herd by
   day**, `worker_turns_working`, `worker_turns_moving`, `crop_tile_days`, `mean_diff` side by side.
   State the **confirmed mechanism** and the **viable increment** separately, in that order (§2
   item 9).
5. `pytest tests/` reported as a delta against **245 passed / 3 pre-existing** failures. New guard
   tests for whichever arms are built (`test_v1r_*`), including one that pins the reserve
   arithmetic directly against a constructed snapshot with animals in flight.
6. `ROADMAP.md` §3.3 / §4.3 / §6 / §7 updated with the outcome and where the work goes next.
7. **A new session entry at the top of [memory.md](memory.md)** — newest-first, same house style and
   same language (Greek) as the entries above it: the instruction, each arm in one line, the
   measured numbers, what is confirmed as a *mechanism*, what is takeable as an *increment*, the
   pytest count, that nothing was submitted, and the hand-off.

---

## 7. The sentence to keep in view

Step 1d earned its stop by refusing to build arms against a mechanism it had not located. This pass
has a located one — a single expression, with a trace showing it computing $50 where the liability
was $250 — so the failure mode to avoid is the opposite one: **taking an arm that removes the
escapes by quietly buying fewer animals.** Criterion 2 exists for that, and it outranks the escape
count.
