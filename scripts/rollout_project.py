from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ANSWER_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*?)\s*$")
EXPECTED_SOURCES = {
    "gh:lehard/dev-platform",
    "https://github.com/lehard/dev-platform",
    "https://github.com/lehard/dev-platform.git",
    "git@github.com:lehard/dev-platform.git",
}

# Paths that a mature project may own while still receiving the additive
# dev-platform lifecycle around them. These mirror the guarded collision points
# in copier.yml. Platform common/bootstrap/doctor/OpenSpec lifecycle remain
# platform-owned; repository-specific Git/task execution stays project-owned.
PROJECT_OWNED_ROLLOUT_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "dev-platform/checks.toml",
    "openspec/config.yaml",
    "docs/engineering/project-rules.md",
    "scripts/agent_board.py",
    "scripts/agent_doctor.py",
    "scripts/agent_friction.py",
    "scripts/finish_task.py",
    "scripts/merge_to_main.py",
    "scripts/project_publish.py",
    "scripts/project_sync.py",
    "scripts/select_checks.py",
    "scripts/start_task.py",
    "scripts/start_worktree.py",
    "scripts/worktree_cleanup.py",
    "scripts/git_hooks/pre-commit",
    "scripts/git_hooks/pre-merge-commit",
}

# A very small migration-only allowlist for files that used to carry downstream
# customization but have since been deliberately reclaimed by the platform.
# They are NEVER treated as project-owned. A Copier conflict is eligible for the
# guarded recopy path only when the downstream file already matches the exact
# target template bytes before the smart update starts.
RECLAIMED_PLATFORM_ROLLOUT_PATHS = {
    "scripts/_platform_common.py",
}


