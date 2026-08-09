from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLATFORM_VERSION_RE = re.compile(r'^platform_version\s*=\s*"[^"]*"\s*$', re.MULTILINE)
ALL_OPENSPEC_WORKFLOWS = ["propose", "explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]


def run(command: list[str], root: Path, check: bool = True, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=root, text=True, check=check, env=env)


def load_config(root: Path) -> dict:
    import tomllib
    with (root / ".dev-platform.toml").open("rb") as fh:
        return tomllib.load(fh)


def copier_commit(root: Path) -> str | None:
    answers = root / ".copier-answers.yml"
    if not answers.exists():
        return None
    for line in answers.read_text(encoding="utf-8").splitlines():
        if line.startswith("_commit:"):
            value = line.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def sync_platform_version(root: Path) -> None:
    commit = copier_commit(root)
    if not commit or not SEMVER_TAG_RE.fullmatch(commit):
        return
    config_path = root / ".dev-platform.toml"
    text = config_path.read_text(encoding="utf-8")
    replacement = f'platform_version = "{commit[1:]}"'
    if not PLATFORM_VERSION_RE.search(text):
        raise RuntimeError(".dev-platform.toml is missing top-level platform_version")
    updated = PLATFORM_VERSION_RE.sub(replacement, text, count=1)
    if updated != text:
        config_path.write_text(updated, encoding="utf-8")
        print(f"Synchronized .dev-platform.toml platform_version to {commit[1:]}")


def openspec_profile() -> dict[str, object]:
    return {"featureFlags": {}, "profile": "custom", "delivery": "both", "workflows": ALL_OPENSPEC_WORKFLOWS}


def initialize_openspec(root: Path, executable: str, tools: str) -> None:
    with tempfile.TemporaryDirectory(prefix="dev-platform-openspec-") as tmp:
        config_dir = Path(tmp) / "openspec"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps(openspec_profile(), indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = tmp
        run([executable, "init", ".", "--tools", tools, "--profile", "custom", "--force"], root, env=env)


def main() -> int:
    root = Path.cwd().resolve()
    sync_platform_version(root)
    config = load_config(root)
    main_branch = str(config.get("main_branch", "main"))
    tools = str(config.get("agent_tools", "claude,codex"))
    was_git_repo = (root / ".git").exists()
    safe_fresh_adoption = os.environ.get("DEV_PLATFORM_SAFE_FRESH_ADOPTION") == "1"
    if not was_git_repo:
        run(["git", "init", "-b", main_branch], root)
    (root / ".claude" / "worktrees").mkdir(parents=True, exist_ok=True)
    openspec = shutil.which("openspec")
    if openspec and (not was_git_repo or safe_fresh_adoption):
        print("Initializing full OpenSpec workflow set for fresh project/adoption...")
        initialize_openspec(root, openspec, tools)
        print("OpenSpec integrations include the expanded workflow set, including /opsx:verify.")
    elif was_git_repo:
        print("Existing/mature Git repository detected; OpenSpec migration is not run automatically.")
        print("After reviewing the adoption diff, run `python3 scripts/dev.py ready` locally.")
    else:
        print("OpenSpec CLI not found. Install the compatible version, then run `python3 scripts/dev.py ready`.")
    doctor = root / "scripts" / "platform_doctor.py"
    if doctor.exists():
        run(["python3", str(doctor)], root, check=False)
    print("Developer-platform bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
