"""Metrics extraction from a recorded episode (env.toJSON()). plan.md §2.4 — Step 0 minimum
covers final/opponent bank and the bank curve; Step 1 (guard metrics G1-G11) adds the rest
once agent/ exists to guard.
"""


def extract_metrics(env_json: dict, seat: int) -> dict:
    """`env_json` is env.toJSON() (or an equivalent replay dict loaded from disk)."""
    opponent = 1 - seat
    steps = env_json["steps"]
    bank_curve = [step[0]["observation"]["farms"][seat]["money"] for step in steps]
    opp_bank_curve = [step[0]["observation"]["farms"][opponent]["money"] for step in steps]

    final_bank = env_json["rewards"][seat]
    opponent_final_bank = env_json["rewards"][opponent]
    if final_bank > opponent_final_bank:
        outcome = "win"
    elif final_bank < opponent_final_bank:
        outcome = "loss"
    else:
        outcome = "tie"

    return {
        "final_bank": final_bank,
        "opponent_final_bank": opponent_final_bank,
        "outcome": outcome,
        "status": env_json["statuses"][seat],
        "bank_curve": bank_curve,
        "opponent_bank_curve": opp_bank_curve,
    }
