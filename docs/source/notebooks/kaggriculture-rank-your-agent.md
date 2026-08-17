# kaggriculture-rank-your-agent

> Extracted by `analysis/nb_extract.py` from `kaggriculture-rank-your-agent.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# Kaggriculture: rank your agent against a known ladder

[Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) scores you on
**head-to-head wins**, not on an absolute metric. That makes progress genuinely hard
to read. Your agent banked 40,000 coins — is that good? It depends entirely on who it
played. Beating the built-in `starter` baseline tells you almost nothing, and the
public leaderboard only updates after you have spent a submission.

So I built a fixed ladder to measure against. This notebook:

1. loads **ten documented reference agents** spanning a very wide skill range, plus the
   top-meta agent that beats all ten of them,
2. lets you plug in **your own agent** three different ways,
3. plays a seat-swapped round robin and ranks everyone with **Bradley-Terry** —
   the same method the competition uses for final standings,
4. tells you which rung you landed on,
5. and writes a **submittable `submission.tar.gz`**, so the agent you ranked is
   literally the artifact you submit.

The whole default run takes a couple of minutes. There is a knob at the bottom for a
much heavier evaluation when you want tighter error bars.

> **What you need:** the
> [Kaggriculture Reference Agents](https://www.kaggle.com/datasets/raykkretzschmar/kaggriculture-reference-agents)
> dataset attached (Add Input → Datasets), the output of
> [Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta)
> attached (Add Input → Notebook Output) for the rung above the ladder, and
> **Internet on** so the notebook can install a matching `kaggle-environments`.

## cell [1] — markdown

---
## 1. Setup

One thing worth being fussy about: **pin the engine version**, and then *verify the pin
actually took*.

This is not a formality. The same game on the same seed can pay out very differently
across releases. Every number in the current reference dataset was measured on
**1.32.7**, and the check below confirms that by replaying a game straight out of
`head_to_head_games.csv` and requiring it to reproduce to the coin.

Worse, checking the version string is not enough. `importlib.metadata.version()` reads
the *newly written* package metadata, while `import kaggle_environments` can still
resolve to an older copy earlier on `sys.path` — so a pip install reports success, the
version check passes, and the engine you are actually running is the old one. I lost
several hours to exactly that, comparing measurements taken on three different engines
without realising it.

So the cell below installs the pin, then **replays a game from the dataset and asserts
the bank matches**. A behavioural fixture cannot be fooled by a stale import.

## cell [2] — code

**output:**

```text
installing kaggle-environments==1.32.7 (found: 1.29.3)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 40.9/40.9 kB 1.3 MB/s eta 0:00:00
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 60.7/60.7 MB 30.7 MB/s eta 0:00:00
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 16.0/16.0 MB 88.0 MB/s eta 0:00:00
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 20.2/20.2 MB 76.1 MB/s eta 0:00:00
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.8/1.8 MB 62.0 MB/s eta 0:00:00
kaggle-environments (reported): 1.32.7
kaggriculture environment loads OK
```

## cell [3] — code

**output:**

```text
dataset: /kaggle/input/datasets/raykkretzschmar/kaggriculture-reference-agents
contents: ['LICENSE', 'NOTICE', 'agents_manifest.csv', 'baseline_league.csv', 'broker_bea.py', 'closer_cleo.py', 'crop_economics.csv', 'fallow_finn.py', 'head_to_head_games.csv', 'homestead_hana.py', 'ledger_lena.py', 'melon_mateo.py', 'price_curves.csv', 'rancher_rita.py', 'rotation_rosa.py', 'season_timeline.csv', 'slotter_silas.py', 'wheat_walter.py']
```

## cell [4] — code

**output:**

```text
PASS  fallow_finn vs wheat_walter, seed 7000, seat 0: expected 3,000/6,694, got 3,000/6,694
```

## cell [5] — markdown

---
## 2. Meet the opponents

Ten agents in two bands, and they isolate different variables.

**Tiers 0–5 — authored.** Written from scratch, all sharing a **byte-identical action
scheduler**; the only difference between them is a `POLICY` dict at the top of each
file. That is deliberate: any gap in results comes from *economic decisions* alone, not
from one agent having better pathfinding than another. Diff two of these and the diff
is the lesson.

**Tiers 6–9 — the shared meta line.** These hold the opposite variable constant. All
four run the *same* production plan — the public meta line that shows up identically
across large groups of unrelated teams in public replays — and differ only in their
**market layer**: what to sell, in what order, and when to hold. Their head-to-head
ordering differs from their standalone bank ordering.

Together: tiers 0–5 teach you how to build a farm, tiers 6–9 show you that once
everyone builds the same farm, selling is the whole game. Expect a large jump between
the two bands — tier 5 banks ~46k, while the meta band banks ~149k–165k.

## cell [6] — code

**output:**

```text
' tier     agent_name                                                       headline  expected_bank  hands  extra_quadrants               crops   animals\n    0    Fallow Finn                       Never plants anything. The reward floor.           3000    0.0              0.0                none      none\n    1   Wheat Walter                    One farmer, wheat only, harvests too early.           7056    0.0              0.0               WHEAT      none\n    2  Rotation Rosa                     Hires help and runs a three-crop rotation.          12929    4.0              0.0 WHEAT|CARROT|TOMATO      none\n    3 Homestead Hana         Buys one quadrant and scales staples with a real crew.          16030    8.0              1.0 CARROT|WHEAT|TOMATO      none\n    4    Melon Mateo                 Farms the premium crop and refuses to dump it.          28349    6.0              1.0         MELON|WHEAT      none\n    5   Rancher Rita         Livestock at scale, on the back of a wheat feed chain.          46211    8.0              2.0               WHEAT COW|SHEEP\n    6     Broker Bea               Meta field plan with opportunistic wheat timing.         164265    NaN              NaN                 NaN       NaN\n    7    Ledger Lena      Meta field plan with a different sell-ordering trade-off.         164540    NaN              NaN                 NaN       NaN\n    8  Slotter Silas                   Meta field plan with a reordered SELL layer.         162999    NaN              NaN                 NaN       NaN\n    9    Closer Cleo Meta field plan, sells reordered in place so buys stay funded.         148546    NaN              NaN                 NaN       NaN'
```

## cell [7] — code

**output:**

```text
--- tier 0: Fallow Finn -----------------------------------------
  strategy: Returns PASS on every one of the 720 turns and issues no market orders, so the farm ends the season exactly as it started.
  lesson  : Fixes the bottom of the scale. Any agent that cannot beat Finn is losing money somewhere -- usually by buying seeds or livestock it then fails to water or feed.

