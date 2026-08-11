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
> **The strategy, in one line:** replicate the top-30's production profile, freeze it, then win the
> premium-sell race that is the only thing still separating them — §4.3.

---

## 1. Where we actually are

| | Value | Source |
|---|---|---|
| Our best public score | **652,5** (`55383610`, v1h) | `kaggle competitions submissions` |
| Our active pair | `55414570` v1i **632,2** · `55409945` v1m_d2 **626,1** | same |
| Our rank | **2218 / 3811 teams** | `kaggle competitions list -s kaggriculture -v` |
| Ladder #1 | **3187,7** (THUNDER THUNDER) | leaderboard, 2026-08-11 |
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
- The submitted agent can be open-loop (a fixed policy). The *research process* that produced it
  must be closed-loop (falsifiable experiments, not narrative).

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

---

## 3. Carried-forward findings

Everything below was measured, survives the reset, and is not derivable from the code. Where a
number lives in a curated file, this is a pointer, not a copy.

### 3.1 Engine (2026-08-11 re-verification)

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
| **v1o.1 `strawberry_last_plant_day` 16 and 20** | STOP, structural | Both break `clipped_production_ticks` (1) — an animal's yield left uncollected past its cap — and lose $4,1k/$7,9k per episode **while producing more** tile-days. Same mechanism as the row above |
| **v1k** late-season replant window | STOP, −$166,9 (CI spans 0) | Mechanism **worked** (413→539 tile-days, idle 28,2%→23,8%) and paid **nothing** — we filled tiles with a cheap crop. **On the shelf, not disproved:** mandatory re-test with the first increment that introduces a crop >$50/tile-day. |
| **v1l** wheat→carrot by $/tile-day | STOP, −$7.161/ep | See the WHEAT caveat in §3.2(6) |
| **v1m / v1m.2** melon race | STOP at smoke (28 unexplained escapes), then STOP at Ε1 | Ε1 was later re-scored under the delta rule and **passed** → `checkpoints/v1m_d2`, submitted |
| **v1n** fertilizer capture | Closed as measured | 62,7% of the loss is structural; the fixable 28 units are ≈**+$720/ep upper bound** |
| **12-14 animals** | Hard-gate failure, 660-885 escapes | Feed logistics, **not** market saturation, is the ceiling. ⚠️ But the top-30 run **13 (9C+4S)** and build them as a **ramp** (6 by d5 → 12 by d10 → 13), not in one purchase — §4.0. Our screen bought them in one step |
| **shop-adaptive sell floor** | −$1.103 to −$24.762/ep, 0/8 wins | The agent is production-constrained, never glut-constrained; a demand-sized floor has no price to win, only volume to lose |
| **herd re-composition toward cow** | `{8C,2S}` −$5.093, `{10C,0S}` −$6.845 + hard-gate fail | And the damage was **larger** in towns *with* a YARN_STORE ⇒ the constraint is **MILK saturation in mirror**, not the rare buyer |
| **shed-access routing fix** (1.32.5 D26) | Net-negative, reverted | The old `(4,4)` distance over-estimate was accidentally inflating WHEAT PICKUP urgency. Needs routing-distance decoupled from urgency-distance in `assign()` first |

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

### 4.1 The finding that decides the strategy

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

So S3 step 1 gains a stage **1b — protect the FEED pipeline** (`FEED` and its mandatory
`PICKUP WHEAT` predecessor lifted one tier above `WATER`, behind a screenable config flag).
Crew >10, herd >10 and `strawberry_last_plant_day` >12 are **all three** blocked on that gate and
all three become worth re-measuring immediately after it — including the standing v1k re-test
(§3.3), whose trigger condition (a crop above $50/tile-day) MELON will satisfy.

---

**S4 — Freeze, submit, measure on the real ladder.**

Matching the profile is worth roughly **$63-95k and ~3.100 Elo** *if* it transfers. Submit as the
**challenger** and keep our current agent as champion until the ladder rules on it — the two active
slots must stay differentiated in exposure (§6bis), and a profile-matched agent beside our own is
the most differentiated pair we have ever had. Then run an L-series ladder diagnostic exactly as
L1/L2 did.

---

**S5 — Innovate on top of the frozen optimum.** *(the actual goal)*

Once production is a constant we control, the mirror gate becomes meaningful again **because the
population genuinely is the mirror** — 26/30 of the top-30 share one opening. The named target is
§4.1's finding: **strawberry / wool / milk realised price, where the measured spread is 2,75× /
3,70× / 3,49× at identical volume.** Beating Hak's $105,1 strawberry and $192,7 wool is a
well-posed, falsifiable objective, and our own realised prices ($210,62 milk, $196,81 wool) say we
are already good at exactly this.

