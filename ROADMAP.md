# ROADMAP — Kaggriculture

> **This is the one plan.** It replaces `docs/MASTERPLAN.md` ("the strategy") and
> `current_phase.md` ("what we're building now"), both deleted on 2026-08-11. Their durable
> *measurements* are carried forward in §3; their narrative is retired. Full history is in git and
> in [memory.md](memory.md).
>
> Written in English (like [README.md](README.md) and [LICENSE](LICENSE)) because this is a
> root-level document in a public repo. The curated reference and dated meta layers
> ([docs/reference/](docs/reference), [docs/meta/](docs/meta)) stay in Greek and stay authoritative
> for numbers — this file points at them, it does not restate them.
>
> Created **2026-08-11**. Engine ground truth: **`kaggle-environments==1.32.6`**, byte-mirrored in
> [engine_reference/](engine_reference). Where docs and engine disagree, the engine wins.
>
> **The strategy, in one line** *(restated 2026-08-17)***:** the top of the ladder is a **mirror
> match** — both seats sell the same basket in the same volume in 150/150 episodes — and the winner
> takes a median **$2.826** on a **1,05× realised-price edge**. So: field the copied production
> (done — two tapes), then win that 1,05× with a market layer the crowd cannot copy off a replay.
> §4.1b, §4.3 S6.
>
> *The previous one-liner — "win the premium-sell race that is the only thing still separating
> them" — named the right arena and the wrong prize: §4.1's per-team price spread turned out to be
> 99-100% the town's random shop draw. §4.1b.*

---

## 1. Where we actually are

