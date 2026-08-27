# ROADMAP — Kaggriculture

> **The plan, not the diary.** This file holds *what we are doing next, what decides it, and what
> must not be re-run*. It is technical and forward-looking by construction.
>
> **Where the rest lives:** per-pass narrative → [memory.md](docs/journal/memory.md) · per-pass measurements →
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

## 1. Where we are — **2026-08-23** *(refreshed against a live leaderboard snapshot + the episodes API)*

| | Value |
|---|---|
| **Active pair** | `55726984` **reconstruction + H2 tail-liquidation — unscored**, uploaded 08-23 23:07 · `55675634` **reconstruction + market overlay + tile recovery — 1.657,3**, 119 public episodes, frozen 08-21 19:06. *(`55726984` evicted `55586926` on 08-23; that route survives inside it — `55726984` **is** `55586926` + H2.)* |
| **Team standing** | **STRAF rank 903 of 6.020, 1.815,1** (snapshot 2026-08-23 15:30, i.e. *before* the 08-23 upload). ⚠️ §2 rule 3: the pool deflates, so read the **rank**, not the score. ⚠️ §9 rule 4: `55726984` is inside its placement burst — **judge nothing before ~100 episodes** (~2-4 days) |
| **Next eviction** | by **date** ⇒ the next upload drops **`55675634`** (08-21, 1.657,3) — the *lower*-scored slot, so this one is cheap again. Decide it deliberately anyway (§9 rule 3) |
| **Converged win rate** | **43,4%** (controlled, past the placement window). By opponent band: **54% / 41% / 38%** at <1.800 / 1.800-2.100 / 2.100+ |
| **Ladder top** (2026-08-23) | #1 Ryo Hasegawa **3.140,7** · #2 Subramanya N 3.027,3 · #3 Arman Tuganbaev 2.966,0 · #4 MiMi 2.948,6 · #5 Izzoudine Mohamed KANTA 2.925,3 · **#16 ReCurSiON 2.769,2** (our donor, still frozen 08-14 — it has lost 146,6 points and 7 places since 08-21 while frozen, §2 rule 4) |
| **The gap** | **954 points / 887 places** to our own donor (2026-08-23; was 1.036 / 915 on 08-21). Measured, not inferred — §1.1 |
| **Deadline** | **2026-09-30 23:59 UTC** (38 days; §9 rule 5 freezes the last week ⇒ real limit ~**09-23**). Final ranking = one Bradley-Terry tournament over the ~2 weeks of episodes played *after* it, using whatever sits in the two slots |
| **Prizes** | 10 **equal** $5.000 prizes, places 1-10 ⇒ the target is **stable top-10**, not #1. A high-variance 3.200 is worth less than a steady 3.050 |
| **Gates** | **2.800+** = minimum bar (below it we are still copying) · **3.000+** = "top-5 tactics replicated"; only above it is originating our own tactics the highest-value work |
| **Local suite** | `pytest tests/` **390 passed, 0 failed, 0 collection errors** (2026-08-23). ⚠️ The old *"3 known `test_v1h2d_*` failures, pre-existing, expected"* line is **retired** — they pass. Never accept a failure as "known" |

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
9. **A readability test, not a waiting period** (adopted 2026-08-27 from a public convergence
   write-up, consistent with rules 2/7). Sample `(episodes_completed, score)` **keyed by submission
   id**, drop every probe where the episode count did not advance — the board updates in batches and
   most probes carry no new episode, so averaging them pulls any drift estimate toward zero — and
   call the rating readable when `|drift| ≤ 1 pt/episode` **and its sign has flipped at least once**.
   The flip is what separates "settled" from "passing through zero on the way somewhere". Episode
   *rate* varies ~10× between agents, so "wait two days" specifies nothing. Corollary, and the one
   that binds an A/B: **two readings of the same agent taken at different times compare nothing** —
   the field turns over underneath (a byte-identical agent measured here lost 182 points over 135
   episodes). **To compare two of our own agents, field both and read them in the same window.**

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
- 🔴 **Any route reconstruction is gated on a fidelity replay before it can be shipped (added
  2026-08-21).** Replay the reconstruction against the **donor's own recorded opponents in their own
  recorded towns** and report median bank error against the donor's recorded bank. Calibration:
  ReCurSiON's reconstruction replays at **0,12%**; the tetsuya reconstruction replayed at **59%**
  (§6 row 29). A trace count and a cross-trace agreement figure are **not** sufficient — §7.1's
  literal KILL condition (*"≥3 traces of one submission"*) passed for a policy whose reconstruction
  was a chimera. Advisory floor alongside it: **`market_agr < 0,90` is a KILL** (halfway between
  ReCurSiON's 0,980 and カワシギ's town-adaptive 0,31). This is the check the desk instruments have
  been missing, and it retires the *"the ladder is the only instrument that can settle it"* clause —
  fidelity settles it before an upload burns a slot.
