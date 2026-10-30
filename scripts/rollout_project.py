from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
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
LEGACY_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validated_legacy_repository(legacy_repository: str) -> str:
    if not LEGACY_REPOSITORY_RE.fullmatch(legacy_repository):
        raise ValueError(f"legacy_repository must be owner/name; got: {legacy_repository!r}")
    return legacy_repository

# Files that remain downstream-owned for every harness mode.
ALWAYS_PROJECT_OWNED_ROLLOUT_PATHS = {
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "dev-platform/checks.toml",
    "openspec/config.yaml",
    "docs/engineering/project-rules.md",
    "docs/context",
}

# These are names only: rollout never creates, reads, stages, or commits the
# corresponding artifacts. They exercise the effective ignore behavior that a
# mature downstream repository commonly needs to keep local.
REPRESENTATIVE_IGNORE_PATHS = {
    ".env": "environment secrets",
    "config/provider-credentials.json": "provider credentials",
    "var/app.sqlite3": "database files",
    "node_modules/.package-lock.json": "dependency directories",
    "dist/assets/app.js": "build products",
    "tsconfig.tsbuildinfo": "TypeScript state",
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

# Project harnesses are intentionally not replaced by Copier.  A rollout may
# nevertheless advance a platform version only when the project-owned
# publication surface can prove the same exact-head invariant as the platform
# lifecycle.  This is a conformance gate, not an ownership grab: it never
# rewrites a project-owned harness whose shape it cannot prove safe.
PROJECT_PUBLICATION_SURFACE = (
    "scripts/project_publish.py",
    "scripts/finish_task.py",
    "scripts/merge_to_main.py",
    "scripts/exact_head_safety.py",
    "scripts/project_terminal_reconciliation.py",
)
EXACT_HEAD_MARKER = "dev-platform:exact-head-publication-v1"
TERMINAL_RECONCILIATION_MARKER = "dev-platform:terminal-reconciliation-v1"
UNSAFE_BRANCH_PR_VIEW_RE = re.compile(
    r"(?:gh\s+pr\s+view|[\[\(]\s*[\"']gh[\"']\s*,\s*[\"']pr[\"']\s*,\s*[\"']view[\"']\s*,\s*(?:branch|current|head_branch))"
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


def copier_render_data(operator_integration: bool) -> list[str]:
    """Return optional Copier render data without mutating the checkout."""
    if operator_integration:
        return ["--data", "operator_integration=true"]
    return []


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
        config = tomllib.load(fh)
    # The rollout reads only these keys of the project-owned configuration; the
    # project's own platform scripts validate the full schema after upgrade.
    for key in ("platform_version", "harness_mode"):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path} must set {key} to a non-empty string")
    return config


def load_platform_version(project_root: Path) -> str:
    config = load_platform_config(project_root)
    return config["platform_version"].strip()


def platform_config_contract(project_root: Path) -> dict[str, Any]:
    """Return project-owned config excluding release metadata allowed to advance."""
    config = load_platform_config(project_root)
    config.pop("platform_version", None)
    return config


def require_platform_config_contract(before: dict[str, Any], after: dict[str, Any], *, operator_integration: bool = False) -> None:
    """Keep Copier rollout from injecting operator-owned configuration.

    Existing operator integrations are project-owned/external and remain valid
    when unchanged; a portable rollout may only advance platform metadata,
    which ``platform_config_contract`` already removes before this comparison.
    """
    if after == before:
        return
    expected = dict(before)
    if operator_integration and "operator" not in expected:
        expected["operator"] = {"enabled": True, "config_env": "DEV_PLATFORM_OPERATOR_CONFIG"}
    if after == expected:
        return
    raise ValueError(
        "project-owned .dev-platform.toml changed beyond platform_version during guarded recopy"
    )


def harness_mode(project_root: Path) -> str:
    return load_platform_config(project_root)["harness_mode"]


def require_project_publication_safety_conformance(project_root: Path) -> None:
    """Fail closed unless a project harness proves exact-head publication safety.

    The gate is deliberately narrow and read-only.  It accepts the explicit
    conformance marker only together with the three mechanical safety signals:
    structured `headRefOid` verification, server-side expected-head guard, and
    a stable PR number/URL cursor.  A branch-name `gh pr view` shape remains a
    blocker even when those words appear elsewhere.  Unknown harnesses retain
    their bytes and receive an actionable rollout failure instead of a
    version-only PR that would falsely claim safety adoption.
    """
    if harness_mode(project_root) != "project":
        return
    found: list[tuple[str, str]] = []
    for relative in PROJECT_PUBLICATION_SURFACE:
        path = project_root / relative
        if path.is_file():
            found.append((relative, path.read_text(encoding="utf-8")))
    if not found:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: no recognized publication surface was found; "
            "preserving project harness bytes"
        )
    combined = "\n".join(text for _, text in found)
    if EXACT_HEAD_MARKER not in combined and UNSAFE_BRANCH_PR_VIEW_RE.search(combined):
        raise ValueError(
            "project-owned publication-safety compatibility blocker: branch-name-only PR lookup remains; "
            "preserving project harness bytes for an explicit exact-head migration"
        )
    signals = (EXACT_HEAD_MARKER, "headRefOid", "--match-head-commit")
    if (project_root / "scripts" / "finish_task.py").is_file():
        signals += (TERMINAL_RECONCILIATION_MARKER, "reconcile_if_exact_merged")
    missing = [signal for signal in signals if signal not in combined]
    if missing:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: unrecognized harness shape (missing "
            + ", ".join(missing)
            + "); preserving project harness bytes"
        )


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


