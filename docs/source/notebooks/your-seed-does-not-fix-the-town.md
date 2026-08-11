# your-seed-does-not-fix-the-town

> Extracted by `analysis/nb_extract.py` from `notebooks/your-seed-does-not-fix-the-town.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# Your seed does not fix the town

**Kaggriculture draws each town shop from the same random stream it has just used to
spawn weeds — one draw per *empty unlocked tile*, on both farms. The shop that unlocks
is therefore a function of how much bare land you and your opponent happened to have
that evening, not of the episode seed alone.**

That has three consequences, and this notebook measures all three on the installed
engine rather than asserting them:

1. **A fixed `configuration["seed"]` does not fix the world.** Adding one occupied tile
   to *either* farm re-rolls every later shop unlock. Measured below on 12 seeds out of 12.
2. **The draw is worth real money, and the exposure grows as you get better.** Holding the
   seed, the opponent and every other rule constant and varying *only* the order the eight
   shops arrive in, a crop farm's season swings about 14% from worst draw to best — while
   the barely-trading built-in `starter` swings under 1%. (Section 4.)
3. **Whether your fixed-seed A/B test is controlled depends on which knob you turn.** A
   change that only reorders market orders draws the identical town on every seed and
   resolves a ten-coin effect from sixteen episodes. A change that touches how many tiles
   are occupied — labour, planting, harvesting, digging, land — re-rolls the town on *every*
   seed and buries the effect under a thousand coins of noise. Section 5, with the harness
   in Section 7.

Then there is the balance change announced on 6 August
([discussion](https://www.kaggle.com/competitions/kaggriculture/discussion/733431),
[PR #1394](https://github.com/Kaggle/kaggle-environments/pull/1394)), which switches shops
to being drawn **with replacement**. Section 6 works out what that does, exactly rather
than approximately: the all-eight-shop town every current strategy is tuned on stops being
guaranteed and becomes a **1-in-416** event, each shop type is missing from **34.4%** of
games, and **wool** — the only product in the game with a single shop demanding it — loses
**95% of its late-season demand** in the third of games with no yarn store. Repeating the
Section 4 swing measurement under the modelled new rules takes it from **14% to 36%**.

Section 7 then prices that out for the herd everyone is running. Using a market model
checked against the engine product by product, a six-sheep herd's season is worth about
**$39k with a yarn store and $11k without** — and cows, whose milk three shop types want,
earn the most in **70%** of drawn towns while sheep manage 28%. Shops unlock from day 3
onward; pastures are bought in the opening. **You commit the herd before you know the town.**

Nothing here is a leaderboard claim. It is engine behaviour, measured.

## cell [1] — markdown

## 1. Setup, and checking the claim against the engine you actually have

Every measurement below is pinned to `kaggle-environments==1.32.5`, the release in use on
2026-08-07. That matters more than usual here: the market model has changed between minor
releases before, and the balance change discussed in Section 6 changes it again. Pinning
means the numbers in this notebook keep reproducing after the engine moves on, and Section 6
tells you what moves.

Then, rather than quote the engine source, the setup cell reads it out of the installed
package and asserts the two things the rest of the notebook depends on: that weed spawning
and the shop draw share one per-day RNG, and that weed spawning runs first. If a release
breaks that ordering the cell fails, which is the intended behaviour — a stale claim is
worse than a broken notebook.

## cell [2] — code

**output:**

```text
pinned: kaggle-environments==1.32.5
```

## cell [3] — code

**output:**

```text
kaggle-environments: 1.32.5
engine already has the with-replacement shop draw: False

--- kaggriculture._end_of_day, the relevant lines ---
    rng = random.Random((seed * 1_000_003) ^ day)
    _spawn_weeds(farm, board_size, weed_chance, rng)
    remaining = [s for s in SHOPS if s not in town["unlocked_shops"]]
    choice = rng.choice(sorted(remaining))
    town["unlocked_shops"].append(choice)