- 🔴 **Any market-side arm is paper-bounded before it can be built, and the bound is the *impact
  ceiling* (added 2026-08-21).** The engine runs a single unified market: `market_price(item, inv)`
  (`kaggriculture.py:192`) is a pure function of inventory and quotes are symmetric (SELL at `I`,
  `BUY_PRODUCT` at `I−1`), so a same-turn round-trip nets zero (`kaggriculture.py:600`). Profit
  exists only for units *held across turns* — and **your own trading walks the price against you**
  (WHEAT: inventory 10.000 → $25, 9.900 → $35, 9.500 → $47). **That impact, not the order cap, sets
  the roof.** Compute `max over splits of [Σ_{j<K} price(lo+j) − Σ_{j≤K} price(hi−j)]` with `hi` the
  highest market inventory before the split and `lo` the lowest after it, **with no cash, shed or
  order limit** — it bounds *any* maker. Convert at $253/ep; **under ~1 rating point → do not
  build.** WHEAT's ceiling is **7,9 pts** (§6 row 30). ⚠️ **Never bound a market arm by a flow
  heuristic**: `maxMarketOrdersPerTurn = 10` caps **orders, not units** (`_parse_order` gives each
  order a `remaining` quantity; our own backbone issues 14-unit orders), and a maker accumulates
  holdings across turns — the first version of row 30 called such a heuristic "a strict upper
  bound" and under-read the ceiling 5,7×.

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
12. **A fill criterion names its own denominator.** *(S10 P2, corrected 2026-08-25.)* «Fill» is not
    one number. Measured on the 92-episode snapshot of `55726984`:
    **sell-order fill = committed/ordered = 0,863**, but **floor fill = floor_committed/floor_ordered
    = 0,725**. They are different quantities and the second is *mechanically* the lower of the two —
    floor units sit at the tail of a bulk dump, which is exactly where an empty shed bites first.
    The S10 P2 gate demanded «committed within 15% of ordered» **of the floor counter** while
    deriving the 15% from the memory's **sell** fill (~0,89). That criterion was internally
    inconsistent; it is retired, not failed.
    🔴 **The committed counter is not suspect.** `harness/metrics.py::_simulate_market` was checked
    against recorded ground truth on **4.314 transitions across 6 episodes: simulated farm money
    equals recorded money in 4.314 of 4.314, worst difference $0,00.** Since the engine mutates
    money in exactly six places and all six sit inside the market walk, this proves every commit
    **and every rejection** is reproduced exactly. `floor_units` is a fact.
    **Rule going forward:** any fill gate states which numerator and which denominator, and a
    threshold imported from one fill is never applied to another.

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

- 🔴 **`step` is missing from seat 1's *recorded* observation — but not from the one the agent
  receives** (verified 2026-08-27, both locally and on live ladder replays). `step` is absent from
  `kaggriculture.json`'s observation schema and `interpreter` propagates only
  `farms/market/town/day/hour`, so `env.steps[i][1].observation["step"]` is **`None` on every turn
  of every episode**.  A public forum post reads this as a runtime bug that makes any step-indexed
  agent replay its turn-0 action in half its games.  **It does not.**  Instrumenting a seat-1 agent
  shows it receives `0,1,2,…` correctly, and our own α-control corroborates it: `tape_agent` does a
  bare `obs["step"]` index and still reproduces **509/509** episodes bit-exactly, which is
  impossible if seat 1 saw `None`.  **No agent change — do not "fix" this.**  The real consequence
  is for **offline tooling**: anything reading `steps[t][1]["observation"]` from a replay file gets
  `None` for `step`.  **Read seat 0's observation for the shared fields.**
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

### 5.1 The target profile — 120 seats, **re-fit 2026-08-21**

Column 2 is the original 120-seat fit; column 3 is the **2026-08-21 re-fit** against 60 fresh traces
of the current top-4 (15 each, `analysis/b1_top4_profile_2026_08_21.py`, §11 row 1), given as the
per-team median **range** across the four. **The shape holds; the levels moved where marked.**

| Quantity | 120-seat fit | **Top-4 re-fit 2026-08-21** (per-team median range) |
|---|---|---|
| Money d5 / d10 / d15 / **d20** / d24 / end | $516 / $4.863 / $16.720 / **$48.560** / $63.129 / **$82.747** | $23-465 / $1,1-16,5k / $18,7-22,2k / **$42,0-51,5k** / $59,5-68,9k / **$82,5-98,4k** |
| Planted tiles d10 / d15 / d20 / **d24** / d27 / d29 | 56 / 62 / 60 / **61** / 45 / **1** | 30-51 / 54-60 / 51-60 / **45-60** / 33-53 / **4-12** |
| Hands d5 / d10 / d15 / d20 / d29 | 3 / **14** / 9 / **14** / 10 | 3-8 / 9-12 / 11-12 / **12 (all four)** / 8-12 |
| Animals d5 / d10 / d15 / d20 / end | 6 / 12 / 12 / 12 / **13** — peak **8-9 COW + 4-5 SHEEP** | 4-8 / 10-15 / 12-15 / **12-16** / 11-15 — peak **7-8 COW + 2-7 SHEEP** |
| Quadrants | **3** — second on day **6**, third on day **10**, SE never | **3** — second d**5-7**, third d**8-10**, fourth never |
| Crop tile-days | **STRAWBERRY 577 · WHEAT 559 · MELON 180** (~1.316 total) | STR **384-609** · WHEAT **432-604** · MELON **110-180** (CARROT 0 on three of four; 99 for Ryo) |
| Sell calendar (first day, batch) | WHEAT d5/6 · FERT d2/4 · WOOL d6/**10** · MILK d9/6 · MELON d10/6 · STRAWBERRY d14/**14** | WHEAT d**0-5**/3-11 · FERT d1-2/1-5 · WOOL d6-7/4-8 · MILK d**8-13**/3-4 · MELON d10-14/6-9 · STRAWBERRY d**11-14**/4-6 |

**What moved, and what it means for the plan:**

- **The animal row moved *away* from us, not toward us.** The old fit's 13 was already unreachable;
  today's top-4 hold **12-16** through d20 and **11-15** at the end, with `hands` pinned at **12** at
  d20 across all four. Peak composition leans **lower COW / more variable SHEEP** (7-8 C, 2-7 S).
- **Hands d20 is 12, not 14** — consistent with §6 row 2's engine reading (one HIRE = one market
  order, cap 10/turn, hands wiped nightly), and it makes the 14 in the old fit look like a
  transient rather than a target.
