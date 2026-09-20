from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def module_names() -> list[str]:
    return sorted(path.stem for path in TESTS_DIR.glob("test_*.py"))


class ModuleImportIsolationTests(unittest.TestCase):
    """Every test module must be importable on its own, not only after some
    other module happened to run first and left sys.path/state behind it.

    Regression coverage for the platform-lifecycle "Two task worktrees
    validate concurrently" / group-partitioning requirement: a partitioned
    group can start any module first, so import order is not guaranteed.
    """

    def test_every_test_module_imports_standalone(self) -> None:
        names = module_names()
        self.assertGreater(len(names), 0)
        failures: dict[str, str] = {}
        for name in names:
            result = subprocess.run(
                [sys.executable, "-c", f"import sys; sys.path.insert(0, 'tests'); import importlib; importlib.import_module({name!r})"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                failures[name] = (result.stderr or result.stdout).strip().splitlines()[-1] if (result.stderr or result.stdout) else "unknown failure"
        if failures:
            detail = "; ".join(f"{name}: {message}" for name, message in sorted(failures.items()))
            self.fail(f"{len(failures)} test module(s) are not standalone-importable (hidden load-order dependency): {detail}")


if __name__ == "__main__":
    unittest.main()
