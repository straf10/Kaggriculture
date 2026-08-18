# Pass brief — S6 step 2c: is the vote erasing town-conditioning in the *other* 58 steps?

> **Read first:** `baselines/2026-08-18/s6_step2b_phase05_report.md` (the pass this one continues, and
> whose refutation stands); [ROADMAP.md](ROADMAP.md) §4.3 **S6 step 2b's Phase 0.5 block**; §1 (the
> transfer-ratio row, the converged curve); **§4.1b** (the town is 99-100% of realised-price variance —
> the reason WOOL/MILK are the target); **S6 step 0 leg 3** (town readability: drain rank stable median
> day 15, 8 shops only by day 24); §3.3's **T2 STOP** and the **step 2b row**; §3.4; **R21 / R27 / R32 /
> R36**; §2.1.1-5; the top of [memory.md](memory.md).

## Where we are

**Phase 0.5 refuted the strawberry mechanism on paper and it stays refuted.** ReCurSiON's strawberry
sell-rule is a fixed hour-0 calendar (`townCenterSellInterval=24`), invariant across 50 towns, already
reproduced by the majority vote. Arms A/B/C are dead; nothing in this brief revives them.

**But the refutation is product-scoped and its conclusion was drawn channel-wide.** STRAWBERRY appears in
**23 of the 127** state-dependent market steps — and is the *only* product traded in just **5** of them.
Most disagreement steps carry several products at once, so the per-channel counts below overlap and do not
sum to 127. **58 steps carry a WOOL or MILK sell, and none of them was tested:**

| channel | disagreeing steps | town-conditionable? |
|---|---:|---|
| SELL FERTILIZER | 53 | **No — analytically eliminated** (below) |
| SELL MILK | 45 | **Yes — 3 shops (PIZZA_SHOP, ICE_CREAM_SHOP, SMOOTHIE_SHOP), 14× drain range §4.1b** |
| SELL WHEAT | 40 | Weakly — 5 of 8 shops, near-always drained |
| SELL WOOL | 26 | **Yes, and it is the sharpest case — single shop (YARN_STORE), 34% of towns draw zero** |
| BUY_PRODUCT WHEAT | 23 | Feed logistics, not market conditioning |
| SELL STRAWBERRY | 23 | ⛔ tested and refuted (Phase 0.5) |
| SELL MELON 9 · BUY_SEED WHEAT 22 / STRAWBERRY 4 / MELON 1 · BUY_ANIMAL 2+2 | tail | tail |

