# ROADMAP — Kaggriculture

> **The plan, not the diary.** This file holds *what we are doing next, what decides it, and what
> must not be re-run*. It is technical and forward-looking by construction.
>
> **Where the rest lives:** per-pass narrative → [memory.md](memory.md) · per-pass measurements →
> `baselines/<date>/*.md` · engine deviations → [docs/reference/engine_deltas.md](docs/reference/engine_deltas.md)
> · full history → git. **A pass touches this file only to change the plan, a gate, or a standing
> rule.** It does not add a session entry here.
>
> *Restructured 2026-08-20 from 2.906 lines. What was deleted is narrative, superseded rows and a
> pass-by-pass log — all of it in `memory.md` and git. Nothing measured was dropped: every STOP
> keeps its row, compressed to its mechanism and its number.*
>
> Engine ground truth: **`kaggle-environments==1.32.7`**, byte-mirrored in
> [engine_reference/](engine_reference). Where docs and engine disagree, the engine wins.

---

## 1. Where we are — 2026-08-20

| | Value |
|---|---|
| **Active pair** | `55586926` **ReCurSiON reconstruction — 1.879,9 / rank 924 of 5.501**, 181 episodes, frozen 08-17 22:29 · `55575305` **Ueddy tape — 1.323,9**, 120 episodes, frozen 08-17 09:24 |
| **Next eviction** | by **date** ⇒ the next upload drops the **Ueddy tape** and keeps the reconstruction. No protective re-upload needed |
| **Converged win rate** | **43,4%** (controlled, past the placement window). By opponent band: **54% / 41% / 38%** at <1.800 / 1.800-2.100 / 2.100+ |
| **Ladder top** | #1 Ryo Hasegawa **3.147,0** · #2 tetsuya 3.095,3 · #3 Arman Tuganbaev 3.053,1 · #4 Crop Dusta 3.017,2 · #5 カワシギ 2.988,3 · **#9 ReCurSiON 2.915,8** (our donor, frozen 08-14) |
| **The gap** | **1.036 points / 915 places** to our own donor. Measured, not inferred — §1.1 |
| **Deadline** | **2026-09-30 23:59 UTC** (41 days). Final ranking = one Bradley-Terry tournament over the ~2 weeks of episodes played *after* it, using whatever sits in the two slots |
| **Prizes** | 10 **equal** $5.000 prizes, places 1-10 ⇒ the target is **stable top-10**, not #1. A high-variance 3.200 is worth less than a steady 3.050 |
| **Gates** | **2.800+** = minimum bar (below it we are still copying) · **3.000+** = "top-5 tactics replicated"; only above it is originating our own tactics the highest-value work |
| **Local suite** | `pytest tests/` **358 passed, 3 failed** — the 3 are the known `test_v1h2d_*` cases (pre-existing, expected) |

### 1.1 The gap is real strength — all four escape hatches are closed

Our route is a **faithful open-loop copy** of a rank-9 agent and plays at rank 924. Every way of
explaining that away has been measured and rejected:

| Escape hatch | Verdict |
|---|---|
| *"the copy is lossy — the vote erased the donor's conditioning"* | ⛔ closed channel-by-channel: market layer town-invariant (§6 row 25), production residual town-reactive but worth **+6,2 rating points** (rows 26-27), loss tail owned by the town's shop draw (row 27) |
| *"we're underrated — the 65% win rate says so"* | ⛔ 65% was the **placement burst**. Converged and controlled: **43,4%**, falling to **38%** vs 2.100+ |
| *"our score is deflating and the donor's isn't"* | ⛔ both deflate; the rates are **band-local**; our rank *rose* while our score fell |
| *"early-draw luck — byte-identical copies finish 300-1.400 apart"* | ⛔ an unlucky copy would still **win**. We win 38% against the band we need to beat |

**Open and unexplained:** *how* a faithfully copied route loses 1.036 points to its donor. Every
desk instrument this repo owns compares traces to each other and reports fidelity. **None has ever
scored our route against a real ladder opponent.** That is §7.

---

## 2. How to read a ladder number

Adopted 2026-08-20 from the #1 team's public write-up, **confirmed and corrected** on our own data
(`baselines/2026-08-20/s7_leg0_report.md`, `analysis/s7_ladder_census.py`,
`tests/test_s7_ladder_census.py`). Violating each of rules 2-4 produced a wrong headline in this
document.

1. **A new submission starts at 600,1 and plays a burst** — measured here at **14,60 episodes/hour
   for ~5 hours (73 episodes)**, then **0,7-2,0/h** (~24-48/day steady state).
2. 🔴 **Never judge inside the first ~70 episodes.** The burst is where the win rate lies: ours read
   **66,1% / 50,8% / 46,7%** across thirds while the opponent's median board score climbed
   **1.212 → ~1.950**. Nothing about the agent changed — matchmaking caught up. Judge at 100+, and
   treat moves under 50 points as noise.
3. 🔴 **Absolute score deflates pool-wide; the invariant is rank.** Over 2,04 days (5.129 → 5.501
   teams, +376 new, **26% of teams re-submitting**) the score at a **fixed rank slot** fell
   **−39/day @#25, −36 @#100, −49 @#400, −26 @#900**, while #1.200 and below *gained*. Same signal
   in the official episodes-index manifest: `top_avg_score` 3.218 → 3.134, `median_avg_score`
   3.068 → 2.893 (08-09 → 08-19). **We lost 32,9 points and gained 15 places; カワシギ lost 200
   points and 4 places.** A score delta without a rank measures nothing.
