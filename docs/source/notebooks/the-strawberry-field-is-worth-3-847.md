# the-strawberry-field-is-worth-3-847

> Extracted by `analysis/nb_extract.py` from `notebooks/the-strawberry-field-is-worth-3-847.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# The strawberry field is worth $3,847. The manure is worth $25,000.

Kaggriculture publishes its entire economy in `README.md`: seed costs, yield rates, and —
crucially — the exact price function the market uses. That means the profitable strategies
are *computable* before you write a single line of agent code. This notebook computes them.

Three results, all falling straight out of the published numbers:

- **Base prices are nearly meaningless.** A full 5×5 field of strawberries produces about
  100 units. Selling 100 strawberries earns **$3,847**, not the $12,000 the $120 base price
  suggests, because the 62nd one already sells for a dollar.
- **Melon is still the best crop**, but by a much smaller margin than the table implies:
  $26,627 for a field, not $75,000.
- **Fertilizer — a free byproduct of owning animals, produced whether or not you feed
  them — has the second-highest revenue ceiling in the game.** For most animals it is worth
  more than the animal's actual product.

Everything below is derived from the published rules. I have not run it against the live
environment, so treat it as a hypothesis with the arithmetic already done — and please
correct me in the comments if the engine disagrees.

## cell [1] — code

**output:**

```text
            P(I0+T)  P(I0+2T)  README P(I0+T)  README P(I0+2T)
Wheat            20        19              20               19
Carrot           10         1              10                1
Tomato           24         9              24                9
Strawberry        1         1               1                1
Melon             1         1               1                1
Egg              40        39              40               39
Milk              1         1               1                1
Wool              1         1               1                1
Fertilizer       60        20              60               20

reproduces the README table exactly: True
```

## cell [2] — markdown

The implementation matches every published price point, so the curve below is the
real one, not a guess.

## cell [3] — markdown

## 1. What your own selling does to the price

Sell orders are processed one unit at a time and each unit you add to market inventory
pushes the price down for the next. The shape of that decay is chosen per resource, and
the README's own words are that premium goods "drive straight to the $1 floor".

## cell [4] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
units you can sell before the price is $1:
  Wheat       never
  Carrot      842
  Tomato      529
  Strawberry  62
  Melon       158
  Egg         never
  Milk        76
  Wool        59
  Fertilizer  493
```

## cell [5] — markdown

Strawberry hits the floor after **62 units**. Wool after 59, milk after 76, melon
after 158. Wheat and egg never do — their glut curves are logarithmic, so they settle
around $19 and $39 and stay there no matter how much you dump.

This is the single most important table in the game and it is not the one in the README.

## cell [6] — markdown

## 2. What a field is actually worth

`T` in the price table is defined as the output of one 5×5 field over 24 days at optimal
watering. So `revenue(T)` answers directly: **if I dedicate a quadrant to this crop for the
season and sell everything, what do I get?**

## cell [7] — code

**output:**

```text
   product  base  field output T  naive T×base  actual revenue glut tax  $/unit
     Melon   250             300         75000           26627      64%    88.8
Fertilizer   100             200         20000           16020      20%    80.1
       Egg    50             332         16600           13839      17%    41.7
    Carrot    35             450         15750            8418      47%    18.7
     Wheat    25             400         10000            8313      17%    20.8
      Wool   200             105         21000            7974      62%    75.9
    Tomato    60             200         12000            7221      40%    36.1
      Milk   160             122         19520            6227      68%    51.0
Strawberry   120             100         12000            3847      68%    38.5
```

**output:**

*[image omitted — see the notebook]*

## cell [8] — markdown

Sorted by what you actually bank rather than by base price, the ranking changes
completely:

Melon ($26,627), fertilizer ($16,020) and egg ($13,839) take the top three. Wool, milk and
strawberry — the three most expensive-looking goods on the price list — finish 6th, 8th
and 9th.

Strawberry has the second-highest base price in the game and the **lowest** field revenue
of any product. Its glut curve is linear with a target of 1.6, which means 100 units —
exactly one field's output — moves the price by 1.6× the base, i.e. straight through zero
to the floor. The card is designed to punish anyone who reads only the yield table.

Melon survives its 64% glut tax and still wins, because $250 is a long way to fall.

## cell [9] — markdown

## 3. The manure economy

Now the part that is easy to miss. From the action list:

> **COLLECT_FERTILIZER** — *Every surviving animal makes 1 available at the end of each
> day, **whether or not it was fed or cared for**.*

