#!/usr/bin/env python3
"""Managed task intake."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from _platform_common import current_worktree_root, github_cli_env, read_platform_config

PACKAGE = "managed-openspec:v1"
MARKER_RE = re.compile(r"<!--\s*(managed-openspec:v[0-9]+)\s*-->")
MANIFEST_RE = re.compile(r"<!--\s*managed-openspec:v1\s*-->[\s\S]*?(?:\x60){3}json\s*\n([\s\S]*?)\n(?:\x60){3}", re.I)
FILE_RE = re.compile(r"<!--\s*managed-openspec:file:([^\s]+)\s*-->\n([\s\S]*?)<!--\s*managed-openspec:endfile\s*-->")
REF_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)$")
CHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVENANCE = ".managed-task.json"


class ManagedTaskError(RuntimeError):
    pass


@dataclass(frozen=True)
class Package:
    source_issue: str
    target_repository: str
    change: str
    prepared_against: str
    artifacts: tuple[str, ...]
    contents: dict[str, str]
    revision: str


def repo(value: str) -> str:
    value = value.strip().removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ManagedTaskError(f"repository must be owner/name, got {value!r}")
    return value.lower()


def issue_ref(value: str) -> tuple[str, int]:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.lower() != "github.com" or len(parts) != 4 or parts[2] != "issues" or not parts[3].isdigit():
            raise ManagedTaskError("issue must be owner/repo#N or https://github.com/owner/repo/issues/N")
        return repo("/".join(parts[:2])), int(parts[3])
    match = REF_RE.fullmatch(value)
    if not match:
        raise ManagedTaskError("issue must be owner/repo#N or https://github.com/owner/repo/issues/N")
    return repo(match.group(1)), int(match.group(2))


def origin_repository(root: Path) -> str:
    result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise ManagedTaskError("current checkout has no readable origin remote")
    remote = result.stdout.strip().removesuffix("/").removesuffix(".git")
    ssh = re.fullmatch(r"(?:[^@]+@)?github\.com:([^/]+)/([^/]+)", remote)
    parsed = urlparse(remote)
    if ssh:
        return repo(f"{ssh.group(1)}/{ssh.group(2)}")
    if parsed.hostname and parsed.hostname.lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2:
            return repo("/".join(parts))
    raise ManagedTaskError("origin must be a standard GitHub HTTPS or SSH owner/repo remote")


def run(command: list[str], root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ManagedTaskError(f"{' '.join(command[:2])} failed: {detail or 'unknown error'}")
    return result


def run_json(command: list[str], root: Path, env: dict[str, str] | None = None) -> Any:
    output = run(command, root, env).stdout.strip()
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        start = min((index for index in (output.find("{"), output.find("[")) if index >= 0), default=-1)
        if start >= 0:
            try:
                return json.loads(output[start:])
            except json.JSONDecodeError:
                pass
        raise ManagedTaskError(f"{' '.join(command[:2])} did not return structured JSON")


def issue_bodies(root: Path, repository: str, number: int) -> list[str]:
    env = github_cli_env(root)
    if env is None:
        raise ManagedTaskError("GitHub CLI authentication is required; run gh auth login and retry")
    issue = run_json(["gh", "api", f"repos/{repository}/issues/{number}"], root, env)
    comments = run_json(["gh", "api", "--paginate", f"repos/{repository}/issues/{number}/comments"], root, env)
    if not isinstance(issue, dict) or not isinstance(comments, list):
        raise ManagedTaskError("GitHub returned an unexpected issue payload")
    if any(not isinstance(comment, dict) for comment in comments):
        raise ManagedTaskError("GitHub returned an invalid issue comment")
    return [str(issue.get("body") or "")] + [str(comment.get("body") or "") for comment in comments]


def safe_artifact(value: str) -> str:
    path = PurePosixPath(value)
    valid_spec = value.startswith("specs/") and len(path.parts) >= 3
    if (
        not value or path.is_absolute() or ".." in path.parts or "." in path.parts
        or ".git" in path.parts or path.suffix != ".md" or str(path) != value
        or (value not in {"proposal.md", "design.md", "tasks.md"} and not valid_spec)
    ):
        raise ManagedTaskError(f"unsafe managed OpenSpec artifact path: {value!r}")
    return value


def revision(manifest: dict[str, Any], artifacts: tuple[str, ...], contents: dict[str, str]) -> str:
    normalized = {key: manifest[key] for key in ("version", "source_issue", "target_repository", "change", "prepared_against")}
    normalized["artifacts"] = list(artifacts)
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode())
    for path in artifacts:
        digest.update(bytes([0]))
        digest.update(path.encode())
        digest.update(bytes([0]))
        digest.update(contents[path].encode())
    return digest.hexdigest()


def parse_package(bodies: list[str], requested: str) -> Package:
    versions = [match.group(1) for body in bodies for match in MARKER_RE.finditer(body)]
    unsupported = sorted(set(version for version in versions if version != PACKAGE))
    if unsupported:
        raise ManagedTaskError(f"unsupported managed OpenSpec package version(s): {', '.join(unsupported)}")
    markers = [(body, match) for body in bodies for match in MARKER_RE.finditer(body) if match.group(1) == PACKAGE]
    if len(markers) != 1:
        raise ManagedTaskError(f"expected exactly one {PACKAGE} package; found {len(markers)}")
    body = markers[0][0]
    manifest_match = MANIFEST_RE.search(body)
    if not manifest_match:
        raise ManagedTaskError("managed package is missing its JSON manifest")
    try:
        manifest = json.loads(manifest_match.group(1))
    except json.JSONDecodeError as exc:
        raise ManagedTaskError(f"managed package manifest is not valid JSON: {exc.msg}") from exc
    required = ("version", "source_issue", "target_repository", "change", "prepared_against", "artifacts")
    if not isinstance(manifest, dict) or any(key not in manifest for key in required):
        raise ManagedTaskError("managed package manifest is incomplete")
    if manifest["version"] != 1 or not all(
        isinstance(manifest[key], str) for key in ("source_issue", "target_repository", "change", "prepared_against")
    ):
        raise ManagedTaskError("managed package manifest has invalid v1 fields")
    source_parts = manifest["source_issue"].rsplit("#", 1)
    if len(source_parts) != 2 or not source_parts[1].isdigit():
        raise ManagedTaskError("source_issue must be owner/repo#N")
    source_issue = f"{repo(source_parts[0])}#{int(source_parts[1])}"
    if source_issue.lower() != requested.lower():
        raise ManagedTaskError("package source_issue does not match the requested issue")
    target = repo(manifest["target_repository"])
    if not CHANGE_RE.fullmatch(manifest["change"]):
        raise ManagedTaskError("change must be a lowercase OpenSpec change name")
    prepared = manifest["prepared_against"].lower()
    if not SHA_RE.fullmatch(prepared):
        raise ManagedTaskError("prepared_against must be a 40-character Git SHA")
    declared = manifest["artifacts"]
    if not isinstance(declared, list) or not declared or not all(isinstance(path, str) for path in declared):
        raise ManagedTaskError("artifacts must be a non-empty ordered list of paths")
    artifacts = tuple(safe_artifact(path) for path in declared)
    if len(set(artifacts)) != len(artifacts):
        raise ManagedTaskError("artifacts must not contain duplicates")
    blocks = list(FILE_RE.finditer(body))
    contents = {match.group(1): match.group(2) for match in blocks}
    if len(contents) != len(blocks) or set(contents) != set(artifacts) or any(not contents[path].strip() for path in artifacts):
        raise ManagedTaskError("declared artifacts and explicit non-empty artifact blocks must match exactly")
    return Package(source_issue, target, manifest["change"], prepared, artifacts, contents, revision(manifest, artifacts, contents))


def openspec_status(root: Path, change: str) -> dict[str, Any]:
    value = run_json(["openspec", "status", "--change", change, "--json"], root)
    if not isinstance(value, dict) or not isinstance(value.get("artifactPaths"), dict):
        raise ManagedTaskError("OpenSpec status did not expose the current artifact contract")
    return value


def check_schema(root: Path, package: Package) -> None:
    paths = openspec_status(root, package.change)["artifactPaths"]
    required: set[str] = set()
    for name in ("proposal", "design", "tasks"):
        item = paths.get(name)
        if not isinstance(item, dict) or not isinstance(item.get("outputPath"), str):
            raise ManagedTaskError(f"current OpenSpec schema has no usable {name} artifact contract")
        required.add(item["outputPath"])
    specs = paths.get("specs")
    if not isinstance(specs, dict) or not isinstance(specs.get("outputPath"), str):
        raise ManagedTaskError("current OpenSpec schema has no usable specs artifact contract")
    if not required.issubset(package.artifacts) or not any(path.startswith("specs/") for path in package.artifacts):
        raise ManagedTaskError("managed package cannot satisfy the current OpenSpec schema")


def change_root(root: Path, change: str) -> Path:
    return (root / "openspec" / "changes" / change).resolve()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_change(root: Path, change: str) -> None:
    run(["openspec", "validate", change, "--strict", "--no-interactive"], root)


def target_main(root: Path) -> str:
    branch = str(read_platform_config(root).get("main_branch", "main"))
    run(["git", "fetch", "--prune", "origin", branch], root)
    return run(["git", "rev-parse", f"refs/remotes/origin/{branch}"], root).stdout.strip().lower()


def read_provenance(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / PROVENANCE).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManagedTaskError("same-name OpenSpec change exists without managed-task provenance") from exc
    except json.JSONDecodeError as exc:
        raise ManagedTaskError(f"managed-task provenance is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ManagedTaskError("managed-task provenance is invalid")
    return value


def write_provenance(root: Path, package: Package) -> None:
    atomic_write(
        root / PROVENANCE,
        json.dumps(
            {
                "version": 1, "source_issue": package.source_issue, "target_repository": package.target_repository,
                "change": package.change, "prepared_against": package.prepared_against,
                "package_revision": package.revision, "artifacts": list(package.artifacts),
                "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            },
            sort_keys=True, indent=2,
        ) + "\n",
    )


def import_task(root: Path, reference: str) -> tuple[Package, str, bool]:
    issue_repository, number = issue_ref(reference)
    requested = f"{issue_repository}#{number}"
    package = parse_package(issue_bodies(root, issue_repository, number), requested)
    if package.target_repository != origin_repository(root):
        raise ManagedTaskError(f"package targets {package.target_repository}, not this checkout; no files changed")
    current_main = target_main(root)
    destination = change_root(root, package.change)
    if destination.exists():
        provenance = read_provenance(destination)
        if provenance.get("source_issue", "").lower() != package.source_issue.lower():
            raise ManagedTaskError("same-name OpenSpec change belongs to a different source issue")
        if provenance.get("package_revision") != package.revision:
            raise ManagedTaskError("managed package changed after materialization; refusing to overwrite local OpenSpec")
        check_schema(root, package)
        validate_change(root, package.change)
        return package, current_main, True
    if shutil.which("openspec") is None:
        raise ManagedTaskError("installed OpenSpec CLI is required")
    created = False
    try:
        run_json(["openspec", "new", "change", package.change, "--json"], root)
        created = True
        if not destination.is_dir():
            raise ManagedTaskError("OpenSpec CLI did not create the expected change root")
        check_schema(root, package)
        for relative in package.artifacts:
            path = (destination / relative).resolve()
            if destination not in path.parents:
                raise ManagedTaskError(f"artifact escapes change root: {relative!r}")
            atomic_write(path, package.contents[relative])
        validate_change(root, package.change)
        write_provenance(destination, package)
    except Exception:
        if created and destination.is_dir():
            shutil.rmtree(destination)
        raise
    return package, current_main, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Import one managed OpenSpec package without starting implementation.")
    parser.add_argument("issue", help="owner/repo#N or GitHub issue URL")
    args = parser.parse_args()
    try:
        package, current_main, reused = import_task(current_worktree_root(), args.issue)
    except ManagedTaskError as exc:
        print(f"Managed task import blocked: {exc}")
        return 2
    freshness = "fresh" if package.prepared_against == current_main else "stale-needs-semantic-preflight"
    print(f"Managed task {'reused' if reused else 'materialized'}: {package.change} from {package.source_issue}")
    print(f"Package revision: {package.revision}")
    print(f"Prepared against: {package.prepared_against}")
    print(f"Current origin/main: {current_main}")
    print(f"Freshness: {freshness}")
    print("Next: perform semantic preflight against current specs/active changes, then use the existing OpenSpec lifecycle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
