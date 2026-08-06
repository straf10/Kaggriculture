# kaggriculture-daily-replays-the-live-meta-report

> Extracted by `analysis/nb_extract.py` from `notebooks/kaggriculture-daily-replays-the-live-meta-report.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# Kaggriculture Daily Replays: The Live Meta Report

*By [Georgy Mamarin](https://www.kaggle.com/georgymamarin)*

Every finished game on the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
ladder leaves a full public replay: 720 turns, both players, every observation and every action.
I collect them into the
[Kaggriculture Episodes](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes)
dataset, and this notebook is the live look inside: what the data holds today, and what the
leading farms measurably do differently.

## cell [1] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
pandas 2.3.3 · numpy 2.0.2 · executed 2026-07-31 09:42 UTC · full run ~1 min
```

## cell [2] — markdown

**A live report, not a snapshot.** It re-runs on a schedule with the dataset, so every number in
the text below is computed at run time. Come back tomorrow and the ladder you see will be the
ladder as it is tomorrow.

Two companions, two jobs: this one is about the data and the state of the ladder; my guide
[Kaggriculture, Visualized](https://www.kaggle.com/code/georgymamarin/kaggriculture-visualized-what-every-crop-pays)
is about the game itself, with every rule and price curve drawn out plus a starter bot. Read that
one first if the mechanics are new to you.

### In this notebook

1. [What is in the dataset today](#s1) — size, coverage, and how fast the corpus grows
2. [The ladder right now](#s2) — every recorded win on one chart
3. [The shape of a big game](#s3) — top coin curves against a median game
4. [Strategy fingerprints](#s4) — crew, land and crops: leaders vs the mid-ladder
5. [The market they create together](#s5) — prices inside the record game
6. [How fast the bar is moving](#s6) — the meta clock, in percent per day
7. [Who beats whom](#s7) — head-to-head win rates the ratings hide
8. [How much of this is luck](#s8) — same bot, different games
9. [Your submission against the ladder](#s9) — a personal report; edit one line

Plus [the honest caveats](#s10) behind every chart, and the [takeaways](#s11).

## cell [3] — markdown

<a id="s1"></a>
## 1. What is in the dataset today

Before the strategy talk, the shape of the data itself: how much of the ladder is captured, how
deep the replay coverage goes, and how fast the corpus grows. Column-level docs live on the
[dataset page](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes).

## cell [4] — code

**output:**

```text
metric | value
episodes | 1,285
with full replay | 1,285 (100%)
ladder games | 1,196
validation (self-play) | 89 (7%)
submissions seen | 255
teams seen | 95
ladder time covered | 12 hours
```

**output:**

*[image omitted — see the notebook]*

**output:**

Coverage is **100%** of episodes; the busiest submission has **44** games on record and the median has **6**. Validation runs (7% of rows) are a submission playing itself. Filter them out before comparing strength; the rest of this notebook does.

## cell [5] — markdown

<a id="s2"></a>
## 2. The ladder right now

Winners' final banks across the recorded ladder games, one dot per episode. The spread is the
story of this competition: the same board and the same rules produce farms that differ by an
order of magnitude.

## cell [6] — code

**output:**

*[image omitted — see the notebook]*

**output:**

The winner's bank across recorded games: **28,707** at p25, **39,652** median, **96,424** at p90. The record of **157,449** is **4.0×** the median win; section 6 tracks how fast that gap moves.

## cell [7] — markdown

<a id="s3"></a>
## 3. The shape of a big game

Coin curves of the biggest wins on record against a median game. Top games share a silhouette:
the bank stays near zero deep into the season while everything is reinvested, then compounding
takes over once the farm is built.

## cell [8] — code

**output:**

*[image omitted — see the notebook]*

**output:**

Each top farm crosses a tenth of its final bank on in-game day **11** (top-1), **15** (top-2), **11** (top-3). That crossing, not the last-day sprint, is where the game is decided.

## cell [9] — markdown

<a id="s4"></a>
## 4. Strategy fingerprints

Replays store actions, not just scores, so bots can be compared by behavior. Three cheap,
readable fingerprints per submission: how deep a crew it runs, when it first buys land, and what
it plants. Leaders against the middle of the ladder:

## cell [10] — code

## cell [11] — code

**output:**

```text
who | bank | hires / day | peak crew | first land (day) | tiles planted | top crop
Victor @ Tufa Labs | 157,449 | 10.8 | 13 | 0 | 105 | Strawberry
Max Manushin | 143,707 | 7.9 | 12 | 10 | 78 | Melon
Max Manushin | 135,131 | 7.9 | 12 | 10 | 73 | Melon
Maxim (mid-ladder) | 38,514 | 6.8 | 7 | — | 86 | Melon
```

**output:**

One best game per submission, so read it as a sketch rather than a verdict. Still, the record holder (Victor @ Tufa Labs) runs a crew of **13** against the mid-ladder's **7** and takes land on day **0**; the mid-ladder farm never buys any. The three biggest wins lead with Strawberry, Melon, Melon. The winning crop varies; what repeats is the economics around it, not the plant.

## cell [12] — markdown

<a id="s5"></a>
## 5. The market they create together

Prices are shared between the two players of an episode, and replays record them every turn.
Inside the biggest game with a replay you can watch supply and demand move under the bots' own
hands.

## cell [13] — code

**output:**

*[image omitted — see the notebook]*

**output:**

In this game melon starts at **250**, bottoms at **184** and peaks at **278**, a swing of 38% of its base price. Wheat runs **25–56** against a base of **25**. Wheat climbing that far above base usually means animal farms buying feed faster than the town supplies it. Both lines are a strategy log: you can see when a farm dumps and when it trickles.

## cell [14] — markdown

<a id="s6"></a>
## 6. How fast the bar is moving

The number every competitor wants: how much the ladder improves while you sleep. Median
winning bank per time slice, against the record so far. Skip a few days and this is the gap you
come back to.

## cell [15] — code

**output:**

*[image omitted — see the notebook]*

**output:**

The median winning bank went from **27,880** to **60,016** over **12 hours** of ladder: **+115%**, and the most recent day moved **+29%** against the day before. A bot that stands still slides down the table on its own.

## cell [16] — markdown

<a id="s7"></a>
## 7. Who beats whom

Ratings compress everything into one number, and that hides the interesting part: matchups don't
have to be transitive. Head-to-head win rates between the busiest teams; read a row as the row
team's share of wins against the column team.

## cell [17] — code

**output:**

*[image omitted — see the notebook]*

**output:**

Cells are blank where the pair has not met yet; early ladders are sparse. Clean sweeps so far: **Waffle** over **Alexander Gremyakov** (2 games); **Waffle** over **Veniamin Nelin** (5 games); **Beisenbek Nurassyl [dsmlkz]** over **Alexander Gremyakov** (3 games).

## cell [18] — markdown

<a id="s8"></a>
## 8. How much of this is luck

Same bot, different games: how wide is its spread? This decides how many submissions you need
before believing a result, and whether that one great game was skill or a lucky matchup.

## cell [19] — code

**output:**

*[image omitted — see the notebook]*

**output:**

Across submissions with at least four games, the typical spread is **19%** of the median bank (worst: **950%**). One episode proves little, which is why the ladder keeps playing more of them.

## cell [20] — markdown

<a id="s9"></a>
## 9. Your submission against the ladder

The part worth forking. Put your own submission id in the cell below and you get a personal
report: where your best game lands in the whole field, and how your strategy fingerprint
compares with the record holder's. Find your id in `episodes.csv`, or leave the default to see
the record holder's own report.

## cell [21] — code

## cell [22] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
best bank | games | hires / day | peak crew | first land (day) | top crop
Victor @ Tufa Labs | 157,449 | 34 | 10.8 | 13 | 0 | Strawberry
Victor @ Tufa Labs (record holder) | 157,449 | 34 | 10.8 | 13 | 0 | Strawberry
```

**output:**

**Victor @ Tufa Labs** has **34** ladder games on record; its best bank of **157,449** beats **100%** of all recorded wins. The row below it is the record holder; the gap in crew size and land timing is usually where the difference starts.

## cell [23] — markdown

<a id="s10"></a>
## Before you quote these numbers

The honest edges of this snapshot, so the charts above don't overclaim:

- Fingerprints read one best game per submission: a sketch of a strategy at its peak, not its
  average behavior.
- The corpus is a crawl, not a census. Episodes are discovered through pairings, so a brand-new
  submission can lag behind the ladder by a few hours; section 1 prints the exact replay
  coverage.
- Head-to-head cells stand on a handful of games. The count is printed inside every cell; a 100%
  built on two games is an anecdote, not a verdict.
- Spread estimates use submissions with four or more games each, a modest per-bot sample even
  on a mature ladder; treat them as order-of-magnitude.
- Validation (self-play) episodes are excluded from every strength comparison; section 1 shows
  their share of the raw data.

## cell [24] — code

**output:**


<a id="s11"></a>
## Takeaways (Jul 31, 2026 snapshot)

1. The ladder's spread is wide: the record win of **157,449** is
   **4.0×** the median win of **39,652**.
2. Big games share one silhouette: reinvest almost everything, then compound. The leaders cross
   a tenth of their final bank around in-game day **11–15**.
3. The record holder's measurable edge is labor and land: a crew of
   **13** and land on day **0**, while the biggest wins disagree on which crop to lead with.
4. Market prices inside a game are their own strategy log: in the biggest replayed game melon swung
   **38%** of its base price
   and wheat ran **25–56**.

The [dataset](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes) and this
notebook both refresh daily, so these numbers re-compute themselves as the meta moves. Build
something on top (a deeper dive, an imitation model, a better fingerprint) and post it; I
feature community work on the dataset page. If there is a metric you want tracked here, say so
in the comments. Replays come from Kaggle's public episode service; credit to the hosts for
keeping it open. For the rules behind these curves, see
[Kaggriculture, Visualized](https://www.kaggle.com/code/georgymamarin/kaggriculture-visualized-what-every-crop-pays).

*— [Georgy Mamarin](https://www.kaggle.com/georgymamarin)*
