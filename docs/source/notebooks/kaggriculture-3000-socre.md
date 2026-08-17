# kaggriculture-3000-socre

> Extracted by `analysis/nb_extract.py` from `kaggriculture-3000-socre.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# HarvestForge-X | High-Throughput Farming and Premium-Market Strategy

HarvestForge-X is a production-focused strategy built around rapid livestock expansion, efficient field utilisation, and early access to high-value market opportunities. Its core configuration targets **8 cattle and 4 sheep**, while prioritising premium returns from **melon, strawberry, and wool**.

The strategy was reconstructed by comparing three publicly accessible reference runs: **92165990, 92185587, and 92223213**. Despite being separate traces, they followed an almost identical production sequence, while their market decisions agreed at approximately **99.91% of decision points**.

This consistency made it possible to derive a reliable baseline strategy. At each decision point, the most frequently observed action across the reference traces was selected and incorporated into the executable policy.

## Experimental Performance

The reconstructed policy was evaluated through local paired simulations using **30 independent seeds** and both possible player orders.

Results:

- **60/60 wins**
- **30/30 positive paired comparisons**
- Successful completion of additional two-player regression tests against established public reference agents

> These figures represent **local simulation results only** and should not be interpreted as official competition scores.

## Strategy Design

The main objective is to accelerate the transition from the initial farm state into a high-output production system.

The strategy:

- Expands into **three additional farm areas**.
- Establishes **4 sheep** early before scaling to **8 cattle**.
- Maintains continuous crop production through a rotation centred on **wheat, strawberry, and melon**.
- Coordinates **hiring, feeding, animal care, harvesting, and fertilisation**.
- Converts accumulated production into repeated **premium-market sales**.

This creates a continuous production cycle where farm expansion, resource generation, livestock growth, and market activity support one another.

## Adaptive Execution

The executable implementation is not restricted to replaying a fixed sequence.

Before performing each action, the controller checks the current number of available workers and adjusts the action queue when necessary. This allows the strategy to remain functional even when the live state differs slightly from the reference runs.

A recovery mechanism is also included for field obstructions. If an obstacle prevents a scheduled **planting** or **pasture construction** action, the controller resolves the obstruction before returning to the intended production sequence.

## Production Pipeline

The overall strategy can be summarised as:

**Expansion → Workforce Management → Crop Production → Livestock Growth → Premium Sales**

The early game focuses on unlocking productive capacity and establishing the required workforce. The middle stage increases crop and livestock throughput, while the later stage repeatedly converts accumulated resources into higher-value market opportunities.

The goal is therefore not to reproduce a replay frame by frame, but to capture the **underlying high-performing decision pattern** and execute it robustly under changing game states.

## cell [1] — code

**output:**

```text
Validated: all displayed results are complete two-seat, 720-turn simulations.
```

## cell [2] — code

**output:**

*[image omitted — see the notebook]*

## cell [3] — markdown

## 2. Add a conservative premium market lead

The shared market rewards queue position: once a `SELL` adds inventory,
later units may receive a lower price. V16-RC5 checks the next scheduled
sale for four premium products. When the current turn has no matching town
demand and the player's own `shed` holds enough stock, it moves part of the
next-turn sale forward by one turn.

The moved quantity is recorded and removed from the original next-turn
order. The two-turn intended quantity stays constant; only its execution
time changes. Purchases, `HIRE` order, and the production schedule remain
unchanged.

## cell [4] — code

**output:**

*[image omitted — see the notebook]*

## cell [5] — markdown

## 3. Dynamic two-seat evaluation

Every matchup below runs both agents from live observations in both seat
orders. A paired result sums the two seat margins for the same seed. The
30-pair route-core panel combines a development screen, a separate holdout,
and a fixed 20-seed random stress panel. The established reference panels
use 12 seed pairs, except V16-RC4-P5D, which uses the same 30-pair set.

All reported games reached 720 frames with both players in `DONE` status.

## cell [6] — code

**output:**

```text
games | W-T-L | Paired +/0/- | Mean margin | Worst margin
reference
Reconstructed 8C/4S core | 60 | 60-0-0 | 30/0/0 | +1,911.9 | +68
V16-RC4-P5D | 60 | 57-0-3 | 29/0/1 | +5,460.6 | -529
V16-RC3 | 24 | 23-0-1 | 12/0/0 | +6,105.2 | -28
Kaito V27 public artifact | 24 | 24-0-0 | 12/0/0 | +18,992.8 | +8,724
Rayk C71 public artifact | 24 | 24-0-0 | 12/0/0 | +18,576.8 | +9,089
llcc public artifact | 24 | 24-0-0 | 12/0/0 | +18,341.0 | +7,104
```

## cell [7] — code

**output:**

*[image omitted — see the notebook]*

## cell [8] — code

**output:**

*[image omitted — see the notebook]*

## cell [9] — markdown

## 4. References and implementation

Public replay analysis supplied the 8C/4S production schedule used here:

- Nikita Lugovoy, submission `55440039`, episodes `92165990`,
  `92185587`, and `92223213`.

Public executable artifacts used as local evaluation references include:

- [Kaito Fukami — 25→27 Strict Future V27 Midgame Meta Reset](https://www.kaggle.com/code/kaitofukami/25-27-strict-future-v27-midgame-meta-reset)
- [Rayk Kretzschmar — Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta)

V16-RC5 contributes the cross-replay reconstruction, state-drift recovery,
and the inventory-bounded premium market lead described above. The next
cell writes the exact competition agent.

## cell [10] — code

**output:**

```text
Writing main.py
```

## cell [11] — code

**output:**

```text
root member | main.py bytes | SHA-256 | smoke frames | status | validated actions | active field orders | market orders
artifact
submission.tar.gz | main.py | 18946 | f029fa0cb66a9eb509afbe44e3f59b800332d0419db916... | 720 | DONE/DONE | 1438 | 1772 | 1220
```

## cell [12] — markdown

## Takeaway

A stable high-throughput route does not need a wholesale production
rewrite to separate close matchups. V16-RC5 keeps the reconstructed 8C/4S
farm plan, adds narrow recovery for route drift, and moves only available
premium inventory into the preceding no-demand turn. The result is a
repeatable paired edge against the source-like core while retaining strong
performance across established public reference strategies.
