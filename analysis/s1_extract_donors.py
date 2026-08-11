#!/usr/bin/env python3
"""S1.2 — extract donor action streams + validate replay fidelity (ROADMAP.md S1).

For each (episode_id, donor_seat) pair, this:
  1. Reads the LOCAL cached replay (data/archive/raw/<id>.json.gz — never re-fetches;
     run analysis/b0_fetch_top_replays.py first if missing).
  2. Extracts the FULL per-step action dict (`{"farmer": [...], "hands": [...],
     "market": [...]}`) for the donor seat AND its recorded opponent, for all 720 steps.
  3. Writes provenance + both streams to baselines/<date>/donors/<episode_id>_seat<seat>.json
     (baselines/ is gitignored wholesale — R11, never committed).
  4. Validates the S1 gate: replays donor-tape vs opponent-tape in OUR harness, under the
     SAME engine seed as the original episode (`replay["info"]["seed"]`), and checks the
     resulting final bank against the recorded bank within a tolerance.

This is the only place a full per-unit action sequence is read in this pass — it is
written to a LOCAL, gitignored path only, never to a tracked file (§2.4b).

Usage:
    python analysis/s1_extract_donors.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.tape_agent import make_tape_agent  # noqa: E402
from harness.play import play  # noqa: E402

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive"
RAW = ARCHIVE / "raw"
OUT_DIR = Path(__file__).resolve().parent.parent / "baselines" / "2026-08-11" / "donors"

CUTOFF_EPISODE_ID = 91476157  # min id of the daily_0810_ids.txt set used for the S1.1 target
                               # profile — donors are drawn strictly BELOW this id (older),
                               # the profile is measured strictly at/above it (later), per
                               # the v27-notebook chronological protocol adopted in ROADMAP S1.

# (episode_id, donor_seat) — all confirmed townCenterSellInterval==24 (current engine),
# all EpisodeId < CUTOFF_EPISODE_ID, donor team is one of the 9 teams the S1.1 profile
# was measured over. Picked for team diversity (Kaito Fukami / Valmorlee / Ueddy) and a
# spread of opponents.
DONOR_PICKS = [
    (90891564, 0, "Kaito Fukami vs Giba"),
    (91456307, 0, "Valmorlee vs THUNDER THUNDER"),
    (90999409, 0, "Ueddy vs Calmracer"),
]

FIDELITY_TOLERANCE = 0.02  # +-2%, ROADMAP S1 gate


def load_replay(episode_id: int) -> dict:
    path = RAW / f"{episode_id}.json.gz"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found locally — run analysis/b0_fetch_top_replays.py --ids-file "
            f"first (episode {episode_id} must be pre-fetched, this script never fetches)."
        )
    return json.loads(gzip.decompress(path.read_bytes()).decode())


def action_stream(replay: dict, seat: int) -> list:
    """The action a tape agent must return when it observes `obs["step"] == t`.

    Verified empirically (not documented anywhere): `replay["steps"][t]["action"]` is the
    action that was APPLIED to produce the state recorded AT index t — i.e. it was chosen
    in response to observing the state at index t-1 (whose `obs["step"] == t-1`), not the
    state at index t. `steps[0]["action"]` is a PASS/PASS placeholder with no earlier
    decision point (the pre-first-action reset record) and is dropped. So the stream
    returned here has 719 entries: entry t (for t in 0..718) is `steps[t+1][seat]["action"]`.
    Replaying naively at the "obvious" index-t alignment reproduces nothing — confirmed by
    a step-by-step engine replay that diverged from the recorded episode on turn 0.
    """
    steps = replay["steps"]
    pass_action = {"farmer": ["PASS"], "hands": [], "market": []}
    return [steps[t][seat].get("action") or pass_action for t in range(1, len(steps))]


def sha256_of(stream: list) -> str:
    blob = json.dumps(stream, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def extract_donor(episode_id: int, donor_seat: int, note: str) -> dict:
    replay = load_replay(episode_id)
    if replay["configuration"].get("townCenterSellInterval") != 24:
        raise ValueError(f"episode {episode_id}: not current-engine (interval != 24)")
    if episode_id >= CUTOFF_EPISODE_ID:
        raise ValueError(
            f"episode {episode_id} >= cutoff {CUTOFF_EPISODE_ID} — donors must be strictly "
            "older than the episodes the target profile is measured on"
        )
    opp_seat = 1 - donor_seat
    names = replay["info"]["TeamNames"]
    donor_stream = action_stream(replay, donor_seat)
    opp_stream = action_stream(replay, opp_seat)
    rewards = replay.get("rewards") or [None, None]

    record = {
        "note": note,
        "episode_id": episode_id,
        "engine_seed": replay["info"].get("seed"),
        "engine_config": replay["configuration"],
        "donor": {
            "seat": donor_seat,
            "team_name": names[donor_seat],
            "recorded_final_bank": rewards[donor_seat],
            "action_stream_sha256": sha256_of(donor_stream),
            "n_steps": len(donor_stream),
        },
        "opponent": {
            "seat": opp_seat,
            "team_name": names[opp_seat],
            "recorded_final_bank": rewards[opp_seat],
            "action_stream_sha256": sha256_of(opp_stream),
            "n_steps": len(opp_stream),
        },
        "donor_action_stream": donor_stream,
        "opponent_action_stream": opp_stream,
    }
    return record


def validate_fidelity(record: dict) -> dict:
    """S1 gate: replay donor-tape vs opponent-tape under the original seed; compare
    final banks to the recorded ones. Both agents are pure tapes (no agent/ involved).
    """
    donor_agent = make_tape_agent(record["donor_action_stream"])
    opp_agent = make_tape_agent(record["opponent_action_stream"])
    seed = record["engine_seed"]

    donor_seat = record["donor"]["seat"]
    agent_a = donor_agent if donor_seat == 0 else opp_agent
    agent_b = opp_agent if donor_seat == 0 else donor_agent

    result = play(agent_a, agent_b, seed=seed, steps=720, record=False, strict=False, metrics=False)
    replayed_donor_bank = result.rewards[donor_seat]
    replayed_opp_bank = result.rewards[1 - donor_seat]
    recorded_donor_bank = record["donor"]["recorded_final_bank"]
    recorded_opp_bank = record["opponent"]["recorded_final_bank"]

    def pct_err(replayed, recorded):
        if recorded in (None, 0):
            return None
        return abs(replayed - recorded) / abs(recorded)

    donor_err = pct_err(replayed_donor_bank, recorded_donor_bank)
    opp_err = pct_err(replayed_opp_bank, recorded_opp_bank)
    passed = (
        result.clean
        and donor_err is not None and donor_err <= FIDELITY_TOLERANCE
        and opp_err is not None and opp_err <= FIDELITY_TOLERANCE
    )

    return {
        "clean": result.clean,
        "health": result.health,
        "replayed_donor_bank": replayed_donor_bank,
        "recorded_donor_bank": recorded_donor_bank,
        "donor_pct_error": donor_err,
        "replayed_opponent_bank": replayed_opp_bank,
        "recorded_opponent_bank": recorded_opp_bank,
        "opponent_pct_error": opp_err,
        "tolerance": FIDELITY_TOLERANCE,
        "passed": passed,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for episode_id, seat, note in DONOR_PICKS:
        print(f"\n=== donor: episode {episode_id} seat {seat} ({note}) ===")
        record = extract_donor(episode_id, seat, note)
        fidelity = validate_fidelity(record)
        record["fidelity_check"] = fidelity

        out_path = OUT_DIR / f"{episode_id}_seat{seat}.json"
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"wrote {out_path} (LOCAL, gitignored)")
        print(f"  donor={record['donor']['team_name']} sha256={record['donor']['action_stream_sha256'][:16]}...")
        print(f"  recorded bank: donor=${fidelity['recorded_donor_bank']:,} "
              f"opponent=${fidelity['recorded_opponent_bank']:,}")
        print(f"  replayed bank: donor=${fidelity['replayed_donor_bank']:,} "
              f"opponent=${fidelity['replayed_opponent_bank']:,}")
        print(f"  pct error: donor={fidelity['donor_pct_error']:.4%} "
              f"opponent={fidelity['opponent_pct_error']:.4%}  clean={fidelity['clean']}")
        print(f"  GATE (<= {FIDELITY_TOLERANCE:.0%}): {'PASS' if fidelity['passed'] else 'FAIL'}")

        summary.append({
            "episode_id": episode_id, "seat": seat, "team": record["donor"]["team_name"],
            "opponent_team": record["opponent"]["team_name"],
            "sha256": record["donor"]["action_stream_sha256"],
            "fidelity_passed": fidelity["passed"],
            "donor_pct_error": fidelity["donor_pct_error"],
            "opponent_pct_error": fidelity["opponent_pct_error"],
            "path": str(out_path),
        })

    index_path = OUT_DIR / "index.json"
    index_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwrote {index_path}")
    all_passed = all(s["fidelity_passed"] for s in summary)
    print(f"\nS1 gate (all donors replay within tolerance): {'PASS' if all_passed else 'FAIL'}")


if __name__ == "__main__":
    main()