4. 🔴 **Frozen decay is monotone in the rating band** — median points/day, frozen teams only
   (n=3.792): **2800+ −69,6 · 2400-2800 −66,9 · 2000-2400 −73,5 · 1600-2000 −56,4 · 1200-1600
   −35,9 · 800-1200 −11,0 · 0-800 −2,8.** Two agents at different heights bleed at different rates
   **by construction**, so a decay figure is comparable only within a band. (A delta is only decay
   at all if `LastSubmissionDate` is unchanged — necessary, and not sufficient.)
5. **Only the latest 2 submissions play**; a third retires the oldest; eviction is by **date, not
   score**; those two run the post-deadline Bradley-Terry. An inactive submission plays **zero**
   episodes — measured 2026-08-17, and the official overview's *"every bot continues to play"* is
   boilerplate that is false here.
6. **A re-submission costs ~1.000 points and hundreds of places** while it re-places. Priced on the
   live board in one week: **Ueddy −970 / −779 places · Peter Parker −365 / −345 · Kaito Fukami
   −1.217 / −1.426.** Never re-submit an unchanged agent; a re-roll buys a nicer live number and
   changes **nothing** in the final.
7. **Any ladder-side criterion states an episode count, never wall-clock**, and two scores are
   comparable only **on the same day, at comparable episode counts, in the same rank neighbourhood**.
8. **The live score is a diagnostic. The product is the two submissions in the slots on 09-30.**

---

## 3. Method — standing rules

- **Never conclude a strategy is "optimal."** The only defensible claim is: *this beat that specific
  challenger, under this test, against these opponents.*
- **The loop:** real losses → one concrete failure mechanism → a challenger targeting it → tested
  across multiple opponents and **both seats** → reject most → freeze the winner → re-validate on
  later/held-out episodes.
- **The framing that generates a pass** is not *"build the optimal agent"* but ***"where does this
  agent lose, and what experiment could disprove the proposed improvement?"*** Every brief starts
  from a measured loss and carries a pre-registered way to be wrong.
- 🔴 **Price a lever in rating points — and price the *programme* too (added 2026-08-20).** The
  standing rule was *divide the plausible dollar gain by ~$253/ep and compare it to the gap*, for a
  **marginal** increment only; it does **not** apply to a change that alters which opponents you
  beat (the T1 tape converted at several times that rate). **The failure this rule did not prevent:**
  step 2a bounded the entire "what did the vote erase" programme at **+2,4 rating points on day
  one**, and five further passes (2b, 2b-0.5, 2c, 2d, 2e) confirmed that same bound from five angles
  against a **1.036-point** gap. The bound was applied inside each pass and never across them.
  **A programme gets the same pre-check as an increment, and a programme whose ceiling is under 1%
  of the gap does not get a second pass.**
- 🔴 **A pass ends in an upload, or it does not get run (added 2026-08-20).** Seven consecutive desk
  passes ran between 2026-08-17 and 08-20 with **zero** uploads and ~15 unused slots. Diagnostics
  earn their place only as a **time-boxed gate at the front of a shipping pass**, carrying a
  pre-registered *"if this reads X, ship anyway."*
- **Retain earlier meta generations as regression opponents.** A change that only beats the latest
  top-30 snapshot can lose to older agents still active on the ladder. Confirmed externally, with a
  submission's rating attached: §5.3(c).
- **Bound a lever's surface area on paper before building it, and prefer the engine to the
  experiment when the engine can answer.** State it in the brief: *what is the maximum this rule
  could earn if it fired perfectly on every opportunity in the recorded data?*
- **Never rank candidates on a number the environment dominates, even for triage.** Ranking donor
  teams by median reward ranks their **town luck** (§5.2) — the good one hides in the noise.
- **The submitted agent may be open-loop.** The *research process* that produced it must be
  closed-loop — falsifiable experiments, not narrative.
- **A confirmed mechanism and a viable increment are different claims.** Every report states both,
  in that order: *(a)* what the arm proved about the game, *(b)* whether it is takeable. Never let
  (a) stand in for (b).
- **A STOP is not final until its own root cause's implied control has been run.** Twice, a stated
  root cause was refuted by the control it implied (§6 rows 18, 19).

### 3.1 Experimental protocol

1. **Both seats, always.** `_end_of_day` builds **one** per-day RNG, spends it on `_spawn_weeds` for
   player 0 then player 1, and only then draws the shop unlock. A one-tile difference on **either**
   farm re-rolls the whole remaining shop sequence. Seat 0 and seat 1 are not symmetric on the same
   seed.
2. **Classify the knob before every A/B.** *Can this change alter how many tiles are occupied on any
   night?* **No** (order/rate/threshold of market orders only) → *market-only*, a fixed seed is a
   genuine controlled experiment. **Yes** (labour/crew, planting, harvest, DIG, BUY_LAND, animal or
   structure placement, routing) → *occupancy*, requires `--town-pin basket` on **both** arms.
   **Don't know** → treat as occupancy. Pinning **reduces, does not eliminate** (~19% of noise sd);
   the final holdout-confirm always runs **unpinned**. Only `--town-pin basket` is valid from 1.32.6.
3. **Screen → confirm, never "keep the max."** Dev seeds 0-47 screen · holdout 100-147 confirm only
   (no tuning decision ever touches them) · smoke 0-11 for controls (never GO) · `CONFIRM2_SEEDS`
   200-247 **burned**. Game-to-game spread is ~19% of median bank (extremes to 950%), so **24-48
   seeds is the floor, not a luxury**.
