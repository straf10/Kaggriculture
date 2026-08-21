"""Local Bradley-Terry ladder — rank an agent against a graded bench, in the ladder's currency.

Why this exists (ROADMAP R22, §4.3 S6 step 3). Kaggriculture's final standings are a
**Bradley-Terry tournament** over post-deadline episodes (§1), and until now this repo has
never computed BT locally. Every gate scored `median_bank` → W/L → `mean_diff` (§2.1.4),
which are the right *acceptance* numbers but say nothing about *who* was beaten: a win over
`meta_route` and a win over a do-nothing baseline are the same row in `results.json`. That is
a large part of why §1's central puzzle — measured local wins converting to ~nothing on the
ladder — stayed open for five weeks.

BT fits each agent a latent strength from the identity of the opponents it beat, so a win
against a strong agent counts for more. Reported on an Elo-like scale (400 points per 10×
strength, mean anchored at 1500) because those are the numbers the competition reports.

This does **not** replace §2.1.4's three numbers. It sits beside them, and it is the one that
is comparable to the thing we are judged on.

Two disciplines from §2 are structural here, not optional:

* **Both seats, always** (§2.1.1). Every pairing is played from both seat orders on every
  seed, and the per-seat records are reported separately as well as pooled — an agent that
  wins from seat 0 and loses from seat 1 has a market-ordering dependency, not a strength.
* **Retain earlier meta generations** (§2). The bench is a *graded* list the caller supplies,
  and `--round-robin` also plays the bench against itself so BT has a connected comparison
  graph. Without it the bench agents are only ever seen through the challenger, and BT cannot
  place either.

⚠️ **The town is a confounder** (§4.1b / R21). A fixed seed fixes the shop draw, and realised
premium price moves 5-18× with it. `--shop-draw` reports the drain distribution actually
sampled, so a suspiciously clean result can be checked against the towns that produced it.
"""
from __future__ import annotations

import gzip
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from harness.play import play

# Products whose realised price §4.1b showed to be town-determined; reported by --shop-draw.
PREMIUM = ("STRAWBERRY", "WOOL", "MILK")


@dataclass
class Duel:
    """A seat-swapped series between two agents, from `agent_a`'s perspective."""
    agent_a: str
    agent_b: str
    seeds: tuple
    wins_a: int = 0
    wins_b: int = 0
    ties: int = 0
    errors: int = 0
    margins: list = field(default_factory=list)
    # Per-seat splits: how the series went with agent_a in seat 0 vs seat 1.
    wins_a_by_seat: dict = field(default_factory=lambda: {0: 0, 1: 0})
    games_by_seat: dict = field(default_factory=lambda: {0: 0, 1: 0})

    @property
    def games(self) -> int:
        return self.wins_a + self.wins_b + self.ties

    @property
    def mean_margin_a(self) -> float:
        return statistics.fmean(self.margins) if self.margins else 0.0

    def row(self) -> dict:
        return {
            "agent_a": self.agent_a, "agent_b": self.agent_b,
            "wins_a": self.wins_a, "wins_b": self.wins_b, "ties": self.ties,
            "errors": self.errors, "games": self.games,
            "mean_margin_a": self.mean_margin_a,
            "wins_a_seat0": self.wins_a_by_seat[0], "games_seat0": self.games_by_seat[0],
            "wins_a_seat1": self.wins_a_by_seat[1], "games_seat1": self.games_by_seat[1],
        }


