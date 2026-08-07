from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path


def run(command: list[str], root: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=root, text=True, check=check)


def load_config(root: Path) -> dict:
    path = root / ".dev-platform.toml"
    if not path.exists():
        raise SystemExit(f"Missing platform configuration: {path}")
    with path.open("rb") as fh:
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
        print("Initializing OpenSpec for fresh project...")
        run(command, root)
    elif was_git_repo:
        print("Existing Git repository detected; OpenSpec migration is not run automatically.")
        print("Review existing OpenSpec/tool files, then run explicitly if appropriate:")
        print("  " + " ".join(command))
    else:
        print("OpenSpec CLI not found. Install it, then run:")
        print("  " + " ".join(command))

    doctor = root / "scripts" / "platform_doctor.py"
    if doctor.exists():
        run(["python3", str(doctor)], root, check=False)

    print("Developer-platform bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
