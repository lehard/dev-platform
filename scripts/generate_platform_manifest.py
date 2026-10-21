#!/usr/bin/env python3
"""Generate or verify `template/dev-platform/platform-manifest.json`.

Source-only release-preparation tool (it is not copied downstream). The manifest
records the sha256 of every plain-copied (non-`.jinja`) platform-owned template
file that `template/dev-platform/protected-surface.toml` classifies. Plain files
render byte-identically, so the digest equals the digest of the same file in an
unmodified installed project. `template/scripts/platform_divergence.py` compares
an installed project with it.

Manifest shape::

    {"version": 1,
     "files": {"<rendered project-relative path>": "<sha256 hex of the bytes>"},
     "project_harness_owned": ["<path>", ...]}

`project_harness_owned` lists the listed files that Copier treats as project-owned
only when `harness_mode == 'project'` (conditional `_skip_if_exists` entries in
`copier.yml`); the divergence check ignores them for such projects. The manifest
itself and every literal project-owned file (`_skip_if_exists`/`_exclude`, with Copier's gitignore
semantics: a slashless name such as `README.md` also covers `docs/README.md`) are
not listed. The installed platform version is not stored here: it is read from the
project's `.dev-platform.toml` `platform_version`.

    python3 scripts/generate_platform_manifest.py --write   # regenerate
    python3 scripts/generate_platform_manifest.py --check   # fail on a stale manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
MANIFEST_RENDERED = "dev-platform/platform-manifest.json"
SURFACE = TEMPLATE / "dev-platform" / "protected-surface.toml"
MANIFEST = TEMPLATE / MANIFEST_RENDERED
MANIFEST_VERSION = 1
PROJECT_HARNESS_ENTRY = re.compile(r"^\{\{\s*'([^']+)'\s+if\s+harness_mode\s*==\s*'project'\s+else\s+'[^']+'\s*\}\}$")
GITLAB_EXCLUDE_ENTRY = re.compile(r"^\{\{\s*'([^']+)'\s+if\s+scm_provider\s*==\s*'gitlab'\s+else\s+'[^']+'\s*\}\}$")


class ManifestError(RuntimeError):
    """The template tree cannot be turned into a well-defined manifest."""


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


def plain_template_paths() -> list[str]:
    paths: list[str] = []
    for path in TEMPLATE.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(TEMPLATE).as_posix()
        if not relative.endswith(".jinja"):
            paths.append(relative)
    return sorted(paths)


def ownership() -> tuple[set[str], set[str], list[re.Pattern[str]]]:
    """Return (literal project-owned paths, project-harness-conditional paths, scm_provider=gitlab exclusion globs)."""
    config = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    literal: set[str] = set()
    conditional: set[str] = set()
    gitlab_only: list[re.Pattern[str]] = []
    for entry in config["_skip_if_exists"]:
        if "{{" not in entry:
            literal.add(entry)
            continue
        match = PROJECT_HARNESS_ENTRY.match(entry)
        if match is None:
            raise ManifestError(f"copier.yml _skip_if_exists entry {entry!r} has a form the manifest generator cannot classify")
        conditional.add(match.group(1))
    for entry in config["_exclude"]:
        if "{{" not in entry:
            literal.add(entry)
            continue
        match = GITLAB_EXCLUDE_ENTRY.match(entry)
        if match is None:
            raise ManifestError(f"copier.yml _exclude entry {entry!r} has a form the manifest generator cannot classify")
        gitlab_only.append(glob_regex(match.group(1)))
    return literal, conditional, gitlab_only


def is_project_owned(relative: str, literal: set[str]) -> bool:
    """Copier applies `_skip_if_exists`/`_exclude` with gitignore semantics.

    A pattern without `/` matches that name at any depth, so `README.md` also
    keeps an existing `docs/README.md`; a pattern with `/` is anchored at the root.
    """
    name = relative.rsplit("/", 1)[-1]
    return any(relative == entry or ("/" not in entry and name == entry) for entry in literal)


def sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict:
    surface = tomllib.loads(SURFACE.read_text(encoding="utf-8"))
    protected = [glob_regex(entry["path"]) for entry in surface["protected"]]
    hotfixable = set(surface["hotfixable"])
    literal, conditional, gitlab_only = ownership()
    files: dict[str, str] = {}
    for relative in plain_template_paths():
        if relative == MANIFEST_RENDERED or is_project_owned(relative, literal):
            continue
        if any(regex.match(relative) for regex in gitlab_only):
            raise ManifestError(f"{relative!r} is a plain file that Copier omits for scm_provider=gitlab; the manifest cannot list it")
        if relative not in hotfixable and not any(regex.match(relative) for regex in protected):
            raise ManifestError(f"platform-owned file {relative!r} is neither protected nor listed hotfixable; classify it in protected-surface.toml")
        files[relative] = sha256_hex(TEMPLATE / relative)
    unknown = sorted(path for path in conditional if path not in files and (TEMPLATE / path).is_file())
    if unknown:
        raise ManifestError(f"project-harness-conditional files are not manifest files: {unknown}")
    return {
        "version": MANIFEST_VERSION,
        "files": files,
        "project_harness_owned": sorted(path for path in conditional if path in files),
    }


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def mismatches(expected: dict, committed_text: str) -> list[str]:
    """Path-level differences between the generated and the committed manifest."""
    try:
        committed = json.loads(committed_text)
    except json.JSONDecodeError as exc:
        return [f"{MANIFEST_RENDERED}: committed manifest is not valid JSON: {exc}"]
    problems: list[str] = []
    if not isinstance(committed, dict) or set(committed) != set(expected):
        return [f"{MANIFEST_RENDERED}: committed manifest keys differ from the generated keys {sorted(expected)}"]
    if committed["version"] != expected["version"]:
        problems.append(f"{MANIFEST_RENDERED}: version {committed['version']!r} != {expected['version']!r}")
    committed_files = committed["files"]
    if not isinstance(committed_files, dict):
        return [f"{MANIFEST_RENDERED}: files must be an object"]
    for path in sorted(set(expected["files"]) | set(committed_files)):
        if path not in committed_files:
            problems.append(f"{path}: missing from the committed manifest")
        elif path not in expected["files"]:
            problems.append(f"{path}: listed in the committed manifest but not a platform-owned template file")
        elif committed_files[path] != expected["files"][path]:
            problems.append(f"{path}: committed sha256 {committed_files[path]} != template sha256 {expected['files'][path]}")
    if committed["project_harness_owned"] != expected["project_harness_owned"]:
        problems.append(f"{MANIFEST_RENDERED}: project_harness_owned differs from the generated list")
    if not problems and committed_text != render(expected):
        problems.append(f"{MANIFEST_RENDERED}: content equals the generated manifest but is not in canonical form")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="regenerate template/dev-platform/platform-manifest.json")
    group.add_argument("--check", action="store_true", help="exit non-zero naming every path whose digest differs from the template tree")
    args = parser.parse_args()
    try:
        expected = build_manifest()
    except ManifestError as exc:
        print(f"generate_platform_manifest: {exc}", file=sys.stderr)
        return 1
    if args.write:
        MANIFEST.write_text(render(expected), encoding="utf-8")
        print(f"Wrote {MANIFEST.relative_to(ROOT)} ({len(expected['files'])} files)")
        return 0
    if not MANIFEST.is_file():
        print(f"generate_platform_manifest: {MANIFEST_RENDERED} is missing; run with --write", file=sys.stderr)
        return 1
    problems = mismatches(expected, MANIFEST.read_text(encoding="utf-8"))
    if problems:
        for problem in problems:
            print(f"stale manifest: {problem}", file=sys.stderr)
        print("Regenerate with: python3 scripts/generate_platform_manifest.py --write", file=sys.stderr)
        return 1
    print(f"{MANIFEST_RENDERED} matches the template tree ({len(expected['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
