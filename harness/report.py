"""harness/report.py (plan.md §1.5.4): turn one recorded replay (+ optional G11 receipts)
into a single self-contained, offline HTML report — no CDN, no external files. On an engine
that never raises (review.md H4), this is what turns "we lost $8k" into "the WATER at (7,2)
on step 341 didn't do what we expected": bank curves for both seats, per-day loss/utilization
breakdowns, a per-unit action timeline (the only thing that would have shown last session's
task-assignment oscillation immediately), a farm-state heatmap by day, sell-price-vs-base, and
an explicit loss-event table naming the exact day/step/tile of every water_weeds_lost /
plant_decay_units_lost occurrence (the acceptance criterion is pinpointing the cause visually
in under two minutes — an aggregate count alone can't do that).
"""
import gzip
import json
from pathlib import Path
from typing import Optional

from kaggle_environments.envs.kaggriculture import kaggriculture as engine

from harness.metrics import extract_metrics

_ACTION_COLORS = {
    "WATER": "#3b82f6", "PLANT": "#22c55e", "HARVEST": "#f59e0b", "DROP": "#a855f7",
    "NORTH": "#cbd5e1", "SOUTH": "#cbd5e1", "EAST": "#cbd5e1", "WEST": "#cbd5e1",
    "PASS": "#f1f5f9", None: "#ffffff",
}
_TILE_COLORS = {
    "EMPTY": "#f8fafc", "LOCKED": "#334155", "WEED": "#dc2626",
    "PLANT": "#16a34a", "COOP": "#0891b2", "PASTURE": "#a16207", "ANIMAL": "#f59e0b",
}


