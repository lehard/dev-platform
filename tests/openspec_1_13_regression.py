#!/usr/bin/env python3
"""Exercise the OpenSpec 1.13.0 archive/delta regressions against an exact CLI."""
from __future__ import annotations

import argparse
import shlex
import subprocess
import tempfile
from pathlib import Path


def run(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise SystemExit(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}{result.stderr}"
        )
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def change_artifacts(root: Path, change: str) -> Path:
    directory = root / "openspec" / "changes" / change
    write(directory / "proposal.md", "# Proposal\n\n## Why\nRegression coverage.\n\n## What Changes\n- Exercise archive behavior.\n")
    write(directory / "design.md", "# Design\n\nUse a temporary OpenSpec project.\n")
    write(directory / "tasks.md", "- [x] Run the controlled regression.\n")
    return directory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openspec-command", required=True, help="exact OpenSpec command prefix")
    args = parser.parse_args()
    cli = shlex.split(args.openspec_command)
    if not cli:
        raise SystemExit("--openspec-command must not be empty")

    with tempfile.TemporaryDirectory(prefix="openspec-1-13-regression-") as tmp:
        root = Path(tmp)
        run(cli + ["init", str(root), "--tools", "none", "--no-animation", "--no-copilot-cloud"], root)

        # Two authored delta sections, plus a fenced literal header, must archive
        # both real requirements without interpreting the example as a third delta.
        write(
            root / "openspec" / "specs" / "archive-fixture" / "spec.md",
            "# Archive fixture\n\n## Purpose\nExercise safe delta application.\n\n## Requirements\n\n"
            "### Requirement: Existing requirement\nThe fixture SHALL retain its existing requirement.\n\n"
            "#### Scenario: Existing behavior\n- **WHEN** the fixture is read\n- **THEN** its original requirement remains.\n",
        )
        run(cli + ["new", "change", "duplicate-delta", "--json"], root)
        change = change_artifacts(root, "duplicate-delta")
        write(
            change / "specs" / "archive-fixture" / "spec.md",
            "## ADDED Requirements\n\n"
            "### Requirement: First authored addition\nThe archive SHALL retain the first addition.\n\n"
            "#### Scenario: First addition is applied\n- **WHEN** archive runs\n- **THEN** the first addition remains in the canonical spec.\n\n"
            "```markdown\n## ADDED Requirements\n### Requirement: Literal example only\n```\n\n"
            "## ADDED Requirements\n\n"
            "### Requirement: Second authored addition\nThe archive SHALL retain the second addition.\n\n"
            "#### Scenario: Second addition is applied\n- **WHEN** archive runs\n- **THEN** the second addition remains in the canonical spec.\n",
        )
        run(cli + ["validate", "duplicate-delta", "--strict", "--no-interactive"], root)
        run(cli + ["archive", "duplicate-delta", "--yes"], root)
        archived = (root / "openspec" / "specs" / "archive-fixture" / "spec.md").read_text(encoding="utf-8")
        for required in ("First authored addition", "Second authored addition"):
            if required not in archived:
                raise SystemExit(f"archive dropped authored requirement: {required}")
        if "Literal example only" in archived:
            raise SystemExit("archive interpreted a fenced delta header as an authored requirement")

        # Retiring a one-requirement capability must accept both `+` bullets and
        # wrapped scenario text, then remove the no-longer-valid empty spec.
        write(
            root / "openspec" / "specs" / "retired-fixture" / "spec.md",
            "# Retired fixture\n\n## Purpose\nExercise capability retirement.\n\n## Requirements\n\n"
            "### Requirement: Retired wrapped requirement\nThe fixture SHALL be removable.\n\n"
            "#### Scenario: Wrapped legacy behavior\n+ **WHEN** the old capability is evaluated with prose that wraps onto\n"
            "  a continuation line\n+ **THEN** the old behavior remains observable.\n",
        )
        run(cli + ["new", "change", "retire-wrapped", "--json"], root)
        change = change_artifacts(root, "retire-wrapped")
        write(change / ".openspec.yaml", "schema: spec-driven\nretire_capabilities: true\n")
        write(
            change / "specs" / "retired-fixture" / "spec.md",
            "## REMOVED Requirements\n\n### Requirement: Retired wrapped requirement\n\n"
            "The capability is intentionally retired after its final requirement is removed.\n",
        )
        run(cli + ["validate", "retire-wrapped", "--strict", "--no-interactive"], root)
        run(cli + ["archive", "retire-wrapped", "--yes"], root)
        if (root / "openspec" / "specs" / "retired-fixture" / "spec.md").exists():
            raise SystemExit("archive did not retire the emptied wrapped-bullet capability")

        # A change with planning artifacts but no delta specs must be surfaced as
        # such by apply guidance; it cannot be silently presented as spec-backed.
        run(cli + ["new", "change", "missing-deltas", "--json"], root)
        change_artifacts(root, "missing-deltas")
        apply = run(cli + ["instructions", "apply", "--change", "missing-deltas", "--json"], root, check=False)
        output = (apply.stdout + apply.stderr).lower()
        if "spec" not in output or not any(word in output for word in ("missing", "no delta", "warning")):
            raise SystemExit("apply guidance did not flag the change with no delta specs")

    print("OpenSpec 1.13.0 archive/delta regression fixtures passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