def bradley_terry(rows, *, iterations: int = 10_000, tol: float = 1e-10,
                  prior: float = 0.5) -> dict:
    """Fit BT strengths by MM iteration (Hunter 2004), returning {agent: strength}.

    `prior` adds half a phantom win each way against an average opponent, which keeps an
    undefeated (or winless) agent from running off to infinity — the common case here, since
    a graded bench is *designed* to contain agents the challenger sweeps.

    A tie counts as half a win to each side, which is the standard BT treatment and matches
    how the competition's own scoring handles a draw.
    """
    wins: dict = defaultdict(float)          # total (weighted) wins per agent
    played: dict = defaultdict(lambda: defaultdict(float))   # games between each pair
    agents: set = set()
    for r in rows:
        a, b = r["agent_a"], r["agent_b"]
        agents.update((a, b))
        wa = r["wins_a"] + 0.5 * r["ties"]
        wb = r["wins_b"] + 0.5 * r["ties"]
        n = wa + wb
        wins[a] += wa
        wins[b] += wb
        played[a][b] += n
        played[b][a] += n
    if not agents:
        return {}

    strength = {a: 1.0 for a in agents}
    for _ in range(iterations):
        new = {}
        for a in agents:
            # MM update: w_a / sum_b n_ab / (p_a + p_b), with the prior as a phantom
            # opponent of strength 1 contributing `prior` games and `prior/2` wins.
            denom = prior / (strength[a] + 1.0)
            for b, n in played[a].items():
                denom += n / (strength[a] + strength[b])
            new[a] = (wins[a] + prior / 2.0) / denom if denom > 0 else strength[a]
        # Renormalise to a fixed geometric mean so the iteration cannot drift as a whole.
        gm = math.exp(statistics.fmean(math.log(max(v, 1e-300)) for v in new.values()))
        new = {a: v / gm for a, v in new.items()}
        delta = max(abs(new[a] - strength[a]) for a in agents)
        strength = new
        if delta < tol:
            break
    return strength


def to_elo(strength: dict, *, anchor: float = 1500.0, scale: float = 400.0,
           anchor_agent: str | None = "starter") -> dict:
    """Strengths → an Elo-like scale: `scale` points per 10× strength, anchored at `anchor`.

    When `anchor_agent` names an agent present in `strength`, that agent is pinned to `anchor`
    so ratings are comparable across runs with different bench compositions. Falls back to
    mean-anchoring when the agent is absent.
    """
    if not strength:
        return {}
    raw = {a: scale * math.log10(max(s, 1e-300)) for a, s in strength.items()}
    if anchor_agent and anchor_agent in raw:
        shift = anchor - raw[anchor_agent]
    else:
        shift = anchor - statistics.fmean(raw.values())
    return {a: v + shift for a, v in raw.items()}


