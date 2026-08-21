# Pass brief — Ship B component (i): transaction / weed-legality recovery overlay

> **Read first:** [ROADMAP.md](ROADMAP.md) **§7.2** (this pass), **§6 rows 26-27** (the measurement
> behind it), **§3.1** (protocol — acceptance is four numbers, wins first), **§9** (the checklist
> and the slot policy). Then [memory.md](memory.md) entries for `s6-step2d-branch-iv` and
> `s6-step2e-loss-tail`.

## Why this pass exists

The open-loop tape (`55586926`, ReCurSiON reconstruction) plays back a fixed action stream
regardless of the actual board state. When the town's per-turn `weedSpawnChance` realisation
places a WEED on a tile the tape expects to be a PLANT, the tape's action for that tile becomes
a silent no-op — it WATERs a weed, PLANTs over a plant, DIGs empty ground. These are **88
production-disagreement steps** across 178 live episodes, measured in §6 step 2d (leg A).

The mechanism: closed-loop tile control (DIG the weed, re-PLANT, WATER by actual dry state) that
a fixed-index 50-town majority vote cannot carry. The vote reproduces the **modal** production at
88/88 — it is a faithful open-loop copy, and this is the residual it cannot copy.

**Bound:** 11/178 episodes are flippable (margin < desync cost), for **+6.2 rating points**. The
per-episode own-farm loss is **$597/ep** ($14.89 decay + $4.99 weeds). This is small against the
1,036-point gap, but it is the only remaining component that is both **measured** and **cheap to
build** — the three other §7.2 components are all KILLED or blocked.

**§7.1 is dead.** Re-donoring to a top-4 route was KILLED by measurement (§6 row 29): all four
candidates are state-adaptive with cross-trace agreement 0.25–0.37 (vs ReCurSiON's 0.993). Both
slots come from §7.2.

## What to build

Extend `TapeOverlay` ([agent/tape_overlay.py](agent/tape_overlay.py)) to also overlay the
**farmer/hands** channel — currently it passes `farmer` and `hands` through verbatim from the tape
and only overlays `market`. The new overlay reads the **actual tile state** from the observation
and substitutes a legal action when the tape's action would be a no-op.

### The validity logic already exists

`_tile_valid(op, tile)` in [analysis/s6_step2e.py](analysis/s6_step2e.py:65) is the complete
checker — it returns `True` if a tile-level action is effective given the tile state. The 10
tile ops it covers: `WATER`, `PLANT`, `DIG`, `HARVEST`, `FERTILIZE`, `BUILD_COOP`,
`BUILD_PASTURE`, `FEED`, `CARE`, `COLLECT_FERTILIZER`. Move this function (or its logic) into
`agent/` so the overlay can use it at runtime.

### Recovery rules

When the tape issues an invalid tile action, the overlay substitutes the **cheapest legal
recovery** for the actual tile state. These are the desync types step 2e measured, in order of
frequency:

| Tape action | Actual tile | Recovery |
|---|---|---|
| `WATER` | WEED | `DIG` (remove the weed so the tile can be replanted next turn) |
| `WATER` | already watered PLANT | `PASS` (already done, skip) |
| `PLANT` | PLANT (already planted) | `WATER` if not watered, else `PASS` |
| `PLANT` | WEED | `DIG` |
| `DIG` | empty | `PASS` (nothing to dig) |
| `HARVEST` | no yield | `WATER` if plant and dry, else `PASS` |

The recovery is **always the single cheapest action that returns the tile to the tape's expected
trajectory**. The goal is re-sync: after recovery, the tape's next action for that tile should
be valid again. Do NOT build a full replanning system — that is §5.3(c)'s state-adaptive layer
and it is out of scope.

### Where it plugs in

In `TapeOverlay.act()` (line 105), after reading `tape_action` from the stream, and before
returning the action dict:

1. Read the player's farm tiles from `snapshot` (the parsed observation).
2. For the farmer action and each hands action, get the unit's position and look up the tile.
3. If the action's op is a tile op and `_tile_valid(op, tile)` is False, substitute the recovery.
4. Return the modified `farmer` and `hands` in the action dict.

The farmer's position is at `farm["farmer"]` (an `[x, y]`), hands positions at `farm["hands"]`
(list of `[x, y]`). The tile grid is `farm["tiles"][y][x]`.

### What NOT to change

- **Market overlay is untouched.** The strawberry sell-timing overlay works and is shipped. Do not
  modify `_decide_sells()`, the mode logic, or the market order assembly.
- **Do not condition on the town or opponent.** The recovery must be a pure function of
  `(tape_action, actual_tile_state)` — no lookup tables, no per-town tuning.
- **Do not add a learned model or heuristic.** The recovery table above is exhaustive.
- **Do not touch the tape stream itself.** The overlay reads the stream and modifies the output;
  it never mutates `self.stream`.
- **No new config arms.** This is a single unconditional fix, not a tunable parameter.

## Gate

**§3.1(4) order**, against §8's bench (A1 + A2 + A3 + `meta_route`), both seats:

1. **Per-opponent W/L per seat** — the primary acceptance criterion. Report each opponent as its
   own row.
2. **Bradley-Terry** (`harness/ladder.py`, `--round-robin`).
3. **`median_bank`** — diagnostic only.
4. **`mean_diff`** in mirror — regression detector.

Seed plan: **SMOKE 0-11 → DEV 0-47 → unpinned holdout 100-147**, both seats. This is an
**occupancy** change (tile actions alter how many tiles are occupied on any night), so it
requires **`--town-pin basket`** on both arms per §3.1(2).

**Priced loss (§3.1(6)):** `plant_decay_units_lost` and `unexpected_weeds_lost` should both
**decrease** (that is the point). Report `priced_loss_delta` and confirm it is ≤ 10% of
`mean_diff` and ≤ $500/ep.

**Pre-registered kill:** if the overlay **increases** total losses against any bench opponent on
both seats, STOP — the recovery rules are wrong. Report and do not ship.

## Package and upload

- Self-contained `main.py` with the overlay logic inlined (no `agent/` import at runtime, §2.12).
  Use `analysis/build_reconstruction_submission.py` or equivalent to build, but **inline the new
  farmer/hands recovery** alongside the existing market overlay.
- **§9 checklist before upload** — every box, including the archive-hash two-filename check.
- **Eviction is pre-decided:** drops `55575305` (Ueddy tape), keeps `55586926`.
- Record the stream sha256, step count, and the recovery hit rate in the submission description.

## What this pass does NOT do

- **Judge the submission.** §2 rule 2: nothing is read before ~100 episodes.
- **Build the deployment-neighbourhood bench** (§7.3) — after both ships.
- **Reopen the "what did the vote erase" family** — CLOSED across all channels (§6).
- **Build a market maker** — KILLED at 7.9 pts (§6 row 30).
- **Build a sell-floor lever** — §6 row 13 reopened but untested; shed wall blocks it.
- **Re-donor** — KILLED (§6 row 29).

## Standing conditions

Local episodes are played for the gate; **the only Kaggle-side action is the single upload.**
Routes, packages, replays and derived data stay **gitignored** (§3.2) and carry the verdict
string. Guards in `tests/`. Report to `baselines/<date>/`, session entry to `memory.md`,
**ROADMAP only if a plan, gate or standing rule changes**. Commit with no co-author.