Fertilizer is not a product you farm. It is a per-animal-per-day dividend that costs one
action to collect and nothing to produce. And its glut curve is the gentlest of any
premium-priced good: linear, target 0.40, so 400 units still average $60.

## cell [10] — code

**output:**

```text
 100 fertilizer -> $   9,010   avg $ 90.1/unit
 200 fertilizer -> $  16,020   avg $ 80.1/unit
 300 fertilizer -> $  21,030   avg $ 70.1/unit
 400 fertilizer -> $  24,040   avg $ 60.1/unit
 500 fertilizer -> $  25,052   avg $ 50.1/unit

for comparison, the animals' own products:
  Egg     50 -> $   2,244   avg $ 44.9
  Egg    100 -> $   4,371   avg $ 43.7
  Egg    200 -> $   8,510   avg $ 42.5
  Milk    50 -> $   5,430   avg $108.6
  Milk   100 -> $   6,205   avg $ 62.0
  Milk   200 -> $   6,305   avg $ 31.5
  Wool    50 -> $   7,655   avg $153.1
  Wool   100 -> $   7,969   avg $ 79.7
  Wool   200 -> $   8,069   avg $ 40.3
```

## cell [11] — code

**output:**

```text
animal  buy cost product  units in 20d  product $  fertilizer units  fertilizer $ manure share
 Goose       300     Egg            20        874                20          1402          62%
   Cow       400    Milk            10        620                20          1402          69%
 Sheep       500    Wool             6        478                20          1402          75%
```

## cell [12] — markdown

Per animal, over twenty days, valued at realistic season volumes, **the manure is
worth more than the animal's actual product in all three cases** — 62% of a goose's
income, 69% of a cow's, 75% of a sheep's.

And it is the *robust* half of that income: it needs no wheat, no feeding schedule, and it
keeps coming while the animal is neglected. A sheep is not a wool machine that also
fertilises. It is a fertiliser machine that occasionally produces wool.

Two consequences worth testing in an agent:

1. **Feeding is only required every other day** — "they will escape if not fed for *two
   successive* days" — and an unfed animal still produces its base yield, losing only the
   banked CARE bonus. Feeding daily doubles the action cost of an animal for a bonus that
   is capped by `max_held` anyway.
2. Fertilizer is also *usable*: it doubles a crop's per-day yield bonus for three days. So
   every unit is a choice between roughly $70 of sale value and a yield multiplier on a
   melon. Given melon is the only crop that survives its own glut, that trade is probably
   worth making — for melons, and almost nothing else.

## cell [13] — markdown

## 4. The budget nobody mentions: 720 actions

There are 24 turns per day and 30 days: **720 farmer actions for the whole season**, plus
whatever you buy with `HIRE` at a Fibonacci price. Every water, every harvest, every
collection, every step across the board spends one.

That reframes the question from "what is profitable per tile" to "what is profitable per
action", and it is why the melon's ten-day watering schedule is expensive and why a
one-action-per-day fertilizer dividend is cheap.

## cell [14] — code

**output:**

```text
season budget: 720 farmer actions
hiring n hands for a day costs fib(1..n) = [1, 1, 2, 3, 5, 8, 13, 21] → 8 hands for one day costs $54 and buys 192 extra actions

so an extra action is worth roughly $0.28 at the margin — anything earning more than that per action is worth doing
```

## cell [15] — markdown

Hired hands are absurdly cheap relative to what an action earns. Eight hands for a
day cost $54 and hand you 192 extra actions; a single melon harvest is worth more than
that. **If your agent is not hiring aggressively every day, that is probably the largest
single number on the table** — larger than any crop choice in section 2.

(Caveat worth checking in the engine: hands spawn adjacent to the shed, and the first hire
each day spawns onto a tile that is locked until you buy the NE quadrant. Locked tiles are
passable, so it costs a move, not the hand.)

## cell [16] — markdown

## What to do with this

1. **Ignore base prices.** Rank by `revenue(T)`, not by the price column.
2. **Melon for the money, wheat and egg for the floor.** Wheat and egg are the only two
   goods with no crash — they are where a large surplus goes without being destroyed.
3. **Never plant a full field of strawberries.** Its ceiling is $3,847 and it hits the
   floor at 62 units.
4. **Collect fertilizer from every animal, every day.** It is free, it is the
   second-largest revenue pool in the game, and for sheep it dwarfs the wool.
5. **Feed every other day, not every day.** Half the actions, same base yield.
6. **Hire hands.** An action costs about $0.28 and earns far more.

All of the above is arithmetic on the published rules, not results from the simulator. If
you run it and something disagrees, say so in the comments — I would rather the numbers
be right than be mine.
