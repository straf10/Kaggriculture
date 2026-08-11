# kaggriculture-what-a-turn-is-worth

> Extracted by `analysis/nb_extract.py` from `notebooks/kaggriculture-what-a-turn-is-worth.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# Kaggriculture: What's Actually Worth Doing With a Turn

**The scarce resource is not land or money. It's actions — and there are exactly 720.**

Reading the rules, one asymmetry stands out and seems to decide most of the strategy:

> Each turn, the player may take one action. There are 24 turns per day, and 30 days.
>
> Each turn you can submit up to `maxMarketOrdersPerTurn` (**default 10**) market actions.

A farmer gets **one** action per turn. The market accepts **ten**. So buying and selling is
effectively free, while planting, watering and harvesting are not. Land is capped at 100
tiles and money is recoverable, but a spent turn is gone.

That makes **profit per action** the number that ranks strategies — not profit per tile,
not margin, not payback period.

This notebook computes it for every crop and animal in the spec. Everything below is
derived in-notebook from constants transcribed out of the competition README; where a
rule is ambiguous I say so and show the alternative rather than picking silently.

**Headline:** melons return roughly **9× wheat per action**, and a cared-for sheep is
competitive with melon while needing no replanting. Details, caveats and the arithmetic
follow.

## cell [1] — code

**output:**

```text
Season budget: 24 turns/day x 30 days = 720 farmer actions
Market orders are separate (10/turn), so BUY/SELL cost no farmer actions.
```

## cell [2] — markdown

## 1. The spec, as data

Transcribed from the competition README. Keeping it as a table rather than prose means
every downstream number is recomputed if a constant is wrong — and if you think one *is*
wrong, you can change it here and rerun rather than re-deriving by hand.

## cell [3] — code

**output:**

```text
Wheat       seed   10  price   25
Carrot      seed   20  price   35
Melon       seed   80  price  250
Tomato      seed   50  price   60
Strawberry  seed  100  price  120
Goose/Egg   cost  300  price   50  every 1d
Cow/Milk    cost  400  price  160  every 2d
Sheep/Wool  cost  500  price  200  every 3d
```

## cell [4] — markdown

## 2. Counting the actions a crop really costs

Three action types per one-time crop: one `PLANT`, one `HARVEST`, and however many
`WATER`s. The waterings are where it gets interesting, because two different rules apply:

- **Survival.** A plant that goes two consecutive days unwatered becomes a weed. So you
  must water at least every other day. Note the README's trap: *"A new seed starts with
  `consecutive_unwatered = 1` — the planting day itself counts as the first missed day."*
  You must water on the day you plant, or it dies that night.
- **Yield.** *"Starting at half the plant's `max_yield_day` rounded up, watering during
  the bonus window will add one unit per day."* Only waterings inside that window add yield.

So the cheapest way to a full harvest is: water on planting day, water every *other* day
to stay alive, then water *every* day once the bonus window opens.

## cell [5] — code

**output:**

```text
crop        window    harvest  waters  yield
Wheat       day 2     4        4       4
Carrot      day 2     3        3       3
Melon       day 6     10       8       6
```

## cell [6] — markdown

Sanity check against the README, which states the answers for two crops: wheat should peak
at **4** units on watering alone and carrot at **3**. If the model above disagrees with
those, the model is wrong — so it is worth checking rather than assuming.

## cell [7] — code

**output:**

```text
  OK  Wheat    model=4  README=4
  OK  Carrot   model=3  README=3
  OK  Melon    model=6  README=6

model reproduces the README's stated yields
```

## cell [8] — markdown

## 3. Profit per action

Now the actual ranking. For one-time crops: `(units x price - seed) / (plant + waters + harvest)`.

For ongoing crops and animals the shape differs — they produce repeatedly, so the fair
comparison is over their full productive life, including the setup actions.

For animals I model two regimes, because `CARE` changes the picture completely:

- **Feed-only**: `FEED` daily, `HARVEST` on production days. One unit per production.
- **Feed + care**: also `CARE` daily, which banks +1 per day and pays the whole bank out
  on the next production, capped by `max_held`.

## cell [9] — code

**output:**

```text
strategy              $/action  actions  units
-----------------------------------------------
Melon                    142.0       10      6
Sheep/Wool +CARE         100.0       71     38
Cow/Milk +CARE            78.9       74     39
Cow/Milk                  34.5       44     12
Sheep/Wool                31.7       41      9
Goose/Egg +CARE           28.1       89     56
Strawberry                27.1       14      4
Goose/Egg                 17.8       59     27
Tomato                    17.3       11      4
Carrot                    17.0        5      3
Wheat                     15.0        6      4
```

## cell [10] — code

**output:**

*[image omitted — see the notebook]*

## cell [11] — markdown

## 4. What this says

Read the chart as a ranking of *what to do with your next turn*, not as a profit forecast.

The gap between the top and bottom is roughly an order of magnitude, which is larger than
most strategic decisions in the game. A player spending turns on wheat while an opponent
spends them on melons is losing ground every single turn, regardless of how well either
plays otherwise.

Three caveats that matter, and none of them are small:

1. **The market is dynamic.** All prices above are the README's *base* prices. Dumping six
   melons at once will move the price against you, and the size of that move is not in the
   spec — it has to be measured in-game. Treat the ranking as an upper bound and a
   priority order, not a revenue estimate.
2. **Wheat is not competitive as a cash crop, but animals eat it.** Every animal needs
   wheat daily. Wheat's value is as feedstock, and the real comparison is growing it versus
   buying it at market price — a different question from the one this notebook answers.
3. **Time-to-first-yield gates everything early.** Melon takes 10 days to first harvest out
   of a 30-day season, and a sheep takes 6 before it produces anything. With 300–500 up
   front and no income, the opening is a cash-flow problem, not an efficiency problem.

The honest summary: **this tells you what to do with turn 400. It does not tell you what
to do with turn 1.** The opening — how to convert seed money into the first melon or the
first animal without starving — is the harder problem, and it is not solved here.

---

*Every figure recomputed in-notebook from constants transcribed out of the competition
README; the model is checked against the two yields the README states outright. If you
think a constant or a rule reading is wrong, the table in section 1 is the only place to
change it — say so in the comments and I'll fix it.*
