"""play(): run one kaggriculture episode with recording and optional per-turn timing.

plan.md §2.4. Uses the installed kaggle-environments package's public `make`/`env.run` API
(Υ2) — the same entrypoint the Kaggle server uses, so a passing local `play()` is a faithful
stand-in for a real episode.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture.kaggriculture import agents as BUILTIN_AGENTS

from harness.metrics import extract_metrics
from harness.profile import timed

AgentSpec = Union[Callable, str]


@dataclass
class PlayResult:
    seed: int
    agents: tuple  # (name_seat0, name_seat1)
    rewards: tuple  # final bank per seat
    winner: Optional[int]  # 0, 1, or None for a tie
    statuses: tuple
    replay_path: Optional[Path]
    turn_times: Optional[list]
    metrics: dict = field(default_factory=dict)


def _agent_name(agent_spec: AgentSpec) -> str:
    if isinstance(agent_spec, str):
        return agent_spec
    return getattr(agent_spec, "__name__", repr(agent_spec))


def resolve_agent(agent_spec: AgentSpec) -> Callable:
    """callable -> itself; built-in name ("pass"/"random"/"starter") -> its function;
    a path to a .py file -> the last callable defined in that file (same loading
    convention kaggle_environments itself uses for file-based agents)."""
    if callable(agent_spec):
        return agent_spec
    if isinstance(agent_spec, str):
        if agent_spec in BUILTIN_AGENTS:
            return BUILTIN_AGENTS[agent_spec]
        path = Path(agent_spec)
        if path.suffix == ".py" and path.exists():
            return get_last_callable(path.read_text(), path=str(path))
    raise ValueError(f"Unrecognized agent spec: {agent_spec!r}")


def play(agent_a, agent_b, seed: int, *,
         steps: int = 720,
         record: bool = True, run_dir: Optional[Path] = None,
         profile_seat: Optional[int] = None,
         debug: bool = False) -> PlayResult:
    """Run one episode: agent_a as seat 0, agent_b as seat 1.

    agent_* = callable(obs)->action | "main.py"-style path | built-in name ("pass"/"random"/"starter").
    record=True writes env.toJSON() to run_dir (default runs/adhoc/) for later replay/metrics.
    profile_seat wraps that seat's agent with a per-call perf_counter timer (harness.profile.timed).
    """
    fn_a, fn_b = resolve_agent(agent_a), resolve_agent(agent_b)

    turn_times = None
    if profile_seat is not None:
        target_fn = fn_a if profile_seat == 0 else fn_b
        wrapped, turn_times = timed(target_fn)
        if profile_seat == 0:
            fn_a = wrapped
        else:
            fn_b = wrapped

    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps}, debug=debug)
    env.run([fn_a, fn_b])
    env_json = env.toJSON()

    rewards = tuple(env_json["rewards"])
    statuses = tuple(env_json["statuses"])
    winner = 0 if rewards[0] > rewards[1] else (1 if rewards[1] > rewards[0] else None)

    replay_path = None
    if record:
        out_dir = Path(run_dir) if run_dir is not None else Path("runs") / "adhoc"
        out_dir.mkdir(parents=True, exist_ok=True)
        replay_path = out_dir / f"seed{seed}_{_agent_name(agent_a)}_vs_{_agent_name(agent_b)}.json"
        replay_path.write_text(json.dumps(env_json))

    metrics = {0: extract_metrics(env_json, 0), 1: extract_metrics(env_json, 1)}

    return PlayResult(
        seed=seed,
        agents=(_agent_name(agent_a), _agent_name(agent_b)),
        rewards=rewards,
        winner=winner,
        statuses=statuses,
        replay_path=replay_path,
        turn_times=turn_times,
        metrics=metrics,
    )
