from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ALL_OPENSPEC_WORKFLOWS = ["propose", "explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]


def run(command: list[str], root: Path, *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=root, env=env, check=True)


def load_config(root: Path) -> dict:
    import tomllib
    with (root / ".dev-platform.toml").open("rb") as fh:
        return tomllib.load(fh)


def openspec_profile() -> dict[str, object]:
    return {"featureFlags": {}, "profile": "custom", "delivery": "both", "workflows": ALL_OPENSPEC_WORKFLOWS}


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
