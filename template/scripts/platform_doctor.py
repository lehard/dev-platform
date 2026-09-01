from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from _platform_common import SharedWorkspaceError, harness_mode, read_platform_config
from shared_workspace import audit as audit_shared_workspace

REQUIRED_COMMON = ["AGENTS.md", "CLAUDE.md", ".dev-platform.toml", "dev-platform/checks.toml", "docs/engineering/openspec-workflow.md", "docs/engineering/task-intake.md", "scripts/dev.py", "scripts/shared_workspace.py", "scripts/managed_task.py", "scripts/managed_project_status.py", "scripts/start_managed_task.py", "scripts/execute_managed_task.py", "scripts/select_checks.py", "scripts/project_sync.py", "scripts/project_publish.py", "scripts/start_task.py", "scripts/finish_task.py", "scripts/reconcile_task.py", "scripts/openspec_lifecycle.py", "scripts/independent_review.py", "scripts/agent_friction.py", "scripts/agent_doctor.py", "scripts/model_routing.py"]
REQUIRED_MULTI_AGENT_PLATFORM = ["scripts/agent_board.py", "scripts/start_worktree.py", "scripts/worktree_cleanup.py", "scripts/git_hooks/pre-commit", "scripts/git_hooks/pre-merge-commit"]
VERIFY_CANDIDATES = [".codex/skills/openspec-verify-change/SKILL.md", ".claude/skills/openspec-verify-change/SKILL.md", ".cursor/skills/openspec-verify-change/SKILL.md"]
IGNORED_CONFLICT_DIRS = {".git", ".claude", ".codex", "node_modules", ".venv", "venv"}
SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TOP_LEVEL_PUSH_RE = re.compile(r"(?m)^  push:\s*$")
TOP_LEVEL_PR_RE = re.compile(r"(?m)^  pull_request:\s*$")
BACKLOG_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BACKLOG_PROJECT_LABEL_RE = re.compile(r"^project:[A-Za-z0-9_.-]+$")
BACKLOG_PRIORITY_RE = re.compile(r"^P[0-3]$")
BACKLOG_PROJECT_OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")


def ok(label: str) -> None: print(f"[ok]   {label}")
def warn(label: str) -> None: print(f"[warn] {label}")
def fail(label: str) -> None: print(f"[fail] {label}")


def version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else None