OK: one per-day RNG, weeds consume it first, the shop draw takes what is left.
```

## cell [4] — markdown

## 2. The mechanism

`_spawn_weeds` calls `rng.random()` exactly once for every tile that is `None` — an empty
tile inside an unlocked quadrant. `"LOCKED"` tiles and any tile holding a plant, a weed, a
coop or a pasture cost nothing. It is called for player 0 and then for player 1, off the
same stream, and only afterwards does the shop unlock take its draw.

So the position in the stream at which the shop is chosen equals

```
(player 0's empty unlocked tiles) + (player 1's empty unlocked tiles)
```

on that evening. First, a check on the counting, then the consequence in pure RNG terms:
how often does shifting the stream by a single draw change which shop comes out?

## cell [5] — code

**output:**

```text
4 tiles, of which 2 are empty -> 2 rng.random() calls

One extra bare tile anywhere on either farm changes the day-3 shop in 1306/2000 seeds = 65.3%
(a fully independent re-roll would change it 87.5% of the time, so this is close to one)
```

## cell [6] — markdown

## 3. It is not just your own farm: the opponent re-rolls your town

The cell above is arithmetic about a random number generator. This one is a real episode.

Player 0 plays the built-in `starter` agent both times, on the same seed. The opponent
differs by **one tile and nothing else that can touch the market**:

* `idle` passes for all 720 turns — 25 empty tiles.
* `idle_plus_one_tile` buys a single carrot seed, plants it, never waters it and never
  sells anything — the plant dies into a weed that first night and occupies its tile for
  the rest of the season, leaving 24 empty tiles.

Seeds are bought from unlimited supply at a fixed price and are not part of market
inventory, so that carrot never touches a price. Neither opponent ever sells.

To make sure player 0 really is the constant, its every action is recorded and the two
runs are compared turn by turn. **Same seed, same 720 actions, different bank.**

## cell [7] — code

**output:**

```text
 seed    vs idle   vs idle+1 tile    delta   same town?  same play?
    0       3509             3499      -10   False       True
    1       3491             3495       +4   False       True
    2       3511             3507       -4   False       True
    3       3487             3503      +16   False       True
    4       3509             3487      -22   False       True
    5       3487             3495       +8   False       True
    6       3485             3503      +18   False       True
    7       3501             3495       -6   False       True
    8       3499             3509      +10   False       True
    9       3514             3504      -10   False       True
   10       3487             3514      +27   False       True
   11       3512             3489      -23   False       True

player 0 played the identical action sequence: 12/12 seeds
identical shop schedule:                      0/12 seeds
player 0's bank changed anyway:               12/12 seeds

First seed, side by side:
  vs idle          : ['YARN_STORE', 'PET_CAFE', 'ICE_CREAM_SHOP', 'BAKERY', 'FARMERS_MARKET', 'PIZZA_SHOP', 'SMOOTHIE_SHOP', 'BRUNCH_SPOT']
  vs idle+one tile : ['SMOOTHIE_SHOP', 'FARMERS_MARKET', 'ICE_CREAM_SHOP', 'BAKERY', 'YARN_STORE', 'PET_CAFE', 'PIZZA_SHOP', 'BRUNCH_SPOT']
```

## cell [8] — markdown

The `starter` agent farms a single tile and banks about $3,500, so the swing here is small
in absolute terms. It is not the size that matters in this section, it is that the size is
**not zero**: the seed did not fix the world. The next section measures what the town is
worth to a farm that actually trades.

## cell [9] — markdown

## 4. What the draw is worth

To measure the town we need an agent whose income depends on it. The one below is
deliberately ordinary — a greedy job scheduler on a crop farm, no animals, no cleverness —
but it is chosen so that its produce (strawberry, carrot, wheat) is what the shops actually
demand. It banks several times the built-in starter and nothing like the top of the ladder,
which is fine: it is a measuring stick, not a submission.

## cell [10] — code

**output:**

```text
field agent 12,571   vs built-in starter 3,477
```

## cell [11] — markdown

Now pin the town. `pinned_shops` overrides one thing and nothing else: the *identity* of
the shop that unlocks. Weeds still spawn from the same stream, the day still refreshes the
same way, both agents still play the same policy on the same seed. Only the order the eight
shops arrive in changes.

Twelve random orders, one fixed seed, two agents of very different trade volume. Everything
that varies below is the town.

## cell [12] — code

**output:**

```text
     starter (seed 7): median      3,502   worst      3,487   best      3,514   spread   0.8% of median
 field agent (seed 7): median     14,184   worst     13,165   best     15,128   spread  13.8% of median
 field agent (seed 21): median     14,222   worst     13,201   best     15,308   spread  14.8% of median
 field agent (seed 42): median     14,284   worst     13,265   best     15,228   spread  13.7% of median