4. 🔴 **Acceptance is four numbers, in this order** (amended 2026-08-20 — the old order led with
   `median_bank` and was wrong):
   1. **Per-opponent W/L, per seat** — a row per opponent, **never** a pooled figure.
   2. **Bradley-Terry over the bench** ([harness/ladder.py](harness/ladder.py), `--round-robin`).
   3. **`median_bank`** — diagnostic.
   4. **`mean_diff`** in mirror — regression detector only.

   **Why:** the live Elo fits W/L; the final Bradley-Terry fits W/L. Step 2e measured
   `r(premium drain, bank) = +0,605` — **a third of our bank variance is the town's random shop
   draw**, which lifts *both* seats and cancels in W/L. Against the win rate that same variable is
   flat-to-inverted (drain 5 → 71%, 8 → 48%, 13 → 43%). **The largest component of the metric we led
   with is invisible to the metric we are judged by.** An arm that raises mean bank while turning two
   wins into losses against the strongest bench opponent is a **loss**.
5. **Selection key when panels disagree** (adopted from §5.3(c)): **worst panel → worst seat →
   overall wins → tail log-ratio → margin.** This stops a large easy panel hiding a
   generation-specific collapse.
6. **Priced loss, judged on the difference.** Structural counters stay hard-zero
   (`clipped_production_ticks`, `plant_decay_units_lost`, unexplained no-ops, market-sim aborts,
   ≤2% low-price sales). Loss counters are priced (`animals_escaped` $1.000, `shed_overflow_burnt`
   $150/unit, weed-lost tile $300) and judged as `priced_loss_delta = max(0, a − b)` ≤10% of
   `mean_diff` **and** ≤$500/ep, **only** on `--arm-role acceptance`. Mirror runs
   `--arm-role regression`: $-verdict + structural, never a priced budget. A non-zero counter needs a
   written mechanism — "don't know why" is a bug and a STOP. **Price a counter even when it passes**;
   a counter inside its budget is still a bill. And **declare a mechanism for every counter that
   *can* be non-zero, not only the ones a pinned screen happened to show** — `shed_overflow_burnt`
   reads 0 under `--town-pin basket` and ~290 unpinned, which is how v1o.1 first failed its holdout
   on a counter its whole screen had never seen.
7. **Never bump the engine or edit `agent/` while a gate is running** (the agent is imported per
   worker process). Writing `.md` is always allowed.
8. **Engine-bump detector, no install:** `pip index versions` → `pip download --no-deps
   --no-binary :all:` → `diff` the `.py` **and the `.json`** (`townCenterSellInterval`,
   `turnsPerDay`, `maxMarketOrdersPerTurn`, `shedCapacity` all live in the json).
9. **Three tooling traps, each paid for once.** *(a)* **Write the final config comment *before*
   creating a screen checkpoint** — a comment edited afterwards changes the package fingerprint, so
   the `stage=dev-screen` artefact no longer keys to the agent being confirmed. *(b)* **Two packages
   both named `main.py` collide** under `harness.play`'s filename sanitizer; give them distinct
   paths. *(c)* **A config-override builder must REPLACE the target key and assert the effective
   value, never insert it** — inserting ahead of an existing default produces a dead flag that looks
   like a finding.
10. **A ratio is a diagnostic, never a target.** Any *"share X falls below N%"* criterion is
   satisfiable by shrinking the denominator. Throughput increments are judged on **absolute
   `worker_turns_working` with `crop_tile_days` held flat (±3%)**.
11. **Report the unflattering panel.** A blind post-freeze panel is published unchanged, even when it
    ties or loses (§5.3(c) does exactly this).

### 3.2 Data handling

- **Public episode replays are game data and may be used, including as a route source.** Provenance
  `(episode_id, seat, team, sha256)` is recorded whenever one is used.
- **Competitor notebook *source* is never opened, extracted or executed** — the `main.py` /
  `submission.tar.gz` blobs those kernels embed are their code, not game data. Markdown, tables and
  printed statistics are read freely as evidence. Standing procedure: extract with
  `analysis/nb_extract.py --no-code` into [docs/source/notebooks/](docs/source/notebooks), verify
  zero blob markers, keep the `.ipynb` out of git.
- **This repo is public.** Routes, packages, replays and derived data stay **gitignored**; `gates/`
  tracks `results.json` only (aggregates, no action streams). Every derived artefact carries its own
  **verdict string**, so a stale flag cannot be misread as a GO — and when a pass corrects its own
  pricing basis, the writer is re-run, not just re-printed.

---

## 4. Engine ground truth (1.32.7)

- **`TOWN_CENTER_DEMAND_SCHEDULE` is gone** (flat `-= 1`), `townCenterSellInterval = 24` (1
  tick/day), shops are drawn **with replacement**, `MAX_SHOP_INSTANCES = 8`. Consequences: the town
  centre absorbs **30 units/product/season instead of 140 (−79%)**, `E[distinct shop types] = 5,25`,
  **`P(a given type absent) = 34,4%`**, `P(all 8 present) = 0,24%`.
- **1.32.7 is live** (verified 61/61 episodes in the 08-16 dataset). Market-only, scarcity-side only,
  CARROT/TOMATO/EGG only, via a new `hinge` shape; TOMATO/EGG are a strict no-op below their knee,
  **CARROT changed from depletion 1 upward**. The glut branch is untouched for all nine products.
  **Everything measured below `checkpoints/v1u_base` was measured on 1.32.6 and its dollar figures
  are engine-stale**; the mechanisms still bind.
- **Step 718 is the last executable turn** (`interpreter` sets `DONE` at `step >= episodeSteps-2`).
  A `SELL` *at* 718 executes. Endgame plans target 718, not 719.