def _read_town(replay_path) -> list:
    if replay_path is None:
        return []
    path = Path(replay_path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        replay = json.load(fh)
    return list(replay["steps"][-1][0]["observation"]["town"].get("unlocked_shops") or ())


def duel(name_a, agent_a, name_b, agent_b, seeds, *, steps=None,
         shop_draw: bool = False, run_dir=None, towns: list | None = None) -> Duel:
    """Seat-swapped series. `agent_a` plays every seed from BOTH seats (§2.1.1)."""
    duel_dir = (Path(run_dir) / f"{name_a}_vs_{name_b}") if run_dir is not None else None
    out = Duel(agent_a=name_a, agent_b=name_b, seeds=tuple(seeds))
    for seed in seeds:
        for seat_a in (0, 1):
            pair = (agent_a, agent_b) if seat_a == 0 else (agent_b, agent_a)
            result = play(*pair, seed=seed, steps=steps,
                          record=shop_draw, metrics=False, strict=False,
                          run_dir=duel_dir)
            if not result.clean or any(r is None for r in result.rewards):
                out.errors += 1
                continue
            mine = result.rewards[seat_a]
            theirs = result.rewards[1 - seat_a]
            out.margins.append(mine - theirs)
            out.games_by_seat[seat_a] += 1
            if mine > theirs:
                out.wins_a += 1
                out.wins_a_by_seat[seat_a] += 1
            elif theirs > mine:
                out.wins_b += 1
            else:
                out.ties += 1
            if shop_draw and towns is not None:
                towns.append(_read_town(result.replay_path))
    return out


def shop_draw_summary(towns: list) -> dict:
    """R21 — what shop draws did this seed set actually sample? (§4.1b)"""
    from analysis.v1v_shop_demand import units_per_tick
    out = {"episodes": len(towns), "products": {}}
    for product in PREMIUM:
        drains = [units_per_tick(t).get(product, 0) for t in towns]
        if not drains:
            continue
        out["products"][product] = {
            "median": statistics.median(drains),
            "min": min(drains),
            "max": max(drains),
            "zero_drain_episodes": sum(1 for d in drains if d == 0),
        }
    return out


def run_ladder(challenger, bench, seeds, *, challenger_name="challenger", steps=None,
               round_robin: bool = False, shop_draw: bool = False, run_dir=None) -> dict:
    """Play `challenger` against every agent in `bench` (a dict of name → agent spec).

    `round_robin=True` also plays the bench against itself. That is slower and it is what
    makes the BT fit trustworthy: without it every bench agent is connected to the graph only
    through the challenger, so their relative strengths are inferred from one shared opponent.
    """
    rows, towns = [], []
    for name, agent in bench.items():
        rows.append(duel(challenger_name, challenger, name, agent, seeds,
                         steps=steps, shop_draw=shop_draw, run_dir=run_dir,
                         towns=towns).row())
    if round_robin:
        names = list(bench)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                rows.append(duel(a, bench[a], b, bench[b], seeds,
                                 steps=steps, shop_draw=shop_draw, run_dir=run_dir,
                                 towns=towns).row())

    strength = bradley_terry(rows)
    elo = to_elo(strength)
    record: dict = defaultdict(lambda: [0, 0, 0])
    margins: dict = defaultdict(list)
    for r in rows:
        record[r["agent_a"]][0] += r["wins_a"]
        record[r["agent_a"]][1] += r["wins_b"]
        record[r["agent_a"]][2] += r["ties"]
        record[r["agent_b"]][0] += r["wins_b"]
        record[r["agent_b"]][1] += r["wins_a"]
        record[r["agent_b"]][2] += r["ties"]
        margins[r["agent_a"]].append(r["mean_margin_a"])
        margins[r["agent_b"]].append(-r["mean_margin_a"])

    standings = []
    for name in sorted(elo, key=lambda n: -elo[n]):
        w, l, t = record[name]
        standings.append({
            "agent": name,
            "bt_rating": round(elo[name]),
            "wins": w, "losses": l, "ties": t,
            "win_pct": 100.0 * (w + 0.5 * t) / (w + l + t) if (w + l + t) else 0.0,
            "mean_margin": statistics.fmean(margins[name]) if margins[name] else 0.0,
        })
    out = {
        "challenger": challenger_name,
        "seeds": list(seeds),
        "round_robin": round_robin,
        "pairings": rows,
        "standings": standings,
        "errors": sum(r["errors"] for r in rows),
    }
    if shop_draw:
        out["shop_draw"] = shop_draw_summary(towns)
    return out


def format_ladder(result: dict) -> str:
    lines = []
    ch = result["challenger"]
    lines.append(f"{ch} vs the bench   ({len(result['seeds'])} seeds x 2 seats "
                 f"= {2 * len(result['seeds'])} games/pairing)")
    lines.append("-" * 78)
    for r in result["pairings"]:
        if r["agent_a"] != ch:
            continue
        verdict = ("WIN " if r["wins_a"] > r["wins_b"]
                   else "LOSS" if r["wins_b"] > r["wins_a"] else "TIE ")
        lines.append(f"  {verdict} vs {r['agent_b']:<24}{r['wins_a']}-{r['wins_b']}"
                     f"   margin {r['mean_margin_a']:+,.0f}"
                     f"   (seat0 {r['wins_a_seat0']}/{r['games_seat0']},"
                     f" seat1 {r['wins_a_seat1']}/{r['games_seat1']})")
    lines.append("")
    lines.append(f"{'#':>3}  {'agent':<28}{'BT':>7}{'record':>14}{'win%':>8}{'mean margin':>14}")
    lines.append("-" * 78)
    for i, s in enumerate(result["standings"], 1):
        rec = f"{s['wins']}-{s['losses']}-{s['ties']}"
        lines.append(f"{i:>3}  {s['agent']:<28}{s['bt_rating']:>7}{rec:>14}"
                     f"{s['win_pct']:>7.1f}%{s['mean_margin']:>14,.0f}")
    if not result["round_robin"]:
        lines.append("")
        lines.append("  note: --round-robin not set, so the bench is connected to the graph only")
        lines.append("        through the challenger; bench BT ratings are weakly identified.")
    if result.get("shop_draw"):
        sd = result["shop_draw"]
        lines.append("")
        lines.append(f"shop draw actually sampled over {sd['episodes']} episodes "
                     f"(R21 — realised premium price moves 5-18x with this):")
        for product, e in sd["products"].items():
            lines.append(f"  {product:<12}median {e['median']:>4.1f} u/tick  "
                         f"range {e['min']}-{e['max']}  "
                         f"zero-drain episodes {e['zero_drain_episodes']}/{sd['episodes']}")
    if result["errors"]:
        lines.append(f"\n  ⚠️  {result['errors']} episode(s) errored and were dropped.")
    return "\n".join(lines)
