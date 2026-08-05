Comment on the final evaluation for this competition
Hi everyone,

For those of you familiar with Kaggle simulations, you may notice the final evaluation is different compared to other competitions of the same format. At the submission deadline, we will continue allowing submissions to run episodes for two weeks. At the end of those two weeks, we will be running a single Bradley-Terry Tournament, which will determine the final leaderboard rankings. This is also specified in the Evaluation section in the Overview tab. While this is different from other simulations, we believe this change reduces any "hot streaks" that may otherwise influence the final results.

Happy farming! 👨‍🌾

Daily Top Episodes Dataset
Each day we order episodes by the average rating of the agents playing (at the time). Then we download up to 20 GB of replays and make a new daily dataset! This should be helpful for everyone trying IL/BC, bootstrapping RL, or just gathering statistics.

https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index

Crucial Information for Starters and Organizers: Documentation vs. Engine Discrepancies
If you are building strategies based strictly on the documentation, please note that the underlying game engine executes several mechanics differently. Where the docs and the engine disagree, the engine wins, adjust your agent's logic accordingly:

Game Mechanics & Yield Discrepancies
Animal Care Bonus: The Rulebook states that feeding and caring for an animal increments pending_care_bonus by 2. In the engine, the payout increments by only +1 per day.

Fertilizer Selling: The Getting Started guide explicitly notes that fertilizer can only be bought, not sold. In practice, the market logic accepts SELL operations for fertilizer.

Digging Up Structures: The Rulebook implies the DIG action can clear goose coops or pastures. In the engine, DIG fails on occupied structures; it only works on empty ones.

Planting-Day Watering: The main Rulebook omits immediate watering rules, while the Getting Started guide notes the planting day counts as the first unwatered day. Because the end-of-day increment runs before the weed check, an unwatered seed turns into a weed that exact same night.

Melon Bonus Window: The Object Types table lists the Melon's Time to Max Yield as 12 days. In practice, because yield reaches the maximum of 6 units at age 10, the last two days of the documented 6–12 window are dead turns that add no yield.

Strawberry Yield Limit: The Object Types table lists Strawberry as an ongoing crop with "Subsequent Yields: every other day". In reality, production is capped at a max yield of 4. A strawberry plant produces exactly 4 times (ages 10, 12, 14, 16) at +1 unit each, and then dies. It is not an indefinite producer.

Yield-Per-Day Calculations: The "Max yield / tile / DAY" table entries (e.g., Tomato at 4, Strawberry at 2, Cow at 1.0, Sheep at 0.67) use inconsistent formulas. Actual effective per-day yields differ significantly (e.g., the actual per-day yield for Tomato is 1, and for Strawberry it is 0.5).

Map & Unit Traps
Shed Grid Absence & Location: The documentation states actions require being "orthogonally adjacent to the shed" without specifying coordinates. Note that the shed does not exist as a tile object in the tiles array, so a starter script searching the array for it will find nothing. Its access points are strictly the four center tiles: (4,4), (5,4), (4,5), and (5,5).

Farm Hand Spawning on Locked Tiles: Hired hands spawn across the four center access tiles, prioritizing a free space following NWSE, or the least occupied space. Because only the NW quadrant is unlocked at the start, hands can spawn on LOCKED tiles. While most can step out within a turn, a hand landing on (5,5) (diagonally opposite the start) is completely enclosed by locked tiles and cannot move until you buy land.

Submission & Notebook Pitfalls
Bare main.py vs. Notebook Submission: The Getting Started guide's quick-start dictates a main.py file at the root. However, if you are using a Kaggle Notebook and strictly writing %%writefile main.py, the notebook's "Submit to Competition" feature produces no submission artifact and fails at scoring. Ensure you are bundling your files properly or using submission.py depending on the platform's execution environment.

A few rule questions for the organizers
Hi @bovard ,

I found a few places where the competition page, README.md, and AGENTS.md seem to say different things. Could you please clarify which behavior is intended?

1. Can fertilizer be sold?
AGENTS.md says:

“Fertilizer can only be bought, not sold.”

However, README.md says:

“Every product (and fertilizer) starts the game with a market inventory of I0 = 10,000 units, far above any single game's realistic production volume so that inventory is essentially guaranteed to stay positive. The sell price for a product is base at I0, rises as inventory falls (players buying or town consumption draining supply), and falls as inventory grows (players selling).”

Fertilizer also has both below-equilibrium and above-equilibrium market parameters:

| Fertilizer | Base: 100 | I0: 10,000 | T: 200 |
| Below func: linear | Below target: 0.40 |
| Above func: linear | Above target: 0.40 |
| P(I0−T): $140 | P(I0+T): $60 | P(I0+2T): $20 |
Is the following order valid?

["SELL", "FERTILIZER", n]
If fertilizer cannot be sold, when would its inventory rise above I0, and what are above_func and above_target used for?

2. Does an animal need CARE to produce fertilizer?
The action description says:

“COLLECT_FERTILIZER — Collect 1 fertilizer from the animal. Each surviving animal makes 1 fertilizer available at the end of every day; collecting consumes that day's stock and the next becomes available after the next end-of-day refresh.”

This sounds like every surviving animal makes fertilizer available, even if it did not receive CARE.

But the observation description says:

"fertilizer_available": bool,   # set after CARE; cleared by COLLECT_FERTILIZER
Which description is correct?

Does CARE only affect pending_care_bonus and the next egg, milk, or wool production, or is it also required to make fertilizer available?

Also, since fertilizer_available is a Boolean, does uncollected fertilizer stay capped at one unit instead of accumulating over multiple days?

3. Why is T based on a 24-day game?
The competition page says:

“This simulation competition is a turn-based farming game where two players compete on separate farms to see who can earn the most profit by the end of a 30-day season (720 turns).”

The rules also say:

“There are 24 turns per day, and 30 days in the season - 720 total turns.”

But the Price Function section says:

“T is the production capacity of a single 5×5 field over a 24-day game at optimal watering with no fertilizer (animal totals are pre-discounted by 30% to account for wheat-feed overhead).”

Is the 24-day period an intentional reference window for calibrating the market curves, or is it wording left over from an earlier version of the game?

If it is intentional, could you explain why the market uses 24-day production capacity when the default season lasts 30 days?

These details affect fertilizer valuation, animal action planning, and market modeling, so an official clarification would be very helpful. Thank you!


Thanks for your great questions! I've updated the readme and "how to play" instructions, and will also answer here.

1. Can fertilizer be sold?

Yes! Readme has been updated to state this.

2. Does an animal need CARE to produce fertilizer?

No, it does not. The comment in kaggriculture.py is misleading and has been updated. You are also correct that fertilizer does not accumulate, a new unit is not yielded until the previous one is picked up.

3. Why is T based on a 24-day game?

We've found that the early days of the game are really setup focused, so the 24 day window represents those later days in the game where things start to heat up as crops are available and the town expands. This was an explicit design choice, but definitely a non-obvious one, so I've added clarification to the readme.



How exactly is skill score calculated? (Slow skill rating increase, stop improving while still winning)
First of all, thanks for the very cool competition. I'm enjoying it and learning a lot.

I think there's some problems with the scheduling and match up of the LB. My agent only suffered 1 loss at around 1850, then a win streak of >20 games. After another loss at 2500, now it stopped getting matches for at all for 2 hours and thus not being able to improve its score.

What is even more strange is during my win streak of >20 games, the rate of improvement slow down from 70-80 points per game at 1850 to barely 13-20 points per game at 2450. My opponent's rating score alone cannot account for this slow down (opponent with the same score as me at 1850 gives a lot more improvement than at 2450). Had it

To me, it feels like the the current setting favors deterministic method that reliably rise to the top, then plateau, than probabilistic method that might get a loss earlier but can compete at higher rate.

What frustrate me the most is that while my agent still have very high win rate, it just don't get match as often anymore. At this rate, if it get 1 win every hour, then it still need a full day (15 x 24) to get to 2860.

The frequency of the matches is expected to drop, since the evaluator gives more games to the newest bots

Every bot submitted will continue to play episodes until the end of the competition, with newer bots playing a much more frequent number of episodes. On the leaderboard, only your best-scoring bot will be shown, but you can track the progress of all of your submissions on your Submissions page.

How much rating change our agents get seems a lot like the Orbit Wars competition, where the agents had a hidden σ, which determined how "certain" the current rating was. The more matches you play, the more confident the ranking system will be in your rating and thus the absolut change in your rating after a match is expected to fall. However, the Orbit Wars competition where a bit more specific about how the rating was calculated

(from Orbit Wars) Each Submission has an estimated Skill Rating which is modeled by a Gaussian N(μ,σ2) where μ is the estimated skill and σ represents the uncertainty of that estimate which will decrease over time.

Are Agents Really Competing Against Each Other?
I am not sure I understand the intended purpose of this competition, and I may be missing something. It seems highly vulnerable to trajectory copying because the two agents do not meaningfully interact or affect each other; they can independently perform the same actions. The only significant randomness I have found is the order in which town shops unlock, which may not be enough to prevent participants from copying or combining publicly visible high-scoring action sequences with simple fallback heuristics. Even now, some of the top public code submissions appear to replay the trajectories of leading agents. Bradley–Terry may produce a more reliable ranking from the match results, but it does not seem to address this underlying design issue. Is there an important mechanic or aspect of the final evaluation that I am overlooking?

The current meta seems to be to just submit a sequence of actions copied from someone else, but I expect a good bot that intelligently reacts to the market to take over eventually. Someone needs to write it or train it though.

Yes, the way you "cash" out is completely determined by market dynamics that you PARTIALLY control. Your opponents decision of what to buy and when to sell directly affects your prices when you try to do the same. If an opponent tries to oversell something -- it makes it cheaper for you to buy. If you both are trying to sell the same thing, both your profits will suffer -- and the first to sell gets the better price.