--- tier 1: Wheat Walter ----------------------------------------
  strategy: Buys wheat seed, plants it in the starting NW quadrant, waters what he can reach and harvests the instant the crop is legal to harvest on day 2. Hires nobody and never buys land.
  lesson  : Two beginner mistakes, isolated. Harvesting at first_yield_day instead of max_yield_day throws away the watering bonus window: wheat taken on day 2 yields 1 unit where day 4 yields 4. And one farmer has only 24 actions a day, so most of the 25 starting tiles sit idle all season.

--- tier 2: Rotation Rosa ---------------------------------------
  strategy: Hires 4 hands every morning and fills the NW quadrant with wheat, carrot and tomato in a 50/30/20 split. Waits for the full watering bonus window before harvesting one-time crops. Never buys land or livestock.
  lesson  : Labour is nearly free. Four hands cost 1+1+2+3 = 7 coins for the whole day and multiply the action budget from 24 to 120. Fixing the harvest timing on top of that lifts Walter's bank by roughly two thirds for seven coins a day.

--- tier 3: Homestead Hana --------------------------------------
  strategy: Buys the NE quadrant, ramps from 4 to 8 hands as the work grows, and runs a carrot-led staple mix (40% carrot, 20% tomato, 40% wheat) across both quadrants. Holds modest price floors on carrot and tomato and meters sales into 30-unit lots.
  lesson  : Land and labour scale staples -- but only so far. Measured across seeds, buying a *second* extra quadrant makes this agent worse, not better: 3,000 coins of land is more than staple crops can repay. A quadrant is only worth buying when you have something valuable to put on it.

