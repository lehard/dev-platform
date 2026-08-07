from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run(command: list[str], root: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=root, text=True, check=check)


def load_config(root: Path) -> dict:
    import tomllib
    with (root / ".dev-platform.toml").open("rb") as fh:
        return tomllib.load(fh)


def main() -> int:
    root = Path.cwd().resolve()
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
