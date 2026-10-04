"""Guard: test modules share one platform module instance regardless of order."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from types import ModuleType

from _platform_modules import identity_violations, load_platform_module

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
SCRIPTS = ROOT / "template" / "scripts"
HELPER = "_platform_modules.py"


def direct_registrations(path: Path) -> list[int]:
    """Line numbers assigning ``sys.modules[...]`` outside scoped patching."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines = []
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else []
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "modules"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "sys"
            ):
                lines.append(node.lineno)
    return lines


PROBE = textwrap.dedent(
    """\
    import importlib, json, sys
    sys.path[:0] = [{tests!r}, {scripts!r}]
    from _platform_modules import identity_violations
    names = json.loads(sys.argv[1])
    loaded = {{}}
    for name in names:
        loaded[name] = vars(importlib.import_module(name))
    print(json.dumps(identity_violations(loaded)))
    """
)


def test_module_names() -> list[str]:
    return sorted(path.stem for path in TESTS.glob("test_*.py"))


class PlatformModuleIdentityTests(unittest.TestCase):
    def test_tests_register_modules_only_through_the_shared_loader(self) -> None:
        offenders = {
            path.name: lines
            for path in sorted(TESTS.glob("*.py"))
            if path.name != HELPER and (lines := direct_registrations(path))
        }
        self.assertEqual(
            offenders,
            {},
            "register platform modules with _platform_modules.load_platform_module or scope "
            "a temporary stand-in with mock.patch.dict(sys.modules, ...)",
        )

    def test_scanner_detects_direct_registration(self) -> None:
        sample = TESTS / "fixtures" / "module_identity_sample.py"
        self.assertEqual(direct_registrations(sample), [6])

    def test_identity_holds_in_forward_and_reverse_import_order(self) -> None:
        names = [name for name in test_module_names() if name != Path(__file__).stem]
        probe = PROBE.format(tests=str(TESTS), scripts=str(SCRIPTS))
        for order in (names, list(reversed(names))):
            with self.subTest(first=order[0]):
                result = subprocess.run(
                    [sys.executable, "-c", probe, json.dumps(order)],
                    cwd=ROOT, capture_output=True, text=True, timeout=600,
                )
                self.assertEqual(result.returncode, 0, result.stderr[-4000:])
                self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1]), [])

    def test_loader_reuses_the_registered_instance(self) -> None:
        first = load_platform_module("start_tier_routing", SCRIPTS / "start_tier_routing.py")
        second = load_platform_module("start_tier_routing", SCRIPTS / "start_tier_routing.py")
        self.assertIs(first, second)
        self.assertIs(sys.modules["start_tier_routing"], first)

    def test_substituted_instance_is_reported(self) -> None:
        registered = load_platform_module("start_tier_routing", SCRIPTS / "start_tier_routing.py")
        stale = ModuleType("start_tier_routing")
        stale.__file__ = registered.__file__
        private = ModuleType("start_tier_routing_private_copy")
        private.__file__ = registered.__file__
        self.assertEqual(
            identity_violations({"test_sample": {"routing": stale, "fine": registered, "private": private}}),
            ["test_sample.routing holds a substituted start_tier_routing instance"],
        )


if __name__ == "__main__":
    unittest.main()
