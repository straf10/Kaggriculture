"""play(): run one kaggriculture episode with recording and optional per-turn timing.

plan.md §2.4. Uses the installed kaggle-environments package's public `make`/`env.run` API
(Υ2) — the same entrypoint the Kaggle server uses, so a passing local `play()` is a faithful
stand-in for a real episode.

Agent specs (callables, built-in names, .py paths) are handed to `env.run()` unresolved
whenever possible, so kaggle_environments' own agent loader (`build_agent`/`get_last_callable`)
does the resolution — lazily, on the first turn, exactly like the Kaggle server does. This
keeps local profiling honest (import cost lands on turn 1, not before the timer starts —
review.md H3) and guarantees the harness never becomes more lenient than the server about
which callable in a file gets picked (review.md C2).
"""
import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture.kaggriculture import agents as BUILTIN_AGENTS

from harness.metrics import extract_metrics

AgentSpec = Union[Callable, str]


@dataclass
class PlayResult:
    seed: int
    agents: tuple  # (name_seat0, name_seat1)
    rewards: tuple  # final bank per seat
    winner: Optional[int]  # 0, 1, or None for a tie
    statuses: tuple  # final (framework-overwritten) statuses — see `health` for the real picture
    episode_steps: int  # actual episodeSteps the episode ran with (env default if steps=None)
    replay_path: Optional[Path]
    turn_times: Optional[list]  # per-turn seconds for `profile_seat`, from env.logs duration
    metrics: dict = field(default_factory=dict)
    health: dict = field(default_factory=dict)  # {seat: [statuses seen other than ACTIVE/DONE]}
    agent_errors: list = field(default_factory=list)  # [{seat, step, stderr}]
    clean: bool = True  # False if any seat ever hit ERROR/TIMEOUT/INVALID or printed to stderr


def _agent_name(agent_spec: AgentSpec) -> str:
    if isinstance(agent_spec, str):
        return agent_spec
    return getattr(agent_spec, "__name__", repr(agent_spec))


def _sanitize_filename_part(name: str) -> str:
    stem = Path(name).stem if any(c in name for c in "/\\") else name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    return cleaned or "agent"


def resolve_agent(agent_spec: AgentSpec, *, entrypoint: Optional[str] = None) -> Callable:
    """callable -> itself; built-in name ("pass"/"random"/"starter") -> its function;
    a path to a .py file -> the last callable defined in that file (same loading
    convention kaggle_environments itself uses for file-based agents).

    This eagerly execs the file, so prefer letting `play()` hand path/name specs
    straight to `env.run()` for the lazy, server-matching path — use this only when
    you need the resolved callable directly (CLI profiling, guard tests).

    `entrypoint`, if given, is a name that must resolve to the *same* callable as the
    server's own last-callable selection; if a module defines that name but it isn't
    the last callable, this raises instead of silently picking a different function
    than the server would (review.md C2) — the harness must never be more forgiving
    of loader order than production.
    """
    if callable(agent_spec):
        return agent_spec
    if isinstance(agent_spec, str):
        if agent_spec in BUILTIN_AGENTS:
            return BUILTIN_AGENTS[agent_spec]
        path = Path(agent_spec)
        if path.suffix == ".py" and path.exists():
            source = path.read_text(encoding="utf-8")
            if entrypoint is None:
                return get_last_callable(source, path=str(path))
            # Exec exactly once (not via get_last_callable + a second exec): each exec() call
            # produces distinct function objects, so comparing across two execs would always
            # fail identity even for an unmodified file. Replicate get_last_callable's own
            # "last callable in namespace" selection here so the comparison is meaningful.
            env = {}
            exec(compile(source, str(path), "exec"), env)  # noqa: S102 - trusted local agent file
            callables = [v for v in env.values() if callable(v)]
            last = callables[-1] if callables else None
            named = env.get(entrypoint)
            if named is not last:
                raise ValueError(
                    f"{path}: the last callable defined in the module is {last!r}, not the "
                    f"{entrypoint!r} entrypoint ({named!r}). The Kaggle server would load the "
                    f"former — fix the file so its final statement defines/imports `{entrypoint}`."
                )
            return named
    raise ValueError(f"Unrecognized agent spec: {agent_spec!r}")


