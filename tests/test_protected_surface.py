"""Fail-closed classification of the platform-owned template tree.

`template/dev-platform/protected-surface.toml` is the machine-readable boundary
between protected rules and hotfixable platform-owned mechanisms. These tests
require every plain-copied platform-owned file to be classified explicitly, so a
new unclassified file fails platform validation instead of receiving a default.
"""
from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SURFACE = TEMPLATE / "dev-platform" / "protected-surface.toml"
SURFACE_RENDERED = "dev-platform/protected-surface.toml"

# Rule categories the downstream contract must protect.
REQUIRED_CATEGORIES = (
    "independent-review",
    "protected-publication",
    "worktree-isolation",
    "credentials",
    "routing-provenance-evidence",
    "git-history",
    "immutable-releases",
)
SURFACE_KEYS = {"hotfixable", "categories", "protected"}
CONDITIONAL_PATH = re.compile(r"^\{\{\s*'([^']+)'\s+if\s+harness_mode\s*==\s*'project'\s+else\s+'[^']+'\s*\}\}$")


def glob_regex(pattern: str) -> re.Pattern[str]:
    """`*` and `?` stay inside one path segment; `**` crosses segments."""
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


def rendered_template_paths() -> tuple[set[str], set[str]]:
    """Return (every rendered path, plain-copied rendered paths) under template/."""
    every: set[str] = set()
    plain: set[str] = set()
    for path in TEMPLATE.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(TEMPLATE).as_posix()
        if relative.endswith(".jinja"):
            every.add(relative[: -len(".jinja")])
        else:
            every.add(relative)
            plain.add(relative)
    return every, plain


def project_owned_paths() -> set[str]:
    """Files Copier never overwrites or never renders: literal `_skip_if_exists` and `_exclude` entries.

    Entries of the form `{{ 'X' if harness_mode == 'project' else ... }}` are
    project-owned only for the `project` harness mode, so X stays platform-owned
    (and must be classified) for the default `platform` mode.
    """
    config = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    every, _ = rendered_template_paths()
    owned: set[str] = set()
    for key in ("_skip_if_exists", "_exclude"):
        for entry in config[key]:
            if "{{" in entry:
                if CONDITIONAL_PATH.match(entry) is None and key == "_skip_if_exists":
                    raise AssertionError(f"copier.yml {key} entry {entry!r} has a form this test cannot classify")
                continue
            owned.add(entry)
            if "/" not in entry:
                # Copier applies gitignore semantics: a slashless name matches at any depth
                # (`README.md` keeps an existing `docs/README.md`), so those files are project-owned too.
                owned |= {path for path in every if path.rsplit("/", 1)[-1] == entry}
    return owned


def surface_problems(surface: dict, every: set[str], plain: set[str], owned: set[str]) -> list[str]:
    """Every way the surface can fail to classify the platform-owned tree, naming the culprit."""
    problems: list[str] = []
    unknown_keys = set(surface) - SURFACE_KEYS
    missing_keys = SURFACE_KEYS - set(surface)
    if unknown_keys or missing_keys:
        return [f"protected-surface.toml keys must be exactly {sorted(SURFACE_KEYS)}; unknown={sorted(unknown_keys)} missing={sorted(missing_keys)}"]

    categories = surface["categories"]
    if not isinstance(categories, dict):
        return ["[categories] must be a table"]
    for category in REQUIRED_CATEGORIES:
        if category not in categories:
            problems.append(f"required protected category {category!r} is not declared in [categories]")
    for category, rationale in categories.items():
        if not isinstance(rationale, str) or not rationale.strip():
            problems.append(f"category {category!r} needs a one-line rationale")

    entries = surface["protected"]
    regexes: list[tuple[str, str, re.Pattern[str]]] = []
    for entry in entries:
        if set(entry) != {"path", "category"} or not all(isinstance(value, str) and value for value in entry.values()):
            problems.append(f"[[protected]] entry must be exactly a non-empty path and category: {entry!r}")
            continue
        if entry["category"] not in categories:
            problems.append(f"protected path {entry['path']!r} uses unknown category {entry['category']!r}")
            continue
        regexes.append((entry["path"], entry["category"], glob_regex(entry["path"])))

    covered: set[str] = set()
    for path, category, regex in regexes:
        matched = {candidate for candidate in every if regex.match(candidate)}
        if not matched:
            problems.append(f"protected glob {path!r} (category {category!r}) matches no existing template file")
        covered |= {category} if matched else set()
    for category in categories:
        if category not in covered:
            problems.append(f"category {category!r} has no existing protected path")

    hotfixable = surface["hotfixable"]
    if not isinstance(hotfixable, list) or not all(isinstance(item, str) for item in hotfixable):
        problems.append("hotfixable must be a list of explicit file paths")
        return problems
    duplicates = sorted({item for item in hotfixable if hotfixable.count(item) > 1})
    for item in duplicates:
        problems.append(f"hotfixable lists {item!r} more than once")

    obligation = {path for path in plain if path not in owned}
    for item in sorted(set(hotfixable)):
        if any(regex.match(item) for _, _, regex in regexes):
            problems.append(f"hotfixable file {item!r} is also matched by a protected glob")
        if item not in obligation:
            reason = "is project-owned" if item in owned else "does not exist as a plain-copied platform-owned template file"
            problems.append(f"hotfixable entry {item!r} {reason}")

    protected_or_hotfixable = set(hotfixable)
    for candidate in sorted(obligation):
        if candidate in protected_or_hotfixable or any(regex.match(candidate) for _, _, regex in regexes):
            continue
        problems.append(f"platform-owned file {candidate!r} is neither protected nor listed hotfixable; classify it explicitly")

    if not any(regex.match(SURFACE_RENDERED) for _, _, regex in regexes):
        problems.append(f"{SURFACE_RENDERED} must itself be matched by a protected glob")
    return problems


class ProtectedSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface = tomllib.loads(SURFACE.read_text(encoding="utf-8"))
        cls.every, cls.plain = rendered_template_paths()
        cls.owned = project_owned_paths()

    def test_template_tree_is_classified_without_a_default(self) -> None:
        problems = surface_problems(self.surface, self.every, self.plain, self.owned)
        self.assertEqual([], problems, "\n".join(problems))

    def test_every_required_category_has_an_existing_protected_path(self) -> None:
        for category in REQUIRED_CATEGORIES:
            with self.subTest(category=category):
                globs = [entry["path"] for entry in self.surface["protected"] if entry["category"] == category]
                self.assertTrue(globs, f"category {category!r} has no protected entry")
                self.assertTrue(
                    any(glob_regex(glob).match(path) for glob in globs for path in self.every),
                    f"category {category!r} has no existing protected path",
                )

    def test_slashless_copier_skip_entries_own_nested_files(self) -> None:
        # `README.md` in _skip_if_exists is a gitignore-style pattern, so Copier also keeps an existing docs/README.md.
        self.assertIn("docs/README.md", self.owned)
        self.assertNotIn("docs/README.md", self.surface["hotfixable"])

    def test_project_owned_files_are_never_classified_hotfixable(self) -> None:
        self.assertTrue(self.owned, "copier.yml declares no project-owned files")
        self.assertFalse(self.owned & set(self.surface["hotfixable"]))


class ProtectedSurfaceFailureModeTests(unittest.TestCase):
    """The classification fails closed: each violation is reported by name."""

    def setUp(self) -> None:
        self.every = {"scripts/a.py", "scripts/b.py", "docs/x.md", SURFACE_RENDERED, "README.md"}
        self.plain = {"scripts/a.py", "scripts/b.py", "docs/x.md", SURFACE_RENDERED, "README.md"}
        self.owned = {"README.md"}
        self.surface = {
            "categories": {category: f"rationale for {category}" for category in REQUIRED_CATEGORIES},
            "protected": [{"path": "scripts/a.py", "category": category} for category in REQUIRED_CATEGORIES]
            + [{"path": SURFACE_RENDERED, "category": "immutable-releases"}],
            "hotfixable": ["scripts/b.py", "docs/x.md"],
        }

    def problems(self) -> list[str]:
        return surface_problems(self.surface, self.every, self.plain, self.owned)

    def test_consistent_surface_has_no_problems(self) -> None:
        self.assertEqual([], self.problems())

    def test_unclassified_file_is_named_and_has_no_default_class(self) -> None:
        self.every.add("scripts/new.py")
        self.plain.add("scripts/new.py")
        self.assertEqual(["platform-owned file 'scripts/new.py' is neither protected nor listed hotfixable; classify it explicitly"], self.problems())

    def test_hotfixable_entry_matched_by_protected_glob_or_missing_is_reported(self) -> None:
        self.surface["hotfixable"].append("scripts/a.py")
        self.surface["hotfixable"].append("scripts/gone.py")
        text = "\n".join(self.problems())
        self.assertIn("hotfixable file 'scripts/a.py' is also matched by a protected glob", text)
        self.assertIn("hotfixable entry 'scripts/gone.py' does not exist", text)

    def test_project_owned_file_cannot_be_hotfixable(self) -> None:
        self.surface["hotfixable"].append("README.md")
        self.assertIn("hotfixable entry 'README.md' is project-owned", "\n".join(self.problems()))

    def test_category_without_existing_path_or_unknown_category_is_reported(self) -> None:
        self.surface["categories"]["extra"] = "no entry"
        self.surface["protected"].append({"path": "scripts/a.py", "category": "undeclared"})
        text = "\n".join(self.problems())
        self.assertIn("category 'extra' has no existing protected path", text)
        self.assertIn("uses unknown category 'undeclared'", text)

    def test_required_category_missing_is_reported(self) -> None:
        del self.surface["categories"]["credentials"]
        self.surface["protected"] = [entry for entry in self.surface["protected"] if entry["category"] != "credentials"]
        self.assertIn("required protected category 'credentials' is not declared", "\n".join(self.problems()))

    def test_protected_glob_matching_nothing_is_reported(self) -> None:
        self.surface["protected"].append({"path": "scripts/missing_*.py", "category": "credentials"})
        self.assertIn("protected glob 'scripts/missing_*.py' (category 'credentials') matches no existing template file", "\n".join(self.problems()))

    def test_surface_file_must_be_protected(self) -> None:
        self.surface["protected"] = [entry for entry in self.surface["protected"] if entry["path"] != SURFACE_RENDERED]
        self.assertIn(f"{SURFACE_RENDERED} must itself be matched by a protected glob", "\n".join(self.problems()))

    def test_single_star_does_not_cross_directories(self) -> None:
        self.assertIsNone(glob_regex("scripts/*.py").match("scripts/git_hooks/x.py"))
        self.assertIsNotNone(glob_regex("scripts/**").match("scripts/git_hooks/x.py"))


if __name__ == "__main__":
    unittest.main()