| | Value | Source |
|---|---|---|
| 🟢 Our best public score | **1.617,6** — `55548339`, the **T1 open-loop donor tape**, read 2026-08-17 (up from 1.091,1 on 08-16 as it kept converging). Beats our best-ever hand-built agent (**652,5**, v1h) by ~**+965**, and v1o.2 (647,5) by ~**+970** | `kaggle competitions submissions` |
| 🟢 Our rank | **1263 / 4947** (2026-08-17 late read) — from **1719 / 4690** yesterday and **2736 / 4555** the day before | `kaggle competitions list -s kaggriculture -v` |
| 🟢 Second tape converging | `55575305` (Ueddy) **1.027,8 → 1.398,7** across this session, still climbing from a 600,1 start. Valmorlee sits at **1.614,0** (from 1.617,6 — converged, drifting slightly down) | same |
| 🔵 A first: a local metric that tracks the ladder | S6 step 0's **same-town** control ranked **Valmorlee above Ueddy** on realised premium price (1,25× STRAWBERRY / 1,13× WOOL against the other donors in a shared town), and the ladder currently agrees (**1.614,0 vs 1.398,7**). ⚠️ Ueddy has **not** converged, so this is *consistent so far*, not confirmed — but it is the first time a local number in this repo has predicted a ladder ordering, and it did so precisely because the comparison held the town fixed (§4.1b) | `baselines/2026-08-17/s6_step0_report.md` |
| 🔴 **The donor cross-check nobody had run** | **A copied route's ladder ceiling is its donor submission's own rating, and ours was a rank-1018 agent.** Public leaderboard, read **2026-08-17 17:16 UTC** (4.979 teams): **Valmorlee — the T1 donor — is #1018 at 1.842,4**, last submission **08-11 20:34**, i.e. the exact generation we taped. Our tape converged at **1.617,6 = 88% of it**. The tape did not stall because it is a tape; it stalled because **the donor tops out at ~1.8k**. Direct counter-evidence that open-loop is the limit: **Peter Parker is a *pure* frozen tape** (12 traces, **1** distinct full-market fingerprint — zero town-conditioning) and sits at **#29 / 2.844,2**. And the S6 donor **ReCurSiON is #4 at 3.004,6**, last submission **08-14 14:14** — *before* the 08-16 episode dataset, so the 50 traces we reconstructed from are that submission's generation. **カワシギ #1 (3.190,1)** is the town-adaptive team Phase 0 rejected as unreconstructible (agreement 0,31), which confirms §4.3's anti-correlation finding from outside the repo | `kaggle competitions leaderboard kaggriculture -d`, this session |
| 🟢 What this settles | **The §4.2 tape decision was correct, and it is now measured on the ladder, not locally.** The whole v1e→v1o.2 planner chain moved us 557,0 → 643,9 across five weeks. One tape moved us to **1.091,1**. §3.4's crop/animal-equilibrium finding predicted exactly this: **the configuration was the product, not the scheduler** | same |
| ⚠️ Caveat on the local number | The gate read median **$128k** unpinned, but that bench is soft — S2 recorded `meta_route` as an easy opponent (all 3 donors *better* there, +2,9% to +57,2%). The honest predictor was always S2's **hard**-opponent figure (7-37% degradation, $57,6-76k), and the ladder's 1.091,1 is the number that counts. Do not quote $128k as a ladder expectation | `baselines/2026-08-11/s2_failure_map.json` |
| 🟢 Our best public score | **1.915,8** — `55586926`, the **ReCurSiON majority-vote reconstruction**, read 2026-08-18 **09:19 UTC on 85 episodes**. **Rank 940 / 5.123** (from 1.263 / 4.947 on 08-17 — **+325 places**). Past the evicted Valmorlee tape's converged 1.599,1, our previous best 1.617,6, and ~2,9× every hand-built agent this repo produced (652,5, v1h) | `kaggle competitions submissions -v` · `leaderboard -d` |
| Our active submissions | **`55586926` ReCurSiON reconstruction — 1.915,8 on 85 episodes** · **`55575305` Ueddy T2 tape — 1.392,9 on 78 episodes** · `55548339` Valmorlee T1 tape — 1.599,1 on 111 episodes, **INACTIVE** (evicted by date per the user's decision — only the latest two count) | `kaggle competitions submissions` · `episodes <id> -v` |
| 📈 The convergence curve, in episodes not hours | **(7, 1.125,9) → (15, 1.736,0) → (16, 1.753,7) → (85, 1.915,8)**. The first 15 episodes bought +1.136 points at ~+76/ep; the next 70 bought **+180 at ~+2,6/ep**. So it is **plateauing near ~1,9-2,0k**, and the "~20 episodes/hour" extrapolation of 08-17 was wrong — the rate fell off with the placement burst. §3.4's episodes-not-hours rule, working as intended | same |
| ✅ **Kill (iii) — CLOSED, and it did not fire** | **The reconstruction method is confirmed on the ladder**, at comparable episode counts and in the same read: recon **1.915,8 on 85 episodes** vs the surviving Ueddy tape's **1.392,9 on 78** — **+523 with a similar amount of play behind each number**, which is exactly the comparison §3.4's episodes-not-hours rule demanded. The first local finding in this repo that the ladder has confirmed rather than reversed (§1's five-week puzzle) | `submissions -v` + `episodes -v`, 2026-08-18 09:19 UTC |
| 🔴 **But the transfer ratio is the new problem, and it points the opposite way to §4.5(b)** | **A majority-vote reconstruction transfers *worse* than a verbatim tape did.** Recon **1.915,8** against its donor ReCurSiON's same-day **2.985,6** = **64%**. The Valmorlee tape was **1.599,1** against its donor's 1.842,4 = **87%**. So the vote left **~1.070 rating points** of its #5 donor on the table — and the prime suspect is the thing the vote *erased*: the **127/719 (17,7%) state-dependent market steps**, i.e. the town-conditioning that made the donor #5. §4.5(b)'s "degrades gracefully" was measured as a local bank margin; on the ladder, a route that is averaged over 50 towns may be optimal in none. **Unproven — this is the next pass's whole question** (§4.3 step 2b Phase 0) | same |
| ⚠️ **Decay is real but an order of magnitude slower than first reported — measure it only on teams that did not resubmit** | 🔴 **Correction, 2026-08-18: Peter Parker's #29 / 2.844,2 → #383 / 2.364,7 was NOT decay — `LastSubmissionDate` moved to 08-18 07:03, i.e. a *new* submission converging from ~600.** Read properly, over the 16h between the two leaderboard pulls, on teams whose submission did **not** change: **boatlee −73,1** (frozen 08-15, ~−110/day) · **ReCurSiON −19,0** (frozen 08-14, ~−28/day) · **カワシギ −1,9** (frozen 08-17) · Ueddy **+16,5** (still converging, 20h old). So a frozen route at the 2,9-3,0k level bleeds roughly **−20 to −110 points/day**, not −500. §4.4#1 still binds on `55586926` — a frozen route with **~6 weeks to 2026-09-30** and a final BT run on post-deadline episodes — but it is a manageable clock, not a fire. **Standing rule: a leaderboard delta is only decay if `LastSubmissionDate` is unchanged** | `leaderboard -d`, 08-17 17:16 vs 08-18 09:22 |
| 🟢 The early signal, and it is steep | **+1.136 points in 15 episodes** (600,0 → 1.736,0), ~+76/episode and still rising. Rating moves only by *winning*, so a climb this steep against a rating-sorted pool is the strongest read this repo has produced — but 15 episodes is a **signal, not a convergence**: Ueddy needed **72** episodes to reach 1.375,9 and Valmorlee **111** to reach 1.599,1, so the honest comparison point is ~72 (kill (iii), §4.3). **It has already passed both tapes**, so kill (iii) is trending decisively against firing. Also already ~2,7× every hand-built agent this repo ever fielded (best 652,5, v1h) | same |
| ⚠️ v1o.2's verdict | +$5.069/ep of holdout production (crop tile-days 413→562) landed at **620,4** — **+20 over its own pairmate**, read the same day, and **−32 under frozen v1h**. The §3.2.1 "local→ladder transfers whole" finding does **not** generalise past v1h.2d | same |
| ⚠️ Rating decay, observed | `55414570` **632,2 → 618,4 → 600,2** over 08-10/08-11/08-15 with no code change — a frozen agent's score falls as the meta moves (§4.4#1), so a score is only comparable to others read the same day | same |
| Rank before the tape | 2736 / 4555 (2026-08-15; 2218 / 3811 on 08-11 — 518 places lost while changing nothing). Kept as the decay baseline | same |
| Ladder #1 | **3187,7** (THUNDER THUNDER) | leaderboard, 2026-08-11 |
| Engine | **`kaggle-environments==1.32.7`** installed, mirrored, and 🟢 **LIVE on the ladder as of 2026-08-16** — `analysis/v1t_engine_probe.py` reads **61/61** episodes of the `kaggriculture-episodes-2026-08-16` dataset as 1.32.7, against **28/28 = 1.32.6** on the 08-14 dataset. The rollout landed between 08-14 and 08-16 | [engine_deltas D28](docs/reference/engine_deltas.md) · `baselines/2026-08-17/v1v_shop_demand_report.md` §0 |
| ⚠️ What that costs us | **Every checkpoint and baseline below `checkpoints/v1u_base` was measured on 1.32.6**, and cross-engine comparison is the exact error §4.2's B1 correction records. The pre-1.32.7 STOPs in §3.3 still bind **on mechanism**; their **dollar** figures are engine-stale. `v1u_base` is the only correct comparison baseline from here | §7 |
| Starting rating of any new submission | 600,1 | `current_phase.md` §0 (retired) |
| Final submission deadline | **2026-09-30 23:59 UTC** — re-verified today | Kaggle API `deadline` field |
| Entry / team-merger deadline | 2026-09-23 | competition overview |
| Final ranking | ~2 more weeks of episodes after the deadline, then **one Bradley-Terry tournament** over that window | [docs/source/discussion.md](docs/source/discussion.md) head |
| Prizes | 10 **equal** prizes of $5.000 (places 1-10) | [docs/source/competition_info.md](docs/source/competition_info.md) |

**The gap is ~2.500 rating points, and the whole v1e→v1i chain has moved us under 100 of them**
(557,0 → 652,5 best, against a 600,1 starting rating for any new submission) — even though the
same chain is worth **+$25,3k/ep** (v1e→v1g) and **+$2,8k/ep** (v1g→v1h) on holdout, and v1h.2d's
local gain transferred to the ladder *whole* (§3.2.1). That combination — measured local wins that
convert into ~nothing on the ladder — is the single fact this document exists to answer. **It is
not a tuning problem.**

### Acceptance gates for this plan

| Gate | Meaning |
|---|---|
| **2800+** | Minimum bar. Below this we are *copying*: the job is to reproduce measured top-5 behaviour, not to invent. |
| **3000+** | "Top-5 tactics successfully replicated." Only above this does originating our own tactics become the highest-value work. |

Because prizes are ten **equal** $5.000 awards and the final ranking is a Bradley-Terry
tournament over post-deadline episodes, the target is **stable top-10**, not #1. A high-variance
agent that peaks at 3200 and swings is worth less than a steady 3050.

---

## 2. Method — standing, not a one-time note

*Adopted verbatim as the operating philosophy for this and all future work:*

- Never conclude a strategy is "optimal." The only defensible claims are: *this beat that
  specific challenger, under this test, against these opponents.*
- The loop is: real losses → identify one concrete failure mechanism → build a challenger that
  targets it → test across multiple opponent teams and **both seats** → reject most candidates →
  freeze the winner → re-validate on later/held-out episodes.
- Don't optimize only against the newest top-30 snapshot. Retain representative strategies from
  earlier meta generations (old notebooks, old checkpoints) as regression opponents — older metas
  are often still active on the ladder, and a change that only beats the latest snapshot can lose
  to them.
  🔴 **Given teeth 2026-08-17, because it had none.** Every gate in this repo to date has scored
  `v_n` against `v_{n-1}` plus `meta_route` — one generation deep, one opponent wide. From S6 the
  standing bench is: **tiers 0-5 of the reference ladder** (§4.5) · **our own frozen `v1h` / `v1i`
  / `v1o_2` / `v1u_base`** · `meta_route` · the two earlier-meta notebook references (Appendix A).
  An arm reports its record against **each**, not a pooled number.
- The submitted agent can be open-loop (a fixed policy). The *research process* that produced it
  must be closed-loop (falsifiable experiments, not narrative).
- 🔴 **The framing that generates the next pass (user, 2026-08-17).** The prompt is **not**
  *"build the optimal agent"* — it is ***"where does this agent lose, and what experiment could
  disprove the proposed improvement?"*** Every pass brief in this repo starts from a measured loss
  and carries a pre-registered way to be wrong. §2's first bullet is the same rule stated
  defensively; this states it offensively, and it is what §4.1b caught: a headline finding that
  was never given a control that could refute it.

### 2.1 What that means operationally (carried over from the retired plans, still binding)

These are not restated theory — each one was paid for with a measured failure.

1. **Both seats, always.** `_end_of_day` builds **one** per-day RNG, spends it on `_spawn_weeds`
   for player 0 then player 1, and *only then* draws the shop unlock. A one-tile difference on
   **either** farm re-rolls the whole remaining shop sequence. Seat 0 and seat 1 are not
   symmetric even on the same seed.
2. **Classify the knob before every A/B.** *Can this change alter how many tiles are occupied on
   any night?*
   - **No** (order/rate/threshold of market orders only) → **market-only**; a fixed seed is a
     genuine controlled experiment (verified: same town in 16/16 seeds).
   - **Yes** (labour/crew, planting, harvest, DIG, BUY_LAND, animal/structure placement, routing)
     → **occupancy**; requires `--town-pin basket` on *both* arms or an explicitly justified
     larger seed budget (0/16 same town without it; paired noise goes from a few coins to >$1.000).
   - **Don't know** → treat as occupancy.
   - Pinning **reduces, does not eliminate** (~19% of noise sd). The final holdout-confirm always
     runs **unpinned**.
   - Only `--town-pin basket` is valid under 1.32.6. `schedule` reproduces a distribution that now
     occurs in 0,24% of episodes — actively misleading, kept only to replay old runs.
3. **Screen → confirm, never "keep the max."** Dev seeds 0-47 for screening, holdout 100-147 for
   confirmation only (no tuning decision ever touches them), smoke 0-11 for controls (never GO),
   `CONFIRM2_SEEDS` 200-247 **burned**. Real game-to-game spread is ~19% of a submission's median
   bank (extremes to 950%), so 24-48 seeds is the floor, not a luxury.
4. **Acceptance is three numbers, in this order:** absolute `median_bank` → W/L against a
   **non-mirror** bench → `mean_diff` in mirror (demoted to tie-breaker and regression detector).
   A positive `mean_diff` with a flat `median_bank` is not progress toward the ladder.
5. **Priced loss, judged on the difference.** Structural counters stay hard-zero
   (`clipped_production_ticks`, `plant_decay_units_lost`, unexplained no-ops, market-sim aborts,
   ≤2% low-price sales). Loss counters are priced (`animals_escaped` $1.000, `shed_overflow_burnt`
   $150/unit, weed-lost tile $300) and judged as
   `priced_loss_delta = max(0, priced_loss_a − priced_loss_b)` ≤ 10% of `mean_diff` **and** ≤$500/ep,
   **only on the acceptance arm** (`--arm-role acceptance`). Mirror runs `--arm-role regression`:
   $-verdict + structural only, never a priced budget. Every non-zero candidate counter still needs
   a written mechanism — "don't know why" is a bug, and a STOP.
6. **Never bump the engine or edit `agent/` while a gate is running.** The agent is imported per
   worker process; editing mid-run mixes versions across seeds. Writing `.md` is always allowed.
7. **Engine-bump detector runs regularly and without installing:** `pip index versions` →
   `pip download --no-deps --no-binary :all:` → `diff` the `.py` **and the `.json`**. A balance
   change can be json-only (`townCenterSellInterval`, `turnsPerDay`, `maxMarketOrdersPerTurn`,
   `shedCapacity` all live there). 1.32.6 caught us out once.
8. **Competitor material — the line, as of 2026-08-11.** **Public episode replays are game data
   and may be used, including as a route source** (§4.2, user decision; the old blanket ban on
   replay-derived priors is withdrawn). Provenance is recorded whenever one is used. Competitor
   **notebook source** — the `main.py` / `submission.tar.gz` those kernels publish — is still **not
   opened, extracted or executed**; that is their code, not game data, and no part of the plan needs
   it. Notebook markdown, tables and printed statistics are read freely as evidence.
9. **A confirmed mechanism and a viable increment are different claims.** Every report states
   both, in that order: *(a)* what the arm proved about how the game works, *(b)* whether the arm
   is takeable in dollars. Never let (a) stand in for (b) — v1o.3's variant E confirmed the
   animal-upkeep mechanism perfectly (escapes 13 → 0) while its dollars stayed REGRESSED against
   production forgone; v1p.2b confirmed the `committed`-in-zoning mechanism the same way. Both
   were reported once, correctly, and re-read wrong the second time by someone skimming only the
   mechanism half.

---

## 3. Carried-forward findings

Everything below was measured, survives the reset, and is not derivable from the code. Where a
number lives in a curated file, this is a pointer, not a copy.

### 3.1 Engine (2026-08-11 re-verification)

> 🔴 **Superseded on the version question, 2026-08-17: installed *and live* are now 1.32.7** (§1,
> §7). The rest of this block — the balance-change consequences, the documentation gap, the
> discussion-tripwire limitation — still stands as written.

- **Installed `kaggle-environments` is 1.32.6; PyPI latest is 1.32.6.** No upgrade available, no
  action taken. `engine_reference/` is **byte-identical** to the installed package for all four
  files (`kaggriculture.py`, `.json`, `README.md`, `AGENTS.md`), and `pytest tests/` is
  **226 passed**.
- **The announced balance change is live and fully landed.** Verified directly in the installed
  1.32.6 source today: `TOWN_CENTER_DEMAND_SCHEDULE` is **gone** (flat `-= 1`),
  `townCenterSellInterval` default is **24** (1 tick/day), the `not in unlocked` shop filter is
  **gone** (shops drawn with replacement), and `MAX_SHOP_INSTANCES = 8` exists. Consequences —
  town centre absorbs **30 units/product/season instead of 140 (−79%)**, `E[distinct shop types]
  = 5,25`, `P(a given type absent) = 34,4%`, `P(all 8 present) = 0,24%` — are current state, not
  forecast.
- ⚠️ **Documentation gap found and to be closed:** `docs/reference/engine_deltas.md` still says it
  is pinned to 1.32.5 and contains no 1.32.6 entry, even though `requirements-dev.txt`, the venv,
  and the whole v1h.1+ line ran on 1.32.6. The 1.32.6 facts existed only in `MASTERPLAN.md` — i.e.
  in a file this reset deletes. **Action item R1 (§6).**
- ⚠️ **The live discussion could not be checked programmatically.** `kaggle.com/competitions/
  kaggriculture/discussion` is a client-rendered SPA (WebFetch returns a 5,6 KB shell); the
  internal `api/i/...` forum endpoints 400/404 without a browser XSRF token, and the public Kaggle
  API exposes no discussion resource. **The pip-version + byte-diff check is our only automatable
  engine tripwire; reading the discussion stays a manual step.** Everything the last-known
  announcement described is already shipped, so there is no known pending change — but "no known"
  here means "not contradicted by the engine," not "confirmed by the forum."
- Full deviation catalogue (D1-D26) stays in
  [docs/reference/engine_deltas.md](docs/reference/engine_deltas.md). Non-obvious ones that keep
  costing people games: planting day counts as the first unwatered day (D4); melon caps at age
  **10**, not 12 (D5); strawberry yields **exactly 4 times** then decays to weed (D6); the shed is
  **not a tile** (D11); `PLANT` is atomic — two units competing for one seed means **neither**
  plants (D21); floor sales add no inventory (D18); invalid actions are silent no-ops (D15).
- **Step 718 is the last executable turn.** `interpreter` sets `DONE` at `step >= episodeSteps-2`.
  A `SELL` *at* 718 does execute. Every endgame plan targets 718, not 719.

### 3.2 Our own agent, measured live (L1/L2 diagnostics, 2026-08-10)

Full tables: [docs/meta/ladder_snapshots.md#l2-v1h2d](docs/meta/ladder_snapshots.md#l2-v1h2d)
and [#l1-v1h](docs/meta/ladder_snapshots.md#l1-v1h).

1. **The local→ladder pipeline works.** v1h.2d transferred *whole*: median live bank
   **$47.091 → $57.360 (+22%)**, `priced_loss` **$4.943 → $154/ep**, overflow −99,6%, ≤$5 sales
   −98,6%, escapes −94%. The methodology is not the problem.
2. **The loss window is d20→d29 and nothing else.** We are **+$12.732 ahead** of the median
   opponent on day 20 and finish **+$1.753**. Window ratios: d15→d20 **1,90×**, d20→d25 **0,78×**,
   d25→d29 **0,58×**. Against the eleven opponents above $70k we were **0-11**, crossing over on
   **day 22**. We do not collapse — **we stop**.
3. **The mechanism: our farm shuts down on day 17.** Planted tiles 26 (d16) → 19 (d18) → **6
   (d24)** → **0 (d28)**. Our STRAWBERRY — our best crop — goes to zero on **day 19** and is never
   replanted. The opponent holds 24 planted tiles at d24.
4. **Crew is not the constraint; it is idle.** We spend **23,0% working / 27,8% idle** unit-turns
   against the opponent's 32,2% / 12,1%, with **more** total unit-turns (6.133 vs 5.895). This is
   why v1j measured `{12 hands, 24 tiles} ≡ {10 hands, 24 tiles}` **exactly** — the extra hands are
   never hired. *Correction carried forward:* the old "they don't fit in the morning bank"
   explanation is **wrong** — hands are a nightly-reset daily rent
   ([kaggriculture.py:867-868](engine_reference/kaggriculture.py#L867-L868)), $233/day against an
   $11k day-15 bank. The cause is our own hire gate. Do not reuse the cash argument as evidence.
5. **The whole gap is in plants.** Crop revenue **$14.042 vs $42.223** (3,0× behind); animals +
   fertilizer **$57.830 vs $45.050** (1,28× **ahead**) with the *same* animal count. Crop
   tile-days **415 vs 688**.
6. **$/tile-day, not cliff depth, is the crop ranking metric** — and the old cliff-depth ranking
   sent 35% of our tile-days to the worst crop in the game:

   | Crop | our tile-days | our $/tile-day | opponent $/tile-day |
   |---|---:|---:|---:|
   | MELON | 0 | — | **$119,6** |
   | STRAWBERRY | 136 | $51,2 | $63,8 |
   | CARROT | 135 | $34,9 | — |
   | **WHEAT** | **144** | **$15,5** ⚠️ | $35,6 |

7. **Revenue by product, us vs the ladder opponent** (median/ep over the same 34 replays,
   `baselines/2026-08-10/l2c_tile_economics.json`) — the single clearest statement of where the
   money is and is not:

   | Product | Us | Opponent | Δ |
   |---|---:|---:|---:|
   | MILK | $26.648 | $29.088 | −$2.440 |
   | **FERTILIZER** | **$13.685** | $10.530 | **+$3.155** |
   | WOOL | $12.795 | $4.249 | **+$8.546** |
   | STRAWBERRY | $6.962 | $7.626 | −$664 |
   | CARROT | $4.709 | $0 | +$4.709 |
   | WHEAT | $2.236 | $4.036 | −$1.800 |
   | **MELON** | **$0** | **$27.263** | **−$27.263** |

   **FERTILIZER is our second-largest revenue line** — ahead of WOOL and ~3× our best crop — and it
   has never been the subject of an increment. Its mechanics are worth knowing:
   [kaggriculture.py:818](engine_reference/kaggriculture.py#L818) sets `fertilizer_available = True`
   **unconditionally** after the escape `continue`, so every non-escaped animal produces 1/day
   regardless of FEED/CARE; it is a **boolean, not a counter**, so anything uncollected is **lost**.
   Its price curve is the gentlest in the game (`price(Δ) = 100 − 0,2Δ`, cliff at **500**) and it has
   **zero NPC demand**, so inventory only rises and both players share one curve ⇒ *sell early,
   always*. v1n then measured that the remaining gap is **62,7% structural** (the herd is only
   complete on day 10) with a fixable residue of 28 units ≈ **+$720/ep upper bound**, concentrated
   on the four busiest days — i.e. exactly where taking the action would displace FEED.

8. **Against the opponents who beat us, the deficit is 95,7% volume and 4,3% price.** Decomposed
   over the same 34 replays (`analysis/v1i_theta1_exposure.py`), splitting
   `price_gap = our_units × (their $/u − our $/u)` from
   `volume_gap = (their_units − our_units) × their $/u`:

   | Opponent bucket | Episodes | Record | crop tile-days ours/theirs | price gap | volume gap |
   |---|---:|---|---:|---:|---:|
   | <$40k | 8 | 7-1 | 415 / 793 | $878 | $22.728 |
   | $40-70k | 15 | 9-6 | 415 / 409 | $1.488 | $22.956 |
   | **>$70k** | **11** | **0-11** | **415 / 968** | **$2.661 — 4,3%** | **$59.370 — 95,7%** |

   Our realised prices already **match** theirs (CARROT $39,06 vs $39,00 · WHEAT $44,72 vs $44,20 ·
   FERTILIZER $63,31 vs $59,49 **ahead** · MILK $210,62 vs $214,71 · WOOL $196,81 vs $205,90 at
   **1,7×** their volume). The whole deficit is **MELON 0 vs 132 units** and **STRAWBERRY 32 vs
   118**. Two consequences that bind: the sell-side layer built in v1h.2d/v1m_d2/v1i **works** —
   415 tile-days produce the same $/unit as opponents with 968 — and **no further sell-side change
   can differentiate the active pair**, because there is no price gap left to close. This is why
   `checkpoints/v1i` passed its gate and was not submitted, and it is the main tension inside
   §4.1: measured across the current top-30, our realised prices (MILK $210,62, WOOL $196,81) are
   at or above theirs, and **all** of their remaining spread is realised price on three products.
   Both readings hold, and together they say the same thing — **our sell side is already strong and
   our production is 3× short**, which is why §4.3 copies production first and returns to sell-side
   timing in S5.

   ⚠️ **The WHEAT figure is sales-only and measurably misleading.** Those 12 SW tiles feed **212
   FEED actions/ep**; at ~190 units of home production the agent is already a **net buyer** (117
   bought / 95 sold). Converting 8 of them to CARROT cost **−$7.161/ep, 0/12 seeds**, with crop
   revenue flat and `animals_underfed_days` 40,8 → 50,9. The correct valuation is *sales + avoided
   feed purchase*, and nobody has measured it. **No further wheat-tile reduction without a
   separate, gated feed-purchase plan.**

### 3.3 Measured STOPs — do not re-run these without new data

| Increment | Result | Why it still binds |
|---|---|---|
| **v1c** land expansion, ×3 variants | STOP | Capacity/routing, not land, was the blocker |
| **v1j** wheat 12→24 tiles + crew 10→12 | STOP, −$759 | +2 hands never hired; land-only ⇒ escapes 0→8. 🔴 **Cause corrected 2026-08-11 (v1o.2):** the hands were not unaffordable — **one HIRE is one market order, `maxMarketOrdersPerTurn` is 10, and the engine silently drops the rest** ([kaggriculture.py:538](engine_reference/kaggriculture.py#L538)); hands are wiped nightly, so a crew rebuilt entirely in hour 0 cannot exceed 10 whatever `hands_target` says. Screening 10→12→14 measured **byte-identical** results (`mean_diff` exactly $0,00, CI [0,0]). Do not cite cost as the reason again |
| **v1o.2 `sw_hands_target` 12** (after the order cap was lifted) | STOP on the **acceptance priced gate** | Best dollars of the session — `mean_diff` **+$4.144,7**, IMPROVED, episodes 82-14, `median_bank` **$59.409** — and `priced_loss_delta` **$477,6/ep against a $414,5 budget** (clears the $500 leg, fails the 10%-of-mean_diff leg; the rule is AND), driven by `animals_escaped` **87 vs 32**. 12 hands on ~594 crop tile-days emit more priority-0 `WATER` than the same tier's `FEED` survives. **The crew cannot be raised past this until feed priority is protected** |
| **v1o.3 animal-upkeep protection** (S3 step 1b — bundling, feed-round re-tiering, and both together), 7 screened variants | ⛔ **STOP on the acceptance arm, twice** | The best SMOKE variant (**E**: visit bundling + FEED/PICKUP at −1/−2 + a decay guard on crop HARVEST) went to DEV against the non-mirror bench and returned `median_bank` **$59.469,5 vs the baseline's $59.875,5**, `mean_diff` **+$61,6 vs +$4.839,9**, episodes **50-46 vs 84-12** — all three §2.1.4 numbers the wrong way — plus `plant_decay_units_lost` **14** (structural). Bundling alone (**A3**) was **−$3.793,4 REGRESSED**, escapes **77 vs 5**. **E worked exactly as designed and that is the point:** `animals_escaped` **13 → 0**, the pipeline fully protected, paid for out of `crop_tile_days` 612 → 574. 13 escapes ≈ $135/ep; the production ≈ $1.180/ep. **Any reallocation toward animals loses at our production level** (574 tile-days against 1.316) however cleanly it is implemented. ⚠️ The **mirror** arm said **+$4.877,5 IMPROVED, 40-8, p=3,3e-6** — the sharpest §3.4 demonstration in the repo |
| **The feed round never closes** (measured, not an increment) | Standing fact | Per-hour count of animals with `fed_today=False`, 8 runs vs `meta_route`: **≥1 animal is unfed for 100% of the hours of a median day from d9 onward** (≥70% every day from d7). There is no moment in the season when the crew is free of tier-0 work ⇒ "wait for a quiet moment" is not an available strategy, and **any reordering inside tier 0 is strictly zero-sum** |
| **v1o.1 `strawberry_last_plant_day` 16 and 20** | STOP, structural | Both break `clipped_production_ticks` (1) — an animal's yield left uncollected past its cap — and lose $4,1k/$7,9k per episode **while producing more** tile-days. Same mechanism as the row above |
| **v1k** late-season replant window | STOP, −$166,9 (CI spans 0) | Mechanism **worked** (413→539 tile-days, idle 28,2%→23,8%) and paid **nothing** — we filled tiles with a cheap crop. **On the shelf, not disproved:** mandatory re-test with the first increment that introduces a crop >$50/tile-day. |
| **v1l** wheat→carrot by $/tile-day | STOP, −$7.161/ep | See the WHEAT caveat in §3.2(6) |
| **v1m / v1m.2** melon race | STOP at smoke (28 unexplained escapes), then STOP at Ε1 | Ε1 was later re-scored under the delta rule and **passed** → `checkpoints/v1m_d2`, submitted |
| **v1n** fertilizer capture | Closed as measured | 62,7% of the loss is structural; the fixable 28 units are ≈**+$720/ep upper bound** |
| **12-14 animals** | Hard-gate failure, 660-885 escapes | Feed logistics, **not** market saturation, is the ceiling. ⚠️ But the top-30 run **13 (9C+4S)** and build them as a **ramp** (6 by d5 → 12 by d10 → 13), not in one purchase — §4.0. Our screen bought them in one step |
| **herd 13 (9C+4S) on the C2 reserve** (S3 step 2, 2026-08-15) | ⛔ STOP at SMOKE — all three herd-13 arms REGRESSED, **−$15-21k/ep, 0-12 seeds** | **The ramp was tested and is not the lever.** Three arms decomposed the change: **H1** (4C+9S, +3 animals at the unclaimed distances 7,7,8, **zero** reassignment/recomposition) escaped **122**/24-ep and collapsed `crop_tile_days` **−35,8%** (574→368/ep); **H2** (9C+4S step) −$20,9k, MILK realised price 151→**139** (§3.3 saturation, now confirmed non-mirror); **H2R** (9C+4S on the 6/12/13 ramp) lowered escapes 88→**66** but recovered **neither** the crop collapse (still −35,8%) **nor** the dollars (−$19k, lowest median bank $31,8k). The 3 far animals raise herd Σdistance **37→59 (+59%)** on a feed round open 100% of the day from d9. C2 pays the **cash** half in full (Phase 0: herd *owns* 13 by d9-11, money never $0); **nothing pays the logistics half**. Herd 13 is blocked on **feed logistics, not cash** — deferred item ③ (travel-ratio) is next, **not** a herd retry. Does **not** refute the §4.0 profile, only reaching it with the current `assign()` routing + PASTURE pool. Report: `baselines/2026-08-15/s3_step2_report.md` |
| **shop-adaptive sell floor** | −$1.103 to −$24.762/ep, 0/8 wins | The agent is production-constrained, never glut-constrained; a demand-sized floor has no price to win, only volume to lose |
| **herd re-composition toward cow** | `{8C,2S}` −$5.093, `{10C,0S}` −$6.845 + hard-gate fail | And the damage was **larger** in towns *with* a YARN_STORE ⇒ the constraint is **MILK saturation in mirror**, not the rare buyer |
| **shed-access routing fix** (1.32.5 D26) | Net-negative, reverted | The old `(4,4)` distance over-estimate was accidentally inflating WHEAT PICKUP urgency. Needs routing-distance decoupled from urgency-distance in `assign()` first |
| **v1p.1 herd compaction** (config-only PASTURE reorder, S3 step 1c) | ⛔ STOP at SMOKE, −$875,4 INCONCLUSIVE | `worker_turns_moving` fell as designed (61,7%→53,6%) but `animals_escaped` went 2→48 — **exactly 2 every single one of 24 orientations**, always the same two COW at (3,2)/(3,3) (untouched by the change), always day 2. Root cause: reassigning two SHEEP PASTURE slots to distance-1 tiles (closer than *any* COW slot) lets SHEEP win the whole initial multi-day PLACE race in `assign()`'s type-blind greedy loop, delaying COW's first feed past `consecutive_unfed >= 2`. Intrinsic to the tile choice (any arm using those two tiles for SHEEP hits it), not screened further. Config reverted, mechanism documented in place |
| **v1p.2 zone assignment** (`assign()` eligible-units filter by quadrant, S3 step 1c) | ⛔ STOP at SMOKE, −$6.966,0 REGRESSED (p=4,9e-4) | The increment's own kill criterion fired at the first screen: `worker_turns_moving` barely moved (60,0%→58,7%, nowhere near the ~55% target). Also broke a structural hard-zero counter, `plant_decay_units_lost` 0→17. Likely mechanism: the zone partition has no memory across turns, so a unit already `committed` (C1 stickiness) to a task can be re-zoned *out* of eligibility for it the next turn as the task-count mix shifts — reproducing the exact commitment-thrash class of bug `committed` was built to prevent, from outside the mechanism that protects against it. Code kept inert at `zone_assignment_enabled: False`; hands off to deferred item ④ (min-cost matching), gated on deferred item ③ (travel-ratio diagnostic) per its own control's result below |
| **v1p.1b herd compaction, both untested controls** (arm A1: COW instead of SHEEP on the same two tiles; arm B: `carrot_tiles` 3→1 alone, PASTURE untouched — S3 step 1c) | ⛔ STOP at SMOKE, both arms | **Closes the "convert a CARROT tile to compact the herd" family for good.** Arm A1: `animals_escaped_a` **48** (vs its own paired baseline 0) — 🔴 **corrected 2026-08-14 (S3 step 1d race):** `mean_diff` **−$7.711,5 REGRESSED**, episodes 0-12 (0-24 orientations), not merely "the same magnitude as arm A" (arm A's own original screen was **−$875,4 INCONCLUSIVE** — the escape count matches, the dollars do not; COW-first reordering made everything substantially worse) — now a *mixed* COW/SHEEP pair — **refutes v1p.1's own type-blind-race root cause**, since giving COW the close tiles instead of SHEEP does not fix it. Arm B: `animals_escaped_a` **12** (vs its own paired baseline 2), seed-dependent, with **zero PASTURE change** — dropping `carrot_tiles` below 3 is itself destabilizing, independent of what the freed land becomes. Analytically confirmed separately: the ten currently-claimed PASTURE slots are already the ten nearest of the 13 available (distances 2,2,2,3,3,4,4,5,6,6,7,7,8) — there is no free reorder inside the existing pool; proximity can only be bought by converting a crop tile, and across both tested splits that purchase does not pay for itself |
| **v1p.2b sticky zone assignment** (`committed` threaded into `_zone_partition`, pin-first — S3 step 1c) | ⛔ STOP at SMOKE, −$2.688,6 REGRESSED (p=6,3e-3) | The untested control v1p.2's own root cause implied. Fixed exactly what it targeted: `plant_decay_units_lost` **0** (was 17, structural), `animals_escaped` back to parity (5 vs 5, was 20 vs 6). But `worker_turns_moving` **58,9%→60,3%**, essentially the same ~1,4pp non-movement as v1p.2's own original screen — the kill criterion's own restated third exit fires: **the constraint genuinely is not which tasks a unit is offered.** Code kept, inert at `zone_assignment_enabled: False`; hands off to deferred item ③ (travel-ratio diagnostic), not directly to ④ (min-cost matching) |
| **deferred item ④ — min-cost matching, offline oracle** (item ④ step 2, 3 arms A/B/C, 2026-08-16) | ⛔ STOP — **both pre-registered legs miss on all arms; ④ refuted** as a route to the §4.0 profile with this planner | The optimal per-turn matcher, substituted into the live agent and played out (SMOKE 0-11, both seats, basket, vs `checkpoints/v1u_base` built on 1.32.7, 24 eps/arm). **The routing prize is real** — arm A (whole-pool optimal) banks **+$4.709/ep winning 23/24**, `worker_turns_working` +5,6%, `crop_tile_days` +8,4% (step 1's 4,30% regret, now in dollars). 🔴 **Leg 1's escape clause was mis-specified, and the correction matters — see the block below this table.** A's `animals_escaped` **3→11** is a real *mechanism* (the v1o.3/G-8 crop-vs-animal exchange in reverse) but **not** an acceptance failure: priced at the repo's own gate it is `priced_loss_delta` **$333,3/ep against a $470,9 budget — a PASS at 1,4×**. The ±5 figure is §3.3's *detectability* floor, not an acceptance threshold. The buildable arm **B** (greedy + 2-opt) earns only **+$812/ep**, under the +$2.000 bar (`B/A` = **0,17**); **C** (feed-only re-match) is **−$441**. **Leg 2 misses and moves the WRONG way**: feed-round saturation stays **100%** from d9 on all three arms and `animals_underfed_days` **rises** (A +23,8%, B +7,2%), because a per-turn distance optimum aims freed turns at *near* crops and defers the *far* feeds — the 96,3% forced-walk floor (step 1) is largely the commute to distant animals. **④ is not the herd-13 unblock; measured, it is the opposite.** The §4.0 profile is **not** refuted (top-30 run 13 profitably) — only reaching it with this `assign()` planner + PASTURE geometry is, the same wall S3 step 2 hit from the herd side. Promotes the tape (§4.2) to the production route; closes ④, steps 3-8 not started. No `agent/` change, no submission. Report: `baselines/2026-08-15/item4_step2_report.md` |
| **T2 market overlay on the shipped tape** (S3 step 3, strawberry-only, replace + augment, 2026-08-16) | ⛔ **STOP at SMOKE — the tape's realised STRAWBERRY price is pinned by shed capacity, not a re-timeable calendar** | Overlay our own sell logic (`_sell_batch_size` + v1i `OpponentSupplyTracker`, reused verbatim) on the Valmorlee (91456307) tape's `market` channel; keep `farmer`/`hands` + all BUY/HIRE verbatim. **Phase 0 (cash coupling, `t2_phase0_report.md`) → GO:** cash floor ≈$6 and 5 turns (48/72/120/168/252) fund buys from same-turn sells, but **STRAWBERRY is never a cash-funding dependency**, so a strawberry-only overlay is unconditionally cash-safe (production stayed byte-identical, `crop_tile_days` equal in every run). **But S3 step 3 STOPS on the shed:** the tape holds **zero** strawberry (shed=0 mid-day; it harvests the whole batch at hour 0 and sells it that same turn) because the shed already runs at **98/100** (WHEAT-feed 13 + FERT 31 + WOOL 16 + MILK 12 + STRAWBERRY 26). **replace** mode (metering strawberry to raise its price) makes it linger → `shed_overflow_burnt` **0→31-89**, WOOL revenue **−$1,3k→−$2,5k**, and a full shed **rejects `BUY_PRODUCT WHEAT`** (feed) → `animals_escaped` **0→11** → **bank −$3-4k/ep** on all 3 opponents (raw tape / Kaito / meta_route), even though it **wins the kill sub-metric** (strawberry $/u $90→$103 vs Kaito). **augment** mode (pull-forward-only, Phase 0's prescribed design) is a **literal no-op** — nothing held to pull forward. ROADMAP §2 item 9: a confirmed mechanism (metering raises $/u) that is not a viable increment (costs more shed than it earns). §3.4 wall in the sell dimension. `agent/tape_overlay.py` kept inert (never imported by `main.py`); no submission. Report: `baselines/2026-08-16/t2_report.md`. 🔴 **Reason widened 2026-08-17 (§4.1b), verdict unchanged:** the −61% realised STRAWBERRY this pass was built to close was measured against *other episodes' towns*, and 99-100% of that quantity's variance is the town's shop draw — so most of the "loss" was never contestable. Consistent with this pass's own data: **replace** mode *won* the strawberry $/u sub-metric while losing bank, i.e. it moved along the 1%-of-variance axis and paid for it in shed capacity. And **augment**'s no-op is donor-specific, not a property of the lever — the same design earns **+$1.911,9/ep, 60-0-0** for an agent that owns its route (§4.5b). The shed wall is real; "the price lever does not exist" is **not** what this row establishes |

| **S6 step 2a own-farm repair (the "route is blind to its farm" lever)** — 2026-08-18 | ⛔ **STOPPED at Phase 0, kill (i)** | The lever the brief called larger than the overlay, refuted by decomposition. The `plant_decay` 15/ep + `unexpected_weeds` 5/ep are **100% WHEAT and the same 5 tiles** (non-ongoing crop stamped with a `max_lifespan_step`, harvest missed late-season in a foreign town), *not* strawberry — honest recoverable ceiling **$599/ep** (14,94 units × $40/u, itself high vs the saturated marginal wheat price), *not* ~$2.800–3.100. **FREE half $0/ep on-tile** (no idle unit is ever on a loss tile — §3.3's own wall, now confirmed on an open-loop tape) **to $241/ep reachable** (needs a closed-loop redirect that desyncs the tape); both **< the $500 gate**. Second kill: full recovery = **+2,4 rating pts / 0,09% of the gap** (§3.4). On the shelf, never worth a pass on a tape. → step 2b (premium-lead overlay) leads. Report: `baselines/2026-08-18/s6_step2a_phase0_report.md` |
| **C-A, in-place SELL reordering ("the Cleo rule")** — S6 step 0, 2026-08-17 | ⛔ **REFUTED before being built, analytically and empirically** | The one mechanism S6 step 0 pre-registered, killed by its own bounding pass. **Leg 1 (same-town self-pair):** a tape against an *identical* route in the same town realises **ratio 1,000** on all three premium products (96 episodes, both seats) — the frozen queue ordering costs exactly nothing, where the mechanism predicted "below 1,0×". **Leg 2 (surface area, priced on the engine's own market path):** despite 29-39 nominally reorderable turns per tape, the best legal permutation against the emitted one is worth **$0/ep (Valmorlee), $3-18/ep (Ueddy/Kaito)** — **0-0,6%** of the $2.826 median gap. **Engine-level reason, verified at [kaggriculture.py:544-597](engine_reference/kaggriculture.py#L544-L597):** market orders run in **per-slot lockstep across both players**, and a SELL depletes **only its own product's pool**, so permuting a fixed multiset of your own sells inside one turn cannot move your realised revenue. The residual $3-18 is entirely the opponent-slot-alignment channel, which we do not control. The 10-order cap never binds on these routes. ⇒ **the 1,04-1,06× winner's edge is not a queue-ordering effect.** Report: `baselines/2026-08-17/s6_step0_report.md` |

🔴 **Correction to item ④ step 2's leg 1, made 2026-08-16 by the author of the criterion.** The
brief's leg 1 required `animals_escaped` "inside the ±5 noise floor". **That was a category error on
my part.** §3.3's ±5 is a *detectability* floor — it says when a change in the counter is signal
rather than seed noise — and it was used as an *acceptance* threshold, which it is not. This repo's
acceptance rule for a priced counter is [harness/compare.py:127](harness/compare.py#L127):
`priced_loss_delta ≤ min($500, 10% × mean_diff)`, at $1.000/escape. Scored properly, **arm A passes:
$333,3/ep against a $470,9 budget (1,4×)**, and arm B passes too ($41,7 vs $81,2).

The code comment directly above that gate records the exact lesson I re-broke: *"The old
all-hard-zero gate rejected +$3,019,3/ep for 84 burnt units and 34 lost tiles… a $237/ep objection
to a $3.019/ep gain, and three sessions were spent on it while the ladder rating stood still."*
**Any future pass writing a counter threshold into a brief must price it, not floor it.**

**This does not reverse the STOP** — it replaces a wrong reason with the two right ones: **leg 2
missed decisively and in the wrong direction** (feed saturation 100% on every arm,
`animals_underfed_days` *up*), which refutes ④'s entire strategic rationale; and the **rating
arithmetic** (below) says even a perfectly shipped arm A is worth ~20 rating points against a
~2.550-point gap. What must *not* be carried forward is "routing improvements break the feed round
beyond acceptability" — measured, they do not; they simply fail to *help* it, which is the different
and fatal finding.

⚠️ **The `animals_escaped` noise floor, recorded 2026-08-14 (S3 step 1d race).** The baseline's own
`animals_escaped_b` read **0, 2, 4 and 5** across the four comparisons above (v1p.1, v1p.2,
v1p.1b, v1p.2b) — same agent, same seeds, same pin. That is §2.1.1 occupancy coupling changing
the *opponent's* farm via the shared per-day weed-spawn RNG, not noise in the mechanism under
test. Pairing within a single comparison stays valid, but on 24 SMOKE episodes this counter has a
noise floor of roughly **±5**. Read against it: v1p.1/v1p.1b arm A1's escape counts (48, both
times, deterministic in 24/24 orientations) are signal, far outside the floor. v1p.1b arm B's 12
vs. its own paired baseline of 2 is a **hypothesis**, not a result — inside the floor, seed/
orientation-dependent (6 of 24), and should not be carried forward as "a second independent,
established mechanism" without a wider seed budget.

✅ **The onboarding-escape defect is LOCATED and a fix is found (2026-08-14, S3 step 1e).** Five
passes misattributed it (hiring cost/v1j, distance/v1h′, feed-priority/v1o.2-3, animal-type
race/v1p.1, "cash-flow exhaustion"/step 1d); it is the v1g feed-cash reserve in
`agent/executor.py` undercounting the in-flight herd. The fix is specifically **arm C2**
(`feed_reserve_horizon="target"` — reserve for the *full intended* herd, not just the in-flight
count): on the deterministic 48-escape reproducer it removes **all** escapes (48→0, +$5.907
IMPROVED) with the herd still reaching its full target on baseline's day; the minimal count-in-flight
fix (C1) and the raise-the-days control (X) both leave 48. See §4.3 S3 step 1e. C2 promotes bundled
with the herd-13 increment (its shipped-config value at herd 10 is ~$0/NON_INFERIOR — the defect
is latent until the herd is large enough to strain day-0 cash).

🔴 **Updated 2026-08-15 (S3 step 2): the herd-13 bundle STOPPED — C2 stays latent, not promoted.** C2
does exactly what step 1e said (Phase 0: at target 13 the herd *owns* 13 by day 9-11, money never $0 —
the day-0 cash half is fully paid), and B0 (C2 at herd 10) re-measured NON_INFERIOR at **−$256,8**, step
1e's number. But **herd 13 itself regressed −$15-21k/ep at the current PASTURE geometry** (STOP row above):
the value C2 was meant to unlock does not exist, because the blocker was never cash — it is feed logistics.
C2 therefore **ships inert** in the 10-herd config and is **not promoted alone** (step 1e's standing rule);
its checkpoint is `checkpoints/v1s_B0`, re-tested only when ③/④ make herd 13 viable.

### 3.4 Standing methodological lessons

- **"Elite modal farm" compositions are end-state measurements, and the engine makes them lie.**
  One-shot crops empty their tile at HARVEST (`:411-412`); STRAWBERRY becomes a **WEED** shortly
  after its age-16 max yield (`:742-744`). Reported crop counts are a **lower bound**, never a mix.
  Land, crew and animals *do* survive to day 30 and can be read directly.
- **Any single-player market model of this dataset yields hypotheses to measure, never rankings
  to adopt.** The 70,2%-cow-herd result inverted the moment an opponent was put in the same market.
- Three separate times a replay aggregate measured something *slightly different* from what it
  appeared to ("winner buys land day 0" — n=1; "carrot 0% win rate" — n=5; "elite plants 6
  strawberry" — end-state). Before building on a meta number, the question is not *what does it
  say* but **at what moment and on what entity was it measured**.
- **The mirror loop optimises inside a ceiling it cannot see.** Every gate being `v_n` vs
  `v_{n-1}` scores a +$3k margin on $44k as a big win while the ladder opponent plays at another
  level entirely. This is why `harness/bench_agents/meta_route*.py` exists and why the acceptance
  arm must be non-mirror.
- 🔴 **The crop/animal equilibrium this planner cannot leave — four independent mechanisms, same
  wall (established 2026-08-16, closing the ③/④ line).** Read together, these are one finding:

  | Pass | Mechanism tried | Dollars | What actually happened |
  |---|---|---:|---|
  | v1o.2 `sw_hands_target` 12 | **more crew** | +$4.144,7 | escapes 87 vs 32 ⇒ failed the priced gate |
  | v1o.3, 7 variants | **protect the feed round** | +$61,6 acceptance | protecting animals cost `crop_tile_days` at ~10:1 |
  | S3 step 2, 3 arms | **more animals** (herd 13) | −$15-21k | feed logistics; `crop_tile_days` −36% |
  | item ④ step 2, arm A | **better matching** | +$4.709 | freed turns went to near crops; `animals_underfed_days` **+23,8%** |
  | T2 market overlay (tape) | **better realised price** | −$3-4k | metering STRAWBERRY overflows the shed; burns WOOL/FERT + starves feed |

  **Every increment that frees capacity loses it to crops and starves the herd; every increment that
  protects the herd costs more crop tile-days than it earns.** Both directions are blocked, and the
  block is not eligibility (v1p.2b), not geometry (v1p.1b), not cash (S3 step 1e/2 Phase 0), not
  matching (④ step 2), and — now on the *sell* side — not price timing either (T2: the shed frontier
  pins realised price; §3.3 STOP row). The top-30 are not trading along this curve at all — they run **13 animals
  *and* 1.316 crop tile-days** on **14 hands** (§4.0). That is a different operating point, not a
  better scheduler. **Stop looking for a scheduler fix; the configuration is the product** — which
  is the strongest independent argument for §4.2's tape decision that this repo has produced.

  ⚠️ **The one named-but-unrun control**, per §2's STOP protocol: **arm A + v1o.3's mechanism E**
  (feed-round protection, already built and inert in `agent/`). E alone failed at herd 10 because
  there was no spare capacity to pay for it; arm A *creates* spare capacity. That combination is the
  only untested thing that could plausibly clear ④'s leg 2. It is **named so it is not lost, and
  deliberately not scheduled** — see the rating arithmetic below.

- 🔴 **Price a local gain in rating points before spending passes on it (2026-08-16).** The only
  clean calibration we have: v1o.2 was **+$5.069/ep** on holdout and resolved to **620,4 against its
  same-day pairmate's 600,2 — +20 rating points**, i.e. **~$253/ep per rating point**. Against that
  scale: item ④'s oracle ceiling (+$4.709/ep) is **~+19 points**, its *buildable* arm (+$812/ep) is
  **~+3**, and the gap to #1 is **~2.567**. Arm A, shipped perfectly, closes **0,7%** of the gap for
  six more passes (plan steps 3-8). This is the number that should have been computed before item ④
  was scoped, and it is now a standing pre-check: **no increment gets a pass until its plausible
  dollar gain has been divided by $253/ep and compared to the gap.**

  🔴 **Amended 2026-08-16, the day after it was written: $253/ep per point is regime-local, not a
  law.** The T1 tape converted to **+447 points over its same-day pairmate** — a rate several times
  better than the marginal increments the figure was fitted on. The mapping is not linear in dollars
  because rating is **won episodes**, not bank: an increment that moves you within a band you already
  lose converts poorly, while one that starts *winning* episodes against a new band converts far
  better. **This does not disturb the item-④ decision** — arm A (+$4.709/ep) sat in the same marginal
  regime as its calibration point (v1o.2, +$5.069/ep → +20), which is the only regime the figure was
  ever applied to. But the pre-check must now read: **divide by $253/ep for a marginal increment, and
  do not apply it at all to a change that alters which opponents you beat.**

- 🔴 **Bound a lever's *surface area* on paper before building it, and prefer the engine to the
  experiment when the engine can answer (2026-08-17, S6 step 0).** C-A was killed by two cheap
  things: a same-town **self-pair** (identical route, both seats — any difference is the lever and
  it read 1,000) and a **paper permutation** priced on the recorded route with no new episodes at
  all. The engine then explained both in one line — per-slot lockstep across players, per-product
  pools — which is a *stronger* result than any number of seeds, because it holds for every route.
  T2 spent a full pass on a lever it never bounded; step 0 spent an afternoon and returned a
  refutation plus a relocated target. **Every future challenger states its surface area first:
  what is the maximum this rule could earn if it fired perfectly on every opportunity in the
  recorded data?**
- 🔵 **The same-town control is the first local metric here that has tracked the ladder
  (2026-08-17).** S6 step 0 ranked Valmorlee above Ueddy on realised premium price with the town
  held fixed; the ladder currently reads 1.614,0 vs 1.398,7 (Ueddy still converging, so consistent
  rather than confirmed). Every earlier local metric in this repo compared across environments and
  §1's puzzle is exactly what that produced. **Hold the environment fixed and the number starts to
  mean something** — this is the practical form of the lesson below.
- 🔴 **A rating is a function of episodes played, so every ladder criterion must be written in
  episodes, never in hours (2026-08-17, S6 step 1b).** Kill (iii) was pre-registered as *"once
  converged (~1 day)"*. Read 22 minutes after the upload, the new submission sat at **1.125,9 on 7
  episodes** against the incumbent tape's **1.375,9 on 72** — and a criterion phrased in wall-clock
  invites exactly the comparison that would have "refuted" a submission gaining **+526 points in 7
  episodes**. Ueddy needed 72 episodes to reach 1.375,9; Valmorlee 111 to reach 1.599,1. **Any
  ladder-side criterion states an episode count, and any two scores compared are read on the same day
  *and* at comparable episode counts.** This is §1's decay caveat's twin: that one says *when* to read,
  this one says *how much play* is behind the number you read.
- 🔴 **Sum the loss counters that are already in every gate artefact before designing the next lever
  (2026-08-17, evaluating S6 step 1b).** The shipped route's own-farm losses —
  `unexpected_weeds_lost` 5,0/ep at the repo's own $300 and `plant_decay_units_lost` 15,0/ep, unpriced —
  add to **~$2,8-3,1k/ep**, *larger than the entire premium-lead overlay ceiling* (+$1.912/ep) the next
  pass was queued to chase. Both numbers were sitting in `results.json` on both arms of every tape gate
  since 08-16, and both are near-identical on the incumbent, i.e. **the whole tape line has been paying
  them the entire time.** R13 already said *price a counter, don't floor it*; this adds: **price it even
  when it passes**, because a counter inside its budget is still a bill. §4.3 S6 step 2a.
- 🔴 **A copied route's ladder ceiling is its donor submission's own rating — read the leaderboard
  before choosing a donor (2026-08-17, evaluating S6 step 1 Phase 0).** The cheapest external check
  available in this competition had never been run: **the donor's public score**. Run once, it
  reprices five weeks of work. Valmorlee, whose tape is our best submission at **1.617,6**, is a
  **#1018 / 1.842,4** agent whose taped submission dates from 08-11 — the tape realises **88%** of its
  donor and could never have gone higher. **Peter Parker**, a *pure* frozen tape (1 distinct market
  stream across 12 traces), holds **#29 / 2.844,2** — so the format was never the ceiling; **donor
  quality was**. And S6's chosen donor **ReCurSiON is #4 / 3.004,6**, which converts §4.3's local
  "+$14.267/ep vs the tape" into a *stated ceiling in the ladder's own units*: ~**+1.383 points** over
  our 1.621,5, i.e. the §1 **3000** gate. **Rule:** the surface area of any route-copy pass is the
  donor's leaderboard score, and it is one API call — state it in the brief, before the pass. Pairs
  with the two rules below: reward is the town, but **rating is the ladder**, and rating is exactly
  what the town-controlled ratio was standing in for.
- 🔴 **Selecting an entity on an uncontrolled aggregate reproduces the §4.1 error one layer up
  (2026-08-17, S6 step 1 Phase 0).** Donor selection's first shortlist ranked teams by **median
  reward** — but reward is 99% the town (§4.1b), so the ranking was the teams' *town luck*, not their
  calendars. It put ReCurSiON — which has the single best premium calendar in the field — nowhere,
  because its median reward (90k) is unremarkable. The **town-controlled** ratio (candidate's realised
  price ÷ its same-town opponent's, straight from the recorded episode — no replay, no desync) is the
  selector, and scanning it across **all** 42 eligible teams is what caught ReCurSiON. **Rule,
  extending the one below: never rank candidates on a number the environment dominates, even for
  triage — the good one hides in the noise.** The cost here was near-zero (the error was caught
  mid-pass by the all-teams scan), which is exactly why the scan must be the default, not a shortlist.
- 🔴 **A cross-entity comparison needs the shared-environment control, and this repo skipped it on
  its own headline (2026-08-17, v1v).** §4.1 ranked nine teams' realised prices against each other
  although **no two of them played the same market**. The controlled quantity was available all
  along — the two seats *inside* one episode — and it says 99-100% of that spread is the town's
  shop draw. **Rule:** before comparing a per-entity number across replays, state which parts of the
  environment the entities shared. If they shared none, the comparison is measuring the environment.
  This is the fourth entry in the §3.4 list of meta numbers that measured something other than what
  they appeared to, and the most expensive — it defined S5.
- **A ratio is a diagnostic, never a target.** Any criterion of the form "share X of unit-turns
  falls below N%" is satisfiable by shrinking the denominator — v1p1b arm A1 hit `worker_turns_moving`
  46,0%, the largest commute reduction ever measured here, by doing *fewer* working turns than
  baseline and shedding 30% of `crop_tile_days` into idle (§4.3 S3 step 1d). The success metric for
  every throughput increment from now on is **absolute `worker_turns_working` per episode, with
  `crop_tile_days` held flat** (within ±3% of the paired baseline) — R17 (§6) puts both numbers in
  every gate artefact. `worker_turns_moving` is reported alongside it and explains *why*; it never
  decides.

---
## 4. Phase B — what the top of the ladder actually does

**Sources.** (a) The **official** `kaggle/kaggriculture-episodes-2026-08-10` daily dataset —
rating-sorted, guaranteed to be on the engine of that day. We took its 60 newest episodes
(**120 seats**), verified every one at `townCenterSellInterval = 24`, and profiled them with
[analysis/b2_current_engine_meta.py](analysis/b2_current_engine_meta.py). (b) The
*What the Top Farms Do* kernel's own `daily_meta-2026-08-10.json` (207 episodes / 414 seats at
Elo ≥ 3100) as an independent cross-check — its median bank $82.237 against our $82.747 on the
same day. (c) The top-30 opening census in the v27 notebook. Full tables:
[ladder_snapshots#b2-current](docs/meta/ladder_snapshots.md#b2-current).

> 🔴 **A correction to what I reported in the previous pass.** The first top-5 profile (B1) read
> whatever replays we held per team — and **56 of those 66 episodes ran the pre-1.32.6 engine**
> (`townCenterSellInterval: 12`, the town centre absorbing 140 units/product/season instead of 30).
> The change reached live episodes **between 07 and 08 August**. Everything B1 said about crop mix,
> per-crop tile-days, $/tile-day and herd composition described a game that no longer exists.
> What survived re-measurement: 3 quadrants, the herd **ramp**, crew peaking above 10, and tiles
> held planted to the end. What did not: 14 animals at 8C+6S (really **13 at 9C+4S**), strawberry
> at $58-67/tile-day (really **$39,7**), wheat at 213-323 tile-days (really **559**). **Any donor
> route must come from a post-2026-08-07 episode**, and that is now a hard rule in §4.3.

### 4.0 The current-engine profile

| Quantity | Median per seat, 120 seats, engine 1.32.6 |
|---|---|
| Money d5 / d10 / d15 / **d20** / d24 / end | $516 / $4.863 / $16.720 / **$48.560** / $63.129 / **$82.747** |
| Planted tiles d10 / d15 / d20 / **d24** / d27 / d29 | 56 / 62 / 60 / **61** / 45 / **1** |
| Hands d5 / d10 / d15 / d20 / d29 | 3 / **14** / 9 / **14** / 10 |
| Animals d5 / d10 / d15 / d20 / end | 6 / 12 / 12 / 12 / **13** — peak **9 COW + 4 SHEEP** |
| Quadrants | **3** — second on day **6**, third on day **10**, SE never |
| Crop tile-days | **STRAWBERRY 577 · WHEAT 559 · MELON 180** (~1.316 total) |
| Sell calendar (first day, batch) | WHEAT d5/6 · FERT d2/4 · WOOL d6/**10** · MILK d9/6 · MELON d10/6 · STRAWBERRY d14/**14** |

Against us (v1h.2d live): **$57.360** final, **415** crop tile-days, **10** animals flat, **6**
planted tiles at d24 and **0** by d28.

⚠️ **The 13-animal (9C+4S) row is blocked for our planner on feed logistics, not on the config
(S3 step 2, 2026-08-15).** Setting `targets` to 9C+4S — with or without the 6/12/13 ramp — REGRESSES
−$15-21k/ep and loses every seed: the three animals beyond ten land at Manhattan distances 7,7,8 from
the (4,4) shed (herd Σdistance 37→59, +59%), and our `assign()` greedy routing cannot feed them
without either escaping them (122/24-ep) or starving crop watering (`crop_tile_days` −36%). C2 pays the
day-0 **cash** half in full; the **logistics** half is unpaid. Reaching this row needs deferred item
③/④ (routing throughput) first — see the §3.3 STOP row and §4.3 S3 step 2. The profile itself is not
refuted; our ability to reach it with the current routing is.

### 4.1 The finding that decides the strategy

> 🔴 **HALF OF THIS SECTION IS REFUTED, 2026-08-17 (v1v).** Read the correction in **§4.1b**
> before using any per-team price number below. In one line: *"production at the top is a
> copied constant"* is **confirmed and strengthened**; *"they are differentiating which
> premium they win"* is **not supported** — 99-100% of the realised-price spread below is the
> town's random shop draw, which no agent controls. The nine-team table was never controlled
> for it. §4.3 **S5 is withdrawn** and replaced by **S6**.

**Production at the top is a copied constant. The entire remaining spread is realised price.**

Nine teams with ≥6 seats each. Their tile-days and their *units sold* are nearly identical —
strawberry 502-581 tile-days, wheat 541-569, melon 180-190; 245-286 strawberry units, 439-473
wheat, 108-114 melon, 132-138 wool, 218-225 milk. **Winners and losers (57/57 seats) are identical**
on every structural measure, on first-sell day and on batch size.

Yet final bank runs **$63.866 → $94.850, a 1,49× spread.** All of it is $/unit:

| | STRAWBERRY | WOOL | MILK | WHEAT | MELON |
|---|---:|---:|---:|---:|---:|
| best realised $/unit | **$105,1** (Hak) | **$192,7** (Hak) | **$195,9** (Ueddy) | $43,6 | $163,6 |
| worst | **$38,2** (Valmorlee) | $52,1 (Ueddy) | $56,2 (Valmorlee) | $39,1 | $140,0 |
| **spread** | **2,75×** | **3,70×** | **3,49×** | 1,12× | 1,17× |

The three products with spread are exactly the three shallow cliffs — **strawberry 62, wool 59,
milk 76 net units**. Wheat (cliff >2.000) and melon are flat for everybody. Hak wins strawberry and
wool; Ueddy wins milk and has the *worst* wool of the nine. **They are differentiating which premium
they win.** The top of this ladder is no longer playing farming; it is playing a three-product
timing race on top of a shared production script.

⚠️ And our own realised prices (Θ1, 34 ladder replays) are **MILK $210,62 · WOOL $196,81**, at
**1,7×** the opponent's wool volume. **Our sell side is not the problem — our production is**
(415 crop tile-days against 1.316). That is the whole reason the plan below is ordered the way it is.

### 4.1b 🔴 The correction — the price spread is the *town*, not the agent (2026-08-17)

Full report: [baselines/2026-08-17/v1v_shop_demand_report.md](baselines/2026-08-17/v1v_shop_demand_report.md).
Script `analysis/v1v_shop_demand.py`, guards `tests/test_v1v_shop_demand.py` (7),
data `data/derived/v1v_shop_demand.json`. **150 episodes / 300 seats** from the official
`kaggle/kaggriculture-episodes-2026-08-16` dataset, rating-sorted, **all on engine 1.32.7**.

**The control §4.1 owed and never paid.** Shops are drawn **with replacement** from the eight
`SHOPS` types, one every 3 days, capped at 8 instances
([kaggriculture.py:886-891](engine_reference/kaggriculture.py#L886-L891)); every 4 steps each
instance consumes `multiplier` units of every product it lists — **2 for single-product
shops**, 1 otherwise ([:733-742](engine_reference/kaggriculture.py#L733-L742)). That drain is
the *denominator* of realised price and it is **redrawn every episode**.

| Product | shop types | E[units/tick] | **P(no buyer at all)** |
|---|---:|---:|---:|
| WHEAT | 5 | 5,0 | 0,04% |
| STRAWBERRY | 4 | 4,0 | 0,4% |
| MILK | 3 | 3,0 | 2,3% |
| CARROT | 2 (PET_CAFE ×2) | 3,0 | 10,0% |
| EGG / TOMATO | 2 | 2,0 | 10,0% |
| **WOOL** | **1** (YARN_STORE ×2) | 2,0 | **34,4%** |
| **MELON** | **0** | **0** | **100%** |
| **FERTILIZER** | **0** (also out of `TOWN_CENTER_PRODUCTS`) | **0** | **100%** |

**Measured decomposition of seat-level realised $/unit:**

| product | median $/u | p10→p90 | **between towns** | within town |
|---|---:|---:|---:|---:|
| STRAWBERRY | 113,7 | 44→208 (4,76×) | **99%** | 1% |
| WOOL | 114,9 | 43→239 (5,55×) | **100%** | 0% |
| MILK | 58,2 | 24→211 (8,70×) | **100%** | 0% |
| **MELON** | 130,5 | 125→200 (1,59×) | 35% | **65%** |
| WHEAT | 44,9 | 42→47 (1,13×) | 99% | 1% |
| FERTILIZER | 52,1 | 45→54 (1,19×) | 94% | 6% |

Monotone dose-response in every case — realised $/u against that town's drain: **STRAWBERRY
13→236 (18×)** over 0→7 units/tick, **MILK 18→252 (14×)**, **WOOL 46→244 (5,3×)**. **51 of
150 towns (34,0%) drew no YARN_STORE at all** — the predicted 34,4%, measured.

⇒ **Hak's $105,1 strawberry against Valmorlee's $38,2 is, on this evidence, overwhelmingly a
statement about their towns.** §4.1's nine-team table compares teams that never played each
other in the same market. This is §3.4's standing trap — *"at what moment and on what entity
was it measured"* — caught on our own headline finding.

#### What the top of the ladder is actually doing

Winner vs loser, median over the same 150 episodes:

| product | W $/u | L $/u | **price ratio** | W units | L units | volume ratio |
|---|---:|---:|---:|---:|---:|---:|
| STRAWBERRY | 117,1 | 112,7 | **1,04** | 254 | 253 | 1,00 |
| WOOL | 117,2 | 111,8 | **1,05** | 120 | 120 | 1,00 |
| MILK | 60,9 | 57,5 | **1,06** | 273 | 272 | 1,00 |
| MELON | 131,6 | 130,2 | 1,01 | 114 | 120 | 0,95 |
| WHEAT | 45,0 | 44,8 | 1,00 | 599 | 598 | 1,00 |
| FERTILIZER | 52,1 | 52,0 | 1,00 | 242 | 242 | 1,00 |

**Both seats sell the same basket in the same volume, to within 1%, in 150/150 episodes.**
That is our own independent measurement of what the reference-agents `NOTICE` reports from 530
replays — identical 712-turn farmer/hand sequences across *"one group of 29 teams, another of
15, another of 8, with 104 distinct teams"* (§4.5). **The top of the ladder is a mirror
match**, and the winner's entire edge is a **1,04-1,06× realised price on the three premium
products**.

The town draw is **common-mode**: it lifts both banks together (median loser bank $50,7k →
$114,1k as premium drain goes 3→14 units/tick) while the gap stays small.

| \|bank gap\| | p10 | p25 | **p50** | p75 | p90 | mean |
|---|---:|---:|---:|---:|---:|---:|
| top-ladder episodes | $406 | $1.104 | **$2.826** | $5.494 | $11.165 | $4.508 |

**Median premium (STR+WOOL+MILK) revenue is $71.924/seat** ⇒ **+1% realised price = +$719/ep**,
and the **+5% edge today's winners already hold = +$3.596/ep**. Episodes reachable by an extra
$X of realised revenue: **+$2.000 → 40,7% · +$3.000 → 52,7% · +$5.000 → 72,7%**.

#### The three consequences that bind

1. **§4.3 S5 is withdrawn.** Its stated objective — *"beating Hak's $105,1 strawberry and
   $192,7 wool"* — is a number no agent controls. Replaced by **S6** below.
2. **MELON is the only product with a real within-town contest** (65% of its variance, **zero**
   shop buyers in 150/150 towns, flat ~$144 whatever the draw) — and it is our single largest
   revenue hole (§3.2(7): **−$27.263**, 0 units against 132).
3. **§3.4's amended rating rule applies in its second form.** A premium-price edge changes
   *which episodes you win* at the top of the ladder, so the **$253/ep marginal rate must not
   be applied to it**. That rate is for increments inside a band you already lose.

⚠️ **Not claimed:** shop *count* and shop *timing* are confounded here (a YARN_STORE drawn on
day 3 drains far more than one drawn on day 24) and were not separated. The within-town control
is tight for the town and **loose for strategy** — with both seats running the same route it
cannot see an edge every top agent already has. And 150 episodes is a stride sample of one
day's rating-sorted dataset; nothing here describes the ladder below the top.

### 4.2 Decision taken (2026-08-11), and what the rules actually say

The repo's standing ban on replay-derived priors ("Open #11") is **withdrawn by the user's explicit
decision**: we follow the top 30. **R10 is now closed** — the full rules text was supplied and read.
What it says matters, because it does not all point one way.

**Clearly permitted — using replays as an input to development.**

- §2.11 *Environments & Public Availability*: *"A replay of each episode of the competition, which
  includes the actions taken by your Submission in the episode, may be publicly available and
  downloadable."* Replays are public by design, actions included.
- §2.4a *Data Access and Use* (licence: **Apache 2.0**, §1.7): *"You may access and use the
  Competition Data for any purpose, whether commercial or non-commercial, including for
  participating in the Competition."*
- §2.6a *External Data*: even on the stricter reading that replays are External rather than
  Competition Data, they are *"publicly available and equally accessible to use by all Participants
  … at no cost"* — the exact condition the clause requires.
- §2.12 *No Ingress or Egress* prohibits the **running agent** from reaching outside itself. A table
  baked into `main.py` is inside the Submission. Not an issue.

So **S1 and S2 are unambiguously fine.** Nothing restricts analysing, extracting or replaying public
episodes offline.

**The exposure is narrower than "can we use replays", and it lands at the prize stage.**

- §3.14a *Warranty*: *"You warrant that your Submission is your own original work and, as such, you
  are the sole and exclusive owner and rights holder of the Submission."* A submission whose core is
  another participant's verbatim 719-action sequence strains that warranty. Whether a game action
  sequence is even copyrightable is genuinely unsettled — move lists read like facts, not creative
  works — and **I am not in a position to resolve that**, only to flag that the clause is broad and
  we would be relying on an untested reading of it.
- §2.5 + §2.8 *Winner Licence / Obligations*: a winner must license the Submission **and its source**
  under **CC-BY 4.0** and *"represent that you have the unrestricted right to grant that license"*,
  plus publish a reproducible description of how it was generated. With ten equal $5.000 prizes and
  top-10 as our stated target, these obligations are **live, not hypothetical**.
- §2.4b *Data Security*: *"You agree not to transmit, duplicate, publish, redistribute or otherwise
  provide or make available the Competition Data to any party not participating in the
  Competition."* **This repo is public** (MIT, README, prepared for release). Committing another
  participant's extracted route into it is redistribution of competition data to non-participants —
  a concrete problem, not a philosophical one.
- §3.8d lets the Sponsor disqualify for *"unfair playing practices"*. Weighing against that: the
  practice is open and credited at the top of this ladder (the v27 notebook, 134 votes, names
  Ezzzzzekki's episode 91493566 as its source), and the organisers discuss trajectory copying in the
  forum without prohibiting it. So this is a low risk — but it is the Sponsor's call, not ours.

**Consequence: copy the profile, not the tape** (default; see §4.3).

> 🔴 **REVERSED BY THE USER, 2026-08-15.** The direction is now explicit: *"I want the measured
> path where we copy the tape and if we win we will figure it out."* The concern below was raised
> and reaffirmed, so it is settled — the tape ships. What that changes and what it does not:
>
> - **It is the only measured path we hold.** S2 replayed 3 donor tapes × 3 opponents × 2 seats:
>   **0/18 fell below our own $57.360**, worst case $57.673, degradation 7-37% against hard
>   opponents, and the de-sync is **opponent-independent** (no-ops start day 4-10 because the route
>   drifts off its own trajectory) ⇒ a **light** repair layer, not a heavy one. Donor home banks are
>   $82-95k. Nothing else in this repo has ever measured above our own floor before being built.
> - **D28 does not touch it.** The top-9 profile grows zero CARROT/TOMATO/EGG, so the 1.32.7 curves
>   cannot move a donor's recorded bank. Re-verify with the S1.2 exact-replay check anyway — that
>   is step 0, and it is cheap.
> - **The three mandatory conditions from the paragraph below stand unchanged**: full provenance
>   (episode id, seat, team, action-stream sha256) in the checkpoint ledger and the submission
>   description; the extracted route stays **out of the public repo** (gitignored, local only, §2.4b);
>   and §3.14a/§2.5 get resolved with the Sponsor if we finish top-10. "We will figure it out" is the
>   user's call on the third of those, not a reason to skip the first two — those are what keep the
>   option open at all.
> - **What does not change:** we still do not open, extract or execute competitor *notebook* source
>   (`main.py` / `submission.tar.gz`). Separate permission, separate licence, and nothing needs it.
> - **Item ④ is no longer the critical path** — a tape never calls `assign()`. It remains the hedge
>   against §4.4#1 tape decay and the precondition for our own planner reaching §4.0. See
>   [docs/plans/item4_min_cost_assignment.md](docs/plans/item4_min_cost_assignment.md) §0.

§4.1 already established that top-30 production is a **constant**, and a constant is described by
about twenty numbers: 13 animals (9 COW + 4 SHEEP) on a 6/12/13 ramp, 3 quadrants at d6 and d10,
~577 strawberry / 559 wheat / 180 melon tile-days, tiles held planted to d24, and the sell calendar.
**Those numbers are measurements** — the same kind of published meta statistic this repo has been
deriving all along, unambiguously ours to use, with no §3.14a warranty question, no §2.4b
redistribution question, and nothing awkward in a §2.8 write-up. Re-implementing our planner to
*hit that profile* buys the same ~$82k production.

It is also **the better engineering answer**, independently of the rules: a parameterised policy
degrades gracefully where a fixed tape desyncs (which is exactly what S2 exists to measure), and it
does not depreciate the way the v27 notebook measured its own frozen v26 doing — **87/90 wins →
14/27** against a newer field.

**What stays out either way:** we still do not open, extract or execute the `main.py` /
`submission.tar.gz` that competitor *notebooks* publish. That is their source code, a separate
permission with a separate licence question, and nothing in the plan needs it.

**If the tape route is still wanted** — it is the user's call and the rules do not forbid the
*activity* — then three things become mandatory rather than advisable: record full provenance
(episode id, seat, team, action-stream sha256) in the checkpoint ledger and the submission
description; keep the extracted route **out of the public repo** (gitignored, local only, per
§2.4b); and accept that §3.14a/§2.5 would be resolved with the Sponsor if we finish top-10.
### 4.3 The programme: replicate → freeze → innovate

The user's direction, made concrete. Each stage has a gate; no stage starts before the one above it
has a measured result.

**Default path: replicate the top-30 *profile* with our own planner** (§4.2). The tape variant is
kept as a documented option — S1 and S2 measure it either way, because what they produce (the exact
target profile, and where an open-loop policy breaks) is what the profile path needs too.

---

**S1 — Extract the target profile, and the donor routes that define it.** *(no `agent/` change)*

Work only from **post-2026-08-07 episodes** (the engine rule from §4.2's correction), drawn from the
official daily datasets, which are rating-sorted and engine-consistent by construction — this is
already how [b2](docs/meta/ladder_snapshots.md#b2-current) was built.

Produce two things:
1. **The target profile as parameters** — per-day herd, crew, quadrant, tile-count and per-crop
   tile-day curves, plus the sell calendar, with the spread across teams so we know which numbers
   are converged (all of them, so far) and which are a single team's choice. This is the
   specification the planner will be aimed at, and it is a measurement, not a copy.
2. **2-3 donor action streams** with full provenance `(episode_id, seat, team, sha256)`, held
   **locally and gitignored** (§2.4b — this repo is public). These exist to answer S2, not to ship.

Adopt the **chronological protocol** the v27 notebook uses, because it is our own screen→confirm
discipline applied to replays and it is the only thing that stops us selecting on the opponents we
then score against: freeze a cutoff `EpisodeId`, select from *older* episodes, evaluate on
**strictly later** ones.

*Gate:* the profile reproduces across ≥6 teams with a stated spread, and each donor stream replays
against a copy of its own opponent's actions to within a defined tolerance of its recorded bank.

---

**S2 — How far does an open-loop policy survive contact?** *(no `agent/` change — the
make-or-break diagnostic, and it is worth running whichever path we take)*

A fixed action sequence desyncs against a *different* opponent for three reasons: prices move
differently, `_spawn_weeds` consumes RNG driven by **both** farms' empty-tile counts, and the shop
unlock is drawn from the same stream (§2.1.1). Every top notebook carries a "local WEED repair
(DIG → retry → short replay)" layer precisely because of this.

Replay each donor stream in our harness against `meta_route`, against `checkpoints/v1i`, and against
another donor, both seats. Record final bank against the donor's original, and **which actions
became silent no-ops, on which day, and why**.

*Why this matters even on the profile path:* the failure map is the specification for how much
runtime adaptivity a replicated profile actually needs. If a tape survives at 90%, a mostly-static
planner is enough; if it collapses at day 12, the adaptive layer is the product.

*Gate:* a measured retention figure and a dated failure map.
*Kill:* if even a repaired route lands below our current $57k, open-loop replication is not the
path, and S3 becomes "scale our own planner toward the §4.0 profile" with no tape involved.

---

**S3 — Hit the profile, then the market overlay.** *(first `agent/` work — smallest possible)*

In order, each gated separately:

1. **Production to profile.** Aim the existing planner at §4.0: herd **13 (9C+4S) on a 6/12/13
   ramp** rather than a step (this is the specific thing our old 12-14 animal STOP got wrong),
   quadrants at d6/d10, tile targets ~577 strawberry / 559 wheat / 180 melon tile-days, **carrot to
   zero**, and tiles held planted through d24. Our measured blockers here are known and named:
   27,8% idle unit-turns, a hire gate that never reaches 11+ hands, and a farm that shuts down at
   d17 — all three are exactly what this stage has to fix.
2. **Desync/repair robustness** — whatever S2's failure map says is needed.
3. **Market overlay** — reorder existing SELL slots by modelled price impact plus live town demand,
   and fire the sell-ahead pre-emption. **We already have this**: `agent/sell_ahead.py`,
   `agent/demand.py` and `checkpoints/v1i`, which passed unpinned holdout at `GO=True`. §4.1 says
   this is where 100% of the top-30's remaining spread lives.
   🔴 **RUN as T2 on the *shipped tape* (not our planner) and ⛔ STOPPED, 2026-08-16.** Phase 0 (cash
   coupling) → GO: STRAWBERRY, the −61% product, is never a cash-funding dependency, so a strawberry-
   only overlay is unconditionally cash-safe and production stayed byte-identical. But the overlay
   **STOPS on the shed**: the Valmorlee tape runs the shed at **98/100** and sells strawberry the
   instant it harvests it (holds zero), so metering strawberry to raise its price overflows the shed,
   burns WOOL/FERTILIZER and rejects the `BUY_PRODUCT WHEAT` feed deposit → escapes → **bank −$3-4k/ep**,
   even though it wins strawberry $/u. The realised-price lever §4.1 identifies is **not accessible on
   this donor tape** — its sells are load-bearing for shed capacity. §3.3 STOP row; §3.4 wall (sell
   dimension); `baselines/2026-08-16/t2_report.md`. (This is about the *tape*; the lever may still be
   live for our own planner if it ever reaches the §4.0 profile with shed headroom — untested.)

*Gate:* the existing protocol unchanged — `--arm-role acceptance` against a non-mirror bench,
`--arm-role regression` in mirror, unpinned holdout confirm, immutable checkpoint. Production
changes are **occupancy** knobs, so `--town-pin basket` on both arms (§2.1.2).

#### S3 step 1 — status as of 2026-08-11 (first `agent/` work since the reset)

Full tables: `baselines/2026-08-11/s3_step1_report.md` (local); session narrative in
[memory.md](memory.md). Live `main.py` ≡ **`checkpoints/v1o_2`**, `pytest tests/` **229 passed**,
**no Kaggle submission** (that is S4).

| | v1i (start) | **v1o_2 (now)** | §4.0 profile |
|---|---:|---:|---:|
| crop tile-days/ep | 413 | **562-612** | 1.316 |
| idle unit-turns | 28,2% | **16-18%** | — |
| `median_bank` vs `meta_route`, DEV pinned | $54.552 | **$59.875** | — |
| animals · MELON tile-days | 10 (4C+6S) · 0 | 10 (4C+6S) · 0 | 13 (9C+4S) · 180 |

- **`checkpoints/v1o_1` ✅ GO** — `strawberry_last_plant_day` 5 → 12, plus `wheat_first_plant_day`
  splitting WHEAT's window off STRAWBERRY's. The E0 diagnostic
  ([analysis/e0_s3_blockers.py](analysis/e0_s3_blockers.py)) showed §3.2's "farm shuts down on day
  17" was **one config constant**: STRAWBERRY's raw target hit 0 on day 6 and never returned.
  Holdout unpinned **+$1.253,1 IMPROVED**.
- **`checkpoints/v1o_2` ✅ GO** — `executor.hire_last_hour` 0 → 2 plus an unconditional order-slot
  cap on HIRE. At the unchanged crew of 10 it adds **no hands**; it stops the morning's 10 HIREs
  from pushing that day's SELL and BUY_SEED orders past the engine's 10-order budget. Holdout
  unpinned **+$5.068,5 IMPROVED**, seeds 42-6, and **every loss counter falls** (escapes 8 vs 25,
  overflow 257 vs 371, water-weeds 192 vs 236).
- ⛔ **Two STOPs**, both in §3.3 above, both the *same* mechanism.

**🔴 The next increment is not the one this section originally listed.** Steps "herd 13 (9C+4S)"
and "MELON in / CARROT to zero" both add work to priority tiers 0-1 — exactly the tier the
`sw_hands_target=12` STOP proved is saturated. Three independent measurements name the blocker:

1. [analysis/v1o1_product_split.py](analysis/v1o1_product_split.py) vs the non-mirror bench —
   STRAWBERRY volume 32 → 80 units at a **higher** realised price ($232,9 → $259,0, i.e. no
   market saturation at all), while **WOOL loses 41% of its units and FERTILIZER 27%**. `HARVEST`
   on an animal tile is priority 1, `COLLECT_FERTILIZER` is 3, `WATER` is 0.
2. The 12-hand STOP: escapes 87 vs 32, `animals_underfed_days` 42,3 vs 39,8.
3. The endgame-crew screen: `endgame_hands_target` 6 → 10 did **not** fix water-weeds ⇒ the tiles
   are lost to **priority**, not to headcount.

So S3 step 1 gained a stage **1b — protect the FEED pipeline**.

#### S3 step 1b — ⛔ run, and STOPPED (2026-08-11 γ)

Seven variants screened on SMOKE, two taken to the DEV acceptance arm, both refused. Full tables
in `baselines/2026-08-11/s3_step1_report.md`; the STOP row is in §3.3. **The diagnosis above was
correct and the fix is still not worth taking**, which is a different outcome from either "it
worked" or "we were wrong", and it is the one that changes the plan:

- **The mechanism is real and the fix works.** Variant E drove `animals_escaped` **13 → 0** and
  recovered the starved line exactly as predicted — `COLLECT_FERTILIZER` ops 123 → 193/ep,
  FERTILIZER units 123 → 191/ep, `worker_turns_moving` 62,0% → 57,5%.
- **And it costs more than it earns.** It was paid for out of `crop_tile_days` (612 → 574).
  13 prevented escapes ≈ $135/ep; the production forgone ≈ $1.180/ep. At 574 crop tile-days
  against the profile's 1.316, a unit-turn is worth roughly an order of magnitude more on a tile
  than on an animal — so **every** reallocation toward animals loses, however cleanly built.
- **The reason it cannot be tuned around:** the feed round is open **100% of the hours of a median
  day** from d9 (§3.3). Tier 0 is saturated all season, so reordering inside it is zero-sum, and
  "wait for a quiet moment" is not an available strategy.

**Consequence for the three items that were said to be blocked behind this gate.** Crew >10,
herd >10 and `strawberry_last_plant_day` >12 are **not unblocked — and they were never blocked by
priority.** They are blocked by what S3 step 1b ran into: work added at tiers 0-1 has nowhere to
go in an already-saturated tier. **The constraint is unit-turn supply and routing, not order.**

**The number that now defines the next increment: `worker_turns_moving` is 57-62% of all
unit-turns** — three in five spent walking, against 19% idle and only ~23% working. That points
straight at the standing §3.3 item, *"routing-distance decoupled from urgency-distance in
`assign()`"* (the reverted 1.32.5 D26 shed-access fix), and at anything else that raises usable
unit-turns rather than redistributing them. The standing v1k re-test still rides on MELON, which
still sits behind whatever fixes throughput.

#### S3 step 1c — ⛔ both increments run, and STOPPED (2026-08-13)

Full report: `baselines/2026-08-13/s3_step1c_report.md` (local). `pytest tests/`: **237 → 244
passed**. **No submission** — live `main.py` ≡ `checkpoints/v1p_1`, verified behaviour-identical
to `checkpoints/v1o_2` (mirror compare, SMOKE 0-11 both seats, `mean_diff` exactly $0,00, 12/12
ties). R15 landed first (`worker_turns_moving` now in every gate artefact via
`_V1K_REPORT_METRICS`), which is what made both STOPs below measurable directly from their gate
output.

- **v1p.1 (herd compaction, config-only)** reordered `animal_structure_tiles["PASTURE"]` to move
  the two farthest SHEEP slots onto the two NW CARROT tiles freed by `carrot_tiles: 3→1` —
  distance 1 instead of 6, herd Σdistance 39→27. ⛔ **STOPPED at SMOKE**: `worker_turns_moving`
  fell exactly as designed (61,7%→53,6%) but `animals_escaped` went 2→48, **deterministically
  (2 in all 24 orientations)**, always the same two COW at (3,2)/(3,3) — tiles the change never
  touched. Root cause: making two SHEEP slots closer than *every* COW slot lets SHEEP win the
  whole initial multi-day PLACE race in `assign()`'s type-blind greedy loop, delaying COW's first
  feed past the escape threshold. Intrinsic to the tile choice, not the specific arm — the
  original brief's arms B and C share the same two tiles and would hit the identical race, so
  neither was screened separately. See §3.3.
- **v1p.2 (zone assignment, `agent/scheduler.py`)** added `scheduler._zone_partition` — a
  proportional, deterministic split of units across owned quadrants, applied in `assign()` as a
  filter on `eligible_units` (never on tasks), with `allowed_unit` tasks and WHEAT-carriers
  exempt and an explicit fallback to the global pool. 7 new `test_v1p2_*` guards pin the
  partition algorithm and the filter in isolation. ⛔ **STOPPED at SMOKE**, and the increment's
  own kill criterion fired: `worker_turns_moving` barely moved (60,0%→58,7%, nowhere near the
  ~55% target), while a structural hard-zero counter broke (`plant_decay_units_lost` 0→17).
  Likely mechanism: the zone partition has no memory across turns, so a unit already `committed`
  to a task (the C1 stickiness fix) can be re-zoned *out* of eligibility for it the next turn as
  the task-count mix shifts — reproducing, from outside `committed`, the exact oscillation class
  of bug it was built to prevent. See §3.3.

**Both STOPs point the same direction.** v1p.1 shows a purely geometric win (Σdistance 39→27)
can be erased by a second-order scheduling interaction (animal-type placement racing); v1p.2
shows that restricting `assign()`'s candidate pool without giving it a continuity guarantee
reproduces the exact commitment-thrash class of bug `committed` exists to prevent. Neither
result says throughput can't be raised — both say the fix has to live *inside* `assign()`'s own
greedy structure (or be paired with a stickiness-aware zone extension), not bolted on as a static
tile reshuffle or a stateless pre-filter.

**⚠️ Neither STOP above was actually final** — each root cause, read closely, implied a control
that was never run. v1p.1's diagnosis ("SHEEP wins the type-blind PLACE race because it got the
close tiles") implied the one-line reorder of giving COW the close tiles instead. v1p.2's
diagnosis ("the zone partition has no memory across turns") implied threading `committed`
through it. ROADMAP §2's STOP protocol was updated to say so explicitly: *a STOP is only final
once its own stated mechanism has no untested implication left.*

#### S3 step 1c — both untested controls run, both STOP too (2026-08-13, continued)

Full report: `baselines/2026-08-13/s3_step1c_controls_report.md` (local). `pytest tests/`:
**244 → 248 passed** (4 new `test_v1p2b_*` guards). Checkpoints created before each screen —
`checkpoints/v1p1b_armA1`, `checkpoints/v1p1b_armB`, `checkpoints/v1p2b` — all `compare` calls
below run against these, never against `main.py` directly (unlike v1p.1/v1p.2's own SMOKE
screens, whose fingerprints match no checkpoint on disk — see §6 R16). Live `main.py` reverts to
exactly `v1o_2`'s measured behaviour again: `gates/v1p1b_v1p2b_final_inertness_check`,
SMOKE 0-11 both seats, `--metrics`, `mean_diff` exactly $0,00, 12/12 ties, every counter
byte-equal (`crop_tile_days`, `worker_turns_idle`, `worker_turns_moving`,
`animals_underfed_days`, `crop_revenue` on both sides). **No submission.**

- **v1p.1b — herd compaction, both controls (config only).** Arm A1 (`checkpoints/v1p1b_armA1`):
  same tile set as arm A, but COW gets the two distance-1 tiles instead of SHEEP.
  `animals_escaped_a` **48** (vs its own paired `v1o_2` mirror at 0) — the *same magnitude* as
  arm A's original failure, but now a **mixed** pair, (4,2) COW and (3,2) SHEEP, at the same day
  2 / step ~48 timing (`gates/v1p1b_armA1_smoke_mirror`). `worker_turns_moving` still fell as
  designed (60,3%→46,0%). **This refutes v1p.1's own root cause**: the race was never
  specifically SHEEP-vs-COW — reordering which type gets the close tiles does not fix it, so the
  mechanism must be something about the shared, type-blind PLACE queue itself (which two of the
  ten claimed slots finish *last*), not a property of SHEEP in particular. Arm B
  (`checkpoints/v1p1b_armB`, the confound control arm A never ran): `carrot_tiles` 3→1 alone,
  `animal_structure_tiles["PASTURE"]` **completely untouched** — no geometry change at all.
  `animals_escaped_a` **12** (vs its own paired baseline 2), seed/orientation-dependent (6 of 24
  orientations, not deterministic) rather than arm A1's 100%-reproducible pattern
  (`gates/v1p1b_armB_smoke_mirror`). **Dropping `carrot_tiles` below 3 is itself destabilizing to
  the feed pipeline, independent of what the freed land becomes** — a second, distinct mechanism
  from v1p.1's. Excess-over-own-paired-baseline decomposition (approximate — §2.1.1 paired
  baselines legitimately drift seed-to-seed under the shared weed-spawn RNG): arm A1 excess ≈48,
  arm B excess ≈10, geometry-only ≈38. **Closes the "convert a CARROT tile to compact the herd"
  family for good** — confirmed analytically alongside the two screens: NW is fully allocated (3
  CARROT + 8 STRAWBERRY + 13 PASTURE + 1 COOP = 25) and the 13 PASTURE tiles sorted by distance
  are 2,2,2,3,3,4,4,5,6,6,7,7,8 — **the ten currently-claimed slots are already the ten
  nearest**, so there is no free reorder left inside the existing pool; proximity can only be
  bought by converting a crop tile, and neither tested split makes that purchase pay for itself.
- **v1p.2b — sticky zone assignment** (`checkpoints/v1p2b`, `agent/scheduler.py`). Threaded
  `committed` into `scheduler._zone_partition`: a unit with a live commitment whose task still
  exists is pinned to that task's zone before any quota is computed, so quotas become a soft
  target for the remaining, uncommitted units only — closing exactly the memory gap v1p.2's STOP
  diagnosed. New mandatory guard (`test_v1p2b_zone_partition_pins_a_committed_unit_to_its_own
  _task_zone`) plus 3 more `test_v1p2b_*` tests pin the pinning, the quota-exclusion, the
  stale-commitment fallback, and an end-to-end two-turn `assign()` reproduction of v1p.2's exact
  STOP scenario. SMOKE 0-11, both seats, `--town-pin basket`, mirror vs `checkpoints/v1o_2`
  (`gates/v1p2b_smoke_mirror`): `mean_diff` **-$2.688,6 REGRESSED** (CI [-3.832,5, -1.544,8],
  p=6,3e-3), episodes 2-22. **The fix worked at the structural level**: `plant_decay_units_lost`
  **0** (was 17, a structural hard-zero break under v1p.2), `animals_escaped` back to parity
  with baseline (5 vs 5, was 20 vs 6). **But the number the whole increment is judged on did not
  move**: `worker_turns_moving` **58,9%→60,3%**, essentially the same ~1,4pp non-movement as
  v1p.2's own original screen (58,7%→60,0%). 🔴 **Corrected 2026-08-14 (S3 step 1d race):** the
  reason recorded here previously — "zoning was never the lever" — is not what the data says.
  Zoning *did* cut travel (60,3%→58,9%) and cut work harder (−828 working turns) while
  quadrupling water-weeds (226 vs 61). The mechanism is: **zoning trades cross-quadrant commute
  for within-quadrant starvation, and the exchange is negative** — apportionment is by task
  *count*, tasks are not equal work, and a quadrant with someone-but-not-enough never trips the
  empty-zone fallback. What is refuted is **proportional-by-task-count apportionment**, not the
  claim that travel share is movable — v1p1b arm A1 (§3.3) later measured `worker_turns_moving`
  falling to 46,0%, proving it is very movable. The pre-registered criterion fired and the STOP
  stands; this corrects the *reason*, not the verdict (ROADMAP §2 item 9 — a confirmed mechanism
  and a viable increment are different claims, and so are a correct verdict and its stated
  reason). `mean_diff`'s regression is now driven by a *different, smaller* loss
  pattern than v1p.2's (`water_weeds_lost`/`unexpected_weeds_lost` 226 vs 61,
  `shed_overflow_burnt` 18 vs 0) — the thrash-driven structural break is gone, but the
  underlying commute cost the increment exists to cut is not.

**Restated kill criterion, as specified going in, applied:** stickiness in place,
`worker_turns_moving` still does not fall below ~55% (or move meaningfully at all) ⇒ the
hypothesis is **genuinely refuted**, not just under-delivering — the constraint is not which
tasks a unit is offered. Both v1p.2b's own two structural fixes (decay, escapes) and its
continued failure to move the commute number are consistent with the same reading: the fix
closed the *symptom* (thrash discarding progress) without touching the *cause* (the greedy
one-at-a-time algorithm still routinely strands a unit next to a task it has just given away).

**Both families are now closed with their own diagnosed root causes intact and confirmed, not
merely stopped one variable short.** Neither result says throughput can't be raised — both say
the fix has to live *inside* `assign()`'s own greedy matching structure, not in what tasks are
offered to which unit (zoning) or in where the herd's claimed tiles sit (compaction).

**Deferred, recorded, not implemented this pass** (ROADMAP §2 — candidates, not decisions),
renumbered now that v1p.2b's own kill criterion has resolved which one goes first:

- **③ The travel-ratio diagnostic — run this *before* anyone commits to a matching rewrite.**
  Instrument, for each completed op, the distance a unit actually travelled to reach it versus
  the distance to the nearest task that was available when it set out. Ratio near 1 ⇒ the
  commute is geometric and only territory or tour construction can touch it (the case v1p.1b's
  analytical finding — the ten claimed PASTURE slots are already the ten nearest — is consistent
  with). Ratio well above 1 ⇒ the assignment is losing real turns and ④ is justified.
  `analysis/v1o3_visit_efficiency.py` is the template. This turns the next decision from a hunch
  into a measurement, cheaply — exactly the gap v1p.2b's SMOKE just widened, since it proved
  stickiness alone does not move `worker_turns_moving` and left open *why*.
  🔴 **Criterion corrected 2026-08-14 (S3 step 1d race, §3.4):** whatever this diagnostic
  recommends, its own success is judged on **absolute `worker_turns_working` per episode with
  `crop_tile_days` held flat** (±3% of the paired baseline), never on the travel ratio or on
  `worker_turns_moving` alone — both are diagnostics that explain a result, neither is the
  target. v1p1b arm A1 is the standing counter-example: it would have "passed" a bare
  `worker_turns_moving < 55%` criterion (46,0%) while shedding 30% of `crop_tile_days` into idle.
  ✅ **RUN and RESOLVED 2026-08-15 (`analysis/v1u_travel_ratio.py`, item ④ step 1).** Not a STOP:
  greedy regret = **4,30% of total moving turns** (5.720 walk-steps over 36 eps / 133.026 moving),
  landing in the pre-registered **3–8% band ⇒ proceed to step 2 but re-scope ④ to the feed round
  only**. The regret is a *matching* loss, not eligibility (the residual v1p.2b left open): the
  **forced-walk floor is 0,963** — even a perfect per-turn matcher pays 96,3% of the commute, so
  ≤3,7% is the hard ceiling ④ can ever return. It is **concentrated**: 82,8% of the absolute regret
  is in the feed round, 86,3% in the worst 5% of turns; the max-cardinality gap is **4 tasks over
  36 episodes** (greedy already ≈ maximum, so the prize is efficiency not throughput). Method chose
  the conservative **re-match** optimum (same served set, only the unit→task pairing changes) —
  a pure-distance optimum that ignores the urgency/slack deadline ordering reads ~25,7% but is
  unachievable (it "saves" by missing FEED deadlines, the exact §3.4 anti-pattern). Report:
  `baselines/2026-08-15/item4_step1_report.md`; data: `data/derived/v1u_travel_ratio-2026-08-15.json`.
  **③ is closed; the next pass is ④ step 2 (the offline oracle), scoped to the feed round, gated
  on +$3.000/ep — a bar a 4,30% routing saving is not expected to clear, which step 2 measures
  cheaply rather than assuming here.** 🔴 **Superseded 2026-08-15/16:** the single +$3.000 bar was
  wrong (step 1's own arithmetic put the naive ceiling at ~$2.100/ep) and was replaced in the plan
  doc by a **two-legged** test — see ④'s STOP below.
- **④ Min-cost matching inside `assign()`** (Hungarian/auction replacing the greedy loop).
  ⛔ **STOPPED / refuted at step 2, 2026-08-16** — the offline oracle (`analysis/v1u_oracle.py`)
  substituted the optimal matcher and played whole episodes out; **all three arms (A/B/C) miss both
  pre-registered legs.** The routing prize is real (arm A +$4.709/ep, 23/24, `worker_turns_working`
  +5,6%) but bought by underfeeding (escapes 3→11 past the ±5 floor); the buildable arm B is
  escape-clean but only +$812 (`B/A` = 0,17); and **every arm leaves feed-round saturation at 100%
  with `animals_underfed_days` rising** — a per-turn distance optimum aims freed turns at near crops
  and defers the far feeds, so **④ moves the herd-13 blocker the wrong way.** The exact things this
  bullet flagged as unresolved decided it: it optimises a single turn while the commute is a
  cross-turn **tour** problem per-turn matching cannot solve (step 1 gap 2), and keeping urgency in
  the cost is mandatory (dropping it reappears step 1's +$6.746 pure-distance mirage). Closes ④;
  steps 3-8 not started. §3.3 STOP row + §7. Report: `baselines/2026-08-15/item4_step2_report.md`.
- **⑤ `sw_hands_target` 12/14, gated on ③/④ actually moving `worker_turns_moving`,** not on
  v1p.2b (which did not pass, so this stays dormant). It STOPPED with idle rising 25,2%→31,8%
  under global assignment — smaller effective territories from a working matching fix are
  exactly the condition that would make extra hands usable, and the top-30 profile runs 14
  hands. Re-run against whichever baseline ③/④ produces, not against the old numbers.
- §3.3's standing item — routing-distance decoupled from urgency-distance in `assign()` (the
  reverted 1.32.5 D26 shed-access fix) — remains last in line: smallest of the levers, best
  attempted once ③/④ has moved `worker_turns_moving` so its own effect is visible instead of
  buried.

---

#### S3 step 1d — the onboarding-escape defect, run as a race: Phase 0 stopped it before Phase 1, on a fifth mechanism (2026-08-14)

Full report: `baselines/2026-08-14/s3_step1d_report.md` (local). R17 landed first
(`worker_turns_working` in every gate artefact, mirroring R15). `checkpoints/v1q_base` rebuilt
(fingerprint `a22cd401aa0cf691…`, confirming it is the post-v1p2b inert state). `pytest tests/`:
**245 passed** (unchanged — the fresh-clone baseline, not a regression; 3 pre-existing
artefact-dependent failures unaffected). **No submission, no arm screened.**

This pass set out to run the deterministic ~2-escapes/episode onboarding defect (misattributed
four times: v1j, v1h′, v1o.2/v1o.3, v1p.1) as a pre-registered three-arm race (PLACE
precondition / feed-round promotion / placement rate limit) — but its own mandatory Phase 0
diagnostic (`analysis/v1q_onboarding_escape.py`, modeled on `analysis/v1i_escape_diagnostic.py`)
traced the actual mechanism directly against the real `checkpoints/v1p1b_armA1` package (its
fingerprint `e9dd026478b00ffe…` matches the ROADMAP citation exactly, so this is the package that
was actually screened, not a config reconstruction) and found **none of the anticipated branches**:

- **Not PLACE-timing infeasibility** (turns-left vs. distance) — the shed holds **zero WHEAT**
  for both escaping animals across their entire unfed window, so no amount of proximity or
  remaining turns would have helped.
- **Not lost FEED-task contention** — `_build_animal_tasks` (`agent/scheduler.py:355-451`,
  read directly, no `agent/` change) does build an unconditional FEED task every hour regardless
  of feasibility, but with zero WHEAT anywhere on the farm every unit is equally unable to
  execute it — there is no contest to lose.
- **Branch C, confirmed: an early-game cash-flow exhaustion.** Both agents place the *same*
  animals at the *same* steps (verified step-for-step identical), but candidate's own money hits
  **exactly $0.0 by hour 25** (day 1, hour 1) and stays there — 30 consecutive `wheat_shortfall`
  receipts (`agent/executor.py`'s own existing diagnostic), `wheat_bought: 0` every time — while
  baseline never once hits a shortfall in the same window and both its `BUY_PRODUCT WHEAT`
  orders succeed. A control (`checkpoints/v1p1b_armB` — `carrot_tiles` 3→1 **alone**, PASTURE
  untouched) does **not** reproduce the collapse (0 shortfalls, escapes 0-1/seed, matching its
  already-recorded milder pattern) — the severe, 100%-deterministic collapse needs arm A1's full
  combination (`carrot_tiles` reduction *and* the PASTURE reorder together). The exact engine-
  level source of the divergence (a consistent ~$40 gap appearing at the very first HIRE
  settlement, hour 1, before either agent has placed a single animal- or PASTURE-specific order)
  was **not** fully isolated within this pass — flagged honestly in the report rather than
  guessed at, since guessing is what produced the four prior misattributions.

**Per prompt.md §2.5 and ROADMAP §2's STOP protocol, Phase 0 stopped the pass here.** Arm P
(PLACE precondition), Arm F (feed-round promotion), and Arm R (placement rate limit) were **not
built** — all three target PLACE/FEED task scheduling, and the traced mechanism is upstream of
that entirely (a market/cash-flow effect, not an assignment one). Building them against an
unverified mechanism would have been exactly the pattern this pass exists to stop repeating — a
fifth misattribution instead of a fourth. Per ROADMAP §2 item 9 (added this pass): there is no
increment to propose here, only a confirmed mechanism and a new, narrower hypothesis for the next
pass — trace the hour-1 HIRE settlement directly, then test whether deferring the last 1-2 day-0
animal purchases when post-purchase cash would fall below a WHEAT-affordability threshold closes
the gap.

Two bugs were found and fixed **in the new diagnostic script itself** before its trace could be
trusted, both worth a general note for future replay-analysis scripts in this repo: (a) two
checkpoint packages both literally named `main.py` collide under `harness.play`'s filename
sanitizer if given the same `run_dir` — give each orientation/arm its own subdirectory and
consume each replay before the next `play()` call; (b) `steps[i][0]` in a recorded episode's
`env.toJSON()` is always seat 0's log entry — `observation` mirrors both farms so indexing it by
`[0]` regardless of which seat's *state* you want is fine, but `action` is logged per acting
agent and must be read from `steps[i][seat]`, not `steps[i][0]`, or a lookup for the non-zero
seat silently returns nothing.

🔴 **Corrected 2026-08-14 (S3 step 1e), two load-bearing errors in the upstream attribution above
— re-verified directly against this pass's own recorded replay, not taken on trust:**

1. **There is no hour-1 HIRE gap; the settlement is identical.** At step 1 *both* agents are at
   exactly **$2.980,0, 6 hands, `hires_today = 6`** ($3.000 − $20). The "~$40 gap at the very
   first HIRE settlement" does not exist. The $40 first appears at **step 2** and it is the
   **CARROT seed order** — candidate `BUY_SEED CARROT 1` vs baseline `BUY_SEED CARROT 3`, two
   seeds at $20 — which leaves the candidate **$40 richer** ($2.360 vs $2.320), exactly
   `carrot_tiles` 3→1 doing what it says, with no anomaly. The recommended "trace the hour-1 HIRE
   settlement" was therefore a dead end and is withdrawn.

2. **The agents do NOT buy the same animals at the same steps.** The claim above that the PLACE/
   purchase sequence is "step-for-step identical" is wrong — those are *purchase* turns and they
   differ: candidate buys 4×COW + 1×SHEEP by step 6 (bank → $260), baseline buys 4×COW spread
   later with **no early SHEEP** (bank $520 at step 8 vs candidate's $60). The **purchase schedule
   is the divergence**, not a footnote to it: the entire $460 gap is one extra early SHEEP
   purchase (+$500) minus the carrot-seed saving (−$40). `placed = 0` for both agents across this
   whole window — the animals are bought and sitting carried/in the shed, not on tiles.

**Located defect (S3 step 1e).** The mechanism is not the HIRE settlement but the v1g feed-cash
reserve at `agent/executor.py`: `reserve = (total_placed + buy_target) × wheat_price × 2` omits
`in_flight` (animals bought on earlier turns, still carried/in the shed). Spreading the purchases
across turns — which arm A1's geometry causes — bypasses the guard (reserve $50 vs a $250-260 real
liability at step 6-8, never binds). This is a defect in the **shipped** agent, reproduced as a
race in the S3 step 1e report — see `baselines/2026-08-14/s3_step1e_report.md` and §4.3 below.

---

#### S3 step 1e — the feed-cash reserve, run as a race: C2 (full-target horizon) kills the defect; C1/X refuted (2026-08-14)

Full report: `baselines/2026-08-14/s3_step1e_report.md` (local). The §1 corrections above (no
hour-1 HIRE gap; purchase schedules differ) and R18(c) landed first. Three arms, all
`agent/executor.py` + one config flag each, all inert by default, all built and checkpointed
before any screen. SMOKE 0-11 both seats, `--town-pin basket`, `--arm-role regression`,
`--metrics`, vs `checkpoints/v1q_base`. `pytest tests/` **248 passed** (+3 `test_v1r_*` guards),
3 pre-existing failures. **No submission.**

**Phase 0** (`analysis/v1r_feed_reserve.py`) pinned the arithmetic from last pass's recorded
replays: on every day-0 buy turn the code reserve is a fraction of the real liability (e.g. $104
vs $364 with 5 animals in flight, 0 placed), converging only when nothing is in flight. Gate
PASS, 3 seeds × both orientations.

**Arm 0 noise floor:** `animals_escaped` **4** (criterion-1 threshold ≤ 9). Reproducer (current
code + A1 config): **48**, −$7.711,5 — the defect holds on today's code, not just v1p1b's.

| Arm | flag (default→arm) | A1-stacked esc / $ | normal esc / $ | verdict |
|---|---|---|---|---|
| **C2** | `feed_reserve_horizon` "in_flight"→**"target"** | **0** / **+$5.907,3 IMPROVED** | 5 / −$256,8 NON_INFERIOR | ✅ **WINNER** |
| C1 | `feed_reserve_counts_in_flight` F→**T** | 48 / −$7.666,9 REGRESSED | 5 / −$256,8 NON_INFERIOR | inert on the reproducer |
| X | `feed_reserve_days` 2→**3** | 48 / −$10.112,5 REGRESSED | 14 / −$5.108,7, **plant_decay 8** | actively harmful |

**Confirmed mechanism** (≠ increment, per §2 item 9): the reserve undercounts the in-flight herd —
but *counting* the in-flight herd (C1) is not enough. C1 lands the reserve (~$260 by step 6)
exactly where the cash-stressed agent already stops on its own, so it changes nothing (48→48).
Only reserving for the **full intended herd** (C2: 10×$26×2=$520) throttles the day-0 over-buy
enough that the WHEAT pipeline never hits $0. Arm X is the size-vs-count control and it resolves
**against** size: raising `FEED_RESERVE_DAYS` while keeping the undercount does not kill the defect
and loses more (it throttles the herd's own feed pipeline; `plant_decay` breaks on normal config).

**Viable increment:** ship C2 (`checkpoints/v1r_armC2`). On the reproducer it removes all 48
escapes with the herd reaching full target (10) on baseline's own day (day 11) and ending at 10 —
**criterion 2 satisfied, not suppressed.** On the shipped config it is NON_INFERIOR (≈$0 at SMOKE,
the defect is latent at herd 10), zero structural breaks. Its value lands as the **precondition
for the §4.0 herd-13 profile** — with 13 intended animals only the target-horizon reserve tracks
the $676 liability — so C2 promotes through the full Phase-2 gate **bundled with herd 13**, not
shipped alone into the 10-herd config for no dollars.

⚠️ **A1 stays STOPPED.** C2 A1-stacked measuring +$5.907 means the escapes were the *dominant*
cost of A1's carrot→PASTURE geometry — a **new hypothesis** (A1 might be viable once fed), for a
future pass with A1's own acceptance/holdout screen, **not** a claim of this one (§5, brief §2 ⚠️).

⚠️ **Builder bug caught mid-pass** (→ R19): the first A1-stacked screens returned an identical
48/−$7711 to the unfixed reproducer because the stacked-package builder inserted the arm flag as
a *duplicate* key before the existing default (later literal wins in the dict), so the fix ran
inert. Caught by instrumenting the executor's own reserve, fixed to replace-and-assert. An
"identical to unfixed" result was treated as a red flag to trace, not a finding to report.

---

#### S3 step 2 — herd 13 on the C2 reserve: ⛔ STOPPED at SMOKE, blocked on feed logistics not cash (2026-08-15)

Full report: `baselines/2026-08-15/s3_step2_report.md` (local). Landed first (all `harness/`+`tests/`
+`.md`, no baseline invalidated): **R20** (per-product MELON/MILK/WOOL units+revenue in every gate
artefact, generic over `_V1K_REPORT_PRODUCTS`, MELON keys byte-preserved) and the **C2 dead-expression
cleanup** (`agent/executor.py`: `min(target_total, max(target_total, …))` ≡ `target_total`), the latter
proven **byte-inert** vs `checkpoints/v1r_armC2` (SMOKE 0-11 both seats basket, mean_diff 0,0, ci [0,0],
ties 12/12, every counter equal — the cleanup *and* the new planner ramp jointly a no-op). The 6/12/13
**ramp** was added to `planner.py` (`animals.ramp`, default None) with 6 `test_v1s_*` guards. `pytest`
**248 → 254**.

**Phase 0** (`analysis/v1r_feed_reserve.py --run-target13`) passed: at target 13 the C2 reserve
(~$676-728 from day 0) throttles the day-0/1 *pace* of buying (spendable → $63) but the farm's earnings
fund completion — the herd **owns** 13 (placed + in-flight) by **day 9** (H2) / **day 11** (H2R), money
never $0 at a day boundary with animals placed. **The cash half is paid.**

**The race** (SMOKE 0-11, both seats, basket, regression, vs `v1q_base`; all arms built + checkpointed
before any screen, flags verified active per R19):

| Arm | targets/ramp | escapes/24-ep | crop_tile_days | MILK $/u | mean_diff | median_bank |
|---|---|---:|---:|---:|---:|---:|
| arm 0 (v1q_base vs self) | 10, — | 4 | 13.771 | 151,3 | 0 | $55.048 |
| **B0** C2 @ herd 10 | 10, — | 5 | 13.860 | 153,1 | −256,8 NON_INFERIOR | $55.068 |
| **H1** count only | 4C+9S, — | **122** | **8.836** (−36%) | 156,1 | **−15.214** REGRESSED | $41.780 |
| **H2** profile | 9C+4S, — | 88 | 9.118 (−34%) | **139,1** | **−20.857** REGRESSED | $33.980 |
| **H2R** profile + ramp | 9C+4S, 6/12/13 | 66 | 8.838 (−36%) | **131,3** | **−19.023** REGRESSED | $31.768 |

**H1 is the decisive arm** and it fails the pre-registered criteria 3 (escapes ≤9) and 4 (crop_tile_days
≥ −3%): the cleanest possible +3-animals test — COW keeps its exact tiles, three SHEEP added to the
unclaimed distances **7,7,8**, zero reassignment, zero recomposition — escapes **122** and collapses crops
**−36%** (574 → 368/ep, *away* from the profile's 1.316). The three far animals raise herd Σdistance
**37 → 59 (+59%)** on a feed round open 100% of the day from d9. **H2/H2R confirm and add the composition
story**: both lose every one of 12 seeds; 9 COW collapses the **MILK realised price** 151 → 131-139
(§3.3's saturation, now non-mirror too); the **ramp (H2R) is not the lever** — it lowers escapes 88→66 but
recovers neither the crop collapse nor the dollars, because it addresses day-0 cash (already solved by C2)
not steady-state feed logistics.

**Confirmed mechanism ≠ viable increment (§2 item 9).** *Mechanism:* the current PASTURE tile geometry +
`assign()` routing cannot feed 13 animals — C2 pays the cash half in full, nothing pays the logistics half.
*Increment:* **none** — herd 13 is a −$15-21k/ep regression blocked on logistics, not cash. C2 stays
inert/latent at herd 10 (B0 = NON_INFERIOR ~$0), **not promoted alone**. Per the pre-registered H1 kill
condition, **deferred item ③ (travel-ratio diagnostic) is the next pass, not a herd retry**; herd 13 is
re-tested only against whatever baseline ③/④ produce. This does **not** refute the §4.0 profile — only
reaching it with our current routing and PASTURE pool. **No submission.**

---

**S4 — Freeze, submit, measure on the real ladder.**

Matching the profile is worth roughly **$63-95k and ~3.100 Elo** *if* it transfers. Submit as the
**challenger** and keep our current agent as champion until the ladder rules on it — the two active
slots must stay differentiated in exposure (§6bis), and a profile-matched agent beside our own is
the most differentiated pair we have ever had. Then run an L-series ladder diagnostic exactly as
L1/L2 did.

---

**S5 — ⛔ WITHDRAWN 2026-08-17, not stopped: its objective was mis-measured.**

S5 read: *"the named target is §4.1's finding: strawberry / wool / milk realised price, where the
measured spread is 2,75× / 3,70× / 3,49× at identical volume. Beating Hak's $105,1 strawberry and
$192,7 wool is a well-posed, falsifiable objective."* §4.1b measured that **99-100% of that spread
is the town's shop draw**. The objective was well-posed and falsifiable; it was also aimed at a
quantity no agent controls, so it is withdrawn rather than attempted and stopped.

**What survived S5 intact, and is now the premise of S6:** *"once production is a constant we
control, the mirror gate becomes meaningful again because the population genuinely is the mirror."*
§4.1b measured that too, and much more strongly than S5 assumed — **both seats sell the same basket
in the same volume in 150/150 top-ladder episodes.** S5 was right about the arena and wrong about
the prize.

---

**S6 — Win the mirror match on the 1,05× margin.** *(replaces S5; the actual goal)*

The measured situation, in one line: **at the top of the ladder two identical routes play the same
town, and the winner takes a median $2.826 out of ~$85k on a 1,04-1,06× realised-price edge over
three products.** We currently field a raw donor tape with **no market layer of our own** — it
emits its donor's sell queue verbatim — so we are not in that fight at all.

Everything below is run under §2's loop and nothing skips a rung:
**real losses → one failure mechanism → challengers → multiple teams and both seats → reject most
→ freeze the winner → re-validate on later episodes.**

#### S6 step 0 — the loss, and the one mechanism (pre-registered before any build)

*Real loss:* the T1/T2 tapes' realised premium prices, measured against the **same-town** control
§4.1b now makes available — not against other teams' towns, which is the error T2 inherited.

*The one failure mechanism, stated so it can be wrong:* **our shipped tape's market queue is frozen
at its donor's ordering, so (a) its per-turn SELL slot order is whatever the donor happened to emit,
and (b) it cannot condition on `obs.town.unlocked_shops` — the variable that moves realised price
5-18× and is redrawn every episode.** A tape is maximally exposed to both; a policy is not.

*Phase 0, mandatory and cheap:* re-measure the tapes' premium $/unit against the **same-town**
opponent, decomposed by that episode's drain. If the tapes are already at the winner's 1,05×, the
mechanism is refuted before anything is built and S6 stops here. This is the T2 lesson applied
early: T2 spent a pass on a lever whose size it never bounded first.

✅ **RUN 2026-08-17 — the C-A mechanism is REFUTED; the edge is cross-turn timing, not in-turn
order.** Report: [baselines/2026-08-17/s6_step0_report.md](baselines/2026-08-17/s6_step0_report.md).
Scripts `analysis/s6_step0_leg{1,2,3}.py`, `analysis/donor_streams.py` (R26/A2),
`harness/bench_agents/reference_ladder.py` (R25/A1); guards `tests/test_s6_step0.py` (12);
`pytest tests/` **316 passed** (3 pre-existing `test_v1h2d_*`). No `agent/` change, no submission
(R27). Three legs:

- **Leg 1 (same-town control, 32 seeds, both seats).** Against an *identical* route the two seats
  realise **1,000×** on STRAWBERRY/WOOL/MILK — queue ordering costs nothing. The seed set spanned
  the draw (**WOOL zero-drain 66/192 = 34%**, R21). The literal kill (≥1,05× on all three) did not
  fire, so by protocol the pass proceeded — but the pre-registered *mechanism* is refuted directly
  by the 1,000 self-pair. What leg 1 *did* find: cross-donor, **Valmorlee realises 1,13-1,25× on
  strawberry/wool vs the other two donors in the same town at the same volume** — a real
  market-layer edge (~$2,8k order), but from *which turns* it sells on, i.e. **cross-turn timing**,
  not in-turn order.
- **Leg 2 (C-A surface, priced on the engine's own market path).** 29-39 nominally reorderable
  turns per tape, **0 turns exceed the 10-order cap**, and the best legal within-turn permutation is
  worth **$0-18/ep** (Valmorlee $0). Mechanistic root, pinned in the tests: a SELL commits against
  its own product's inventory only, so reordering a fixed multiset is revenue-neutral. **C-A is dead
  before it is built.**
- **Leg 3 (town readability, 150 episodes).** Premium drain rank stabilises on **median day 15** =
  exactly when the `shop_evidence_min_unlocks=5` gate fires; all 8 shops only at day 24. Only
  **29% / 34% / 43%** of episodes have WOOL/MILK/STRAWBERRY's rank readable by its first-sell day
  (6/9/14). The town is **not** readable in time for the early premium sells; C-B's reliable surface
  is the back half of the season.
- **R22 ladder** (`--round-robin --shop-draw`, tapes + A1 tiers + v1u_base + meta_route + pass):
  Valmorlee **BT 3008 (56-0-0)** › Ueddy 2349 › Kaito 2182 › v1u_base 1701 › meta_route 1299 ›
  tier5 818 › tier2 651 › pass. R21 over 224 ladder eps: WOOL zero-drain 73/224 = 33%.

**Consequence for step 1 (§2 item 9 — mechanism vs increment).** *Mechanism:* in-place SELL
reordering cannot move realised premium price (self-pair 1,000, ≤$18/ep). *Where the increment
actually is:* **cross-turn sell timing** — but on our shipped tape that is behind the **T2 shed
wall** (§3.3), so it needs a *modifiable* route with shed headroom (the §4.5(b) reconstruction
path), a larger project than C-A/B/C. C-A ⛔ do not build. C-B alive but late-only and within-turn
(~$0); its only real value is as a cross-turn metering trigger, again T2-blocked on the tape. C-C
(MELON, −$27.263) is the only step-1 lever with a measured prize; sequence last.

> **The 1,05× is cross-turn sell timing, not in-turn ordering.** That is the tier-6-9 lever
> (§4.5a) and the §4.5(b) premium-lead lever, and on a verbatim tape it is behind the **T2 shed
> wall** — metering needs headroom a 98/100 tape does not have. Which is what redefines step 1.

#### S6 step 1 — 🔴 REDEFINED by step 0: own a modifiable route

The three challengers step 0 was written to bound are resolved as follows, and **none of them is
the next pass**:

- **C-A — ⛔ refuted** (§3.3 row). Not built, not revisited.
- **C-B (shop-conditioned ordering) — alive but small and late.** Within a turn it is worth ~$0
  (legs 1-2 apply to it identically — it is also a within-turn reorder). Its only non-trivial form
  is as a **cross-turn metering trigger** ("hold WOOL in a town that drew no YARN_STORE" — 34% of
  towns), which is the same shed-blocked lever. Do **not** build it on a tape.
- **C-C (MELON) — the only step-1 candidate with a measured prize** (−$27.263, §3.2(7); the only
  product with a real within-town contest, §4.1b). A *production* change, so it inherits every
  §3.3 tier-0/1 STOP, and it rides behind a route we control. Still sequenced last.

**All three roads run through the same missing asset: a route we can modify.** Our tapes are
verbatim performances — they cannot meter (T2), cannot be given headroom, and decay (§4.4#1). The
§4.5(b) reconstruction method is the way to one: **majority-vote across multiple traces of a single
strong submission** (V16-RC5 measured ~99,91% market-decision agreement across three traces of
`55440039`), plus worker-count adaptation and obstruction recovery. That yields a *measurement* of a
policy rather than a copy of one performance — better under §3.14a, graceful under drift, and it is
the only thing that unblocks the cross-turn lever leg 1 just priced at ~$2,8k scale.

**Step 1 is therefore: cost and then build the reconstruction.** Its Phase 0 is donor selection,
and it is a measurement, not a preference — see the pass brief in [prompt.md](prompt.md).

⚠️ **A constraint found while updating this section:** in the 150-episode stride sample of the
08-16 dataset, **39 distinct teams appear and Valmorlee is not among them**, while **Ueddy has 17
seats** and **27 teams have ≥3**. The donor whose calendar wins leg 1 may not have enough recent
traces to reconstruct from. Donor selection has to be measured over the **full 700**, not assumed.

✅ **RUN 2026-08-17 — Phase 0 GO; donor = ReCurSiON; route owned with proven shed headroom.** Report:
[baselines/2026-08-17/s6_step1_phase0_report.md](baselines/2026-08-17/s6_step1_phase0_report.md).
Scripts `analysis/s6_step1_phase0.py` (inventory · cluster · agreement · calendar),
`analysis/s6_step1_calendar_replay.py` (criterion 3), `analysis/s6_step1_reconstruct.py`
(build · fidelity · shed); guards `tests/test_s6_step1_phase0.py` (**10**); `pytest tests/` **326
passed** (3 pre-existing `test_v1h2d_*`; the report's "8 guards / 324 passed" was measured before the
two reconstruction guards were added — re-run this session). No `agent/` change, no submission (R27).
All 699 episodes / 1.398 seats scanned.

- **The field is one crowded meta line — prefix identity is dead as a submission test.** 1.398 live
  seats, only **4 distinct openings**, the largest **1.219 (87%)**; the 48-step opening is
  byte-identical across teams (§4.4#7 measured from the raw streams). Submissions separate on the
  **full/market** stream, not the opening. **42 teams have ≥3 traces** (criterion 1 abundant).
- **Criterion 2 (agreement) and criterion 3 (calendar) are anti-correlated.** Town-*adaptive* teams
  carry the best calendars (カワシギ 1,02-1,07× vs field) but majority-vote erases their edge
  (agreement 0,31); near-frozen teams reconstruct but sell neutral calendars. **ReCurSiON is both**:
  market agreement **0,987** (unanimity 0,954 — the V16-RC5 ~99% profile) **and** the field's best
  premium calendar.
- **🔴 The donor was nearly missed, and the lesson is logged (§3.4).** The first shortlist ranked by
  **median reward** — which is 99% town (§4.1b) — and ReCurSiON (reward 90k, unremarkable) was not in
  it. The **town-controlled recorded-episode scan across all 42 teams** surfaced it. **Select donors
  on the town-controlled ratio, never on reward.**
- **Criterion 3 gate (24 seeds, same incumbent pool, R21 spanned — WOOL zero-drain 153/432 = 35%):**
  ReCurSiON **ties** Valmorlee on STRAWBERRY (1,243 vs 1,263 — inside overlapping CIs and a frozen-
  tape under-estimate; recorded-episode 1,339) and **beats** it on **WOOL 1,221 vs 0,992** and
  **MILK 1,072 vs 0,974**. Valmorlee is a strawberry specialist; ReCurSiON's calendar is ≥ Valmorlee's
  across all three. **Gate clears.**
- **Deliverable met.** Fidelity (S1.2): the 50-trace reconstruction reproduces recorded banks to
  **median 0,12%** (11/12 within 0,26%; 1 graceful adaptive outlier) — *better* than a raw tape.
  **Shed headroom: peak 72/100, never ≥90 (0,0%)** vs the Valmorlee tape's peak 100 / 0,9% ≥90. T2's
  "sustained 98/100" was the harvest spike; ReCurSiON holds ~28 units of headroom at its fullest —
  **the cross-turn metering lever is not shed-blocked on this route.** Surface area (§3.4): a perfect
  step-2 overlay is worth **≤ +$1.912/ep** (§4.5b), now buildable because the headroom exists.
- **Ladder currency (§2.1.4) — the reconstruction sweeps the tapes 24-0-0.** SMOKE 0-11, both seats:
  recon median bank vs raw **Valmorlee tape $87.098 vs $74.186 (24-0-0, +$14.267/ep)**, vs Ueddy
  +$15.943, vs Kaito +$19.308. Partly the 08-11→08-16 field advancing (§4.4#1 decay from the other
  side) and partly that a 50-episode town-averaged route desyncs *less* in foreign towns than a single
  tape (§4.5b "degrades gracefully", now a bank margin). **This is R28's new rung above the tapes,
  produced** — and a route that would be a better submission than the current top tape *and* is
  modifiable. (No package built and no upload — R27; step 2's job.)

> **Step 1 is GO and its deliverable is done: we own a modifiable, non-decaying route (ReCurSiON)
> whose calendar ≥ the top tape's and whose shed has the headroom the tape lacked.** ~~Step 2 (the
> premium-lead overlay) is the next pass~~ — **re-sequenced: see step 1b below.** The reconstruction's
> 17,7% state-dependent market steps are the scope of its adaptive layer (worker-count / obstruction
> recovery), which stays with step 2.

##### Second read of the Phase 0 report (2026-08-17, evaluation pass — no new episodes)

**The gate verdict stands, and the method is the best in this repo to date.** Criterion 3 is measured
with the town held fixed *twice over* (recorded-episode same-town ratio, then the leg-1 instrument
against a shared incumbent pool); the all-42-team scan is the right default and it caught a
reward-biased shortlist mid-pass; the mechanism claim (agreement ⟂ calendar quality, one exception)
is stated so it could have been wrong and is supported by its own table; the fidelity, shed-headroom
and bank legs each answer a *different* question, and the report volunteers the two honest caveats
(08-11 vs 08-16 meta advance; a frozen candidate under-states an adaptive donor). **Three corrections
and one omission**, none of which touch the verdict:

1. **Guard count and test total were stale** — 10 guards, `pytest tests/` **326**, fixed above.
2. **"One submission" is asserted, not established.** The report's own headline finding kills the
   opening as a submission test (87% of the field shares it byte-for-byte), and then the provenance
   line says *"one submission (single opening fingerprint across all 50 traces)"* — the dead test.
   Measured this session from the pass's own inventory: ReCurSiON's 50 traces carry **50 distinct
   full-market fingerprints** and **16 distinct full-production** ones (largest 25). That is expected
   for a town-conditioned policy at 0,987 agreement, and the 0,12% fidelity says the majority vote
   reproduces the recorded banks either way — but **it does not rule out two near-identical active
   submissions being blended**, and a blend of two policies is not a measurement of either. Cheap
   check, deferred to 1b: 2-cluster the 50 traces on pairwise market-decision distance and confirm one
   mode, not two.
3. **R21 was discharged for criterion 3 (153/432 = 35% WOOL zero-drain) but not for the bank sweep**
   that produced the 24-0-0 headline (SMOKE 0-11, 24 eps). That is the number the next decision rests
   on, so it is the one that most needs its draw distribution printed.
4. 🔴 **The omission that re-orders the plan: the donor's own leaderboard rating.** One API call,
   never made, and it reprices everything (§1, §3.4). **ReCurSiON is #4 at 3.004,6.** Our shipped best
   is **1.621,5**. So the surface area of *shipping the reconstruction as it stands* is ~**+1.383
   rating points** — the §1 **3000** gate, reached by replication, which is precisely what §1's gate
   language ("below 2800 the job is to reproduce measured top-5 behaviour") describes. Against that,
   **step 2's entire ceiling is +$1.912/ep** (§4.5b) on top of a route we have not yet fielded. And
   the same call explains §1's five-week puzzle from a new direction: **Valmorlee is #1018 / 1.842,4**,
   so the tape at 1.617,6 was already at **88% of its donor** — there was never 1.000 points of
   headroom in it. **Building the overlay before shipping the route would spend a pass on ≤$1,9k/ep
   while a measured ~+1.383-point asset sits unfielded and its donor's field advances (§4.4#1).**

**Consequence: step 2 is deferred one pass; step 1b (below) ships the route first.** This is §3.4's
own standing pre-check applied to the pass that produced it — price the gain in rating points before
spending a pass — and it is the first time in this repo that the arithmetic has favoured *shipping*
over building.

#### S6 step 1b — ✅ SHIPPED (2026-08-17→18): reconstruction fielded as `55586926`

✅ **RUN and SHIPPED.** Both pre-registered gate kills resolved (neither fired); the ReCurSiON
majority-vote reconstruction was packaged, gated and uploaded as **`55586926`** (public **600,0**,
validated `COMPLETE`, converging). **Valmorlee `55548339` evicted per the user's decision**; active
pair now **{Ueddy `55575305` (1.371,1), ReCurSiON `55586926`}**. Report:
[baselines/2026-08-17/s6_step1b_report.md](../baselines/2026-08-17/s6_step1b_report.md). Scripts
`analysis/s6_step1b_cluster.py`, `analysis/build_reconstruction_submission.py`,
`analysis/s6_step1b_gate.py`; tracked evidence `gates/s6_step1b_gate_{dev,holdout}/results.json`;
`pytest tests/` **326 passed**.

- **Item 1 — kill (ii) does not fire (ONE MODE).** 2-medoid on market-decision distance is a
  degenerate 48/2 peel of two low-reward adaptive-degradation outliers; **majority-vote invariance
  1,000** (the 50-vote is byte-identical to the dominant-48 vote), dominant-48 silhouette 0,153 (no
  internal structure). The single majority vote measures the dominant policy's mode.
- **Item 4 — kill (i) does not fire.** vs the raw Valmorlee tape (incumbent): DEV 48-0 **+$15.276
  IMPROVED**; **unpinned holdout 100-147 both seats 48-0 +$12.212 IMPROVED**, median $88.463. Priced
  loss recon $1.500/ep < tape $3.836/ep (`priced_loss_delta $0`); **zero escapes / zero shed overflow**
  vs the tape's 107/680; crop tile-days 1316 vs 1236. R21 draw spanned for every seed set (WOOL
  15-25% zero-drain). `GO=False` is the **T1-precedent structural N/A for a code-less tape**
  (`plant_decay ~15/ep`, *equal* to the incumbent tape's ~14,9/ep) — the substantive §2.1.4 gate is
  passed ≫ floor, which is what kill (i) is defined on.
- **Item 5 — §6bis all green.** G12, timing both seats (max×3<1s), G13, mirror `clean=True`, size,
  pytest 326.
- **Kill (iii) — OPEN, and its instrument was mis-specified.** ~~pending (~1 day)~~ The criterion was
  written against **wall-clock** ("~1 day"), and a rating is a function of **episodes played**, not
  hours. Read 2026-08-17 22:51 UTC — **22 minutes** after the upload — `55586926` is at **1.125,9 on 7
  episodes** against Ueddy's **1.375,9 on 72**. Comparing those two numbers today would "fire" kill
  (iii) on an artefact of episode count, which would have been a serious mis-read of a submission that
  has gained **+526 points in 7 episodes**. **Restated criterion:** record **(episode count, score)
  pairs for both submissions on the same reads** until `55586926` has **≥72 episodes** — Ueddy's count
  — and compare there; a converged-looking early number is not evidence either way. Does **not** carry
  to step 2 (which would evict Ueddy — separate decision, §6bis).

⚠️ **Two loose ends from this pass, both cheap, neither affecting the verdict.**
**(a) Item 3's BT number was never produced.** The report's item 3 carries an unfilled
`<!-- BT_LADDER_RESULT -->` placeholder and no BT artefact exists on disk; what it actually reports is a
**challenger-only 24-0-0 sweep with margins** (Valmorlee +17.054, Ueddy +15.117, Kaito +21.194,
`meta_route` +97.730, tiers +99k-170k). That sweep is real and is the substance, but **R28's rung is a
*Bradley-Terry rating*, and it is still unmeasured** — `--round-robin` is what makes the graph
connected, and it was either not run or not captured. Carry it into the next pass; it is one command.
**(b) No `memory.md` entry was written** for the pass; added retroactively in the evaluation session
below it. **(c) The report's "Gate evidence (tracked)" line is false** — `.gitignore:10` ignores
`gates/` wholesale, so `gates/s6_step1b_gate_{dev,holdout}/results.json` exist **only on this machine**.
That is the **R14 failure repeating one directory over**: the evidence for the largest shipping decision
in this repo's history is not in git. See **R34** — the numbers themselves are verified (I re-read both
files this session and they match the report exactly), but verified-by-me is not the same as
recoverable.

*The whole increment already existed.* Nothing was invented: 1b took the artefact step 1 built and
put it through §2.1.3's protocol and §6bis's checklist, because an unfielded route earns zero.

#### S6 step 2a — ⛔ STOPPED at Phase 0 (2026-08-18): the loss is WHEAT, worth ≤$599/ep, $0 of it free → step 2b leads

> ⛔ **Phase 0 STOPPED the pass; kill (i) fired. The premise was wrong and the measurement says so.**
> Decomposed on 48 episode-seats (recon vs the incumbent Valmorlee tape, both seats, unpinned), the
> `plant_decay_units_lost` 15/ep and `unexpected_weeds_lost` 5/ep are **100% WHEAT and the same 5
> tiles** — not strawberry. Wheat is non-ongoing but the engine stamps it with a `max_lifespan_step`
> at plant time ([:224](engine_reference/kaggriculture.py#L224)); the fixed route misses the
> late-season harvest (days 21/25/28) in a foreign town, the tile bleeds its 3 units and weeds. **The
> two counters are one event counted twice.** Honest recoverable ceiling **$599/ep** (14,94 units ×
> $40/u, itself high — the marginal wheat clears below the 443-unit average, §3.3), *not* the
> ~$2.800–3.100 the strawberry assumption predicted. And the **FREE (non-displacing) half is $0/ep
> on-tile** (no idle unit is ever on a loss tile — §3.3's wall, now confirmed on a tape) **to $241/ep
> reachable** (over-generous, needs a closed-loop redirect that desyncs the tape) — both **< the
> $500/ep gate**. Second, independent kill: the full $599/ep is **+2,4 rating points / 0,09% of the
> ~2.567 gap** (§3.4). The premium-lead overlay (step 2b, §4.5b's +$1.911,9/ep for a route that owns
> its calendar) is the larger, cleaner lever after all — **it leads the queue.** The wheat channel is
> on the shelf (§3.3 idiom), never worth a pass on a tape at this rating scale. Report:
> `baselines/2026-08-18/s6_step2a_phase0_report.md`; script `analysis/s6_step2a_phase0.py`.
>
> **Loose ends closed:** R33/R28 — the step-1b round-robin ladder (run after its report) rates the
> reconstruction **BT 3.317, #1 of 13, 48-0-0, 24-0/24-0 per seat**, above all three tapes; the
> `<!-- BT_LADDER_RESULT -->` placeholder is now filled. **Kill (iii), correctly instrumented
> (episodes not wall-clock):** 2026-08-18 recon `55586926` **1.753,7 on 16 eps** vs Ueddy `55575305`
> **1.380,7 on 72 eps** — recon is *above* the incumbent tape at ¼ the episodes, so the method is
> confirmed on the ladder, not refuted. ~~the fair ≥72-episode read is days out~~ ✅ **CLOSED a few
> hours later: 2026-08-18 09:19 UTC the recon reads 1.915,8 on 85 episodes against Ueddy's 1.392,9 on
> 78 — comparable play behind each number, same read, +523. Kill (iii) does not fire.** The plateau
> call was right (the last 70 episodes bought +2,6/ep, not +76), the "days out" estimate was not.

🔴 **The measurement that re-points step 2b, available only after this report was written (§1).** With
the recon converged near ~1,9-2,0k, the transfer ratio can finally be read — and it is the opposite of
what §4.5(b) predicted:

| route | our ladder score | its donor, same-day | transfer |
|---|---:|---:|---:|
| Valmorlee **verbatim tape** | 1.599,1 | 1.842,4 | **87%** |
| ReCurSiON **majority-vote reconstruction** | 1.915,8 | 2.985,6 | **64%** |

**The vote left ~1.070 rating points of a #5 donor on the table, and it transfers *worse* than a
verbatim tape.** The prime suspect is exactly what the vote erased — the **127/719 (17,7%)
state-dependent market steps**, i.e. the town-conditioning that made the donor #5. §4.5(b)'s "degrades
gracefully" was measured as a *bank margin against three fixed tapes*; against 5.123 adaptive teams, a
route averaged over 50 towns may be optimal in none. **Unproven, and it is the next pass's question.**

⚠️ **One defect in the artefact, not in the reasoning (R35).** `data/derived/s6_step2a_phase0.json`
still carries the **pre-correction** summary — `gate_value: 840,5` (the `reachable` tier *with* the
double-counting $300 proxy) and **`gate_clears: true`** — while the corrected script prints
`gate $241/ep (on_tile $0) ⇒ STOP → kill (i) FIRES` and writes different keys entirely
(`gate_value_reachable_unitonly`, `gate_value_ontile`). Both were re-run this session: **the script's
verdict is right and the artefact on disk contradicts it**, so anyone grepping the JSON later reads a
GO. `--report-only` recomputes the print but does not rewrite the stale summary. **Fix: re-run the
script in full.** Same class as R12/R19 — an artefact keyed to a version other than the one reported.

<details><summary>Original step-2a brief (pre-Phase-0, superseded by the STOP above)</summary>

🔴 **Read out of step 1b's own gate artefacts this session, and it re-orders step 2.** The holdout
artefact (`gates/s6_step1b_gate_holdout/results.json`, 96 episodes, unpinned, both seats) contains a
loss decomposition nobody summed:

| loss, per episode | reconstruction | incumbent tape | priced at | ≈ $/ep |
|---|---:|---:|---|---:|
| `unexpected_weeds_lost` | **5,0 tiles** | 5,5 | $300/tile (§2.1.5) | **$1.500** |
| `plant_decay_units_lost` | **15,0 units** | 14,9 | *unpriced* — structural counter | **~$1.300-1.600** ⚠️ |
| `animals_escaped` | 0 | 1,1 | $1.000 | $0 |
| `shed_overflow_burnt` | 0 | 7,1 | $150/unit | $0 |

The first row **is** the whole of the reconstruction's `priced_loss_a` ($1.500/ep, exactly 5,0 × $300).
The second is 15 units/ep of crop passing its max-yield tick uncollected (D6) and has **never been
priced** — the ⚠️ figure assumes strawberry at the route's realised $90-105/u and **must be decomposed
by product, not assumed**. Together they are of order **$2,8-3,1k/ep**, against the premium-lead
overlay's entire ceiling of **+$1.912/ep** (§4.5b). And they are near-identical on the incumbent tape,
so this is **inherent to open-loop replay in a foreign town** — a loss the whole tape line has been
paying since 08-16 while every pass looked at the market layer.

**The one failure mechanism, stated so it can be wrong: the reconstruction is blind to its own farm
state.** It plays a stream calibrated to the donor's town, so when *this* town's weeds spawn on a
planted tile the stream does not clear, or a crop passes its max-yield tick the stream does not
harvest, the loss is taken silently. §4.5(b)'s method prescribes exactly this layer — "worker-count
adaptation and obstruction recovery" — and step 1 deferred it as an afterthought to the overlay.
**Measured, it is the larger lever of the two**, it is *own-farm* (no opponent interaction, and
critically **no town confounder** — §4.1b's 99% does not apply to a weed on our own tile), and it is
the cleanest increment shape this repo has had available.

**Why it might still be worth nothing, which is the point (§3.4).** A repair inserts an action the
route did not emit. If a unit is **idle** at that step it is nearly free; if it **displaces** a route
action, §3.3's crop/animal equilibrium — five independent mechanisms, same wall — says it loses more
than it earns. *That* is the surface area to bound on paper first, and it is the whole risk of the pass:
**if fewer than ~$500/ep of the events above coincide with an idle unit-turn, the lever does not exist
and the pass goes straight to step 2b.** No episodes are needed to find out; the recorded replays and
the reconstruction's own stream answer it.

**And the selection between 2a and 2b should be made on our own live losses, not on a prior.** We now
have something this repo has never had at this quality: **our own shipped route's public episodes**, in
real towns, against rating-sorted opponents, both seats — the §3.2 L1/L2 diagnostic, with §4.1b's
same-town control available inside every episode. §4.5(b)'s +$1.911,9/ep is *V16-RC5's* number for
*its* route; ours is unmeasured. Read our own losses first.

> **Step 2b (the premium-lead overlay) keeps its place in the queue and its own Phase 0 and kill** — it
> is not withdrawn, it is *second*, because the thing ahead of it is bigger, cleaner and cheaper to
> bound. If 2a's Phase-0 bound comes in under $500/ep, 2b becomes the next pass instead.

**Surface area, stated first (§3.4):** the donor scores **3.004,6 (#4)**; a faithful reconstruction
of it cannot exceed that and should approach it (fidelity 0,12%, calendar ≥ Valmorlee's, 24-0-0 vs
all three tapes). Floor: it must at least beat the **1.842,4** donor-ceiling class our current tape
belongs to. **Anything in 1.9k-3.0k is a result; below ~1.6k it has not beaten the thing it replaces.**

**Kill, pre-registered.** (i) The reconstruction fails the §2.1.3 gate — DEV acceptance against the
**non-mirror** bench or the **unpinned** holdout 100-147 — ⇒ do not ship, and the tape stays the
product (the standing kill from §4.5's surface-area block). (ii) The trace population turns out to be
**two** submissions blended (correction 2 above) ⇒ re-vote per cluster and re-gate the larger one
before anything is packaged. (iii) It ships and, once converged (~1 day, per T1), reads **below the
Ueddy tape's live score** ⇒ the reconstruction method is refuted on the ladder, not locally, and S6
returns to the tape line with that measurement in hand.

Order of work, cheapest-first:

1. **One submission or two** — the 2-cluster check on ReCurSiON's 50 traces (correction 2). Paper only.
2. **Package** the majority-vote route as a self-contained gitignored `main.py` under
   `baselines/2026-08-17/tape_submissions/`, exactly as T1/T2 were, with full provenance (team,
   episode ids, seats, action-stream sha256) — §4.2's three mandatory conditions apply unchanged.
   This also discharges **R28**: a file path is what `harness.cli ladder` needs.
3. **BT number over the graded bench** (§4.5 A1 tiers 0-5 + the three tapes + `v1u_base` +
   `meta_route`), `--round-robin --shop-draw`, per-seat split reported (§2.1.1). The new rung R28 asked
   for, now measurable.
4. **Gate it properly**: SMOKE 0-11 → **DEV acceptance vs the non-mirror bench** → **unpinned holdout
   100-147**, with **R21's realised-drain distribution printed for every seed set** (correction 3) and
   every non-zero priced counter declared per R13/§2.1.5.
5. **§6bis pre-upload checklist** — G12 loader contract, cold-process timing both seats, G13
   determinism, mirror smoke `clean=True`, size, `pytest` green.
6. ✅ **Eviction decided by the user, 2026-08-17: accept losing Valmorlee (1.614,0) and ship** (R27
   satisfied — see §6bis for the full terms). Rationale on record: only the latest 2 play the
   post-deadline Bradley-Terry, the deadline is ~6 weeks out, Valmorlee's own donor is #1018 at 1.842,4
   so its ceiling is known and low, and the resulting pair {Ueddy tape, ReCurSiON} is differentiated in
   *premium mix* — Ueddy the milk specialist, ReCurSiON broad across all three (§6bis's differentiation
   rule, otherwise unsatisfiable now that 87% of the field shares one production line). ⚠️ **The
   authorisation is conditional on the gate**: kills (i) and (ii) below still stop the upload, and it
   does **not** carry to step 2's upload, which evicts the Ueddy tape and needs its own decision.
7. **Step 4 becomes runnable the same week** — the 08-18+ daily datasets are the strictly-later
   confirmation this route was screened before, and §4.4#1 makes it the test that matters most.

*Then* step 2 (the premium-lead overlay + the adaptive layer for the 17,7% state-dependent market
steps), against the shipped reconstruction as its baseline — a cleaner A/B than it would have had here.

> ⛔ **C-A REFUTED at step 0 (2026-08-17). Do not build it.** In-place within-turn reordering of a
> fixed sell multiset is revenue-neutral (independent per-product inventory pools; the 10-order cap
> never binds on these routes): self-pair ratio **1,000**, best-permutation upper bound **$0-18/ep**
> against the $2.826 gap. The tier-7↔8↔9 separation the *Prior* below cites is **cross-turn metering
> and sell-timing**, which C-A explicitly forbids (no overnight hold) — so the prior was mis-mapped
> onto the wrong lever. The real edge is cross-turn timing (leg 1: Valmorlee 1,13-1,25× on the same
> route class), and on our tape it is behind the T2 shed wall. See the step-0 results block above.

**C-A — the Cleo rule: in-place sell reordering.** Reorder SELL orders **within the slots the
donor already used for selling**; never move a sell into a slot holding a purchase; never change
quantities; never hold inventory overnight. This is the only design that survives **both** of T2's
own root causes — the shed runs at 98/100 so we add zero inventory, and sells fund same-turn buys
so we cross no slot boundary. It is also the exact lesson the reference ladder's tier-9 agent is
built to teach (§4.5), and its authored A/B partners (tiers 7/8) bracket how much it is worth.
*Prior:* the reference league measures tier 7↔8↔9 — identical production, market layer only —
separating by **$164 to $2.617/ep**, i.e. the same order as the $2.826 median gap.

**C-B — shop-conditioned premium ordering.** Order the premium products inside the turn by *this
town's* measured drain, using `agent/demand.py::shop_buyer_counts` and `npc_daily_demand` — both
already built, already gated, already used by `checkpoints/v1i`. In a 0-YARN_STORE town (34% of
towns) WOOL goes last; in a 7-instance strawberry town STRAWBERRY goes first. **This is the one
thing a fixed tape structurally cannot do**, which is what makes it the right first original
increment rather than a tuning knob.

> ⚠️ **Scoped down at step 0 (2026-08-17).** Leg 3 measured the town unreadable in time for the
> early premium sells (premium rank stable only from median day 15 = the `shop_evidence_min_unlocks`
> gate; WOOL/MILK/STRAWBERRY readable-in-time in only 29%/34%/43% of episodes; all 8 shops at day
> 24). And leg 1/leg 2 showed *within-turn* ordering is worth ~$0. So C-B's within-turn form is dead
> like C-A; its only non-trivial value is as a **cross-turn metering trigger** on the back half of
> the season — which hits the same T2 shed wall on our tape. Not a clean step-1 increment on the
> tape; revisit only behind a route with shed headroom.

**C-C — MELON entry.** The only product with a within-town contest (§4.1b), zero shop buyers in
150/150 towns, flat ~$144, and our largest single revenue hole. This is a **production** change,
not a market one, so it does **not** ride on the tape — it goes behind whatever route we control,
and it inherits every §3.3 STOP about adding tier-0/1 work. Sequenced last, deliberately.

</details>

#### S6 step 2b — 🟢 THE NEXT PASS, and its Phase 0 is the donor gap, not the overlay

**The overlay finally leads the queue — and its surface area has never been measured on *our* route,
while the ladder has just handed us a number two orders of magnitude larger.** §4.5(b)'s
**+$1.911,9/ep, 60-0-0** is *V16-RC5's* premium-lead layer against *V16-RC5's* core; divided by §3.4's
$253/ep that is **~+7,6 rating points** (more if it changes *which* episodes we win — §3.4's amendment
— but that is the honest starting estimate). Against it: **the ~1.070-point donor gap above.** §3.4's
standing pre-check — *divide the plausible gain by $253/ep and compare to the gap **before** scoping* —
therefore binds: **decompose the gap first.** That decomposition is also what sizes the overlay for our
route, so this is not a deferral of 2b; **it is 2b's Phase 0, done properly.**

*The candidate mechanism, stated so it can be wrong:* **the majority vote erased the town-conditioning
that made the donor #5.** The vote replaces each of the 17,7% state-dependent market steps with the
modal action — optimal in the average town, in no particular one.

*The refutation, and it is cheap (§3.4: bound the lever before building it).* We hold **85 of our own
public episodes** — the shipped route, real towns, both seats, a rating-sorted pool — plus the donor's
50 recorded traces and the reconstruction's own disagreement set. **If our live realised premium $/u
already matches the donor's recorded same-town ratios** (STRAWBERRY 1,339 recorded / 1,243
frozen-replay), then the calendar transferred, the overlay's lever is small on our route too, and the
~1.070 points are somewhere else — production desync, tier-0 loss, or the opponent population. **That
kills the overlay before it is built, which is the entire point of running this first:** C-A died in an
afternoon this way; T2 spent a full pass because it did not.

#### S6 step 2 — the bench (this is the part §2 says we have been getting wrong)

Every arm is scored against a bench that **retains earlier meta generations**, not only the current
top-30. **Decided by the user 2026-08-17: adopt A1 + A2, skip A3.** Concretely, closing **R4**:

- **A1 — tiers 0-5 of the reference-agent ladder** (§4.5): MIT, original work, documented, graded
  from a do-nothing floor ($3.000) to a livestock build ($46.211), all sharing a byte-identical
  scheduler so every gap between them is an *economic* decision. Cheap regression opponents that
  fail **loudly and differently from each other**. *Ceiling acknowledged:* they top out at $46k
  against our tape's $118k, so they catch catastrophic breaks — they do not spar.
- **A2 — our own three extracted donor tapes** (Valmorlee `91456307` · Ueddy `90999409` · Kaito
  `90891564`): these already **are** the shared meta line (§4.1b measured 150/150 top episodes
  selling one basket; the reference `NOTICE` counts 104 teams on identical sequences). They need
  **no new licence**, they are already on disk and gitignored, and as **fixed-production** opponents
  they give the cleanest possible A/B for a market-layer change — the production is held constant by
  construction, so any difference *is* our layer. This is the sparring partner A1 cannot be.
- **⛔ A3 — reference tiers 6-9: skipped by decision.** Their base85 `_TRACE` field plan is
  explicitly outside the MIT grant, and A2 reproduces the same fight from material we already hold.
  Their published separation ($164-$2.617/ep between identical-production agents) is retained as a
  **calibration figure**, which is free to cite and needs none of their code.
- **our own frozen checkpoints as earlier metas** — `v1h`, `v1i`, `v1o_2`, `v1u_base`. We have been
  deleting this signal by always gating `v_n` against `v_{n-1}`.
- **`meta_route`** and the two earlier-meta notebook references already retained on purpose
  (`v13-r3`, `177-180 v21.1` — Appendix A).
- **both seats, always** (§2.1.1), and **`--town-pin basket`** for anything touching occupancy.

*Open action:* ✅ **done 2026-08-17 (R25).** The six tier-0-5 `.py` are fetched into the
**gitignored** `harness/bench_agents/reference/`; `harness/bench_agents/reference_ladder.py`
(committed, no competition data) resolves them by tier/slug/name. A2 is `analysis/donor_streams.py`
(R26). Both are exercised by the S6-step-0 R22 ladder — Valmorlee tape BT 3008 sweeps the graded
bench (tiers 0-5 + tapes + v1u_base + meta_route + pass).

⚠️ **The town is now a known confounder in every market-only A/B.** §2.1.2 classifies a
market-order change as *"market-only ⇒ a fixed seed is a genuine controlled experiment"*. That
still holds for occupancy, but §4.1b shows a fixed seed also fixes the **shop draw** — so a
market-only screen on few seeds can be measuring one town. **Any S6 arm reports its seed set's
realised drain distribution alongside its dollars**, and the acceptance arm needs enough seeds to
span the draw (a 0-YARN_STORE town occurs 34% of the time and is a different game).

#### S6 step 3 — score it in the ladder's own currency

Add **Bradley-Terry** to `harness/` and report it beside `median_bank` / W-L / `mean_diff`. The
competition ranks by BT over post-deadline episodes (§1); we have never once computed it locally,
which is a large part of why §1's central puzzle — *"measured local wins that convert into ~nothing
on the ladder"* — has stayed open. A win against tier 2 and a win against tier 9 are the same row
in `results.json` today and must stop being so. This does **not** replace §2.1.4's three numbers;
it sits beside them and is the one that is comparable to the thing we are actually judged on.

✅ **BUILT AND RUN, 2026-08-17** — [harness/ladder.py](harness/ladder.py),
`python -m harness.cli ladder`, 11 guards (**R22**). Two runs, and both paid immediately:

**(i) Round-robin over our own lineage** (seeds 0-1, both seats, `--round-robin`) reproduces our
development history as a clean monotone ladder, which is the validation:

| # | agent | BT | record | mean margin |
|---:|---|---:|---|---:|
| 1 | live `main.py` (v1o.2) | **2556** | 20-0-0 | $35.848 |
| 2 | v1i | 2063 | 16-4-0 | $28.714 |
| 3 | v1h | 1675 | 12-8-0 | **$28.749** |
| 4 | v1e | 1325 | 8-12-0 | −$214 |
| 5 | `starter` | 937 | 4-16-0 | −$43.870 |
| 6 | `pass` | 444 | 0-20-0 | −$49.227 |

Note rows 2-3: **v1h has the higher mean margin and the lower BT rating.** That is the whole
point — BT scores *who* you beat, `mean_margin` scores *by how much*, and the two disagree on real
data from our own repo.

🔴 **(ii) And it localises §1's central puzzle rather than solving it.** Our local ladder ranks
**v1i above v1h**; the real ladder scored **v1h 652,5 and v1i 593,8**. (Read a day apart, so §1's
decay caveat applies and this is suggestive, not decisive — but they are ordered the *opposite*
way, not merely close.) Since the BT fit is now pinned by tests, the remaining suspect is the one
S6 step 2 names: **the opponent population**. A bench made of our own lineage plus `meta_route`
can be measured perfectly and still rank agents in an order the ladder reverses. This is the
strongest evidence yet that the bench, not the metric, is what has been wrong.

⚠️ **R21 fired on the very first run**, which is what it was added for. Over seeds 0-3 (56
episodes) the sampled shop draw was **WOOL zero-drain in 27/56 episodes — 48%, against the
population's 34%**. A small-seed screen on those seeds is materially biased toward wool-dead
towns, and any wool-side result from it would have been a statement about the seed set. MILK
ranged 0-7 u/tick, STRAWBERRY 1-7.

*Gate (unchanged protocol, §2.1.3-5):* SMOKE 0-11 → DEV acceptance against the **non-mirror**
bench → unpinned holdout 100-147 → immutable checkpoint.
*Kill, pre-registered per arm:* an arm that does not move realised premium $/unit **against the
same-town control** has missed the only thing it was built for — stop and record, do not tune.

#### S6 step 4 — re-validate on strictly later episodes

The chronological protocol (§4.3 S1), applied to ourselves: **fit and screen on episodes up to and
including 2026-08-16; confirm on the daily datasets from 2026-08-18 onward.** §4.4#1 says a frozen
policy decays (87/90 → 14/27 measured), and §1 has measured our own frozen agent losing 632,2 →
600,2 with no code change. An arm that only wins on the meta it was screened against is exactly
what this step exists to catch.

### 4.4 Risks in this plan, stated up front

1. **An open-loop policy decays.** The v27 notebook measured its own frozen v26 going from
   **87/90 wins** to **14/27** against a newer opponent distribution. Whatever is frozen is a
   depreciating asset, and the final Bradley-Terry runs on a meta we cannot see. This is the
   strongest argument for S5 being the point of the exercise rather than a nice-to-have — and the
   main engineering reason §4.2 prefers a parameterised profile over a fixed tape.
2. **A ceiling around 3.130.** The v23-fork cluster plateaued at 3.117-3.131 while private agents
   sat above it. Replication should clear the **2800** gate comfortably and approach **3000**; it
   will not by itself reach #1. That is consistent with the goal — ten *equal* prizes make stable
   top-10 the target.
3. **Both seats.** Donor streams are recorded from one seat, and the top farms run the same policy
   in both. Our seat-asymmetry rule (§2.1.1) applies unchanged: everything is measured both ways.
4. **S3 step 1 is the hard part, and we have failed at it before.** Reaching the §4.0 profile means
   fixing the three things L2 measured: 27,8% idle unit-turns, a hire gate that never reaches 11+
   hands, and a farm that shuts down at d17. Our previous attempts at scale (v1j, v1k, v1l) all
   stopped. What is different now is that we have the **target** — a converged, current-engine
   profile from 120 seats — rather than a guess, and the herd **ramp** explains why the 12-14 animal
   screen failed. That is a real change in information, but it is not a guarantee.
5. **Legal exposure lands at the prize stage, not during development** — §4.2. The profile path
   removes it; the tape path defers it to a conversation with the Sponsor if we finish top-10.
6. **Timing/size is a non-issue either way.** A 719-entry table is trivially fast; a parameterised
   planner already fits the 1s budget with margin.

7. 🔴 **Added 2026-08-17 — our two tapes are inside the shared meta line, not outside it.** §4.1b
   measured both seats of 150/150 top episodes selling the same basket in the same volume, and the
   reference-agents `NOTICE` reports identical 712-turn sequences across **104 distinct teams**
   over 530 replays. So the Valmorlee and Ueddy tapes are not two independent assets — they are
   two samples of one crowded route, and a large share of their opponents play **the same
   trajectory**. This weakens the §6bis differentiation argument for the current active pair
   (differentiated from each other, but both inside the modal line) and *raises* the value of S6's
   C-B, which is differentiation the crowd structurally cannot copy from a replay.

### 4.5 New sources read 2026-08-17, and what each is good for

Two competitor notebooks were read this session. **§2 item 8 applies unchanged: their markdown,
tables and printed statistics are read freely as evidence; the `main.py` / `submission.tar.gz`
blobs they embed are not opened, decompressed or executed.** Neither was. Both were extracted
prose-only to [docs/source/notebooks/](docs/source/notebooks) and the `.ipynb` files were then
**deleted, never committed** — see the handling rule at the end of Appendix A, which is now
standing policy for any competitor notebook.

**One thing they got wrong that we already had right**, worth recording because it is the only
place their engine reading and ours disagree: the rank-your-agent checklist reports *"the rules say
`CARE` banks +2 per day; the engine adds +1"* as a discovery. That is our **D1**, tested since the
first engine pass (`test_care_bonus_plus_one_not_two`). `docs/reference/engine_deltas.md` is ahead
of the public material here, not behind it.

**(a) `kaggriculture-rank-your-agent.ipynb`** (Rayk Kretzschmar). A Bradley-Terry ranking harness
over a published **[Kaggriculture Reference Agents](https://www.kaggle.com/datasets/raykkretzschmar/kaggriculture-reference-agents)**
dataset — ten documented agents in graded tiers. Only its `LICENSE`, `NOTICE` and `*.csv` tables
were pulled (statistics, §2.8); **no `.py` agent file was downloaded.** What it gives us:

| Band | Agents | Bank | What it isolates |
|---|---|---:|---|
| **tiers 0-5** | Fallow Finn → Rancher Rita | $3.000 → $46.211 | Authored from scratch, **byte-identical scheduler**, differing only in a `POLICY` dict ⇒ every gap is an *economic* decision. **MIT, original work of the author** |
| **tiers 6-9** | Broker Bea, Ledger Lena, Slotter Silas, Closer Cleo | $148.546 → $164.540 | The **same** shared meta field plan, differing **only in the market layer**. Their spread is the S6 target, measured |

Three things in it are load-bearing for us:

1. **The tier 6-9 band is a measured price on S6.** Identical production, market layer only,
   separating by **$164 → $2.617/ep** — the same order as §4.1b's $2.826 median gap.
2. **Closer Cleo's lesson is our own T2 STOP, with the fix attached:** *"Sells fund the buys that
   follow them in the same queue; hoist the sells out of their original slots and a
   `BUY_PRODUCT WHEAT` later in the turn fails on a near-zero balance, animals go unfed."* We
   measured that mechanism independently in T2's Phase 0 (cash floor ≈$6; escapes 0→11) and then
   stopped. Cleo is the design that respects it — **S6's C-A**.
3. **An independent correction to the price model** — *"`units_until_price_floor` measures a
   **static** market … what decides your realised price is how many shops demand your product."*
   This is the same mechanism §4.1b measured from replays, arrived at independently. Its own shop
   table has an arithmetic slip we should not inherit: it prices CARROT at 12 units/day, missing
   that PET_CAFE is a single-product shop and therefore consumes at **multiplier 2** (correct: 18).
   Our numbers come from the engine and the tests pin them.

⚠️ **Licensing is a live decision, not settled here.** `NOTICE` grants **MIT** over the `.py`
files, and states plainly that **tiers 0-5 are the author's original work and MIT in full**, while
for **tiers 6-9 the base85 `_TRACE` field plan is explicitly not covered** — it is the shared public
meta line, which the author declines to claim. Recommendation: **adopt tiers 0-5 as bench opponents**
(clean, MIT, and exactly the graded earlier-generation regression ladder §2 and R4 have been asking
for); treat **tiers 6-9 as a separate call by the user**, because their uncovered `_TRACE` carries
the identical §3.14a question the user already resolved for the tape.

**(b) `kaggriculture-3000-socre.ipynb`** (HarvestForge-X / V16-RC5). Markdown and result tables
only. Two things worth carrying:

1. **A route-reconstruction method strictly better than our verbatim tape.** It compares **three**
   public traces of the *same* submission (`55440039`, eps 92165990 / 92185587 / 92223213), finds
   the production sequence near-identical and the **market decisions agreeing at ~99,91%** of
   decision points, and takes the **per-decision majority vote** as an executable policy — then adds
   worker-count adaptation and an obstruction-recovery step. That is a *measurement* of a policy
   rather than a copy of one performance: it degrades gracefully where a tape desyncs (§4.4#1), and
   it is the natural upgrade path for §4.2's tape if S6 needs a route it can modify.
2. **A price on the market overlay when you own the route:** its premium-lead layer beats its own
   reconstructed production core **60-0-0, mean margin +$1.911,9, worst margin +$68**. A small,
   *perfectly consistent* edge — which is the shape §3.4's amended rating note says converts well.
   Its design is also the exact one T2 found inert on a tape ("augment" mode, a literal no-op
   because the tape held zero inventory), confirming that **T2's STOP was donor-specific, not a
   property of the lever.**

⚠️ Its census reads **8 COW + 4 SHEEP**, and the reference ladder's meta line reads **8C + 5S**,
against our §4.0's **9C + 4S** from 120 seats. Three independent reads inside ±1 animal: treat the
herd row as **8-9 COW / 4-5 SHEEP**, not as a pinned constant.

## 5. Phase 2 — gated on 2800+, decide later, do not build now

Not started until the ladder shows **2800+**. Recorded now only so the decision is made against
stated criteria rather than momentum.

**Branch (a) — continued heuristic refinement.** Incremental, uses the existing harness, zero
runtime risk. **Superseded in part:** §4.3 makes the route-copy programme the primary path, and
S5 is where heuristic refinement now lives. This branch survives as the fallback if S2 kills
copying.

**Branch (b) — RL trained continuously on a remote Linux box (user-provided).** Not chosen, not
rejected. Open questions to answer *before* committing, none of which need answering today:

- *Throughput.* Measured ~3s per 720-step episode ⇒ ~240 env-steps/s/core. The bottleneck is the
  Python engine (CPU), so the value of the remote box is **cores, not the GPU**. A vectorised
  reimplementation would be 2-4 weeks plus a permanent divergence risk against
  `tests/test_engine_facts.py`.
- *Self-play data format.* Undecided. Must be defined so it never becomes a channel for trajectory
  data into the submission.
- *Reuse of `harness/`.* `harness/play.py` already steps the environment with correct seat and
  determinism handling; whether it is the training-loop stepper or only the evaluator is open.
- *Checkpoint/versioning convention.* The existing immutable `checkpoints/` + fingerprint
  verification (G15) is the natural fit, but has never been exercised against learned weights.
- *Action space.* One op per unit × ~17 op types × positions, plus ≤10 market orders/turn. Needs
  hierarchical/factored actions with masking — and once the masking is written, most of the domain
  knowledge is already hand-coded.
- *The pre-existing trigger, kept as-is:* full RL requires **all four** of — land+animals+
  liquidation complete; ≥2 BBO sweep rounds producing no `IMPROVED` over 48 seeds; local median
  bank still <60% of the ladder's median winner bank; **≥3 weeks left before the deadline**. That
  last clause has teeth: from 2026-08-11 the deadline is ~7 weeks out, so the RL window closes
  around **2026-09-09**.

---

## 6. Immediate follow-ups from this pass

| # | Item | Why |
|---|---|---|
| **R1** ✅ | Added **D27** (the full 1.32.6 balance change) to [docs/reference/engine_deltas.md](docs/reference/engine_deltas.md) and re-pinned its header 1.32.5 → 1.32.6 | Those facts existed **only** in the MASTERPLAN this pass deletes. A DERIVED doc lagging the installed engine is exactly the failure mode that file exists to prevent |
| **R2** ✅ | [docs/INDEX.md](docs/INDEX.md) now records that `kaggle kernels pull` is **source-only** and that `kaggle kernels output` is what carries the numbers, plus the "never refresh the *visualized* notebook" rule | Recorded so it is not re-broken; it cost us five notebooks' outputs today |
| **R3** | Re-run [analysis/b1_top5_profile.py](analysis/b1_top5_profile.py) against the refreshed archive whenever the ladder top-5 changes | The top-5 turned over completely between 2026-08-05 and 2026-08-11 |
| **R4** 🟡 | **Route found 2026-08-17 (§4.5), not yet executed — no agent file has been downloaded.** Rather than authoring one older-generation opponent, adopt **tiers 0-5 of the reference-agent ladder** — six documented agents sharing a byte-identical scheduler and differing only in a `POLICY` dict, spanning $3.000 → $46.211, **MIT and the author's original work** — plus our own frozen `v1h` / `v1i` / `v1o_2` checkpoints as earlier metas. Wired into §2's bullet and S6 step 2 as the *intended* bench. ⚠️ **Blocked on R23** — nothing from that dataset beyond `LICENSE`/`NOTICE`/`*.csv` has been fetched, and the `.py` download is the user's call. **A third option exists and may be better: our own three extracted donor tapes** (Valmorlee 91456307 · Ueddy 90999409 · Kaito 90891564) already *are* the shared meta line, need no new licence, and as fixed-production opponents make the cleanest possible A/B for a market-layer change | §2 requires regression opponents from earlier metas; every bench to date was the current one, one generation deep |
| **R5** ✅ | **Decided 2026-08-11 by the user: a public replay may seed a route.** Recorded in §4.2, then refined once the rules were read — replicate the measured *profile*, keep the *tape* as a documented option | Competitor *notebook source code* remains out of scope — a separate, undecided question |
| **R10** ✅ | **Rules read** (supplied 2026-08-11). Using replays for development is clearly permitted (§2.4a, §2.6a, §2.11); the exposure is §3.14a "own original work", §2.5/§2.8 winner licensing, and §2.4b redistribution **into this public repo**. Resolved in §4.2 by replicating the *profile* rather than shipping a *tape* | Closes the one item that could have invalidated §4.3. The activity is not prohibited — the exposure is narrow, lands only at the prize stage, and the profile path removes it entirely |
| **R11** | Keep any extracted donor action stream **gitignored and local** | §2.4b forbids redistributing Competition Data to non-participants, and this repo is public |
| **R3b** ✅ | `.gitignore`: `notebooks/` → **`/notebooks/`** | A bare pattern matches *any* directory of that name, so it was also swallowing **`docs/source/notebooks/`** — the tracked markdown extracts that every `viz cell N` / notebook citation in `docs/` points at. Nine older extracts were tracked; the eight added today were silently invisible. The whole "the extract is the durable artefact" argument in Appendix A depended on this |
| **R8** | Decide whether `data/archive/*.py` (the collector chain) should be tracked | `data/archive/` is gitignored wholesale, so `scrape.py` / `repack.py` / `teams.py` / `features.py` are **not version-controlled** — including two bugs fixed today (below). The data is rightly ignored; the code that produces it probably is not |
| **R9** | Two collector bugs found and fixed **in untracked files** (see R8) | (a) `repack.py` copied unconditionally into `data/episodes_dataset/`, a directory that no longer exists — killing the whole chain *after* a successful 22-minute crawl; now guarded. (b) `teams.py` calls `subprocess.run(..., text=True)` and reads `.stdout` — which is `None` when the Kaggle CLI dies printing a non-cp1252 team name. `scrape.py` invokes it with `check=False`, so **`teams.csv` silently stayed five days stale with no error**. Re-run with `PYTHONUTF8=1` → 3.813 teams. The `check=False` is the real defect |
| **R6** | Leave the `MASTERPLAN.md` / `current_phase.md` citations in code comments alone (32 files under `agent/`, `harness/`, `tests/`, `analysis/`) | They are *historical* citations for why a line exists; rewriting them would touch `agent/` (out of scope) and would not make them more true. [docs/INDEX.md](docs/INDEX.md) "Χάρτης παλιών ονομάτων" resolves them, and git has the originals |
| **R12** | **Write the final config comment *before* creating a screen checkpoint.** A comment edited after the screen changes the package fingerprint, so the `stage=dev-screen` artefact no longer keys to the agent being confirmed and `prior_dev_screen_found` goes False at holdout | Cost one full DEV re-run (2 × 96 episodes) in v1o.1 |
| **R13** | **Declare a mechanism for every counter that *can* be non-zero, not only the ones a pinned screen happened to show.** `shed_overflow_burnt` is 0 under `--town-pin basket` and ~290 unpinned, so v1o.1's first holdout pull failed the metric gate on a counter no screen had exposed | Cost a `repeat_confirm_index=1` re-pull. The re-pull changed no code and no config — only the declaration — and both pulls returned identical numbers, but the confirm ledger correctly records it as a second look |
| **R15** ✅ | Added `worker_turns_moving` to `_V1K_REPORT_METRICS` (2026-08-13, S3 step 1c) — `harness/compare.py` aggregation, `CompareResult` fields, `results.json` keys and the CLI summary line are all generic over that tuple, so this was a 3-line change plus a print line. Pinned by extending `test_compare_metrics_reads_agent_a_seat_in_each_orientation` rather than a parallel test | Both v1p.1 and v1p.2's SMOKE STOPs below were decided directly from this number in the gate artefact, with no separate script needed |
| **R16** ✅ | **Checkpoint-naming convention, decided 2026-08-13 (S3 step 1c controls pass).** `<version>` names a candidate that was actually **screened** (`compare` run against its `checkpoints/<version>/main.py`, never against live `main.py`) — `checkpoints/v1p1b_armA1`, `_armB`, `v1p2b` above. An **inert post-STOP state** (live `main.py` reverted, behaviour-identical to an already-immutable baseline) gets **no checkpoint at all** — it is definitionally the baseline it reverts to, and creating one would just be a second, redundant immutable copy of `v1o_2`. `checkpoints/v1p_1` (2026-08-13, earlier this same day) predates this decision and is the case the convention exists to stop repeating: it is a post-STOP inert state that *did* get a checkpoint, inverting `v1o_3`'s naming (a stopped variant that also got one) from the pass before it — left as-is, not renamed, since a checkpoint's whole point is immutability once created | v1p.1 and v1p.2's own SMOKE screens ran against live `main.py` directly and then reverted it — fingerprints `bb9d173c…`/`06ebef7c…` in `gates/v1p1_armA_smoke_mirror`/`gates/v1p2_smoke_mirror` match no checkpoint on disk and can never be re-derived |
| **R14** ✅ | **`checkpoints/` was gitignored wholesale**, contradicting the invariant the directory exists to enforce: [harness/checkpoint.py](harness/checkpoint.py) records (review H2) that checkpoints were *moved out of* `runs/` precisely because being gitignored "erased the only record of every accepted regression baseline from git history" — and then the same was done to `checkpoints/`. **Decided 2026-08-11 by the user: track the manifests only.** `.gitignore` is now `/checkpoints/**` + `!/checkpoints/**/` + `!/checkpoints/*/manifest.json` (that order is required — git cannot re-include a file whose parent directory is excluded). 20 manifests for v0…v1o_2 now carry every accepted baseline's fingerprint in history; the packages stay out | Same class as R3b: an argument the repo relies on ("immutable, verifiable baselines") was not true on disk |
| **R7** | Unresolved: submission `55387820` (2026-08-09 18:58, score 613,0) corresponds to no checkpoint or gate in this repo; its description ("4th attempt…") is hand-written, so it was almost certainly a manual upload | It occupied an active slot and pushed v1g out. Harmless, but the two active slots are the final-ranking lineup |
| **R17** ✅ | Added `worker_turns_working` to `_V1K_REPORT_METRICS` (2026-08-14, S3 step 1d) — same 3-line-plus-print-line change as R15, generic over the tuple. Pinned by extending `test_compare_metrics_reads_agent_a_seat_in_each_orientation` rather than a parallel test | v1p1b arm A1 hit `worker_turns_moving` 46,0% — the largest commute cut ever measured here — by doing *fewer* working turns and shedding 30% of `crop_tile_days` into idle. A ratio alone would have let it pass; the absolute counterweight now sits next to it in every gate artefact (§3.4) |
| **R18** | **Replay-analysis scripts: two indexing traps, found and fixed in `analysis/v1q_onboarding_escape.py` (2026-08-14).** (a) Two checkpoint packages that are both literally named `main.py` collide under `harness.play`'s filename sanitizer if given the same `run_dir` — the second `play()` call silently overwrites the first's replay before it's read. Give each orientation/arm its own `run_dir` subdirectory and consume each replay before the next `play()` call. (b) In a recorded episode's `env.toJSON()`, `steps[i][0]` is always seat 0's log entry — `observation` mirrors both farms (safe to index by `[0]` regardless of which seat's *state* you want, verified directly), but `action` is logged per acting agent and must be read from `steps[i][seat]`, not `steps[i][0]`, or a lookup for the non-zero seat silently returns nothing. **(c) added 2026-08-14 (S3 step 1e): the action logged at `steps[i]` is the one that *produced* `steps[i]`'s observation, not the one applied to it.** Pairing an order at step *i* with the money at step *i+1* shifts every purchase one turn later and makes the settlement look lagged — it is not. Read the order and the resulting state from the *same* `steps[i]` entry | Both bugs produced a plausible-looking but wrong result before being caught — the first made escapes appear to track *seat* rather than *agent*, the second made every "which unit acted" lookup fail silently (`None`) for seat 1. Neither raised an exception. Trap (c) is what made S3 step 1d misread the HIRE settlement as gapped and the purchase schedule as identical — corrected in §4.3 |
| **R19** | **Config-override package builders must REPLACE the target key and assert the effective value, never insert it (2026-08-14, S3 step 1e).** `analysis/v1r_build_stacked.py` first inserted an arm flag as a new key *before* the same key's existing default in the copied `config.py`; the later dict literal wins, so the flag was a silent no-op and every A1-stacked screen ran inert — returning a plausible "identical to the unfixed reproducer" result. The builder now string-replaces the existing key line and re-loads the built config to assert the effective value before writing the package. **General rule:** any tool that edits a config by source-text must round-trip through `load_config` and check the value it intended to set — a dict with a duplicate key does not raise | The result *looked* like a clean "the fix does nothing" finding; it was a dead flag. Caught only by instrumenting the executor's own reserve and seeing the C1 package compute the undercounted number. An A/B whose treatment arm is byte-identical to control is a red flag to trace, not a finding to publish |
| **R21** ✅ | **Report the seed set's realised shop draw in every market-side gate artefact.** §4.1b makes the town a first-class confounder: a fixed seed fixes the shop draw, so a small-seed market-only screen can be measuring one town. Emit per-arm the distribution of `units_per_tick` for STRAWBERRY / WOOL / MILK across the seed set, next to the dollars. **Discharged in `--shop-draw` (R22) and directly in S6 step 0 leg 1 (2026-08-17): the 32-seed set sampled WOOL zero-drain 66/192 = 34%, the predicted 34,4%** | §2.1.2 licenses fixed seeds for market-only changes on *occupancy* grounds, which is still true — and is not the same as the arm being unconfounded. A 0-YARN_STORE town (34% of towns) is a different game, and a 12-seed screen can contain zero of them or six |
| **R22** ✅ | **Bradley-Terry landed 2026-08-17** — [harness/ladder.py](harness/ladder.py) + `python -m harness.cli ladder`, 11 guards in `tests/test_ladder.py`. MM fit (Hunter 2004) with a half-phantom-win prior so an agent that sweeps a graded bench stays finite, reported on the competition's own Elo-like scale (400 pts/10× strength, mean 1500). Both seats on every pairing and **the per-seat split is reported separately** (§2.1.1 — an agent that wins only from seat 0 has a market-ordering dependency, not a strength). `--round-robin` plays the bench against itself so the comparison graph is connected; without it the printout says so rather than letting weakly-identified bench ratings look authoritative. `--shop-draw` discharges **R21** in the same command | This is a large part of why §1's central puzzle — measured local wins converting to ~nothing on the ladder — has stayed open for five weeks. The pinned defect is `test_beating_a_strong_opponent_outranks_beating_a_weak_one`: two agents with identical 60% records must not receive identical strengths, and under `median_bank`/W-L they do. S6 step 3 |
| **R23** ✅ | **Decided by the user 2026-08-17: A1 + A2, skip A3.** Tiers 0-5 (MIT, original work) as the graded regression ladder; **our own three extracted donor tapes** as the fixed-production mirror bench; **tiers 6-9 not used** — their uncovered `_TRACE` is avoidable because A2 reproduces the same fight from material we already hold. Their published $164-$2.617/ep separation is kept as a citation-only calibration figure. Wired into S6 step 2 | The uncovered `_TRACE` was the only ambiguity in the dataset, and it is now simply not touched |
| **R25** ✅ | **Done 2026-08-17.** Fetched the six tier-0-5 `.py` (MIT) into the **gitignored** `harness/bench_agents/reference/` (with `LICENSE`/`NOTICE`/`PROVENANCE.md`); resolver `harness/bench_agents/reference_ladder.py` (committed, carries no competition data) maps tier/slug/name → local path. Tiers 6-9 not fetched (R23); CC BY-SA CSVs read transiently, never vendored (§4.5). Verified loadable + graded (Finn $3.000 floor → Rita ~$40k). Wired into the S6-step-0 R22 ladder | A1 is decided but not executed — nothing beyond `LICENSE`/`NOTICE`/`*.csv` has been downloaded |
| **R26** ✅ | **Done 2026-08-17.** `analysis/donor_streams.py` wraps the three donor tapes via `analysis/tape_agent.py::make_tape_agent`, sha256-verified against provenance on load; used programmatically by S6-step-0 leg 1 and by the R22 ladder (tape `main.py` paths). Route files stay gitignored (§2.4b / R11) | The fixed-production opponent is what makes an S6 market-layer A/B clean — production held constant by construction |
| **R28** 🟢 | **The BT bench had a ceiling problem — S6 step 1 produced the new rung (2026-08-17).** The round-robin read Valmorlee **3008 (56-0-0)** › Ueddy 2349 › Kaito 2182 › `v1u_base` 1701 › … — the tapes swept every rung, so nothing could score a challenger *better than a tape*. **The ReCurSiON reconstruction now sits above them: 24-0-0 vs the Valmorlee tape (+$14.267/ep), 24-0-0 vs Ueddy/Kaito** (SMOKE 0-11, both seats). It is a local tape agent (parameterised by its majority-vote stream), not a file path, so wiring it into `harness.cli ladder` for a full BT number needs a packaged local `main.py` (gitignored) — **now item 2-3 of step 1b, this coming pass** | A graded bench whose top rung is the thing under test measures nothing above it. Step 1's reconstruction is that next rung |
| **R35** | **A derived artefact must be regenerated when the verdict changes, not just re-printed (2026-08-18, S6 step 2a Phase 0).** `data/derived/s6_step2a_phase0.json` still holds `gate_value: 840,5` / **`gate_clears: true`** — the pre-correction summary computed on the double-counting $300 proxy — while the corrected script prints `$241 (on_tile $0) ⇒ STOP` and emits different keys. `--report-only` recomputes the console output and leaves the stale summary in place. **Rule: when a pass corrects its own pricing basis, re-run the writer, and make the artefact carry the verdict string itself** so a future grep cannot read GO off a superseded flag | Third time in this repo (R12: comment edited after the screen ⇒ artefact keys to the wrong package; R19: duplicate config key ⇒ a dead flag that looked like a finding). The reasoning here is right and the file says the opposite |
| **R34** ✅ | **`gates/` is gitignored wholesale, so no gate result is in git — R14 repeating one directory over.** R14 found `checkpoints/` ignored, contradicting the invariant that directory exists to enforce, and the user's fix was **track the manifests only** (`/checkpoints/**` + `!/checkpoints/**/` + `!/checkpoints/*/manifest.json`, in that order — git cannot re-include a file under an excluded parent). The same argument applies verbatim to `gates/`: step 1b's DEV and unpinned-holdout `results.json` are the evidence for shipping `55586926`, they hold **aggregates only** (banks, counters, verdicts — no action streams, so no §2.4b exposure), and they exist on one laptop. **Confirmed by the user 2026-08-18 and implemented:** `.gitignore` is now `/gates/**` + `!/gates/**/` + `!/gates/**/results.json` (that order is required — git cannot re-include a file under an excluded parent). 5 artefacts, 660 KB, verified before committing: **no per-step action streams** (longest line 327 chars), and the only competition identifier is the episode id `91456307` inside an `agent_a_spec` *path* — already stated openly in this file, so no §2.4b exposure. Replays, shop draws and confirm logs under `gates/` stay local | An accepted-gate record that lives only on the machine that produced it is not a record. Every "measured, not narrative" claim in this file rests on artefacts like these |
| **R32** | **Price *every* loss counter in the artefact, including the ones that pass, and state the total (2026-08-17, evaluating S6 step 1b).** The shipped reconstruction's `priced_loss_a` reads a comfortable $1.500/ep against budget — and is **100% `unexpected_weeds_lost`** (5,0 tiles × $300). Beside it sits `plant_decay_units_lost` **15,0 units/ep**, structural, unpriced, and ~equal on the incumbent tape (14,9). Summed: **~$2,8-3,1k/ep of own-farm loss on both arms of every tape gate since 08-16**, never once totalled, and **bigger than the +$1.912/ep lever the next pass was queued to build**. Add a per-episode **loss ledger** (counter → count → unit price → $) to the gate summary, with unpriced structural counters listed at "unpriced" rather than omitted | A counter inside its budget is still a bill. R13 fixed *floored-instead-of-priced*; this fixes *passed-therefore-invisible*. It is also the answer to "where does this agent lose": it was in the artefact all along |
| **R33** | **`--round-robin` BT is still unmeasured for the reconstruction (R28's rung).** Step 1b's item 3 reports a genuine challenger-only **24-0-0 sweep with margins** but its BT table is an unfilled `<!-- BT_LADDER_RESULT -->` placeholder and no artefact exists on disk. A challenger-only sweep cannot produce a rating — the round-robin is what connects the comparison graph (R22's own caveat). One command, carried into step 2a | R28 exists because the tapes swept every rung, so nothing could score *above* a tape. The reconstruction is that rung and its rating is still a blank |
| **R30** | **Read the donor's public leaderboard score before selecting it, and quote it as the pass's surface area (2026-08-17, evaluating S6 step 1 Phase 0).** `kaggle competitions leaderboard kaggriculture -d` is one call and it is the only number in this competition that is *already* in the units we are judged in. Run it, it says: T1's donor **Valmorlee #1018 / 1.842,4** (tape at 1.617,6 = 88% of it — the ceiling was the donor), S6's donor **ReCurSiON #4 / 3.004,6** (⇒ step 1b's ~+1.383-point surface area), and **Peter Parker #29 / 2.844,2 as a *pure* frozen tape** (1 distinct market stream in 12 traces). ⚠️ Only valid where the team's `LastSubmissionDate` **precedes** the episode dataset the traces come from — otherwise the score belongs to a submission you did not trace (true for ReCurSiON 08-14 and boatlee 08-15; **not** for Ueddy/カワシギ/Tschinkel, all 08-17) | Five weeks of §1's central puzzle had a one-call component nobody spent: our best asset was a faithful copy of a rank-1018 agent. R29 says never rank on reward because reward is the town; this says **do** rank on rating, because rating is the ladder |
| **R31** | **"Same submission" is tested on the *market/full* stream, never on the opening (2026-08-17, S6 step 1 Phase 0).** The 48-step opening is byte-identical across 1.219 of 1.398 live seats (87%), so it discriminates nothing — yet the Phase 0 provenance line still claims one submission *from* the opening fingerprint. Measured: ReCurSiON's 50 traces show **50 distinct** `fp_market_full` and **16 distinct** `fp_prod_full`. Any future donor-provenance claim states the test used, and a majority vote over a mixed population must first show the population has **one** mode (2-cluster on pairwise market-decision distance — step 1b, item 1) | A majority vote across two near-identical submissions is a blend that measures neither. The fidelity result (0,12%) makes this unlikely here, but "unlikely" is not the same claim as the report made |
| **R29** | **Donor/route selection ranks on the *town-controlled* ratio, never on reward or bank (2026-08-17, S6 step 1 Phase 0).** The first shortlist ranked candidate teams by median reward and **missed ReCurSiON — the field's best calendar — entirely**, because reward is 99% the town (§4.1b). `analysis/s6_step1_phase0.py calendar --all` (candidate realised price ÷ same-town opponent's, straight from the recorded episode) is the selector, and it must scan **every** eligible team, not a reward-triaged shortlist. Same tool answers criterion 2 (`agreement`, per channel) and the `cluster` inventory. §3.4 lesson logged | The environment dominates every raw aggregate here; a triage that ranks on it hides exactly the entity worth finding. Cost was near-zero only because the all-teams scan caught it mid-pass |
| **R27** | **Never let the top submission fall out of the active pair as a side effect of shipping.** Eviction is by submission **date**, not score (§6bis, measured): uploading anything today evicts Valmorlee (1.617,6), not Ueddy. Decide the eviction before the upload, and price the re-upload (restarts at 600,1, ~1 day to re-converge) | Measured 2026-08-17: an inactive submission plays **zero** episodes (v1h dead 8 days) and the final Bradley-Terry runs on the latest 2 only. The official overview's "every bot continues to play" is boilerplate and is false here |
| **R24** | **Re-test the §3.3 `shop-adaptive sell floor` STOP against `v1u_base`.** It failed at 415 crop tile-days as *"production-constrained, never glut-constrained"* — true then, and false at the tape's production. Engine-stale as well (1.32.6) | §2's STOP protocol: a STOP is final once its own mechanism has no untested implication left. This one's stated mechanism explicitly names a production level we have since left |
| **R20** ✅ | **Per-product units + realised revenue in every gate artefact (2026-08-15, S3 step 2).** `harness/compare.py::_attach_v1k_diagnostics` read `units_sold_by_product`/`revenue_by_product` but wrote only the MELON pair (`melon_units_*`/`melon_revenue_*`), so MILK/WOOL **realised price** — the §4.1 currency every herd-13 economic risk turns on — could not be read from a gate artefact at all. Generalised over module-level `_V1K_REPORT_PRODUCTS = ("MELON","MILK","WOOL")`, emitting `{product.lower()}_units_{arm}` / `_revenue_{arm}`; the six longhand melon sites (`_attach_v1k_diagnostics`, the `CompareResult` fields, the four aggregation/None-fill blocks) each now loop the tuple, with the MELON keys **byte-preserved** (MELON is first, keyed by `.lower()`). Added the MILK/WOOL fields to `CompareResult`, `cli.py`'s `results.json` dict and the CLI summary. Pinned by extending the existing metrics test | Named the §3.3 MILK-saturation-on-9-COW mechanism directly from the herd-13 gate output (MILK $/u 151 → 131-139 on H2/H2R) with no separate script. R20's six-site loop deliberately avoids the "miss one None-fill block" trap the brief flagged: a missed block silently absents the key from exactly the failed-metrics artefacts |

---

## 6bis. Submission operations (carried over verbatim — this is the only copy now)

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "<version> <description>"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID>           # -v for CSV
kaggle competitions replay <EPISODE_ID> -p ./baselines/<date>/replays
kaggle competitions logs <EPISODE_ID> 0 -p ./baselines/<date>/logs   # index = seat
```

Auth: `KAGGLE_API_TOKEN` in `.env`; the CLI lives in `.venv/Scripts`, not on `PATH`. Package with
`tar -czf submission.tar.gz main.py agent/` — `main.py` at the **root**.

**Before every upload:**

- [ ] **Loader contract (G12):** the exported `agent` is the *last* callable; imports at top level;
      no `__file__` shim; vendored constants ([agent/_vendored.py](agent/_vendored.py)) parity-tested
      against the **currently installed** engine version.
- [ ] **Timing:** cold-process profile on both seats; gate `max_turn × 3 < 1s`.
- [ ] **Determinism (G13):** same seed in two fresh processes with different `PYTHONHASHSEED` →
      identical trajectory.
- [ ] **Mirror smoke:** `python -m harness.cli play main.py main.py --steps 720` → `clean=True`.
- [ ] Size < 100 MiB · `pytest tests/` fully green · `KAGGRI_DEBUG` **off** by default.

**Slots.** 5 uploads/day; **only the latest 2 are active**, and those two are what the final
Bradley-Terry tournament runs. They must be **champion + a challenger differentiated in exposure**
(herd composition, sell-side aggressiveness) — not simply the two newest versions. The community's
own list of common mistakes puts it plainly: *"two near-identical active submits → meta shift kills
both."* In the final week before 2026-09-30, both are frozen.

#### 🔴 Slot mechanics, measured 2026-08-17 — two traps, both counter-intuitive

The question that prompted this: *"once a submission converges at 1.600+, is there any point
letting it live? Its rating can only move a few points, and it still counts toward the leaderboard."*
**Measured, both halves of that are false, and acting on them would retire our best asset.**

**Trap 1 — an inactive submission stops playing entirely, and is excluded from the final.** Newest
episode per submission, read 2026-08-17 10:46 UTC:

| Submission | Score | Newest episode | Status |
|---|---:|---|---|
| `55383610` v1h | 652,5 | **2026-08-09 20:28** | dead **8 days** |
| `55414570` v1i | 593,8 | 2026-08-16 05:04 | died when the T1 tape took its slot |
| `55438252` v1o.2 | 647,5 | 2026-08-17 05:26 | died when the Ueddy tape took its slot |

A submission outside the latest 2 plays **zero** episodes. Its score freezes where it stood; it is
not "still competing at a converged level." And the overview is explicit that *"the latest 2
submissions are **also used for final leaderboard evaluation**"* — the final Bradley-Terry
tournament runs on **post-deadline episodes**, which a retired bot does not play. **A frozen 1.617,6
would contribute nothing to the ranking that pays.**

⚠️ **The official overview contradicts itself here and our measurement settles it.** The same page
also says *"Every bot submitted will continue to play episodes until the end of the competition."*
That is generic Kaggle simulation boilerplate and **it is not true in this competition** — the three
rows above are the counter-evidence. Trust "only the latest 2 are tracked."

**Trap 2 — we cannot choose which slot to free. Eviction is by submission *date*, not by score.**
Confirmed against our own history: shipping the T1 tape on 08-16 dropped **v1i (08-10)**, the
*older* one, while keeping the higher-scoring v1o.2. So with the pair currently
**Valmorlee `55548339` (08-16, 1.617,6) + Ueddy `55575305` (08-17, 1.027,8)**, uploading anything
new evicts **Valmorlee — our best submission** — and keeps Ueddy plus the newcomer.

**Consequence for the agreed policy** (*one top tape + one innovation slot*): to ship an S6
challenger while keeping the top tape, the tape must be **re-uploaded first** so it becomes the
newer of the two, then the challenger goes second. That costs the tape's converged rating — a
re-upload restarts at **600,1** and has to re-converge (T1 took ~1 day to go 1.091 → 1.617). Budget
that, or accept losing Valmorlee.

**And a converged rating is not stable — it decays.** §1 records `55414570` at **632,2 → 618,4 →
600,2** across three reads with **no code change**, and §4.4#1 measured a frozen agent going 87/90
→ 14/27 against a newer field. A converged submission is a **depreciating** asset that must keep
playing to hold its place, which is the opposite of the premise above.

**Standing rule from this:** never let the top submission fall out of the active pair as a side
effect of shipping something else. Decide the eviction deliberately, before the upload.

🔴 **The eviction decision S6 step 1b needs, with the donor ratings attached (2026-08-17).** The pair
is **Valmorlee `55548339` (08-16, 1.614,0) + Ueddy `55575305` (08-17, 1.398,7 and climbing)**, so
uploading the reconstruction evicts **Valmorlee**. New information that bears on it (§1, R30): the
Valmorlee *donor submission* is **#1018 / 1.842,4** — the tape is at **88% of a ceiling we now know**,
and re-uploading it to protect it costs its converged rating anyway (600,1 restart). The
reconstruction's donor is **#4 / 3.004,6**. Only the latest 2 play the post-deadline Bradley-Terry, and
the deadline is ~6 weeks out. ~~Recommendation: accept losing Valmorlee and ship.~~

✅ **DECIDED BY THE USER, 2026-08-17: accept losing Valmorlee and ship the reconstruction.** R27 is
satisfied — the eviction was decided deliberately and *before* the upload, which is the whole content
of that rule. Two things this authorisation does **not** do:

- **It does not waive the gate.** The decision is *which submission to sacrifice*, not *whether the
  route qualifies*. Step 1b's kills (i) and (ii) still bind: if the reconstruction misses DEV
  acceptance on the non-mirror bench or the unpinned holdout, or the 50 traces turn out to be two
  submissions, **nothing is uploaded** and the tape stays the product. The authorisation covers a
  package that has cleared §2.1.3 and §6bis, and nothing else.
- **It does not extend to the next upload.** Once this ships the active pair is **{Ueddy tape,
  ReCurSiON reconstruction}**, so the *following* upload evicts the **Ueddy tape** and would leave
  **{reconstruction, reconstruction + overlay}** — two near-identical actives, exactly the pattern
  §6bis warns kills both on a meta shift. **Step 2's eviction is therefore a separate and harder
  question**, and it should be raised at the *start* of step 2, not at its end.

⏳ ~~**Not yet decided: which tape is "the top tape".**~~ 🔴 **Settled by the decision above, not by
convergence: Valmorlee leaves the pair, so the surviving tape is `55575305` (Ueddy)** — and it becomes
the incumbent the reconstruction is judged against on the live ladder (step 1b kill (iii)). The
original note is kept below because its reasoning about reading scores on the same day still binds.

⏳ **Not yet decided *(superseded — retained for its reasoning)*: which tape is "the top tape".** Valmorlee is at 1.617,6 and converged; Ueddy
is at 1.027,8 on **7 episodes** from a 600,1 start, and T1 took a full day to converge. Ueddy's
holdout was *stronger* than Valmorlee's (median $124k, 96-0, 0 seats under floor). **Let Ueddy
converge before ranking them** — the comparison is not yet available, and §1's decay note says it
must be read on the same day.

✅ **Standing debt cleared, 2026-08-11.** It read: *"the active pair is `55414570` (v1i) +
`55409945` (v1m_d2), which differ only in market-order emission ordering — same herd (4C/6S),
same tiles, same sell-side thresholds. That is the exact pattern the rule warns about."* Θ1
(§3.2.8) had already measured that **no sell-side lever could fix it**; differentiation had to be
productive, and §4.3 S3 step 1 produced it. The active pair is now **`55438252` (v1o.2) +
`55414570` (v1i)**, differing in **production** — 562-612 crop tile-days against 413, a 1,4×
gap — which is the most differentiated pair this repo has ever fielded.

Pre-upload checklist for `55438252`, all green: G12 loader contract · timing **both seats**
max 12,6ms ⇒ `max×3 < 1s` · G13 determinism (identical action-stream sha256 under two
`PYTHONHASHSEED` values) · mirror smoke `clean=True` · `pytest` 229 · `KAGGRI_DEBUG` off ·
53 KB. **4 submissions remaining that day.**

🟢 **T1 tape shipped as challenger, 2026-08-16.** Submission **`55548339`** — an open-loop verbatim
replay of public episode **91456307 seat 0 (Valmorlee)**, action-stream sha256
`49c4c3d7e6842b43…`, 719 steps, self-contained `main.py` (no `agent/` dep), route held gitignored
under `baselines/2026-08-16/tape_submissions/` (§2.4b). The active pair is now **`55548339` (T1
tape) + `55438252` (v1o.2)** — maximally differentiated in production (tape home bank $117.931 vs
v1o.2's ~$60k). `55414570` (v1i) drops inactive. Pre-upload checklist all green: G12 · timing
1,2ms · G13 (identical bank under two `PYTHONHASHSEED`) · mirror `clean=True` · `pytest` 286
(3 expected `test_v1h2d_*`) · 9 KB. **4 submissions remaining that day.** Full record:
`baselines/2026-08-15/t1_repair_justification.md`.

---

## 7. Where this stands

*(Updated 2026-08-17. The paragraph this replaces — "nothing under `agent/` has been
touched" — was true up to and including S1/S2; it no longer is.)*

The plan is **§4.3 S1 → S4 → S6, replicate → freeze → innovate**, with the target profile measured
from 120 current-engine seats rather than guessed. **R10 is closed** — the rules were read, using
replays for development is clearly permitted, and the user's 2026-08-15 decision settled §4.2 in
favour of shipping the tape.

🔴 **S5 was withdrawn on 2026-08-17 and replaced by S6.** Not stopped — *mis-measured*: its
objective was a realised-price spread that §4.1b shows is 99-100% the town's random shop draw.
What survived is the premise S5 got right and understated: **the top of the ladder is a mirror
match**, and the whole fight there is a **1,05× realised-price edge worth a median $2.826/ep**.
S6 is that fight, run under §2's loop with a bench that finally retains earlier meta generations.

- **S1 ✅ and S2 ✅** (2026-08-11): the target profile reproduces across 9 teams with near-zero
  structural spread (`data/derived/b3_target_profile.json`), and S2's kill criterion did **not**
  fire — 0/18 donor matchup-seats fell below the $57.360 floor.
- **S3 step 1 — in progress.** Two increments gated and accepted (`checkpoints/v1o_1`,
  `checkpoints/v1o_2`, both `GO=True` on unpinned holdout); **five** STOPs now recorded in §3.3.
  Crop tile-days **413 → 562-612** against a target of 1.316; idle unit-turns **28,2% → 16-18%**.
  Live `main.py` ≡ `checkpoints/v1o_2`, `pytest tests/` **237 passed**.
- **S3 step 1b — ⛔ run and stopped (2026-08-11 γ).** Seven variants screened, two taken to the DEV
  acceptance arm, both refused. The diagnosis was right — bundling recovered FERTILIZER 123 → 191
  units/ep and the feed-round promotion took `animals_escaped` **13 → 0** — and the fix still
  costs more than it earns, because it is paid for out of crop tile-days at ~10× the exchange
  rate. **Tier 0 is saturated 100% of the day**, so nothing inside it can be reordered profitably.
  The mechanism is retained in `agent/`, switched off, with live `main.py` verified
  behaviour-identical to `v1o_2` (`mean_diff` $0,00, 4/4 ties).
- **S3 step 1c — ⛔ both increments run and stopped (2026-08-13).** Herd compaction (v1p.1,
  config-only) cut the herd's summed shed distance 39→27 and did lower `worker_turns_moving`
  (61,7%→53,6%) but deterministically escaped 2 COW/episode via an animal-type placement race in
  `assign()`'s greedy PLACE competition — 100% reproducible, always the same two tiles, tiles the
  change never touched. Zone assignment (v1p.2, `agent/scheduler.py`) filtered `assign()`'s
  eligible units by quadrant and hit its own pre-specified kill criterion at the first SMOKE:
  `worker_turns_moving` barely moved (60,0%→58,7%) and a structural counter broke
  (`plant_decay_units_lost` 0→17), most likely because the zone partition has no memory across
  turns and can re-zone a `committed` unit out of eligibility for its own in-flight task. Both
  kept in `agent/`, switched off, live `main.py` verified behaviour-identical to `checkpoints
  /v1o_2` (`mean_diff` $0,00, 12/12 ties). `pytest tests/` **237 → 244 passed**. Full report:
  `baselines/2026-08-13/s3_step1c_report.md`.
- **S3 step 1c, continued — ⛔ both untested controls run, both STOP too (2026-08-13, same
  day).** Neither original STOP was actually final — each root cause implied a control that was
  never run (ROADMAP §2's STOP protocol was updated to say so explicitly). v1p.1b ran both:
  arm A1 (COW instead of SHEEP on the same two distance-1 tiles) still escaped **48** animals,
  same magnitude as arm A but now a *mixed* COW/SHEEP pair — **refuting v1p.1's own
  type-blind-race root cause**. Arm B (`carrot_tiles` 3→1 alone, PASTURE untouched, the confound
  control arm A never ran) escaped **12** with zero geometry change at all — dropping
  `carrot_tiles` is itself destabilizing, a second, independent mechanism. Closes the "convert a
  CARROT tile to compact the herd" family for good, confirmed analytically: the ten claimed
  PASTURE slots are already the ten nearest of the 13 available. v1p.2b threaded `committed`
  into `scheduler._zone_partition` (pin-first, quotas as a soft target for uncommitted units
  only) — it fixed both structural symptoms v1p.2 broke (`plant_decay_units_lost` 17→0,
  `animals_escaped` back to parity) but `worker_turns_moving` still barely moved (58,9%→60,3%,
  same ~1,4pp non-movement as before) — its own restated kill criterion's third exit: **the
  constraint genuinely is not which tasks a unit is offered.** Both kept in `agent/`, switched
  off, live `main.py` re-verified behaviour-identical to `v1o_2` (`mean_diff` $0,00, 12/12
  ties). `pytest tests/` **244 → 248 passed**. Full report:
  `baselines/2026-08-13/s3_step1c_controls_report.md`.
- **S3 step 1d — Phase 0 stopped the race before Phase 1, on a fifth mechanism (2026-08-14).**
  R17 landed (`worker_turns_working` in every gate artefact) plus the §1.2/§1.3/§1.4 corrections
  to §3.3/§3.4/§4.3's deferred item ③. `checkpoints/v1q_base` rebuilt. The mandatory Phase 0
  diagnostic (`analysis/v1q_onboarding_escape.py`) traced the deterministic ~2-escapes/episode
  onboarding defect directly against the real `checkpoints/v1p1b_armA1` package and found
  **neither** anticipated branch — not PLACE-timing infeasibility, not lost FEED-task contention
  — but a **fifth mechanism**: an early-game cash-flow exhaustion specific to arm A1's exact
  config (both animals' shed WHEAT reads **zero** for their entire unfed window; candidate's own
  money hits exactly $0 by hour 25 while baseline never does; a `carrot_tiles`-alone control does
  not reproduce the collapse). Per its own STOP protocol, the pass stopped **before** building
  Arm P/F/R — all three would have targeted PLACE/FEED scheduling, which the trace shows is not
  where the defect lives. `pytest tests/` **245 passed** (fresh-clone baseline, unchanged). No
  arm screened, no submission. Full report: `baselines/2026-08-14/s3_step1d_report.md`.
  🔴 **Corrected 2026-08-14 (S3 step 1e):** the "trace the hour-1 HIRE settlement" recommendation
  is **withdrawn** — there is no hour-1 gap (both agents at $2.980,0, 6 hands at step 1); the $40
  is the CARROT seed at step 2 and leaves the candidate *richer*, and the purchase schedules
  differ (one extra early SHEEP), they are not identical. See the step 1d 🔴 block above and R18(c).
- **S3 step 1e — the feed-cash reserve, run as a race (2026-08-14).** The real, *located* defect:
  `agent/executor.py`'s reserve counts placed animals + this order's additions but not the herd
  already in flight, so purchases spread across turns bypass it — see §4.3 above and
  `baselines/2026-08-14/s3_step1e_report.md`. **Outcome:** the fix is **arm C2**
  (`feed_reserve_horizon="target"`, reserve for the *full intended* herd, `checkpoints/v1r_armC2`):
  48→0 escapes on the reproducer, +$5.907 IMPROVED, herd reaching full target on baseline's day;
  the count-in-flight fix (C1) and the raise-the-days control (X) both leave 48 (X is worse). C2
  is NON_INFERIOR on the shipped config (≈$0, DEV 48-seed confirmed) and structural-clean. `pytest`
  248 passed (+3 `test_v1r_*`), no submission. Two ROADMAP corrections landed (no hour-1 HIRE gap;
  purchase schedules differ) plus R18(c) and R19.
- **S3 step 2 — herd 13 on the C2 reserve: ⛔ STOPPED at SMOKE, blocked on feed logistics not cash
  (2026-08-15).** R20 (per-product MELON/MILK/WOOL units+revenue in every gate artefact) and the C2
  dead-expression cleanup landed first, the cleanup + the new 6/12/13 ramp proven byte-inert vs
  `checkpoints/v1r_armC2` (ties 12/12, mean_diff 0,0). Phase 0 passed — at target 13 the herd *owns*
  13 by day 9-11, money never $0 (the cash half is paid). But all three herd-13 arms REGRESSED,
  −$15-21k/ep, losing every one of 12 seeds: **H1** (4C+9S, +3 animals at the unclaimed distances
  7,7,8, zero reassignment) escaped **122**/24-ep and collapsed `crop_tile_days` **−36%**, failing
  the pre-registered criteria 3 and 4; **H2** (9C+4S) −$20,9k with MILK realised price 151→**139**
  (§3.3 saturation, non-mirror); **H2R** (9C+4S on the ramp) lowered escapes 88→**66** but recovered
  neither the crop collapse nor the dollars — **the ramp is not the lever.** *Mechanism:* the current
  PASTURE geometry + `assign()` routing cannot feed 13 (herd Σdistance 37→59, +59%); C2 pays the cash
  half, nothing pays the logistics half. *Increment:* **none** — C2 stays inert/latent at herd 10 (B0
  = `checkpoints/v1s_B0`, NON_INFERIOR ~$0), not promoted alone. `pytest` **248 → 254** (+6
  `test_v1s_*`). **No submission.** Full report: `baselines/2026-08-15/s3_step2_report.md`.
- **Engine 1.32.7 landed 2026-08-15 (D28).** Market-only, scarcity-side only, CARROT/TOMATO/EGG
  only, via a new `hinge` shape. TOMATO/EGG are a **strict no-op** below their knee; **CARROT
  changed from depletion 1 upward** (shape *and* target moved). All six other products are
  byte-identical everywhere, and the glut branch is untouched for all nine — so no sell-side model
  built on the glut curve needs revisiting. `agent/_vendored.py` re-synced, `pytest tests/`
  **254 → 268 passed** (+14 `test_v1t_hinge.py` guards; the vendored price sweep was widened from 3
  points to ±3T after it was found to sample only the knee, where hinge and linear agree by
  construction). ⚠️ **Not yet live:** 28/28 episodes in the 2026-08-14 dataset probe as 1.32.6.
  Measured knee-crossing rates on those 28 (TOMATO 54%, EGG 25%, CARROT 18%) reproduce the
  announced 50/22/26% closely. The top-9 profile grows **zero** of all three, so **donor tapes are
  unaffected** — which is what makes §4.2's tape option survive this bump intact.
  🔴 **But every checkpoint and baseline in this repo was measured on 1.32.6, and we *do* sell
  CARROT ($4.709/ep) and EGG.** Cross-engine comparison is exactly the error §4.2's B1 correction
  records. Any new gate needs its baseline **rebuilt on 1.32.7** (`v1u_base`); the magnitude of the
  shift on our own agent is **unmeasured** and should not be guessed at. The pre-1.32.7 STOPs in
  §3.3 still bind on mechanism (logistics, saturation, geometry — none of which the bump touched),
  but any *dollar* figure in them is now engine-stale.
- **Deferred item ③ — the travel-ratio diagnostic: RUN 2026-08-15, not a STOP (item ④ step 1).**
  `analysis/v1u_travel_ratio.py` captured the exact per-turn `(tasks, snapshot, committed)` triple
  at the source (an in-process wrap of `agent.policy.assign`, opponents untouched), reconstructed
  greedy byte-for-byte (0 voids on 25.884 turns), and compared it against the conservative
  **re-match** optimum (same served set, only the unit→task pairing changes; pins committed +
  `allowed_unit`, honours cargo/priority-tier — the way a legal ④ must). **Greedy regret = 4,30%
  of moving turns** (5.720 walk-steps / 133.026, ≈159/ep), in the pre-registered **3–8% band ⇒
  proceed to ④ step 2, re-scoped to the feed round only.** So the 62% commute is *mostly* a
  geometric floor — **forced-walk floor 0,963, ceiling ≤3,7%** — but the residual v1p.2b left open
  **is** a matching loss, not eligibility, and it is concentrated (82,8% in the feed round, 86,3% in
  5% of turns; max-cardinality gap just 4 tasks/36 eps ⇒ efficiency, not throughput). This answers
  v1p.2b's open *why*: partly floor, a thin slice matching. Report:
  `baselines/2026-08-15/item4_step1_report.md`. 🔴 **The step-2 gate was revised the same day, in
  the plan doc, because step 1's own numbers showed the original single bar was the wrong test.**
  Bounding the prize from step 1: ≈159 walk-steps/ep ⇒ at most ≈159 extra working turns (+11,6% on
  1.365/ep) ⇒ at ~0,42 crop-tile-days/working-turn and v1o.3's ~$31/crop-tile-day, **≈+$2.100/ep
  before any implementation loss** — i.e. **under the old +$3.000 bar before the oracle even runs**,
  which would have made step 2 a formality rather than a measurement. But ④'s value was never mostly
  its own dollars: it is a **precondition**, and the nearest blocked thing is **herd 13 (−$15-21k/ep
  purely on feed logistics)** while step 1 measured **82,8% of recoverable regret in the feed
  round** — the same currency. Step 2 is therefore **two-legged: (1) standalone ≥ +$2.000/ep, OR
  (2) measurable feed-round relief** (saturation <90% on the median day from d9, or
  `animals_underfed_days` −15%); **STOP only if both miss**, and if leg 2 clears, re-run the existing
  `checkpoints/v1s_H2R` under the oracle. Also added to the plan: **arm B (greedy + 2-opt repair)** —
  O(n²), no solver, no new dependency, constraint-safe by construction; **if it lands near the
  whole-pool optimum, plan steps 5-6 collapse** — a mandatory **A→B→C arm order** (A is the strict
  ceiling), and **hot-turn gating** for step 5 (86,3% of regret in 5% of turns ⇒ the matcher need not
  run every turn; the main G-7 lever, its recall checkable offline against step 1's own trace). Brief:
  [docs/plans/item4_step2_prompt.md](docs/plans/item4_step2_prompt.md). **Not a herd retry.** ④ still has to
  re-establish G13 determinism and not re-break `committed` stickiness; §3.3's *"routing-distance
  decoupled from urgency-distance"* stays last in line; and whatever ships has to earn its
  acceptance arm against `meta_route` (v1o.3 passed mirror at p=3,3e-6 and was worth nothing there).
  `pytest tests/` **268 → 275** (+7 `test_v1u_travel_ratio.py`). No `agent/` change, no submission.
- **Deferred item ④ — the offline oracle: ⛔ STOP, item ④ refuted (item ④ step 2, 2026-08-16).**
  `analysis/v1u_oracle.py` **substituted** the optimal matcher into the live agent (swap of
  `agent.policy.assign`, opponent `checkpoints/v1u_base` untouched) and played whole episodes out —
  SMOKE 0-11, both seats, basket, 24 eps/arm, all fresh on 1.32.7. Three arms (A whole-pool optimal /
  B greedy + 2-opt / C feed-only re-match), pre-registered two-legged decision. **All three miss both
  legs ⇒ STOP** (§3.3 row above). The finding is sharper than a bare "doesn't pay": the routing prize
  is **real** — arm A banks **+$4.709/ep, 23/24 seeds**, `worker_turns_working` +5,6%, `crop_tile_days`
  +8,4% (step 1's 4,30% regret converted to dollars) — but (1) **leg 1's trade is unavoidable**: A
  reaches the dollars only by underfeeding (escapes **3→11**, past the ±5 floor), while the buildable
  arm B keeps escapes clean (3→4) but earns just **+$812** (`B/A` = **0,17**, so no "steps 5-6
  collapse"); and (2) **leg 2 moves the wrong way** — feed-round saturation stays **100%** and
  `animals_underfed_days` **rises** on every arm, because a per-turn distance optimum aims freed turns
  at *near* crops, away from the *far* feed round (the 96,3% forced-walk floor is largely the commute
  to distant animals). **④ is refuted as the herd-13 unblock — measured, it is the opposite.** This
  hits the same wall as S3 step 2 from the routing side; the §4.0 profile stands, reaching it with
  *this* planner does not. Promotes the tape (§4.2) to the production route and closes ④ (steps 3-8
  not started). ⚠️ Method note: arm A needed an urgent-sub-round inside each priority tier to stay off
  step 1's pure-distance mirage (+$6.746 → −$954 on seed 0 when urgency is dropped) — any future
  matcher must keep urgency/slack in the cost. `pytest tests/` **275 → 286** (+11
  `test_v1u_oracle.py`). No `agent/` change, no submission. Report:
  `baselines/2026-08-15/item4_step2_report.md`.

- **S4 — first submission of this line made, 2026-08-11:** `55438252` (v1o.2), PENDING, full
  §6bis checklist green. It went in as the **challenger**, holding `55414570` (v1i) as champion
  until the ladder rules on it — the reading recorded here before the run, now executed. The
  differentiation debt in §6bis is cleared: the pair now differs in production, not in
  market-order ordering.
- **T1 — tape shipped as challenger, 2026-08-16:** `55548339`, verbatim replay of public ep
  91456307 seat 0 (Valmorlee), gate 48-0 vs `meta_route` both seats, unpinned holdout median
  $128k IMPROVED, ≫ the $57.360 floor. **The premised WEED repair was refuted, not built:** a new
  farmer/hands no-op scan (`analysis/s2_farmer_noop_scan.py`) measured the donor farm as
  **byte-identical against every opponent** (0 weed/hand collisions — positions are
  opponent-invariant, a dense tape leaves no empty tile for weeds), the end shed is **empty** (no
  unsold sweep), and the entire 7-37% degradation is **realised price** (STRAWBERRY −61% vs a
  competing seller) = the S3-step-3 market overlay, out of scope. So the smallest thing the failure
  map justified was the raw tape. Formal `GO=True` is structurally unreachable for a receipt-less
  tape (its metric gate needs `agent/` mechanism accounting; the *differenced* priced loss is 0,0/ep
  and the tape's absolute priced loss is *below* the bench's). Active pair now **`55548339` (tape) +
  `55438252` (v1o.2)**; `55414570` drops inactive. Route + submission gitignored (§2.4b). Full
  record: `baselines/2026-08-15/t1_repair_justification.md`.

- **v1v — the realised-price spread is the town, not the agent: 🔴 §4.1 half-refuted, S5
  withdrawn, S6 opened (2026-08-17).** Episodes updated to the
  `kaggle/kaggriculture-episodes-2026-08-16` daily dataset (700 episodes). Two results:
  **(1) engine 1.32.7 is LIVE** — `v1t_engine_probe` reads **61/61** as 1.32.7 against 28/28 as
  1.32.6 on the 08-14 dataset, so §1's "not yet live" row closes and every pre-`v1u_base` dollar
  figure is engine-stale. **(2)** `analysis/v1v_shop_demand.py` over **150 episodes / 300 seats**
  decomposes seat-level realised $/unit into between-town and within-town variance and finds
  **99-100% between-town** on STRAWBERRY / WOOL / MILK, with a monotone dose-response against the
  town's shop drain (**STRAWBERRY 13→236, 18×**; MILK 14×; WOOL 5,3×) and **34,0% of towns drawing
  no YARN_STORE**, matching the engine's predicted 34,4%. §4.1's nine-team price table compared
  teams that never shared a market. **What the top actually does:** both seats sell the same basket
  in the same volume in **150/150** episodes, and the winner's whole edge is **1,04-1,06× realised
  price**, worth a median **$2.826** bank gap — against which a **+5% premium edge is +$3.596/ep and
  reaches 52,7% of currently-lost episodes**. `pytest tests/` **286 → 293** (+7
  `test_v1v_shop_demand.py`, which also pin two engine indexing facts: `_town_consume` gets the
  pre-increment step, and step 0 fires the shop *and* town-centre intervals together). No `agent/`
  change, no submission. Report:
  [baselines/2026-08-17/v1v_shop_demand_report.md](baselines/2026-08-17/v1v_shop_demand_report.md).
- **Two competitor notebooks read (markdown/tables only, §2 item 8 respected — no embedded
  `main.py` blob opened, decompressed or executed).** §4.5 records what each is for: a
  Bradley-Terry harness over a **graded, MIT, documented reference ladder** that closes **R4** and
  supplies the earlier-generation bench §2 has always required; an independent confirmation of the
  shop-drain price mechanism; a **measured price on the S6 target** (identical production, market
  layer only, separating by $164-$2.617/ep); the Closer Cleo design that is our own T2 cash-coupling
  STOP with the fix attached; and a **route-reconstruction method** (majority vote over three traces
  of one submission, agreeing at ~99,91% of market decisions) that is the natural upgrade from a
  verbatim tape to a route we can modify.

**The next pass is S6 step 0** — the mandatory Phase 0 that bounds the lever before anything is
built: re-measure the two shipped tapes' premium $/unit against the **same-town** control §4.1b
makes available, decomposed by that episode's drain. If they already sit at the winner's 1,05×,
the stated mechanism is refuted and S6 stops there. That is the T2 lesson applied early — T2 spent
a whole pass on a lever whose size it never bounded first.

**Still open and unchanged:** an L-series ladder diagnostic on the tapes once they have enough
episodes, done exactly as L1/L2 were (§3.2), read against **same-day** opponents — §1's recorded
rating decay (632,2 → 618,4 → 600,2 on a frozen agent, no code change) is why a stored score is
never a comparison.

---

## Appendix A — notebooks audit (2026-08-11)

`notebooks/` is gitignored (large embedded outputs); the durable artefact of each is its markdown
extract in [docs/source/notebooks/](docs/source/notebooks), which **is** tracked — though only after
today's `.gitignore` fix (R3b): the bare `notebooks/` pattern had been swallowing that directory too,
so eight extracts written this session were invisible to git. Deleting a `.ipynb` whose extract
exists loses nothing textual.

⚠️ **Caveat recorded honestly:** refreshing five notebooks via `kaggle kernels pull` this session
**replaced their local copies with output-free source**. For four of them the previous run's
numbers survive in the tracked extract; for `kaggriculture-findings-from-zero-to-top-meta` there
was no prior extract, so that run's outputs are gone locally (the kernel is public and re-runnable).

| Notebook | Decision | Rationale |
|---|---|---|
| `kaggriculture-what-the-top-farms-do-a-live-meta` | **keep + refreshed** | Daily Elo-banded tracker; the single highest-signal source we have. Its `daily_meta-*.json` is now archived in `data/derived/` |
| `kaggriculture-daily-replays-the-live-meta-report` | **keep + refreshed** | Scheduled full-ladder crawl; the only whole-population view |
| `what-actually-wins-on-the-kaggriculture-ladder` | **keep + refreshed** | Scheduled top-of-ladder sample; complements the above at the other end |
| `25-27-strict-future-v27-midgame-meta-reset` | **keep** | Current meta reset; source of the top-30 opening census (§4) |
| `adaptive-farming-strategy-for-kaggriculture` | **keep (new)** | 99 votes, states the route+overlay architecture explicitly — the reference design for §4.3 |
| `kaggriculture-findings-from-zero-to-top-meta` | **keep** | Replay-hunting diary, 74 votes. ⚠️ Embeds a base64+zlib executable blob — **never executed or decompressed**; markdown only |
| `kaggriculture-structured-economic-policy` | **keep** | Independent structural convergence (3 quadrants, 12-13 hands) from a different method |
| `kaggriculture-visualized-what-every-crop-pays` | **keep, do NOT refresh** | Every `viz cell N` reference across `docs/` is anchored to *this* run. Refreshing silently invalidates dozens of citations |
| `kaggriculture-getting-started` | **keep** | Official reference notebook |
| `kaggriculture-rank-your-agent` (read 2026-08-17) | **extracted → `.ipynb` DELETED** | Bradley-Terry harness over a graded, documented, **MIT** ten-agent reference ladder. Closes **R4**, motivated **R22** (now shipped as [harness/ladder.py](harness/ladder.py)), prices the S6 target ($164-$2.617/ep between identical-production agents), and independently confirms the §4.1b shop-drain price mechanism. See §4.5(a) |
| `kaggriculture-3000-socre` (read 2026-08-17) | **extracted → `.ipynb` DELETED** | Majority-vote reconstruction of one submission's policy from **three** of its own traces (~99,91% market-decision agreement) plus drift/obstruction recovery — the upgrade path from a verbatim tape to a route we can modify. Also prices a premium-lead market layer at **+$1.911,9/ep, 60-0-0** when you own the route, which is the same design T2 found inert on a tape. See §4.5(b) |

🔴 **Handling rule applied to both, 2026-08-17, and it is the standing one for any competitor
notebook from here.** Each was extracted with `analysis/nb_extract.py --no-code` to
[docs/source/notebooks/](docs/source/notebooks) — **prose, tables and printed outputs only, code
cells excluded by construction**, so neither extract can contain the base85+zlib `main.py` /
`submission.tar.gz` payload each notebook embeds (verified: zero matches for the blob markers, and
the longest line in each extract is a pandas table). The `.ipynb` files were then **deleted and
never committed** — this repo is public (§2.4b), and committing a competitor's embedded submission
archive would redistribute it. Nothing was decompressed or executed at any point (§2 item 8).

⚠️ **Do not vendor the reference-agent CSVs.** `NOTICE` licenses that dataset's `*.csv` under
**CC BY-SA 4.0** — copyleft, and this repo is MIT. Only `LICENSE`/`NOTICE`/`*.csv` were pulled, to
a scratch directory outside the repo, and **no `.py` agent file was downloaded at all.** Every
engine number we now rely on (shop table, drain rates, floors) is derived from
`engine_reference/` and pinned by `tests/test_v1v_shop_demand.py`, so nothing of theirs needs to
live here.
| `v13-r3-top-meta-order-safe-premium-control` | **keep — regression reference** | The original sell-ahead evidence (31-1, +$2.304 mean margin). Deliberately retained as an **earlier-meta** opponent per §2 |
| `177-180-fresh-top-30-v21-1-conditional-memory` | **keep — regression reference** | v21.1-era top-30. Deliberately retained as the second earlier-meta reference; superseded for *current* meta but still active on the ladder |
| `your-seed-does-not-fix-the-town` | **keep** | Sole independent verification of the shop-unlock RNG coupling (§2.1.1); unique methodology content |
| `44-46-strict-future-top-30-v22-price-impact` | **delete `.ipynb`** | Middle generation between the two references we keep; price-impact content fully captured in its extract |
| `kaggriculture-what-a-turn-is-worth` | **delete `.ipynb`** | $/action table fully digested and *corrected* (it ranks melon #1, which 1.32.6 inverted); extract retained |
| `the-strawberry-field-is-worth-3-847` | **delete `.ipynb`** | 3 votes, single-scenario estimate superseded by our own measured $/tile-day |
| `two-private-bots-beating-kaggriculture-meta` | **delete `.ipynb`** | Its top-5 cluster census is superseded by the fresher v27 census; extract retained |
| `93-wr-vs-kaito-s-v21-1-local-tuning-experiment` | **delete `.ipynb`** | Its claimed 100-episode measurement is **not reproducible** (the recorded run lasts 4s and plays no games) — already flagged as unreliable in `ladder_snapshots.md` |
