from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PLATFORM_SOURCE = "https://github.com/lehard/dev-platform.git"
PLATFORM_CI_REF = "dab74494c9a6ad9a77d99e73bb36774a6d42350d"
FRESH_MAX_FILES = 60
FRESH_MAX_CODE_FILES = 20
PROCESS_MARKERS = (
    "AGENTS.md",
    "CLAUDE.md",
    "openspec",
    ".github/workflows",
    "dev-platform",
    "scripts/platform_doctor.py",
    "scripts/start_task.py",
)
CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs",
    ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".swift", ".vue", ".svelte",
}
IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build", ".next"}


def run(
    command: list[str],
    cwd: Path,
    *,
    capture: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=capture, env=env)
    if check and result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")
        raise ValueError(f"command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def parse_version(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"platform version must be an exact stable tag vX.Y.Z; got {tag!r}")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def adoption_branch(version: str) -> str:
    parse_version(version)
    return f"dev-platform/adopt-{version}"


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True)
    if result.returncode == 0:
        return [line for line in result.stdout.splitlines() if line]
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        files.append(str(relative))
    return sorted(files)


def classify_repository(root: Path) -> tuple[str, list[str]]:
    root = root.resolve()
    if (root / ".dev-platform.toml").exists() or (root / ".copier-answers.yml").exists():
        return "adopted", ["existing Dev Platform metadata"]
    reasons: list[str] = []
    for marker in PROCESS_MARKERS:
        if (root / marker).exists():
            reasons.append(f"process marker: {marker}")
    files = tracked_files(root)
    code_files = [path for path in files if Path(path).suffix.lower() in CODE_SUFFIXES]
    if len(files) > FRESH_MAX_FILES:
        reasons.append(f"tracked files: {len(files)} > {FRESH_MAX_FILES}")
    if len(code_files) > FRESH_MAX_CODE_FILES:
        reasons.append(f"code files: {len(code_files)} > {FRESH_MAX_CODE_FILES}")
    return ("existing", reasons) if reasons else ("fresh", [])


def adoption_defaults(kind: str) -> dict[str, str]:
    if kind == "fresh":
        return {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "direct"}
    if kind == "existing":
        return {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "pr"}
    raise ValueError(f"unsupported adoption kind: {kind}")


def source_env() -> dict[str, str]:
    token = os.environ.get("DEV_PLATFORM_SOURCE_TOKEN", "").strip()
    if not token:
        raise ValueError("DEV_PLATFORM_SOURCE_TOKEN is required for private template access")
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = f"url.https://x-access-token:{token}@github.com/.insteadOf"
    env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
    return env


def ensure_clean(root: Path) -> None:
    status = run(["git", "status", "--porcelain"], root, capture=True)
    if status.stdout.strip():
        raise ValueError("target checkout is dirty before adoption")


def reject_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.rej") if not any(part in IGNORED_PARTS for part in path.relative_to(root).parts))


def validate_project(root: Path, base_branch: str) -> None:
    rejects = reject_files(root)
    if rejects:
        raise ValueError("Copier left unresolved .rej files: " + ", ".join(rejects[:10]))
    run(["git", "diff", "--check", "--"], root)
    run(["python3", "scripts/platform_doctor.py"], root)
    run(["python3", "scripts/openspec_lifecycle.py", "check"], root)
    openspec = shutil.which("openspec")
    if openspec:
        run([openspec, "validate", "--all", "--strict", "--no-interactive"], root)
    run(["python3", "scripts/select_checks.py", "--base", f"origin/{base_branch}", "--execute"], root)


def write_result(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if path:
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def adopt(root: Path, repository: str, version: str, base_branch: str, output: Path | None = None) -> int:
    root = root.resolve()
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository must be owner/name")
    parse_version(version)
    if shutil.which("copier") is None:
        raise ValueError("Copier is not installed")
    ensure_clean(root)
    kind, reasons = classify_repository(root)
    branch = adoption_branch(version)
    if kind == "adopted":
        write_result(output, {"status": "already_adopted", "repository": repository, "kind": kind, "branch": branch, "base_branch": base_branch})
        return 0
    defaults = adoption_defaults(kind)
    run(["git", "fetch", "origin", base_branch], root)
    remote_probe = run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch], root, capture=True, check=False)
    if remote_probe.returncode == 0 and remote_probe.stdout.strip():
        raise ValueError(f"adoption branch already exists: {branch}")
    if remote_probe.returncode not in {0, 2}:
        raise ValueError("could not inspect adoption branch state")
    run(["git", "checkout", "-b", branch, f"origin/{base_branch}"], root)
    env = source_env()
    if kind == "fresh":
        env["DEV_PLATFORM_SAFE_FRESH_ADOPTION"] = "1"
    repo_name = repository.split("/", 1)[1]
    command = [
        "copier", "copy", "--trust", "--defaults", "--vcs-ref", version, "--conflict", "rej",
        "--data", f"project_name={repo_name}", "--data", f"project_slug={repo_name.lower().replace('_', '-')}",
        "--data", "project_description=", "--data", f"workflow_profile={defaults['workflow_profile']}",
        "--data", f"harness_mode={defaults['harness_mode']}", "--data", f"publish_mode={defaults['publish_mode']}",
        "--data", f"platform_ci_ref={PLATFORM_CI_REF}", PLATFORM_SOURCE, ".",
    ]
    run(command, root, env=env)
    validate_project(root, base_branch)
    run(["git", "add", "-A"], root)
    staged = run(["git", "diff", "--cached", "--quiet"], root, check=False)
    if staged.returncode == 0:
        raise ValueError("adoption produced no changes")
    if staged.returncode != 1:
        raise ValueError("could not inspect staged adoption diff")
    run(["git", "commit", "-m", f"chore: adopt dev-platform {version}"], root)
    write_result(output, {"status": "updated", "repository": repository, "kind": kind, "reasons": reasons, "branch": branch, "base_branch": base_branch, **defaults})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare first-time Dev Platform adoption for one checked-out repository.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        return adopt(args.project_root, args.repository, args.version, args.base_branch, args.output)
    except ValueError as exc:
        print(f"Adoption: BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