def run(
    command: list[str],
    cwd: Path,
    *,
    capture: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=capture, env=env)
    if check and result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")
        raise SystemExit(result.returncode)
    return result


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_answers(text: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    for line in text.splitlines():
        match = ANSWER_RE.match(line)
        if match:
            answers[match.group(1)] = clean_scalar(match.group(2))
    return answers


def normalize_copier_answers(project_root: Path) -> None:
    path = project_root / ".copier-answers.yml"
    if not path.exists():
        raise ValueError(".copier-answers.yml is missing after Copier update")
    text = path.read_text(encoding="utf-8")
    normalized = text.rstrip("\r\n") + "\n"
    if normalized != text:
        path.write_text(normalized, encoding="utf-8")
        print("Normalized .copier-answers.yml trailing newline formatting")


def load_answers(project_root: Path) -> dict[str, str]:
    path = project_root / ".copier-answers.yml"
    if not path.exists():
        raise ValueError(".copier-answers.yml is missing; first-time adoption is required")
    answers = parse_answers(path.read_text(encoding="utf-8"))
    source = answers.get("_src_path")
    current = answers.get("_commit")
    if source not in EXPECTED_SOURCES:
        raise ValueError(f"unexpected Copier source: {source!r}")
    if current is None:
        raise ValueError(".copier-answers.yml does not contain _commit")
    parse_version(current)
    return answers


def load_platform_config(project_root: Path) -> dict[str, Any]:
    import tomllib

    path = project_root / ".dev-platform.toml"
    if not path.exists():
        raise ValueError(".dev-platform.toml is missing")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_platform_version(project_root: Path) -> str:
    config = load_platform_config(project_root)
    value = str(config.get("platform_version", "")).strip()
    if not value:
        raise ValueError(".dev-platform.toml does not contain platform_version")
    return value


def platform_config_contract(project_root: Path) -> dict[str, Any]:
    """Return project-owned config excluding release metadata allowed to advance."""
    config = load_platform_config(project_root)
    config.pop("platform_version", None)
    return config


def harness_mode(project_root: Path) -> str:
    return str(load_platform_config(project_root).get("harness_mode", "platform"))


def require_version_coherence(project_root: Path, copier_tag: str) -> None:
    expected = copier_tag[1:]
    configured = load_platform_version(project_root)
    if configured != expected:
        raise ValueError(
            f"platform version metadata mismatch: .copier-answers.yml={copier_tag}, "
            f".dev-platform.toml={configured!r}"
        )


def parse_version(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"platform version must be a stable SemVer tag vX.Y.Z; got {tag!r}")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def rollout_branch(version: str) -> str:
    parse_version(version)
    return f"dev-platform/rollout-{version}"


def find_reject_files(project_root: Path) -> list[str]:
    ignored_dirs = {".git", ".venv", "venv", "node_modules", ".claude"}
    found: list[str] = []
    for path in project_root.rglob("*.rej"):
        relative = path.relative_to(project_root)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        found.append(str(relative))
    return sorted(found)


def reject_target(reject_path: str) -> str:
    return reject_path[:-4] if reject_path.endswith(".rej") else reject_path


def project_owned_paths(project_root: Path) -> set[str]:
    config = load_platform_config(project_root)
    paths = set(PROJECT_OWNED_ROLLOUT_PATHS)
    required = config.get("project_required_files", [])
    if isinstance(required, list):
        paths.update(str(item) for item in required if isinstance(item, str) and item)
    # Product CI is intentionally not generated by the platform anymore, but
    # fingerprint it during recopy to prove the fallback did not disturb it.
    paths.add(".github/workflows/ci.yml")
    return paths


def path_fingerprint(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        return ("symlink", os.readlink(path))
    if path.is_file():
        return ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    if path.is_dir():
        return ("dir", "present")
    return ("missing", "")


def reclaimed_platform_path_matches_template(project_root: Path, relative: str) -> bool:
    if relative not in RECLAIMED_PLATFORM_ROLLOUT_PATHS:
        return False
    project_path = project_root / relative
    template_path = PLATFORM_ROOT / "template" / relative
    project_fingerprint = path_fingerprint(project_path)
    template_fingerprint = path_fingerprint(template_path)
    return project_fingerprint[0] != "missing" and project_fingerprint == template_fingerprint


def require_reclaimed_platform_paths_match_template(
    project_root: Path, relatives: set[str]
) -> None:
    mismatched = sorted(
        relative
        for relative in relatives
        if not reclaimed_platform_path_matches_template(project_root, relative)
    )
    if mismatched:
        raise ValueError(
            "reclaimed platform files no longer match the target template: "
            + ", ".join(mismatched[:10])
        )


def snapshot_existing_project_owned(project_root: Path) -> dict[str, tuple[str, str]]:
    snapshot: dict[str, tuple[str, str]] = {}
    for relative in sorted(project_owned_paths(project_root)):
        path = project_root / relative
        fingerprint = path_fingerprint(path)
        if fingerprint[0] != "missing":
            snapshot[relative] = fingerprint
    return snapshot


def require_project_owned_snapshot(
    project_root: Path, snapshot: dict[str, tuple[str, str]]
) -> None:
    changed = [
        relative
        for relative, expected in snapshot.items()
        if path_fingerprint(project_root / relative) != expected
    ]
    if changed:
        raise ValueError(
            "project-owned files changed during guarded Copier recopy: "
            + ", ".join(changed[:10])
        )


def ensure_clean(project_root: Path) -> None:
    status = run(["git", "status", "--porcelain"], project_root, capture=True)
    if status.stdout.strip():
        raise ValueError("downstream checkout is dirty before rollout")


def ensure_branch_absent(project_root: Path, branch: str) -> None:
    result = run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        project_root,
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        raise ValueError(f"rollout branch already exists without a handled open PR: {branch}")
    if result.returncode not in {0, 2}:
        raise ValueError("could not inspect downstream rollout branch state")


def private_source_git_env() -> dict[str, str]:
    token = os.environ.get("DEV_PLATFORM_SOURCE_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "DEV_PLATFORM_SOURCE_TOKEN is required to fetch the private dev-platform Copier source"
        )
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = f"url.https://x-access-token:{token}@github.com/.insteadOf"
    env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
    return env


def reset_failed_copier_update(project_root: Path) -> None:
    """Reset only the ephemeral rollout branch after a conflict-only update attempt."""
    run(["git", "reset", "--hard", "HEAD"], project_root)
    run(["git", "clean", "-fd"], project_root)
    ensure_clean(project_root)


def run_rendered_platform_bootstrap(project_root: Path, *, env: dict[str, str]) -> None:
    """Apply platform-owned post-render initialization from the candidate version.

    Copier update can otherwise execute `_tasks` from the historical template
    snapshot. Managed rollout deliberately skips those tasks and runs only this
    newly rendered bootstrap after the update/recovery path is conflict-free.
    """
    bootstrap = project_root / "scripts" / "platform_bootstrap.py"
    if not bootstrap.is_file():
        raise ValueError("updated project is missing scripts/platform_bootstrap.py")
    run(["python3", str(bootstrap)], project_root, env=env)


def copier_update_with_guarded_recopy(
    project_root: Path,
    version: str,
    *,
    env: dict[str, str],
) -> str:
    """Run smart update, falling back to recopy only for proven-safe conflicts.

    Copier's update algorithm replays the downstream diff from the old template
    onto the new template. When ownership changes, that historic diff can conflict
    even though the current downstream tree is already correct. Recopy is allowed
    only for a project-owned harness when every conflict is either a declared
    project-owned path or a narrowly allowlisted reclaimed platform path that
    already matched the exact target template before the smart update started.
    """

    mode = harness_mode(project_root)
    config_before = platform_config_contract(project_root)
    protected_before = snapshot_existing_project_owned(project_root)
    reclaimed_before = {
        relative
        for relative in RECLAIMED_PLATFORM_ROLLOUT_PATHS
        if reclaimed_platform_path_matches_template(project_root, relative)
    }

    run(
        [
            "copier",
            "update",
            "--trust",
            "--defaults",
            "--skip-tasks",
            "--vcs-ref",
            version,
            "--conflict",
            "rej",
        ],
        project_root,
        env=env,
    )
    rejects = find_reject_files(project_root)
    if not rejects:
        run_rendered_platform_bootstrap(project_root, env=env)
        return "update"

    owned = project_owned_paths(project_root)
    conflict_targets = {reject_target(path) for path in rejects}
    reclaimed_conflicts = conflict_targets & reclaimed_before
    unexpected = sorted(conflict_targets - owned - reclaimed_conflicts)
    if mode != "project" or unexpected:
        detail = ", ".join(rejects[:10])
        if unexpected:
            detail += "; non-project-owned conflicts: " + ", ".join(unexpected[:10])
        raise ValueError("Copier left unresolved .rej files: " + detail)

    print(
        "Smart Copier update conflicted only on protected project-owned paths "
        "or already-reclaimed platform paths; retrying with guarded recopy.",
        flush=True,
    )
    reset_failed_copier_update(project_root)
    require_project_owned_snapshot(project_root, protected_before)
    require_reclaimed_platform_paths_match_template(project_root, reclaimed_conflicts)

    # Copier 9.17 `recopy` has no --conflict switch. We use --overwrite so
    # platform-owned files can update non-interactively; template skip_if_exists
    # still excludes project-owned collision points. Fingerprints and config are
    # verified immediately afterwards.
    run(
        [
            "copier",
            "recopy",
            "--trust",
            "--defaults",
            "--skip-tasks",
            "--overwrite",
            "--vcs-ref",
            version,
        ],
        project_root,
        env=env,
    )

    recopy_rejects = find_reject_files(project_root)
    if recopy_rejects:
        raise ValueError(
            "guarded Copier recopy still left unresolved .rej files: "
            + ", ".join(recopy_rejects[:10])
        )
    run_rendered_platform_bootstrap(project_root, env=env)
    require_project_owned_snapshot(project_root, protected_before)
    require_reclaimed_platform_paths_match_template(project_root, reclaimed_conflicts)
    config_after = platform_config_contract(project_root)
    if config_after != config_before:
        raise ValueError(
            "project-owned .dev-platform.toml changed beyond platform_version during guarded recopy"
        )
    if harness_mode(project_root) != "project":
        raise ValueError("guarded recopy changed harness_mode away from project")
    return "guarded-recopy"


def run_project_validation(project_root: Path, base_branch: str) -> None:
    rejects = find_reject_files(project_root)
    if rejects:
        raise ValueError("Copier left unresolved .rej files: " + ", ".join(rejects[:10]))
    run(["git", "diff", "--check", "--"], project_root)

    doctor = project_root / "scripts" / "platform_doctor.py"
    if not doctor.exists():
        raise ValueError("updated project is missing scripts/platform_doctor.py")
    run(["python3", str(doctor)], project_root)

    if harness_mode(project_root) == "project":
        print(
            "harness_mode=project; rollout delegates product/application checks to downstream CI.",
            flush=True,
        )
        return

    checks = project_root / "scripts" / "select_checks.py"
    if not checks.exists():
        raise ValueError("updated project is missing scripts/select_checks.py")
    run(
        ["python3", str(checks), "--base", f"origin/{base_branch}", "--execute"],
        project_root,
    )


def write_result(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if path:
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def apply_rollout(
    project_root: Path,
    repository: str,
    version: str,
    base_branch: str,
    output: Path | None = None,
) -> int:
    project_root = project_root.resolve()
    target = parse_version(version)
    if shutil.which("copier") is None:
        raise ValueError("Copier is not installed")
    ensure_clean(project_root)
    answers = load_answers(project_root)
    current_tag = answers["_commit"]
    current = parse_version(current_tag)
    require_version_coherence(project_root, current_tag)
    branch = rollout_branch(version)

    if current == target:
        write_result(
            output,
            {
                "status": "up_to_date",
                "repository": repository,
                "current": current_tag,
                "target": version,
                "branch": branch,
            },
        )
        return 0
    if current > target:
        raise ValueError(f"refusing platform downgrade from {current_tag} to {version}")

    ensure_branch_absent(project_root, branch)
    run(["git", "fetch", "origin", base_branch], project_root)
    run(["git", "checkout", "-b", branch, f"origin/{base_branch}"], project_root)
    ensure_clean(project_root)

    strategy = copier_update_with_guarded_recopy(
        project_root,
        version,
        env=private_source_git_env(),
    )
    normalize_copier_answers(project_root)

    updated = load_answers(project_root)
    if updated["_commit"] != version:
        raise ValueError(
            f"Copier recorded {updated['_commit']!r}, expected exact target {version!r}"
        )
    require_version_coherence(project_root, version)

    run_project_validation(project_root, base_branch)
    status = run(["git", "status", "--porcelain"], project_root, capture=True)
    if not status.stdout.strip():
        raise ValueError("Copier changed the recorded version but produced no repository diff")

    run(["git", "add", "-A"], project_root)
    run(["git", "diff", "--cached", "--check", "--"], project_root)
    run(["git", "commit", "-m", f"chore: update dev-platform to {version}"], project_root)
    write_result(
        output,
        {
            "status": "updated",
            "repository": repository,
            "current": current_tag,
            "target": version,
            "branch": branch,
            "strategy": strategy,
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare one managed downstream repository for an exact dev-platform Copier rollout PR."
    )
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        return apply_rollout(
            args.project_root,
            args.repository,
            args.version,
            args.base_branch,
            args.output,
        )
    except ValueError as exc:
        print(f"Managed rollout: BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