--- tier 4: Melon Mateo -----------------------------------------
  strategy: Buys the NE quadrant, hires 6 hands and devotes 70% of his land to melon with wheat as filler. Fertilizes melons through the bonus window to reach the 6-unit cap, then sells at most 12 melons a turn and refuses to sell below 120.
  lesson  : Melon grosses about 115 per tile per day, five times wheat. But its glut curve is quadratic with above_target 3.60, so the market only absorbs roughly 150 melons before the price hits the $1 floor. Metering sales and holding a floor is worth more than growing more melons -- which is also why extra land does not help him.

--- tier 5: Rancher Rita ----------------------------------------
  strategy: Buys two extra quadrants, hires 8 hands, builds 16 pastures and stocks them with 10 cows and 6 sheep. Feeds and CAREs every animal daily, grows her own wheat for feed and tops up from the market below 55 a unit.
  lesson  : Animals out-earn crops per action once CARE is running: a cared cow yields 3 milk every 2 days instead of 1. But a cow yields nothing at all for its first 8 days, so the binding constraint is working capital, not land. Rita holds 16 days of feed money in reserve before buying an animal. With a 4-day reserve instead she goes bankrupt on day 3 against a wheat-heavy opponent, the whole herd starves, and she scores zero -- losing to tier 1. An animal dies permanently after two unfed days, and there is no way back.

--- tier 6: Broker Bea ------------------------------------------
  strategy: Runs the shared meta field plan -- an 8-cow / 5-sheep / 6-strawberry build across three quadrants with a full crew -- and layers on a market schedule that times wheat purchases against the opponent's cash position rather than buying on a fixed cadence.
  lesson  : The first thing to notice is how far above the authored ladder this sits. The second is that the production plan is not what makes it strong: tiers 6-9 all share the same field plan and differ only in when they sell, and that alone spreads them by thousands of coins.

--- tier 7: Ledger Lena -----------------------------------------
  strategy: Same meta field plan and the same reordering idea as Slotter Silas, tuned to a different balance between selling premium goods early and keeping staples flowing.
  lesson  : A useful A/B against Slotter Silas: identical production, identical strategy in outline, measurably different results. If you want to know whether your own market layer is any good, these two bracket the question.

--- tier 8: Slotter Silas ---------------------------------------
  strategy: Same meta field plan, with the market queue reordered so that premium goods take the earliest slots of the turn and the glut-resistant staples fill in behind them.
  lesson  : Market orders resolve in list order, and the first unit of a sale gets the best price. Reordering the queue costs nothing and is worth real money.

--- tier 9: Closer Cleo -----------------------------------------
  strategy: Same meta field plan, but the SELL layer only reorders within the market slots the plan already used for selling. Nothing is moved into a slot that was holding a purchase.
  lesson  : The subtlest lesson in the dataset, and the most expensive one to learn the hard way. Sells fund the buys that follow them in the same queue; hoist the sells out of their original slots and a BUY_PRODUCT WHEAT later in the turn fails on a near-zero balance, animals go unfed, and the farm quietly loses far more than the reordering gained.