field agent, seed 7 fixed, only the shop ORDER varies, n=12
     13,165   first three shops: BAKERY, SMOOTHIE_SHOP, YARN_STORE
     13,194   first three shops: PIZZA_SHOP, PET_CAFE, ICE_CREAM_SHOP
     13,603   first three shops: BRUNCH_SPOT, BAKERY, PET_CAFE
     13,881   first three shops: PET_CAFE, BRUNCH_SPOT, PIZZA_SHOP
     13,957   first three shops: ICE_CREAM_SHOP, YARN_STORE, FARMERS_MARKET
     14,126   first three shops: PET_CAFE, BRUNCH_SPOT, PIZZA_SHOP
     14,242   first three shops: ICE_CREAM_SHOP, YARN_STORE, BRUNCH_SPOT
     14,323   first three shops: BRUNCH_SPOT, ICE_CREAM_SHOP, PIZZA_SHOP
     14,381   first three shops: FARMERS_MARKET, PET_CAFE, YARN_STORE
     14,726   first three shops: FARMERS_MARKET, PIZZA_SHOP, BRUNCH_SPOT
     14,926   first three shops: BRUNCH_SPOT, SMOOTHIE_SHOP, ICE_CREAM_SHOP
     15,128   first three shops: ICE_CREAM_SHOP, FARMERS_MARKET, SMOOTHIE_SHOP
  spread 1,963 = 13.8% of the median season, standard deviation 623
  with no shops at all: 9,198 (54% below the median town)
```

## cell [13] — code

**output:**

*[image omitted — see the notebook]*

## cell [14] — markdown

Having a town at all is worth about half again on top of a townless season, and *which*
town you get is worth around a seventh of it. Neither is under your control, and neither is
pinned by the seed.

Note the two agents in the table above. The built-in starter sells a handful of carrots all
season and barely notices which shops arrive. The field agent works a whole quadrant and
swings by more than a tenth. **The exposure scales with how much you trade** — which means
the number that matters to a top-of-ladder farm, selling far more than either of these, is
plausibly larger than 14%, not smaller. Getting better at this game makes more of your
score depend on a draw you do not control.

A different agent shape will give a different figure again — a wool-and-milk ranch is
exposed to a different basket than a crop farm. What does not change is that the exposure
exists and that the seed does not remove it.

## cell [15] — markdown

## 5. Which changes are safe to A/B on a fixed seed, and which are not

The mechanism says the confound arrives through *tile occupancy*. So it should matter
enormously which knob you turn, and that is testable. Two one-knob changes to the agent
above, measured the way everyone measures: same seeds, same opponent, paired differences.

* **Market-only** — strawberry sell batch, 3 units per turn instead of 4. Changes the order
  book, cannot change which tiles are occupied.
* **Labour** — five hired hands instead of four. Changes how many tiles get tended, so it
  changes how many sit bare at nightfall.

Each is run twice: on the stock engine, and with the town pinned per seed so both arms face
the same eight shops in the same order. I expected both to be contaminated. Only one is.

## cell [16] — code

**output:**

```text
n = 16 seeds, paired differences against the same base agent

market only
  drew the SAME town as the base agent: 16/16 seeds
  stock engine : mean       -10   sd         1   95% CI [      -11,       -10]
  town pinned  : mean       -10   sd         2
  -> pinning changes nothing here; there was nothing to pin away
  -> calling an effect of 10 at 80% power takes about 1 seed with the town pinned

labour
  drew the SAME town as the base agent: 0/16 seeds
  stock engine : mean      +342   sd     1,322   95% CI [     -305,      +990]
  town pinned  : mean      +274   sd     1,074
  -> pinning cuts the noise sd by 19%, worth 1.5x the episodes
  -> calling an effect of 342 at 80% power takes about 77 seeds with the town pinned
