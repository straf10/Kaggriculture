# 106-130-multi-generation-v36-robust-hybrid

> Extracted by `analysis/nb_extract.py` from `106-130-multi-generation-v36-robust-hybrid.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# 106/130 Multi-Generation | v36 Robust Hybrid

**The newest route was not the safest route. This update measures generation
overfit, rejects a tempting learned branch, and restores a stronger floor.**

v35 started losing to two very different families: a near-v18 actor with a new
market overlay, and a high-expansion animal route unrelated to my public
lineage. Optimizing only against the latest Top-10 snapshot had removed useful
coverage of strategies still present on the leaderboard.

v36 uses a simple principle:

```text
one coherent 719-action production backbone
                    +
feedback only where observation has measured value
```

The title is an aggregate of **130 local frozen-opponent games in both seats**,
not a Public-LB score and not one pure holdout. The panels and their roles are
separated below so the number cannot hide model selection.

## cell [1] — markdown

## 1. Why v35 slipped

The current v35 submission began 16/19 live, but its three losses exposed two
different omissions.

- **izh yng:** the actor path matched the public v18 lineage on 717/719 turns,
  while 195 market turns differed. Of 106 reorder-only mismatches, 55 changed
  public v18's `SELL -> BUY` order to `BUY -> SELL`. A newer market controller
  had been attached to an older public backbone.
- **Arda Ceylan:** no historical public agent matched even 2% of full turns.
  The opponent reached four quadrants and a sheep-heavy late economy; v35's two
  Ryo continuations both lost badly.
- **Mister Qi:** another small early loss where both v34 continuations won in
  the frozen counterfactual.

The defect was not one SELL threshold. v35 had two routes from the same recent
basin, so its apparent portfolio had low effective diversity. Public agents do
not disappear when a new Top-10 family arrives; old public generations return
with small market overlays.

## cell [2] — markdown

## 2. A generation panel instead of one snapshot

I replayed 13 historical candidates on three disjoint surfaces:

| Surface | Opponent trajectories | Both-seat games | Role |
|---|---:|---:|---|
| Top-10 diagnostic | 18 | 36 | recent public families |
| later strict capture | 2 | 4 | small post-freeze check |
| v35 live opponents | 19 | 38 | actual deployment neighborhood |

The selection key starts with the worst panel, then worst seat, overall wins,
tail log-ratio and margin. This prevents a large easy panel from hiding a
generation-specific collapse.

| Historical candidate | Wins / 78 | Mean margin |
|---|---:|---:|
| v34 Kawashigi-basin fixed hybrid | **67/78** | **+24,057** |
| v35 Ryo router | 66/78 | +17,259 |
| v27 public | 60/78 | +17,148 |
| v23 public | 40/78 | +2,626 |
| v18 public | 31/78 | +4,412 |
| v20 public | 29/78 | +2,889 |

The result is not “v34 is globally optimal.” It says v35 paid a robustness
cost for one recent basin, while a prior coherent route retained wider current
coverage.

## cell [3] — code

**output:**

```text
v35-router             66/78   +17,259
v34-kawashigi          67/78   +24,057
v27-public             60/78   +17,148
v23-public             40/78    +2,626
v18-public             31/78    +4,412
v20-public             29/78    +2,889
```

## cell [4] — markdown

## 3. The branch that looked good — and was rejected

The two v34 routes share their first 116 actions, so a legal continuation gate
is possible. I trained a public-state kNN at steps 72, 96 and 112. Each OOF
prediction excluded **every row from the target opponent submission**.

The best step-72 market/demand model looked excellent:

| Grouped OOF | Wins |
|---|---:|
| fixed robust backbone | 67/78 |
| fixed alternative | 67/78 |
| learned continuation router | **70/78** |

But after freezing it and downloading another 19 Top-10 trajectories:

| Post-freeze comparison | Wins / 38 | Mean margin |
|---|---:|---:|
| **fixed robust backbone** | **33/38** | **+13,376** |
| learned router | 31/38 | +12,471 |
| fixed alternative | 29/38 | +9,819 |
| current v35 | 25/38 | +5,070 |

The gate confused identical or nearby step-72 states whose opponents diverged
later. This is **state aliasing**: more classifier confidence cannot recover
future information that is not yet observable. The learned route branch is
therefore absent from the submitted artifact.

## cell [5] — markdown

## 4. Final architecture: open backbone, sparse feedback

The final agent locks one complete route, hash
`8ff594fc0c180392...`, and keeps only closed-loop components with an explicit
safety boundary:

1. **transaction recovery:** repair bounded weed/legality slips and clip to
   legal inventory;
2. **SELL ordering:** reorder existing legal SELL slots from current price,
   projected shed and public opponent exposure;
3. **near-clone preemption:** require 24 near-identical public states before a
   one-turn SELL preemption, with inventory debt reconciliation;
4. **independent WHEAT market maker:** at most q10, using only capital left
   after a 500 cash floor, two feed days, two investment turns and shed
   headroom.

```text
production / movement / investment horizon -> coherent open-loop route
legality / order / clone / residual capital -> bounded closed-loop feedback
```

No identity, team name, opponent private inventory, future action, replay ID or
seed is used at runtime.

## cell [6] — markdown

## 5. What the final blind panel said

After selecting and packaging the fixed backbone, I downloaded each Top-10
submission's still-unseen third trajectory. Six unique episodes yielded seven
opponent trajectories and 14 both-seat games. I did not change the agent after
opening this result.

| Final blind | Wins / 14 | Mean margin | Worst margin |
|---|---:|---:|---:|
| v36 fixed hybrid | 6/14 | -1,388 | -19,115 |
| current v35 | 6/14 | **+1,721** | -23,721 |

This is deliberately reported even though it is not flattering. v36 does not
solve every older trajectory: it ties v35 on wins and loses mean margin on this
small blind panel. Its measured advantage comes from the current deployment
surface and the newer Top-10 capture, not universal dominance.

Across the three disjoint blocks used in this update:

| Block | v36 wins / games |
|---|---:|
| multi-generation observed panel | 67/78 |
| post-freeze comparison used for final selection | 33/38 |
| final blind after selection | 6/14 |
| **aggregate** | **106/130** |

The aggregate is descriptive, not a single unbiased confidence interval.

## cell [7] — markdown

## 6. Artifact contract

The last cell reconstructs the exact linked submission output offline.

- `main.py`: **46,395 bytes**
- SHA-256: `47ebf29039463dc0eb803ccf38d5a6f0c130d2b49f3698b20c53f495c1062dc8`
- post-freeze replay: **33/38**, 0 runtime failures
- final blind replay: **6/14**, 0 runtime failures
- source/standalone parity: **2,876 calls, 0 mismatches** on each panel
- focused regression tests: **22 passed**
- latency: **0.129 ms mean, 0.340 ms p99**
- deterministic archive SHA-256: `555ae260822e9dce16be073230bcd0e21ec8f6a24f6257287cbf32c36fd21163`
- archive members: one top-level `main.py`
- runtime dependencies: Python standard library only

The same archive hash was reproduced under two output filenames, preventing a
gzip-header filename leak from masquerading as a deterministic artifact.

## cell [8] — markdown

## 7. Public lineage and related work

This is a public iteration over community strategies, not a claim that the
backbone appeared in isolation.

- [Kaito v18 — original version of this Notebook](https://www.kaggle.com/code/kaitofukami/40-53-top-10-future-holdout-v18-closed-loop?scriptVersionId=340030138)
- [Kaito v20 — WEED-Slip Recovery](https://www.kaggle.com/code/kaitofukami/159-160-vs-frontier-v20-weed-slip-recovery)
- [Kaito v23 — Sparse Closed Loop](https://www.kaggle.com/code/kaitofukami/23-23-strict-future-v23-sparse-closed-loop)
- [Ray Kretzschmar — Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta)
- [beicicc — C20 Exact Replication Control](https://www.kaggle.com/code/beicicc/kaggriculture-c20-exact-replication-control)
- [prvsiyan — Frontier: The Moon Counts Melons](https://www.kaggle.com/code/prvsiyan/kaggriculture-frontier-the-moon-counts-melons)

The final backbone descends from the publicly observed Kawashigi-basin work in
the v32-v34 chain. The contribution in v36 is the multi-generation audit, the
grouped-OOF continuation experiment, its post-freeze rejection, and the
artifact-level rollback to the smaller measured hybrid.

## cell [9] — code

**output:**

```text
{
  "agent": "v36 Multi-Generation Minimax Fixed Hybrid",
  "sha256": "47ebf29039463dc0eb803ccf38d5a6f0c130d2b49f3698b20c53f495c1062dc8",
  "bytes": 46395,
  "multi_generation": "106/130 (descriptive aggregate)",
  "postfreeze_selection_panel": "33/38",
  "final_blind": "6/14",
  "route_switching": false
}
created main.py for the linked competition submission
```
