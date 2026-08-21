from __future__ import annotations

import argparse
import ast
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
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "dev-platform/checks.toml",
    "openspec/config.yaml",
    "docs/engineering/project-rules.md",
}

# These are names only: rollout never creates, reads, stages, or commits the
# corresponding artifacts. They exercise the effective ignore behavior that a
# Cuby-like repository commonly needs to keep local.
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

# Reviewed live project-harness shapes.  These fingerprints deliberately make
# compatibility opt-in by bytes, so a downstream edit cannot be overwritten by
# an apparently similar migration.
JARA_MERGE_TO_MAIN_SHA256 = "a201795ddc3785630e789e409e510a471a8b848699014a815f461a0a2a38d91d"
JARA_TEST_MERGE_TO_MAIN_SHA256 = "756c1b87df8c4abb2e4539785998e07e87bd6bf8f617cb3234908db5368537a4"
PLANNER_PROJECT_PUBLISH_SHA256 = "0bc3a4d169f41c6c8565e8f740ff92db51c7b8400a1aeaaa5bbcf5cbe1f1dfcb"
PLANNER_FINISH_TASK_SHA256 = "7f10a5f605becb5cfa77d32dfbe2a4987b69d52d78ad777cc6ae515f7142385c"

EXACT_HEAD_HELPER = '''# dev-platform:exact-head-publication-v1
from __future__ import annotations
import json
import subprocess
import time

def exact_pr(root, branch, base, env):
    head = subprocess.run(["git", "rev-parse", branch], cwd=root, text=True, capture_output=True, check=False)
    if head.returncode or not head.stdout.strip(): raise RuntimeError("local task head is unavailable")
    expected = head.stdout.strip()
    listed = subprocess.run(["gh", "pr", "list", "--state", "all", "--head", branch, "--base", base, "--limit", "100", "--json", "number,url,state,headRefOid,baseRefName,headRefName"], cwd=root, env=env, text=True, capture_output=True, check=False)
    if listed.returncode: raise RuntimeError("GitHub exact PR candidate list is unavailable")
    try: candidates = json.loads(listed.stdout)
    except json.JSONDecodeError as exc: raise RuntimeError("GitHub exact PR candidate list is invalid") from exc
    matches = [p for p in candidates if isinstance(p, dict) and p.get("baseRefName") == base and p.get("headRefName") == branch and p.get("headRefOid") == expected and p.get("state") in ("OPEN", "MERGED") and isinstance(p.get("number"), int)]
    if len(matches) > 1: raise RuntimeError("GitHub returned multiple exact PR candidates")
    return (matches[0] if matches else None), expected

def ensure_exact_pr(root, branch, base, env, title, body):
    current, expected = exact_pr(root, branch, base, env)
    if current: return current, expected
    made = subprocess.run(["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body], cwd=root, env=env, text=True, capture_output=True, check=False)
    current, expected = exact_pr(root, branch, base, env)
    if current and current.get("state") == "OPEN": return current, expected
    detail = made.stderr.strip() or made.stdout.strip() or "exact PR was not observable after creation"
    raise RuntimeError(detail)

ensure_exact_pr.exact_pr = exact_pr

def exact_state(root, pr, expected, env):
    view = subprocess.run(["gh", "pr", "view", str(pr["number"]), "--json", "state,headRefOid"], cwd=root, env=env, text=True, capture_output=True, check=False)
    try: payload = json.loads(view.stdout) if view.returncode == 0 else {}
    except json.JSONDecodeError: payload = {}
    return payload.get("state") == "MERGED" and payload.get("headRefOid") == expected

def wait_for_exact_merge(root, pr, expected, env, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if exact_state(root, pr, expected, env): return True
        time.sleep(2)
    return exact_state(root, pr, expected, env)

def check_exact_pr(root, pr, expected, env):
    state = subprocess.run(["gh", "pr", "view", str(pr["number"]), "--json", "headRefOid"], cwd=root, env=env, text=True, capture_output=True, check=False)
    try: head = json.loads(state.stdout).get("headRefOid") if state.returncode == 0 else None
    except json.JSONDecodeError: head = None
    if head != expected: raise RuntimeError("PR head changed from the validated exact head")
    checks = subprocess.run(["gh", "pr", "checks", str(pr["number"]), "--required", "--watch", "--fail-fast", "--interval", "5"], cwd=root, env=env, text=True, capture_output=True, check=False)
    if checks.returncode: raise RuntimeError(checks.stderr.strip() or checks.stdout.strip() or "required checks did not pass")

def merge_exact_pr(root, pr, expected, env, timeout=600):
    if exact_state(root, pr, expected, env): return
    attempts = (
        ["gh", "pr", "merge", str(pr["number"]), "--squash", "--match-head-commit", expected],
        ["gh", "pr", "merge", str(pr["number"]), "--auto", "--squash", "--match-head-commit", expected],
    )
    detail = "merge did not confirm exact head"
    for command in attempts:
        result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False)
        detail = result.stderr.strip() or result.stdout.strip() or detail
        if wait_for_exact_merge(root, pr, expected, env, timeout if result.returncode == 0 else min(timeout, 15)):
            return
        _, observed = exact_pr(root, pr["headRefName"], pr["baseRefName"], env)
        if observed != expected:
            raise RuntimeError("local task head changed while merge was being confirmed")
    raise RuntimeError(detail)
'''