- **One HIRE is one market order and `maxMarketOrdersPerTurn` is 10**, and hands are wiped nightly,
  so a crew rebuilt entirely in hour 0 cannot exceed 10 however high `hands_target` is set.
- Deviations that keep costing games (catalogue D1-D28 in
  [engine_deltas.md](docs/reference/engine_deltas.md)): planting day counts as the first unwatered
  day (D4) · melon caps at age **10** (D5) · strawberry yields **exactly 4 times** then becomes a
  weed (D6) · the shed is **not a tile** (D11) · invalid actions are **silent no-ops** (D15) · floor
  sales add no inventory (D18) · `PLANT` is atomic — two units competing for one seed means
  **neither** plants (D21) · `CARE` banks **+1**, not the documented +2 (D1).
- ⚠️ **The live discussion cannot be checked programmatically** (client-rendered SPA; the API exposes
  no discussion resource). The pip-version + byte-diff check is the only automatable tripwire;
  reading the forum stays manual.

---

## 5. What the top of the ladder actually does

### 5.1 The target profile — 120 seats, current engine

| Quantity | Median per seat |
|---|---|
| Money d5 / d10 / d15 / **d20** / d24 / end | $516 / $4.863 / $16.720 / **$48.560** / $63.129 / **$82.747** |
| Planted tiles d10 / d15 / d20 / **d24** / d27 / d29 | 56 / 62 / 60 / **61** / 45 / **1** |
| Hands d5 / d10 / d15 / d20 / d29 | 3 / **14** / 9 / **14** / 10 |
| Animals d5 / d10 / d15 / d20 / end | 6 / 12 / 12 / 12 / **13** — peak **8-9 COW + 4-5 SHEEP** |
| Quadrants | **3** — second on day **6**, third on day **10**, SE never |
| Crop tile-days | **STRAWBERRY 577 · WHEAT 559 · MELON 180** (~1.316 total) |
| Sell calendar (first day, batch) | WHEAT d5/6 · FERT d2/4 · WOOL d6/**10** · MILK d9/6 · MELON d10/6 · STRAWBERRY d14/**14** |

⚠️ **Our own planner cannot reach the 13-animal row** — blocked on feed logistics, not config or cash
(§6 rows 11, 12, 20). The profile is not refuted; reaching it with `assign()`'s routing is.

### 5.2 The town, not the agent

- **99-100% of seat-level realised $/unit variance is *between-town***, with a monotone dose-response
  against the town's shop drain (STRAWBERRY **18×**, MILK 14×, WOOL 5,3×) and **34,0% of towns
  drawing no YARN_STORE** (matching the engine's predicted 34,4%). Any cross-team price comparison
  across different episodes is measuring the environment.
- **The top of the ladder is a mirror match**: both seats sell the same basket in the same volume in
  **150/150** top episodes, and the winner's edge is **1,04-1,06× realised price**, worth a median
  **$2.826** bank gap.
- 🔴 **And that gap moves no wins.** The shop draw is **common-mode** — it lifts both seats. Step 2e:
  `r(drain, bank) = +0,605`, monotone $40k at drain 3 → $118k at drain 13. S7 leg 0, same episodes:
  the win rate is **flat to inverted** against the same variable. This is why §3.1(4) demotes
  `median_bank`.
- **MELON is the only product with a real within-town contest** (65% of its variance, **zero** shop
  buyers in 150/150 towns, flat ~$144 whatever the draw) — and it is our largest revenue hole
  (−$27.263, 0 units against 132).
- ⚠️ Shop *count* and shop *timing* are confounded and were never separated (a YARN_STORE on day 3
  drains far more than one on day 24).

### 5.3 External sources, and what each is for

**(a) `kaggriculture-rank-your-agent`** (Rayk Kretzschmar) — a Bradley-Terry harness over a graded
**MIT** ten-agent reference ladder. **Tiers 0-5** ($3.000 → $46.211) share a byte-identical scheduler
and differ only in a `POLICY` dict, so every gap is an *economic* decision — adopted as bench
opponents (fetched into the gitignored `harness/bench_agents/reference/`). **Tiers 6-9** share one
field plan and differ **only in the market layer**, separating by **$164-$2.617/ep** — a measured
price on a market-layer change, retained as a citation; their code is **not** used (their base85
`_TRACE` is outside the MIT grant, and the dataset's `*.csv` are CC BY-SA, which this MIT repo does
not vendor). Independently confirms the shop-drain price mechanism.

**(b) `kaggriculture-3000-socre`** (HarvestForge-X / V16-RC5) — the **majority-vote route
reconstruction** we built `55586926` from: compare *n* public traces of one submission, take the
per-decision modal action. Prices its own premium-lead market layer at **+$1.911,9/ep, 60-0-0** when
you own the route. Its adaptive layer (worker-count adaptation + obstruction recovery) is **not** in
our submission.

**(c) `106-130-multi-generation-v36-robust-hybrid`** (Kaito Fukami, read 2026-08-20) — the most
methodologically useful competitor document read here:

1. **A measured price on tuning against the current top-30 only.** Their v35 lost to *"a near-v18
   actor with a new market overlay"* — an old public generation returning with a small overlay — and
   to an unrelated high-expansion animal route. *"Public agents do not disappear when a new Top-10
   family arrives."*
2. **Three disjoint evaluation surfaces:** a top-10 diagnostic, a post-freeze strictly-later capture,
   and **their own live opponents — "the actual deployment neighbourhood."**
3. **The selection key** adopted verbatim in §3.1(5).
4. 🔴 **State aliasing.** A public-state kNN continuation router, grouped-OOF-validated with every row
   of the target submission excluded, won selection **70/78 vs 67/78** and **lost post-freeze 31/38
   vs 33/38**. *"More classifier confidence cannot recover future information that is not yet
   observable."* They deleted it from the shipped artifact. **Every "recover the donor's conditioning
   rule from replays" arm is this shape.**
5. **Architecture:** one coherent 719-action open-loop backbone + four bounded closed-loop
   components — (i) transaction/weed-legality recovery, (ii) SELL reordering on price + projected
   shed + public opponent exposure, (iii) near-clone preemption gated on **24** near-identical public
   states, (iv) a **WHEAT market maker** capped at q10 on capital above a $500 floor, two feed days,
   two investment turns and shed headroom. **(i)-(iii) we have measured and bounded; (iv) this repo
   has never examined.**
6. **Artifact contract:** route hash, byte size, latency mean/p99, parity call count, and the archive
   SHA reproduced **under two output filenames** so a gzip filename header cannot fake determinism.

⚠️ **Do not read a competitor's live score as evidence about their newest version** — Kaito sits at
1.542,7 / #1.489 having re-submitted that morning, from #63 / 2.759,7 two days earlier (§2 rule 6).

**(d) The #1 team's rating-mechanics write-up** — adopted, confirmed and corrected in **§2**.

---

## 6. Measured STOPs — do not re-run without new data

One line each: the increment, the number, and the **mechanism** that makes it bind. Full reports in
`baselines/`; narrative in `memory.md`.

| # | Increment | Result and the mechanism that binds |
|---:|---|---|
| 1 | **v1c** land expansion, ×3 | STOP. Capacity/routing, not land, is the blocker |
| 2 | **v1j** wheat 12→24 tiles + crew 10→12 | STOP −$759. The +2 hands were never hired: **one HIRE = one market order, cap 10/turn**, hands wiped nightly ⇒ 10→12→14 is byte-identical. Not a cost problem |
| 3 | **v1o.2 `sw_hands_target` 12** | STOP on the priced gate. Best dollars of its session (+$4.144,7, 82-14) but escapes 87 vs 32 ⇒ `priced_loss_delta` $477,6 against a $414,5 budget. **12 hands on ~594 crop tile-days emit more priority-0 WATER than the same tier's FEED survives** |
| 4 | **v1o.3 animal-upkeep protection**, 7 variants | STOP on the acceptance arm, twice. Best variant took escapes **13 → 0** and paid in `crop_tile_days` 612 → 574: 13 escapes ≈ $135/ep, that production ≈ $1.180/ep. **Any reallocation toward animals loses at our production level.** ⚠️ Its *mirror* arm read +$4.877,5 IMPROVED, p=3,3e-6 — the sharpest mirror-is-a-ceiling demonstration in the repo |
| 5 | **The feed round never closes** (standing fact) | ≥1 animal is unfed for **100% of the hours** of a median day from d9 (≥70% from d7). There is no quiet moment ⇒ **any reordering inside tier 0 is strictly zero-sum** |
| 6 | **v1o.1 `strawberry_last_plant_day` 16 / 20** | STOP, structural. Both break `clipped_production_ticks` and lose $4,1k/$7,9k **while producing more** tile-days |
| 7 | **v1k** late-season replant window | STOP −$166,9 (CI spans 0). Mechanism worked (413→539 tile-days) and paid nothing — we filled tiles with a cheap crop. **On the shelf: mandatory re-test with the first crop >$50/tile-day** |
| 8 | **v1l** wheat→carrot by $/tile-day | STOP −$7.161/ep |
| 9 | **v1m / v1m.2** melon race | STOP at smoke (28 unexplained escapes), then at Ε1. Ε1 later re-scored under the delta rule and **passed** → `v1m_d2`, submitted |
| 10 | **v1n** fertilizer capture | Closed as measured: 62,7% of the loss is structural; the fixable 28 units are **≤+$720/ep** |
| 11 | **12-14 animals** (one-step purchase) | Hard-gate failure, 660-885 escapes. Feed **logistics**, not market saturation |
| 12 | **herd 13 (9C+4S) on the C2 reserve**, 3 arms | STOP at SMOKE, **−$15-21k/ep, 0-12 seeds**, and **the ramp is not the lever**. The 3 animals past ten sit at Manhattan 7,7,8 from the shed (herd Σdistance 37→59, **+59%**); the C2 reserve pays the day-0 **cash** half in full, **nothing pays the logistics half**. Crop tile-days −36% |
| 13 | **shop-adaptive sell floor** | −$1.103 to −$24.762/ep, 0/8. We are **production-constrained, never glut-constrained**: a demand-sized floor has no price to win, only volume to lose |
| 14 | **herd re-composition toward cow** | `{8C,2S}` −$5.093 · `{10C,0S}` −$6.845 + hard-gate fail. Damage was **larger** in towns *with* a YARN_STORE ⇒ the constraint is **MILK saturation in mirror**, not the rare buyer |
| 15 | **shed-access routing fix** (D26) | Net-negative, reverted. The old `(4,4)` over-estimate was inflating WHEAT PICKUP urgency; needs routing-distance decoupled from urgency-distance first |
| 16 | **v1p.1 herd compaction** | STOP at SMOKE −$875,4. Escapes 2→48, **exactly 2 in all 24 orientations**, always the same two COW, always day 2 |
| 17 | **v1p.2 zone assignment** | STOP at SMOKE −$6.966,0 (p=4,9e-4). `worker_turns_moving` barely moved and `plant_decay_units_lost` 0→17 — the partition has no cross-turn memory and re-zones a `committed` unit out of its own in-flight task |
| 18 | **v1p.1b, both untested controls** | STOP, both. Arm A1 (COW on those tiles) still escaped 48 ⇒ **refutes v1p.1's own type-blind-race root cause**; arm B (`carrot_tiles` 3→1 alone, zero geometry change) escaped 12 ⇒ a **second, independent** mechanism. Closes the "convert a CARROT tile to compact the herd" family: the ten claimed PASTURE slots are already the ten nearest of the 13 available |
| 19 | **v1p.2b sticky zone assignment** | STOP at SMOKE −$2.688,6. Fixed both structural symptoms and `worker_turns_moving` still barely moved ⇒ **the constraint is not which tasks a unit is offered** |
| 20 | **deferred item ④ — min-cost matching oracle**, 3 arms | STOP; **④ refuted** as the herd-13 unblock. The prize is real — whole-pool-optimal banks **+$4.709/ep, 23/24** — but reaches it by underfeeding (escapes 3→11); the *buildable* arm earns **+$812** (B/A = 0,17); and **leg 2 moves the wrong way**: a per-turn distance optimum aims freed turns at *near* crops and defers the *far* feeds, so `animals_underfed_days` **rises** on every arm. ⚠️ Any future matcher must keep urgency/slack in the cost (+$6.746 → −$954 on seed 0 without it) |
| 21 | **T2 market overlay on the shipped tape** | STOP at SMOKE. **The tape's realised STRAWBERRY price is pinned by shed capacity, not a re-timeable calendar**: the shed runs at 98/100, metering strawberry overflows it, burns WOOL/FERT and rejects the `BUY_PRODUCT WHEAT` feed deposit ⇒ escapes 0→11, bank −$3-4k/ep — *while winning* the strawberry $/u sub-metric. ⚠️ **Donor-specific**: the same design earns +$1.911,9/ep for an agent that **owns** its route |
| 22 | **C-A, in-place SELL reordering ("the Cleo rule")** | REFUTED before being built, analytically **and** empirically: per-slot lockstep across players and per-product pools mean the reorder cannot move realised price. The engine answered before the experiment ran |
| 23 | **S6 step 2a — own-farm repair** | STOPPED at Phase 0. The loss is **100% WHEAT on the same 5 tiles**, ceiling **$599/ep**; free half **$0-241** (no idle unit is ever on a loss tile); full recovery **+2,4 rating points / 0,09% of the gap** |
| 24 | **S6 step 2b — "restore the erased sell-timing"** | REFUTED on paper, no episodes. ReCurSiON's strawberry rule is a **fixed global calendar** (hold, release into the hour-0 town-centre pulse), invariant across 50 towns: 46/50 sell an identical **290 units**; at step 336 all 50 sell exactly 6 while price spans $151-$230. corr(units, own shed) **+0,92** vs corr(units, shop identity) **+0,02**. **The vote already reproduces it** |
| 25 | **S6 step 2c — the family, channel-wide** | BRANCH (i): **every** market channel is town-invariant. **40% of towns never draw a YARN_STORE**, yet at all 20 contested wool steps the modal action is identical across the drain split. MILK never presents a zero-drain population; WHEAT's residual is a fixed 4-trace variant; FERTILIZER is in no `SHOPS` entry ⇒ analytically eliminated. **Family CLOSED channel-wide** |
| 26 | **S6 step 2d — the production channel** | BRANCH (iv): the 88 production-disagreement steps **are** town-reactive (per-town weed spawns → the hands DIG, re-PLANT and WATER by real dry state, re-syncing one op later; farmer op differs 0/88; 62% of hand-slot disagreements stand on a disjoint tile) — **a genuine closed-loop rule the vote cannot carry**, bounded at **$597/ep ⇒ +2,4 pts**. ⚠️ Its bank-gap decomposition blamed the opponent pool; **that gloss is circular** — Kaggle pairs by rating |
| 27 | **S6 step 2e — the loss tail, re-priced in wins** | BRANCH (i)+(iv), replicated on 178 episodes. Decay counters **do not track bank** (r=−0,029); desync depth explains **nothing** (r=−0,085; partial r given drain **−0,029**) while the town's drain explains **R²=0,366**. Flippable losses **11/178 ⇒ +6,2 pts** upper bound. **The 2,14× bank spread is the town, not a defect. Programme CLOSED** |
| 28 | **S7 leg 0 — the census** | *Not a STOP — a re-reading.* Retired three of this document's own claims; see §1.1 and §2 |

---

## 7. The plan — ship twice, then measure

*Adopted 2026-08-20, replacing a seven-pass desk programme that never uploaded. Both bets below end
in a submission; the diagnostics inside them are time-boxed gates, not passes.*

**The reasoning.** §1.1 leaves one fact: a faithful copy of a #9 route plays at #924, and nothing we
can measure at the desk explains it. Two responses are available and they are not alternatives — they
occupy the **two slots**, which is exactly the differentiation §9 demands.

### 7.1 Ship A — re-donor to a top-4 route

The reconstruction instrument works and is built (`analysis/s6_step1_reconstruct.py`,
`analysis/build_reconstruction_submission.py`). It was pointed at a **#9** donor. The standing rule
is **a copied route's ladder ceiling is its donor submission's own rating** — one API call, and the
cheapest external check this repo ever failed to run.

- **Front gate, time-boxed (≤ half a pass).** Donor selection by the **town-controlled** ratio
  (candidate's realised price ÷ its same-town opponent's, straight from the recorded episode — never
  by median reward, which is 99% town luck; §3). Candidates: Ryo Hasegawa 3.147 · tetsuya 3.095 ·
  Arman Tuganbaev 3.053 · Crop Dusta 3.017. Require ≥3 traces of **one** submission, cross-trace
  agreement comparable to ReCurSiON's (production 0,993 / market 0,980), and the 2-medoid check
  against a two-submission population. ⚠️ **That check reads the market/full stream, never the
  opening** — the 48-step opening is byte-identical across 87% of live seats and discriminates
  nothing.
- **Pre-registered "ship anyway":** if the best candidate's agreement is materially lower than
  ReCurSiON's, **ship the highest-agreement donor above 2.900 regardless**, recording the agreement
  figure. A #4 route reconstructed at 0,95 is a better bet than a #9 route reconstructed at 0,99,
  and the ladder is the only instrument that can settle it.
- **Kill:** if **no** top-4 team clears 3 traces of one submission (the カワシギ problem — agreement
  0,31, town-adaptive, unreconstructible), say so and go straight to 7.2 with both slots.
- **Gate before upload:** §9's checklist, including the new two-filename archive-hash check.
- **Eviction:** drops the Ueddy tape, keeps `55586926`. Already decided.

### 7.2 Ship B — the closed-loop layer on our own route

What §5.3(c) ships and we do not. Three of its four components are already measured here; the fourth
has never been looked at.

| Component | Status here |
|---|---|
| (i) transaction / weed-legality recovery | bounded at **+6,2 rating points** (§6 rows 26-27) — small, cheap, and the bound is *on our episodes against our opponents* |
| (ii) SELL reordering | ⛔ shed wall on a tape (§6 row 21) — **but that STOP is donor-specific**; re-test only on a route with shed headroom |
| (iii) near-clone preemption | ⛔ the sell-timing is a fixed calendar and already reproduced (§6 row 24) |
| (iv) **WHEAT market maker** on residual capital above a cash floor + feed reserve + shed headroom | 🔵 **never examined.** The only component whose surface area is unpriced |

- **Bound (iv) on paper first** (§3): from the recorded route's own idle capital and shed headroom,
  what is the maximum it could earn firing perfectly on every opportunity? If that is under ~+50
  rating points, build only (i) and ship.
- **Gate:** §3.1(4) order, against §8's bench, both seats.
- **The purpose of this slot is differentiation**, not maximum expected score: two open-loop tapes is
  the exact pattern §9 warns kills both on a meta shift.

### 7.3 Then — and only then — the deployment-neighbourhood bench

The 178 held live replays carry both seats' full action streams for **165 distinct opponent teams**
in the band where we lose. That is the bench §3's retention rule has demanded and §5.3(c) shows a top
player paying for the lack of. **It is built *after* A and B are on the ladder**, because it is a
measuring instrument and those two uploads are what calibrate it. Scope when it runs: extract with
provenance, verify each stream replays (state a retention figure), stratify by the **controlled**
opponent score (§2 rule 5's corollary: an opponent-strength cut names which submission the score
belongs to, or it is not a cut), and give the reconstruction its first BT rung.

### 7.4 Standing kills for the whole stage

- **A local bench that ranks agents in an order the ladder reverses is not an instrument.** This has
  already happened: our own round-robin ranked v1i above v1h; the ladder ordered them the other way.
  If 7.3's bench disagrees with the live ordering of A, B and `55586926`, **say so and stop tuning
  against it.**
- **No arm gets a second pass on a ceiling under 1% of the gap** (§3).

---

## 8. The bench

Every arm is scored against a bench that **retains earlier meta generations**, not only the current
top-30, and reports its record against **each** opponent — never a pooled number.

- **A1 — reference tiers 0-5** ($3.000 → $46.211, byte-identical scheduler, MIT). Cheap regression
  opponents that fail **loudly and differently from each other**. *Ceiling acknowledged:* they top
  out well below our route, so they catch catastrophic breaks — they do not spar.
- **A2 — our three extracted donor tapes** (Valmorlee `91456307` · Ueddy `90999409` · Kaito
  `90891564`), via `analysis/donor_streams.py`. **Fixed-production** opponents ⇒ the cleanest possible
  A/B for a market-layer change.
- **A3 — our own frozen checkpoints as earlier metas**: `v1h`, `v1i`, `v1o_2`, `v1u_base`. We have
  been deleting this signal by always gating `v_n` against `v_{n-1}`.
- **A4 — the deployment neighbourhood** (built in §7.3): 165 distinct real ladder opponents at our
  own band, both seats, already on disk. **A1 cannot represent it and A2 is three routes.** Arms
  report the **1.800-2.100** and **2.100+** strata separately — where we currently win 41% and 38%.
- Plus `meta_route` and the two earlier-meta notebook references (`v13-r3`, `177-180 v21.1`).
- **Both seats, always**; `--town-pin basket` for anything touching occupancy.

⚠️ **The town is a confounder in every market-only A/B.** A fixed seed also fixes the **shop draw**,
so a market-only screen on few seeds can be measuring one town. Over seeds 0-3 the sampled draw was
**WOOL zero-drain in 48% of episodes against a 34% population rate**. **Every arm reports its seed
set's realised drain distribution beside its dollars**, and the acceptance arm needs enough seeds to
span the draw.

---

## 9. Submission operations

```powershell
kaggle competitions submit kaggriculture -f submission.tar.gz -m "<version> <description>"
kaggle competitions submissions kaggriculture          # status + SUBMISSION_ID
kaggle competitions episodes <SUBMISSION_ID> -v        # CSV — no score column, see §2
kaggle competitions replay <EPISODE_ID> -p ./data/archive/raw/<dir>
kaggle competitions leaderboard kaggriculture -d -p ./data/archive/raw/<dir>
```

Auth: `KAGGLE_API_TOKEN` in `.env`; the CLI lives in `.venv/`, not on `PATH`. Package with
`tar -czf submission.tar.gz main.py agent/` — `main.py` at the **root**.

**Before every upload:**

- [ ] **Loader contract (G12):** the exported `agent` is the *last* callable; imports at top level; no
      `__file__` shim; vendored constants ([agent/_vendored.py](agent/_vendored.py)) parity-tested
      against the **currently installed** engine version.
- [ ] **Timing:** cold-process profile on both seats; gate `max_turn × 3 < 1s`.
- [ ] **Determinism (G13):** same seed in two fresh processes with different `PYTHONHASHSEED` →
      identical trajectory.
- [ ] 🔴 **Archive determinism:** reproduce the archive SHA-256 **under two output filenames**, so a
      gzip filename header cannot make a non-deterministic build look deterministic.
- [ ] **Mirror smoke:** `python -m harness.cli play main.py main.py --steps 720` → `clean=True`.
- [ ] Size < 100 MiB · `pytest tests/` green (bar the 3 known `test_v1h2d_*`) · `KAGGRI_DEBUG` off.
- [ ] **Provenance recorded** in the submission description; route files gitignored.

**Slot policy** — 5 uploads/day, **latest 2 active**, eviction by **date**:

1. **Never re-submit an unchanged agent** (§2 rule 6 — priced at ~1.000 points and hundreds of
   places).
2. **The two slots must stay differentiated in exposure** — herd composition, sell-side
   aggressiveness, route family. *"Two near-identical active submits → meta shift kills both."*
   §5.3(c) is the measured case: their v35 held two routes from the same basin and lost to an old
   generation carrying a new overlay.
3. **Decide the eviction before the upload, never as a side effect.** Currently pre-decided: the next
   upload drops the Ueddy tape.
4. **Judge nothing before ~100 episodes, never inside the first ~70** (§2 rule 2). At ~24-48
   episodes/day that is under two days, so **convergence time is not a constraint on shipping** — it
   is a constraint on judging, and the temptation it creates is to react to placement noise.
5. **Freeze both slots for the final week** and leave a full day to confirm each runs cleanly. An
   erroring agent plays nothing — including in the final tournament.

---

## 10. Risks

1. **An open-loop policy decays — but read the right instrument.** The *rating* decline of a frozen
   agent is mostly **pool-wide deflation** and is **band-local** (§2 rules 3-4); it is not evidence of
   skill decay, and our own frozen submission lost 32,9 points while gaining 15 places. The *skill*
   half is real and separate (a competitor measured its own frozen version going **87/90 → 14/27**
   against a newer field), and the only instrument that sees it is a **win rate against a bench that
   retains earlier generations** — §8's A3/A4. **Rank for the clock; wins for the decay.**
2. **A ceiling around 3.130.** The public-fork cluster plateaus there while private agents sit above
   it. A replication path tops out at whatever the donor is worth (§7.1).
3. **The donor is frozen and the meta moves.** Our current donor last submitted 08-14; the top-4 has
   turned over completely twice since 08-11.
4. **The engine can move again.** §4's detector runs regularly; a json-only balance change has caught
   this repo out once.
5. **Desk instruments measure fidelity, not strength.** Six passes established our copy is faithful
   and none of them could see a 1.036-point gap. Any future *"the route lacks X"* claim needs an
   opponent, not a trace comparison.
6. **Licensing at the prize stage.** Replays are game data and using them is permitted; the exposure
   is the "own original work" warranty and winner licensing, and it lands only if we finish top-10.
   Recorded, decided, not re-opened.

---

## 11. Open items

The only carried-forward actions with live obligations. Everything else on the old follow-up list is
either done, folded into §3.1 as a protocol rule, or housekeeping recorded in git.

| Item | Action | Why it is still open |
|---|---|---|
| **Top-5 profile is stale** | Re-run [analysis/b1_top5_profile.py](analysis/b1_top5_profile.py) against the refreshed archive. | The top-5 has turned over **completely, twice** since the profile in §5.1 was fitted (カワシギ #1 → #5; Ryo Hasegawa, tetsuya, Arman Tuganbaev and Crop Dusta are all new). §7.1 selects a donor from exactly that set, so this feeds the next pass |
| **§6 row 13 is engine-stale and production-stale** | Re-test the `shop-adaptive sell floor` STOP against `v1u_base`. | It failed at **415** crop tile-days as *"production-constrained, never glut-constrained"* — true then, and possibly false at the tape's ~1.316. Also measured on 1.32.6. Relevant to §7.2's component (ii)/(iv) |
| **Untracked collector chain** | Decide whether `data/archive/*.py` (`scrape.py` / `repack.py` / `teams.py` / `features.py`) should be tracked. | `data/archive/` is gitignored wholesale, so the whole episode-collection chain — including two bug fixes — is version-controlled nowhere |

---

## 12. Gated on 2.800+ — do not build now

**RL, trained on a remote box.** Not chosen, not rejected. Requires **all four** of: land + animals +
liquidation complete · ≥2 sweep rounds producing no `IMPROVED` over 48 seeds · local median bank still
<60% of the ladder's median winner · **≥3 weeks left**. That last clause closes the window around
**2026-09-09**. Open questions if it is ever taken: throughput (~240 env-steps/s/core — the bottleneck
is the Python engine, so the value of a remote box is **cores, not GPU**), self-play data format,
whether `harness/play.py` is the training stepper or only the evaluator, checkpoint convention against
learned weights, and a factored/masked action space — *and once the masking is written, most of the
domain knowledge is already hand-coded.*
