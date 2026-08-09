from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ALL_OPENSPEC_WORKFLOWS = ["propose", "explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]
LOCAL_GENERATED_EXCLUDES = [".claude/", ".codex/skills/openspec-*/", "AGENTS.local.md"]


def run(command: list[str], root: Path, *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=root, env=env, check=True)


def load_config(root: Path) -> dict:
    import tomllib
    with (root / ".dev-platform.toml").open("rb") as fh:
        return tomllib.load(fh)


def openspec_profile() -> dict[str, object]:
    return {"featureFlags": {}, "profile": "custom", "delivery": "both", "workflows": ALL_OPENSPEC_WORKFLOWS}


def ensure_local_generated_excludes(root: Path) -> None:
    git_dir_result = subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=root, text=True, capture_output=True, check=True
    )
    git_dir = Path(git_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    exclude = git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    existing_lines = {line.strip() for line in existing.splitlines()}
    missing = [pattern for pattern in LOCAL_GENERATED_EXCLUDES if pattern not in existing_lines]
    if not missing:
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = "# Dev Platform machine-local generated integrations\n" + "\n".join(missing) + "\n"
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write(prefix + block)
    print("Configured Git-local excludes for generated agent integrations.")


def refresh_openspec(root: Path) -> None:
    executable = shutil.which("openspec")
    if not executable:
        raise RuntimeError("OpenSpec CLI is not installed; install the version required by .dev-platform.toml")
    tools = str(load_config(root).get("agent_tools", "claude,codex"))
    with tempfile.TemporaryDirectory(prefix="dev-platform-openspec-") as tmp:
        config_dir = Path(tmp) / "openspec"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(json.dumps(openspec_profile(), indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = tmp
        run([executable, "init", ".", "--tools", tools, "--profile", "custom", "--force"], root, env=env)


def maybe_sync_main(root: Path) -> None:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    main_branch = str(load_config(root).get("main_branch", "main"))
    if branch != main_branch:
        print(f"Skipping integration sync: current branch is {branch!r}, not {main_branch!r}.")
        return
    run(["python3", "scripts/project_sync.py"], root)


def ready(root: Path) -> int:
    root = root.resolve()
    maybe_sync_main(root)
    ensure_local_generated_excludes(root)
    refresh_openspec(root)
    run(["python3", "scripts/platform_doctor.py"], root)
    run(["python3", "scripts/agent_doctor.py"], root)
    print("Ready: repository, Dev Platform and OpenSpec integrations are healthy.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Single developer entrypoint for Dev Platform projects.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready", help="Synchronize when safe, refresh OpenSpec integrations, and run platform/agent doctors.")
    args = parser.parse_args()
    if args.command == "ready":
        try:
            return ready(Path.cwd())
        except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"Ready: BLOCKED: {exc}")
            return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
