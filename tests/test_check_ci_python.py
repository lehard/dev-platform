"""Developer validation compiles the platform's sources on the Python version CI pins."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

ci_python = load_platform_module("check_ci_python", ROOT / "scripts/check_ci_python.py")

LOCAL = "%d.%d" % sys.version_info[:2]
WORKFLOW = """
name: CI
on: pull_request
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "{version}"
      - run: python3 -m compileall -q src
"""


class CiPythonCheckTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workflow = self.root / "ci.yml"
        self.src = self.root / "src"
        self.src.mkdir()
        (self.src / "ok.py").write_text("value = 1\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def pin(self, version: str, text: str = WORKFLOW) -> None:
        self.workflow.write_text(text.format(version=version))

    def interpreter(self, name: str, *, reports: str, compiles: bool = True) -> None:
        """A fake ``python<x.y>`` on PATH that reports a version and compiles or fails like the CI version."""
        script = self.bin / name
        script.write_text("#!/bin/sh\n"
                          f'if [ "$1" = "-c" ]; then echo {reports}; exit 0; fi\n'
                          + ("exit 0\n" if compiles else
                             "echo '*** Error compiling src/nested.py' ; "
                             "echo 'SyntaxError: too many statically nested blocks'; exit 1\n"))
        script.chmod(0o755)

    def run_check(self, local: str):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            return ci_python.check(self.workflow, "validate", [str(self.src)], local)

    def test_matching_version_passes_without_a_second_compilation(self):
        self.pin(LOCAL)
        with mock.patch.object(ci_python.subprocess, "run", side_effect=AssertionError("compiled again")):
            code, message = self.run_check(LOCAL)
        self.assertEqual(code, 0)
        self.assertIn(f"local {LOCAL} matches CI {LOCAL}", message)

    def test_ci_only_compile_error_fails_naming_both_versions(self):
        self.pin("3.11")
        self.interpreter("python3.11", reports="3.11", compiles=False)
        code, message = self.run_check("3.13")
        self.assertEqual(code, 1)
        self.assertIn("local 3.13 but not on CI 3.11", message)
        self.assertIn("too many statically nested blocks", message)

    def test_mismatch_compiling_on_the_ci_version_passes_and_states_its_limit(self):
        self.pin("3.11")
        self.interpreter("python3.11", reports="3.11")
        code, message = self.run_check("3.13")
        self.assertEqual(code, 0)
        self.assertIn("local 3.13, CI 3.11", message)
        self.assertIn("only compile-time errors", message)

    def test_missing_or_wrong_ci_interpreter_is_refused_naming_both_versions(self):
        self.pin("3.11")
        code, message = self.run_check("3.13")
        self.assertEqual(code, 2)
        self.assertIn("local 3.13, CI 3.11: no python3.11 on PATH", message)
        self.interpreter("python3.11", reports="3.12")
        code, message = self.run_check("3.13")
        self.assertEqual(code, 2)
        self.assertIn("local 3.13, CI 3.11", message)
        self.assertIn("reports 3.12", message)

    def test_unreadable_ci_version_is_refused_naming_the_local_version(self):
        cases = {
            "missing workflow": None,
            "no setup-python": WORKFLOW.replace("actions/setup-python@v6", "actions/cache@v4"),
            "two setup-python": WORKFLOW + "      - uses: actions/setup-python@v6\n",
            "bad version": WORKFLOW.replace('"{version}"', '"3.x"'),
            "patch version": WORKFLOW.replace('"{version}"', '"3.11.4"'),
        }
        for case, text in cases.items():
            with self.subTest(case=case):
                if text is None:
                    self.workflow.unlink(missing_ok=True)
                else:
                    self.pin("3.11", text)
                code, message = self.run_check("3.13")
                self.assertEqual(code, 2)
                self.assertIn("local 3.13, CI version unreadable", message)

    def test_cli_compiles_real_sources_with_the_current_interpreter_when_versions_match(self):
        self.pin(LOCAL)
        done = subprocess.run([sys.executable, str(ROOT / "scripts/check_ci_python.py"), "--workflow", str(self.workflow),
                               "--job", "validate", "--compile", str(self.src)],
                              capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("matches", done.stdout)

    def test_repository_ci_workflow_pins_a_readable_version(self):
        self.assertRegex(ci_python.ci_version(ROOT / ".github/workflows/ci.yml", "validate"), r"^3\.\d+$")

    def test_full_check_set_runs_the_step(self):
        import tomllib

        settings = tomllib.loads((ROOT / "dev-platform/checks.toml").read_text())
        command = ("python3 scripts/check_ci_python.py --workflow .github/workflows/ci.yml --job validate "
                   "--compile template/scripts --compile scripts --compile tests")
        self.assertIn(command, settings["settings"]["full_commands"])
        self.assertIn(command, settings["checks"]["python"]["commands"])


if __name__ == "__main__":
    unittest.main()
