#!/usr/bin/env python
"""Notebook → markdown extractor for docs/meta/ snapshots.

The community notebooks in `notebooks/` carry numbers that exist nowhere else in the repo
(profit/tile-day, animal season totals, ladder distributions, per-crop win rates). Two of them —
`kaggriculture-daily-replays-the-live-meta-report` and `what-actually-wins-on-the-kaggriculture-
ladder` — **re-run on a schedule on Kaggle**, so a re-download is a *new measurement*, not the
same file. This script turns any of them into a plain markdown dump so that refreshing a snapshot
in `docs/meta/ladder_snapshots.md` is a re-run plus a paste, not an archaeology session inside a
3 MB JSON blob.

What it emits, per cell, in notebook order:
  - markdown cells verbatim
  - code cells fenced (skippable with --no-code; the prose + outputs are what carry the findings)
  - outputs: stream text, `text/markdown` and `text/plain` results, and HTML tables flattened to
    pipe-delimited text. Images are noted as `[image omitted]` — they are the one thing that does
    not survive the trip, so a chart-only finding still needs the notebook.

Usage:
    python analysis/nb_extract.py notebooks/*.ipynb -o docs/meta/_raw/
    python analysis/nb_extract.py notebooks/foo.ipynb --no-code        # prose + numbers only

The output is an *input* to a curated snapshot entry, not the entry itself: `ladder_snapshots.md`
keeps dated, deduplicated findings, because the same notebook re-run tomorrow restates most of
today's numbers with different values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<(style|script).*?</\1>", re.S)


def flatten_html(html: str) -> str:
    """Pandas `.to_html()` tables → pipe-delimited rows. Good enough to read and to grep."""
    out = _STYLE.sub("", html)
    out = re.sub(r"</t[dh]>\s*", " | ", out)
    out = re.sub(r"</tr>", "\n", out)
    out = _TAG.sub("", out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n\s*\n+", "\n", out)
    return "\n".join(line.strip(" |").strip() for line in out.splitlines() if line.strip(" |").strip())


def render_output(out: dict) -> list[str]:
    kind = out.get("output_type")
    if kind == "stream":
        text = "".join(out.get("text", [])).rstrip()
        return [f"```text\n{text}\n```"] if text else []
    if kind == "error":
        return [f"```text\n{out.get('ename')}: {out.get('evalue')}\n```"]
    if kind not in ("execute_result", "display_data"):
        return []

    data = out.get("data", {})
    if "text/markdown" in data:
        return ["".join(data["text/markdown"]).rstrip()]
    if "text/html" in data:
        flat = flatten_html("".join(data["text/html"]))
        return [f"```text\n{flat}\n```"] if flat else []
    if "text/plain" in data:
        text = "".join(data["text/plain"]).rstrip()
        if text.startswith("<Figure") or not text:
            return ["*[image omitted — see the notebook]*"]
        return [f"```text\n{text}\n```"]
    if any(k.startswith("image/") for k in data):
        return ["*[image omitted — see the notebook]*"]
    return []


def extract(path: Path, include_code: bool = True) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        f"# {path.stem}",
        "",
        f"> Extracted by `analysis/nb_extract.py` from `{path.as_posix()}`.",
        "> Cell numbers below are the anchors cited elsewhere in the repo "
        "(e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).",
        "",
    ]
    for i, cell in enumerate(nb.get("cells", [])):
        src = "".join(cell.get("source", [])).rstrip()
        kind = cell.get("cell_type")
        lines.append(f"## cell [{i}] — {kind}")
        lines.append("")
        if kind == "markdown":
            lines += [src, ""]
        elif include_code and src:
            lang = "python"
            lines += [f"```{lang}", src, "```", ""]
        for out in cell.get("outputs", []):
            rendered = render_output(out)
            if rendered:
                lines += ["**output:**", ""] + rendered + [""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("notebooks", nargs="+", type=Path)
    ap.add_argument("-o", "--out-dir", type=Path, default=None,
                    help="write <stem>.md here; default is stdout")
    ap.add_argument("--no-code", action="store_true", help="skip code cells, keep prose + outputs")
    args = ap.parse_args(argv)

    for nb_path in args.notebooks:
        if not nb_path.exists():
            print(f"missing: {nb_path}", file=sys.stderr)
            return 1
        text = extract(nb_path, include_code=not args.no_code)
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            dest = args.out_dir / f"{nb_path.stem}.md"
            dest.write_text(text, encoding="utf-8")
            print(f"{nb_path.name} -> {dest} ({len(text):,} chars)")
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