def is_ignored(project_root: Path, relative: str) -> bool:
    """Return Git's effective ignore decision for a synthetic relative path."""
    result = run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
        project_root,
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
    raise ValueError(f"could not evaluate ignore coverage for {relative}: {detail}")


def snapshot_effective_ignore_coverage(project_root: Path) -> set[str]:
    """Capture only representative paths already ignored before rendering."""
    return {
        relative
        for relative in REPRESENTATIVE_IGNORE_PATHS
        if is_ignored(project_root, relative)
    }


def require_effective_ignore_coverage(
    project_root: Path, coverage_before: set[str]
) -> None:
    """Fail closed if rendering exposed an artifact class previously ignored."""
    lost = sorted(relative for relative in coverage_before if not is_ignored(project_root, relative))
    if lost:
        descriptions = ", ".join(
            f"{relative} ({REPRESENTATIVE_IGNORE_PATHS[relative]})" for relative in lost
        )
        raise ValueError(
            "managed rendering removed effective ignore coverage for: "
            + descriptions
            + "; inspect the project-owned .gitignore. No local artifacts were read, staged, or modified."
        )


def reject_target(reject_path: str) -> str:
    return reject_path[:-4] if reject_path.endswith(".rej") else reject_path


def project_owned_paths(project_root: Path) -> set[str]:
    config = load_platform_config(project_root)
    paths = set(ALWAYS_PROJECT_OWNED_ROLLOUT_PATHS)
    if config["harness_mode"] == "project":
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
        digest = hashlib.sha256()
        for entry in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
            relative = entry.relative_to(path).as_posix().encode("utf-8")
            if entry.is_symlink():
                digest.update(b"symlink\0" + relative + b"\0" + os.readlink(entry).encode("utf-8") + b"\0")
            elif entry.is_file():
                digest.update(b"file\0" + relative + b"\0" + entry.read_bytes() + b"\0")
            elif entry.is_dir():
                digest.update(b"dir\0" + relative + b"\0")
        return ("dir", digest.hexdigest())
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


