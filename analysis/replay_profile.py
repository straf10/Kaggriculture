#!/usr/bin/env python3
"""Gap analysis from top-decile ladder replays (MASTERPLAN §3.4).

Offline data work, deliberately separate from harness/ (not agent/benchmark code).

Replays are used ONLY as a target-curve / diagnostic reference: this script extracts
per-day AGGREGATE profiles (money, hands, tiles, animals, quadrants, sales) from the
top-decile teams' games. It never reads or stores per-unit action sequences, and
produces no policy, weights, or trajectory data — see MASTERPLAN §3.4 / Open #11.

`replays.parquet` (~337MB) is downloaded via kagglehub into the local cache and is
NEVER copied into the repo. Only the small aggregated `data/derived/top_agent_profiles.csv`
is committed.

Usage:
    python analysis/replay_profile.py
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import kagglehub
import pandas as pd
import pyarrow.parquet as pq

DATASET = "georgymamarin/kaggriculture-episodes"
MIN_GAMES = 8
TOP_DECILE = 0.10
TURNS_PER_DAY = 24
DAY_CHECKPOINTS = (10, 20, 30)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT_CSV = REPO / "data" / "derived" / "top_agent_profiles.csv"
OUT_MD = REPO / "data" / "derived" / "top_agent_profiles.md"

ANIMAL_STRUCTURES = ("COOP", "PASTURE")


def wilson_lower_bound(wins: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center - margin) / denom


def select_top_teams(episodes: pd.DataFrame) -> list[int]:
    """Cross-team EPISODE_TYPE_PUBLIC games only (validation = self-play, excluded per README)."""
    pub = episodes[
        (episodes["type"] == "EPISODE_TYPE_PUBLIC") & (episodes["team_0"] != episodes["team_1"])
    ]
    wins: dict = defaultdict(int)
    n: dict = defaultdict(int)
    for row in pub.itertuples():
        n[row.team_0] += 1
        n[row.team_1] += 1
        if row.bank_0 > row.bank_1:
            wins[row.team_0] += 1
        elif row.bank_1 > row.bank_0:
            wins[row.team_1] += 1

    qualified = [(t, wilson_lower_bound(wins[t], n[t])) for t in n if n[t] >= MIN_GAMES]
    qualified.sort(key=lambda x: -x[1])
    cutoff = max(1, int(len(qualified) * TOP_DECILE))
    return [t for t, _ in qualified[:cutoff]]


def select_episode_seats(episodes: pd.DataFrame, top_teams: set, have_replay: set) -> list[tuple]:
    """Return (episode_id, seat) pairs where `seat`'s team is a top-decile team."""
    pub = episodes[
        (episodes["type"] == "EPISODE_TYPE_PUBLIC")
        & (episodes["team_0"] != episodes["team_1"])
        & (episodes["episode_id"].isin(have_replay))
    ]
    pairs = []
    for row in pub.itertuples():
        if row.team_0 in top_teams:
            pairs.append((row.episode_id, 0))
        if row.team_1 in top_teams:
            pairs.append((row.episode_id, 1))
    return pairs


def _tile_counts(tiles):
    plants, animals = defaultdict(int), defaultdict(int)
    for row in tiles:
        for cell in row:
            if not isinstance(cell, dict):
                continue
            kind = cell.get("kind")
            if kind == "PLANT":
                plants[cell["crop"]] += 1
            elif kind in ANIMAL_STRUCTURES and "animal" in cell:
                animals[cell["animal"]] += 1
    return plants, animals


def extract_profile(replay: dict, seat: int) -> dict:
    """Per-day end-of-day snapshot for one seat, plus first-acquisition-day markers.

    Diagnostic extraction only: reads aggregate farm/market state per day, never the
    per-unit action stream (MASTERPLAN §3.4 — no trajectory data leaves this function).
    """
    steps = replay["steps"]
    n_days = len(steps) // TURNS_PER_DAY

    daily = []
    quadrants_seen = 0
    first_quadrant_day = {}
    first_animal_day = {}
    cum_sales = defaultdict(int)
    cum_sales_by_day = {}

    for day in range(n_days):
        t = min(day * TURNS_PER_DAY + (TURNS_PER_DAY - 1), len(steps) - 1)
        obs = steps[t][0]["observation"]
        farm = obs["farms"][seat]
        plants, animals = _tile_counts(farm["tiles"])

        quads = farm["unlocked_quadrants"]
        if len(quads) > quadrants_seen:
            for i in range(quadrants_seen, len(quads)):
                first_quadrant_day[i + 1] = day
            quadrants_seen = len(quads)

        for species in animals:
            if species not in first_animal_day:
                first_animal_day[species] = day

        for hour in range(day * TURNS_PER_DAY, min((day + 1) * TURNS_PER_DAY, len(steps))):
            action = steps[hour][seat].get("action") or {}
            for order in action.get("market") or []:
                if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                    cum_sales[order[1]] += order[2]
        cum_sales_by_day[day] = dict(cum_sales)

        daily.append({
            "day": day,
            "money": farm["money"],
            "hands": len(farm["hands"]),
            "tiles_planted": sum(plants.values()),
            "animals_total": sum(animals.values()),
            "unlocked_quadrants": len(quads),
            **{f"plants_{k.lower()}": v for k, v in plants.items()},
            **{f"animals_{k.lower()}": v for k, v in animals.items()},
        })

    return {
        "daily": daily,
        "first_quadrant_day": first_quadrant_day,
        "first_animal_day": first_animal_day,
        "final_cum_sales": dict(cum_sales),
    }


