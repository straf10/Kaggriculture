"""Resolution path for the MIT tier-0-5 reference agents (ROADMAP R25 / S6 step 2 A1).

The six authored reference agents (Rayk Kretzschmar, `kaggriculture-reference-agents`, MIT) are
fetched into the **gitignored** `harness/bench_agents/reference/` directory — MIT permits
redistribution but they are not ours to carry in this public repo (§4.5). This module is the
committed half: it names the graded ladder and resolves each tier to its local `.py` path *if
present*, so an S6 gate can ask for `tier2` / `Rotation Rosa` by name and get a file-loadable
bench spec, or discover that the local fetch is missing.

Carries no competition data — only the tier→filename map (public statistics, §2.8) and a
presence check. Tiers 6-9 are deliberately absent (their base85 `_TRACE` is outside the MIT
grant, R23); the CC BY-SA CSVs are never fetched (§4.5).
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent / "reference"

# tier -> (display name, filename). The authored tier-0-5 ladder, graded $3.000 -> $46.211
# (agents_manifest.csv, read as statistics). Every gap between adjacent tiers is one economic
# decision on a byte-identical scheduler (§4.5).
REFERENCE_TIERS = {
    0: ("Fallow Finn", "fallow_finn.py"),
    1: ("Wheat Walter", "wheat_walter.py"),
    2: ("Rotation Rosa", "rotation_rosa.py"),
    3: ("Homestead Hana", "homestead_hana.py"),
    4: ("Melon Mateo", "melon_mateo.py"),
    5: ("Rancher Rita", "rancher_rita.py"),
}

_BY_SLUG = {fn[:-3]: tier for tier, (_n, fn) in REFERENCE_TIERS.items()}
_BY_NAME = {name.lower(): tier for tier, (name, _fn) in REFERENCE_TIERS.items()}


def reference_agent_path(key) -> Path | None:
    """Resolve `key` (a tier int, a `tierN` string, a slug `rotation_rosa`, or a display name)
    to the local `.py` path, or None if the file is not present locally."""
    tier = None
    if isinstance(key, int):
        tier = key
    elif isinstance(key, str):
        k = key.strip().lower()
        if k.startswith("tier") and k[4:].isdigit():
            tier = int(k[4:])
        elif k in _BY_SLUG:
            tier = _BY_SLUG[k]
        elif k in _BY_NAME:
            tier = _BY_NAME[k]
    if tier is None or tier not in REFERENCE_TIERS:
        return None
    path = _DIR / REFERENCE_TIERS[tier][1]
    return path if path.exists() else None


def available_reference_agents() -> dict[str, Path]:
    """{`tierN_slug`: path} for every tier-0-5 agent present locally — the A1 bench, ready to
    hand to `harness.cli ladder --bench` or `run_ladder`. Empty when the fetch is absent."""
    out = {}
    for tier, (_name, fn) in REFERENCE_TIERS.items():
        path = _DIR / fn
        if path.exists():
            out[f"tier{tier}_{fn[:-3]}"] = path
    return out
