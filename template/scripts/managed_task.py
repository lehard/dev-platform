#!/usr/bin/env python3
"""Managed task intake and authoring."""
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
from urllib.parse import quote, urlparse

from _platform_common import atomic_write_text, current_worktree_root, github_cli_env, harness_mode, main_root, profile, read_platform_config, run_git

PACKAGE = "managed-openspec:v1"
MARKER_RE = re.compile(r"<!--\s*(managed-openspec:v[0-9]+)\s*-->")
MANIFEST_RE = re.compile(r"<!--\s*managed-openspec:v1\s*-->[\s\S]*?(?:\x60){3}json\s*\n([\s\S]*?)\n(?:\x60){3}", re.I)
FILE_RE = re.compile(r"<!--\s*managed-openspec:file:([^\s]+)\s*-->\n([\s\S]*?)<!--\s*managed-openspec:endfile\s*-->")
REF_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)$")
CHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVENANCE = ".managed-task.json"
AUTHORING_RECEIPT_RE = re.compile(r"<!--\s*managed-task:authoring:([0-9a-f]{64})\s*-->")
ISSUE_TARGET_RE = re.compile(r"^\*\*Target repository:\*\*\s*`([^`]+)`", re.MULTILINE)
ISSUE_CHANGE_RE = re.compile(r"^\*\*OpenSpec change:\*\*\s*`([^`]+)`", re.MULTILINE)
PRIORITY_RE = re.compile(r"^P[0-3]$")


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


@dataclass(frozen=True)
class AuthoringConfig:
    repository: str
    project_label: str
    default_priority: str


@dataclass(frozen=True)
class AuthoringBundle:
    title: str
    issue_body: str
    change: str
    artifacts: tuple[str, ...]
    contents: dict[str, str]


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


def run(command: list[str], root: Path, env: dict[str, str] | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, input=input_text)
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


def authoring_config(root: Path) -> AuthoringConfig:
    value = read_platform_config(root).get("development_backlog")
    if not isinstance(value, dict):
        raise ManagedTaskError("Development Backlog authoring is not configured; add [development_backlog] to .dev-platform.toml")
    repository = value.get("repository")
    project_label = value.get("project_label")
    default_priority = value.get("default_priority")
    if not isinstance(repository, str):
        raise ManagedTaskError("development_backlog.repository must be owner/name")
    if not isinstance(project_label, str) or not re.fullmatch(r"project:[A-Za-z0-9_.-]+", project_label):
        raise ManagedTaskError("development_backlog.project_label must be a project:<slug> label")
    if not isinstance(default_priority, str) or not PRIORITY_RE.fullmatch(default_priority):
        raise ManagedTaskError("development_backlog.default_priority must be one of P0, P1, P2 or P3")
    return AuthoringConfig(repo(repository), project_label, default_priority)


def priority_label(value: str) -> str:
    if not PRIORITY_RE.fullmatch(value):
        raise ManagedTaskError("priority must be one of P0, P1, P2 or P3")
    return f"priority:{value}"


def contained_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise ManagedTaskError(f"authoring bundle artifact is missing or escapes the bundle: {relative!r}")
    return path


