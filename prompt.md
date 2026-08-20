# Pass brief — S6 step 2e: the loss tail — why we lose a quarter of our episodes badly

> **Read first:** `baselines/2026-08-18/s6_step2d_report.md` (leg A's mechanism — this pass re-prices it)
> and `s6_step2c_report.md`; [ROADMAP.md](ROADMAP.md) **§1** (the five-week puzzle: *"measured local wins
> that convert into ~nothing on the ladder"* — this pass is that puzzle, measured on our own ladder
> episodes); **§4.1b** (99-100% of realised-price variance is between-town — **the rival hypothesis, and
> it is strong**); §3.3's **step 2a / 2c / 2d** rows; **§3.4** (the rating-conversion note: a small
> *perfectly consistent* edge converts well — this pass is about its inverse); **R21 / R27 / R32 / R36**;
> §2.1.1-5; the top of [memory.md](memory.md).

## Where we are — and the pivot this pass makes

Five passes (2a, 2b, 2b-0.5, 2c, 2d) have each asked **"what did the majority vote erase?"**, priced the
answer as a **mean dollars-per-episode**, and closed it below the gate:

| pass | erased component | bound | verdict |
|---|---|---:|---|
| 2b-0.5 | strawberry sell-timing | ≈$0 (zero-sum) | ⛔ never town-conditioned |
| 2c | the whole market layer | ~$1.202/ep (WOOL drift, shelved) | ⛔ town-invariant channel-wide |
| 2a / 2d | closed-loop tile control | **$597/ep → +2,4 pts** | ⛔ real mechanism, bounded small |

**2d found a genuine town-reactive rule** — the hands DIG a per-town spawned weed, re-PLANT, and WATER by
the actual dry state, re-syncing one op later; carried by 25 traces, farmer-op invariant 0/88, 62% of
hand-slot disagreements standing on a disjoint tile. That is the first real closed-loop rule any pass has
located, and the finding is not in question.

🔴 **What is in question is the currency of its bound.** $597/ep is a **mean**. The ladder pays in
**episodes won**. A mechanism that costs little on average but occasionally cascades flips episodes, and
flipping episodes is what moves rating. Measured on the 84 real ladder episodes of `55586926` already on
disk (**the 85th file is a STRAF-vs-STRAF validation episode — exclude it from every per-episode
average**; 2d's $597/ep and leg B's $85.468 median both include it):

| | n | our bank (med) | opp bank (med) | margin (med) | margin p10 |
|---|---:|---:|---:|---:|---:|
| **wins** | 56 | **$94.028** | $77.458 | +$6.046 | +$244 |
| **losses** | 28 | **$77.428** | $87.568 | −$3.600 | −$21.496 |

**Our own bank is $16.6k lower in the episodes we lose**, and across all 84 it spans p05 **$53.9k** ·
p10 **$58.5k** · median **$85.8k** · p90 **$125.3k** · max $140.9k — a **p90/p10 ratio of 2,14**, with
**22 of 84 episodes (26%) under $70k** and a tail to **$36.2k**, 42% of our own median. Leg B's own
richness match reports every one of these towns at **8 unlocked shops (range 8-8)**, so a shop-*count*
story cannot carry it.

**And the fact that most wants explaining:** our converged win rate is **65% and stable** (last 56
episodes 64,3% / 64,3%; last 20 **65,0%**; last 10 60,0%) against a rating that is flat-to-**declining**
(1.915,8 → 1.906,5 → 1.886,8, `LastSubmissionDate` unchanged). Winning two thirds of episodes while
*losing* rating is §1's puzzle, now measured rather than inferred. Note this rehabilitates the win-rate
half of the band table R36 invalidated: **R36 killed the opponent-rating axis, not the win rate**, and the
65% survives at n=56, not n=20.

## The one question

> **What separates our $36-58k episodes from our $95-125k ones — and is 2d's open-loop desync the cause?
> If it is, the mechanism's value is not +2,4 rating points, because +2,4 prices a mean where the ladder
> pays per episode.**

## ⚠️ The rival hypothesis, pre-registered as a control, not an afterthought

**§4.1b measured that 99-100% of realised-price variance is *between-town*, with the shop draw moving
STRAWBERRY 18×, MILK 14×, WOOL 5,3×.** Eight shops are unlocked in every one of our towns, but *which
eight* varies, and that alone could produce a 2,14× bank spread with no defect whatsoever. **This is the
strongest prior against the desync reading and it must be able to win.** Leg C runs it as a control; if
composition explains the tail, the honest result is that the tail is the town and 2d's shelving stands.

## Legs — all desk-only, zero episodes, cheapest first

**Leg A — un-average the 2d instrument (free).** `analysis/s6_step2d.py` already computes
`plant_decay_units_lost` / `unexpected_weeds_lost` / `water_weeds_lost` across the live set and reports
the **mean** ($597/ep). Emit them **per episode** instead, and regress our own final bank on them across
the 84. Report the counters' distribution, not just their mean — specifically their value in the 22
sub-$70k episodes versus the top quartile. **A mean of 4,99 weeds/ep is consistent with both "5 weeds
every episode" and "0 in most, 25 in a few", and those two have completely different rating prices.**