def ensure_platform_tag_available(tag: str, *, env: dict[str, str], legacy_repository: str | None = None) -> None:
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
    if fetched.returncode == 0:
        return
    detail = fetched.stderr.strip() or fetched.stdout.strip() or f"exit {fetched.returncode}"
    if not legacy_repository:
        raise ValueError(f"could not fetch recorded platform baseline {tag}: {detail}")
    # A fresh-history canonical checkout never contains a pre-cutover tag; a
    # configured legacy repository (the pre-cutover history, preserved
    # verbatim under a different slug) is the only other place it can live.
    legacy_repository = validated_legacy_repository(legacy_repository)
    legacy_fetched = subprocess.run(
        ["git", "fetch", "--quiet", "--no-tags", "--depth=1", f"https://github.com/{legacy_repository}.git", f"refs/tags/{tag}:refs/tags/{tag}"],
        cwd=PLATFORM_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if legacy_fetched.returncode != 0:
        legacy_detail = legacy_fetched.stderr.strip() or legacy_fetched.stdout.strip() or f"exit {legacy_fetched.returncode}"
        raise ValueError(
            f"could not fetch recorded platform baseline {tag} from origin ({detail}) or legacy_repository={legacy_repository} ({legacy_detail})"
        )


def rendered_template_fingerprints(
    tag: str,
    answers_text: str,
    relatives: set[str],
    *,
    env: dict[str, str],
    baseline_equivalence: bool = False,
    legacy_repository: str | None = None,
    operator_integration: bool = False,
) -> dict[str, tuple[str, str]]:
    """Render an immutable template revision with the downstream's recorded answers.

    A Copier template path can contain Jinja, so comparing it directly with a
    rendered downstream path is not evidence that the downstream has not
    customized the file.  Render in an isolated directory instead.  Tasks are
    explicitly skipped: this is a read-only ownership proof, not adoption.
    """
    ensure_platform_tag_available(tag, env=env, legacy_repository=legacy_repository)
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
                *copier_render_data(operator_integration),
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
    legacy_repository: str | None = None,
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
        legacy_repository=legacy_repository,
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


def target_equivalent_conflict_paths(
    project_root: Path,
    version: str,
    relatives: set[str],
    *,
    env: dict[str, str],
    answers_text: str,
    legacy_repository: str | None = None,
    operator_integration: bool = False,
) -> set[str]:
    """Prove the committed downstream file already equals its target template render.

    Copier replays a downstream edit from the recorded old template and rejects a
    hunk whose lines the target template itself changed, even when the edit and
    the target agree (a customization the platform later absorbed into a recorded
    answer, such as a self-hosted CI runner).  When the committed file is
    byte-identical to the target render with the recorded answers, guarded recopy
    rewrites it to the same bytes, so no downstream content is lost.  The proof
    reads downstream HEAD; a path that is missing or not a regular file on either
    side is not proven, because recopy would create, delete or retype it.
    """
    if not relatives:
        return set()
    target = rendered_template_fingerprints(
        version,
        answers_text,
        relatives,
        env=env,
        legacy_repository=legacy_repository,
        operator_integration=operator_integration,
    )
    proven: set[str] = set()
    for relative in relatives:
        downstream = git_tree_path_fingerprint(project_root, "HEAD", relative)
        if downstream[0] == "file" and downstream == target[relative]:
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
            "baseline- or target-equivalent conflict paths do not match the target template after recopy: "
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
    project_root: Path,
    snapshot: dict[str, tuple[str, str]],
    *,
    permitted_fingerprints: dict[str, tuple[str, str]] | None = None,
) -> None:
    permitted_fingerprints = permitted_fingerprints or {}
    changed = [
        relative
        for relative, expected in snapshot.items()
        if path_fingerprint(project_root / relative)
        not in {expected, permitted_fingerprints.get(relative)}
    ]
    if changed:
        raise ValueError(
            "project-owned files changed during guarded Copier recopy: "
            + ", ".join(changed[:10])
        )