def load_authoring_bundle(value: str) -> AuthoringBundle:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ManagedTaskError("authoring bundle must be a directory")
    manifest_path = contained_file(root, "manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManagedTaskError(f"authoring bundle manifest is not valid JSON: {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise ManagedTaskError("authoring bundle manifest must be a JSON object")
    title = manifest.get("title")
    change = manifest.get("change")
    declared = manifest.get("artifacts")
    if not isinstance(title, str) or not title.strip():
        raise ManagedTaskError("authoring bundle manifest needs a non-empty title")
    if not isinstance(change, str) or not CHANGE_RE.fullmatch(change):
        raise ManagedTaskError("authoring bundle change must be a lowercase OpenSpec change name")
    if not isinstance(declared, list) or not declared or not all(isinstance(item, str) for item in declared):
        raise ManagedTaskError("authoring bundle artifacts must be a non-empty ordered list")
    artifacts = tuple(safe_artifact(item) for item in declared)
    if len(set(artifacts)) != len(artifacts):
        raise ManagedTaskError("authoring bundle artifacts must not contain duplicates")
    issue_body = contained_file(root, "issue.md").read_text(encoding="utf-8")
    if not issue_body.strip():
        raise ManagedTaskError("authoring bundle issue.md must not be empty")
    contents = {path: contained_file(root, path).read_text(encoding="utf-8") for path in artifacts}
    if any(not content.strip() for content in contents.values()):
        raise ManagedTaskError("authoring bundle artifacts must not be empty")
    return AuthoringBundle(title.strip(), issue_body, change, artifacts, contents)


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


def package_for_bundle(bundle: AuthoringBundle, source_issue: str, target_repository: str, prepared_against: str) -> Package:
    manifest = {
        "version": 1,
        "source_issue": source_issue,
        "target_repository": target_repository,
        "change": bundle.change,
        "prepared_against": prepared_against,
        "artifacts": list(bundle.artifacts),
    }
    return Package(
        source_issue=source_issue,
        target_repository=target_repository,
        change=bundle.change,
        prepared_against=prepared_against,
        artifacts=bundle.artifacts,
        contents=bundle.contents,
        revision=revision(manifest, bundle.artifacts, bundle.contents),
    )


def serialize_package(package: Package) -> str:
    manifest = {
        "version": 1,
        "source_issue": package.source_issue,
        "target_repository": package.target_repository,
        "change": package.change,
        "prepared_against": package.prepared_against,
        "artifacts": list(package.artifacts),
    }
    fence = "`" * 3
    parts = [f"<!-- {PACKAGE} -->\n\n## Managed OpenSpec package\n\n{fence}json\n", json.dumps(manifest, indent=2), f"\n{fence}\n"]
    for path in package.artifacts:
        parts.extend((f"\n### OpenSpec artifact: `{path}`\n<!-- managed-openspec:file:{path} -->\n", package.contents[path], "<!-- managed-openspec:endfile -->\n"))
    return "".join(parts)


def authoring_receipt(bundle: AuthoringBundle, target_repository: str, prepared_against: str) -> str:
    digest = hashlib.sha256()
    for value in (target_repository, prepared_against, bundle.title, bundle.issue_body, bundle.change):
        digest.update(value.encode())
        digest.update(bytes([0]))
    for path in bundle.artifacts:
        digest.update(path.encode())
        digest.update(bytes([0]))
        digest.update(bundle.contents[path].encode())
        digest.update(bytes([0]))
    return digest.hexdigest()


def validate_authoring_bundle(root: Path, bundle: AuthoringBundle, target_repository: str, prepared_against: str) -> None:
    """Validate in a short-lived real change root so the current CLI owns syntax checks."""
    if shutil.which("openspec") is None:
        raise ManagedTaskError("installed OpenSpec CLI is required")
    destination = change_root(root, bundle.change)
    if destination.exists():
        raise ManagedTaskError(f"OpenSpec change {bundle.change!r} already exists; authoring must not overwrite active local planning")
    package = package_for_bundle(bundle, "placeholder/issue#1", target_repository, prepared_against)
    created = False
    try:
        run_json(["openspec", "new", "change", bundle.change, "--json"], root)
        created = True
        if not destination.is_dir():
            raise ManagedTaskError("OpenSpec CLI did not create the expected temporary change root")
        check_schema(root, package)
        for relative in package.artifacts:
            atomic_write((destination / relative).resolve(), package.contents[relative])
        validate_change(root, bundle.change)
    finally:
        if created and destination.is_dir():
            shutil.rmtree(destination)


def change_root(root: Path, change: str) -> Path:
    return (root / "openspec" / "changes" / change).resolve()


def atomic_write(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def validate_change(root: Path, change: str) -> None:
    run(["openspec", "validate", change, "--strict", "--no-interactive"], root)


def target_main(root: Path) -> str:
    branch = str(read_platform_config(root).get("main_branch", "main"))
    run(["git", "fetch", "--prune", "origin", branch], root)
    return run(["git", "rev-parse", f"refs/remotes/origin/{branch}"], root).stdout.strip().lower()


def open_backlog_issues(root: Path, config: AuthoringConfig) -> list[dict[str, Any]]:
    env = github_cli_env(root)
    if env is None:
        raise ManagedTaskError("GitHub CLI authentication is required; run gh auth login and retry")
    endpoint = f"repos/{config.repository}/issues?state=open&per_page=100&labels={quote(config.project_label, safe='')}"
    value = run_json(["gh", "api", "--paginate", endpoint], root, env)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ManagedTaskError("GitHub returned an invalid open-issue list for duplicate checking")
    return [item for item in value if "pull_request" not in item]


def validate_backlog_labels(root: Path, config: AuthoringConfig, priority: str) -> None:
    """Fail before Issue creation when configured labels cannot be applied."""
    env = github_cli_env(root)
    if env is None:
        raise ManagedTaskError("GitHub CLI authentication is required; run gh auth login and retry")
    for label in (config.project_label, priority_label(priority)):
        value = run_json(["gh", "api", f"repos/{config.repository}/labels/{quote(label, safe='')}"], root, env)
        if not isinstance(value, dict) or value.get("name") != label:
            raise ManagedTaskError(f"configured Development Backlog label is unavailable: {label}")


def issue_metadata(issue: dict[str, Any]) -> tuple[str | None, str | None]:
    body = str(issue.get("body") or "")
    target_match = ISSUE_TARGET_RE.search(body)
    change_match = ISSUE_CHANGE_RE.search(body)
    try:
        target = repo(target_match.group(1)) if target_match else None
    except ManagedTaskError:
        target = None
    change = change_match.group(1) if change_match else None
    return target, change


def candidate_summary(issues: list[dict[str, Any]], target_repository: str, change: str, receipt: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any] | None]:
    resumed: dict[str, Any] | None = None
    exact: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = []
    for issue in issues:
        body = str(issue.get("body") or "")
        if receipt in AUTHORING_RECEIPT_RE.findall(body):
            resumed = issue
            continue
        target, existing_change = issue_metadata(issue)
        if target != target_repository:
            continue
        if existing_change == change:
            exact = issue
        else:
            candidates.append(issue)
    return exact, candidates, resumed


def issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("number")
    if not isinstance(value, int) or value < 1:
        raise ManagedTaskError("GitHub returned an issue without a valid number")
    return value


def summarize_candidates(issues: list[dict[str, Any]]) -> str:
    return ", ".join(f"#{issue_number(item)} {str(item.get('title') or '').strip()!r}" for item in issues[:10])


def create_issue(root: Path, config: AuthoringConfig, bundle: AuthoringBundle, target_repository: str, priority: str, receipt: str) -> int:
    env = github_cli_env(root)
    if env is None:
        raise ManagedTaskError("GitHub CLI authentication is required; run gh auth login and retry")
    body = (
        f"**Target repository:** `{target_repository}`\n\n"
        f"**OpenSpec change:** `{bundle.change}`\n\n"
        + bundle.issue_body.rstrip()
        + f"\n\n<!-- managed-task:authoring:{receipt} -->\n"
    )
    result = run(
        [
            "gh", "issue", "create", "--repo", config.repository, "--title", bundle.title,
            "--body", body, "--label", config.project_label, "--label", priority_label(priority),
        ],
        root,
        env,
    )
    _, number = issue_ref(result.stdout.strip())
    return number


def publish_package(root: Path, config: AuthoringConfig, package: Package) -> bool:
    bodies = issue_bodies(root, config.repository, int(package.source_issue.rsplit("#", 1)[1]))
    marker_count = sum(len(MARKER_RE.findall(body)) for body in bodies)
    if marker_count:
        existing = parse_package(bodies, package.source_issue)
        if existing.revision != package.revision:
            raise ManagedTaskError("existing managed package for the authoring receipt differs; refusing to publish another one")
        return True
    env = github_cli_env(root)
    if env is None:
        raise ManagedTaskError("GitHub CLI authentication is required; run gh auth login and retry")
    endpoint = f"repos/{config.repository}/issues/{int(package.source_issue.rsplit('#', 1)[1])}/comments"
    # The REST endpoint requires a JSON object with a `body` field. Passing
    # Markdown via --input makes gh parse that Markdown as the entire JSON
    # request, which GitHub rejects with HTTP 400.
    run(
        ["gh", "api", "--method", "POST", endpoint, "--raw-field", "body=" + serialize_package(package)],
        root,
        env,
    )
    return False


def create_task(root: Path, bundle_path: str, requested_priority: str | None, confirm_distinct: bool) -> tuple[Package, bool, bool]:
    config = authoring_config(root)
    bundle = load_authoring_bundle(bundle_path)
    priority = requested_priority or config.default_priority
    priority_label(priority)
    target_repository = origin_repository(root)
    prepared_against = target_main(root)
    validate_backlog_labels(root, config, priority)
    validate_authoring_bundle(root, bundle, target_repository, prepared_against)
    receipt = authoring_receipt(bundle, target_repository, prepared_against)
    issues = open_backlog_issues(root, config)
    exact, candidates, resumed = candidate_summary(issues, target_repository, bundle.change, receipt)
    if resumed is not None:
        number = issue_number(resumed)
        package = package_for_bundle(bundle, f"{config.repository}#{number}", target_repository, prepared_against)
        already_published = publish_package(root, config, package)
        return package, True, already_published
    if exact is not None:
        raise ManagedTaskError(f"clear duplicate already exists: {config.repository}#{issue_number(exact)}; no issue was created")
    if candidates and not confirm_distinct:
        raise ManagedTaskError(
            "potential same-project/target tasks require an explicit scope decision: "
            + summarize_candidates(candidates)
            + "; review them, then rerun with --confirm-distinct if this is a separate change"
        )
    number = create_issue(root, config, bundle, target_repository, priority, receipt)
    package = package_for_bundle(bundle, f"{config.repository}#{number}", target_repository, prepared_against)
    already_published = publish_package(root, config, package)
    return package, False, already_published


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


def discover_task(root: Path, reference: str) -> Package:
    issue_repository, number = issue_ref(reference)
    requested = f"{issue_repository}#{number}"
    package = parse_package(issue_bodies(root, issue_repository, number), requested)
    if package.target_repository != origin_repository(root):
        raise ManagedTaskError(f"package targets {package.target_repository}, not this checkout; no files changed")
    return package


def direct_materialization_is_forbidden(root: Path) -> bool:
    """Return whether this is the platform integration checkout of a feature profile."""
    config = read_platform_config(root)
    if harness_mode(config) != "platform" or profile(config) not in {"standard", "multi-agent"}:
        return False
    try:
        integration = main_root()
        branch = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return False
    return root.resolve() == integration.resolve() and branch == str(config.get("main_branch", "main"))


def import_task(root: Path, reference: str, *, expected_revision: str | None = None) -> tuple[Package, str, bool]:
    package = discover_task(root, reference)
    if expected_revision is not None and package.revision != expected_revision:
        raise ManagedTaskError("managed package changed after discovery; refusing to materialize a different revision")
    if direct_materialization_is_forbidden(root):
        raise ManagedTaskError("managed import from the platform integration branch is blocked; use scripts/start_managed_task.py owner/repo#N")
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
    parser = argparse.ArgumentParser(description="Import or author one managed OpenSpec task without starting implementation.")
    subcommands = parser.add_subparsers(dest="command")
    create = subcommands.add_parser("create", help="publish a prepared managed-task bundle and stop")
    create.add_argument("--bundle", required=True, help="directory containing manifest.json, issue.md and declared OpenSpec artifacts")
    create.add_argument("--priority", help="override configured priority (P0, P1, P2 or P3)")
    create.add_argument("--confirm-distinct", action="store_true", help="confirm that bounded same-project/target candidates are separate work")
    parser.add_argument("issue", nargs="?", help="owner/repo#N or GitHub issue URL to import")
    args = parser.parse_args()
    if args.command == "create":
        try:
            package, resumed, already_published = create_task(
                current_worktree_root(), args.bundle, args.priority, args.confirm_distinct
            )
        except ManagedTaskError as exc:
            print(f"Managed task authoring blocked: {exc}")
            return 2
        state = "resumed" if resumed else "created"
        package_state = "already present" if already_published else "published"
        print(f"Managed task {state}: {package.source_issue} ({package.change})")
        print(f"Managed OpenSpec package {package_state}: {PACKAGE}")
        print("Authoring stops here; import the task later only when the user explicitly requests execution.")
        return 0
    if not args.issue:
        parser.error("an issue is required for import, or use create --bundle <directory>")
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