**Leg B — desync depth, the direct test (free).** The vote is open-loop, so this is computable exactly:
for each of the 84 live episodes, walk the emitted stream against the **actual** board and record (1) the
step of the **first** action that is illegal or a no-op given the real tile state, (2) the running count
of such actions, and (3) whether the count is front-loaded (a cascade) or scattered (isolated slips).
2d's own trace shows the failure shape to look for — the vote emitting `WATER` onto a tile that holds a
`WEED` in that town. **Correlate desync depth against final bank.** This is the instrument the whole pass
turns on; legs A and C are its controls.

**Leg C — the §4.1b control (free).** For each episode, extract the town's **shop composition** (not just
the count of 8) and the realised per-product $/u, and ask how much of the bank spread it explains on its
own. Then ask whether leg B's desync depth explains anything **after** composition is partialled out.
**Report both the raw and the residual association.** If composition carries the tail and desync adds
nothing, say so plainly — that is the result, and it closes the family for good.

**Leg D — convert to the right currency (free, arithmetic).** Whatever leg B/C locate, price it in
**episodes flipped**, not dollars per episode: how many of the 28 losses had a margin smaller than the
episode's own measured loss from the mechanism? That count, over 84, is the rating-relevant number, and it
is the one 2d's +2,4 pts did not compute. State it beside the $597 mean rather than replacing it, and be
explicit that a flipped-episode count is an **upper** bound (it assumes recovery converts to a win).

## Kills / branches, pre-registered before any leg runs

- **(i) The tail is town composition (leg C wins, leg B's residual ≈ 0)** ⇒ the bank spread is §4.1b
  operating as measured, there is no defect, and **2d's shelving stands unchanged**. Close the
  re-pricing question, record it, and the open question returns to R36 / §4.4#1's clock. **A clean
  negative here is a real result and ends the "what did the vote erase" programme properly.**
- **(ii) Desync depth carries the tail after composition is controlled** ⇒ **2d's bound was priced in the
  wrong currency.** Report the flipped-episode count and **re-open the closed-loop rule in §3.3 at its
  corrected price**. Still **do not build it this pass** — recover, re-price, stop.
- **(iii) Neither explains it** ⇒ the tail has a third owner (opponent identity, seat, an unmeasured
  structural counter). Say so, name what you ruled out, and do not fill the gap with a guess.
- **(iv) Leg A finds the counters are uniform across episodes** (no tail in weeds/decay at all) ⇒ leg B's
  hypothesis is dead before leg B runs; go straight to leg C and report.

## Corrections to record in this pass's report

1. **Leg B's opponent-pool reading is circular.** 2d attributes most of the $4.718/ep absolute bank gap to
   the donor's opponents banking $88,0k vs our $79,3k — "a richer/stronger pool the donor did not create."
   **Kaggle pairs by rating**, so opponent strength is a *consequence* of the 2.989 vs 1.887 rating
   difference, not a cause of it. It cannot be netted out as an explanation. The head-to-head margin
   comparison (+$2.922 vs +$2.100) stands; the causal gloss on it does not.
2. 🔴 **R36 prescribes something this data cannot support.** R36 directs future passes to read the
   opponent rating "recorded in the episode metadata at play time." **Verified this session across all 85
   live replays: `info` carries `Agents`, `EpisodeId`, `LiveVideoPath`, `TeamNames`, `seed` and *no rating
   field of any kind*.** The rule is not executable here; the team-name proxy it warns against is the only
   axis that exists. **Amend R36** to say so, rather than leaving a standing instruction that silently
   cannot be followed.
3. **The 85th live file is a STRAF-vs-STRAF validation episode**, not a ladder episode. Every per-episode
   average computed over "85 live episodes" (2d's $597/ep, leg B's $85.468 median) includes it. The
   effect is small but the set is **84**.

## Standing conditions

**No `agent/` change. Zero episodes — every leg is desk work on replays already held. No upload (R27)**,
so the active-pair eviction is not raised. Derived artefacts stay **gitignored** (§2.4b / R11) and carry
the **verdict string** (R35). Guards in `tests/`. R32 applies: price every counter you report, and list
unpriced structural counters as "unpriced" rather than omitting them. Competitor notebook source
untouched (§2 item 8). Report to `baselines/<date>/`, `memory.md` entry, commit with no co-author.

## Out of scope

- **Building anything.** This is a re-pricing pass. It ends with a measurement, a corrected bound and a
  branch — the discipline the last five passes got right.
- **Leg C of step 2d (the tape-vs-vote SMOKE head-to-head)** — deliberately **not** revived. Both sides
  are open-loop and differ only at the disagreement steps 2c and 2d have bounded; it would read near-tie
  and cost ~24 episodes to learn nothing.
- **The adaptive layer** (§4.5b obstruction recovery / worker-count) — same class, same bound, and leg B
  of this pass is the cheaper test of whether that class matters at all.
- **Any market-layer overlay** ⛔ closed channel-wide (2c) · **step 2a's wheat repair** ⛔ on the shelf ·
  **C-A** ⛔ refuted · **C-C (MELON)** last · **a donor swap**, **RL**, **planner refinement** — unchanged.