def build_profiles(limit_episodes: int | None = None) -> dict:
    path = Path(kagglehub.dataset_download(DATASET))
    episodes = pd.read_csv(path / "episodes.csv")
    top_teams = set(select_top_teams(episodes))
    print(f"top-decile teams (n>=8, Wilson LB): {len(top_teams)} -> {sorted(top_teams)}")

    parquet_path = path / "replays.parquet"
    pf = pq.ParquetFile(parquet_path)
    have_replay = set(pf.read(columns=["episode_id"]).to_pandas()["episode_id"].tolist())

    pairs = select_episode_seats(episodes, top_teams, have_replay)
    if limit_episodes is not None:
        pairs = pairs[:limit_episodes]
    wanted_eids = {eid for eid, _ in pairs}
    seats_by_eid: dict = defaultdict(list)
    for eid, seat in pairs:
        seats_by_eid[eid].append(seat)
    print(f"episodes with a top-team seat + replay available: {len(wanted_eids)} "
          f"({len(pairs)} (episode, seat) rows)")

    all_daily = []
    first_quadrant_days = defaultdict(list)
    first_animal_days = defaultdict(list)
    first_animal_any_days = []
    first_extra_quadrant_days = []
    bank_at_day = defaultdict(list)
    parsed = 0
    for batch in pf.iter_batches(batch_size=16, columns=["episode_id", "replay_json"]):
        tbl = batch.to_pydict()
        for eid, blob in zip(tbl["episode_id"], tbl["replay_json"]):
            if eid not in wanted_eids:
                continue
            replay = json.loads(blob)
            for seat in seats_by_eid[eid]:
                profile = extract_profile(replay, seat)
                for row in profile["daily"]:
                    all_daily.append({"episode_id": eid, "seat": seat, **row})
                for q, day in profile["first_quadrant_day"].items():
                    first_quadrant_days[q].append(day)
                for species, day in profile["first_animal_day"].items():
                    first_animal_days[species].append(day)
                if profile["first_animal_day"]:
                    first_animal_any_days.append(min(profile["first_animal_day"].values()))
                if 2 in profile["first_quadrant_day"]:
                    first_extra_quadrant_days.append(profile["first_quadrant_day"][2])
                money_by_day = {r["day"]: r["money"] for r in profile["daily"]}
                max_day = max(money_by_day) if money_by_day else None
                for target_day in DAY_CHECKPOINTS:
                    # a 30-day season has day indices 0..29 — day 30 has no row of its own,
                    # so it clamps to the last day played (matches how the v1b overlay's
                    # bank_curve index is clamped in write_markdown).
                    lookup_day = target_day if target_day in money_by_day else max_day
                    if lookup_day is not None:
                        bank_at_day[target_day].append(money_by_day[lookup_day])
            parsed += 1
            if parsed % 50 == 0:
                print(f"  parsed {parsed}/{len(wanted_eids)} target replays")

    return {
        "daily_rows": all_daily,
        "first_quadrant_days": first_quadrant_days,
        "first_animal_days": first_animal_days,
        "first_animal_any_days": first_animal_any_days,
        "first_extra_quadrant_days": first_extra_quadrant_days,
        "bank_at_day": bank_at_day,
        "n_episode_seats": len(pairs),
        "n_top_teams": len(top_teams),
    }


def aggregate_to_csv(result: dict, out_path: Path) -> pd.DataFrame:
    df = pd.DataFrame(result["daily_rows"])
    value_cols = [c for c in df.columns if c not in ("episode_id", "seat", "day")]
    df[value_cols] = df[value_cols].fillna(0)
    agg = df.groupby("day")[value_cols].median().reset_index()
    agg.insert(1, "n_episode_seats", df.groupby("day").size().values)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(out_path, index=False)
    return agg