**FERTILIZER — 53 steps, the largest channel — is eliminated from the desk, no measurement needed.** It
is in **no** `SHOPS` entry and is excluded from `TOWN_CENTER_PRODUCTS`
([kaggriculture.py:103-114](engine_reference/kaggriculture.py#L103)), so its realised price moves only
with the shared depletion pool, never with the town's shop draw. There is no town-conditioning channel
for it to have erased. Record this as the C-A pattern again: **the engine answered before the
experiment.**

**And the report's closing framing needs one correction, which is the reason this pass exists.** Phase 0.5
explains our strawberry parity as zero-sum — the donor's 08-14 opponents were naive, "the $7.833/ep is a
ceiling against a pool that no longer exists." That is sound for the **$/u** measurement. It **cannot**
explain the rating gap, because both sides of that gap are being earned against the **same live pool right
now**: leaderboard 2026-08-18 14:36 UTC reads **ReCurSiON 2.989,4** with `LastSubmissionDate` frozen at
**08-14 14:14** — the exact submission we reconstructed — against our **55586926 at 1.886,8**
(1.915,8 → 1.906,5 → 1.886,8, `LastSubmissionDate` unchanged). ~1.100 points, live, between the donor's
route and our 50-town average of it. **The strawberry channel is closed; the gap is not.**

## The one question

> **At the 58 of 127 state-dependent market steps that carry a WOOL (26) or MILK (45) sell — steps
> counted once each, since most disagreement steps trade several products at once — does the donor's
> action move with the town's shop draw? If it does, the majority vote erased a
> rule a 50-town mode structurally cannot represent, and we have located the erased conditioning that
> strawberry did not contain.**

WOOL is the sharpest instrument in the repo for this. `YARN_STORE` is the **only** shop that drains WOOL,
**34% of towns draw none** (§4.1b, matching the engine's predicted 34,4%), and a majority vote over 50
towns must emit *one* action into a population where roughly a third of towns have zero demand. If the
donor sells WOOL differently in a yarn-dead town than in a yarn-rich one, the vote cannot carry it.

## Method — the Phase 0.5 instrument, generalised (paper, zero episodes)

Extend `analysis/s6_step2b_phase05.py` (`recover`) from `STRAWBERRY`/`STR_SHOPS` to a **per-product**
sweep, driving the shop set from the engine's own `SHOPS` table rather than a hand-written constant. Same
alignment (stream index *i* ↔ action in `steps[i+1]`, obs in `steps[i]`), same 50 traces, same five
instruments, run per product:

1. **Determinism** — of the product's sell-steps, how many are byte-identical across all 50 traces, and is
   the residual the *same fixed trace subset* (43/45/46/49) as strawberry's, or a **town-varying** one?
   A town-varying residual is the positive result; a fixed-subset residual is another variant artefact.
2. **Invariance — the decisive frame.** At each contested step, tabulate the action against that town's
   realised draw: for WOOL, `yarn_stores ∈ {0,1,2,…}` and the WOOL list price; for MILK, the milk-shop
   count and price. **State the ranges the way Phase 0.5 did** ("all 50 sell exactly N while price spans
   $X–$Y and shops span A–B"). Report the **zero-drain sub-population separately** — the 0-YARN_STORE
   towns are the whole test, and if the sample holds too few of them, say so and stop rather than
   concluding invariance from a thin cell.
3. **Feature regression** — corr(units sold, feature) over the contested steps for: own shed inventory of
   that product, shop count for that product, current list price, day/turn, bank. Phase 0.5's strawberry
   row was shed **+0,92** / shops **+0,02**; a materially non-zero **shop** correlation on WOOL or MILK is
   the finding.
4. **Calendar** — what fraction of the product's units land at hour 0. Strawberry was 79,5%. A product
   that is *not* calendar-locked has room for a conditioned rule that strawberry did not.
5. **Vote reproduction** — does the reconstruction stream emit the modal per-product volume, as it did for
   strawberry's 290? Where it does not, that step is a candidate loss and belongs in the report by number.

Then, for whichever channel survives, **price the surface area on paper before anything is built**
(§3.4): units × the realised $/u spread between the drain-rich and drain-poor sub-populations, and state
plainly that it is a ceiling against the pool we meet.

## Kills / branches, pre-registered

- **(i) Every non-strawberry channel is town-invariant too** ⇒ the "erased conditioning" family closes
  **channel-wide**, not just for strawberry. That is a real, final result: it says the vote is a faithful
  reproduction of the donor's whole market layer, and the ~1.100-point gap must live somewhere the market
  layer is not. **Record it, close the family in §3.3, and the queued Track 2 becomes the pass that
  ships.**
- **(ii) WOOL or MILK conditions on shop identity** ⇒ we have located the rule Phase 0 assumed and
  strawberry did not contain. **Do not build it this pass.** Report the rule, its size, and — via step 0
  leg 3 — the fraction of episodes in which its conditioning state is **readable in time** (the drain rank
  is stable only from median day 15). That cap is part of the finding, not a detail.
- **(iii) The residual is the fixed 4-trace variant again** ⇒ variant artefact, not conditioning; fold it
  into (i).
- **(iv) The zero-drain cell is too thin to decide** ⇒ say so, report the cell counts, and stop. Do not
  read invariance off a cell with n<5 towns.

## Standing conditions

**No `agent/` change. No episodes. No upload (R27).** Nothing ships from this pass, so the active-pair
eviction is not raised here. Derived artefacts stay **gitignored** (§2.4b / R11) and must carry the
**verdict string** itself (R35). Guards in `tests/`. Competitor notebook source untouched (§2 item 8).
Report to `baselines/<date>/`, `memory.md` entry, commit with no co-author.

Carry the live-pool anomaly into the report as a standing, unexplained fact with its numbers
(ReCurSiON 2.989,4 frozen 08-14 vs our 1.886,8, same pool, 2026-08-18 14:36 UTC), whichever branch fires.
Under R36, quote it as a **submission-level** comparison — it is one, both sides being the rating of a
specific submission — and draw no band-crossing conclusions from it.

## Out of scope

- **Arms A/B/C** ⛔ refuted by Phase 0.5. Not revived, not re-run, not tuned.
- **Any strawberry overlay** ⛔ closed (§3.3). **Step 2a's wheat repair** ⛔ on the shelf. **C-A** ⛔
  refuted. **C-C (MELON)** still last.
- **Building whatever this pass finds.** This is a bounding pass; it ends with a measurement and a branch,
  the way C-A and Phase 0.5 did.
- **A donor swap**, **RL**, **planner refinement** — all unchanged from the previous brief.

---

## ⏸️ Queued — Track 2: verbatim ReCurSiON trace vs our majority vote

**Not in this pass, by size and by dependency.** It needs the full §2.1.3-5 ladder (SMOKE 0-11 → DEV vs
the non-mirror bench → unpinned holdout 100-147, both seats) *and* a shipping decision with the §6bis
checklist — and its **design depends on this pass's branch**: under (i) the verbatim trace is the right
challenger, under (ii) the right challenger is the recovered conditioning rule, and a verbatim trace
carries one town's answer into all towns.

The measurement it exists for: **we have never played the vote against a verbatim single ReCurSiON
trace**, same donor, same town, both seats. Materials are already in hand —
[analysis/tape_agent.py](analysis/tape_agent.py) plus the 50 traces under `data/archive/raw/2026-08-16/`.
The transfer-ratio prior favours verbatim: Valmorlee's verbatim tape reached **87%** of its donor
(1.599,1 / 1.842,4); our vote reaches **63%** (1.886,8 / 2.989,4). Same instrument, two donors, opposite
outcomes — that is the §1 transfer-ratio row, still unexplained.

**Upload economics, for the pass that ships:** a new submission evicts by date, and the oldest active is
`55575305` (Ueddy, **1.372,6**) — our weakest, so the eviction is near-free. **The upload remains the
user's call and a prerequisite, not a consequence (R27).**

**And the clock, stated correctly:** the final ranking is one Bradley-Terry tournament over
**post-deadline** episodes, so today's drifting 1.886,8 is a **predictor, not the score**. What is scored
is the strength of the active pair on **2026-09-30** (43 days out). The drift is diagnostic — our route is
losing ground to an improving pool — and re-uploading the same route does not fix it, since a fresh
submission simply re-converges to its current fair value. Budget the remaining passes on that basis:
roughly 2-3 days per converge-and-read, two active slots, eviction by date.
