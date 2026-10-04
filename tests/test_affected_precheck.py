"""Affected-test precheck: direct-reference mapping and fail-early validation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

affected = load_platform_module("affected_test_groups", SCRIPTS / "affected_test_groups.py")
select_checks = load_platform_module("select_checks", SCRIPTS / "select_checks.py")

PASSING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
FAILING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_fails(self):\n        self.fail('broken')\n"


def fixture(root: Path) -> dict[str, dict[str, object]]:
    (root / "lib").mkdir()
    (root / "tests").mkdir()
    (root / "lib" / "alpha.py").write_text("import beta\n", encoding="utf-8")
    (root / "lib" / "beta.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "lib" / "gamma.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "tests" / "test_uses_alpha.py").write_text("import alpha\n" + PASSING, encoding="utf-8")
    (root / "tests" / "test_names_beta.py").write_text('PATH = "lib/beta.py"\n' + PASSING, encoding="utf-8")
    (root / "tests" / "test_unrelated.py").write_text(PASSING, encoding="utf-8")
    return {
        "one": {"targets": ["test_uses_alpha", "test_unrelated"], "mode": "parallel"},
        "two": {"targets": ["test_names_beta.T"], "mode": "serial"},
    }


class AffectedMappingTests(unittest.TestCase):
    def map(self, root: Path, groups: dict[str, dict[str, object]], changed: list[str]) -> dict[str, object]:
        return affected.affected_groups(root, groups, changed, start_dir="tests", source_roots=["lib"])

    def test_import_and_string_references_select_only_direct_test_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            groups = fixture(root)
            self.assertEqual(self.map(root, groups, ["lib/alpha.py"]), {"groups": {"one": ["test_uses_alpha"]}, "unmapped": []})
            # beta is imported by alpha, but transitive importers are not followed.
            self.assertEqual(self.map(root, groups, ["lib/beta.py"]), {"groups": {"two": ["test_names_beta.T"]}, "unmapped": []})

    def test_changed_test_module_selects_itself(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            groups = fixture(root)
            self.assertEqual(self.map(root, groups, ["tests/test_unrelated.py"]), {"groups": {"one": ["test_unrelated"]}, "unmapped": []})

    def test_same_stem_in_two_source_roots_maps_by_actual_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            groups = fixture(root)
            (root / "wrappers").mkdir()
            (root / "wrappers" / "alpha.py").write_text("# wrapper\n", encoding="utf-8")
            result = affected.affected_groups(root, groups, ["wrappers/alpha.py"], start_dir="tests", source_roots=["lib", "wrappers"])
            self.assertEqual(result, {"groups": {"one": ["test_uses_alpha"]}, "unmapped": []})

    def test_unreferenced_and_non_python_paths_are_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            groups = fixture(root)
            self.assertEqual(
                self.map(root, groups, ["lib/gamma.py", "dev-platform/checks.toml", "docs/x.md"]),
                {"groups": {}, "unmapped": ["lib/gamma.py", "dev-platform/checks.toml", "docs/x.md"]},
            )


class RunnerAffectedModeTests(unittest.TestCase):
    def run_main(self, root: Path, config: str, *argv: str) -> tuple[int, str, str]:
        import io
        import os
        import tomllib
        from contextlib import redirect_stderr, redirect_stdout

        runner = load_platform_module("run_test_groups", SCRIPTS / "run_test_groups.py")
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(runner, "current_worktree_root", return_value=root),
            mock.patch.object(runner, "load_check_config", return_value=tomllib.loads(config)),
            mock.patch.object(sys, "argv", ["run_test_groups.py", *argv]),
            mock.patch.dict(os.environ, {"PYTHONPATH": str(root / "lib")}),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = runner.main()
        return code, out.getvalue(), err.getvalue()

    CONFIG = (
        '[settings]\naffected_source_roots = ["lib"]\n'
        '[test_groups.one]\ntargets = ["test_uses_alpha", "test_unrelated"]\nmode = "parallel"\n'
        '[test_groups.two]\ntargets = ["test_names_beta"]\nmode = "serial"\n'
    )

    def test_changed_file_runs_only_mapped_modules_and_reports_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "tests" / "test_uses_alpha.py").write_text("import alpha\n" + FAILING, encoding="utf-8")
            code, out, _ = self.run_main(root, self.CONFIG, "--quiet", "--changed-file", "lib/alpha.py")
            self.assertEqual(code, 1, out)
            self.assertIn('"groups": {"one": ["test_uses_alpha"]}', out)
            self.assertIn('"mode": "affected"', out)
            code, out, _ = self.run_main(root, self.CONFIG, "--quiet", "--changed-file", "lib/beta.py")
            self.assertEqual(code, 0, out)
            code, out, _ = self.run_main(root, self.CONFIG, "--quiet", "--changed-file", "lib/gamma.py")
            self.assertEqual(code, 0)
            self.assertIn("nothing to run", out)

    def test_changed_file_cannot_claim_full_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            code, _, err = self.run_main(root, self.CONFIG, "--all", "--changed-file", "lib/alpha.py")
            self.assertEqual(code, 2)
            self.assertIn("cannot be combined with --all", err)


class SelectChecksPrecheckTests(unittest.TestCase):
    def test_outcome_distinguishes_failures_crashes_and_empty_selection(self) -> None:
        run = lambda code, out: subprocess.CompletedProcess("pre", code, out, "")  # noqa: E731
        self.assertEqual(select_checks.precheck_outcome(run(1, 'DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": ["g"]}')), "failure")
        self.assertEqual(select_checks.precheck_outcome(run(1, "Traceback: ImportError")), "unavailable")
        self.assertEqual(select_checks.precheck_outcome(run(1, "DEV_PLATFORM_TEST_AGGREGATE: {trunc")), "unavailable")
        self.assertEqual(select_checks.precheck_outcome(run(0, 'DEV_PLATFORM_AFFECTED_SELECTION: {"groups": {}, "unmapped": ["a.py"]}')), "not-applicable")
        self.assertEqual(select_checks.precheck_outcome(run(0, 'DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": []}')), "success")

    CONFIG = {"settings": {"affected_precheck": True}, "test_groups": {"one": {"targets": ["test_x"]}}}

    def test_precheck_paths_only_for_opted_in_full_selections(self) -> None:
        full = [{"id": "full-trigger", "selection_reason": "high-impact-path", "paths": ["a.py", "b.toml"], "commands": ["x"]}]
        self.assertEqual(select_checks.precheck_paths(self.CONFIG, full), ["a.py"])
        self.assertEqual(select_checks.precheck_paths({"settings": {}, "test_groups": {"g": {}}}, full), [])
        mapped = [{"id": "docs", "paths": ["a.py"], "commands": ["x"]}]
        self.assertEqual(select_checks.precheck_paths(self.CONFIG, mapped), [])

    def test_failed_precheck_stops_before_full_commands_and_keeps_command_evidence_clean(self) -> None:
        failed = subprocess.CompletedProcess("pre", 1, 'precheck-detail\nDEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": ["one"]}\n', "")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(select_checks.subprocess, "run", return_value=failed) as run:
            evidence = Path(directory) / "evidence.json"
            outcome = select_checks.execute(Path(directory), [{"id": "full-trigger", "commands": ["full-suite"]}], evidence, None, ["a.py"])
            payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(outcome, 1)
        self.assertEqual(run.call_count, 1)
        self.assertIn("--changed-file a.py", run.call_args.args[0])
        self.assertEqual(payload["outcome"], "failure")
        self.assertEqual(payload["executed_commands"], [])
        self.assertEqual(payload["affected_precheck"]["outcome"], "failure")

    def test_precheck_tooling_error_does_not_block_the_full_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            real_run = subprocess.run

            def fake(command, **kwargs):
                if "run_test_groups.py" in command:
                    return subprocess.CompletedProcess(command, 2, "", "config error")
                return real_run(command, **kwargs)

            with mock.patch.object(select_checks.subprocess, "run", side_effect=fake):
                outcome = select_checks.execute(Path(directory), [{"id": "full-trigger", "commands": ["printf one"]}], evidence, None, ["a.py"])
            payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(outcome, 0)
        self.assertEqual(payload["outcome"], "success")
        self.assertEqual(payload["affected_precheck"]["outcome"], "unavailable")

    def test_passing_precheck_still_runs_every_full_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            real_run = subprocess.run

            def fake(command, **kwargs):
                if "run_test_groups.py" in command:
                    return subprocess.CompletedProcess(command, 0, 'DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": []}\n', "")
                return real_run(command, **kwargs)

            with mock.patch.object(select_checks.subprocess, "run", side_effect=fake):
                outcome = select_checks.execute(Path(directory), [{"id": "full-trigger", "commands": ["printf one", "printf two"]}], evidence, None, ["a.py"])
            payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(outcome, 0)
        self.assertEqual([item["command"] for item in payload["executed_commands"]], ["printf one", "printf two"])
        self.assertEqual(payload["affected_precheck"]["outcome"], "success")
        self.assertIn("not validation coverage", payload["affected_precheck"]["role"])


if __name__ == "__main__":
    unittest.main()
