Verified against the artefacts. The housekeeping is fixed properly this time — three immutable checkpoints, and the inertness check now runs with --metrics and comes back genuinely byte-equal (escapes 4/4, water-weeds 45/45, crop_tile_days 13771/13771, animals_underfed_days 842/842, moving 60,1%/60,1%, mean_diff $0,00). 248 passed. That part is exactly right.

But the summary reports the commute number and omits the one that decides, and once you put them side by side the whole pass says something different.

Every arm reduced walking by reducing work
arm	moving	idle	working turns	crop_tile_days	dollars
baseline v1o_2	60,1-60,3%	17,1-17,5%	32.174-32.902	13.628-14.112	—
A1 COW-first	46,0%	32,3%	29.785	9.824	−$7.711 REGRESSED 0-12
B carrot-only	57,7%	20,9%	30.327	12.343	−$2.293 INCONCLUSIVE 1-11
v1p2b sticky zoning	58,9%	19,1%	31.827	11.789	−$2.689 REGRESSED 1-11
Arm A1 posted a 14,3pp commute reduction — by far the largest ever measured here — and did fewer working turns than baseline. The freed turns went to idle, because the farm had shrunk: 48 escapes and 30% fewer crop tile-days mean there was less to walk to. Not one arm in this entire step converted a travel turn into a work turn.

The kill criterion I wrote was wrong, and I should say so plainly: worker_turns_moving < 55% is satisfiable by doing less. Arm A1 cleared it at 46,0% while destroying the farm — had it not also broken the escape counter, it would have "passed." The criterion should have been absolute worker_turns_working per episode, with crop_tile_days held flat. Moving% is a diagnostic, never a target. Worth fixing in the ROADMAP before anything else is screened against it.

Two omissions worth correcting in the record: A1 is REGRESSED −$7.711, 0-12 seeds, 0-24 episodes — not "same magnitude as the original STOP," which was −$875 INCONCLUSIVE; the COW-first reorder made everything substantially worse. And v1p2b is still REGRESSED −$2.689 with water_weeds_lost 226 vs 61 and tile-days −15%. Sticky zoning removed the structural breaks, but it did not make zoning work.

On the zoning conclusion
The pre-registered criterion fired, so stop — re-litigating a criterion after seeing the data is what the protocol exists to prevent. But the recorded reason should be corrected, because "zoning was never the lever" isn't what the data says. Zoning did cut travel (60,3 → 58,9) and cut work harder (−828 turns), while quadrupling water-weeds. The mechanism is: zoning trades cross-quadrant commute for within-quadrant starvation, and the exchange is negative — the apportionment is by task count, but tasks aren't equal work, and a quadrant with someone-but-not-enough never triggers the empty-zone fallback. What's refuted is proportional-by-task-count apportionment, not the idea that travel share is movable; A1's 46,0% proves it is very movable.

The finding nobody named, and it's the biggest one here
Arm A gave 48 escapes. Arm A1 gave 48 escapes. Twenty-four episodes each — exactly 2,00 per episode, in both, under opposite COW/SHEEP assignments. That isn't a race one side wins; a race would respond to reversing it. It's a saturating structural limit: perturb early-game timing at all and precisely two animals are always lost, deterministically, in every seed and both orientations. Arm B — a pure crop knob, zero animal change — leaked 12.

This same defect has now been misattributed four times: as hiring cost (v1j), as distance to the far tiles (v1h'), as feed-priority contention (v1o.2/v1o.3), and as animal-type ordering (v1p.1). It is the only bug in this repo that reproduces in 100% of seeds — which makes it the cheapest thing here to debug and one of the most valuable, because herd 10 → 13 is a §4.0 profile item blocked squarely behind it.

The concrete hypothesis to test first: the engine escapes at consecutive_unfed >= 2, so an animal PLACEd with no delivery slack left in the day gets zero feeds on day d, and one miss on d+1 is enough. The guard is a precondition, not a priority: never emit a PLACE unless a FEED can still reach that tile today — wheat in hand or fetchable, and turns_left_today >= distance + 1. That directly encodes the engine's own rule and is a small change to _build_animal_tasks.

One caveat on effect sizes: the baseline's own animals_escaped reads 0, 2, 4 and 5 across the four comparisons (same agent, same seeds, same pin — it's the §2.1.1 occupancy coupling changing the opponent's farm). Pairing within a comparison is still valid, but on 24 SMOKE episodes this counter has a noise floor of roughly ±5. Arm B's "12 vs 2" is therefore much weaker evidence than 48 vs 0-5; I'd treat "a second independent mechanism" as a hypothesis, not a result.

What I'd do next
The onboarding-escape defect — deterministic, 100% reproducible, four times misattributed, and it gates herd 13. Debug it before anything else; a KAGGRI_DEBUG replay of one seed under arm A1 should show the exact step it happens.
③ travel-ratio diagnostic, with the corrected success metric (working turns, not moving%).
④ min-cost matching stays contingent on ③.
And one process note for the ROADMAP: this pass is the second time a mechanism has been "confirmed" from an arm whose dollars were REGRESSED. A confirmed mechanism and a viable increment are different claims — the report should always state both, in that order.