def load_replay(path) -> dict:
    """Accepts the harness's own `.json.gz` replay format or a plain `.json` file."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def load_receipts(path) -> Optional[list]:
    """None (not []) when the file is missing — mirrors extract_metrics()'s own
    None-means-unmeasured convention for unexplained_noops."""
    path = Path(path)
    if not path.exists():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _tile_code(tile) -> str:
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, dict):
        if "animal" in tile:
            return "ANIMAL"
        return tile.get("kind", "EMPTY")
    return "EMPTY"


def _unit_action_kind(action) -> Optional[str]:
    if not isinstance(action, list) or not action:
        return "PASS"
    return action[0]


def _build_timeline(env_json: dict, seat: int) -> dict:
    """One row per unit (0=farmer, 1+=hands), one column per step, action opcode per cell —
    the only view that would have shown last session's task-assignment oscillation at a
    glance instead of requiring a guessing game over aggregate metrics."""
    steps = env_json["steps"]
    max_units = 1
    for step in steps:
        action = step[seat].get("action")
        if isinstance(action, dict):
            max_units = max(max_units, 1 + len(action.get("hands") or []))
    grid = [[] for _ in range(max_units)]
    for step in steps:
        action = step[seat].get("action")
        action = action if isinstance(action, dict) else {}
        unit_actions = [action.get("farmer", ["PASS"]), *(action.get("hands") or [])]
        for unit_index in range(max_units):
            kind = (
                _unit_action_kind(unit_actions[unit_index])
                if unit_index < len(unit_actions) else None
            )
            grid[unit_index].append(kind)
    return {"units": max_units, "grid": grid}


def _build_heatmaps(env_json: dict, seat: int) -> list:
    """One tile-kind grid per day, sampled at that day's first recorded step (mid-day tile
    edits between waterings are not the point of a day-granularity overview)."""
    heatmaps = []
    seen_days = set()
    for step in env_json["steps"]:
        observation = step[seat]["observation"]
        day = int(observation.get("day", 0))
        if day in seen_days:
            continue
        seen_days.add(day)
        tiles = observation["farms"][seat]["tiles"]
        heatmaps.append({"day": day, "grid": [[_tile_code(tile) for tile in row] for row in tiles]})
    return heatmaps


def _sell_price_table(metrics: dict) -> list:
    rows = []
    for item, avg_price in sorted(metrics["average_sell_price"].items()):
        base = engine.MARKET_PARAMS.get(item, {}).get("base")
        rows.append({
            "item": item,
            "avg_price": round(avg_price, 2),
            "base_price": base,
            "delta_pct": round((avg_price - base) / base * 100.0, 1) if base else None,
        })
    return rows


def build_report_data(env_json: dict, *, seat: int = 0, diagnostics: Optional[list] = None) -> dict:
    """Assembles every series the HTML template needs, from `seat`'s point of view (the agent
    under test) — `opponent_metrics` is included only for the bank-curve comparison."""
    opponent = 1 - seat
    metrics_seat = extract_metrics(env_json, seat, diagnostics=diagnostics)
    metrics_opp = extract_metrics(env_json, opponent, diagnostics=diagnostics)
    return {
        "seat": seat,
        "agents": env_json.get("info", {}).get("TeamNames") or [f"seat{seat}", f"seat{opponent}"],
        "metrics": metrics_seat,
        "opponent_metrics": metrics_opp,
        "timeline": _build_timeline(env_json, seat),
        "heatmaps": _build_heatmaps(env_json, seat),
        "sell_prices": _sell_price_table(metrics_seat),
    }


def _embed_json(data) -> str:
    """Safe to place inside a <script> block — `</script>` inside the JSON string can't
    prematurely close the tag."""
    return json.dumps(data).replace("</", "<\\/")


_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>kaggriculture episode report</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #e2e8f0; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 28px 0 8px; color: #93c5fd; }}
  .sub {{ color: #94a3b8; font-size: 13px; margin-bottom: 20px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .row .card {{ flex: 1; min-width: 280px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ text-align: left; padding: 4px 10px; border-bottom: 1px solid #334155; }}
  th {{ color: #93c5fd; font-weight: 600; }}
  .scroll-x {{ overflow-x: auto; max-width: 100%; }}
  .timeline-row {{ display: flex; align-items: center; margin-bottom: 2px; }}
  .timeline-label {{ width: 60px; font-size: 12px; color: #94a3b8; flex-shrink: 0; }}
  .timeline-cell {{ width: 3px; height: 16px; flex-shrink: 0; }}
  .legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; margin-top: 8px; color: #cbd5e1; }}
  .swatch {{ display: inline-block; width: 10px; height: 10px; margin-right: 4px; vertical-align: middle; border-radius: 2px; }}
  .heatmap-grid {{ display: grid; gap: 1px; background: #0f172a; }}
  .heatmap-cell {{ width: 14px; height: 14px; }}
  input[type=range] {{ width: 100%; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }}
  .badge.ok {{ background: #14532d; color: #86efac; }}
  .badge.bad {{ background: #7f1d1d; color: #fca5a5; }}
  .badge.na {{ background: #334155; color: #94a3b8; }}
  canvas {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>kaggriculture episode report</h1>
<div class="sub" id="subtitle"></div>

<div class="card">
  <h2 style="margin-top:0">Bank curve</h2>
  <canvas id="bankCanvas" width="900" height="240"></canvas>
</div>

<div class="row">
  <div class="card">
    <h2 style="margin-top:0">Daily losses</h2>
    <canvas id="lossCanvas" width="440" height="220"></canvas>
  </div>
  <div class="card">
    <h2 style="margin-top:0">Worker-turn utilization per day</h2>
    <canvas id="utilCanvas" width="440" height="220"></canvas>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0">Per-unit action timeline (seat under test)</h2>
  <div class="scroll-x" id="timelineContainer"></div>
  <div class="legend" id="timelineLegend"></div>
</div>

<div class="card">
  <h2 style="margin-top:0">Farm-state heatmap</h2>
  <input type="range" id="daySlider" min="0" value="0">
  <div class="sub" id="dayLabel"></div>
  <div class="heatmap-grid" id="heatmapGrid"></div>
  <div class="legend" id="heatmapLegend"></div>
</div>

<div class="row">
  <div class="card">
    <h2 style="margin-top:0">Sell price vs base</h2>
    <table id="sellTable"><thead><tr><th>Item</th><th>Avg sell</th><th>Base</th><th>Δ%</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="card">
    <h2 style="margin-top:0">G11 receipts</h2>
    <div id="noopsSummary"></div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0">Loss events (exact day / step / tile)</h2>
  <div class="scroll-x">
    <table id="lossTable"><thead><tr><th>Type</th><th>Day</th><th>Step</th><th>Tile (x,y)</th><th>Units</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<script>
const DATA = __DATA__;

function el(tag, attrs) {{
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}}

document.getElementById("subtitle").textContent =
  `seat ${{DATA.seat}} (${{DATA.agents[DATA.seat] || "?"}}) vs seat ${{1 - DATA.seat}} `
  + `(${{DATA.agents[1 - DATA.seat] || "?"}}) — outcome: ${{DATA.metrics.outcome}}, `
  + `final bank $${{DATA.metrics.final_bank.toFixed(0)}} vs $${{DATA.metrics.opponent_final_bank.toFixed(0)}}`;

// ---- bank curve ----
(function drawBank() {{
  const canvas = document.getElementById("bankCanvas");
  const ctx = canvas.getContext("2d");
  const a = DATA.metrics.bank_curve, b = DATA.metrics.opponent_bank_curve;
  const maxY = Math.max(...a, ...b, 1);
  const w = canvas.width, h = canvas.height, pad = 10;
  function plot(series, color) {{
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    series.forEach((v, i) => {{
      const x = pad + (i / (series.length - 1 || 1)) * (w - 2 * pad);
      const y = h - pad - (v / maxY) * (h - 2 * pad);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}
  plot(a, "#3b82f6");
  plot(b, "#f59e0b");
  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px sans-serif";
  ctx.fillText("seat " + DATA.seat, pad, 14);
  ctx.fillStyle = "#3b82f6";
  ctx.fillRect(pad + 60, 6, 10, 10);
  ctx.fillStyle = "#94a3b8";
  ctx.fillText("opponent", pad + 140, 14);
  ctx.fillStyle = "#f59e0b";
  ctx.fillRect(pad + 200, 6, 10, 10);
}})();

// ---- daily losses (stacked bar) ----
(function drawLoss() {{
  const canvas = document.getElementById("lossCanvas");
  const ctx = canvas.getContext("2d");
  const daily = DATA.metrics.daily;
  const w = canvas.width, h = canvas.height, pad = 24;
  const maxV = Math.max(1, ...daily.map(d => d.water_weeds_lost + d.plant_decay_units_lost));
  const bw = (w - 2 * pad) / Math.max(1, daily.length);
  daily.forEach((d, i) => {{
    const x = pad + i * bw;
    const wwl = (d.water_weeds_lost / maxV) * (h - 2 * pad);
    const pdl = (d.plant_decay_units_lost / maxV) * (h - 2 * pad);
    ctx.fillStyle = "#dc2626";
    ctx.fillRect(x, h - pad - wwl, Math.max(1, bw - 1), wwl);
    ctx.fillStyle = "#a855f7";
    ctx.fillRect(x, h - pad - wwl - pdl, Math.max(1, bw - 1), pdl);
  }});
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px sans-serif";
  ctx.fillText("red=water_weeds_lost  purple=plant_decay_units_lost (per day)", pad, 14);
}})();

// ---- worker utilization (stacked bar) ----
(function drawUtil() {{
  const canvas = document.getElementById("utilCanvas");
  const ctx = canvas.getContext("2d");
  const daily = DATA.metrics.daily;
  const w = canvas.width, h = canvas.height, pad = 24;
  const bw = (w - 2 * pad) / Math.max(1, daily.length);
  daily.forEach((d, i) => {{
    const total = Math.max(1, d.worker_turns_moving + d.worker_turns_working + d.worker_turns_idle);
    const x = pad + i * bw;
    let y = h - pad;
    [["worker_turns_working", "#22c55e"], ["worker_turns_moving", "#3b82f6"], ["worker_turns_idle", "#475569"]]
      .forEach(([key, color]) => {{
        const seg = (d[key] / total) * (h - 2 * pad);
        ctx.fillStyle = color;
        ctx.fillRect(x, y - seg, Math.max(1, bw - 1), seg);
        y -= seg;
      }});
  }});
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px sans-serif";
  ctx.fillText("green=working  blue=moving  gray=idle (share of turns per day)", pad, 14);
}})();

// ---- per-unit action timeline ----
(function drawTimeline() {{
  const container = document.getElementById("timelineContainer");
  const colors = {json_action_colors};
  DATA.timeline.grid.forEach((row, unitIndex) => {{
    const rowDiv = el("div", {{ class: "timeline-row" }});
    const label = el("div", {{ class: "timeline-label" }});
    label.textContent = unitIndex === 0 ? "farmer" : "hand " + unitIndex;
    rowDiv.appendChild(label);
    row.forEach(kind => {{
      const cell = el("div", {{ class: "timeline-cell" }});
      cell.style.background = colors[kind] || "#ffffff";
      cell.title = kind || "(no unit)";
      rowDiv.appendChild(cell);
    }});
    container.appendChild(rowDiv);
  }});
  const legend = document.getElementById("timelineLegend");
  Object.entries(colors).forEach(([kind, color]) => {{
    if (kind === "null" || kind === "undefined") return;
    const span = el("span");
    const sw = el("span", {{ class: "swatch" }});
    sw.style.background = color;
    span.appendChild(sw);
    span.appendChild(document.createTextNode(kind));
    legend.appendChild(span);
  }});
}})();

// ---- farm heatmap ----
(function drawHeatmap() {{
  const tileColors = {json_tile_colors};
  const slider = document.getElementById("daySlider");
  const grid = document.getElementById("heatmapGrid");
  const dayLabel = document.getElementById("dayLabel");
  slider.max = DATA.heatmaps.length - 1;
  function render(dayIndex) {{
    const day = DATA.heatmaps[dayIndex];
    dayLabel.textContent = "day " + day.day;
    grid.innerHTML = "";
    grid.style.gridTemplateColumns = `repeat(${{day.grid[0].length}}, 14px)`;
    day.grid.forEach(row => row.forEach(code => {{
      const cell = el("div", {{ class: "heatmap-cell" }});
      cell.style.background = tileColors[code] || "#f8fafc";
      cell.title = code;
      grid.appendChild(cell);
    }}));
  }}
  slider.addEventListener("input", () => render(parseInt(slider.value, 10)));
  render(0);
  const legend = document.getElementById("heatmapLegend");
  Object.entries(tileColors).forEach(([code, color]) => {{
    const span = el("span");
    const sw = el("span", {{ class: "swatch" }});
    sw.style.background = color;
    span.appendChild(sw);
    span.appendChild(document.createTextNode(code));
    legend.appendChild(span);
  }});
}})();

// ---- sell price table ----
(function fillSellTable() {{
  const tbody = document.querySelector("#sellTable tbody");
  DATA.sell_prices.forEach(row => {{
    const tr = el("tr");
    tr.innerHTML = `<td>${{row.item}}</td><td>$${{row.avg_price}}</td><td>$${{row.base_price ?? "?"}}</td>`
      + `<td>${{row.delta_pct === null ? "?" : row.delta_pct + "%"}}</td>`;
    tbody.appendChild(tr);
  }});
}})();

// ---- G11 unexplained_noops ----
(function fillNoops() {{
  const n = DATA.metrics.unexplained_noops;
  const div = document.getElementById("noopsSummary");
  if (n === null || n === undefined) {{
    div.innerHTML = '<span class="badge na">not measured</span> — record with '
      + '<code>KAGGRI_DEBUG=1</code> set for the agent process to enable receipts.';
  }} else if (n === 0) {{
    div.innerHTML = '<span class="badge ok">0 unexplained no-ops</span> — every scheduled '
      + 'WATER/PLANT/HARVEST reconciled against the observed tile.';
  }} else {{
    div.innerHTML = `<span class="badge bad">${{n}} unexplained no-op(s)</span> — a committed `
      + 'action did not produce the tile effect the scheduler expected.';
  }}
}})();

// ---- loss events ----
(function fillLossTable() {{
  const tbody = document.querySelector("#lossTable tbody");
  DATA.metrics.loss_events.forEach(ev => {{
    const tr = el("tr");
    tr.innerHTML = `<td>${{ev.type}}</td><td>${{ev.day}}</td><td>${{ev.step}}</td>`
      + `<td>(${{ev.pos[0]}}, ${{ev.pos[1]}})</td><td>${{ev.units ?? 1}}</td>`;
    tbody.appendChild(tr);
  }});
  if (DATA.metrics.loss_events.length === 0) {{
    const tr = el("tr");
    tr.innerHTML = '<td colspan="5" style="color:#94a3b8">none — zero water_weeds_lost / plant_decay_units_lost this episode</td>';
    tbody.appendChild(tr);
  }}
}})();
</script>
</body>
</html>
"""


def render_html(report_data: dict) -> str:
    html = _TEMPLATE.replace("__DATA__", _embed_json(report_data))
    html = html.replace("{json_action_colors}", _embed_json(_ACTION_COLORS))
    html = html.replace("{json_tile_colors}", _embed_json(_TILE_COLORS))
    return html


def write_report(env_json: dict, out_path, *, seat: int = 0,
                  diagnostics: Optional[list] = None) -> Path:
    data = build_report_data(env_json, seat=seat, diagnostics=diagnostics)
    out_path = Path(out_path)
    out_path.write_text(render_html(data), encoding="utf-8")
    return out_path
