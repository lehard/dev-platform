from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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
BACKLOG_PROJECT_OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
TASK_INTAKE_REFERENCE_MARKER = "<!-- dev-platform:task-intake-reference -->"
TASK_INTAKE_REFERENCE = "docs/engineering/task-intake.md"

# Files that remain downstream-owned for every harness mode.
ALWAYS_PROJECT_OWNED_ROLLOUT_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "dev-platform/checks.toml",
    "openspec/config.yaml",
    "docs/engineering/project-rules.md",
}

# Paths that a mature project-owned harness may keep while still receiving the
# additive dev-platform lifecycle around it. Platform harnesses own these paths.
PROJECT_HARNESS_ROLLOUT_PATHS = {
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

# Compatibility union retained for callers/tests that inspect the declared
# collision surface directly.
PROJECT_OWNED_ROLLOUT_PATHS = (
    ALWAYS_PROJECT_OWNED_ROLLOUT_PATHS | PROJECT_HARNESS_ROLLOUT_PATHS
)

# A very small migration-only allowlist for files that used to carry downstream
# customization but have since been deliberately reclaimed by the platform.
# They are NEVER treated as project-owned for recovery. A Copier conflict is
# eligible for guarded recopy when the committed downstream file already matches
# the exact target template bytes before the smart update starts.
RECLAIMED_PLATFORM_ROLLOUT_PATHS = {
    "scripts/_platform_common.py",
    "scripts/project_publish.py",
}

# One historical managed project removed a redundant blank separator from the
# platform-owned workflow.  That formatting-only drift is safe to replace, but
# the exception must not become a general ownership bypass: it is limited to
# this generated workflow and is disabled if its YAML later gains block scalar
# content, where blank lines can carry meaning.
BASELINE_FORMAT_EQUIVALENT_PATHS = {".github/workflows/dev-platform.yml"}
YAML_BLOCK_SCALAR_RE = re.compile(rb":\s*[>|][+-]?\s*(?:#.*)?$", re.MULTILINE)


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
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise ValueError(f"command failed (exit {result.returncode}): {' '.join(command)}{suffix}")
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


def development_backlog_locator_answers(project_root: Path) -> tuple[str, int]:
    answers = parse_answers((project_root / ".copier-answers.yml").read_text(encoding="utf-8"))
    owner = answers.get("development_backlog_project_owner", "lehard")
    number_text = answers.get("development_backlog_project_number", "1")
    if not BACKLOG_PROJECT_OWNER_RE.fullmatch(owner):
        raise ValueError("Copier answer development_backlog_project_owner must be a GitHub login")
    try:
        number = int(number_text)
    except ValueError as exc:
        raise ValueError("Copier answer development_backlog_project_number must be a positive integer") from exc
    if number < 1:
        raise ValueError("Copier answer development_backlog_project_number must be a positive integer")
    return owner, number


def expected_development_backlog_migration(
    config: dict[str, Any],
    *,
    project_owner: str = "lehard",
    project_number: int = 1,
) -> dict[str, Any] | None:
    """Return the sole bootstrap-owned addition permitted to project config."""
    existing = config.get("development_backlog")
    if isinstance(existing, dict):
        additions = {
            key: value
            for key, value in {"project_owner": project_owner, "project_number": project_number}.items()
            if key not in existing
        }
        if not additions:
            return None
        migrated = dict(config)
        migrated["development_backlog"] = {**existing, **additions}
        return migrated
    if existing is not None:
        return None
    project_slug = config.get("project_slug")
    if not isinstance(project_slug, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", project_slug):
        return None
    migrated = dict(config)
    migrated["development_backlog"] = {
        "repository": "lehard/development-backlog",
        "project_label": f"project:{project_slug}",
        "default_priority": "P2",
        "project_owner": project_owner,
        "project_number": project_number,
    }
    return migrated


def expected_process_health_migration(before: dict[str, Any]) -> dict[str, Any] | None:
    if "process_health" in before:
        return None
    migrated = dict(before)
    migrated["process_health"] = {
        "process_label": "process",
        "managed_label": "process:managed",
    }
    return migrated


def expected_platform_config_migrations(
    before: dict[str, Any], *, project_owner: str, project_number: int
) -> list[dict[str, Any]]:
    """Return every bounded, bootstrap-owned config migration from ``before``."""
    candidates = [before]
    for migrate in (
        lambda config: expected_development_backlog_migration(
            config, project_owner=project_owner, project_number=project_number
        ),
        expected_process_health_migration,
    ):
        for candidate in list(candidates):
            migrated = migrate(candidate)
            if migrated is not None:
                candidates.append(migrated)
    return candidates


def require_platform_config_contract(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    project_owner: str = "lehard",
    project_number: int = 1,
) -> None:
    if after in expected_platform_config_migrations(
        before, project_owner=project_owner, project_number=project_number
    ):
        return
    raise ValueError(
        "project-owned .dev-platform.toml changed beyond platform_version or the expected bounded platform migrations during guarded recopy"
    )


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
    paths = set(ALWAYS_PROJECT_OWNED_ROLLOUT_PATHS)
    if str(config.get("harness_mode", "platform")) == "project":
        paths.update(PROJECT_HARNESS_ROLLOUT_PATHS)
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


def normalize_baseline_bytes(relative: str, content: bytes) -> bytes:
    """Normalize the narrowly allowed formatting-only baseline drift."""
    if relative not in BASELINE_FORMAT_EQUIVALENT_PATHS:
        return content
    if YAML_BLOCK_SCALAR_RE.search(content):
        return content
    lines = content.splitlines()
    normalized: list[bytes] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = blank
    return b"\n".join(normalized) + (b"\n" if content.endswith((b"\n", b"\r")) else b"")


def baseline_path_fingerprint(path: Path, relative: str) -> tuple[str, str]:
    if path.is_file():
        content = normalize_baseline_bytes(relative, path.read_bytes())
        return ("file", hashlib.sha256(content).hexdigest())
    return path_fingerprint(path)


def git_tree_path_fingerprint(
    root: Path,
    treeish: str,
    relative: str,
    *,
    normalize_baseline: bool = False,
) -> tuple[str, str]:
    """Fingerprint one committed path without depending on the mutated worktree."""
    pathspec = relative.replace("\\", "/")
    listing = subprocess.run(
        ["git", "ls-tree", treeish, "--", pathspec],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if listing.returncode != 0:
        detail = listing.stderr.strip() or listing.stdout.strip() or f"exit {listing.returncode}"
        raise ValueError(f"could not inspect {treeish}:{pathspec}: {detail}")
    line = listing.stdout.strip()
    if not line:
        return ("missing", "")
    metadata, _, _listed_path = line.partition("\t")
    parts = metadata.split()
    if len(parts) < 3:
        raise ValueError(f"unexpected git ls-tree output for {treeish}:{pathspec}")
    mode, object_type, _sha = parts[:3]
    if object_type == "tree":
        return ("dir", "present")
    content = subprocess.run(
        ["git", "show", f"{treeish}:{pathspec}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if content.returncode != 0:
        detail = content.stderr.decode(errors="replace").strip() or f"exit {content.returncode}"
        raise ValueError(f"could not read {treeish}:{pathspec}: {detail}")
    if mode == "120000":
        return ("symlink", content.stdout.decode(errors="surrogateescape"))
    raw_content = content.stdout
    if normalize_baseline:
        raw_content = normalize_baseline_bytes(relative, raw_content)
    return ("file", hashlib.sha256(raw_content).hexdigest())


def ensure_platform_tag_available(tag: str, *, env: dict[str, str]) -> None:
    found = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        cwd=PLATFORM_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if found.returncode == 0:
        return
    fetched = subprocess.run(
        ["git", "fetch", "--quiet", "--depth=1", "origin", f"refs/tags/{tag}:refs/tags/{tag}"],
        cwd=PLATFORM_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if fetched.returncode != 0:
        detail = fetched.stderr.strip() or fetched.stdout.strip() or f"exit {fetched.returncode}"
        raise ValueError(f"could not fetch recorded platform baseline {tag}: {detail}")


def rendered_template_fingerprints(
    tag: str,
    answers_text: str,
    relatives: set[str],
    *,
    env: dict[str, str],
    baseline_equivalence: bool = False,
) -> dict[str, tuple[str, str]]:
    """Render an immutable template revision with the downstream's recorded answers.

    A Copier template path can contain Jinja, so comparing it directly with a
    rendered downstream path is not evidence that the downstream has not
    customized the file.  Render in an isolated directory instead.  Tasks are
    explicitly skipped: this is a read-only ownership proof, not adoption.
    """
    ensure_platform_tag_available(tag, env=env)
    with tempfile.TemporaryDirectory(prefix="dev-platform-rollout-baseline-") as temporary:
        root = Path(temporary)
        answers = root / "answers.yml"
        rendered = root / "rendered"
        answers.write_text(answers_text, encoding="utf-8")
        run(
            [
                "copier",
                "copy",
                "--trust",
                "--defaults",
                "--skip-tasks",
                "--vcs-ref",
                tag,
                "--data-file",
                str(answers),
                str(PLATFORM_ROOT),
                str(rendered),
            ],
            PLATFORM_ROOT,
            env=env,
        )
        return {
            relative: baseline_path_fingerprint(rendered / relative, relative)
            if baseline_equivalence
            else path_fingerprint(rendered / relative)
            for relative in relatives
        }


def baseline_equivalent_conflict_paths(
    project_root: Path,
    current_tag: str,
    relatives: set[str],
    *,
    env: dict[str, str],
    answers_text: str,
) -> set[str]:
    """Prove the committed downstream path still equals its recorded old template.

    The proof reads downstream HEAD, not the worktree after Copier has modified it.
    Missing/missing is a valid equivalence: there was no downstream customization
    at that path in the recorded baseline, so guarded recopy cannot erase one.
    """
    baseline = rendered_template_fingerprints(
        current_tag,
        answers_text,
        relatives,
        env=env,
        baseline_equivalence=True,
    )
    proven: set[str] = set()
    for relative in relatives:
        downstream = git_tree_path_fingerprint(
            project_root,
            "HEAD",
            relative,
            normalize_baseline=True,
        )
        if downstream == baseline[relative]:
            proven.add(relative)
    return proven


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


def require_paths_match_rendered_template(
    project_root: Path, expected: dict[str, tuple[str, str]]
) -> None:
    mismatched = sorted(
        relative
        for relative, fingerprint in expected.items()
        if path_fingerprint(project_root / relative) != fingerprint
    )
    if mismatched:
        raise ValueError(
            "baseline-equivalent conflict paths do not match the target template after recopy: "
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


def reconcile_task_intake_reference(project_root: Path) -> bool:
    """Add the one stable shared-intake pointer without replacing local rules.

    Root guidance is intentionally project-owned, so Copier cannot be expected
    to rewrite it during normal releases.  This migration is applicable only to
    already managed projects (those with a Development Backlog table), appends
    a bounded marked block once, and preserves every existing byte otherwise.
    """
    config = load_platform_config(project_root)
    if not isinstance(config.get("development_backlog"), dict):
        return False
    contract = project_root / TASK_INTAKE_REFERENCE
    if not contract.is_file():
        raise ValueError(f"updated managed project is missing {TASK_INTAKE_REFERENCE}")
    agents = project_root / "AGENTS.md"
    if not agents.is_file():
        raise ValueError("updated managed project is missing project-owned AGENTS.md")
    text = agents.read_text(encoding="utf-8")
    if TASK_INTAKE_REFERENCE_MARKER in text:
        return False
    block = (
        "\n\n"
        + TASK_INTAKE_REFERENCE_MARKER
        + "\n## Shared managed-task intake\n\n"
        + "For task authoring or execution, follow the platform-owned "
        + f"[managed task-intake contract]({TASK_INTAKE_REFERENCE}). "
        + "Fresh non-trivial execution establishes managed provenance before implementation; "
        + "explicit fixation remains authoring-only. Project/domain and module rules above remain in force.\n"
    )
    agents.write_text(text.rstrip("\n") + block, encoding="utf-8")
    print(f"Reconciled stable shared task-intake reference in {agents}")
    return True


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

    Copier replays the downstream diff from the recorded old template onto the
    new template. Recovery is safe when a project-owned snapshot is preserved,
    a narrowly reclaimed path already equals the target, or (platform harness)
    the committed downstream path still exactly equals its recorded old template.
    """

    mode = harness_mode(project_root)
    current_tag = load_answers(project_root)["_commit"]
    answers_before = (project_root / ".copier-answers.yml").read_text(encoding="utf-8")
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
        reconcile_task_intake_reference(project_root)
        project_owner, project_number = development_backlog_locator_answers(project_root)
        require_platform_config_contract(
            config_before,
            platform_config_contract(project_root),
            project_owner=project_owner,
            project_number=project_number,
        )
        return "update"

    owned = project_owned_paths(project_root)
    recoverable_owned = owned if mode == "project" else set()
    conflict_targets = {reject_target(path) for path in rejects}
    reclaimed_conflicts = conflict_targets & reclaimed_before
    baseline_conflicts = (
        baseline_equivalent_conflict_paths(
            project_root,
            current_tag,
            conflict_targets - reclaimed_conflicts,
            env=env,
            answers_text=answers_before,
        )
        if mode == "platform"
        else set()
    )
    unexpected = sorted(
        conflict_targets - recoverable_owned - reclaimed_conflicts - baseline_conflicts
    )
    if unexpected:
        detail = ", ".join(rejects[:10])
        detail += "; non-recoverable conflicts: " + ", ".join(unexpected[:10])
        raise ValueError("Copier left unresolved .rej files: " + detail)

    print(
        "Smart Copier update conflicted only on recoverable project-owned paths, "
        "proven reclaimed target paths, or platform paths still identical to their "
        "recorded baseline; retrying with guarded recopy.",
        flush=True,
    )
    reset_failed_copier_update(project_root)
    require_project_owned_snapshot(project_root, protected_before)
    require_reclaimed_platform_paths_match_template(project_root, reclaimed_conflicts)
    # Re-prove from committed HEAD after reset. This is intentionally independent
    # of the failed Copier worktree mutation.
    reproven = baseline_equivalent_conflict_paths(
        project_root,
        current_tag,
        baseline_conflicts,
        env=env,
        answers_text=answers_before,
    )
    if reproven != baseline_conflicts:
        missing = sorted(baseline_conflicts - reproven)
        raise ValueError(
            "baseline-equivalent rollout proof changed before recopy: "
            + ", ".join(missing[:10])
        )

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
    expected_target = rendered_template_fingerprints(
        version,
        answers_before,
        baseline_conflicts,
        env=env,
    )
    require_paths_match_rendered_template(project_root, expected_target)
    project_owner, project_number = development_backlog_locator_answers(project_root)
    require_platform_config_contract(
        config_before,
        platform_config_contract(project_root),
        project_owner=project_owner,
        project_number=project_number,
    )
    reconcile_task_intake_reference(project_root)
    if harness_mode(project_root) != mode:
        raise ValueError(f"guarded recopy changed harness_mode away from {mode}")
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


def stage_rollout_changes(project_root: Path) -> None:
    """Stage the Copier result before validation can create disposable outputs."""
    run(["git", "add", "-A"], project_root)
    staged = run(
        ["git", "diff", "--cached", "--quiet", "--"],
        project_root,
        capture=True,
        check=False,
    )
    if staged.returncode == 0:
        raise ValueError("Copier changed the recorded version but produced no repository diff")
    if staged.returncode != 1:
        detail = (staged.stderr or staged.stdout or f"exit {staged.returncode}").strip()
        raise ValueError(f"could not inspect staged rollout changes: {detail}")
    run(["git", "diff", "--cached", "--check", "--"], project_root)


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

    stage_rollout_changes(project_root)
    run_project_validation(project_root, base_branch)
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
