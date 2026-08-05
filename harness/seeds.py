"""Single source of truth for which seeds mean what (plan.md §1.5.1).

No other module or script should hardcode a seed list or range — import from here so a
change to the dev/holdout split can't happen in one place and not another.

DEV_SEEDS is for screening and tuning: touch these freely, decide on them, ablate on them.
HOLDOUT_SEEDS is for final confirmation only (plan.md §1.5.3 screen -> confirm protocol) —
no tuning decision may be made by looking at holdout results. SMOKE_SEEDS is a coarse,
fast sanity check; a smoke result is never a GO by itself.
"""

DEV_SEEDS = range(0, 48)
HOLDOUT_SEEDS = range(100, 148)
SMOKE_SEEDS = range(0, 12)