def copier_commit(root: Path) -> str | None:
    answers = root / ".copier-answers.yml"
    if not answers.exists():
        return None
    for line in answers.read_text(encoding="utf-8").splitlines():
        if line.startswith("_commit:"):
            value = line.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def find_update_conflicts(root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*.rej"):
        if any(part in IGNORED_CONFLICT_DIRS for part in path.relative_to(root).parts):
            continue
        issues.append(str(path.relative_to(root)))
    for args in (["diff", "--check", "--"], ["diff", "--cached", "--check", "--"]):
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            if "leftover conflict marker" in line.lower():
                issues.append(line.strip())
    return sorted(set(issues))


def check_tool_version(root: Path, tool: str, config: dict, failures: list[int], required_when_present: bool = True) -> None:
    minimum = str(config.get("min_version", ""))
    tested = str(config.get("tested_version", minimum))
    executable = shutil.which(tool)
    if not executable:
        warn(f"{tool} is not installed on this machine")
        return
    result = subprocess.run([executable, "--version"], cwd=root, text=True, capture_output=True)
    parsed = version_tuple((result.stdout or result.stderr).strip())
    minimum_tuple = version_tuple(minimum)
    tested_tuple = version_tuple(tested)
    if parsed and minimum_tuple and parsed < minimum_tuple:
        message = f"{tool} {'.'.join(map(str, parsed))} is below minimum {minimum}"
        if required_when_present:
            fail(message); failures[0] += 1
        else:
            warn(message)
    elif parsed:
        ok(f"{tool} {'.'.join(map(str, parsed))} installed (minimum {minimum})")
        if tested_tuple and parsed > tested_tuple:
            warn(f"{tool} is newer than platform-tested version {tested}; run upgrade smoke checks before adopting it")
    else:
        warn(f"{tool} version could not be parsed")


def check_rendered_workflow_mode(root: Path, config: dict, failures: list[int]) -> None:
    """Detect a stale Copier render after a publication-mode answer changes.

    Copier can preserve a previously rendered conditional block as a downstream
    customization when `.copier-answers.yml` is changed by hand. The workflow is
    executable safety policy, so configuration and rendered triggers must agree.
    """
    workflow = root / ".github" / "workflows" / "dev-platform.yml"
    if not workflow.exists():
        fail("missing .github/workflows/dev-platform.yml"); failures[0] += 1
        return
    text = workflow.read_text(encoding="utf-8")
    if not TOP_LEVEL_PR_RE.search(text):
        fail("dev-platform workflow is missing the pull_request gate"); failures[0] += 1
    mode = str(config.get("publish_mode", "pr"))
    has_push = bool(TOP_LEVEL_PUSH_RE.search(text))
    if mode == "direct" and not has_push:
        fail("publish_mode=direct but rendered dev-platform workflow has no main push health trigger"); failures[0] += 1
    elif mode == "pr" and has_push:
        fail("publish_mode=pr but rendered dev-platform workflow still has a main push trigger; re-render/reconcile the workflow")
        failures[0] += 1
    elif mode not in {"direct", "pr"}:
        fail(f"unknown publish_mode={mode!r}; expected 'direct' or 'pr'"); failures[0] += 1
    else:
        ok(f"rendered workflow agrees with publish_mode={mode}")


def check_development_backlog_config(config: dict, failures: list[int]) -> None:
    """Accept pre-authoring renders while rejecting a partially configured authoring contract."""
    backlog = config.get("development_backlog")
    if backlog is None:
        warn("Development Backlog authoring is not configured (compatible with pre-authoring renders)")
        return
    if not isinstance(backlog, dict):
        fail("development_backlog must be a TOML table"); failures[0] += 1
        return
    before = failures[0]
    repository = backlog.get("repository")
    project_label = backlog.get("project_label")
    priority = backlog.get("default_priority")
    project_owner = backlog.get("project_owner")
    project_number = backlog.get("project_number")
    if not isinstance(repository, str) or not BACKLOG_REPOSITORY_RE.fullmatch(repository):
        fail("development_backlog.repository must be owner/name"); failures[0] += 1
    if not isinstance(project_label, str) or not BACKLOG_PROJECT_LABEL_RE.fullmatch(project_label):
        fail("development_backlog.project_label must be project:<slug>"); failures[0] += 1
    if not isinstance(priority, str) or not BACKLOG_PRIORITY_RE.fullmatch(priority):
        fail("development_backlog.default_priority must be P0, P1, P2 or P3"); failures[0] += 1
    if not isinstance(project_owner, str) or not BACKLOG_PROJECT_OWNER_RE.fullmatch(project_owner):
        fail("development_backlog.project_owner must be a GitHub login"); failures[0] += 1
    if isinstance(project_number, bool) or not isinstance(project_number, int) or project_number < 1:
        fail("development_backlog.project_number must be a positive integer"); failures[0] += 1
    if failures[0] == before:
        ok("Development Backlog authoring configuration is valid")


def check_task_intake_reference(root: Path, config: dict, failures: list[int]) -> None:
    """Require managed repositories to expose the updateable intake contract."""
    if not isinstance(config.get("development_backlog"), dict):
        return
    agents = root / "AGENTS.md"
    try:
        text = agents.read_text(encoding="utf-8")
    except OSError:
        return
    if "docs/engineering/task-intake.md" not in text:
        warn("managed repository AGENTS.md lacks the shared docs/engineering/task-intake.md reference; run a reviewed platform rollout migration")
    else:
        ok("shared managed task-intake reference is present")


REQUIRED_TASK_START_SYMBOLS = ("StartedTask", "start_task", "cleanup_started_task", "admit_task", "admission_reason")
REQUIRED_STARTED_TASK_FIELDS = {"profile", "branch", "task_root", "board_id"}
# start_task.py's own transitive imports. A real doctor process only ever
# probes one project's scripts/ directory, so relying on whatever these
# happen to already be in sys.modules is harmless there -- but the probe
# itself must not silently reuse a stale/foreign copy cached from a
# different scripts/ directory (for example under repeated in-process
# testing), so they are forced to reimport fresh from this exact root.
TASK_START_DEPENDENCY_MODULES = ("_platform_common", "rollout_preflight", "start_worktree")


def check_task_start_contract(root: Path, config: dict, harness: str, failures: list[int]) -> None:
    """Import the rendered scripts/start_task.py and probe its public surface.

    File-presence checking alone lets a downstream project keep a stale or
    hand-patched start_task.py that still exists on disk but no longer
    satisfies the callable interface (StartedTask, start_task,
    cleanup_started_task, admit_task, admission_reason) that
    scripts/start_managed_task.py imports directly. That mismatch used to
    surface as a crash mid managed-intake, before package discovery, instead
    of here.
    """
    if harness != "platform":
        return  # the contract only governs the platform-owned managed-intake entrypoint
    if str(config.get("platform_version", "")) == "source":
        return  # source checkout re-executes the template module as a CLI shim, not an importable API
    path = root / "scripts" / "start_task.py"
    if not path.exists():
        return  # already reported by the required-files presence check
    scripts_dir = str(path.parent)
    module_name = "_platform_doctor_start_task_probe"
    probe_module_names = (module_name, *TASK_START_DEPENDENCY_MODULES)
    saved_modules = {name: sys.modules.pop(name) for name in probe_module_names if name in sys.modules}
    path_inserted = scripts_dir not in sys.path
    if path_inserted:
        sys.path.insert(0, scripts_dir)
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            fail("scripts/start_task.py could not be loaded for a task-start contract probe"); failures[0] += 1
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            fail(f"scripts/start_task.py failed to import: {exc}"); failures[0] += 1
            return
        missing = [name for name in REQUIRED_TASK_START_SYMBOLS if not hasattr(module, name)]
        if missing:
            fail("scripts/start_task.py is missing the managed-intake task-start contract: " + ", ".join(missing))
            failures[0] += 1
            return
        uncallable = [name for name in REQUIRED_TASK_START_SYMBOLS[1:] if not callable(getattr(module, name))]
        if uncallable:
            fail("scripts/start_task.py task-start contract symbol(s) are not callable: " + ", ".join(uncallable))
            failures[0] += 1
            return
        # Probe the real keyword contract managed intake relies on (for
        # example scripts/start_task.py's own `StartedTask(profile=prof,
        # branch=main_branch, task_root=root)` with no board_id for
        # light/standard) rather than requiring StartedTask to literally be
        # a @dataclass -- an equally compatible plain class or namedtuple
        # must not be flagged incompatible.
        try:
            probe = module.StartedTask(profile="probe", branch="probe", task_root=Path("/probe"))
        except TypeError as exc:
            fail(f"scripts/start_task.py's StartedTask does not accept the managed-intake keyword contract (profile, branch, task_root, optional board_id): {exc}")
            failures[0] += 1
            return
        missing_fields = sorted(name for name in REQUIRED_STARTED_TASK_FIELDS if not hasattr(probe, name))
        if missing_fields:
            fail("scripts/start_task.py's StartedTask is missing field(s): " + ", ".join(missing_fields))
            failures[0] += 1
            return
        ok("scripts/start_task.py satisfies the managed-intake task-start contract")
    finally:
        if path_inserted:
            sys.path.remove(scripts_dir)
        for name in probe_module_names:
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)


