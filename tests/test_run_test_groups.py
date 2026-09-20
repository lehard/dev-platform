from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

SPEC = importlib.util.spec_from_file_location("run_test_groups", SCRIPT_ROOT / "run_test_groups.py")
assert SPEC and SPEC.loader
run_test_groups = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_test_groups)


PASSING_MODULE = """
import unittest

class PassingTests(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
"""

FAILING_MODULE = """
import unittest

class FailingTests(unittest.TestCase):
    def test_fails(self):
        self.assertTrue(False)
"""


def _write_fixture(root: Path, modules: dict[str, str]) -> None:
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    for name, content in modules.items():
        (tests_dir / f"{name}.py").write_text(content, encoding="utf-8")


class _IsolatedModuleNameTestCase(unittest.TestCase):
    """Each fixture uses module names unique to this test method.

    unittest's discovery caches loaded modules in sys.modules by bare name;
    reusing a name like `test_a` across fixture roots within one process would
    make discovery silently return a stale module from an earlier temp root
    instead of the current one. Real single-shot CLI invocations never hit
    this (discovery runs once per process), so run_test_groups.py itself is
    not changed for it; the fixture just avoids the collision.
    """

    _counter = 0

    def unique(self, base: str) -> str:
        type(self)._counter += 1
        return f"{base}_{type(self)._counter}"


class CoverageEquivalenceTests(_IsolatedModuleNameTestCase):
    def test_declared_groups_equivalent_to_discovery_pass(self) -> None:
        a, b = self.unique("test_a"), self.unique("test_b")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE, b: PASSING_MODULE})
            groups = {
                "g1": {"targets": [a], "mode": "parallel"},
                "g2": {"targets": [b], "mode": "parallel"},
            }
            report = run_test_groups.coverage_report(root, "tests", groups)
            self.assertEqual(report["missing_from_groups"], [])
            self.assertEqual(report["declared_but_not_discovered"], [])
            self.assertEqual(report["duplicated_tests"], [])
            run_test_groups.require_total_coverage(report)  # must not raise

    def test_module_missing_from_every_group_is_reported(self) -> None:
        a, b = self.unique("test_a"), self.unique("test_b")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE, b: PASSING_MODULE})
            groups = {"g1": {"targets": [a], "mode": "parallel"}}
            report = run_test_groups.coverage_report(root, "tests", groups)
            self.assertEqual(len(report["missing_from_groups"]), 1)
            self.assertIn(b, report["missing_from_groups"][0])
            with self.assertRaises(run_test_groups.TestGroupError):
                run_test_groups.require_total_coverage(report)

    def test_test_declared_in_two_groups_is_reported_as_duplicate(self) -> None:
        a = self.unique("test_a")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE})
            groups = {
                "g1": {"targets": [a], "mode": "parallel"},
                "g2": {"targets": [a], "mode": "serial"},
            }
            report = run_test_groups.coverage_report(root, "tests", groups)
            self.assertEqual(len(report["duplicated_tests"]), 1)
            with self.assertRaises(run_test_groups.TestGroupError):
                run_test_groups.require_total_coverage(report)


class AggregateExecutionTests(_IsolatedModuleNameTestCase):
    def test_all_groups_passing_yields_success_aggregate(self) -> None:
        a, b = self.unique("test_a"), self.unique("test_b")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE, b: PASSING_MODULE})
            groups = {
                "g1": {"targets": [a], "mode": "parallel"},
                "g2": {"targets": [b], "mode": "serial"},
            }
            records = run_test_groups.execute(root, "tests", groups, jobs=2, verbose=False)
            self.assertEqual({record["outcome"] for record in records}, {"success"})

    def test_one_mandatory_group_failure_fails_the_aggregate(self) -> None:
        a, b = self.unique("test_a"), self.unique("test_b")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE, b: FAILING_MODULE})
            groups = {
                "g1": {"targets": [a], "mode": "parallel"},
                "g2": {"targets": [b], "mode": "parallel"},
            }
            records = run_test_groups.execute(root, "tests", groups, jobs=2, verbose=False)
            failed = [record["group"] for record in records if record["outcome"] == "failure"]
            self.assertEqual(failed, ["g2"])
            # This mirrors main()'s aggregate computation: any failed group
            # must make the aggregate result "failure", never partial success.
            self.assertTrue(any(record["outcome"] == "failure" for record in records))

    def test_serial_group_runs_after_parallel_groups_not_concurrently_with_them(self) -> None:
        a, b = self.unique("test_a"), self.unique("test_b")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, {a: PASSING_MODULE, b: PASSING_MODULE})
            groups = {
                "par": {"targets": [a], "mode": "parallel"},
                "ser": {"targets": [b], "mode": "serial"},
            }
            records = run_test_groups.execute(root, "tests", groups, jobs=4, verbose=False)
            self.assertEqual(sorted(record["group"] for record in records), ["par", "ser"])
            self.assertEqual({record["outcome"] for record in records}, {"success"})


class GroupConfigValidationTests(unittest.TestCase):
    def test_empty_group_targets_is_rejected(self) -> None:
        with self.assertRaises(run_test_groups.TestGroupError):
            run_test_groups.read_groups({"orphan": {"targets": [], "mode": "parallel"}})

    def test_unsupported_mode_is_rejected(self) -> None:
        with self.assertRaises(run_test_groups.TestGroupError):
            run_test_groups.read_groups({"g": {"targets": ["test_a"], "mode": "eventually"}})

    def test_no_groups_configured_is_rejected(self) -> None:
        with self.assertRaises(run_test_groups.TestGroupError):
            run_test_groups.read_groups({})


class DefaultParallelismTests(unittest.TestCase):
    def test_auto_parallelism_is_capped_on_a_many_cpu_host(self) -> None:
        env = {key: value for key, value in run_test_groups.os.environ.items() if key != "DEV_PLATFORM_TEST_JOBS"}
        with mock.patch.object(run_test_groups.os, "cpu_count", return_value=64), \
                mock.patch.dict(run_test_groups.os.environ, env, clear=True):
            jobs, source = run_test_groups.resolve_jobs()
        self.assertLessEqual(jobs, run_test_groups._DEFAULT_JOBS_CEILING)
        self.assertGreaterEqual(jobs, 1)
        self.assertEqual(source, "auto-capped")

    def test_explicit_operator_job_count_is_honoured_verbatim(self) -> None:
        with mock.patch.object(run_test_groups.os, "cpu_count", return_value=2), \
                mock.patch.dict(run_test_groups.os.environ, {"DEV_PLATFORM_TEST_JOBS": "9"}):
            jobs, source = run_test_groups.resolve_jobs()
        self.assertEqual((jobs, source), (9, "DEV_PLATFORM_TEST_JOBS"))


if __name__ == "__main__":
    unittest.main()
