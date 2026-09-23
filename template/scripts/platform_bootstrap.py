from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from _platform_common import SharedWorkspaceError, configure_shared_repository, posix_available, preflight

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLATFORM_VERSION_RE = re.compile(r'^platform_version\s*=\s*"[^"]*"\s*$', re.MULTILINE)
ALL_OPENSPEC_WORKFLOWS = ["propose", "explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]

PROJECT_CONTEXT_MAP = """# Project context map

This directory is project-owned, reviewed context for stable knowledge that
helps an agent understand this repository's product and implementation. It is a
map, not an always-on prompt: read it only after work reaches a listed concern,
then open only the focused document that applies.

## What belongs here

Add concise, evidence-backed context only when it will remain useful across
tasks. The following names are optional conventions, not mandatory empty
templates:

| Reached concern | Focused context to add or consult |
| --- | --- |
| Product goals, users, key scenarios, or product invariants | `product.md` |
| Project vocabulary, entities, rules, and source-of-truth boundaries | `domain.md` |
| Architecture invariants, decisions, and links to canonical designs | `architecture.md` |
| Approaches that have repeatedly failed or must be avoided | `anti-patterns.md` |
| Small representative implementation paths or fixtures | `examples.md` |

Link to authoritative owners instead of copying them: engineering rules and
checks stay in `docs/engineering/project-rules.md` and check configuration;
accepted behavior stays in OpenSpec; module constraints stay in module
`AGENTS.md`; detailed runbooks and designs stay in their existing documents.

## Bootstrap or refresh

Preserve any non-empty reviewed context. Before adding or changing it, list
the likely evidence-bearing sources, then inspect the relevant ones:

```bash
python3 scripts/project_context.py inventory
```

This helper lists paths but never infers facts or writes a draft. Review the
README, project rules, OpenSpec specs and active changes, relevant code and
checks, and existing documentation.
Distill facts supported by that evidence, with links or concise source notes
where they help later review.

If a material product, domain, or architecture fact remains unresolved after
that inspection, ask one bounded human question at a time; the helper formats
exactly one only after the agent confirms the gap:

```bash
python3 scripts/project_context.py question product
```

Keep an unanswered item explicitly `TODO` or `Unknown`; do not promote a
plausible inference into canonical context. Treat exports, copied tickets,
transcripts, and other raw source material as temporary machine-local input.
Do not commit it to this directory; commit only reviewed distilled context.

When ownership or review cadence matters, use lightweight metadata such as
`owner` and `last-reviewed`; a Git modification time is not evidence that a
fact is still valid.
"""


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


def operator_integration_selected(root: Path) -> bool:
    answers = root / ".copier-answers.yml"
    if not answers.exists():
        return False
    return any(line.strip().lower() == "operator_integration: true" for line in answers.read_text(encoding="utf-8").splitlines())


def sync_operator_integration(root: Path) -> None:
    """Add only the stable generic opt-in; existing reviewed tables are preserved."""
    if not operator_integration_selected(root):
        return
    config_path = root / ".dev-platform.toml"
    config = load_config(root)
    operator = config.get("operator")
    if operator is not None:
        if not isinstance(operator, dict) or operator.get("enabled") is not True:
            raise RuntimeError("existing [operator] configuration conflicts with requested generic operator integration")
        return
    text = config_path.read_text(encoding="utf-8").rstrip("\n")
    config_path.write_text(text + "\n\n[operator]\nenabled = true\nconfig_env = \"DEV_PLATFORM_OPERATOR_CONFIG\"\n", encoding="utf-8")
    print("Enabled generic environment-backed operator integration")


def ensure_project_context_map(root: Path) -> None:
    """Create the initial map without ever replacing reviewed project context."""
    context_map = root / "docs" / "context" / "README.md"
    if context_map.exists():
        return
    context_map.parent.mkdir(parents=True, exist_ok=True)
    context_map.write_text(PROJECT_CONTEXT_MAP, encoding="utf-8")


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
    sync_operator_integration(root)
    ensure_project_context_map(root)
    sync_engineering_capabilities(root)
    config = load_config(root)
    main_branch = str(config.get("main_branch", "main"))
    tools = str(config.get("agent_tools", "claude,codex"))
    was_git_repo = (root / ".git").exists()
    safe_fresh_adoption = os.environ.get("DEV_PLATFORM_SAFE_FRESH_ADOPTION") == "1"
    if not was_git_repo:
        run(["git", "init", "-b", main_branch], root)
    (root / ".claude" / "worktrees").mkdir(parents=True, exist_ok=True)
    # Bootstrap/adoption owns the initial stable shared-repository configuration;
    # the ordinary lifecycle only verifies it afterwards.
    if posix_available():
        try:
            configure_shared_repository(root)
        except SharedWorkspaceError as exc:
            print(f"[warn] could not configure {exc}")
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
