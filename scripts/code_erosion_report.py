#!/usr/bin/env python3
"""Render upstream scb-check output as an informational Markdown report.

Formatting only: all analysis is done by the pinned upstream ``scb-check``.
Each ``--area NAME=PREFIX`` reads ``PREFIX.json`` (``--report``), ``PREFIX.txt``
(human output, for hotspots) and ``PREFIX.exit``. The script never fails: a
missing or garbled input becomes a note in the report. Contract:
docs/engineering/code-erosion.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MARKER = "<!-- code-erosion-report -->"
TOP_HOTSPOTS = 5
HOTSPOT_RE = re.compile(
    r"^erosion: function `(?P<name>[^`]+)` exceeds complexity threshold\n"
    r"\s*┌─ (?P<where>\S+)\n(?:.*\n)*?\s*= complexity: (?P<cc>\d+), sloc: (?P<sloc>\d+)",
    re.MULTILINE,
)
METRICS = ("verbosity", "erosion", "cog_erosion", "files_scanned", "total_loc", "high_cc_functions", "total_functions")


def hotspots(text: str) -> list[tuple[str, str, int, int]]:
    found = [(m["name"], m["where"], int(m["cc"]), int(m["sloc"])) for m in HOTSPOT_RE.finditer(text)]
    return sorted(found, key=lambda item: (-item[2], item[1]))[:TOP_HOTSPOTS]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def render_area(name: str, prefix: str) -> list[str]:
    base = Path(prefix)
    exit_code = read_text(base.with_suffix(".exit")).strip() or "?"
    lines = [f"### `{name}`", ""]
    try:
        data = json.loads(read_text(base.with_suffix(".json")))
        values = {key: data[key] for key in METRICS}
        verbosity, erosion, cog = (float(values[k]) for k in ("verbosity", "erosion", "cog_erosion"))
    except (ValueError, KeyError, TypeError):
        lines.append(f"> scb-check produced no usable report (exit {exit_code}); no signal for this area.")
        return lines
    if exit_code == "2":
        lines += ["> scb-check exited 2 (path/config error); values may be incomplete.", ""]
    lines += [
        "| Verbosity | Erosion | Cognitive erosion | Files | SLOC | High-CC functions |",
        "|---|---|---|---|---|---|",
        f"| {verbosity:.3f} | {erosion:.3f} | {cog:.3f} | {values['files_scanned']} | {values['total_loc']} "
        f"| {values['high_cc_functions']}/{values['total_functions']} |",
    ]
    top = hotspots(read_text(base.with_suffix(".txt")))
    if top:
        lines += ["", f"Most complex functions flagged (top {len(top)}):", ""]
        lines += [f"- `{fn}` at `{where}` (complexity {cc}, {sloc} SLOC)" for fn, where, cc, sloc in top]
    return lines


def render(version: str, areas: list[tuple[str, str]]) -> str:
    out = [
        MARKER,
        "## Code Erosion Report",
        "",
        f"_Informational only; it never blocks merge. Upstream `scb-check=={version}` (SlopCodeBench) "
        "heuristics, not a quality score: they are Python-calibrated, not comparable across languages or "
        "projects, and do not replace tests, lint or review. Compare with the baseline in "
        "`docs/engineering/code-erosion.md`._",
        "",
    ]
    for name, prefix in areas:
        out += render_area(name, prefix) + [""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--area", action="append", default=[], metavar="NAME=PREFIX")
    args = parser.parse_args(argv)
    areas = [tuple(item.split("=", 1)) for item in args.area if "=" in item]
    try:
        sys.stdout.write(render(args.version, areas))
    except Exception as error:  # informational tool: never fail the caller
        sys.stdout.write(f"{MARKER}\n## Code Erosion Report\n\n> report rendering failed: `{error}`\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
