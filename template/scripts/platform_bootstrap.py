from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLATFORM_VERSION_RE = re.compile(r'^platform_version\s*=\s*"[^"]*"\s*$', re.MULTILINE)


def run(command: list[str], root: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=root, text=True, check=check)


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


def main() -> int:
    root = Path.cwd().resolve()
    sync_platform_version(root)
    config = load_config(root)
    main_branch = str(config.get("main_branch", "main"))
    tools = str(config.get("agent_tools", "claude,codex"))
    was_git_repo = (root / ".git").exists()
    if not was_git_repo:
        run(["git", "init", "-b", main_branch], root)
    (root / ".claude" / "worktrees").mkdir(parents=True, exist_ok=True)
    command = ["openspec", "init", ".", "--tools", tools, "--profile", "core", "--no-animation"]
    openspec = shutil.which("openspec")
    if openspec and not was_git_repo:
        print("Initializing OpenSpec core workflows for fresh project...")
        run(command, root)
        print("Platform policy also requires /opsx:verify for non-trivial changes.")
        print("Enable the expanded verify workflow once with `openspec config profile`, then run `openspec update`.")
    elif was_git_repo:
        print("Existing Git repository detected; OpenSpec migration is not run automatically.")
        print("Review existing OpenSpec/tool files, then run explicitly if appropriate:")
        print("  " + " ".join(command))
        print("Then enable verify with `openspec config profile` and run `openspec update`.")
    else:
        print("OpenSpec CLI not found. Install a compatible version, then run:")
        print("  " + " ".join(command))
    doctor = root / "scripts" / "platform_doctor.py"
    if doctor.exists():
        run(["python3", str(doctor)], root, check=False)
    print("Developer-platform bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