Candidate levers, all inside §2's method: differentiate *which* premium we win rather than
contesting all three; gate the pre-emption on public-state checkpoints the way the top farms do
(steps 216/240/264); and exploit the one thing a fixed tape cannot do — react when the opponent's
visible farm says their harvest is coming.

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
| **R4** | Build one **older-generation** bench opponent (v21/v22-era statistics) alongside `meta_route` | §2 requires regression opponents from earlier metas; today every bench is the current one |
| **R5** ✅ | **Decided 2026-08-11 by the user: a public replay may seed a route.** Recorded in §4.2, then refined once the rules were read — replicate the measured *profile*, keep the *tape* as a documented option | Competitor *notebook source code* remains out of scope — a separate, undecided question |
| **R10** ✅ | **Rules read** (supplied 2026-08-11). Using replays for development is clearly permitted (§2.4a, §2.6a, §2.11); the exposure is §3.14a "own original work", §2.5/§2.8 winner licensing, and §2.4b redistribution **into this public repo**. Resolved in §4.2 by replicating the *profile* rather than shipping a *tape* | Closes the one item that could have invalidated §4.3. The activity is not prohibited — the exposure is narrow, lands only at the prize stage, and the profile path removes it entirely |
| **R11** | Keep any extracted donor action stream **gitignored and local** | §2.4b forbids redistributing Competition Data to non-participants, and this repo is public |
| **R3b** ✅ | `.gitignore`: `notebooks/` → **`/notebooks/`** | A bare pattern matches *any* directory of that name, so it was also swallowing **`docs/source/notebooks/`** — the tracked markdown extracts that every `viz cell N` / notebook citation in `docs/` points at. Nine older extracts were tracked; the eight added today were silently invisible. The whole "the extract is the durable artefact" argument in Appendix A depended on this |
| **R8** | Decide whether `data/archive/*.py` (the collector chain) should be tracked | `data/archive/` is gitignored wholesale, so `scrape.py` / `repack.py` / `teams.py` / `features.py` are **not version-controlled** — including two bugs fixed today (below). The data is rightly ignored; the code that produces it probably is not |
| **R9** | Two collector bugs found and fixed **in untracked files** (see R8) | (a) `repack.py` copied unconditionally into `data/episodes_dataset/`, a directory that no longer exists — killing the whole chain *after* a successful 22-minute crawl; now guarded. (b) `teams.py` calls `subprocess.run(..., text=True)` and reads `.stdout` — which is `None` when the Kaggle CLI dies printing a non-cp1252 team name. `scrape.py` invokes it with `check=False`, so **`teams.csv` silently stayed five days stale with no error**. Re-run with `PYTHONUTF8=1` → 3.813 teams. The `check=False` is the real defect |
| **R6** | Leave the `MASTERPLAN.md` / `current_phase.md` citations in code comments alone (32 files under `agent/`, `harness/`, `tests/`, `analysis/`) | They are *historical* citations for why a line exists; rewriting them would touch `agent/` (out of scope) and would not make them more true. [docs/INDEX.md](docs/INDEX.md) "Χάρτης παλιών ονομάτων" resolves them, and git has the originals |
| **R12** | **Write the final config comment *before* creating a screen checkpoint.** A comment edited after the screen changes the package fingerprint, so the `stage=dev-screen` artefact no longer keys to the agent being confirmed and `prior_dev_screen_found` goes False at holdout | Cost one full DEV re-run (2 × 96 episodes) in v1o.1 |
| **R13** | **Declare a mechanism for every counter that *can* be non-zero, not only the ones a pinned screen happened to show.** `shed_overflow_burnt` is 0 under `--town-pin basket` and ~290 unpinned, so v1o.1's first holdout pull failed the metric gate on a counter no screen had exposed | Cost a `repeat_confirm_index=1` re-pull. The re-pull changed no code and no config — only the declaration — and both pulls returned identical numbers, but the confirm ledger correctly records it as a second look |
| **R14** | ⚠️ **`checkpoints/` is gitignored (`.gitignore:11`), which contradicts the invariant the directory exists to enforce.** [harness/checkpoint.py](harness/checkpoint.py) records (review H2) that checkpoints were *moved out of* `runs/` precisely because being gitignored "erased the only record of every accepted regression baseline from git history" — and then the same thing was done to `checkpoints/`. Every accepted baseline v0…v1o_2 exists only on this disk. Not changed unilaterally: un-ignoring it commits ~20 copies of the agent package, which may well be the deliberate trade. **Needs a decision, not a silent fix** | The same class of bug as R3b, and with the same consequence: an argument the repo relies on ("immutable, verifiable baselines") is not actually true on disk |
| **R7** | Unresolved: submission `55387820` (2026-08-09 18:58, score 613,0) corresponds to no checkpoint or gate in this repo; its description ("4th attempt…") is hand-written, so it was almost certainly a manual upload | It occupied an active slot and pushed v1g out. Harmless, but the two active slots are the final-ranking lineup |

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

