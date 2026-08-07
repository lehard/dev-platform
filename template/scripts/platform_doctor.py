from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from _platform_common import read_platform_config

REQUIRED_COMMON = ["AGENTS.md", "CLAUDE.md", ".dev-platform.toml", "dev-platform/checks.toml", "docs/engineering/openspec-workflow.md", "scripts/select_checks.py", "scripts/project_sync.py", "scripts/project_publish.py", "scripts/start_task.py", "scripts/finish_task.py", "scripts/agent_friction.py", "scripts/agent_doctor.py"]
REQUIRED_MULTI_AGENT = ["scripts/agent_board.py", "scripts/start_worktree.py"]
VERIFY_CANDIDATES = [".agents/skills/openspec-verify/SKILL.md", ".claude/skills/openspec-verify/SKILL.md", ".cursor/skills/openspec-verify/SKILL.md"]


def ok(label: str) -> None: print(f"[ok]   {label}")
def warn(label: str) -> None: print(f"[warn] {label}")
def fail(label: str) -> None: print(f"[fail] {label}")

def version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else None


def main() -> int:
    root = Path.cwd().resolve()
    failures = 0
    config = read_platform_config(root)
    workflow_profile = str(config.get("workflow_profile", "standard"))
    if sys.version_info >= (3, 11): ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        fail("Python 3.11+ is required (tomllib is used by platform scripts)"); failures += 1
    if shutil.which("git"): ok("git is installed")
    else:
        fail("git is not installed"); failures += 1
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, text=True, capture_output=True)
    if probe.returncode == 0: ok("inside a Git repository")
    else:
        fail("not inside a Git repository"); failures += 1
    required = list(REQUIRED_COMMON) + (REQUIRED_MULTI_AGENT if workflow_profile == "multi-agent" else [])
    for relative in required:
        if (root / relative).exists(): ok(relative)
        else:
            fail(f"missing {relative}"); failures += 1
    openspec_cfg = config.get("tools", {}).get("openspec", {})
    minimum = str(openspec_cfg.get("min_version", "1.6.0")); tested = str(openspec_cfg.get("tested_version", minimum))
    openspec = shutil.which("openspec")
    if openspec:
        result = subprocess.run([openspec, "--version"], cwd=root, text=True, capture_output=True)
        parsed = version_tuple((result.stdout or result.stderr).strip()); min_tuple = version_tuple(minimum); tested_tuple = version_tuple(tested)
        if parsed and min_tuple and parsed < min_tuple:
            fail(f"OpenSpec {'.'.join(map(str, parsed))} is below minimum {minimum}"); failures += 1
        elif parsed:
            ok(f"OpenSpec {'.'.join(map(str, parsed))} installed (minimum {minimum})")
            if tested_tuple and parsed > tested_tuple: warn(f"OpenSpec is newer than platform-tested version {tested}; run project checks after openspec update")
        else: warn("OpenSpec CLI version could not be parsed")
    else: warn("OpenSpec CLI is not installed on this machine")
    if openspec_cfg.get("verify_required", True):
        if any((root / relative).exists() for relative in VERIFY_CANDIDATES): ok("OpenSpec verify workflow is installed")
        else: warn("OpenSpec verify workflow is not detected. Enable it with `openspec config profile`, then run `openspec update` before archiving non-trivial changes.")
    ignored = subprocess.run(["git", "check-ignore", "-q", ".claude/agents-board.json"], cwd=root)
    if ignored.returncode == 0: ok(".claude machine-local state is ignored")
    else:
        fail(".claude machine-local state is not ignored"); failures += 1
    local_rules = subprocess.run(["git", "check-ignore", "-q", "AGENTS.local.md"], cwd=root)
    if local_rules.returncode == 0: ok("AGENTS.local.md is ignored")
    else:
        fail("AGENTS.local.md is not ignored"); failures += 1
    if failures:
        print(f"Doctor found {failures} blocking issue(s)."); return 1
    print(f"Doctor: platform contract looks healthy for profile={workflow_profile}."); return 0


if __name__ == "__main__":
    raise SystemExit(main())