```

## cell [8] — markdown

---
## 3. Why the top tiers do what they do

Before ranking anything, look at this table. It is the single most useful thing I
worked out about this game, and it explains the whole top half of the ladder.

Every product has an independent **glut curve**. Sell into the market and the price
drops — but *how fast* varies enormously. The `units_until_price_floor` column is the
punchline: it is how many units you can sell before that product is worth $1.

## cell [9] — code

**output:**

```text
'   product  base_price  anchor_throughput_T glut_shape  glut_target scarcity_shape  scarcity_target  price_at_50_sold  price_at_150_sold  price_at_400_sold  price_at_1000_sold units_until_price_floor\n     MELON         250                  300         sq          3.6            log              0.2               225                 25                  1                   1                     158\n      WOOL         200                  105         sq          3.2            log              0.2                55                  1                  1                   1                      59\n      MILK         160                  122     linear          1.6           sqrt              0.6                55                  1                  1                   1                      76\nSTRAWBERRY         120                  100     linear          1.6           sqrt              0.7                24                  1                  1                   1                      62\nFERTILIZER         100                  200     linear          0.4         linear              0.4                90                 70                 20                   1                     493\n    TOMATO          60                  200       sqrt          0.6          hinge              0.4                42                 29                  9                   1                     529\n       EGG          50                  332        log          0.2          hinge              0.4                43                 41                 40                  38                   >6000\n    CARROT          35                  450       sqrt          0.7          hinge              1.0                27                 21                 12                   1                     842\n     WHEAT          25                  400        log          0.2           sqrt              0.8                22                 21                 20                  19                   >6000'
```

## cell [10] — code

**output:**

*[image omitted — see the notebook]*

## cell [11] — markdown

Read that chart and the ladder stops looking arbitrary:

- **MELON** grosses ~115 per tile per day, about five times wheat — but its glut curve
  is *quadratic* (`above_target` 3.60), so the market absorbs only ~150 melons before
  the price floors. That is why **Melon Mateo** meters his sales into 12-unit lots and
  holds a price floor, and why buying more land does *not* help him.
- **MILK** and **WOOL** floor almost as fast. **Rancher Rita** still wins with them,
  because livestock earns far more *per action* than crops once `CARE` is running.
- **WHEAT** and **EGG** are logarithmic (`above_target` 0.20) — nearly glut-proof.
  Wheat is why Rita can run a feed chain without wrecking her own margins.

The general lesson: **in this game, deciding what to sell matters more than deciding
what to grow.**

## cell [12] — markdown

---
## 4. Load the reference agents

Nothing clever here — the agents are plain single-file Python modules exposing
`agent(obs)`, so `importlib` is all it takes. This is exactly how the competition
loads your `main.py`, which makes it a good habit.

## cell [13] — code

**output:**

```text
loaded 10 reference agents: fallow_finn (t0), wheat_walter (t1), rotation_rosa (t2), homestead_hana (t3), melon_mateo (t4), rancher_rita (t5), broker_bea (t6), ledger_lena (t7), slotter_silas (t8), closer_cleo (t9)
```

## cell [14] — markdown

### One more opponent: the top of the public meta

The ladder above tops out at Closer Cleo. There is a rung above it that is not in the
dataset, because it is not mine to redistribute: the agent shipped by my other notebook,
[Kaggriculture: Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta),
which is built on a public replay tape and beats **all ten** reference agents 60–0–0 —
Cleo included, by about 13,500 coins.

It is attached here as a *notebook output* (Add Input → Notebook Output) rather than
copied, so what you rank against is byte-for-byte the artifact that notebook published.
If the input is missing the cell below just skips it and the rest of the notebook runs
unchanged.

## cell [15] — code

**output:**

```text
top-meta host: /kaggle/input/kaggriculture-findings-from-zero-to-top-meta/main.py (75,098 bytes)
```

## cell [16] — markdown

---
## 5. Two worked examples: an idea I killed, and one that survived

Before you plug in your own agent, here is the harness doing the job it exists for —
on me. I had a new agent, I was fairly confident in it, and it is not in the dataset.
This is why.

### The hypothesis

Straight out of `price_curves.csv`: **EGG never floors.** Its glut curve is logarithmic
with `above_target` 0.20, so 4,700 eggs only move the price from 50 to about 35. MILK is
linear at 1.60 and floors after roughly **76** units; WOOL is quadratic and floors after
**59**. Rancher Rita (tier 5) sells milk and wool. Her ceiling therefore looked like a
*price* problem, not a production problem — so bolting a goose wing onto her working
wheat feed chain should add an uncapped revenue stream to a herd already paid for.

That is a clean, evidence-backed argument. It is also wrong.

### Attempt 1 — add geese to Rita

32 configurations: coop share, flock size, when the coops start, feed float, sell chunk.
**All 32 lost to Rita**, the best by −7,569. But that test moved three things at once —
more mouths on the feed chain, fewer tiles growing wheat, more structures — so it does
not tell you *which* one hurt.

### Attempt 2 — hold everything constant, vary only the mix

Same 16 animals, same 16 structures, same land, same feed load. Only the composition
changes:

| cows | sheep | geese | bank | vs Rita |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 6 | 0 | 52,957 | — (Rita) |
| 12 | 4 | 0 | 54,512 | +1,555 |
| **16** | **0** | **0** | **57,407** | **+4,450** |
| 10 | 0 | 6 | 38,845 | −14,112 |
| 8 | 0 | 8 | 36,638 | −16,319 |
| 0 | 0 | 16 | 10,602 | −42,356 |

Every goose variant loses badly, and an all-goose farm is a catastrophe. Meanwhile
dropping the sheep and running 16 cows looked like a **+4,450** improvement.

### The part that matters

That +4,450 was measured on the same seeds I tuned on. Re-run on **held-out** seeds
(8000–8005, both seats), the all-cow agent **loses to Rita 3–9**, margin −3,627. It beats
every other tier 12–0 and loses to the one that counts.

So there is no new tier. The idea died, and it died specifically because I checked it on
seeds it had not seen. If you take one habit from this notebook, take that one: **tune on
one seed set, decide on another.** Six games on the seeds you tuned with will tell you
whatever you want to hear.

The cell below reproduces the flip on a 3-seed subset so it finishes in about a minute —
expect roughly 4–2 for the candidate on the tuned seeds and 1–5 against it on the
held-out ones. The 12-game run quoted above (3–9) is the same effect measured harder.

## cell [17] — markdown

### Why eggs lose, and why the price curve misled me

`price_curves.csv` measures a **static** market. Real games are not static: town shops
consume product every four turns, all season, which continuously drains inventory and
holds the price up. What actually decides your realised price is **how many shops demand
your product**, not how steep its glut curve is.

| Product | Shops demanding it | Base price | Shop demand/day |
| :--- | ---: | ---: | ---: |
| WHEAT | 5 | 25 | 30 |
| STRAWBERRY | 4 | 120 | 24 |
| **MILK** | **3** | **160** | **18** |
| EGG | 2 | 50 | 12 |
| CARROT / TOMATO | 2 | 35 / 60 | 12 |
| WOOL | 1 | 200 | 12 |
| **MELON** | **0** | **250** | **0** |

Measured at the end of a 720-turn season, this is what that does:

| Farm | MILK inventory | MILK price | EGG inventory | EGG price |
| :--- | ---: | ---: | ---: | ---: |
| 16 cows | **−148** (scarce) | **266** | −302 | 68 |
| 16 geese | −464 | 347 | **+104** (glutted) | **42** |

Three shops drain milk faster than sixteen cows can supply it, so milk sells **above** its
$160 base for the entire season — the 76-unit "ceiling" never binds. Eggs, on two shops at
a $50 base, do glut and sell at 42. The uncapped product is worth less per action than the
capped one that nobody can keep in stock.

The same table explains the rest of the ladder. **Melon appears in no shop at all** —
only the town centre buys it, a couple of units a day — which is the real reason Melon
Mateo tops out around 44k no matter how much land he buys. And **wool has a single shop**,
which is why deleting the sheep helped at all.

So: `units_until_price_floor` is the wrong column to optimise. Multiply base price by shop
demand and you get much closer to what you can actually bank.

## cell [18] — code

**output:**

```text
tuned-on  (7000-7002):  2-4  margin -3,951   -> Rita wins
held-out  (8000-8002):  0-6  margin -8,755   -> Rita wins
```

## cell [19] — markdown

---
## 5. Default submission artifact: K304 diversified horizon

This notebook packages **`k304_diversified_horizon`** byte-for-byte as its default
`submission.tar.gz`, and the evaluation below loads that exact archive.

K304 preserves C165's complete horizon-4 farm and economic route, but broadens its
opponent response beyond clone detection. At four safe checkpoints it reads only the
opponent's public farm and counts committed plants, cows, sheep, melons and
strawberries. Two production-pressure votes activate the horizon-4 premium market
programme. The decision is persistent; field actions are never spliced or displaced.

This is the deliberately diversified second route beside K301. In a paired 60-game
gate against six current opponent families, K304 scored **34-26** versus C165's
**33-27**, improving mean margin from +3,270 to +3,730 with zero errors. More
importantly, a source-exact replay audit showed meaningful behavioural separation:
K304 changed 871 market decisions across **18/18** games against production-heavy
live-derived families, while remaining identical to C165 in **4/4** low-pressure
control games. It is therefore opponent-adaptive rather than an unconditional timed
switch.

Important evaluation boundary: the published reference ladder in this notebook is
intentionally pinned to 1.32.7 so its stored games replay exactly. The archive below is
the exact selected K304 artifact; the short ladder run is an artifact and compatibility
check, not a reproduction of the broader live-field gates above. Those opponents are
observation-derived reconstructions of public trajectories rather than private source
agents, and the underlying production route is replay-derived. It should not be
represented as an original policy, and only live competition play can establish its
public rating.

## cell [20] — code

**output:**

```text
wrote /kaggle/working/main.py  (21,723 bytes, sha256=742cea3a9a053403bf8e351b400a60a1d30bd9fd05c88d04ef24635416091d79)
wrote /kaggle/working/submission.tar.gz  (12,665 bytes)
packaged k304_diversified_horizon: status=DONE  bank=179,301
```

## cell [21] — markdown

---
## 6. Plug in your own agent

Three ways, pick whichever suits you. **Option A** is the one to use if you are just
forking this notebook to try an idea.

## cell [22] — markdown

### Option A — write it in a cell

Edit the cell below. The template is a deliberately mediocre wheat loop so you can see
the machinery work end to end; replace the body with your own policy.

## cell [23] — code

**output:**

```text
Writing my_agent.py
```

## cell [24] — markdown

### Option B — from your own Kaggle dataset

If your agent already lives in a dataset (handy for anything with weights or several
modules), attach it and point at the file.

### Option C — from a submission archive

If you submit a `submission.tar.gz`, evaluate *that exact artifact* rather than a copy
of the source. This is the option I trust most, because it catches packaging mistakes —
a missing module or a wrong path shows up here instead of on the leaderboard.

Handles `.tar.gz` / `.tgz` / `.tar.bz2` / `.tar.xz` / plain `.tar`, and `.zip`.
**`.7z` is not supported** — `py7zr` is not installed on Kaggle images, and the
competition wants a `.tar.gz` anyway, so repack rather than fight it.

## cell [25] — code

**output:**

```text
challenger loaded: k304_diversified_horizon via archive
```

## cell [26] — markdown

### Sanity check first

Before spending minutes on a round robin, play one short game and confirm the agent
does not crash. A Kaggriculture agent that raises gets status `ERROR` and forfeits, and
because invalid actions are *silent no-ops* you can otherwise burn a full evaluation on
an agent that quietly did nothing at all.

## cell [27] — code

**output:**

```text
120-turn smoke test — rewards: [396.0, 3000.0] statuses: ['DONE', 'DONE']
OK
```

## cell [28] — markdown

---
## 7. The evaluation

Two details make the difference between a number you can trust and one you cannot:

**Swap seats.** Player 0 and player 1 are not symmetric — market orders are processed
in player order, so seat 0 gets first call on a contested price. Every pairing is
played from both seats.

**Fix the seeds.** Weeds, shop unlock order and shop selection are all seeded. Reusing
the same seed list keeps runs comparable when you tweak your agent.

## cell [29] — code

## cell [30] — code

**output:**

```text
  k304_diversified_horizon 6-0 fallow_finn  (tier 0, margin +153,992)
  k304_diversified_horizon 6-0 wheat_walter  (tier 1, margin +147,406)
  k304_diversified_horizon 6-0 rotation_rosa  (tier 2, margin +137,019)
  k304_diversified_horizon 6-0 homestead_hana  (tier 3, margin +136,430)
  k304_diversified_horizon 6-0 melon_mateo  (tier 4, margin +138,788)
  k304_diversified_horizon 6-0 rancher_rita  (tier 5, margin +115,752)
  k304_diversified_horizon 6-0 broker_bea  (tier 6, margin +21,189)
  k304_diversified_horizon 6-0 ledger_lena  (tier 7, margin +20,872)
  k304_diversified_horizon 6-0 slotter_silas  (tier 8, margin +20,364)
  k304_diversified_horizon 6-0 closer_cleo  (tier 9, margin +30,619)
  k304_diversified_horizon 6-0 top_meta_host  (tier 10, margin +602)
  top_meta_host 6-0 closer_cleo  (margin +32,030)