def github_hosted_actions_runner(environ: dict[str, str] | None = None) -> bool:
    """Recognize only the Actions environment without local group topology."""
    environ = os.environ if environ is None else environ
    return (
        environ.get("GITHUB_ACTIONS", "").lower() == "true"
        and environ.get("RUNNER_ENVIRONMENT", "").lower() == "github-hosted"
    )


def check_shared_workspace(root: Path, failures: list[int]) -> None:
    """Doctor is diagnostic-only; lifecycle preflights perform bounded repair."""
    if github_hosted_actions_runner():
        warn(
            "GitHub-hosted Actions runner detected; shared-workspace group/setgid "
            "topology is unavailable, so permission enforcement is advisory"
        )
        return
    try:
        group, findings = audit_shared_workspace(root, fix=False)
    except SharedWorkspaceError as exc:
        fail(str(exc)); failures[0] += 1
        return
    if group is None:
        warn("shared-workspace POSIX enforcement is unavailable; no permission changes were attempted")
        return
    if findings:
        for finding in findings[:10]:
            fail(f"shared workspace {finding.path}: {finding.message}")
        if len(findings) > 10:
            fail(f"{len(findings) - 10} additional shared-workspace permission problem(s)")
        failures[0] += 1
    else:
        ok(f"shared workspace group contract is valid for {group.name} ({group.source})")


def check_platform_check_contract(root: Path, config: dict, harness: str) -> None:
    """Report latent empty mappings without making unrelated scopes fail doctor."""
    if harness != "platform":
        return
    try:
        relative = str(config.get("paths", {}).get("checks", "dev-platform/checks.toml"))
        with (root / relative).open("rb") as handle:
            checks_config = tomllib.load(handle)
        checks = checks_config.get("checks", {})
        empty_groups = sorted(
            str(check_id) for check_id, rule in checks.items()
            if isinstance(rule, dict) and not rule.get("commands", [])
        ) if isinstance(checks, dict) else []
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warn(f"could not inspect platform check contract: {exc}")
        return
    if empty_groups:
        warn(
            "platform check group(s) currently have no executable commands: "
            + ", ".join(empty_groups)
            + "; an affected scope will be blocked by select_checks.py"
        )
    else:
        ok("platform check mappings have executable commands")


