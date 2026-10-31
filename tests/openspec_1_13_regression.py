#!/usr/bin/env python3
"""Exercise the OpenSpec archive/delta/verify regressions against an exact CLI.

The fixtures pin the correctness fixes that motivated adopting each tested
release: the 1.13.1/1.13.2 fixtures fail against 1.13.0, and the 1.14.1-1.15.0
fixtures (strict requirement length, dropped delta text) fail against 1.13.2.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
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


VERIFY_PROFILE = {
    "featureFlags": {},
    "profile": "custom",
    "delivery": "both",
    "workflows": ["propose", "explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"],
}


def delta_change(root: Path, cli: list[str], change: str, delta: str, tasks: str = "- [x] Run the controlled regression.\n") -> Path:
    run(cli + ["new", "change", change, "--json"], root)
    directory = change_artifacts(root, change)
    write(directory / "tasks.md", tasks)
    write(directory / "specs" / "rename-fixture" / "spec.md", delta)
    return directory


def check_rename_remove_case_and_tasks(root: Path, cli: list[str]) -> None:
    spec = root / "openspec" / "specs" / "rename-fixture" / "spec.md"
    write(
        spec,
        "# Rename fixture\n\n## Purpose\nExercise rename, removal and name-collision safety.\n\n## Requirements\n\n"
        "### Requirement: Alpha behavior\nThe fixture SHALL do alpha.\n\n"
        "#### Scenario: Alpha\n- **WHEN** alpha runs\n- **THEN** alpha happens\n\n"
        "### Requirement: Beta behavior\nThe fixture SHALL do beta.\n\n"
        "#### Scenario: Beta\n- **WHEN** beta runs\n- **THEN** beta happens\n",
    )
    original = spec.read_text(encoding="utf-8")

    # 1.13.1: a requirement differing from an existing one only in case must
    # not be archived as a second near-duplicate requirement.
    delta_change(
        root, cli, "case-duplicate",
        "## ADDED Requirements\n\n### Requirement: alpha BEHAVIOR\nThe fixture SHALL do alpha twice.\n\n"
        "#### Scenario: Duplicate alpha\n- **WHEN** alpha runs\n- **THEN** alpha happens again\n",
    )
    run(cli + ["archive", "case-duplicate", "--yes"], root, check=False)
    if spec.read_text(encoding="utf-8") != original:
        raise SystemExit("archive applied a requirement that differs from an existing one only in case")

    # 1.13.1: RENAMED FROM/TO lines that do not pair are rejected before archive.
    delta_change(
        root, cli, "unpaired-rename",
        "## RENAMED Requirements\n\n- FROM: `### Requirement: Alpha behavior`\n"
        "- FROM: `### Requirement: Beta behavior`\n- TO: `### Requirement: Gamma behavior`\n",
    )
    if not run(cli + ["validate", "unpaired-rename", "--strict", "--no-interactive"], root, check=False).returncode:
        raise SystemExit("strict validation accepted unpaired RENAMED FROM/TO lines")
    run(cli + ["archive", "unpaired-rename", "--yes"], root, check=False)
    if spec.read_text(encoding="utf-8") != original:
        raise SystemExit("archive applied unpaired RENAMED FROM/TO lines")

    # Task progress: `[~]`, `+` and numbered markers are open work (1.13.1).
    delta_change(
        root, cli, "task-markers",
        "## RENAMED Requirements\n\n- FROM: `### Requirement: Alpha behavior`\n- TO: `### Requirement: Gamma behavior`\n\n"
        "## REMOVED Requirements\n\n### Requirement: Beta behavior\n\n**Reason**: Retired by the fixture.\n**Migration**: None.\n",
        tasks="- [x] Done task\n- [~] Partially done task\n+ [ ] Plus-marker task\n1. [ ] Numbered task\n",
    )
    apply = json.loads(run(cli + ["instructions", "apply", "--change", "task-markers", "--json"], root).stdout)
    if apply.get("taskTrackingConfigured") is not True or apply.get("progress") != {"total": 4, "complete": 1, "remaining": 3}:
        raise SystemExit(f"task progress hid open non-dash or [~] tasks: {apply.get('progress')}")
    if apply.get("state") == "all_done":
        raise SystemExit("apply reported all_done while tasks remain open")

    # A correctly paired RENAMED plus REMOVED archives exactly.
    run(cli + ["validate", "task-markers", "--strict", "--no-interactive"], root)
    write(root / "openspec" / "changes" / "task-markers" / "tasks.md", "- [x] Done task\n")
    run(cli + ["archive", "task-markers", "--yes"], root)
    archived = spec.read_text(encoding="utf-8")
    if "### Requirement: Gamma behavior" not in archived or "The fixture SHALL do alpha." not in archived:
        raise SystemExit("archive did not rename the requirement while keeping its behavior")
    if "Alpha behavior" in archived or "Beta behavior" in archived:
        raise SystemExit("archive kept a renamed or removed requirement")


def check_new_capability_purpose(root: Path, cli: list[str]) -> None:
    """Pin the behavior the platform archive Purpose preflight relies on (BR-580)."""
    requirement = (
        "## ADDED Requirements\n\n### Requirement: Purpose fixture behaves\nThe fixture SHALL behave.\n\n"
        "#### Scenario: Behaves\n- **WHEN** the fixture runs\n- **THEN** it behaves.\n"
    )
    authored = "Exercise how archive creates a capability whose delta carries an authored Purpose."
    run(cli + ["new", "change", "purpose-authored", "--json"], root)
    write(change_artifacts(root, "purpose-authored") / "specs" / "purpose-authored" / "spec.md",
          f"## Purpose\n{authored}\n\n{requirement}")
    run(cli + ["archive", "purpose-authored", "--yes"], root)
    created = (root / "openspec" / "specs" / "purpose-authored" / "spec.md").read_text(encoding="utf-8")
    if authored not in created or "TBD" in created:
        raise SystemExit("archive did not write the authored delta Purpose to the new capability")
    run(cli + ["validate", "purpose-authored", "--type", "spec", "--strict", "--no-interactive"], root)

    run(cli + ["new", "change", "purpose-missing", "--json"], root)
    write(change_artifacts(root, "purpose-missing") / "specs" / "purpose-missing" / "spec.md", requirement)
    run(cli + ["validate", "purpose-missing", "--strict", "--no-interactive"], root)
    run(cli + ["archive", "purpose-missing", "--yes"], root)
    created = (root / "openspec" / "specs" / "purpose-missing" / "spec.md").read_text(encoding="utf-8")
    if "Update Purpose after archive" not in created:
        raise SystemExit("archive no longer writes the placeholder Purpose the platform preflight detects")
    if not run(cli + ["validate", "purpose-missing", "--type", "spec", "--strict", "--no-interactive"], root, check=False).returncode:
        raise SystemExit("strict validation accepted a placeholder Purpose")
    (root / "openspec" / "specs" / "purpose-missing" / "spec.md").unlink()


def check_requirement_length_and_dropped_text(root: Path, cli: list[str]) -> None:
    """1.14.1-1.15.0: strict requirement length and archive text-drop warnings (BR-799, DEC-0007)."""
    write(
        root / "openspec" / "specs" / "length-fixture" / "spec.md",
        "# Length fixture\n\n## Purpose\nExercise the strict requirement length limit and dropped delta text.\n\n"
        "## Requirements\n\n### Requirement: Kept requirement\nThe fixture SHALL keep its requirement.\n\n"
        "#### Scenario: Kept\n- **WHEN** the fixture is read\n- **THEN** its requirement remains.\n",
    )

    def added(change: str, length: int, extra: str = "") -> None:
        prefix = "The fixture SHALL hold a requirement description of exactly the tested length"
        text = (prefix + " " + "x" * length)[:length]
        run(cli + ["new", "change", change, "--json"], root)
        write(change_artifacts(root, change) / "specs" / "length-fixture" / "spec.md",
              f"{extra}## ADDED Requirements\n\n### Requirement: {change} requirement\n{text}\n\n"
              "#### Scenario: Holds\n- **WHEN** the fixture is validated\n- **THEN** its length is checked.\n")

    def strict_ok(change: str) -> bool:
        return not run(cli + ["validate", change, "--strict", "--no-interactive"], root, check=False).returncode

    added("length-at-limit", 500)
    if not strict_ok("length-at-limit"):
        raise SystemExit("strict validation rejected an ADDED requirement of exactly 500 characters")
    added("length-over-limit", 501)
    run(cli + ["validate", "length-over-limit", "--no-interactive"], root)
    if strict_ok("length-over-limit"):
        raise SystemExit("strict validation accepted an ADDED requirement over 500 characters")

    added("dropped-text", 60, extra="Prose above the first section.\n\n")
    with_notes = root / "openspec" / "changes" / "dropped-text" / "specs" / "length-fixture" / "spec.md"
    with_notes.write_text(with_notes.read_text(encoding="utf-8") + "\n## Notes\nAn extra section.\n", encoding="utf-8")
    result = run(cli + ["validate", "dropped-text", "--no-interactive"], root)
    output = result.stdout + result.stderr
    for required in ('Text above the first "## " section is not carried', 'Section "## Notes" is not carried'):
        if required not in output:
            raise SystemExit(f"validate no longer warns that archive drops delta text: {required}")
    if strict_ok("dropped-text"):
        raise SystemExit("strict validation accepted delta text that archive drops")
    for change in ("length-at-limit", "length-over-limit", "dropped-text"):
        shutil.rmtree(root / "openspec" / "changes" / change)


def check_verify_workflow(cli: list[str]) -> None:
    # 1.13.2: generated verify guidance must not pass skipped checks, must invert
    # REMOVED checks and check RENAMED against original behavior, and stays
    # advisory so platform archive gates remain authoritative.
    with tempfile.TemporaryDirectory(prefix="openspec-verify-workflow-") as tmp:
        root = Path(tmp) / "project"
        config = Path(tmp) / "config"
        root.mkdir()
        write(config / "openspec" / "config.json", json.dumps(VERIFY_PROFILE))
        env = {**os.environ, "XDG_CONFIG_HOME": str(config)}
        result = subprocess.run(
            cli + ["init", ".", "--tools", "claude", "--profile", "custom", "--force"],
            cwd=root, text=True, capture_output=True, env=env,
        )
        if result.returncode:
            raise SystemExit(f"openspec init for verify workflow failed:\n{result.stdout}{result.stderr}")
        skill = root / ".claude" / "skills" / "openspec-verify-change" / "SKILL.md"
        if not skill.is_file():
            raise SystemExit("platform custom profile did not generate the verify workflow")
        text = skill.read_text(encoding="utf-8")
        for required in (
            "Verification is advisory",
            "Archive retains its own checks",
            "**Not verified**",
            "Never report a REMOVED requirement as \"Requirement not found\"",
            "Removed requirement still implemented",
            "Do not report the FROM name as missing",
        ):
            if required not in text:
                raise SystemExit(f"verify workflow lacks required guidance: {required}")


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
        if archived.count("### Requirement: Literal example only") != 1:
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

        check_rename_remove_case_and_tasks(root, cli)
        check_new_capability_purpose(root, cli)
        check_requirement_length_and_dropped_text(root, cli)

    check_verify_workflow(cli)

    print("OpenSpec archive/delta/verify regression fixtures passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
