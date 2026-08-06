# what-actually-wins-on-the-kaggriculture-ladder

> Extracted by `analysis/nb_extract.py` from `notebooks/what-actually-wins-on-the-kaggriculture-ladder.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# What actually wins on the Kaggriculture ladder, read from the replays

Most reads on this competition explain the crop economics or hand you a baseline agent. This one recomputes
the meta in front of you from the raw episode replays, so every number below comes from parsing the actual
720 turn games, not from the game manual. Each episode is one ranked match between two submitted agents. From
its replay I read what each side actually did, tag each side by its agent name, and read the winner from the
final profit. Aggregate a day of ladder games and you get the real question answered: not which crop pays
most on paper, but what the farms that actually win do differently from the farms that lose.

Fork it, point it at another day, and it recomputes. Every archetype, win rate, and strategy number is
parsed live from the logs, with no pasted figures and no leaderboard claim.

## cell [1] — code

**output:**

```text
replay dir: /kaggle/input/datasets/organizations/kaggle/kaggriculture-episodes-2026-08-01 | day: 2026-08-01 | games to parse: 300
```

## cell [2] — code

**output:**

```text
  50/300 replays, 50 decisive, 26s
  100/300 replays, 98 decisive, 51s
  150/300 replays, 147 decisive, 77s
  200/300 replays, 195 decisive, 102s
  250/300 replays, 242 decisive, 127s
  300/300 replays, 290 decisive, 152s
parsed 290 decisive games (580 sides) in 152s
distinct agents seen: 75
```

## cell [3] — markdown

## 1. The agent tier list

Every game has two sides, each an agent. Here is each agent's win rate across all its games, with a Wilson
interval so you can see which leads are real and which are small sample noise. This is the ladder as the
replays actually played out, not the public leaderboard rating.

## cell [4] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
              agent  games  winrate    lo    hi  avg_score
Mominul Islam Hemal     10    0.800 0.490 0.943 130327.600
            Tony Li      8    0.750 0.409 0.929 115535.750
        this is lsm      8    0.750 0.409 0.929 105802.875
 radiant-allomancer     34    0.735 0.569 0.854 120480.235
     Yaroslav Tanko     10    0.700 0.397 0.892 122408.700
           Subin An     10    0.700 0.397 0.892 118893.100
                Ali     19    0.684 0.460 0.846 126160.684
              midnq     15    0.667 0.417 0.848 120536.000
   Md. Mehedi Hasan     16    0.625 0.386 0.815 102871.750
              Sheep      8    0.625 0.306 0.863 115961.750
         Jeff Horon     23    0.609 0.408 0.778 115826.000
       Pilkwang Kim     15    0.600 0.357 0.802 115376.333
             yw8837     10    0.600 0.313 0.832 109554.100
    Pawan Rama Mali     10    0.600 0.313 0.832 113998.200
        Omkar Kadam     10    0.600 0.313 0.832 108144.000
  Hozuma ITOBAYASHI      9    0.556 0.267 0.811 112560.333
           takai380     11    0.545 0.280 0.787 118484.091
         RuiKimura4     27    0.519 0.340 0.693 110793.444
 Lucien de Rubempre     16    0.500 0.280 0.720 119683.812
Grzegorz Sionkowski      8    0.500 0.215 0.785 112752.375
   Juste Me (●'◡'●)      9    0.444 0.189 0.733 110661.000
          Samrish B      9    0.444 0.189 0.733 120081.000
              venks     21    0.429 0.245 0.635 112871.286
       yjhv buddies     14    0.429 0.214 0.674 105449.286
 Victor @ Tufa Labs      8    0.375 0.137 0.694 101710.250
     Krizsó Gergely     17    0.353 0.173 0.587 115761.000
         Seb Mallia     20    0.350 0.181 0.567 108310.050
           chocolat     12    0.333 0.138 0.609 112164.000
              Rylan     10    0.300 0.108 0.603 105888.900
           Raiden.B     10    0.300 0.108 0.603 112482.300
            neurlog      8    0.250 0.071 0.591 105037.625
   Rayk Kretzschmar      8    0.250 0.071 0.591 113250.125
      nishchal jain      8    0.250 0.071 0.591 108044.000
              smlcr      8    0.125 0.022 0.471 112938.875
```

## cell [5] — markdown

## 2. What the winning farms actually do

This is the cell worth reading. For every side we counted the real moves: how much it planted, sold on the
market, hired farm hands, bought animals and land, and collected fertilizer over the season. Here are those
counts averaged for the winning side versus the losing side of the same games. The gaps are what winners
tend to do more or less of, separate from what the manual says pays. Read them as description, not proof
that any one action causes the win; both sides play the same 720 turns, so the counts are comparable.

## cell [6] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
            winning  losing  ratio
plant          74.2    81.0    0.9
sell          331.1   322.3    1.0
hire          290.9   294.7    1.0
harvest       258.1   256.1    1.0
fert          287.2   280.8    1.0
buy_animal      7.6     8.0    1.0
buy_land        2.5     2.8    0.9

mean final profit: winners 118420 | losers 110265
```

## cell [7] — markdown

## 3. Which crop the winners lean on

Each side has a most planted crop. This is how often each crop is the primary crop of a winning side versus
a losing side, which tells you what the field currently rewards without you having to submit an agent to find
out.

## cell [8] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
win rate when a crop is the primary crop:
  STRAWBERRY   53%  (n=515)
  WHEAT        30%  (n=53)
  MELON        43%  (n=7)
  CARROT       0%  (n=5)
```

## cell [9] — markdown

## 4. The meta is heating up

The organisers publish a daily index with the top and median agent score for each day. Scores have been
climbing fast as agents improve, so a strategy that won yesterday is not a safe read for tomorrow. That is
the whole reason this is a live tracker and not a one time analysis: the target keeps moving.

## cell [10] — code

**output:**

*[image omitted — see the notebook]*

**output:**

```text
      date  episode_count  top_avg_score  median_avg_score
2026-07-30            864         1152.4             669.8
2026-07-31            928         1427.0            1175.3
2026-08-01            829         1580.6            1348.2
```

## cell [11] — markdown

## Honest scope, and how to use it

This is one day of ladder replays, so read it as a snapshot, not a law; fork it onto another day to see what
moves. Each replay is about 25MB, so I read a seeded random sample of at most 300 games of the day, not the
full dump; the parse cell prints exactly how many went in. The winner is the side with the higher final
profit, straight from the replay rewards. Ties and unfinished games are dropped. The strategy counts are the
raw action tallies over the 720 turn season, a faithful count of what each side did, not a judgement of why.
Everything is recomputed from the logs when you run the notebook, with no pasted numbers and no leaderboard
claim, so you can trust it as far as the parse, which is all shown above.

If you want the same live-from-raw-logs read for a different competition, the companion tracker
[What actually wins on the ladder](https://www.kaggle.com/code/busyaprime/what-actually-wins-on-the-ladder)
does this for the Pokemon TCG battle meta, and
[Which open Kaggle competition still has room](https://www.kaggle.com/code/busyaprime/which-open-kaggle-competition-still-has-room)
tracks every open competition worth entering.
