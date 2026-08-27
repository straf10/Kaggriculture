# S12 — MELON sell-schedule repair (task α)

> **Type:** implementation brief. Self-contained — assume nothing from prior conversation.
> **Written:** 2026-08-27. **Upload only if the agent is provably better** (§5 gate).
> Touches `agent/`. One upload at most, and only through §5.

## Read first

`ROADMAP.md` §3.1 (protocol), §6 rows 30/31 (glut is real, WHEAT is the exception), §8 (the bench),
§9 (submission ops, cutoff ~09-23).
`docs/plans/s11_instrument_completion.md` §1 — the lockstep-quoting result binds any revenue model here.
Memory: `s9-live-read-55726984`, `price-floor-liquidation-sink`, `kaggle-ladder-rating-mechanics`.

---

## 1. The measurement this is built on

97 ladder replays of `55726984`, our own MELON sell schedule (measured 2026-08-27, **input datum —
do not re-derive**):

| day | units/ep | median price | cum. volume | revenue/ep |
|---:|---:|---:|---:|---:|
| 10 | 30 | $250 | 26% | $7.500 |
| 20 | 60 | $152 | 79% | $9.120 |
| 21 | 12 | $51 | 89% | $612 |
| 22 | 12 | **$4** | 100% | **$48** |

114 units on **four days**, weighted mean sell-day **17,68**. The last 24 units are **21% of volume
for 3,8% of revenue**, and the final 12 go at essentially the floor.

Two independent readings agree that this is the wrong schedule:
- **Ours (§6 row 31):** MELON is `above_func 'sq'`, `above_target 3,6` — at +100 units above
  baseline it bottoms at **$4** against a $250 base. Our own 60-unit day-20 block is the crash.
- **External (forum price census, 5 replays / 1 agent, 2026-08-27):** MELON peaks ~day 10 at 272 and
  ends at 60; a melon sold day 25 is worth ~⅕ of one sold day 12. Treat the exact peak day as
  approximate — it is one agent and prices are endogenous — but the **direction** matches ours.

**The lever is not "sell earlier".** Dumping 114 units on day 10 crashes the price ourselves, which
is what §6 row 31 measured. The lever is **spreading a 4-day lumpy schedule across the days where
the price recovers**, under our own impact. That is an optimisation with a real interior optimum,
not a threshold flip.

🔴 The S9 glut work (`s7-glut-phase0-desk`, S9) ruled MELON out of the **hold/meter-up** family
(absorption 1/day). This is the opposite direction — **pull forward and spread** — and is not
covered by that kill. Do not treat it as re-opening a closed row.

---

## 2. What we are NOT doing

| | why |
|---|---|
| Re-opening B2 / opponent inventory | Killed in S11. No consumer. |
| Dropped-SELL repair overlay | §10 risk 7: $24.420/ep but Δ only $1.877 loss-vs-win ⇒ rank-neutral. |
| Touching STRAWBERRY / the H2 rule | H2 is shipped and frozen. This arm is MELON-only and must leave H2 byte-identical. |
| "Fixing" the seat-1 `step` field | **Not a bug at runtime** — see §6. Do not patch it. |

---

## 3. Build

**Channel: `agent/tape_overlay.py`, `mode="augment"`.** The pull-forward machinery already exists
(`pull_forward_before_step`, the sell-ahead controller) and was built for exactly this shape: keep
every tape order verbatim and only **add** earlier sells, so shed occupancy is monotonically ≤ the
tape's — no new overflow, no feed starvation. Reuse it; do not write a second overlay.

**The rule (one parameter family, declared before any run):**

```
For MELON, on each step from `pf_open_day` to `pf_close_day`:
    if market_price(MELON, inv) >= pf_floor:
        sell up to pf_rate units from shed, capped so the post-sale
        quote stays >= pf_floor
Leave every tape order untouched; this only ADDS sells ahead of them.
```