⚠️ **Standing debt:** the active pair is currently `55414570` (v1i) + `55409945` (v1m_d2), which
differ only in market-order emission ordering — same herd (4C/6S), same tiles, same sell-side
thresholds. That is the exact pattern the rule warns about. Θ1 (§3.2.8) measured that **no
sell-side lever can fix it**; differentiation has to be productive. §4.3 resolves this directly —
a profile-matched agent beside our current one is the most differentiated pair we have ever had.

---

## 7. Where this stands

*(Updated 2026-08-11 (β). The paragraph this replaces — "nothing under `agent/` has been
touched" — was true up to and including S1/S2; it no longer is.)*

The plan is set and running: **§4.3 S1 → S5, replicate → freeze → innovate**, with the target
profile measured from 120 current-engine seats rather than guessed. **R10 is closed** — the rules
were read, using replays for development is clearly permitted, and §4.2 routes around the one
clause that would have bitten (§3.14a) by replicating the profile rather than shipping someone
else's tape.

- **S1 ✅ and S2 ✅** (2026-08-11): the target profile reproduces across 9 teams with near-zero
  structural spread (`data/derived/b3_target_profile.json`), and S2's kill criterion did **not**
  fire — 0/18 donor matchup-seats fell below the $57.360 floor.
- **S3 step 1 — in progress.** Two increments gated and accepted (`checkpoints/v1o_1`,
  `checkpoints/v1o_2`, both `GO=True` on unpinned holdout); two STOPs recorded in §3.3. Crop
  tile-days **413 → 562-612** against a target of 1.316; idle unit-turns **28,2% → 16-18%**.
  Live `main.py` ≡ `checkpoints/v1o_2`, `pytest tests/` **229 passed**.
- **Next: S3 step 1b — protect the FEED pipeline from crop watering.** Not on the original list;
  named by three independent measurements this session (§4.3). Herd size, crew size and the
  strawberry replant window are **all three** blocked behind that one gate, so it is worth
  strictly more than any of them.

**No Kaggle submission has been made from this line.** The two active slots are still
`55414570` (v1i) + `55409945` (v1m_d2), and the §6bis differentiation debt is unchanged — but
`v1o_2` is now the most differentiated challenger this repo has ever had (1,4× the crop
tile-days of either active submission), which is what S4 exists to exploit.

One thing to settle before S4: whether the profile-matched agent goes into the **champion** or
**challenger** slot on first submission (§6bis). My reading is challenger, holding our current
agent as champion until the ladder rules on it.

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
| `v13-r3-top-meta-order-safe-premium-control` | **keep — regression reference** | The original sell-ahead evidence (31-1, +$2.304 mean margin). Deliberately retained as an **earlier-meta** opponent per §2 |
| `177-180-fresh-top-30-v21-1-conditional-memory` | **keep — regression reference** | v21.1-era top-30. Deliberately retained as the second earlier-meta reference; superseded for *current* meta but still active on the ladder |
| `your-seed-does-not-fix-the-town` | **keep** | Sole independent verification of the shop-unlock RNG coupling (§2.1.1); unique methodology content |
| `44-46-strict-future-top-30-v22-price-impact` | **delete `.ipynb`** | Middle generation between the two references we keep; price-impact content fully captured in its extract |
| `kaggriculture-what-a-turn-is-worth` | **delete `.ipynb`** | $/action table fully digested and *corrected* (it ranks melon #1, which 1.32.6 inverted); extract retained |
| `the-strawberry-field-is-worth-3-847` | **delete `.ipynb`** | 3 votes, single-scenario estimate superseded by our own measured $/tile-day |
| `two-private-bots-beating-kaggriculture-meta` | **delete `.ipynb`** | Its top-5 cluster census is superseded by the fresher v27 census; extract retained |
| `93-wr-vs-kaito-s-v21-1-local-tuning-experiment` | **delete `.ipynb`** | Its claimed 100-episode measurement is **not reproducible** (the recorded run lasts 4s and plays no games) — already flagged as unreliable in `ladder_snapshots.md` |
