"""Prove a release candidate can be installed without product commands.

The matrix intentionally covers the supported delivery/harness boundaries,
not every workflow-profile permutation.  Each disposable target is rendered
with real Copier and checked by the same platform-only validator used by
managed rollout.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rollout_project import normalize_copier_answers, validate_platform_installation

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class InstallationCase:
    name: str
    scm_provider: str
    harness_mode: str
    workflow_profile: str = "standard"
    publish_mode: str = "pr"


# GitHub owns both supported harness modes. GitLab has a platform-owned
# lifecycle only, so one fresh render covers its documented support boundary.
FRESH_CASES = (
    InstallationCase("github-platform", "github", "platform"),
    InstallationCase("github-project", "github", "project", workflow_profile="multi-agent"),
    InstallationCase("gitlab-platform", "gitlab", "platform"),
)
UPGRADE_CASES = FRESH_CASES


def run(command: list[str], cwd: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, text=True, check=True)


def stable_baseline_ref() -> str | None:
    result = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*", "--sort=-version:refname"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return next((tag for line in result.stdout.splitlines() if (tag := line.strip())), None)


def shallow_repository() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return result.stdout.strip().lower() == "true"


def copier_data(case: InstallationCase) -> list[str]:
    values = {
        "project_name": f"Release installation {case.name}",
        "project_slug": f"release-installation-{case.name}",
        "project_description": "Disposable release installation validation",
        "workflow_profile": case.workflow_profile,
        "harness_mode": case.harness_mode,
        "publish_mode": case.publish_mode,
        "scm_provider": case.scm_provider,
        "platform_ci_ref": "release-installation-validation",
    }
    return [item for key, value in values.items() for item in ("--data", f"{key}={value}")]


def initialize_repository(target: Path) -> None:
    run(["git", "init", "-b", "main"], target)
    run(["git", "config", "user.name", "dev-platform-release-validation"], target)
    run(["git", "config", "user.email", "dev-platform-release-validation@example.invalid"], target)


def stage_for_hygiene(target: Path) -> None:
    # A Copier fresh render is untracked; staging it makes the shared validator
    # exercise both unstaged and staged diff hygiene on every case.
    run(["git", "add", "-A"], target)


def render(case: InstallationCase, target: Path, source_ref: str) -> None:
    run(
        ["copier", "copy", "--trust", "--defaults", "--vcs-ref", source_ref, *copier_data(case), str(ROOT), str(target)],
        ROOT,
    )


def validate_fresh(case: InstallationCase, root: Path) -> None:
    target = root / case.name
    render(case, target, "HEAD")
    normalize_copier_answers(target)
    initialize_repository(target)
    stage_for_hygiene(target)
    validate_platform_installation(target)


def validate_upgrade(case: InstallationCase, root: Path, baseline: str) -> None:
    target = root / case.name
    render(case, target, baseline)
    initialize_repository(target)
    run(["git", "add", "-A"], target)
    run(["git", "commit", "-m", "Baseline rendered from " + baseline], target)
    run(["copier", "update", "--trust", "--defaults", "--vcs-ref", "HEAD", "--conflict", "inline"], target)
    normalize_copier_answers(target)
    stage_for_hygiene(target)
    validate_platform_installation(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate representative Copier installations before publication.")
    parser.add_argument("--baseline-ref", help="Stable tag to upgrade from (defaults to newest local vX.Y.Z tag).")
    parser.add_argument("--allow-missing-baseline", action="store_true", help="Skip upgrades only for local snapshot checks without tag history.")
    parser.add_argument("--allow-shallow-snapshot", action="store_true", help="Skip all cases only for an explicitly local shallow checkout; CI and publication must have complete history.")
    args = parser.parse_args()
    if shallow_repository():
        if args.allow_shallow_snapshot:
            print("Skipping release installation validation for this explicit shallow local snapshot; CI and publication require complete history.")
            return 0
        raise SystemExit("Release installation validation requires complete Git history; fetch an unshallowed checkout.")
    baseline = args.baseline_ref or stable_baseline_ref()
    if baseline is None and not args.allow_missing_baseline:
        raise SystemExit("Release installation validation requires a stable baseline tag; fetch full tag history.")
    if baseline is None:
        print("No stable baseline is available; skipping upgrade cases for this explicit local snapshot run.")

    # The validator must remain platform-only. Do not add select_checks.py or
    # repository application commands here; those are downstream CI ownership.
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    with tempfile.TemporaryDirectory(prefix="dev-platform-release-installation-") as temporary:
        root = Path(temporary)
        for case in FRESH_CASES:
            print(f"Validating fresh installation: {case.name}", flush=True)
            validate_fresh(case, root / "fresh")
        if baseline:
            for case in UPGRADE_CASES:
                print(f"Validating upgrade installation: {case.name} from {baseline}", flush=True)
                validate_upgrade(case, root / "upgrade", baseline)
    print("Release installation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
