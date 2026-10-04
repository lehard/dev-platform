"""Map changed Python paths to the test modules that exercise them directly.

The map is derived statically from source: a test module references a Python
module by importing it or by naming it in a string (``"managed_task"``,
``"managed_task.py"``, ``".../managed_task.py"``). Transitive importers are
deliberately not followed: lifecycle scripts import each other so densely that
the closure selects nearly the whole suite. The result is early feedback only;
a path with no mapping contributes nothing, and callers still run the complete
validation set.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def _string_references(tree: ast.Module) -> set[str]:
    """Module names a string names exactly (``"x"``) or as a file (``"x.py"``, ``".../x.py"``)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if IDENTIFIER.fullmatch(node.value):
                names.add(node.value)
            for token in re.split(r"[\s/\\'\"(),=]+", node.value):
                if token.endswith(".py") and IDENTIFIER.fullmatch(token[:-3]):
                    names.add(token[:-3])
    return names


def _module_files(root: Path, source_roots: list[str]) -> dict[Path, str]:
    """Every Python file in the source roots, keyed by resolved path, valued by module name."""
    files: dict[Path, str] = {}
    for relative in source_roots:
        directory = root / relative
        if directory.is_dir():
            for path in sorted(directory.glob("*.py")):
                files[path.resolve()] = path.stem
    return files


def affected_groups(
    root: Path,
    groups: dict[str, dict[str, Any]],
    changed: list[str],
    *,
    start_dir: str,
    source_roots: list[str],
) -> dict[str, Any]:
    """Return mapped test targets per canonical group and the unmapped paths."""
    tests = root / start_dir
    references: dict[str, set[str]] = {}
    for rule in groups.values():
        for target in rule["targets"]:
            module = target.split(".")[0]
            if module not in references:
                tree = _parse(tests / f"{module}.py")
                references[module] = set() if tree is None else _imports(tree) | _string_references(tree)
    files = _module_files(root, [*source_roots, start_dir])
    tests_prefix = start_dir.rstrip("/") + "/"

    selected: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for path in changed:
        candidate = Path(path)
        matched = False
        stem = files.get((root / path).resolve()) if candidate.suffix == ".py" else None
        # A shared test helper (a non-test module under the test root) feeds
        # nearly every test module; it goes straight to the full set instead.
        if stem is not None and path.startswith(tests_prefix) and stem not in references:
            stem = None
        if stem is not None:
            direct_test = path.startswith(tests_prefix) and stem in references
            for group, rule in groups.items():
                for target in rule["targets"]:
                    module = target.split(".")[0]
                    if (direct_test and module == stem) or (not direct_test and stem in references[module]):
                        matched = True
                        if target not in selected.setdefault(group, []):
                            selected[group].append(target)
        if not matched:
            unmapped.append(path)
    return {"groups": {group: selected[group] for group in sorted(selected)}, "unmapped": unmapped}