```

## cell [17] — code

**output:**

*[image omitted — see the notebook]*

## cell [18] — markdown

The two panels are the same experiment on the same agent and the same seeds. The only
difference is which number was changed.

**The market-only knob is clean.** It cannot move a tile, so the town is identical on every
seed, stock and pinned agree exactly, and a single seed already resolves the ten-coin
effect. On a fixed seed, that experiment is a real experiment.

**The labour knob is not.** One fewer hand means fewer tiles tended, which means a different
number of bare tiles at nightfall, which re-rolls the town — on *every* seed. The paired
difference goes from a couple of coins of noise to well over a thousand, and calling the
effect at 80% power now takes dozens of seeds rather than one. Pinning the town removes part
of that and not all: the same change also perturbs the weeds and genuinely interacts with the
season, and pinning does not touch either.

So the rule is narrower and more useful than "fixed seeds are broken":

> **If the knob you are testing can change how many tiles are occupied on any evening —
> labour, planting, harvesting, digging, buying land — your fixed-seed A/B is comparing two
> different towns. If it only reorders market orders, it is not.**

Most of the interesting knobs in this game are in the first list.

This also explains why local win rates here can look decisive and mean very little. A change
that adds a few coins wins nearly every mirror match, because the two agents are otherwise
identical and the margin is a rounding error; a change worth thousands can lose a fixed-seed
comparison because it moved the shops. Neither is measuring strategy.

## cell [19] — markdown

## 6. After the balance change

On 6 August the organisers announced two rebalances
([discussion](https://www.kaggle.com/competitions/kaggriculture/discussion/733431)). The one
that matters here, from the [diff](https://github.com/Kaggle/kaggle-environments/pull/1394):

```python
# before: sampled without replacement from the shops not yet unlocked
remaining = [s for s in SHOPS if s not in town["unlocked_shops"]]
if remaining:
    town["unlocked_shops"].append(rng.choice(sorted(remaining)))

# after: drawn WITH replacement, capped at MAX_SHOP_INSTANCES = 8
if len(town["unlocked_shops"]) < MAX_SHOP_INSTANCES:
    town["unlocked_shops"].append(rng.choice(sorted(SHOPS)))
```

Today every game ends with all eight shop types open and only the order varies. After the
change the *composition* varies too, and the arithmetic is unforgiving. None of the
following is simulated — it is counted.

## cell [20] — code

**output:**

```text
Drawing 8 shop instances with replacement from 8 types:
  P(a given type never appears)  = (7/8)^8 =  34.4%
  P(all eight types appear)      = 8!/8^8  =  0.24%   (about 1 game in 416)
  E[distinct types in a town]    = 5.25 of 8

  copies of one specific shop:
    exactly 0:  34.4%
    exactly 1:  39.3%
    exactly 2:  19.6%
    exactly 3:   5.6%
    exactly 4:   1.0%

How many shop types demand each product:
  CARROT      2
  EGG         2
  MILK        3
  STRAWBERRY  4
  TOMATO      2
  WHEAT       5
  WOOL        1   <-- single source
```

## cell [21] — markdown

**Wool is the only product in the game with exactly one shop behind it.** The yarn store is
a single-product shop, so it eats double on every tick; lose it and wool has nothing left
but the town centre — which the same PR cuts from up to 4 units every 12 turns to 1 unit
every 24.

That matters because sheep are in the farm shape currently reported at the top of the
ladder — around eight cows and six sheep, per the public replay tracker in
[What the Top Farms Do](https://www.kaggle.com/code/cjlcjlcjl/kaggriculture-what-the-top-farms-do-a-live-meta)
(that composition is their measurement of the ladder, not mine; everything below is mine).
Here is what such a herd's wool market looks like before and after.

## cell [22] — code

**output:**

```text
one yarn store eats 12 wool/day (6 ticks/day, 2 per tick)

late-season wool demand (day 25)                  units/day
today, yarn store guaranteed                             20
after the change, one yarn store drawn                   13
after the change, no yarn store drawn                     1   <- 34.4% of games

that is a 95% cut in wool demand, in about one game in three