- `pf_open_day` — first day we may pull forward to. Candidates 9, 11, 13.
- `pf_close_day` — last (the tape's own day-20 block is the target). Fixed at 19.
- `pf_floor` — do not sell below this quote. Candidates 120, 160, 200.
- `pf_rate` — max units/step. Candidates 2, 4, 8.

🔴 **Declare the grid before running it** and report every cell, not the best one. §3.1 forbids
picking a winner post hoc.

**Constraints that must hold by construction, not by test:**
1. `agent/` changes are additive and MELON-scoped. H2's STRAWBERRY path stays byte-identical —
   verify with the existing bit-exact H2 test, not by inspection.
2. The overlay reads only `obs` and our own private state. No opponent action.
3. Any change lands in **both** `agent/tape_overlay.py` and the inlined copy in
   `analysis/build_tape_overlay_submission.py` (G13, bit-equivalent).

---

## 4. Measure

**Instrument A, the existing bench** (`analysis/s10_replay_bench.py`), unchanged.

- **α-control first.** Both sides tape must still reproduce 509/509 bit-exactly. If it does not,
  stop — the harness moved, and nothing measured after that is readable.
- **Screen:** `55726984` (97 eps). **Confirm:** `55586926 + 55675634` (412 eps). Never tune on the
  confirm set.
- **Both seats, always.** Report `by_seat` separately (§6 below).
- Report per arm: **W/L and McNemar `c`/`b`**, `median_bank`, MELON units and $ by day, and the
  realised floor-unit count. Wins are the currency — dollars are a diagnostic (§3.1(4)).

**Acceptance (pre-registered, do not move):**

| gate | threshold |
|---|---|
| α-control | 509/509 bit-exact |
| H2 regression | STRAWBERRY path byte-identical |
| Screen | `c > b`, McNemar **p < 0,01** on 97 eps |
| Confirm | `c > b`, McNemar **p < 0,01** on 412 eps, **same sign in both seats** |
| Floor units | must **not** increase vs baseline (`price-floor-liquidation-sink`) |

**Kill criteria — stop and ask, do not widen:**
- Confirm-set `b >= c`, or the sign flips between seats ⇒ **dead**, one §6 row, nothing else.
- Best cell beats baseline by **< 10 net wins on 412** ⇒ below the noise the ladder can resolve;
  **do not upload**, write it up as measured-and-too-small.
- α-control breaks ⇒ stop, fix the harness first.

---

## 5. Upload gate — the only path to a submission

An upload happens **only** if all of §4's acceptance rows pass. Then:

1. Build via `analysis/build_tape_overlay_submission.py`; verify the built file is **bit-exact**
   against the in-repo rule on ≥400 replays before it leaves the machine.
2. **Eviction is by date.** A new upload evicts `55675634` (the cheaper slot) and leaves
   `55726984` + new. That is the intended trade — confirm it explicitly before uploading.
3. **Upload by 2026-09-10.** A submission needs ~100 ranked episodes to be readable, and the
   episode rate varies ~10× between agents; later than that and the result is unreadable before
   the ~09-23 freeze.
4. **Judge on episodes, not hours** — see §6. Do not re-roll before 100 episodes.
5. No upload in the last 48h; a full day of margin before 09-30 (§9).

If §4 fails: **no upload.** Finishing with the current pair is a legitimate outcome.

---

## 6. Two corrections from external material (verified 2026-08-27)

**(a) The seat-1 `obs["step"]` "bug" is a replay-serialisation artifact, not a runtime bug.**
A forum post claims seat 1 never receives `step`, so any step-indexed agent replays its turn-0
action forever in half its games. The stored state does show it — `env.steps[i][1].observation`
has `step: None` on every turn, in local `env.run()` and in our live ladder replays alike — because
`step` is absent from `kaggriculture.json`'s observation schema and the interpreter does not
propagate it. **But the observation actually delivered to the agent is correct:** instrumenting a
seat-1 agent shows it receives `0,1,2,3,4…`. Our own α-control corroborates this — `tape_agent`
does a bare `obs["step"]` index and reproduces 509/509 episodes bit-exactly, which is impossible if
seat 1 got `None`. **No agent change. Do not "fix" this.**
🔴 The one real consequence is for **offline tooling**: anything reading
`steps[t][1]["observation"]["step"]` from a replay file gets `None`. Read seat 0's observation for
shared fields — the analysis layer already does.

**(b) A real seat asymmetry exists and is unexplained.** Live, on 97 episodes of `55726984`:

```
seat 0: 30W-16L, WR 0,652, median bank 94.027 vs 89.471
seat 1: 24W-27L, WR 0,471, median bank 90.061 vs 88.186
```

18 points of win rate. It is **not** the `step` field (a), and **not** MELON timing — both seats
sell 114 units at a weighted mean day of 17,68, identically. At n=46/51 the gap is suggestive, not
significant (**p ≈ 0,07**), so it is a **question, not a finding**. It rides along here: this pass
reports `by_seat` on every arm anyway, which either reproduces the split on 412 episodes or
dissolves it. **Do not build anything for it until it survives 412.**

---

## 7. Standing rules for this pass

1. One upload at most, and only through §5. No upload if the gates fail.
2. Do not tune a parameter or move a threshold to pass a gate. Hit a kill criterion → **STOP and ask**.
3. Declare the parameter grid before running it; report every cell.
4. One implementation per concept. The pull-forward channel already exists — extend it, do not add
   a second overlay. Call engine rules, never re-implement them.
5. Derived artifacts to `data/derived/` (gitignored); every derived JSON carries a `verdict` string
   and a generation date.
6. Every correction ships with a test that **reddens on the pre-fix code** — verify by reverting.
7. Do not change `harness/seeds.py::NAMED_SEED_SETS`; do not pass live seeds as `--seed-set`.
8. Both seats on every arm. Report `by_seat` unpooled.

## 8. Sequencing against the clock

| by | |
|---|---|
| 08-29 | α-control green, overlay built, grid declared |
| 09-02 | screen on 97 eps, all cells reported |
| 09-05 | **decision point** — confirm on 412, or kill |
| 09-10 | upload **iff** §5 passes; otherwise stop and finish with the current pair |
| 09-23 | freeze. No new code |
| 09-30 | the two slots hold the two best agents |
