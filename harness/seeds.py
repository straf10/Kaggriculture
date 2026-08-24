"""Single source of truth for which seeds mean what.

No other module or script should hardcode a seed list or range — import from here so a
change to the dev/holdout split can't happen in one place and not another.

DEV_SEEDS is for screening and tuning: touch these freely, decide on them.
HOLDOUT_SEEDS is for final confirmation only (screen -> confirm protocol) —
no tuning decision may be made by looking at holdout results. SMOKE_SEEDS is a coarse,
fast sanity check; a smoke result is never a GO by itself.

CONFIRM2_SEEDS (review.md C1, 2026-08-06): HOLDOUT_SEEDS was burned for the v1c-vs-v1d
question — a second holdout-confirm pull was made after a config value (`ne_carrot_tiles`)
was picked by looking at the first pull's result, which is a tuning decision on holdout data,
not a confirmation. An until-then-untouched second confirm set for re-deciding that specific
question. Like HOLDOUT_SEEDS, once a (agent_b, seed set) pair is confirmed against, it is
burned for that question — see harness.compare's confirm ledger (review.md C2).

CONFIRM_SEED_SETS lists every seed set that may back a stage="holdout-confirm" compare()
call — a union, not a single range, precisely because a burned set (HOLDOUT_SEEDS) needed a
successor without silently allowing arbitrary ad-hoc seeds to also pass the stage check. Add
new confirm sets here, never inline in a caller.
"""

DEV_SEEDS = range(0, 48)
HOLDOUT_SEEDS = range(100, 148)
SMOKE_SEEDS = range(0, 12)
CONFIRM2_SEEDS = range(200, 248)

CONFIRM_SEED_SETS = (HOLDOUT_SEEDS, CONFIRM2_SEEDS)

# Every named seed set, keyed by the name used in ledger/provenance rows and --seed-set.
NAMED_SEED_SETS = {
    "dev": DEV_SEEDS,
    "holdout": HOLDOUT_SEEDS,
    "confirm2": CONFIRM2_SEEDS,
    "smoke": SMOKE_SEEDS,
}
