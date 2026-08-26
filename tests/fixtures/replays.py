"""Synthetic replay generation from the real engine.

`write_synthetic_replay` runs a `kaggle_environments.make("kaggriculture")` episode
to completion and writes the result in the on-disk replay format consumed by
`analysis/s8_replay_io.{meta,load,replay_paths}`.  The episode is real engine output —
not a hand-crafted blob — so every downstream consumer (ledger, metrics, bench) sees
structurally correct data.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from kaggle_environments import make

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def write_synthetic_replay(
    dir_: Path,
    episode_id: int,
    *,
    teams: tuple[str, str] = ("STRAF", "OppA"),
    seed: int = 0,
    episode_steps: int = 60,
    seat0_action=None,
    seat1_action=None,
    shed_preload: dict | None = None,
    gzip_it: bool = False,
) -> Path:
    """Run a real engine episode and write it as a replay file.

    Parameters
    ----------
    dir_ : directory to write the replay into.
    episode_id : the EpisodeId stamped into the replay info.
    teams : two-element tuple of team names.
    seed : engine seed.
    episode_steps : number of engine steps (including step 0).
    seat0_action : callable(step_index) -> action dict, or None for PASS.
    seat1_action : callable(step_index) -> action dict, or None for PASS.
    shed_preload : {product: qty} pushed into seat 0's shed before running.
        Ensures market activity so downstream tests see real trades.
    gzip_it : write .json.gz instead of .json.

    Returns the path to the written file.
    """
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": episode_steps})

    if shed_preload:
        for product, qty in shed_preload.items():
            env.state[0].observation.private["shed"][product] = qty

    act_a = seat0_action or (lambda _i: PASS)
    act_b = seat1_action or (lambda _i: PASS)
    i = 0
    while not env.done:
        env.step([act_a(i), act_b(i)])
        i += 1

    env_json = env.toJSON()

    replay = {
        "info": {
            "EpisodeId": episode_id,
            "TeamNames": list(teams),
            "seed": seed,
        },
        "rewards": list(env_json["rewards"]),
        "steps": env_json["steps"],
        "configuration": env_json["configuration"],
    }

    name = f"episode-{episode_id}-replay.json"
    if gzip_it:
        name += ".gz"
        path = dir_ / name
        with gzip.open(str(path), "wt") as f:
            json.dump(replay, f)
    else:
        path = dir_ / name
        path.write_text(json.dumps(replay))
    return path
