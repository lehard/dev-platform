"""One module instance per platform source file within a test process.

Test modules load platform scripts by file path. Loading the same file again
under the same name used to replace the ``sys.modules`` entry, so production
code imported earlier kept one instance while a later test patched another and
results depended on module order inside a group. ``load_platform_module``
reuses an instance already registered for the same file and is the only place
tests register modules in ``sys.modules``; a test needing a temporary stand-in
uses ``mock.patch.dict(sys.modules, ...)`` instead.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_SOURCE_ROOTS = (ROOT / "template" / "scripts", ROOT / "scripts")


def _source(module: ModuleType) -> Path | None:
    filename = getattr(module, "__file__", None)
    return Path(filename).resolve() if filename else None


def load_platform_module(name: str, path: Path | str) -> ModuleType:
    """Return the module registered for ``path`` under ``name``, loading it once."""
    source = Path(path).resolve()
    existing = sys.modules.get(name)
    if existing is not None and _source(existing) == source:
        return existing
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader, f"cannot load {name} from {source}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(name) is module:
            if existing is not None:
                sys.modules[name] = existing
            else:
                del sys.modules[name]
        raise
    return module


def is_platform_source(module: ModuleType) -> bool:
    source = _source(module)
    return source is not None and any(source.is_relative_to(root) for root in PLATFORM_SOURCE_ROOTS)


def identity_violations(namespaces: dict[str, dict[str, object]]) -> list[str]:
    """Name every platform module a namespace holds beside another registered instance.

    A private instance under a name nothing registers is self-contained; one
    under a registered name is a duplicate production code may not be using.
    """
    violations = []
    for owner, namespace in sorted(namespaces.items()):
        for attribute, value in sorted(namespace.items()):
            if not isinstance(value, ModuleType) or not is_platform_source(value):
                continue
            registered = sys.modules.get(value.__name__)
            if registered is not None and registered is not value:
                violations.append(f"{owner}.{attribute} holds a substituted {value.__name__} instance")
    return violations
