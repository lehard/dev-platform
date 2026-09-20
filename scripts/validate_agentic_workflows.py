#!/usr/bin/env python3
"""Compile the pinned gh-aw sources and reject generated-file drift."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / ".github" / "aw" / "gh-aw-version.txt"
WORKFLOWS = ("process-issue-triage", "weekly-process-backlog-review")


def run(*args: str) -> None:
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        raise SystemExit(f"Invalid gh-aw version pin: {version!r}")

    installed = subprocess.run(
        ("gh", "aw", "version"), cwd=ROOT, text=True, capture_output=True, check=False
    )
    if installed.returncode or version not in installed.stdout + installed.stderr:
        raise SystemExit(
            f"gh-aw {version} is required; install it with: "
            f"gh extension install github/gh-aw --pin {version} --force"
        )

    run("gh", "aw", "compile", *WORKFLOWS, "--strict", "--validate")
    changed = subprocess.run(
        (
            "git",
            "diff",
            "--exit-code",
            "--",
            ".github/aw",
            ".github/workflows/process-issue-triage.lock.yml",
            ".github/workflows/weekly-process-backlog-review.lock.yml",
        ),
        cwd=ROOT,
    )
    if changed.returncode:
        raise SystemExit("Generated gh-aw files drifted; rerun scripts/validate_agentic_workflows.py and commit the result.")
    print(f"Agentic workflow sources and locks match gh-aw {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
