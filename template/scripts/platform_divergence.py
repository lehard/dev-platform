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
- missing-friction-event: the entry's friction evidence is not committed or is invalid.
  Every entry names an `agent_friction.py` event id (`friction_event`) and carries a
  committed sanitized copy of that event in `dev-platform/hotfix-friction/<id>.json`,
  bound by `friction_evidence_sha256`. The check verifies only committed data, so it
  behaves identically on a developer machine and on CI; it never reads the
  machine-local friction log unless asked. `scripts/platform_divergence.py
  export-friction <id>` writes the committed copy from the local log and prints the
  digest for the record. `--verify-local-friction-log` is the explicit local mode: it
  additionally requires the event in the machine-local log and fails if that log is
  absent or unreadable (never silently accepted).
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

import argparse
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from _platform_common import gate_message

MANIFEST_PATH = "dev-platform/platform-manifest.json"
SURFACE_PATH = "dev-platform/protected-surface.toml"
RECORD_PATH = "dev-platform/local-hotfixes.toml"
CONFIG_PATH = ".dev-platform.toml"
MANIFEST_VERSION = 1
ENTRY_FIELDS = frozenset({"path", "platform_version", "patched_sha256", "defect", "regression_test", "friction_event", "friction_evidence_sha256", "temporary"})
EVIDENCE_DIR = "dev-platform/hotfix-friction"
EVIDENCE_VERSION = 1
EVIDENCE_TEXT_FIELDS = ("id", "at", "category", "scope", "severity", "observation", "hypothesis", "proposal")
EVENT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
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
    for name in ("patched_sha256", "friction_evidence_sha256"):
        digest = entry.get(name)
        if isinstance(digest, str) and digest.strip() and not SHA256_RE.fullmatch(digest):
            problems.append(f"{name} must be 64 lowercase hex characters")
    event_id = entry.get("friction_event")
    if isinstance(event_id, str) and event_id.strip() and not EVENT_ID_RE.fullmatch(event_id):
        problems.append("friction_event must be a plain event id (letters, digits, '.', '_', '-')")
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


def friction_evidence_path(event_id: str) -> str:
    return f"{EVIDENCE_DIR}/{event_id}.json"


def committed_friction_problem(root: Path, entry: dict) -> str | None:
    """Verify the committed, sanitized friction evidence of one entry; None when it is valid."""
    event_id = entry["friction_event"]
    relative = friction_evidence_path(event_id)
    target = root / relative
    if not target.is_file():
        return f"friction evidence {relative} is not committed; run `python3 scripts/platform_divergence.py export-friction {event_id}` where the event was recorded and commit the file"
    try:
        raw = target.read_bytes()
        evidence = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"friction evidence {relative} cannot be read as JSON: {exc}"
    if not isinstance(evidence, dict):
        return f"friction evidence {relative} must be a JSON object"
    if evidence.get("version") != EVIDENCE_VERSION:
        return f"friction evidence {relative} has unsupported version {evidence.get('version')!r}"
    for name in EVIDENCE_TEXT_FIELDS:
        if not isinstance(evidence.get(name), str) or not evidence[name].strip():
            return f"friction evidence {relative} field {name!r} must be a non-empty string"
    unknown = sorted(set(evidence) - set(EVIDENCE_TEXT_FIELDS) - {"version"})
    if unknown:
        return f"friction evidence {relative} has unknown field(s) {unknown}"
    if evidence["id"] != event_id:
        return f"friction evidence {relative} names event {evidence['id']!r}, not {event_id!r}"
    if evidence["scope"] != "platform":
        return f"friction evidence {relative} must report a platform-scope defect, found scope {evidence['scope']!r}"
    actual = hashlib.sha256(raw).hexdigest()
    if actual != entry["friction_evidence_sha256"]:
        return f"friction evidence {relative} sha256 {actual} does not equal the recorded friction_evidence_sha256 {entry['friction_evidence_sha256']}"
    return None


def export_friction(root: Path, event_id: str) -> tuple[str, str]:
    """Write the sanitized committed copy of a machine-local friction event; return (path, sha256)."""
    if not EVENT_ID_RE.fullmatch(event_id):
        raise RecordError(f"{event_id!r} is not a plain friction event id")
    import agent_friction

    try:
        log = agent_friction.log_path()
    except (Exception, SystemExit) as exc:
        raise RecordError(f"the friction log location cannot be resolved through agent_friction.py: {exc!r}") from exc
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise RecordError(f"friction log {log} cannot be read: {exc}") from exc
    event = None
    for line in lines:
        if not line.strip():
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("id") == event_id:
            event = candidate
    if event is None:
        raise RecordError(f"friction event {event_id!r} is not in {log}")
    evidence = {"version": EVIDENCE_VERSION}
    for name in EVIDENCE_TEXT_FIELDS:
        if not isinstance(event.get(name), str) or not event[name].strip():
            raise RecordError(f"friction event {event_id!r} has no usable {name!r} field; it cannot be exported")
        evidence[name] = event[name]
    relative = friction_evidence_path(event_id)
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    target.write_bytes(payload)
    return relative, hashlib.sha256(payload).hexdigest()


def check(root: Path, *, verify_local_friction_log: bool = False) -> Result:
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
        reason = committed_friction_problem(root, entry)
        if reason is not None:
            result.problems.append(Problem(NO_FRICTION, path, reason))
        elif verify_local_friction_log:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local divergence from the installed platform release.")
    parser.add_argument("--verify-local-friction-log", action="store_true",
                        help="also require each hotfix's friction event in the machine-local friction log (developer machine)")
    sub = parser.add_subparsers(dest="command")
    export = sub.add_parser("export-friction", help="write the committed sanitized copy of a local friction event")
    export.add_argument("event_id")
    args = parser.parse_args(argv)
    if args.command == "export-friction":
        try:
            relative, digest = export_friction(Path.cwd().resolve(), args.event_id)
        except RecordError as exc:
            print(f"platform_divergence: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {relative}\nfriction_evidence_sha256 = \"{digest}\"")
        return 0
    result = check(Path.cwd().resolve(), verify_local_friction_log=args.verify_local_friction_log)
    if result.problems:
        for problem in result.problems:
            print(problem)
        protected = [problem for problem in result.problems if problem.kind == PROTECTED]
        other = [problem for problem in result.problems if problem.kind != PROTECTED]
        if other:
            print(gate_message("platform-divergence", f"{len(other)} divergence problem(s) outside the protected surface"))
        if protected:
            print(gate_message("platform-divergence-protected", f"{len(protected)} protected-touch problem(s)"))
        print(f"platform_divergence: FAILED with {len(result.problems)} problem(s)")
        return 1
    print(f"platform_divergence: OK ({result.checked} manifest files checked, {len(result.hotfixes)} declared hotfix(es))")
    for hotfix in result.hotfixes:
        print(f"hotfix: {hotfix.path} patched from platform {hotfix.platform_version}; temporary, not an official release; defect: {hotfix.defect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
