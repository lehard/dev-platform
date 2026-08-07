from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from _platform_common import read_platform_config

REQUIRED_COMMON = ["AGENTS.md", "CLAUDE.md", ".dev-platform.toml", "dev-platform/checks.toml", "docs/engineering/openspec-workflow.md", "scripts/select_checks.py", "scripts/project_sync.py", "scripts/project_publish.py", "scripts/start_task.py", "scripts/finish_task.py", "scripts/agent_friction.py", "scripts/agent_doctor.py"]
REQUIRED_MULTI_AGENT = ["scripts/agent_board.py", "scripts/start_worktree.py"]
VERIFY_CANDIDATES = [".agents/skills/openspec-verify-change/SKILL.md", ".claude/skills/openspec-verify-change/SKILL.md", ".cursor/skills/openspec-verify-change/SKILL.md"]
IGNORED_CONFLICT_DIRS = {".git", ".claude", "node_modules", ".venv", "venv"}


def ok(label: str) -> None: print(f"[ok]   {label}")
def warn(label: str) -> None: print(f"[warn] {label}")
def fail(label: str) -> None: print(f"[fail] {label}")


def version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else None


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


def main() -> int:
    root = Path.cwd().resolve()
    failures = [0]
    config = read_platform_config(root)
    workflow_profile = str(config.get("workflow_profile", "standard"))
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

    required = list(REQUIRED_COMMON) + (REQUIRED_MULTI_AGENT if workflow_profile == "multi-agent" else [])
    for relative in required:
        if (root / relative).exists(): ok(relative)
        else:
            fail(f"missing {relative}"); failures[0] += 1

    tools = config.get("tools", {})
    openspec_cfg = tools.get("openspec", {})
    check_tool_version(root, "openspec", openspec_cfg, failures)
    if openspec_cfg.get("verify_required", True):
        if any((root / relative).exists() for relative in VERIFY_CANDIDATES): ok("OpenSpec verify workflow is installed")
        else: warn("OpenSpec verify workflow is not detected. Enable it with `openspec config profile`, then run `openspec update` before archiving non-trivial changes.")

    copier_cfg = tools.get("copier", {"min_version": "9.17.0", "tested_version": "9.17.0"})
    check_tool_version(root, "copier", copier_cfg, failures)

    conflicts = find_update_conflicts(root)
    if conflicts:
        for item in conflicts[:10]: fail(f"unresolved update conflict: {item}")
        if len(conflicts) > 10: fail(f"{len(conflicts) - 10} additional unresolved update conflict(s)")
        failures[0] += 1
    else:
        ok("no unresolved Copier/Git conflict artifacts")

    ignored = subprocess.run(["git", "check-ignore", "-q", ".claude/agents-board.json"], cwd=root)
    if ignored.returncode == 0: ok(".claude machine-local state is ignored")
    else:
        fail(".claude machine-local state is not ignored"); failures[0] += 1
    local_rules = subprocess.run(["git", "check-ignore", "-q", "AGENTS.local.md"], cwd=root)
    if local_rules.returncode == 0: ok("AGENTS.local.md is ignored")
    else:
        fail("AGENTS.local.md is not ignored"); failures[0] += 1

    if failures[0]:
        print(f"Doctor found {failures[0]} blocking issue(s)."); return 1
    print(f"Doctor: platform contract looks healthy for profile={workflow_profile}."); return 0


if __name__ == "__main__":
    raise SystemExit(main())
