from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from _platform_common import preflight

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLATFORM_VERSION_RE = re.compile(r'^platform_version\s*=\s*"[^"]*"\s*$', re.MULTILINE)
PROJECT_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
PROJECT_OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
BACKLOG_HEADER_RE = re.compile(r"(?m)^\[development_backlog\]\s*$")
PROCESS_HEALTH_HEADER_RE = re.compile(r"(?m)^\[process_health\]\s*$")
TABLE_HEADER_RE = re.compile(r"(?m)^\[[^\n]+\]\s*$")
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


def copier_answer(root: Path, key: str) -> str | None:
    answers = root / ".copier-answers.yml"
    if not answers.exists():
        return None
    prefix = key + ":"
    for line in answers.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def development_backlog_locator(root: Path) -> tuple[str, int]:
    owner = copier_answer(root, "development_backlog_project_owner") or "lehard"
    number_text = copier_answer(root, "development_backlog_project_number") or "1"
    if not PROJECT_OWNER_RE.fullmatch(owner):
        raise RuntimeError("development_backlog_project_owner Copier answer must be a GitHub login")
    try:
        number = int(number_text)
    except ValueError as exc:
        raise RuntimeError("development_backlog_project_number Copier answer must be a positive integer") from exc
    if number < 1:
        raise RuntimeError("development_backlog_project_number Copier answer must be a positive integer")
    return owner, number


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


def sync_development_backlog_config(root: Path) -> None:
    """Add the platform-owned authoring section without rewriting project config."""
    config = load_config(root)
    existing = config.get("development_backlog")
    if existing is not None and not isinstance(existing, dict):
        raise RuntimeError("development_backlog must be a TOML table")
    project_slug = config.get("project_slug")
    if not isinstance(project_slug, str) or not PROJECT_SLUG_RE.fullmatch(project_slug):
        raise RuntimeError(".dev-platform.toml is missing a safe project_slug for Development Backlog migration")
    config_path = root / ".dev-platform.toml"
    text = config_path.read_text(encoding="utf-8")
    project_owner, project_number = development_backlog_locator(root)
    if existing is None:
        addition = (
            "\n\n[development_backlog]\n"
            'repository = "lehard/development-backlog"\n'
            f'project_label = "project:{project_slug}"\n'
            'default_priority = "P2"\n'
            f'project_owner = "{project_owner}"\n'
            f'project_number = {project_number}\n'
        )
        config_path.write_text(text.rstrip() + addition, encoding="utf-8")
        print("Added Development Backlog authoring and Project workflow configuration.")
        return

    missing = []
    if "project_owner" not in existing:
        missing.append(f'project_owner = "{project_owner}"')
    if "project_number" not in existing:
        missing.append(f"project_number = {project_number}")
    if not missing:
        return
    header = BACKLOG_HEADER_RE.search(text)
    if header is None:
        raise RuntimeError("development_backlog configuration has no readable TOML table header")
    next_header = TABLE_HEADER_RE.search(text, header.end())
    end = next_header.start() if next_header else len(text)
    section = text[header.start():end].rstrip()
    updated = text[:header.start()] + section + "\n" + "\n".join(missing) + "\n" + text[end:].lstrip("\n")
    config_path.write_text(updated, encoding="utf-8")
    print("Added Development Backlog Project workflow locator configuration.")


def sync_process_health_config(root: Path) -> None:
    """Add the bounded process-health labels without rewriting project config."""
    config = load_config(root)
    existing = config.get("process_health")
    if existing is not None and not isinstance(existing, dict):
        raise RuntimeError("process_health must be a TOML table")
    config_path = root / ".dev-platform.toml"
    text = config_path.read_text(encoding="utf-8")
    if existing is None:
        addition = "\n\n[process_health]\nprocess_label = \"process\"\nmanaged_label = \"process:managed\"\n"
        config_path.write_text(text.rstrip() + addition, encoding="utf-8")
        print("Added process-health label configuration.")
        return
    missing = []
    if "process_label" not in existing:
        missing.append('process_label = "process"')
    if "managed_label" not in existing:
        missing.append('managed_label = "process:managed"')
    if not missing:
        return
    header = PROCESS_HEALTH_HEADER_RE.search(text)
    if header is None:
        raise RuntimeError("process_health configuration has no readable TOML table header")
    next_header = TABLE_HEADER_RE.search(text, header.end())
    end = next_header.start() if next_header else len(text)
    section = text[header.start():end].rstrip()
    updated = text[:header.start()] + section + "\n" + "\n".join(missing) + "\n" + text[end:].lstrip("\n")
    config_path.write_text(updated, encoding="utf-8")
    print("Added missing process-health label configuration.")


def sync_engineering_capabilities(root: Path) -> None:
    """Materialize only project-selected, platform-owned capability surfaces."""
    manager = root / "scripts" / "capability_manager.py"
    selection = root / "dev-platform" / "capabilities.toml"
    if not manager.is_file() or not selection.is_file():
        return
    result = run(["python3", str(manager), "--quiet", "sync"], root, check=False)
    if result.returncode:
        raise RuntimeError("optional engineering capability synchronization failed")


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
    sync_development_backlog_config(root)
    sync_process_health_config(root)
    sync_engineering_capabilities(root)
    config = load_config(root)
    main_branch = str(config.get("main_branch", "main"))
    tools = str(config.get("agent_tools", "claude,codex"))
    was_git_repo = (root / ".git").exists()
    safe_fresh_adoption = os.environ.get("DEV_PLATFORM_SAFE_FRESH_ADOPTION") == "1"
    if not was_git_repo:
        run(["git", "init", "-b", main_branch], root)
    (root / ".claude" / "worktrees").mkdir(parents=True, exist_ok=True)
    preflight(root)
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