- **WHEAT's first sell is d0-5, not d5/6** — two of the four sell on **day 0**.
- **MELON tile-days span 110-180**, so §5.2's *"MELON is our largest revenue hole"* stands but its
  ceiling is the low end of the old single figure, not the high end.

⚠️ **Our own planner cannot reach the animal row** — blocked on feed logistics, not config or cash
(§6 rows 11, 12, 20). The profile is not refuted; reaching it with `assign()`'s routing is. The
re-fit widens that gap rather than closing it.

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
| 21 | **T2 market overlay on the shipped tape** | STOP at SMOKE. **The tape's realised STRAWBERRY price is pinned by shed capacity, not a re-timeable calendar**: the shed runs at 98/100, metering strawberry overflows it, burns WOOL/FERT and rejects the `BUY_PRODUCT WHEAT` feed deposit ⇒ escapes 0→11, bank −$3-4k/ep — *while winning* the strawberry $/u sub-metric. ⚠️ **Donor-specific**: the same design earns +$1.911,9/ep for an agent that **owns** its route. 🔴 **Re-measured 2026-08-23 across all 253 live replays, both submissions, both seats: the 98/100 was the *Ueddy* tape. OUR route peaks at 84/100 (median 72)**, p90 on the tight days d18/d21/d22/d23 = 72/72/71/69. The binding number is not the p90 but the per-episode minimum free capacity at the day boundary (`_drop_inventories_to_shed` :843 discards the overflow silently) = **16 units**: a 20-unit hold busts `shedCapacity` in **8/253** episodes, a 16- or 12-unit hold in **0/253**. Row 21 still binds — it is now *bounded*, at ≤12 held units |
| 22 | **C-A, in-place SELL reordering ("the Cleo rule")** | REFUTED before being built, analytically **and** empirically: per-slot lockstep across players and per-product pools mean the reorder cannot move realised price. The engine answered before the experiment ran |
| 23 | **S6 step 2a — own-farm repair** | STOPPED at Phase 0. The loss is **100% WHEAT on the same 5 tiles**, ceiling **$599/ep**; free half **$0-241** (no idle unit is ever on a loss tile); full recovery **+2,4 rating points / 0,09% of the gap** |
| 24 | **S6 step 2b — "restore the erased sell-timing"** | REFUTED on paper, no episodes. ReCurSiON's strawberry rule is a **fixed global calendar** (hold, release into the hour-0 town-centre pulse), invariant across 50 towns: 46/50 sell an identical **290 units**; at step 336 all 50 sell exactly 6 while price spans $151-$230. corr(units, own shed) **+0,92** vs corr(units, shop identity) **+0,02**. **The vote already reproduces it** |
| 25 | **S6 step 2c — the family, channel-wide** | BRANCH (i): **every** market channel is town-invariant. **40% of towns never draw a YARN_STORE**, yet at all 20 contested wool steps the modal action is identical across the drain split. MILK never presents a zero-drain population; WHEAT's residual is a fixed 4-trace variant; FERTILIZER is in no `SHOPS` entry ⇒ analytically eliminated. **Family CLOSED channel-wide** |
| 26 | **S6 step 2d — the production channel** | BRANCH (iv): the 88 production-disagreement steps **are** town-reactive (per-town weed spawns → the hands DIG, re-PLANT and WATER by real dry state, re-syncing one op later; farmer op differs 0/88; 62% of hand-slot disagreements stand on a disjoint tile) — **a genuine closed-loop rule the vote cannot carry**, bounded at **$597/ep ⇒ +2,4 pts**. ⚠️ Its bank-gap decomposition blamed the opponent pool; **that gloss is circular** — Kaggle pairs by rating |
| 27 | **S6 step 2e — the loss tail, re-priced in wins** | BRANCH (i)+(iv), replicated on 178 episodes. Decay counters **do not track bank** (r=−0,029); desync depth explains **nothing** (r=−0,085; partial r given drain **−0,029**) while the town's drain explains **R²=0,366**. Flippable losses **11/178 ⇒ +6,2 pts** upper bound. **The 2,14× bank spread is the town, not a defect. Programme CLOSED** |
| 28 | **S7 leg 0 — the census** | *Not a STOP — a re-reading.* Retired three of this document's own claims; see §1.1 and §2 |
| 29 | **S7 Leg A — re-donor to a top-4 route** | KILL by measurement. All four candidates (Ryo Hasegawa, tetsuya, Arman Tuganbaev, Crop Dusta) are highly state-adaptive: cross-trace agreement **prod 0,25-0,37 / market 0,64-0,86** (vs ReCurSiON's 0,993/0,980). The tetsuya reconstruction — the highest-agreement candidate above 2.900 — replayed against its own recorded opponents in their own towns at **59% median bank error** (one episode $1.567 vs $105.369 = **98,5%**), for comparison ReCurSiON's reconstruction replayed at 0,12%. The pre-registered *"ship anyway"* would have shipped a chimera. **Both slots go to §7.2.** §5.3(c)'s state-aliasing warning applies verbatim |
| 30 | **S7 Ship B — component (iv) WHEAT market maker paper-bound** | KILL by paper bound. Defensible ceiling across 178 live replays of `55586926`: **$2.009/ep = 7,9 rating pts** — best single round trip **with our own price impact** and **no cash/shed/order limit at all**, optimum at a median **231 units held** (2,3× the whole shed). **6,3× under §7.2's +50-pt build threshold.** Root cause is the impact, not the order cap: `market_price` is a pure function of inventory with symmetric quotes (`kaggriculture.py:192`/`:600` — a same-turn round-trip nets zero), and buying walks WHEAT $25 → $35 → $47 as inventory falls 10.000 → 9.900 → 9.500. Diagnostics: tight $270/ep (1,07 pts) against recorded prices, and a **discredited** flow heuristic at $351/ep — see §3, it is not a bound. ⚠️ **The ride-along did NOT re-close §6 row 13** — see row 31. Full report: [baselines/2026-08-21/s7_ship_b_bound_report.md](baselines/2026-08-21/s7_ship_b_bound_report.md) |
| 31 | **§6 row 13 re-test — the route IS glut-constrained** | *Not a STOP — a reopening.* Row 30's first pass measured glut on **WHEAT only** and re-closed row 13 on it. WHEAT is structurally the **one product whose price our selling cannot crash** (`above_target` **0,2**: +400 units moves it $25 → $20); MELON is `above_func 'sq'` / `above_target 3,6`. Re-measured model-free across all nine products on the same 178 episodes: **WOOL sits at the $1 floor a median 30 turns/episode** (base $200), MILK 7 turns, STRAWBERRY 2; at just **+100 units** above baseline MILK / WOOL / STRAWBERRY are all at **$1**, MELON bottoms at **$4** against base $250. **The premium products — the route's actual revenue — are deep in the collapse zone.** ⚠️ This does **not** revive the sell-floor lever: §6 row 21's shed wall, 1.32.7's 30 units/product/season town absorption (recovery is slow, so a floor may mean never selling) and §5.2's common-mode result all argue it still fails. **Status: open and untested** — §11 row 2 reopened |
| 32 | **S11 B2.5 — leakage-safe dump predictor** | KILL by measurement, **final**. Definition unchanged from S10 P4.3 (opponent sells ≥20 units of a premium product within 24 turns); predictor sees `obs` + our own action only, enforced by a PASS-replay bit-identical test (`tests/test_s11_b25_leakage.py`); 20 ladder replays of `55726984`, 14.380 steps. Precision **MELON 0,10** against a **0,076** base rate (lift **1,31×**) and **STRAWBERRY 0,48** against **0,191** (lift **2,52×**, recall 0,88) — target was ≥0,70 on **both**. Parameters were carried over untouched (rule 3: no tuning to a gate). Read beside its own instrument: B2.4 coverage **0,957** overall / **0,944** on the seven products the opponent actually holds / **0,880** worst product, and MAE **conditional on `uncertainty_width == 0`** (MELON 0,039 on 39% of steps, STRAWBERRY 1,15 on 80%, WHEAT 2,64 on 13%). So the instrument is not the binding constraint — **the event is simply not predictable from the non-floor channel**; STRAWBERRY carries real but insufficient signal, MELON is near base rate. The ground-truth label counts *ordered* rather than *committed* units, which biases precision **upward**, so the kill is conservative. **Does not reopen without a new mechanism** — not a new threshold. `data/derived/s10_opponent_inventory.json` |
| 33 | **S13 Phase 1 — the 18-point seat gap does not replicate at that size** | KILL by measurement (of the *claim as screened*), pre-registered gate. `55726984`'s 97-episode screen (seat 0 30W-16L WR 0,652, seat 1 24W-27L WR 0,471, gap **+0,182**) does not hold up: `55675634` (119 eps) reads gap **+0,095**, and `55586926` (293 eps, the largest sample) reads **−0,003** — a true zero (72/145 vs 74/148, Fisher p=1,00), not an opposing effect; treat the earlier "signs disagree, which alone fails the gate" framing as over-stated, since a null is not a sign. Headline CMH stratified by rating zone (379/509 episodes matched, 74,5%): **χ²=1,62, p=0,204** (uncorrected 0,168) — fails the 0,01 bar regardless. Both controls came back clean: no opponent-strength confound (Mann-Whitney U, p=0,264), no town/shop-draw confound (p=0,830), seat term does not survive a pooled logistic regression (LR p=0,255). **Dropping each submission's first 70 episodes is the actual mechanism** — pooled gap **+0,052 → +0,020** — exactly §2 rule 2's placement-burst warning. 🔴 **Not proof of zero effect**: pooled gap **+0,052** (95% CI **[−0,034, +0,137]**), MH odds ratio **1,35** favouring seat 0, and **5 of 6** rating zones point the same direction (only 2400+, n=27, reverses). Power at a 5-point gap is **~24%** — this sample cannot see an effect that size. **Correct verdict: not established at 18 points; a modest seat effect (~5 pts) is not ruled out and not actionable.** §11 item closed as not-actionable, not as disproven. `analysis/s13_seat_asymmetry.py`, `data/derived/s13_seat_phase1.json`, `tests/test_s13_seat_asymmetry.py` |

---

## 7. The plan — ship twice, then measure

*Adopted 2026-08-20, replacing a seven-pass desk programme that never uploaded. Both bets below end
in a submission; the diagnostics inside them are time-boxed gates, not passes.*

**The reasoning.** §1.1 leaves one fact: a faithful copy of a #9 route plays at #924, and nothing we
can measure at the desk explains it. Two responses are available and they are not alternatives — they
occupy the **two slots**, which is exactly the differentiation §9 demands.

### 7.1 Ship A — re-donor to a top-4 route ⛔ KILLED BY MEASUREMENT 2026-08-21

**Verdict:** the top-4 population is a state-adaptive one. Every candidate sits far below
ReCurSiON's cross-trace agreement line, and a fidelity replay of the highest-agreement candidate's
majority-vote reconstruction against its own recorded opponents in their own towns lost **59%
median bank** — for comparison, the ReCurSiON reconstruction replayed at **0.12%**. §7.1 as written
would have "shipped anyway" tetsuya at 0.856 market / 0.374 production; the fidelity replay says
that would have shipped a chimera. **Both slots go to §7.2.** Full report:
[baselines/2026-08-21/s7_leg_a_report.md](baselines/2026-08-21/s7_leg_a_report.md).

Measured per submission (15 fresh public episodes per candidate, `kaggle competitions episodes`):

| Candidate | prod agr | market agr | mean premium ratio |
|---|---:|---:|---:|
| Ryo Hasegawa `55614463` | 0,331 | 0,692 | 0,90 |
| tetsuya `55574890` | 0,374 | 0,856 | 0,94 |
| Arman Tuganbaev `55617399` | 0,247 | 0,777 | 0,99 |
| Crop Dusta `55623460` | 0,269 | 0,636 | **1,18** |
| ReCurSiON (calibration) | **0,993** | **0,980** | — |

The strong price ratios (Crop Dusta ≥1,10 on all three premium products) confirm the top-4 has a
real edge in the market layer against the opponents it faces — **and that edge is not portable via
a fixed calendar.** §5.3(c) point 4's state-aliasing warning applies here in its exact form.

**Standing rules the pass added — both promoted out of this killed section, into §3 and §9's
checklist, so they survive it:** (a) §7.1's KILL condition needs a numerical threshold beyond
trace count — the literal *"3 traces of one submission"* passes for a policy whose reconstruction
is a chimera; adopt `market_agr < 0,90` as an advisory KILL floor (halfway between ReCurSiON and
カワシギ). (b) **The fidelity replay against the donor's own recorded opponents is the decisive
front-gate check for any future reconstruction** — it is what the desk instruments have been
missing; add it to the gate ahead of every reconstruction upload. It closes the "the ladder is the
only instrument that can settle it" clause: at 0,86 market / 0,37 production, fidelity already
settles it before an upload burns a slot.

- **Ride-along (§11) done in the same pass.** `analysis/b1_top4_profile_2026_08_21.py` refit §5.1's
  top-N profile against the 60 fresh top-4 traces (gitignored:
  `data/derived/b1_top4_profile_2026_08_21.json`). The old profile holds: quadrants **3** (SE never)
  · first extra day 5-7 · second extra day 8-10 · d29 end $82,5-$98,4k (was $82,7k median) · COW
  peaks 7-8, SHEEP 2-7 (§5.1 said 8-9 COW + 4-5 SHEEP; today's top-4 leans **lower COW / more
  variable SHEEP**). MELON tile-days 110-180 (was 180). WHEAT first sell d0-5 (was d5/6).
  **§5.1's table now carries the re-fit in full, as its own column.**

### 7.2 Ship B — the closed-loop layer on our own route ⇐ (iv) KILLED, (i) IN BUILD (2026-08-21)

*§7.1 KILLed by measurement (row 29). Both slots come from this section. §9's differentiation rule
("two near-identical active submits → meta shift kills both") still binds. The paper-bound step
(below) killed the (i)+(iv) variant; **the differentiated pair is now (i) as the new upload +
`55586926` unchanged in the other slot** — one new upload, pre-decided eviction (Ueddy tape)
unchanged. ⚠️ **This is thin differentiation and is flagged, not resolved:** §7.2 justified the
pair by *"differ in market-side exposure"*, and killing (iv) removed exactly that. Backbone vs
backbone-plus-a-6,2-pt patch is close to the "two near-identical active submits" pattern §9 rule 2
warns kills both on a meta shift. Row 31's glut finding is the most promising candidate for a
genuinely differentiated second variant.* 🔴 **Realised 2026-08-23:** that variant is built — the
H2 liquidation overlay (§11 row 2). The pair becomes **"tape + tile recovery" (`55675634`) vs
"tape + liquidation layer"** — genuinely different market-side exposure, which is what §9 rule 2
demands and what killing (iv) had removed.

What §5.3(c) ships and we do not. Three of the four components were already measured here; the
fourth is now measured too and priced out.

| Component | Status here |
|---|---|
| (i) transaction / weed-legality recovery | bounded at **+6,2 rating points** (§6 rows 26-27) — small, cheap, and the bound is *on our episodes against our opponents*. **In build (task list #3).** |
| (ii) SELL reordering | ⛔ shed wall on a tape (§6 row 21) — donor-specific; re-test only on a route with shed headroom |
| (iii) near-clone preemption | ⛔ the sell-timing is a fixed calendar and already reproduced (§6 row 24) |
| (iv) **WHEAT market maker** | ⛔ **KILLED on paper 2026-08-21**, row 30 — impact ceiling **$2.009/ep = 7,9 pts** across 178 live episodes with *no* cash/shed/order limit, **6,3× under** §7.2's +50-pt threshold. The roof is our own price impact (WHEAT $25 → $47 as we buy inventory down), not the order cap. Full report: [baselines/2026-08-21/s7_ship_b_bound_report.md](baselines/2026-08-21/s7_ship_b_bound_report.md) |

- 🔴 **Ride-along CORRECTED (row 31).** The first pass measured glut on **WHEAT** — the one product
  whose glut side is flat by construction — and wrongly re-closed §6 row 13. Across all nine
  products the route **is** glut-constrained where it earns: **WOOL at the $1 floor a median 30
  turns/episode**, MILK 7, STRAWBERRY 2, MELON bottoming at $4 of base $250. **§11 row 2 is
  reopened**; whether the sell-floor lever is *takeable* is still untested (§6 row 21's shed wall
  and §5.2's common-mode result argue it is not).
- **Gate:** §3.1(4) order, against §8's bench, both seats.
- **Standing rule adopted 2026-08-21 (promoted into §3):** any future "add a market-side arm" pass
  must run the **impact ceiling** first — the roof is set by how fast your own trading walks the
  price against you, never by a flow heuristic on the order cap. Under ~1 rating point → do not
  build.

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

### 7.5 S12 — MELON sell-schedule repair 🔴 **BLOCKED, needs a decision, not "the current pass"** (`docs/plans/s12_melon_pullforward.md`)

The measurement it stands on, from 97 ladder replays of `55726984` (2026-08-27): we sell **114 MELON
units on four days**, weighted mean sell-day **17,68** —

| day | units/ep | median price | revenue/ep |
|---:|---:|---:|---:|
| 10 | 30 | $250 | $7.500 |
| 20 | 60 | $152 | $9.120 |
| 21 | 12 | $51 | $612 |
| 22 | 12 | **$4** | **$48** |

**The last 24 units are 21% of volume for 3,8% of revenue**, and the final 12 clear at essentially
the floor. §6 row 31 already measured *why*: MELON is `above_func 'sq'` / `above_target 3,6`, so our
own 60-unit day-20 block is the crash. An external price census (5 replays, one agent — direction
only, not the exact peak day) reads the same shape: MELON peaks ~day 10 and a day-25 melon is worth
~⅕ of a day-12 one.

🔴 **BLOCKED before implementation, 2026-08-27 — the pull-forward premise is false.** Our own MELON
stock is **0 on every day through 18** (median and max, 25 replays); it is 12 on day 20 and 12 on
day 21. The day-10 and day-20 blocks are **harvest events sold within the day they land**, not a
hoard released late — `CROPS["MELON"]` is `first_yield_day 10 / max_yield_day 12 / ongoing False`,
so **the sell day is set by the harvest, not by a holding decision** and a market overlay has no
degree of freedom. Genuinely held inventory is **~12 units (~$650/ep gross)**, one to two orders of
magnitude under §7.2's +50-point threshold. The real question is production-side — **is the second
MELON wave worth its tile-days**, and can the two waves be re-phased without crashing the day 9-14
window against each other (§6 row 31) — which is a larger, riskier pass than an additive overlay.
A second, independent blocker: `TapeOverlay.act()` returns early on `mode=="liquidate"`
(`agent/tape_overlay.py:270`), so **`liquidate` and `augment` are mutually exclusive** — any MELON
arm must *compose* with the shipped H2, not replace its mode. **Re-scope or kill before building.**

---

## 8. The bench

Every arm is scored against a bench that **retains earlier meta generations**, not only the current
top-30, and reports its record against **each** opponent — never a pooled number.

**S10 addition (2026-08-25) — `analysis/s10_replay_bench.py` is Instrument A.**  It replays every
recorded ladder episode with our seat's action stream substituted for a candidate agent, opponent
seat held as a tape.  α-control (both sides tape) reproduces 509/509 recorded episodes bit-exactly.
H2 calibration reproduces the frozen S9 result on 412 confirm-set episodes (`232-180 → 255-157`,
McNemar `c=23 b=0 p=2,38·10⁻⁷`), bit-identical to the s9-phase2-gate memory.  **Screen = `55726984`
(97 eps)**; **confirm = `55586926` + `55675634` (412 eps)** — never mix.  Every bench "look" writes
one line to `gates/s10_bench_ledger.jsonl` (same semantics as `gates/confirm_log.jsonl`).  Live
seeds do NOT enter `harness/seeds.py::NAMED_SEED_SETS`.  Reports are per-seat and per-submission-
generation; opponents whose sign flipped are listed by name.  **Every** bench output and every
ledger line carries the P1.5 constraint as a `constraint` field: tape opponents do not react, so a
timing change is priced to **first order only** — sufficient to screen a candidate, never a proof.  See
`docs/plans/s10_instrument_rebuild.md` §P1 / §P3 and `data/derived/s10_bench_h2_calibration_report.json`.

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

**The mirror arm (S10 P1.6 / S11 B4) is CLOSED without code — 2026-08-27.**  It was never a
fidelity check: the tapes are **seat-bound** (`stream[0]` points at seat 0's tiles, positions and
money), so handing one to seat 1 desynchronises immediately and P1.2's bit-exact criterion does not
apply to it.  The only question a mirror arm would have answered — whether H2's sign is an artefact
of seat — is already answered by the bench's existing `by_seat` split: seat 0 `c=10, b=0`, seat 1
`c=13, b=0`.  **Same sign, comparable magnitude, both seats.**  Building the arm would re-measure a
settled result, so it is closed as answered rather than carried as debt.

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
- [ ] Size < 100 MiB · `pytest tests/` green — **all of it**. ⚠️ The old *"bar the 3 known
      `test_v1h2d_*`"* carve-out is **stale and was removed 2026-08-23**: measured **390 passed, 0
      failures, 0 collection errors**. Never accept a failure as "known". · `KAGGRI_DEBUG` off.
- [ ] 🔴 **Fidelity replay (reconstructions only, §3):** the packaged route replayed against the
      donor's own recorded opponents in their own towns, median bank error reported. Calibration
      0,12% (ReCurSiON) vs 59% (tetsuya, §6 row 29). A chimera does not get a slot.
- [ ] **Provenance recorded** in the submission description; route files gitignored.

🔴 **Reading the metric gate on a tape/reconstruction arm (standing rule, 2026-08-24).** The structural
leg (`plant_decay_units_lost == 0`, ≤2% low-price sales) is **absolute on `agent_a`** by design and pinned
by `test_v1h2d_structural_faults_stay_hard_zero_at_any_price` — its rationale is *"the agent did something
it did not intend"*, which assumes **we authored the policy**. A tape replays a donor's policy, whose
structural counters are non-zero **by construction** and cannot be driven to zero without abandoning the
tape. So `metric_gate_passed=False` / `GO=False` is **expected on every tape arm and is NOT a STOP**.
Precedent: `gates/s6_step1b_gate_holdout/results.json` — the gate of **`55586926`**, our highest-scored
live slot — reads `metric_gate_passed=False` with `plant_decay=1437` and 11,09% low-price sales, and was
shipped. Read the structural leg **differentially** (candidate vs the base it overlays): a STOP is a
non-zero **Δ**, or a `priced_loss_delta` breach. Every gate leg that *can* detect overlay damage
(`clipped_production_ticks`, `shed_overflow_burnt`, `animals_escaped`, `market_sim_aborted`,
unexplained no-ops, declared mechanisms, `priced_loss_delta`) stays absolute and binding.

**Slot policy** — 5 uploads/day, **latest 2 active**, eviction by **date**:

1. **Never re-submit an unchanged agent** (§2 rule 6 — priced at ~1.000 points and hundreds of
   places).
2. **The two slots must stay differentiated in exposure** — herd composition, sell-side
   aggressiveness, route family. *"Two near-identical active submits → meta shift kills both."*
   §5.3(c) is the measured case: their v35 held two routes from the same basin and lost to an old
   generation carrying a new overlay.
3. **Decide the eviction before the upload, never as a side effect.** Two pre-decisions are now spent:
   the Ueddy tape (08-21, by `55675634`) and `55586926` (08-23, by `55726984` — approved deliberately,
   and the route survives inside its evictor). Currently pre-decided: the next upload drops
   **`55675634`**, the lower-scored slot (§1).
4. **Judge nothing before ~100 episodes, never inside the first ~70** (§2 rule 2). At ~24-48
   episodes/day that is under two days, so **convergence time is not a constraint on shipping** — it
   is a constraint on judging, and the temptation it creates is to react to placement noise.
5. **Freeze both slots for the final week** and leave a full day to confirm each runs cleanly. An
   erroring agent plays nothing — including in the final tournament.

**Deadline checklist (S10 P5.3, 2026-09-30 lockdown, real cutoff ~09-23):**
1. Both slots hold **strong, error-free** agents by 2026-09-23; no upload in the last **48 hours**.
2. `python -m harness.cli play main.py <opponent> --steps 720` runs `clean=True` on both slots.
3. Archive SHA-256 reproduces under **two output filenames** for both slots (§9 above, still binding).
4. Leave a **full day of margin** between the last upload and 2026-09-30 UTC.  The Bradley-Terry
   fit runs on the ~2 weeks of episodes *after* the deadline (§2 rule 4); the live score at
   09-30 08:00 UTC is not what decides the final rank — only the two agents that survive to that
   moment do.  A last-minute repair burns ~1.000 live points, does not change the final BT, and
   only exists to protect against unnoticed breakage.

---

## 10. Risks

1. **An open-loop policy decays — but read the right instrument.** The *rating* decline of a frozen
   agent is mostly **pool-wide deflation** and is **band-local** (§2 rules 3-4); it is not evidence of
   skill decay, and our own frozen submission lost 32,9 points while gaining 15 places. The *skill*
   half is real and separate (a competitor measured its own frozen version going **87/90 → 14/27**
   against a newer field), and the only instrument that sees it is a **win rate against a bench that
   retains earlier generations** — §8's A3/A4. **Rank for the clock; wins for the decay.**
2. **A ceiling around 3.130 — and the replication path can no longer be re-pointed upward.** The
   public-fork cluster plateaus there while private agents sit above it. A replication path tops out
   at whatever the donor is worth, and **re-donoring above ReCurSiON is now measured shut**: the
   whole top-4 is state-adaptive and unreconstructible by any state-blind method (§6 row 29).
   ReCurSiON's 2.915,8 is the ceiling of the copying route; passing it requires §7.2's own layer.
3. **The donor is frozen and the meta moves.** Our current donor last submitted 08-14; the top-4 has
   turned over completely twice since 08-11.
4. **The engine can move again.** §4's detector runs regularly; a json-only balance change has caught
   this repo out once.
5. **Desk instruments measure fidelity, not strength — and that is exactly what makes the fidelity
   replay decisive.** Six passes established our copy is faithful and none of them could see a
   1.036-point gap; any future *"the route lacks X"* claim still needs an opponent, not a trace
   comparison. **The converse now also holds:** a *"this route is worth copying"* claim is a
   fidelity question, and §3's replay gate answered it at the desk for a fraction of an upload
   slot (§6 row 29). Use fidelity where fidelity is the question, and only there.
6. **Licensing at the prize stage.** Replays are game data and using them is permitted; the exposure
   is the "own original work" warranty and winner licensing, and it lands only if we finish top-10.
   Recorded, decided, not re-opened.
7. **Dropped SELLs (~14% of ordered units) — measured 2026-08-25, documented acceptance (S10 P5.2).**
   On 97 replays of `55726984`: overall SELL fill **0,863** (matches the memory's "~0,89"), dropping
   **$24.420/ep** in unrealised revenue.  Distribution by product: WOOL 0,66 / MILK 0,74 / FERTILIZER
   0,82 / MELON 0,92 / WHEAT 0,97 / STRAWBERRY 0,98.  **Loss-side $25.465/ep vs win-side $23.588/ep,
   Δ = $1.877** — a large dollar leak with a small W/L discriminator (below the memory's typical
   "flippable" margin).  A repair overlay in the shape of `agent/tape_overlay.py` (or the s7 tile-
   recovery pattern) would attack the $ number but not the *rank* number, and the incremental W/L
   headroom is in the MELON early-liquidation lever (`s9-live-read-55726984`: +$4.924/ep, 13/38
   loss flips), out of scope for this pass.  **Decision: accept and do not build a repair overlay
   in this pass.**  See `data/derived/s10_dropped_sells.json`.
   *Day axis (added 2026-08-25):* fill is **0,98 through day 9** and falls to **0,87 from day 20
   on**; worst slots are day 10 (0,626) and day 29 (0,770, **47,1 units/ep** — the largest
   single-day leak).  The drops are not uniform: they concentrate in the late liquidation window,
   the same window the H2 overlay operates in.  Any future repair overlay should be aimed there.

8. **A joint-seat simulator leaks — and the opponent-inventory instrument is unfinished (S11 B2,
   2026-08-27).**  **Standing rule, the reusable half:** the market is **per-unit lockstep** —
   both seats are quoted at the *same* pre-commit inventory (`kaggriculture.py:612`) — so **any
   helper that simulates both seats is ground-truth-only, never estimator input**, and a
   PASS-replay bit-identical test is the cheap way to prove it.  `_transition_events` broke this
   silently and moved our own reported prices by $1-2; B2.0′'s PASS was an artefact of it and the
   gate reads **0,472 FAIL** once isolated.  **The instrument's own limits**, recorded so nobody
   re-reads it as finished: the upper bound is clean (0 violations / 129.420 product-steps) but
   the **lower bound is not** (5.604, 4,3% — every coverage miss is one), because the ledger is a
   running sum from step 1 with no re-anchor; and **B2.1 was never wired to its stated job** of
   narrowing the `MOD10` bracket (median width is under `shed_cap` for 9/9 products, but the tail
   passes it on four).  **Not being repaired**: B2 existed to feed B2.5, and B2.5 is dead (§6 row
   32).  Detail and the one legitimate re-open route in
   `docs/plans/s11_instrument_completion.md` §1.

---

## 11. Open items — and where each one runs

Carried-forward actions. **None of them gets its own pass**: two ride along inside a pass that
already touches the same data, and the third is closed below.

| Item | Scheduled | Why there, and what it costs |
|---|---|---|
| ~~**Seat asymmetry — 18 points of win rate, unexplained**~~ | ⛔ **CLOSED 2026-08-27 — not actionable, not disproven** (§6 row 33, `docs/plans/s13_seat_asymmetry.md` Phase 1) | The 97-episode `55726984` screen (seat 0 WR 0,652 vs seat 1 WR 0,471, gap +0,182) does not hold at that size: `55675634` reads +0,095, `55586926` (the largest sample) reads a true zero, −0,003. The headline CMH stratified by rating zone reads **p=0,204**, short of the pre-registered 0,01 bar, and neither confound explains anything (opponent strength p=0,264, town/shop draw p=0,830). **But the data does not clear the effect either**: pooled gap +0,052 (95% CI [−0,034, +0,137]), MH OR 1,35 toward seat 0, 5/6 rating zones pointing the same way, and only ~24% power to detect a 5-point gap at this sample size. Closed as **not actionable at any size this pass could confirm**, not as a proven null. No Phase 2, no `agent/` change, no slot spent |
| ~~**The §5.1 top-N profile is stale**~~ | ✅ **DONE 2026-08-21** — the re-fit is **in §5.1's table as its own column** ([analysis/b1_top4_profile_2026_08_21.py](analysis/b1_top4_profile_2026_08_21.py)) | Refit against the 60 fresh top-4 traces pulled by the §7.1 selection pass. Old profile largely holds: quadrants 3 (SE never), first extra day 5-7, second 8-10, d29 end $82,5-$98,4k (was $82,7k median). What moved: **COW peaks 7-8 (was 8-9), SHEEP more variable (2-7 vs 4-5), MELON tile-days 110-180 (was 180), WHEAT first sell d0-5 (was d5/6)**. The old b1_top5_profile.py depends on the retired collector chain (§11 last row) and cannot re-run without it; the v2 script reads the kaggle-CLI-fetched replays directly |
| ~~**§6 row 13 REOPENED — the route *is* glut-constrained**~~ | ✅ **DONE — shipped 2026-08-23, this is the active `55726984`** | RAN 2026-08-23 (S9). WOOL and MELON are out of this family (WOOL's volume lives in towns where it can never recover; MELON absorption is 1/day and the tape drops+sells it inside one turn). What survives is **STRAWBERRY in the ≥d22 tail**, built as `tape_overlay.mode="liquidate"`: **412 live replays, W/L 232-180 → 255-157, c=23 b=0, McNemar p=2,4e-7**, margin +$458/ep, gain on the **opponent's** bank (−$357) not ours (+$110) — why `median_bank` alone can't see it. **Phase 2 gate passed and uploaded 08-23 23:07** (`s9-phase2-gate` memory; §1's active-pair line) — this stale row is the pre-upload snapshot of that same result, kept only so the row-13 history reads in order |
| ~~**Untracked collector chain**~~ | ⛔ **CLOSED as obsolete, 2026-08-20** | The item asked whether `data/archive/*.py` should be tracked. **They no longer exist on disk.** `scrape.py` / `repack.py` / `teams.py` / `features.py` were tracked once (`a4783c8`), removed from the index when `data/archive/` was gitignored wholesale, and are now gone from the working tree — so the two bug fixes made to the untracked copies are **lost**, and only the pre-fix version is recoverable from git. ⚠️ **This does not need rebuilding:** every input the plan uses now comes from the official daily episode datasets, `kaggle competitions replay`, `episodes -v` and `leaderboard -d` (§9), which is how the 178 live replays and both leaderboard snapshots were obtained |

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