reused 45 precomputed reference pairings from the dataset

57 pairings in 526s   errors: 0
```

## cell [31] — markdown

---
## 8. Ranking with Bradley-Terry

Win rate alone is misleading in a ladder: beating tier 0 four times is not the same
achievement as beating tier 5 twice, but a raw win rate treats them identically.

Bradley-Terry fits each agent a latent strength from *who* it beat, so wins against
strong opponents count for more. The competition uses the same family of model for
final standings, which is the main reason I rank this way locally.

I report it on an Elo-like scale (400 points per 10x strength, mean anchored at 1500)
because those numbers are easier to hold in your head than raw strengths.

## cell [32] — code

**output:**

```text
agent | slug | tier | bt_rating | record | win_pct | mean_margin
1 | k304_diversified_horizon | k304_diversified_horizon | you | 2049 | 66-0-0 | 100.0 | 83912
2 | Closer Cleo | closer_cleo | 9 | 1924 | 53-13-0 | 80.3 | 64781
3 | Ledger Lena | ledger_lena | 7 | 1862 | 45-15-0 | 75.0 | 79804
4 | Slotter Silas | slotter_silas | 8 | 1858 | 45-15-0 | 75.0 | 79218
5 | Top Meta Host | top_meta_host | 10 | 1803 | 6-6-0 | 50.0 | 15714
6 | Broker Bea | broker_bea | 6 | 1748 | 37-23-0 | 61.7 | 79525
7 | Rancher Rita | rancher_rita | 5 | 1610 | 30-30-0 | 50.0 | -40656
8 | Melon Mateo | melon_mateo | 4 | 1435 | 22-38-0 | 36.7 | -56818
9 | Homestead Hana | homestead_hana | 3 | 1388 | 20-40-0 | 33.3 | -75575
10 | Rotation Rosa | rotation_rosa | 2 | 1118 | 12-48-0 | 20.0 | -69656
11 | Wheat Walter | wheat_walter | 1 | 825 | 6-54-0 | 10.0 | -76332
12 | Fallow Finn | fallow_finn | 0 | 379 | 0-60-0 | 0.0 | -86216
```

## cell [33] — code

**output:**

*[image omitted — see the notebook]*

## cell [34] — markdown

---
## 9. Reading the result

Find the highest tier you beat consistently, then look up what that tier does in the
manifest above. The gaps are where your next improvement is.

## cell [35] — code

**output:**

```text
k304_diversified_horizon vs the ladder
==========================================================
  WIN  vs tier 0 Fallow Finn        6-0   margin +153,992
  WIN  vs tier 1 Wheat Walter       6-0   margin +147,406
  WIN  vs tier 2 Rotation Rosa      6-0   margin +137,019
  WIN  vs tier 3 Homestead Hana     6-0   margin +136,430
  WIN  vs tier 4 Melon Mateo        6-0   margin +138,788
  WIN  vs tier 5 Rancher Rita       6-0   margin +115,752
  WIN  vs tier 6 Broker Bea         6-0   margin +21,189
  WIN  vs tier 7 Ledger Lena        6-0   margin +20,872
  WIN  vs tier 8 Slotter Silas      6-0   margin +20,364
  WIN  vs tier 9 Closer Cleo        6-0   margin +30,619
  WIN  vs tier 10 Top Meta Host      6-0   margin +602