def _median(xs):
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def write_markdown(result: dict, agg: pd.DataFrame, v1b_bank_curve: list[float] | None, out_path: Path):
    fq = result["first_quadrant_days"]
    fa = result["first_animal_days"]
    bd = result["bank_at_day"]

    lines = []
    lines.append("# Top-decile replay profile vs v1b\n")
    lines.append(
        f"Top-decile teams: **{result['n_top_teams']}** (winrate n>=8, Wilson lower bound, "
        f"top 10%). Extracted from **{result['n_episode_seats']}** (episode, seat) rows.\n"
    )
    lines.append(
        "> Replays used strictly as target curve / diagnostic (MASTERPLAN §3.4, Open #11). "
        "No trajectory copying, no BC/IL prior — only aggregate per-day state.\n"
    )

    lines.append("## (i) Quadrant acquisition day (median across top-decile episodes)\n")
    lines.append("| Quadrant # | median day | n episodes |")
    lines.append("|---|---|---|")
    for q in sorted(fq):
        lines.append(f"| {q} | {_median(fq[q])} | {len(fq[q])} |")
    lines.append("")

    lines.append("## (ii) Animal species acquired + median day\n")
    lines.append("| Species | median first day | n episodes (out of total) |")
    lines.append("|---|---|---|")
    for species in sorted(fa):
        lines.append(f"| {species} | {_median(fa[species])} | {len(fa[species])} / {result['n_episode_seats']} |")
    lines.append("")

    first_animal_any = _median(result["first_animal_any_days"])
    first_extra_quadrant = _median(result["first_extra_quadrant_days"])
    reversed_order = (
        first_animal_any is not None and first_extra_quadrant is not None
        and first_animal_any < first_extra_quadrant
    )
    lines.append("## Decision: land vs animals first\n")
    lines.append(
        f"Median day of 1st animal (any species): **{first_animal_any}** "
        f"(n={len(result['first_animal_any_days'])}). "
        f"Median day of 1st extra quadrant (beyond starting NW): **{first_extra_quadrant}** "
        f"(n={len(result['first_extra_quadrant_days'])})."
    )
    lines.append(
        f"\n**Decision ({'v1d -> v1c, animals before land' if reversed_order else 'v1c -> v1d, land before animals'})**: "
        f"top-decile teams get their first animal at day {first_animal_any}, "
        f"{'before' if reversed_order else 'after'} their first extra quadrant at day "
        f"{first_extra_quadrant} — per the §5.1 criterion, the order "
        f"{'reverses to v1d then v1c' if reversed_order else 'stays v1c then v1d'}.\n"
    )

    lines.append("## (iii) Bank at day 10/20/30 — top-decile median vs v1b\n")
    lines.append("| Day | top-decile median bank | v1b bank | gap |")
    lines.append("|---|---|---|---|")
    for day in DAY_CHECKPOINTS:
        top_median = _median(bd.get(day, []))
        v1b_val = None
        if v1b_bank_curve is not None:
            idx = min(day * TURNS_PER_DAY + (TURNS_PER_DAY - 1), len(v1b_bank_curve) - 1)
            v1b_val = v1b_bank_curve[idx]
        gap = None if (top_median is None or v1b_val is None) else round(top_median - v1b_val, 1)
        lines.append(f"| {day} | {top_median} | {v1b_val} | {gap} |")
    lines.append("")

    lines.append("## Full per-day median target curve\n")
    lines.append(f"See [top_agent_profiles.csv](top_agent_profiles.csv) ({len(agg)} day rows, "
                  f"{len(agg.columns)} columns: money/hands/tiles per crop/animals per species/"
                  f"unlocked_quadrants, median across all top-decile (episode, seat) rows for that day).\n")
    lines.append(
        "Each column is an **independent per-day median** across all 662 (episode, seat) rows — "
        "the row at a given day is not a single coherent episode's trajectory (e.g. "
        "`animals_total` need not equal the sum of the per-species columns for that same row). "
        "Use it as a target curve/diagnostic per column, not as a literal reference playthrough."
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = build_profiles()
    agg = aggregate_to_csv(result, OUT_CSV)
    print(f"wrote {OUT_CSV} ({len(agg)} rows)")

    v1b_bank_curve = None
    try:
        import sys
        sys.path.insert(0, str(REPO))
        from harness.play import play
        play_result = play("checkpoints/v1b/main.py", "pass", seed=0, record=False, metrics=True)
        v1b_bank_curve = play_result.metrics[0]["bank_curve"]
    except Exception as e:
        print(f"WARNING: could not obtain v1b bank curve for overlay: {e}")

    write_markdown(result, agg, v1b_bank_curve, OUT_MD)
    print(f"wrote {OUT_MD}")
