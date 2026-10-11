#!/usr/bin/env python3
"""Detect undeclared or unsafe local divergence from the installed platform release.

Run from the project root. Exit status 0 means every platform-owned file listed in
`dev-platform/platform-manifest.json` matches its release digest, or diverges only
through a valid, temporary hotfix declared in `dev-platform/local-hotfixes.toml`.
Any other state exits non-zero and prints one line per problem::

    [<class>] <path>: <message>

Failure classes:

- undeclared-divergence: a hotfixable manifest file differs from (or is missing
  against) the manifest and no hotfix entry covers it.
- protected-touch: a protected file (including the protected surface, this check and
  the manifest) differs from the manifest, or a hotfix entry names a protected path.
  Protected files have no local change path.
- unknown-path: a hotfix entry names a path that is not in the manifest.
- stale-hotfix: the entry's `platform_version` differs from the installed
  `.dev-platform.toml` platform_version (for example after a Copier update). The
  entry must be re-evaluated by a human or agent; this check never edits the record.
- digest-mismatch: the entry's `patched_sha256` is not the current digest of the
  file (or the patched file is missing, or the entry patches nothing).
- missing-regression-test: the entry's `regression_test` is not an existing file.
  Only presence is verified; the independent PR review judges whether the test
  really fails without the patch.
- missing-friction-event: the entry's `friction_event` is not in the machine-local
  friction log used by `agent_friction.py`, or that log cannot be read. An
  unreadable or absent log is reported, never accepted. The log is machine-local,
  so run this check where the friction event was recorded (the developer machine).
- invalid-record: the manifest, the protected surface, `.dev-platform.toml` or the
  record is missing, malformed or has a missing/unknown field. No default is
  substituted for any of them.

Limits, stated honestly. The check compares files with a manifest that is itself a
local file. An agent that edits a protected file *and* the manifest (and this
script) consistently cannot be detected by this local check. That tampering is
detected by the Copier update diff against the released template and by the
independent review of the PR, which stay mandatory. A hotfix is never an official
release, and this check does not claim a regression test proves the fix.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

MANIFEST_PATH = "dev-platform/platform-manifest.json"
SURFACE_PATH = "dev-platform/protected-surface.toml"
RECORD_PATH = "dev-platform/local-hotfixes.toml"
CONFIG_PATH = ".dev-platform.toml"
MANIFEST_VERSION = 1
ENTRY_FIELDS = frozenset({"path", "platform_version", "patched_sha256", "defect", "regression_test", "friction_event", "temporary"})
SHA256_RE = re.compile(r"[0-9a-f]{64}")

UNDECLARED = "undeclared-divergence"
PROTECTED = "protected-touch"
UNKNOWN = "unknown-path"
STALE = "stale-hotfix"
DIGEST = "digest-mismatch"
NO_TEST = "missing-regression-test"
NO_FRICTION = "missing-friction-event"
INVALID = "invalid-record"


@dataclass(frozen=True)
class Problem:
    kind: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.path}: {self.message}"


@dataclass(frozen=True)
class Hotfix:
    path: str
    platform_version: str
    defect: str


@dataclass
class Result:
    problems: list[Problem] = field(default_factory=list)
    hotfixes: list[Hotfix] = field(default_factory=list)
    checked: int = 0


class RecordError(Exception):
    """A required input file is missing or malformed."""


def glob_regex(pattern: str) -> re.Pattern[str]:
    """`*` and `?` stay inside one path segment; `**` crosses segments (as in protected-surface.toml)."""
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        out.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
        index += 1
    return re.compile("".join(out) + r"\Z")


def read_toml(root: Path, relative: str) -> dict:
    path = root / relative
    if not path.is_file():
        raise RecordError(f"{relative} is missing")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RecordError(f"{relative} cannot be read as TOML: {exc}") from exc


def load_manifest(root: Path) -> tuple[dict[str, str], frozenset[str]]:
    path = root / MANIFEST_PATH
    if not path.is_file():
        raise RecordError(f"{MANIFEST_PATH} is missing; the installed platform release carries it")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError(f"{MANIFEST_PATH} cannot be read as JSON: {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"version", "files", "project_harness_owned"}:
        raise RecordError(f"{MANIFEST_PATH} must be an object with exactly version, files and project_harness_owned")
    if manifest["version"] != MANIFEST_VERSION:
        raise RecordError(f"{MANIFEST_PATH} version {manifest['version']!r} is not supported (expected {MANIFEST_VERSION})")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise RecordError(f"{MANIFEST_PATH} files must be a non-empty object")
    for name, digest in files.items():
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise RecordError(f"{MANIFEST_PATH} files[{name!r}] is not a sha256 hex digest")
    owned = manifest["project_harness_owned"]
    if not isinstance(owned, list) or not all(isinstance(item, str) and item in files for item in owned):
        raise RecordError(f"{MANIFEST_PATH} project_harness_owned must list manifest files")
    return files, frozenset(owned)


def load_surface(root: Path) -> tuple[list[re.Pattern[str]], frozenset[str]]:
    surface = read_toml(root, SURFACE_PATH)
    protected = surface.get("protected")
    hotfixable = surface.get("hotfixable")
    if not isinstance(protected, list) or not all(isinstance(e, dict) and isinstance(e.get("path"), str) and e["path"] for e in protected):
        raise RecordError(f"{SURFACE_PATH} [[protected]] entries must each have a path")
    if not isinstance(hotfixable, list) or not all(isinstance(item, str) for item in hotfixable):
        raise RecordError(f"{SURFACE_PATH} hotfixable must be a list of paths")
    return [glob_regex(entry["path"]) for entry in protected], frozenset(hotfixable)


def load_platform_config(root: Path) -> tuple[str, str]:
    config = read_toml(root, CONFIG_PATH)
    version = config.get("platform_version")
    if not isinstance(version, str) or not version:
        raise RecordError(f"{CONFIG_PATH} platform_version must be a non-empty string")
    harness = config.get("harness_mode")
    if harness not in {"platform", "project"}:
        raise RecordError(f"{CONFIG_PATH} harness_mode must be 'platform' or 'project', not {harness!r}")
    return version, harness


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_project_relative(value: str) -> bool:
    pure = PurePosixPath(value)
    return bool(value) and pure.as_posix() == value and not pure.is_absolute() and ".." not in pure.parts and value != "."


def load_hotfix_entries(root: Path) -> list[dict]:
    record = read_toml(root, RECORD_PATH)
    unknown = sorted(set(record) - {"hotfix"})
    if unknown:
        raise RecordError(f"{RECORD_PATH} has unknown top-level key(s) {unknown}; only [[hotfix]] entries are allowed")
    entries = record.get("hotfix", [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise RecordError(f"{RECORD_PATH} hotfix must be an array of [[hotfix]] tables")
    return entries


def entry_shape_problems(entry: dict) -> list[str]:
    problems: list[str] = []
    missing = sorted(ENTRY_FIELDS - set(entry))
    unknown = sorted(set(entry) - ENTRY_FIELDS)
    if missing:
        problems.append(f"missing field(s) {missing}")
    if unknown:
        problems.append(f"unknown field(s) {unknown}")
    for name in sorted(ENTRY_FIELDS - {"temporary"}):
        if name in entry and not (isinstance(entry[name], str) and entry[name].strip()):
            problems.append(f"{name} must be a non-empty string")
    if "temporary" in entry and entry["temporary"] is not True:
        problems.append("temporary must be true: a hotfix is a temporary divergence, not an official release")
    for name in ("path", "regression_test"):
        if isinstance(entry.get(name), str) and entry[name].strip() and not is_project_relative(entry[name]):
            problems.append(f"{name} must be a normalized project-relative path")
    digest = entry.get("patched_sha256")
    if isinstance(digest, str) and digest.strip() and not SHA256_RE.fullmatch(digest):
        problems.append("patched_sha256 must be 64 lowercase hex characters")
    return problems


class FrictionLog:
    """Event ids of the machine-local friction log that `agent_friction.py` writes."""

    def __init__(self) -> None:
        self.ids: set[str] = set()
        self.error: str | None = None
        self.malformed = 0
        self.location = "the friction log"
        self._load()

    def _load(self) -> None:
        try:
            import agent_friction

            path = agent_friction.log_path()
        except (Exception, SystemExit) as exc:  # reported as the reason, never accepted silently
            self.error = f"the friction log location cannot be resolved through agent_friction.py: {exc!r}"
            return
        self.location = str(path)
        if not path.is_file():
            self.error = f"friction log {path} does not exist"
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self.error = f"friction log {path} cannot be read: {exc}"
            return
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                self.malformed += 1
                continue
            if isinstance(event, dict) and isinstance(event.get("id"), str):
                self.ids.add(event["id"])

    def problem_for(self, event_id: str) -> str | None:
        if self.error is not None:
            return f"friction event {event_id!r} cannot be verified: {self.error}"
        if event_id in self.ids:
            return None
        suffix = f" ({self.malformed} unparseable log line(s) were not counted)" if self.malformed else ""
        return f"friction event {event_id!r} is not in {self.location}{suffix}"


def check(root: Path) -> Result:
    result = Result()
    try:
        version, harness = load_platform_config(root)
        files, harness_owned = load_manifest(root)
        protected_globs, hotfixable = load_surface(root)
        entries = load_hotfix_entries(root)
    except RecordError as exc:
        result.problems.append(Problem(INVALID, "dev-platform", str(exc)))
        return result

    def is_protected(path: str) -> bool:
        return path == MANIFEST_PATH or any(regex.match(path) for regex in protected_globs)

    skipped = harness_owned if harness == "project" else frozenset()
    current: dict[str, str | None] = {}
    unreadable: set[str] = set()
    for path in sorted(files):
        if path in skipped:
            continue
        target = root / path
        try:
            current[path] = sha256_of(target) if target.is_file() else None
        except OSError as exc:
            result.problems.append(Problem(INVALID, path, f"cannot be read: {exc}"))
            unreadable.add(path)
    result.checked = len(current)

    friction: FrictionLog | None = None
    covered: set[str] = set()
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        label = entry["path"] if isinstance(entry.get("path"), str) and entry["path"] else f"{RECORD_PATH}[hotfix #{index}]"
        shape = entry_shape_problems(entry)
        if shape:
            result.problems.extend(Problem(INVALID, label, message) for message in shape)
            if isinstance(entry.get("path"), str):
                covered.add(entry["path"])
            continue
        path = entry["path"]
        if path in seen:
            result.problems.append(Problem(INVALID, path, "more than one hotfix entry covers this path"))
            continue
        seen.add(path)
        covered.add(path)
        if is_protected(path):
            result.problems.append(Problem(PROTECTED, path, "a hotfix entry names a protected path; protected files have no local change path and change only through a platform release"))
            continue
        if path not in files:
            result.problems.append(Problem(UNKNOWN, path, "a hotfix entry names a path that is not a platform-owned file in the release manifest"))
            continue
        if path in unreadable:
            continue
        if path in skipped:
            result.problems.append(Problem(INVALID, path, "this file is project-owned under harness_mode=project and needs no hotfix entry"))
            continue
        if path not in hotfixable:
            result.problems.append(Problem(INVALID, path, "the path is neither protected nor hotfixable in protected-surface.toml"))
            continue
        if entry["platform_version"] != version:
            result.problems.append(Problem(STALE, path, f"hotfix was made against platform {entry['platform_version']!r} but {version!r} is installed; re-evaluate the entry (the record is not modified)"))
            continue
        digest = current[path]
        if digest is None:
            result.problems.append(Problem(DIGEST, path, "the patched file is missing"))
        elif digest != entry["patched_sha256"]:
            result.problems.append(Problem(DIGEST, path, f"current sha256 {digest} does not equal the recorded patched_sha256 {entry['patched_sha256']}"))
        elif digest == files[path]:
            result.problems.append(Problem(DIGEST, path, "the recorded patched_sha256 equals the release digest; the entry describes no divergence"))
        if not (root / entry["regression_test"]).is_file():
            result.problems.append(Problem(NO_TEST, path, f"regression test {entry['regression_test']} does not exist (only its presence is checked)"))
        if friction is None:
            friction = FrictionLog()
        reason = friction.problem_for(entry["friction_event"])
        if reason is not None:
            result.problems.append(Problem(NO_FRICTION, path, reason))
        if not any(problem.path == path for problem in result.problems):
            result.hotfixes.append(Hotfix(path, entry["platform_version"], entry["defect"]))

    for path in sorted(current):
        digest = current[path]
        if digest == files[path] or path in covered:
            continue
        state = "is missing from the project" if digest is None else "differs from the release manifest"
        if is_protected(path):
            result.problems.append(Problem(PROTECTED, path, f"protected file {state}; protected files have no local change path"))
        else:
            result.problems.append(Problem(UNDECLARED, path, f"platform-owned file {state} and no hotfix entry in {RECORD_PATH} covers it"))
    return result


def main() -> int:
    result = check(Path.cwd().resolve())
    if result.problems:
        for problem in result.problems:
            print(problem)
        print(f"platform_divergence: FAILED with {len(result.problems)} problem(s)")
        return 1
    print(f"platform_divergence: OK ({result.checked} manifest files checked, {len(result.hotfixes)} declared hotfix(es))")
    for hotfix in result.hotfixes:
        print(f"hotfix: {hotfix.path} patched from platform {hotfix.platform_version}; temporary, not an official release; defect: {hotfix.defect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
