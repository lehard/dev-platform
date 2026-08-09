from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "managed-projects.json"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
ALLOWED_STATES = {"managed", "candidate", "excluded"}


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"managed project registry not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in managed project registry: {exc}") from exc
    validate_registry(data)
    return data


def save_registry(data: dict[str, Any], path: Path = DEFAULT_REGISTRY) -> None:
    validate_registry(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise ValueError("managed project registry schema_version must be 1")
    projects = data.get("projects")
    if not isinstance(projects, list):
        raise ValueError("managed project registry projects must be a list")
    seen: set[str] = set()
    for index, item in enumerate(projects):
        label = f"projects[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        repository = item.get("repository")
        state = item.get("state")
        default_branch = item.get("default_branch")
        note = item.get("note", "")
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            raise ValueError(f"{label}.repository must be owner/name")
        if repository in seen:
            raise ValueError(f"duplicate repository in managed project registry: {repository}")
        seen.add(repository)
        if state not in ALLOWED_STATES:
            raise ValueError(f"{repository}: state must be one of {sorted(ALLOWED_STATES)}")
        if not isinstance(default_branch, str) or not default_branch or not BRANCH_RE.fullmatch(default_branch):
            raise ValueError(f"{repository}: invalid default_branch")
        if note is not None and not isinstance(note, str):
            raise ValueError(f"{repository}: note must be a string")
        if state == "excluded" and (not isinstance(note, str) or not note.strip()):
            raise ValueError(f"{repository}: excluded entries must explain the exclusion in note")


def managed_projects(data: dict[str, Any], repository: str | None = None) -> list[dict[str, str]]:
    projects = [item for item in data["projects"] if item["state"] == "managed"]
    if repository:
        matching = [item for item in data["projects"] if item["repository"] == repository]
        if not matching:
            raise ValueError(f"repository is not registered: {repository}")
        if matching[0]["state"] != "managed":
            raise ValueError(f"repository is registered as {matching[0]['state']}, not managed: {repository}")
        projects = matching
    return [{"repository": item["repository"], "repo_name": item["repository"].split("/", 1)[1], "default_branch": item["default_branch"]} for item in projects]


def matrix_payload(data: dict[str, Any], repository: str | None = None) -> dict[str, Any]:
    return {"include": managed_projects(data, repository)}


def promote_repository(data: dict[str, Any], repository: str, default_branch: str = "main", note: str = "Adopted through Dev Platform onboarding; eligible for reviewed managed rollout.") -> bool:
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository must be owner/name")
    if not default_branch or not BRANCH_RE.fullmatch(default_branch):
        raise ValueError(f"invalid default_branch: {default_branch!r}")
    if not note.strip():
        raise ValueError("managed project note must not be empty")
    for item in data["projects"]:
        if item["repository"] != repository:
            continue
        changed = item.get("state") != "managed" or item.get("default_branch") != default_branch or item.get("note") != note
        item["state"] = "managed"
        item["default_branch"] = default_branch
        item["note"] = note
        validate_registry(data)
        return changed
    data["projects"].append({"repository": repository, "state": "managed", "default_branch": default_branch, "note": note})
    validate_registry(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and query the dev-platform managed-project registry.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate registry syntax and invariants.")
    matrix = sub.add_parser("matrix", help="Print the GitHub Actions matrix for managed projects.")
    matrix.add_argument("--repository", help="Limit to one exact registered managed repository.")
    status = sub.add_parser("status", help="Print registry entries and state.")
    status.add_argument("--json", action="store_true")
    promote = sub.add_parser("promote", help="Explicitly promote an adopted repository to managed.")
    promote.add_argument("--repository", required=True)
    promote.add_argument("--default-branch", default="main")
    promote.add_argument("--note", default="Adopted through Dev Platform onboarding; eligible for reviewed managed rollout.")
    args = parser.parse_args()
    try:
        data = load_registry(args.registry)
        if args.command == "validate":
            counts = {state: sum(1 for item in data["projects"] if item["state"] == state) for state in sorted(ALLOWED_STATES)}
            print("Managed project registry: OK " f"({counts['managed']} managed, {counts['candidate']} candidate, {counts['excluded']} excluded)")
            return 0
        if args.command == "matrix":
            payload = matrix_payload(data, args.repository)
            if not payload["include"]:
                raise ValueError("managed project registry contains no rollout targets")
            print(json.dumps(payload, separators=(",", ":")))
            return 0
        if args.command == "status":
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                for item in data["projects"]:
                    print(f"{item['state']:9} {item['repository']} ({item['default_branch']})")
            return 0
        if args.command == "promote":
            changed = promote_repository(data, args.repository, args.default_branch, args.note)
            if changed:
                save_registry(data, args.registry)
                print(f"Promoted {args.repository} to managed.")
            else:
                print(f"{args.repository} is already managed with the requested metadata.")
            return 0
    except ValueError as exc:
        print(f"Managed project registry: BLOCKED: {exc}")
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
