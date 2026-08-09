from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ANSWER_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*?)\s*$")
EXPECTED_SOURCES = {
    "gh:lehard/dev-platform",
    "https://github.com/lehard/dev-platform",
    "https://github.com/lehard/dev-platform.git",
    "git@github.com:lehard/dev-platform.git",
}


def run(command: list[str], cwd: Path, *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=capture)
    if check and result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")
        raise SystemExit(result.returncode)
    return result


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_answers(text: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    for line in text.splitlines():
        match = ANSWER_RE.match(line)
        if match:
            answers[match.group(1)] = clean_scalar(match.group(2))
    return answers


def load_answers(project_root: Path) -> dict[str, str]:
    path = project_root / ".copier-answers.yml"
    if not path.exists():
        raise ValueError(".copier-answers.yml is missing; first-time adoption is required")
    answers = parse_answers(path.read_text(encoding="utf-8"))
    source = answers.get("_src_path")
    current = answers.get("_commit")
    if source not in EXPECTED_SOURCES:
        raise ValueError(f"unexpected Copier source: {source!r}")
    if current is None:
        raise ValueError(".copier-answers.yml does not contain _commit")
    parse_version(current)
    return answers


def parse_version(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"platform version must be a stable SemVer tag vX.Y.Z; got {tag!r}")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def rollout_branch(version: str) -> str:
    parse_version(version)
    return f"dev-platform/rollout-{version}"


def find_reject_files(project_root: Path) -> list[str]:
    ignored_dirs = {".git", ".venv", "venv", "node_modules", ".claude"}
    found: list[str] = []
    for path in project_root.rglob("*.rej"):
        relative = path.relative_to(project_root)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        found.append(str(relative))
    return sorted(found)


def ensure_clean(project_root: Path) -> None:
    status = run(["git", "status", "--porcelain"], project_root, capture=True)
    if status.stdout.strip():
        raise ValueError("downstream checkout is dirty before rollout")


def ensure_branch_absent(project_root: Path, branch: str) -> None:
    result = run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch], project_root, capture=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        raise ValueError(f"rollout branch already exists without a handled open PR: {branch}")
    if result.returncode not in {0, 2}:
        raise ValueError("could not inspect downstream rollout branch state")


def run_project_validation(project_root: Path, base_branch: str) -> None:
    rejects = find_reject_files(project_root)
    if rejects:
        raise ValueError("Copier left unresolved .rej files: " + ", ".join(rejects[:10]))
    run(["git", "diff", "--check", "--"], project_root)

    doctor = project_root / "scripts" / "platform_doctor.py"
    if not doctor.exists():
        raise ValueError("updated project is missing scripts/platform_doctor.py")
    run(["python3", str(doctor)], project_root)

    checks = project_root / "scripts" / "select_checks.py"
    if not checks.exists():
        raise ValueError("updated project is missing scripts/select_checks.py")
    run(["python3", str(checks), "--base", f"origin/{base_branch}", "--execute"], project_root)


def write_result(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if path:
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def apply_rollout(project_root: Path, repository: str, version: str, base_branch: str, output: Path | None = None) -> int:
    project_root = project_root.resolve()
    target = parse_version(version)
    if shutil.which("copier") is None:
        raise ValueError("Copier is not installed")
    ensure_clean(project_root)
    answers = load_answers(project_root)
    current_tag = answers["_commit"]
    current = parse_version(current_tag)
    branch = rollout_branch(version)

    if current == target:
        write_result(output, {"status": "up_to_date", "repository": repository, "current": current_tag, "target": version, "branch": branch})
        return 0
    if current > target:
        raise ValueError(f"refusing platform downgrade from {current_tag} to {version}")

    ensure_branch_absent(project_root, branch)
    run(["git", "fetch", "origin", base_branch], project_root)
    run(["git", "checkout", "-b", branch, f"origin/{base_branch}"], project_root)
    ensure_clean(project_root)

    run(["copier", "update", "--trust", "--defaults", "--vcs-ref", version, "--conflict", "rej"], project_root)

    updated = load_answers(project_root)
    if updated["_commit"] != version:
        raise ValueError(f"Copier recorded {updated['_commit']!r}, expected exact target {version!r}")

    run_project_validation(project_root, base_branch)
    status = run(["git", "status", "--porcelain"], project_root, capture=True)
    if not status.stdout.strip():
        raise ValueError("Copier changed the recorded version but produced no repository diff")

    run(["git", "add", "-A"], project_root)
    run(["git", "diff", "--cached", "--check", "--"], project_root)
    run(["git", "commit", "-m", f"chore: update dev-platform to {version}"], project_root)
    write_result(output, {"status": "updated", "repository": repository, "current": current_tag, "target": version, "branch": branch})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one managed downstream repository for an exact dev-platform Copier rollout PR.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        return apply_rollout(args.project_root, args.repository, args.version, args.base_branch, args.output)
    except ValueError as exc:
        print(f"Managed rollout: BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