JARA_OVERRIDE = '''\n# dev-platform:exact-head-publication-v1\nfrom exact_head_safety import exact_pr, exact_state, ensure_exact_pr, check_exact_pr, merge_exact_pr\ndef publish_branch_and_pr(worktree, branch, env):\n    run_git(worktree, "push", "-u", "origin", branch)\n    title = run_git(worktree, "log", "-1", "--pretty=%s").stdout.strip() or branch\n    try: ensure_exact_pr(worktree, branch, "main", env, title, "Published by Jara_Fin protected-main agent lifecycle after local validation.")\n    except RuntimeError as exc: raise MergeError(f"Could not create exact PR for {branch!r}: {exc}") from exc\ndef wait_for_pr_checks(worktree, branch, env):\n    try:\n        pr, head = exact_pr(worktree, branch, "main", env)\n        if not pr: raise RuntimeError("exact PR is absent")\n        if pr.get("state") != "MERGED": check_exact_pr(worktree, pr, head, env)\n        elif not exact_state(worktree, pr, head, env): raise RuntimeError("merged PR no longer proves the exact head")\n    except RuntimeError as exc: raise MergeError(f"Required exact PR checks did not pass: {exc}") from exc\ndef merge_pr(worktree, branch, env):\n    try:\n        pr, head = exact_pr(worktree, branch, "main", env)\n        if not pr: raise RuntimeError("exact PR is absent")\n        merge_exact_pr(worktree, pr, head, env)\n        delete_remote_branch(worktree, branch)\n    except RuntimeError as exc: raise MergeError(f"Exact protected merge failed: {exc}") from exc\n'''

PLANNER_OVERRIDE = '''\n# dev-platform:exact-head-publication-v1\nfrom exact_head_safety import ensure_exact_pr, check_exact_pr, merge_exact_pr\ndef publish_pr(root, remote, main_branch, title, body, merge_mode):\n    env = require_gh_env(root)\n    current = push_feature_branch(root, remote, main_branch)\n    title = title or run_git(["log", "-1", "--pretty=%s"], cwd=root).stdout.strip() or current\n    body = body or "Published by Planner Agent Lab after local validation and a fresh origin/main check."\n    try: pr, head = ensure_exact_pr(root, current, main_branch, env, title, body)\n    except RuntimeError as exc: raise SystemExit(f"Could not create exact Planner PR: {exc}") from exc\n    if merge_mode == "manual":\n        print("PR published for manual review; no merge attempted.")\n        return 0\n    try:\n        check_exact_pr(root, pr, head, env)\n        merge_exact_pr(root, pr, head, env)\n    except RuntimeError as exc: raise SystemExit(f"Exact Planner merge failed: {exc}") from exc\n    return 0\n'''
PLANNER_TERMINAL_OVERRIDE = '''\n# dev-platform:terminal-reconciliation-v1\nfrom managed_project_status import discover_source_issue\nfrom project_terminal_reconciliation import reconcile_if_exact_merged\n_legacy_main = main\ndef main():\n    root = current_worktree_root()\n    branch = current_branch(root)\n    source = discover_source_issue(root)\n    source_issue = source.reference if source is not None else None\n    try:\n        if reconcile_if_exact_merged(root, branch, source_issue):\n            print("Planner task terminal reconciliation completed without republishing.")\n            return 0\n        result = _legacy_main()\n        if reconcile_if_exact_merged(root, branch, source_issue):\n            print("Planner task terminal reconciliation completed after exact merge.")\n        return result\n    except Exception as exc:\n        raise SystemExit("Managed terminal reconciliation pending; rerun finish_task.py after restoring GitHub Project/Issue access: " + str(exc)) from exc\n'''

