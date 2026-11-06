#!/usr/bin/env python3
"""Scripted repair writer behind --llm-command: writes the files a scenario chose into its checkout.

argv: <edits file> <platform task>. The edits file maps relative paths to their new content; the task is ignored,
so a run reproduces the same repair.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    edits = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for relative, content in edits.items():
        target = Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