one cared-for sheep produces 1.33 wool/day; six produce 8.0/day
wool hits the $1 floor 59 units above its starting inventory of 10,000
```

## cell [23] — markdown

So six cared-for sheep clear in a single day roughly what a yarn-store-less town absorbs in
a week, and wool's glut curve is quadratic — the floor arrives fast. In about a third of
post-change games, a wool herd is farming something the town does not want.

The same reasoning applies in reverse: a town that draws three ice cream shops wants a lot
of strawberry and milk. **After this change, the shop list stops being flavour and starts
being the most important thing in the observation.** An agent that reads
`obs["town"]["unlocked_shops"]` and re-plans can chase that; a recorded action tape cannot,
because the town it was recorded in now recurs roughly once in 416 games.

Below the announced rules are modelled locally, both changes transcribed from the PR, and
the same swing measurement from Section 4 is repeated under them.

## cell [24] — code

**output:**

```text
     14,856   [('YARN_STORE', 3), ('BRUNCH_SPOT', 2)]
     13,564   [('YARN_STORE', 2), ('BAKERY', 2)]
     13,668   [('BAKERY', 4), ('PET_CAFE', 1)]
     13,893   [('ICE_CREAM_SHOP', 3), ('SMOOTHIE_SHOP', 2)]
     12,926   [('ICE_CREAM_SHOP', 2), ('PIZZA_SHOP', 1)]
     14,635   [('PET_CAFE', 3), ('FARMERS_MARKET', 1)]
     11,800   [('SMOOTHIE_SHOP', 3), ('YARN_STORE', 2)]
     11,852   [('PIZZA_SHOP', 3), ('BRUNCH_SPOT', 2)]
     10,017   [('YARN_STORE', 2), ('BAKERY', 2)]
     13,620   [('ICE_CREAM_SHOP', 3), ('PIZZA_SHOP', 2)]
     13,220   [('BAKERY', 2), ('SMOOTHIE_SHOP', 2)]
     12,568   [('PIZZA_SHOP', 3), ('SMOOTHIE_SHOP', 2)]

under the modelled new rules, seed 7, only the town varies, n=12
  worst 10,017   median 13,392   best 14,856
  spread 36.1% of the median (today, same measurement: 13.8%)

This models an unmerged pull request read on 2026-08-07, not the shipped engine.
Re-run it against the release before betting anything on the number.
```

## cell [25] — markdown

## 7. So what should you farm?

Everything so far has been about measurement. This section is about the decision, because
the arithmetic in Section 6 has a direct answer in it.

Pricing a season needs only the market, so it does not need an agent — but it does need the
model to be right. The cell below builds a single-product market and checks it against the
engine the only way that is unambiguous: with both players passing, nothing is ever sold,
so inventory moves purely by town consumption. If the model reproduces the engine's final
inventory for all nine products, the demand arithmetic is correct.

## cell [26] — code

**output:**

```text
seed 0: model reproduces the engine's final inventory for all 9 products
seed 3: model reproduces the engine's final inventory for all 9 products
seed 11: model reproduces the engine's final inventory for all 9 products
```

## cell [27] — markdown

Now price three herds. Six animals each, production rates taken from the engine's own
`ANIMALS` table assuming they are fed and cared for every day, sold in a steady metered
trickle from their first yield.

What this deliberately leaves out, because it is identical across three herds of the same
size and would only add noise to the comparison: feed (one wheat per animal per day),
the fertilizer each animal drops, and the tile each one occupies. The comparison is
therefore **per tile, not per dollar** — a goose is $300, a cow $400 and a sheep $500, which
matters against a $3,000 opening bank even though it washes out by the end of a season.

What it leaves out and should not: the opponent selling into the same market. Two sheep
herds in one game floor the wool price far faster than one, so treat the dollars below as
an upper bound and the *ratios between towns* as the result.

## cell [28] — code

**output:**

```text
6 goose: 12.0 egg/day from day 5
6 cow:  9.0 milk/day from day 9
6 sheep:  8.0 wool/day from day 7

herd   product   today median   after median   after p10
goose  egg             13,785         12,970      12,692
cow    milk            46,691         42,366      16,032
sheep  wool            39,768         24,408      11,052

which herd earns most, over 500 drawn towns:
  cow      351 = 70.2%
  sheep    141 = 28.2%
  goose      8 =  1.6%