# These are the three strict subprocess mocks in the reviewed Jara regression
# source.  They are deliberately complete, exact replacements rather than a
# heuristic rewrite: removing the generated blocks must reconstruct the
# reviewed legacy bytes before a rerun is accepted.
JARA_TEST_MOCK_REPLACEMENTS = (
    (
        '''        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            calls.append(command)
            if command[:3] == ["gh", "pr", "merge"]:
                if "--auto" in command:
                    state["merged"] = True
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="Merge commits are not allowed on this repository")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now"} if state["merged"] else {"state": "OPEN"}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
        '''        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            calls.append(command)
            exact_head = "a" * 40
            exact_pr = {"number": 41, "url": "https://example.test/pr/41", "state": "OPEN", "headRefOid": exact_head, "baseRefName": "main", "headRefName": branch}
            if command[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(command, 0, stdout=exact_head + "\\n", stderr="")
            if command[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps([exact_pr]), stderr="")
            if command[:3] == ["gh", "pr", "merge"]:
                if "--auto" in command:
                    state["merged"] = True
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="Merge commits are not allowed on this repository")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now", "headRefOid": exact_head} if state["merged"] else {"state": "OPEN", "headRefOid": exact_head}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
    ),
    (
        '''    def test_non_zero_merge_exit_confirmed_as_merged_is_not_treated_as_failure(self) -> None:
        branch = "ready"
        calls: list[list[str]] = []

        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            calls.append(command)
            if command[:3] == ["gh", "pr", "merge"]:
                # gh reports a convenience/API error even though GitHub already merged server-side.
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="unexpected EOF")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now"}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
        '''    def test_non_zero_merge_exit_confirmed_as_merged_is_not_treated_as_failure(self) -> None:
        branch = "ready"
        calls: list[list[str]] = []
        state = {"merged": False}

        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            calls.append(command)
            exact_head = "b" * 40
            exact_pr = {"number": 42, "url": "https://example.test/pr/42", "state": "OPEN", "headRefOid": exact_head, "baseRefName": "main", "headRefName": branch}
            if command[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(command, 0, stdout=exact_head + "\\n", stderr="")
            if command[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps([exact_pr]), stderr="")
            if command[:3] == ["gh", "pr", "merge"]:
                # gh reports a convenience/API error even though GitHub already merged server-side.
                state["merged"] = True
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="unexpected EOF")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now", "headRefOid": exact_head} if state["merged"] else {"state": "OPEN", "headRefOid": exact_head}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
    ),
    (
        '''    def test_cleanup_failure_after_confirmed_merge_is_a_warning_not_a_failure(self) -> None:
        branch = "ready"

        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            if command[:3] == ["gh", "pr", "merge"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now"}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
        '''    def test_cleanup_failure_after_confirmed_merge_is_a_warning_not_a_failure(self) -> None:
        branch = "ready"
        state = {"merged": False}

        def fake_run(command, cwd=None, env=None, text=True, capture_output=True, check=False):
            exact_head = "c" * 40
            exact_pr = {"number": 43, "url": "https://example.test/pr/43", "state": "OPEN", "headRefOid": exact_head, "baseRefName": "main", "headRefName": branch}
            if command[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(command, 0, stdout=exact_head + "\\n", stderr="")
            if command[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps([exact_pr]), stderr="")
            if command[:3] == ["gh", "pr", "merge"]:
                state["merged"] = True
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[:3] == ["gh", "pr", "view"]:
                payload = {"state": "MERGED", "mergedAt": "now", "headRefOid": exact_head} if state["merged"] else {"state": "OPEN", "headRefOid": exact_head}
                return subprocess.CompletedProcess(command, 0, stdout=__import__("json").dumps(payload), stderr="")
''',
    ),
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


def is_cli_guard(test: ast.expr) -> bool:
    """Return whether ``test`` is the conventional direct-script guard."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False

    left, right = test.left, test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def unique_top_level_cli_guard_offset(source: str) -> int:
    """Find the one module-level CLI guard before which an override may run."""
    try:
        module = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: harness has invalid Python syntax; "
            "preserving harness bytes"
        ) from exc
    guards = [node for node in module.body if isinstance(node, ast.If) and is_cli_guard(node.test)]
    if len(guards) != 1:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: harness has no unique top-level CLI guard; "
            "preserving harness bytes"
        )
    return sum(len(line) for line in source.splitlines(keepends=True)[: guards[0].lineno - 1])


def install_pre_entrypoint_override(source: str, override: str) -> str:
    """Insert the reviewed override before, rather than after, the CLI guard."""
    offset = unique_top_level_cli_guard_offset(source)
    return source[:offset] + override + source[offset:]


def reviewed_legacy_source(
    source: str,
    expected_sha256: str,
    override: str,
) -> tuple[str, str]:
    """Return a reviewed source and its migration state without accepting drift.

    Version 1.4.34 wrote ``source.rstrip("\\n") + override``.  Recover the
    exact prior source only when the known suffix and one of the two possible
    original newline forms re-hash to the reviewed predicate.
    """
    if hashlib.sha256(source.encode("utf-8")).hexdigest() == expected_sha256:
        return source, "unmigrated"
    if EXACT_HEAD_MARKER not in source:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: unrecognized harness bytes; "
            "preserving harness bytes"
        )
    if source.count(EXACT_HEAD_MARKER) != 1 or not source.endswith(override):
        raise ValueError(
            "project-owned publication-safety compatibility blocker: incomplete migrated surface; "
            "preserving harness bytes"
        )
    stripped = source[: -len(override)]
    candidates = (stripped, stripped + "\n")
    matches = [
        candidate
        for candidate in candidates
        if hashlib.sha256(candidate.encode("utf-8")).hexdigest() == expected_sha256
    ]
    if len(matches) != 1:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: unrecognized harness bytes; "
            "preserving harness bytes"
        )
    return matches[0], "v1.4.34-append"


def reviewed_jara_test_source(source: str) -> tuple[str, str]:
    """Return the reviewed Jara test source and migration state.

    The companion test is project-owned.  Its active form is therefore
    accepted only when all three known generated replacements occur exactly
    once and reversing them recreates the reviewed legacy fingerprint.
    """
    if hashlib.sha256(source.encode("utf-8")).hexdigest() == JARA_TEST_MERGE_TO_MAIN_SHA256:
        return source, "unmigrated"
    legacy = source
    for original, migrated in JARA_TEST_MOCK_REPLACEMENTS:
        if legacy.count(migrated) != 1:
            raise ValueError(
                "project-owned publication-safety compatibility blocker: incomplete migrated regression test surface; "
                "preserving harness and test bytes"
            )
        legacy = legacy.replace(migrated, original)
    if hashlib.sha256(legacy.encode("utf-8")).hexdigest() != JARA_TEST_MERGE_TO_MAIN_SHA256:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: unrecognized regression test bytes; "
            "preserving harness and test bytes"
        )
    return legacy, "migrated"


def migrate_jara_test_source(source: str) -> str:
    migrated = source
    for original, replacement in JARA_TEST_MOCK_REPLACEMENTS:
        if migrated.count(original) != 1:
            raise ValueError(
                "project-owned publication-safety compatibility blocker: unrecognized regression test blocks; "
                "preserving harness and test bytes"
            )
        migrated = migrated.replace(original, replacement)
    return migrated


def migrate_project_publication_safety(project_root: Path, repository: str) -> bool:
    """Apply only reviewed Jara/Planner overrides, guarded by exact bytes."""
    if harness_mode(project_root) != "project":
        return False
    if repository == "lehard/Jara_Fin":
        target, expected, override = project_root / "scripts/merge_to_main.py", JARA_MERGE_TO_MAIN_SHA256, JARA_OVERRIDE
    elif repository == "lehard/planner-agent-lab":
        target, expected, override = project_root / "scripts/project_publish.py", PLANNER_PROJECT_PUBLISH_SHA256, PLANNER_OVERRIDE
    else:
        return False
    helper = project_root / "scripts/exact_head_safety.py"
    terminal_helper = project_root / "scripts/project_terminal_reconciliation.py"
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    helper_current = helper.read_text(encoding="utf-8") if helper.is_file() else None
    test_target = project_root / "scripts/tests/test_merge_to_main.py" if repository == "lehard/Jara_Fin" else None
    test_current = test_target.read_text(encoding="utf-8") if test_target and test_target.is_file() else ""

    harness_active = False
    if EXACT_HEAD_MARKER in current and not current.endswith(override):
        # This can only be the deterministic active form if removing the exact
        # known block reconstructs the reviewed source byte-for-byte.
        if helper_current != EXACT_HEAD_HELPER or current.count(override) != 1:
            raise ValueError(
                "project-owned publication-safety compatibility blocker: incomplete migrated surface; "
                "preserving harness bytes"
            )
        active = current.index(override)
        legacy = current[:active] + current[active + len(override):]
        if (
            hashlib.sha256(legacy.encode("utf-8")).hexdigest() == expected
            and current == install_pre_entrypoint_override(legacy, override)
        ):
            harness_active = True
        else:
            raise ValueError(
                "project-owned publication-safety compatibility blocker: unrecognized harness bytes; "
                "preserving harness bytes"
            )

    if helper_current is not None and helper_current != EXACT_HEAD_HELPER:
        raise ValueError(
            "project-owned publication-safety compatibility blocker: incomplete migrated surface; "
            "preserving harness bytes"
        )
    if not harness_active:
        legacy, state = reviewed_legacy_source(current, expected, override)
        if helper_current is not None and state == "unmigrated":
            raise ValueError(
                "project-owned publication-safety compatibility blocker: incomplete migrated surface; "
                "preserving harness bytes"
            )
        if state == "v1.4.34-append" and helper_current != EXACT_HEAD_HELPER:
            raise ValueError(
                "project-owned publication-safety compatibility blocker: incomplete migrated surface; "
                "preserving harness bytes"
            )
        migrated = install_pre_entrypoint_override(legacy, override)
    else:
        migrated = current

    test_migrated = test_current
    test_active = True
    if test_target is not None:
        _, test_state = reviewed_jara_test_source(test_current)
        test_active = test_state == "migrated"
        if not test_active:
            test_migrated = migrate_jara_test_source(test_current)

    terminal_changed = False
    finish_target = None
    finish_migrated = None
    if repository == "lehard/planner-agent-lab":
        finish_target = project_root / "scripts/finish_task.py"
        finish_current = finish_target.read_text(encoding="utf-8") if finish_target.is_file() else ""
        if TERMINAL_RECONCILIATION_MARKER not in finish_current:
            if hashlib.sha256(finish_current.encode("utf-8")).hexdigest() != PLANNER_FINISH_TASK_SHA256:
                raise ValueError(
                    "project-owned terminal-reconciliation compatibility blocker: unrecognized Planner finish_task bytes; "
                    "preserving harness bytes"
                )
            finish_migrated = install_pre_entrypoint_override(finish_current, PLANNER_TERMINAL_OVERRIDE)
            terminal_changed = True
        elif finish_current.count(PLANNER_TERMINAL_OVERRIDE) != 1:
            raise ValueError(
                "project-owned terminal-reconciliation compatibility blocker: incomplete migrated finish_task surface; "
                "preserving harness bytes"
            )

    # All failure-prone proof has completed before either downstream-owned
    # harness/test bytes or the helper is written.
    changed = not harness_active or not test_active or terminal_changed
    if changed:
        helper.write_text(EXACT_HEAD_HELPER, encoding="utf-8")
        target.write_text(migrated, encoding="utf-8")
        if test_target is not None:
            test_target.write_text(test_migrated, encoding="utf-8")
        if terminal_changed and finish_target is not None and finish_migrated is not None:
            finish_target.write_text(finish_migrated, encoding="utf-8")
            terminal_helper.write_bytes(
                (PLATFORM_ROOT / "template" / "scripts" / "project_terminal_reconciliation.py").read_bytes()
            )
    return changed


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
        require_project_owned_snapshot(project_root, protected_before)
        require_effective_ignore_coverage(project_root, ignore_coverage_before)
        reconcile_task_intake_reference(project_root)
        run_rendered_platform_bootstrap(project_root, env=env)
        require_project_owned_snapshot(
            project_root,
            protected_before,
            permitted_fingerprints=permitted_task_intake_migration(project_root, agents_before),
        )
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
    migrate_project_publication_safety(project_root, repository)
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