def _turn_durations(env, seat: int) -> list:
    """Per-turn wall time for `seat`, read from env.logs (what the framework itself timed —
    this includes first-turn import/exec cost for lazily-loaded path agents, unlike a
    wrapper applied before env.run() starts). Not present in env.toJSON()."""
    out = []
    for log in env.logs:
        if seat < len(log) and log[seat] and "duration" in log[seat]:
            out.append(log[seat]["duration"])
    return out


def _agent_errors(env) -> list:
    """[{seat, step, stderr}] for every turn where the agent printed to stderr (crash
    tracebacks land here). env.toJSON() does not include this — it's the only place a
    silent ERROR/TIMEOUT/INVALID status leaves a trace (review.md C1)."""
    errors = []
    for step, log in enumerate(env.logs):
        for seat in (0, 1):
            if seat < len(log) and log[seat] and "duration" in log[seat] and log[seat].get("stderr"):
                errors.append({"seat": seat, "step": step, "stderr": log[seat]["stderr"][:2000]})
    return errors


def play(agent_a, agent_b, seed: int, *,
         steps: Optional[int] = None,
         record: bool = True, run_dir: Optional[Path] = None,
         profile_seat: Optional[int] = None,
         debug: bool = False,
         strict: bool = True,
         metrics: bool = True) -> PlayResult:
    """Run one episode: agent_a as seat 0, agent_b as seat 1.

    agent_* = callable(obs)->action | "main.py"-style path | built-in name ("pass"/"random"/"starter").
    steps=None uses the engine's own episodeSteps default (currently 720) instead of hardcoding
    it, so a future engine bump is visible locally instead of silently diverging (review.md M9).
    record=True writes a gzip-compressed env.toJSON() to run_dir (default runs/adhoc/).
    profile_seat selects which seat's per-turn durations (from env.logs) populate turn_times.
    strict=True (default) raises RuntimeError if either seat ever left ACTIVE/DONE status or
    printed to stderr — a crashing/timing-out/invalid agent must never silently produce a
    number that looks like a valid result (review.md C1). Pass strict=False to inspect
    `clean`/`health`/`agent_errors` on the result instead of raising.
    metrics=False skips extract_metrics() (two full 720-float bank curves per seat) — use it
    for bulk runs like compare() that only need `rewards` (review.md L5).
    """
    configuration = {"seed": seed}
    if steps is not None:
        configuration["episodeSteps"] = steps

    env = make("kaggriculture", configuration=configuration, debug=debug)
    env.run([agent_a, agent_b])
    env_json = env.toJSON()

    rewards = tuple(env_json["rewards"])
    statuses = tuple(env_json["statuses"])
    winner = 0 if rewards[0] > rewards[1] else (1 if rewards[1] > rewards[0] else None)
    episode_steps = env_json["configuration"]["episodeSteps"]

    per_step_status = [[s["status"] for s in step] for step in env_json["steps"]]
    health = {
        seat: sorted({st for st in (row[seat] for row in per_step_status)} - {"ACTIVE", "DONE"})
        for seat in (0, 1)
    }
    agent_errors = _agent_errors(env)
    clean = not health[0] and not health[1] and not agent_errors

    if strict and not clean:
        raise RuntimeError(
            f"play(): agent(s) not clean (seed={seed}) — health={health}, "
            f"first_error={agent_errors[0] if agent_errors else None}"
        )

    turn_times = _turn_durations(env, profile_seat) if profile_seat is not None else None

    replay_path = None
    if record:
        out_dir = Path(run_dir) if run_dir is not None else Path("runs") / "adhoc"
        out_dir.mkdir(parents=True, exist_ok=True)
        name_a = _sanitize_filename_part(_agent_name(agent_a))
        name_b = _sanitize_filename_part(_agent_name(agent_b))
        replay_path = out_dir / f"seed{seed}_seat0-{name_a}_seat1-{name_b}.json.gz"
        with gzip.open(replay_path, "wt", encoding="utf-8") as f:
            json.dump(env_json, f)

    computed_metrics = {0: extract_metrics(env_json, 0), 1: extract_metrics(env_json, 1)} if metrics else {}

    return PlayResult(
        seed=seed,
        agents=(_agent_name(agent_a), _agent_name(agent_b)),
        rewards=rewards,
        winner=winner,
        statuses=statuses,
        episode_steps=episode_steps,
        replay_path=replay_path,
        turn_times=turn_times,
        metrics=computed_metrics,
        health=health,
        agent_errors=agent_errors,
        clean=clean,
    )