sheep herd, with a yarn store : median $   39,121  (n=326)
sheep herd, no yarn store     : median $   11,052  (n=174)   -> 72% of the season gone
```

## cell [29] — code

**output:**

*[image omitted — see the notebook]*

## cell [30] — markdown

Three things fall out of that.

**Egg is the hedge that never pays.** Its glut curve is nearly flat, so twelve eggs a day
never move the price — and the base is $50, so the season lands in the same modest place
whatever the town does. The narrowest distribution on the chart, and the lowest.

**Wool is a bet on one shop.** With a yarn store the sheep herd is competitive with cows;
without one it loses most of its season, and that happens in about a third of drawn towns.
The bimodal shape on the chart is literally the presence or absence of a single building.

**Cows are the robust choice under the new rules**, because milk is demanded by three shop
types rather than one, so the draw has to go badly wrong three times over to strand it.

The uncomfortable part is the timing. Shops unlock on days 3, 6, 9 and so on, but pastures
and animals are bought in the opening. **You commit the herd before you know the town.**
That is the concrete form of the open-loop question people have been asking in the forum:
you cannot pick the right herd in advance, so the adaptive margin is in what you sell, when
you sell it, and how much you hedge across products — not in the opening.

## 8. The harness

Two context managers, thirty lines, no dependencies. Paste them above your tuning loop so
both arms of a comparison at least face the same town.

```python
with pinned_shops(schedule_for(seed)):
    ...          # both arms see the same eight shops in the same order

with no_shops():
    ...          # the floor: what your agent earns with only the town centre buying
```

What this buys you, honestly: on the labour test in Section 5 it removed about a sixth of
the noise standard deviation. Useful, not magic. Three things it does not do:

* **It does not fix the weeds.** Player 0's weed draws are taken before player 1's, so a
  change to your own occupancy still shifts your opponent's weeds. At
  `weedSpawnChance = 0.005` that is small next to the town, but it is not zero.
* **It does not make a genuinely seed-dependent effect go away.** Most of the residual noise
  on the labour test is the change really interacting with the season differently seed by
  seed. That is signal about robustness, not something to pin out.
* **It changes the distribution you are sampling from.** Pinned results tell you which
  variant is better *in the towns you pinned*. Pin a set of schedules that covers the range,
  and after the balance change pin baskets drawn with replacement rather than permutations,
  or you will be tuning for a town that shows up once in 416 games.

The cheapest thing in this notebook is not the harness, it is the question it forces:
**can the knob I am about to test change how many tiles are occupied?** If no, a fixed seed
is enough. If yes, budget for the noise before you trust the result.

### This is not an exploit

Worth saying plainly, because the coupling sounds like one. The episode seed is scrubbed
from the configuration before agents ever see an observation
(`resolve_episode_seed` in `kaggle_environments.utils`), and it is a 31-bit draw. An agent
can therefore *shift* the shop draw by leaving a tile bare, but it has no way to know what
the shifted draw will produce — it is turning a wheel with no numbers on it. There is no
directed advantage here for either player, and nothing in this notebook should be read as
one.

What the coupling costs is measurement validity, not fairness. It is a problem for your
tuning loop, not for the ladder.

## What I did not test

* Two agent shapes are played in the engine and both are crop farms. The 14% is one agent's
  exposure, not a universal constant. What the pair shows is that the exposure tracks trade
  volume, not that any particular number is the right one. The mechanism is the claim; the
  magnitude is an illustration.
* Section 7 prices the market, not a farm. It holds each herd's production fixed and
  perfect — fed and cared every day, sold in a steady trickle — so it is an upper bound on
  what the town will pay, not a prediction of what an agent will bank. Above all it ignores
  the opponent selling into the same market, which is a real and material omission: two
  sheep herds in one game floor the wool price far faster than one. Read the *ratios*
  between towns, which is what the section is for, rather than the absolute dollars.
* No ladder or leaderboard evidence appears anywhere in this notebook. Everything is local
  episodes against the built-in `starter`, or arithmetic on the engine's own constants.
* Section 6 and Section 7's "after" numbers model an unmerged PR. If it ships changed, those
  are wrong and Sections 1-5 are not.
* I have made no submission to this competition. Take the engine reading, the harness and
  the herd arithmetic; do not take the agent as advice.

*Engine: `kaggle-environments`, version printed in Section 1. Everything above recomputes
when you run it — there are no pasted numbers in the outputs.*