def main() -> int:
    root = Path.cwd().resolve()
    failures = [0]
    config = read_platform_config(root)
    check_development_backlog_config(config, failures)
    check_task_intake_reference(root, config, failures)
    workflow_profile = str(config.get("workflow_profile", "standard"))
    harness = harness_mode(config)
    if harness not in {"platform", "project"}:
        fail(f"unknown harness_mode={harness!r}; expected 'platform' or 'project'"); failures[0] += 1
    else:
        ok(f"harness ownership: {harness}")
    check_platform_check_contract(root, config, harness)
    if sys.version_info >= (3, 11): ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        fail("Python 3.11+ is required (tomllib is used by platform scripts)"); failures[0] += 1
    if shutil.which("git"): ok("git is installed")
    else:
        fail("git is not installed"); failures[0] += 1
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, text=True, capture_output=True)
    if probe.returncode == 0: ok("inside a Git repository")
    else:
        fail("not inside a Git repository"); failures[0] += 1
    if probe.returncode == 0:
        check_shared_workspace(root, failures)

    project_required = config.get("project_required_files", [])
    if not isinstance(project_required, list) or not all(isinstance(item, str) and item for item in project_required):
        fail("project_required_files must be a list of non-empty repository-relative paths"); failures[0] += 1
        project_required = []
    required = list(REQUIRED_COMMON) + list(project_required)
    if workflow_profile == "multi-agent" and harness == "platform":
        required += REQUIRED_MULTI_AGENT_PLATFORM
    for relative in dict.fromkeys(required):
        if (root / relative).exists(): ok(relative)
        else:
            fail(f"missing {relative}"); failures[0] += 1

    check_task_start_contract(root, config, harness, failures)
    check_rendered_workflow_mode(root, config, failures)

    commit = copier_commit(root)
    configured_version = str(config.get("platform_version", ""))
    if commit and SEMVER_TAG_RE.fullmatch(commit):
        expected_version = commit[1:]
        if configured_version == expected_version:
            ok(f"platform version metadata agrees at {commit}")
        else:
            fail(f"platform version metadata mismatch: .copier-answers.yml={commit}, .dev-platform.toml={configured_version!r}"); failures[0] += 1
    elif commit:
        warn(f"Copier _commit is not a stable SemVer tag: {commit}")

    tools = config.get("tools", {})
    openspec_cfg = tools.get("openspec", {})
    check_tool_version(root, "openspec", openspec_cfg, failures)
    if openspec_cfg.get("verify_required", True):
        if any((root / relative).exists() for relative in VERIFY_CANDIDATES): ok("OpenSpec verify workflow is installed")
        else: warn("OpenSpec verify workflow is not detected. Run `python3 scripts/dev.py ready` to restore platform-selected integrations.")

    copier_cfg = tools.get("copier", {"min_version": "9.17.0", "tested_version": "9.17.0"})
    check_tool_version(root, "copier", copier_cfg, failures)

    conflicts = find_update_conflicts(root)
    if conflicts:
        for item in conflicts[:10]: fail(f"unresolved update conflict: {item}")
        if len(conflicts) > 10: fail(f"{len(conflicts) - 10} additional unresolved update conflict(s)")
        failures[0] += 1
    else:
        ok("no unresolved Copier/Git conflict artifacts")

    board_rel = str(config.get("paths", {}).get("agent_board", ".claude/agents-board.json"))
    ignored = subprocess.run(["git", "check-ignore", "-q", board_rel], cwd=root)
    if ignored.returncode == 0: ok(f"machine-local agent state is ignored: {board_rel}")
    else:
        fail(f"machine-local agent state is not ignored: {board_rel}"); failures[0] += 1
    local_rules = subprocess.run(["git", "check-ignore", "-q", "AGENTS.local.md"], cwd=root)
    if local_rules.returncode == 0: ok("AGENTS.local.md is ignored")
    else:
        fail("AGENTS.local.md is not ignored"); failures[0] += 1

    if failures[0]:
        print(f"Doctor found {failures[0]} blocking issue(s)."); return 1
    print(f"Doctor: platform contract looks healthy for profile={workflow_profile}, harness={harness}."); return 0


if __name__ == "__main__":
    raise SystemExit(main())