Highest tier beaten: 10 (Top Meta Host)

You beat the top-meta host as well. There is no rung left here --
raise SEEDS for tighter error bars, then submit.
```

## cell [36] — markdown

### The checklist I actually use

Most of my own broken agents failed one of these, and every one of them is cheap to
check. In rough order of how much money they cost me:

1. **Hire hands.** Four hands cost `1+1+2+3 = 7` coins for a whole day and take you
   from 24 actions to 120. Not hiring is the single most expensive mistake available.
2. **Sell before you buy, in the same turn.** The market queue is processed in list
   order, so a `SELL` placed ahead of a `BUY` funds it immediately. Budget against
   post-sale cash or you will sit at zero coins all season with a full shed.
3. **Feed before you expand.** An animal dies *permanently* after two unfed days.
   Wheat has to be bought before land or livestock, never after.
4. **Do not hoard seeds.** Twenty-five melon seeds is 2,000 coins earning nothing.
   Hold only what you can plant in the next few turns.
5. **Spread your carriers.** One hand with a full sack cannot walk a whole quadrant in
   24 turns. Send several part-loaded hands instead.
6. **Meter premium sales.** Melon, milk, wool and strawberry all floor fast. Check
   `price_curves.csv` before dumping a harvest.
7. **Stop investing near the end.** Coins spent on day 28 never come back, and produce
   still in the shed at the final bell scores exactly nothing — liquidate.
8. **Count what your hands are carrying.** Wheat in a hand's inventory is still yours;
   forget it and you will sell your feed each morning and buy it back at double by
   afternoon.

Two engine details that cost me real time, and that the written rules get wrong:

- The rules say `CARE` banks **+2** per day. The engine adds **+1**
  (`kaggriculture.py`, `_daily_refresh_animals`). Trust the source.
- While only NW is unlocked, `(4, 4)` is the **only** usable shed tile — the other
  three access tiles sit in locked quadrants, and `PICKUP`/`DROP` silently no-op on
  `LOCKED`. Hired hands spawn on those locked tiles and lose a turn walking in.

## cell [37] — markdown

---
## 10. Turning up the rigour

The default budget (3 seeds, challenger-only) is tuned to be fast enough that you
actually run it. Before trusting a close result, raise it:

```python
SEEDS = list(range(9001, 9021))   # 20 seeds
FULL_ROUND_ROBIN = True           # replay the reference pairings on your seeds too
```

That is 20 seeds x 2 seats x 21 pairings = 840 games, roughly 20 minutes. Worth it when
two candidates are within ~50 BT points, because a 6-game sample cannot separate them.

A few other things worth trying from here:

- **Beat the ladder, then beat yourself.** Add your previous submission as a seventh
  agent — the rung that matters most is your own last version.
- **Check seat bias.** If your agent wins from seat 0 and loses from seat 1, you have a
  market-ordering dependency worth understanding.
- **Watch a game.** `env.render(mode="ipython", width=900, height=700)` after a `play()`
  call is the fastest way to spot a farmer walking in circles.

---

*Reference agents: [kaggriculture-reference-agents](https://www.kaggle.com/datasets/raykkretzschmar/kaggriculture-reference-agents)
(agent code MIT; data and analysis CC BY-SA 4.0; see the dataset's provenance notes).
Measured on `kaggle-environments` 1.32.7. If you find a rung mis-ranked, tell me
in the comments and I will re-measure.*