def canonical_task_intake_reference_text(text: str) -> str:
    """Return the sole permitted platform-owned addition to root guidance.

    The migration deliberately owns only its marked trailing block.  A marker
    in any other shape is not normalized in place because that would rewrite
    project-owned guidance; it must instead be resolved explicitly downstream.
    """
    marker_count = text.count(TASK_INTAKE_REFERENCE_MARKER)
    block = (
        "\n\n"
        + TASK_INTAKE_REFERENCE_MARKER
        + "\n## Shared managed-task intake\n\n"
        + "For task authoring or execution, follow the platform-owned "
        + f"[managed task-intake contract]({TASK_INTAKE_REFERENCE}). "
        + "Fresh non-trivial execution establishes managed provenance before implementation; "
        + "explicit fixation remains authoring-only. Project/domain and module rules above remain in force.\n"
    )
    if marker_count == 0:
        return text.rstrip("\n") + block
    if marker_count != 1:
        raise ValueError("project-owned AGENTS.md contains duplicate task-intake migration markers")
    marker_start = text.index(TASK_INTAKE_REFERENCE_MARKER)
    canonical = text[:marker_start].rstrip("\n") + block
    if text != canonical:
        raise ValueError("project-owned AGENTS.md contains a non-canonical task-intake migration block")
    return text


def task_intake_reference_fingerprint(text: str) -> tuple[str, str]:
    return ("file", hashlib.sha256(canonical_task_intake_reference_text(text).encode("utf-8")).hexdigest())


def permitted_task_intake_migration(
    project_root: Path, agents_before: str | None
) -> dict[str, tuple[str, str]]:
    """Allow exactly the deterministic migration, and only for managed projects."""
    if agents_before is None:
        return {}
    if not isinstance(load_platform_config(project_root).get("development_backlog"), dict):
        return {}
    return {"AGENTS.md": task_intake_reference_fingerprint(agents_before)}


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
    reconciled = canonical_task_intake_reference_text(text)
    if reconciled == text:
        return False
    agents.write_text(reconciled, encoding="utf-8")
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


def ensure_legacy_baseline_tag_available(
    project_root: Path,
    *,
    legacy_repository: str | None,
    version: str,
) -> None:
    """Bridge a project's pre-cutover Copier baseline tag into Copier's own
    mirror cache of its template source, so `copier update` can perform its
    normal 3-way transition even though a fresh-history canonical template
    never contains that historical tag.

    A no-op when `legacy_repository` is not configured, or when the
    project's recorded baseline is already resolvable in the mirror (for
    example a project already on a post-cutover release). Never mutates the
    canonical remote, the legacy remote, or any committed project state:
    the combined objects live only in this process's local Copier cache,
    and only Copier's own already-narrow `git worktree add <ref>` needs to
    resolve `ref` -- nothing else reads this cache's extra tag.
    """
    if not legacy_repository:
        return
    legacy_repository = validated_legacy_repository(legacy_repository)
    try:
        import copier._vcs as copier_vcs  # noqa: PLC0415 - optional, only needed here
    except ImportError as exc:
        raise ValueError("Copier is not installed; cannot bridge the legacy baseline") from exc

    answers = load_answers(project_root)
    try:
        url = copier_vcs.get_repo(answers["_src_path"])
        mirror = copier_vcs._get_or_create_mirror(url) if url is not None else None  # noqa: SLF001 - no public API for this cache
    except AttributeError as exc:
        raise ValueError("installed Copier version does not expose the expected mirror-cache internals") from exc
    if url is None:
        raise ValueError(f"cannot resolve Copier template source: {answers['_src_path']!r}")

    baseline = answers["_commit"]
    already_present = subprocess.run(
        ["git", "--git-dir", str(mirror), "rev-parse", "--verify", f"refs/tags/{baseline}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if already_present.returncode == 0:
        return

    # Copier's own mirror refresh (`git remote update --prune`) treats every
    # ref matching origin's fetch refspec as origin's to prune, so a plain
    # `+refs/*:refs/*` mirror refspec would delete the tag we are about to
    # add on the very next refresh. Narrow it first to exactly what this
    # rollout still needs from the real canonical remote.
    run(["git", "--git-dir", str(mirror), "config", "--unset-all", "remote.origin.fetch"], project_root, check=False)
    run(["git", "--git-dir", str(mirror), "config", "--add", "remote.origin.fetch", "+refs/heads/*:refs/heads/*"], project_root)
    run(
        ["git", "--git-dir", str(mirror), "config", "--add", "remote.origin.fetch", f"+refs/tags/{version}:refs/tags/{version}"],
        project_root,
    )
    run(
        [
            "git", "--git-dir", str(mirror), "fetch", "--no-tags",
            f"https://github.com/{legacy_repository}.git",
            f"refs/tags/{baseline}:refs/tags/{baseline}",
        ],
        project_root,
    )


RUNNER_WORKFLOWS = (
    (".github/workflows/dev-platform.yml", "platform-ci", "PLATFORM_CI_RUNS_ON_RE"),
    (".github/workflows/process-health-labels.yml", "provision", "PROVISION_RUNS_ON_RE"),
)
DEFAULT_RUNNER = "ubuntu-latest"


def platform_doctor_module() -> Any:
    """Load the shipped doctor so the rollout applies the exact runner-label rule CI will enforce."""
    scripts = PLATFORM_ROOT / "template" / "scripts"
    spec = importlib.util.spec_from_file_location("rollout_platform_doctor", scripts / "platform_doctor.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {scripts / 'platform_doctor.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
    return module


def parse_runner_labels(doctor: Any, value: str) -> list[str] | None:
    """Labels of a simple `runs-on` value, or None when it is not a plain label, quoted label or flow list of them."""
    value = value.strip()
    if not value or " #" in value:
        return None
    is_list = value.startswith("[") and value.endswith("]")
    if not is_list and "," in value:
        return None  # YAML reads an unbracketed `a, b` as the single string "a, b"
    labels: list[str] = []
    for item in (value[1:-1] if is_list else value).split(","):
        item = item.strip()
        quoted = len(item) >= 2 and item[0] == item[-1] and item[0] in {"'", '"'}
        if quoted:
            item = item[1:-1]
        elif item.lower() in doctor.YAML_PLAIN_SPECIAL_WORDS or not item[:1].isalpha():
            return None  # YAML would not read this unquoted scalar as the label string
        labels.append(item)
    entries, problems = doctor.ci_runner_label_problems(",".join(labels))
    if problems or DEFAULT_RUNNER in entries:
        return None  # `[ubuntu-latest]` is the hosted runner in list form, not a self-hosted label
    return entries


def runner_migration_block(repository: str, relative: str, found: str, action: str) -> ValueError:
    return ValueError(
        f"{repository}: {relative}: {found}. The target release records the platform CI runner as the Copier "
        f"answers ci_runner/ci_runner_labels, and this rollout will not replace it with github-hosted. "
        f"Next action: {action}. The default branch was not changed."
    )


def migrate_ci_runner_answers(
    project_root: Path,
    repository: str,
    current_tag: str,
    version: str,
    *,
    env: dict[str, str],
    legacy_repository: str | None = None,
) -> str:
    """Carry a hand-edited platform CI runner into the Copier answers, or stop, before `copier update`.

    Returns `skipped` (not applicable), `default` (every present runner is ubuntu-latest) or `migrated`.
    The migration reverts only the `runs-on` value to the baseline and records the answers in one rollout
    branch commit, so Copier replays no downstream diff on those files; this is identical for both
    harness modes and needs no recopy.
    """
    answers_path = project_root / ".copier-answers.yml"
    answers_text = answers_path.read_text(encoding="utf-8")
    answers = parse_answers(answers_text)
    if "ci_runner" in answers:
        return "skipped"
    ensure_platform_tag_available(version, env=env, legacy_repository=legacy_repository)
    target_copier = subprocess.run(
        ["git", "show", f"{version}:copier.yml"], cwd=PLATFORM_ROOT, text=True, capture_output=True, check=False
    )
    if target_copier.returncode != 0:
        raise ValueError(f"could not read copier.yml of target {version}: {target_copier.stderr.strip()}")
    if not re.search(r"^ci_runner:\s*$", target_copier.stdout, re.MULTILINE):
        return "skipped"
    scm_provider = answers.get("scm_provider")
    if scm_provider is None:
        raise ValueError(
            f"{repository}: .copier-answers.yml records no scm_provider answer, so the rollout cannot tell whether the "
            "platform CI runner applies. Next action: record scm_provider: github (or gitlab) in .copier-answers.yml "
            "on the project's default branch and rerun the rollout. The default branch was not changed."
        )
    if scm_provider != "github":
        return "skipped"

    doctor = platform_doctor_module()
    found: dict[str, tuple[str, re.Match[str], str]] = {}
    for relative, job, regex_name in RUNNER_WORKFLOWS:
        path = project_root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        match = getattr(doctor, regex_name).search(text)
        if not match:
            raise runner_migration_block(
                repository, relative,
                f"job {job} has no runs-on the rollout can read",
                f"restore the platform-rendered {job} job with a `runs-on:` line in {relative} (it is platform-owned) "
                "and rerun the rollout",
            )
        found[relative] = (job, match, text)
    custom = {
        relative: item for relative, item in found.items()
        if item[1].group(1).strip("'\"") != DEFAULT_RUNNER
    }
    if not custom:
        return "default"

    labels_by_file: dict[str, list[str]] = {}
    for relative, (job, match, _text) in custom.items():
        value = match.group(1)
        labels = parse_runner_labels(doctor, value)
        if labels is None:
            raise runner_migration_block(
                repository, relative,
                f"job {job} has runs-on {value!r}, which is not a plain label or a list of plain labels",
                f"keep {relative} equal to the platform render with `runs-on: {DEFAULT_RUNNER}` and record the runner "
                "yourself as ci_runner: self-hosted and ci_runner_labels: <comma-separated labels> in "
                ".copier-answers.yml on the project's default branch, or move the custom runner out of the "
                "platform-owned workflow; then rerun the rollout",
            )
        labels_by_file[relative] = labels
    distinct = {tuple(labels) for labels in labels_by_file.values()}
    if len(distinct) != 1 or len(custom) != len(found):
        raise runner_migration_block(
            repository, sorted(custom)[0],
            "the platform CI runners disagree: "
            + ", ".join(f"{relative} job {job} uses {match.group(1)!r}" for relative, (job, match, _t) in sorted(found.items())),
            "give platform-ci and provision the same runner (or both ubuntu-latest) and rerun the rollout",
        )
    labels = list(distinct.pop())

    restored: dict[str, str] = {}
    for relative, (_job, match, text) in custom.items():
        restored[relative] = text[: match.start(1)] + DEFAULT_RUNNER + text[match.end(1):]
    baseline = rendered_template_fingerprints(
        current_tag, answers_text, set(restored), env=env, baseline_equivalence=True, legacy_repository=legacy_repository
    )
    for relative, text in restored.items():
        digest = hashlib.sha256(normalize_baseline_bytes(relative, text.encode("utf-8"))).hexdigest()
        if baseline[relative] != ("file", digest):
            raise runner_migration_block(
                repository, relative,
                f"the runner is {custom[relative][1].group(1)!r} but the file also differs from the {current_tag} platform render",
                f"remove the other edits from {relative} (it is platform-owned) so that only runs-on differs, or "
                "record ci_runner/ci_runner_labels yourself and resolve the file by hand; then rerun the rollout",
            )

    for relative, text in restored.items():
        (project_root / relative).write_text(text, encoding="utf-8")
    separator = "" if answers_text.endswith("\n") else "\n"
    answers_path.write_text(
        answers_text + separator + "ci_runner: self-hosted\n" + f"ci_runner_labels: {json.dumps(','.join(labels))}\n",
        encoding="utf-8",
    )
    run(["git", "add", ".copier-answers.yml", *sorted(restored)], project_root)
    run(["git", "commit", "-m", "chore: record the platform CI runner as Copier answers before the dev-platform update"], project_root)
    ensure_clean(project_root)
    print(f"Migrated hand-edited CI runner {labels} into ci_runner/ci_runner_labels answers", flush=True)
    return "migrated"


def copier_update_with_guarded_recopy(
    project_root: Path,
    version: str,
    *,
    env: dict[str, str],
    legacy_repository: str | None = None,
    operator_integration: bool = False,
) -> str:
    """Run smart update, falling back to recopy only for proven-safe conflicts.

    Copier replays the downstream diff from the recorded old template onto the
    new template. Recovery is safe when a project-owned snapshot is preserved,
    a narrowly reclaimed path already equals the target, or (platform harness)
    the committed downstream path still exactly equals its recorded old template
    or already exactly equals its target render.
    """

    mode = harness_mode(project_root)
    current_tag = load_answers(project_root)["_commit"]
    answers_before = (project_root / ".copier-answers.yml").read_text(encoding="utf-8")
    config_before = platform_config_contract(project_root)
    protected_before = snapshot_existing_project_owned(project_root)
    ignore_coverage_before = snapshot_effective_ignore_coverage(project_root)
    agents_before = (
        (project_root / "AGENTS.md").read_text(encoding="utf-8")
        if (project_root / "AGENTS.md").is_file()
        else None
    )
    reclaimed_before = {
        relative
        for relative in RECLAIMED_PLATFORM_ROLLOUT_PATHS
        if reclaimed_platform_path_matches_template(project_root, relative)
    }

    ensure_legacy_baseline_tag_available(project_root, legacy_repository=legacy_repository, version=version)
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
            *copier_render_data(operator_integration),
        ],
        project_root,
        env=env,
    )
    rejects = find_reject_files(project_root)
    if not rejects:
        require_project_owned_snapshot(project_root, protected_before)
        require_effective_ignore_coverage(project_root, ignore_coverage_before)
        reconcile_task_intake_reference(project_root)
        run_rendered_platform_bootstrap(project_root, env=env)
        require_project_owned_snapshot(
            project_root,
            protected_before,
            permitted_fingerprints=permitted_task_intake_migration(project_root, agents_before),
        )
        require_platform_config_contract(config_before, platform_config_contract(project_root), operator_integration=operator_integration)
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
            legacy_repository=legacy_repository,
        )
        if mode == "platform"
        else set()
    )
    target_conflicts = (
        target_equivalent_conflict_paths(
            project_root,
            version,
            conflict_targets - reclaimed_conflicts - baseline_conflicts,
            env=env,
            answers_text=answers_before,
            legacy_repository=legacy_repository,
            operator_integration=operator_integration,
        )
        if mode == "platform"
        else set()
    )
    unexpected = sorted(
        conflict_targets - recoverable_owned - reclaimed_conflicts - baseline_conflicts - target_conflicts
    )
    if unexpected:
        detail = ", ".join(rejects[:10])
        detail += "; non-recoverable conflicts: " + ", ".join(unexpected[:10])
        raise ValueError("Copier left unresolved .rej files: " + detail)

    print(
        "Smart Copier update conflicted only on recoverable project-owned paths, "
        "proven reclaimed target paths, or platform paths still identical to their "
        "recorded baseline or already identical to the target render; retrying with "
        "guarded recopy.",
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
        legacy_repository=legacy_repository,
    )
    if reproven != baseline_conflicts:
        missing = sorted(baseline_conflicts - reproven)
        raise ValueError(
            "baseline-equivalent rollout proof changed before recopy: "
            + ", ".join(missing[:10])
        )
    retarget = target_equivalent_conflict_paths(
        project_root,
        version,
        target_conflicts,
        env=env,
        answers_text=answers_before,
        legacy_repository=legacy_repository,
        operator_integration=operator_integration,
    )
    if retarget != target_conflicts:
        missing = sorted(target_conflicts - retarget)
        raise ValueError(
            "target-equivalent rollout proof changed before recopy: "
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
            *copier_render_data(operator_integration),
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
    require_project_owned_snapshot(project_root, protected_before)
    require_effective_ignore_coverage(project_root, ignore_coverage_before)
    reconcile_task_intake_reference(project_root)
    run_rendered_platform_bootstrap(project_root, env=env)
    require_project_owned_snapshot(
        project_root,
        protected_before,
        permitted_fingerprints=permitted_task_intake_migration(project_root, agents_before),
    )
    require_reclaimed_platform_paths_match_template(project_root, reclaimed_conflicts)
    expected_target = rendered_template_fingerprints(
        version,
        answers_before,
        baseline_conflicts | target_conflicts,
        env=env,
        operator_integration=operator_integration,
    )
    require_paths_match_rendered_template(project_root, expected_target)
    require_platform_config_contract(config_before, platform_config_contract(project_root), operator_integration=operator_integration)
    if harness_mode(project_root) != mode:
        raise ValueError(f"guarded recopy changed harness_mode away from {mode}")
    return "guarded-recopy"


def validate_platform_installation(project_root: Path) -> None:
    """Validate only platform-owned compatibility of a rendered installation.

    This deliberately stops before the rendered check selector. Product
    verification belongs to the downstream repository's normal CI, while this
    reusable gate proves the Copier result has the platform surfaces needed to
    reach that CI safely.
    """
    rejects = find_reject_files(project_root)
    if rejects:
        raise ValueError("Copier left unresolved .rej files: " + ", ".join(rejects[:10]))
    run(["git", "diff", "--check", "--"], project_root)
    run(["git", "diff", "--cached", "--check", "--"], project_root)

    doctor = project_root / "scripts" / "platform_doctor.py"
    if not doctor.exists():
        raise ValueError("updated project is missing scripts/platform_doctor.py")
    run(["python3", str(doctor)], project_root)


def run_project_validation(project_root: Path, base_branch: str) -> None:
    """Validate the rendered Dev Platform Harness before opening a rollout PR.

    ``base_branch`` remains part of the public rollout helper signature. The
    platform installation checks themselves are branch-independent so release
    candidate validation can reuse them verbatim.
    """
    validate_platform_installation(project_root)
    print(
        "Rollout validated Dev Platform Harness compatibility; downstream rollout PR CI verifies product behavior.",
        flush=True,
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
    legacy_repository: str | None = None,
    operator_integration: bool = False,
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

    migrate_ci_runner_answers(
        project_root,
        repository,
        current_tag,
        version,
        env=private_source_git_env(),
        legacy_repository=legacy_repository,
    )
    strategy = copier_update_with_guarded_recopy(
        project_root,
        version,
        env=private_source_git_env(),
        legacy_repository=legacy_repository,
        operator_integration=operator_integration,
    )
    normalize_copier_answers(project_root)

    updated = load_answers(project_root)
    if updated["_commit"] != version:
        raise ValueError(
            f"Copier recorded {updated['_commit']!r}, expected exact target {version!r}"
        )
    require_version_coherence(project_root, version)
    require_project_publication_safety_conformance(project_root)

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
    parser.add_argument("--operator-integration", action="store_true", help="Enable the generic environment-backed operator integration for this managed rollout.")
    parser.add_argument(
        "--legacy-repository",
        default=None,
        help=(
            "Optional owner/name of the preserved pre-cutover platform history "
            "(see docs/managed-rollout.md). When set, a project still on a "
            "baseline tag the fresh-history canonical repository no longer "
            "contains can still be rolled out."
        ),
    )
    args = parser.parse_args()
    try:
        return apply_rollout(
            args.project_root,
            args.repository,
            args.version,
            args.base_branch,
            args.output,
            legacy_repository=args.legacy_repository,
            operator_integration=args.operator_integration,
        )
    except ValueError as exc:
        print(f"Managed rollout: BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
