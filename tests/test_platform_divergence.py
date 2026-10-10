"""Behavior of template/scripts/platform_divergence.py against a fixture project.

Each test builds a throwaway "installed project" by copying the released template
files named in the real manifest, then edits it the way an agent or user would.
The check runs as a subprocess from the project root, exactly as downstream.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
MANIFEST = json.loads((TEMPLATE / "dev-platform" / "platform-manifest.json").read_text(encoding="utf-8"))
PLATFORM_VERSION = "1.9.5"
HOTFIXABLE = "scripts/check_docs_links.py"
PROTECTED = "scripts/finish_task.py"
SURFACE_PATH = "dev-platform/protected-surface.toml"
RECORD_PATH = "dev-platform/local-hotfixes.toml"
FRICTION_LOG = ".claude/agent-friction.jsonl"
FRICTION_ID = "0123456789ab"
REGRESSION_TEST = "tests/test_hotfix_regression.py"
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def toml_string(value: str) -> str:
    return json.dumps(value)


def hotfix_toml(**overrides: object) -> str:
    fields: dict[str, object] = {
        "path": HOTFIXABLE,
        "platform_version": PLATFORM_VERSION,
        "patched_sha256": "0" * 64,
        "defect": "docs link check scans vendored markdown",
        "regression_test": REGRESSION_TEST,
        "friction_event": FRICTION_ID,
        "temporary": True,
    }
    fields.update(overrides)
    lines = ["[[hotfix]]"]
    for name, value in fields.items():
        if value is None:
            continue
        rendered = "true" if value is True else "false" if value is False else toml_string(str(value))
        lines.append(f"{name} = {rendered}")
    return "\n".join(lines) + "\n"


class DivergenceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._base_tmp = tempfile.TemporaryDirectory(prefix="platform-divergence-base-")
        cls.base = Path(cls._base_tmp.name) / "base"
        for relative in [*MANIFEST["files"], "dev-platform/platform-manifest.json", RECORD_PATH]:
            target = cls.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TEMPLATE / relative, target)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._base_tmp.cleanup()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="platform-divergence-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        shutil.copytree(self.base, self.root)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write_config()
        (self.root / REGRESSION_TEST.rsplit("/", 1)[0]).mkdir(exist_ok=True)
        (self.root / REGRESSION_TEST).write_text("# regression test placeholder\n", encoding="utf-8")
        self.write_friction_log([FRICTION_ID])

    def write_config(self, *, version: str = PLATFORM_VERSION, harness: str = "platform") -> None:
        (self.root / ".dev-platform.toml").write_text(
            f'platform_version = "{version}"\nharness_mode = "{harness}"\n\n[paths]\nfriction_log = "{FRICTION_LOG}"\n',
            encoding="utf-8",
        )

    def write_friction_log(self, ids: list[str]) -> None:
        log = self.root / FRICTION_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("".join(json.dumps({"id": event_id, "at": "2026-01-01T00:00:00Z"}) + "\n" for event_id in ids), encoding="utf-8")

    def patch(self, relative: str, marker: str = "# local hotfix\n") -> str:
        path = self.root / relative
        path.write_text(path.read_text(encoding="utf-8") + marker, encoding="utf-8")
        return sha256(path)

    def declare(self, **overrides: object) -> None:
        if "patched_sha256" not in overrides:
            overrides["patched_sha256"] = sha256(self.root / str(overrides.get("path", HOTFIXABLE)))
        record = self.root / RECORD_PATH
        record.write_text(record.read_text(encoding="utf-8") + "\n" + hotfix_toml(**overrides), encoding="utf-8")

    def run_check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "scripts/platform_divergence.py"], cwd=self.root, text=True, capture_output=True, env=ENV)

    def assert_fails(self, kind: str, path: str, *, contains: str = "") -> str:
        completed = self.run_check()
        self.assertNotEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertRegex(completed.stdout, rf"(?m)^\[{re.escape(kind)}\] {re.escape(path)}: .*{re.escape(contains)}")
        self.assertNotIn("platform_divergence: OK", completed.stdout)
        return completed.stdout

    def assert_passes(self) -> str:
        completed = self.run_check()
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("platform_divergence: OK", completed.stdout)
        return completed.stdout


class DivergenceCheckTests(DivergenceTestCase):
    def test_unmodified_install_passes_and_reports_no_hotfix(self) -> None:
        output = self.assert_passes()
        self.assertIn("0 declared hotfix(es)", output)
        self.assertNotIn("\nhotfix: ", output)

    def test_valid_hotfix_passes_and_reports_source_version_and_path(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare()
        output = self.assert_passes()
        self.assertIn(f"hotfix: {HOTFIXABLE} patched from platform {PLATFORM_VERSION}; temporary, not an official release", output)

    def test_undeclared_divergence_of_a_hotfixable_file_fails(self) -> None:
        self.patch(HOTFIXABLE)
        self.assert_fails("undeclared-divergence", HOTFIXABLE, contains="no hotfix entry")

    def test_missing_platform_file_is_a_divergence(self) -> None:
        (self.root / HOTFIXABLE).unlink()
        self.assert_fails("undeclared-divergence", HOTFIXABLE, contains="missing")

    def test_protected_file_edit_fails_as_protected_touch_without_a_record(self) -> None:
        self.patch(PROTECTED)
        self.assert_fails("protected-touch", PROTECTED)

    def test_record_naming_a_protected_path_fails_as_protected_touch_even_with_matching_digest(self) -> None:
        self.patch(PROTECTED)
        self.declare(path=PROTECTED)
        output = self.assert_fails("protected-touch", PROTECTED, contains="names a protected path")
        self.assertEqual(1, output.count(PROTECTED))

    def test_protected_surface_edit_is_a_protected_touch(self) -> None:
        self.patch(SURFACE_PATH, "# reclassify\n")
        self.assert_fails("protected-touch", SURFACE_PATH)

    def test_record_naming_the_manifest_or_detector_is_a_protected_touch(self) -> None:
        for path in ("dev-platform/platform-manifest.json", "scripts/platform_divergence.py", "scripts/platform_doctor.py"):
            with self.subTest(path=path):
                (self.root / RECORD_PATH).write_text(hotfix_toml(path=path), encoding="utf-8")
                self.assert_fails("protected-touch", path, contains="names a protected path")

    def test_unknown_path_in_a_record_fails(self) -> None:
        extra = self.root / "scripts" / "not_in_manifest.py"
        extra.write_text("print('x')\n", encoding="utf-8")
        self.declare(path="scripts/not_in_manifest.py")
        self.assert_fails("unknown-path", "scripts/not_in_manifest.py")

    def test_stale_hotfix_after_a_platform_update_fails_without_editing_the_record(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare()
        before = (self.root / RECORD_PATH).read_bytes()
        self.write_config(version="1.9.6")
        output = self.assert_fails("stale-hotfix", HOTFIXABLE, contains="1.9.5")
        self.assertNotIn("undeclared-divergence", output)
        self.assertEqual(before, (self.root / RECORD_PATH).read_bytes())

    def test_digest_mismatch_fails(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare(patched_sha256="f" * 64)
        self.assert_fails("digest-mismatch", HOTFIXABLE, contains="patched_sha256")

    def test_edit_after_the_record_was_written_fails_as_digest_mismatch(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare()
        self.patch(HOTFIXABLE, "# a later unrecorded edit\n")
        self.assert_fails("digest-mismatch", HOTFIXABLE)

    def test_record_describing_no_divergence_fails(self) -> None:
        self.declare(patched_sha256=MANIFEST["files"][HOTFIXABLE])
        self.assert_fails("digest-mismatch", HOTFIXABLE, contains="no divergence")

    def test_missing_regression_test_fails(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare(regression_test="tests/test_does_not_exist.py")
        self.assert_fails("missing-regression-test", HOTFIXABLE, contains="tests/test_does_not_exist.py")

    def test_missing_friction_event_fails(self) -> None:
        self.write_friction_log(["another-event"])
        self.patch(HOTFIXABLE)
        self.declare()
        self.assert_fails("missing-friction-event", HOTFIXABLE, contains=FRICTION_ID)

    def test_unreadable_or_absent_friction_log_is_reported_never_accepted(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare()
        log = self.root / FRICTION_LOG
        log.write_bytes(b"\xff\xfe not utf-8 \x00\n")
        self.assert_fails("missing-friction-event", HOTFIXABLE, contains="cannot be read")
        log.unlink()
        self.assert_fails("missing-friction-event", HOTFIXABLE, contains="does not exist")
        log.mkdir()
        self.assert_fails("missing-friction-event", HOTFIXABLE, contains="does not exist")

    def test_missing_manifest_fails_explicitly(self) -> None:
        (self.root / "dev-platform" / "platform-manifest.json").unlink()
        self.assert_fails("invalid-record", "dev-platform", contains="platform-manifest.json is missing")

    def test_malformed_inputs_fail_explicitly_without_defaults(self) -> None:
        cases = {
            "dev-platform/platform-manifest.json": ("{not json", "cannot be read as JSON"),
            SURFACE_PATH: ("not = [valid", "cannot be read as TOML"),
            RECORD_PATH: ("hotfix = [", "cannot be read as TOML"),
            ".dev-platform.toml": ("harness_mode = 'platform'\n", "platform_version must be a non-empty string"),
        }
        for relative, (content, message) in cases.items():
            with self.subTest(relative=relative):
                original = (self.root / relative).read_bytes()
                (self.root / relative).write_text(content, encoding="utf-8")
                self.assert_fails("invalid-record", "dev-platform", contains=message)
                (self.root / relative).write_bytes(original)
        self.assert_passes()

    def test_missing_config_or_surface_fails_explicitly(self) -> None:
        (self.root / ".dev-platform.toml").unlink()
        self.assert_fails("invalid-record", "dev-platform", contains=".dev-platform.toml is missing")
        self.write_config()
        (self.root / SURFACE_PATH).unlink()
        self.assert_fails("invalid-record", "dev-platform", contains="protected-surface.toml is missing")

    def test_record_with_missing_unknown_or_wrong_typed_fields_is_invalid(self) -> None:
        self.patch(HOTFIXABLE)
        digest = sha256(self.root / HOTFIXABLE)
        cases = {
            "missing field": (hotfix_toml(patched_sha256=digest, friction_event=None), "missing field(s) ['friction_event']"),
            "unknown field": (hotfix_toml(patched_sha256=digest, owner="me"), "unknown field(s) ['owner']"),
            "not temporary": (hotfix_toml(patched_sha256=digest, temporary=False), "temporary must be true"),
            "bad digest": (hotfix_toml(patched_sha256="XYZ"), "64 lowercase hex"),
            "escaping path": (hotfix_toml(patched_sha256=digest, regression_test="../outside.py"), "normalized project-relative"),
        }
        for name, (text, message) in cases.items():
            with self.subTest(name=name):
                (self.root / RECORD_PATH).write_text(text, encoding="utf-8")
                output = self.assert_fails("invalid-record", HOTFIXABLE, contains=message)
                self.assertNotIn("undeclared-divergence", output)
        (self.root / RECORD_PATH).write_text("unexpected = 1\n", encoding="utf-8")
        self.assert_fails("invalid-record", "dev-platform", contains="unknown top-level key")

    def test_duplicate_entries_for_one_path_are_invalid(self) -> None:
        self.patch(HOTFIXABLE)
        self.declare()
        self.declare()
        self.assert_fails("invalid-record", HOTFIXABLE, contains="more than one")

    def test_project_harness_mode_ignores_files_copier_treats_as_project_owned(self) -> None:
        owned = MANIFEST["project_harness_owned"]
        self.assertIn("scripts/select_checks.py", owned)
        self.patch("scripts/select_checks.py")
        self.assert_fails("undeclared-divergence", "scripts/select_checks.py")
        self.write_config(harness="project")
        self.assert_passes()
        self.patch(HOTFIXABLE)
        self.assert_fails("undeclared-divergence", HOTFIXABLE)

    def test_unknown_harness_mode_is_invalid(self) -> None:
        self.write_config(harness="sideways")
        self.assert_fails("invalid-record", "dev-platform", contains="harness_mode")


class DoctorWiringTests(DivergenceTestCase):
    def load_doctor(self):
        sys.path.insert(0, str(TEMPLATE / "scripts"))
        self.addCleanup(sys.path.remove, str(TEMPLATE / "scripts"))
        spec = importlib.util.spec_from_file_location("platform_doctor_divergence_wiring", TEMPLATE / "scripts" / "platform_doctor.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_doctor_counts_divergence_problems_as_failures(self) -> None:
        doctor = self.load_doctor()
        failures = [0]
        config = tomllib.loads((self.root / ".dev-platform.toml").read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            doctor.check_platform_divergence_contract(self.root, config, failures)
            self.assertEqual([0], failures)
            self.patch(HOTFIXABLE)
            doctor.check_platform_divergence_contract(self.root, config, failures)
        self.assertEqual([1], failures)
        self.assertIn("[fail] [undeclared-divergence]", printed.getvalue())

    def test_doctor_main_invokes_the_check(self) -> None:
        source = (TEMPLATE / "scripts" / "platform_doctor.py").read_text(encoding="utf-8")
        self.assertIn("check_platform_divergence_contract(root, config, failures)", source)


class HotfixEndToEndTests(DivergenceTestCase):
    """A reproducible defect in a hotfixable script is fixed locally and passes with no new release."""

    REGRESSION = '''import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_docs_links


class VendoredMarkdownTests(unittest.TestCase):
    def test_vendored_markdown_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vendor").mkdir()
            (root / "vendor" / "third-party.md").write_text("[broken](missing.md)\\n", encoding="utf-8")
            (root / "README.md").write_text("# Title\\n", encoding="utf-8")
            scanned = [path.name for path in check_docs_links.iter_markdown_files(root)]
        self.assertEqual(["README.md"], scanned)


if __name__ == "__main__":
    unittest.main()
'''

    def run_regression(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, REGRESSION_TEST], cwd=self.root, text=True, capture_output=True, env=ENV)

    def record_friction_event(self) -> str:
        (self.root / FRICTION_LOG).unlink()
        completed = subprocess.run(
            [
                sys.executable, "scripts/agent_friction.py", "record", "--no-route",
                "--category", "observed-drift", "--scope", "platform",
                "--observation", "check_docs_links scans vendored markdown",
                "--evidence", "vendor/third-party.md reported as a broken link",
                "--hypothesis", "EXCLUDED_DIRS lacks vendor",
                "--proposal", "exclude vendor in the released script",
            ],
            cwd=self.root, text=True, capture_output=True, env=ENV,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        match = re.search(r"Recorded friction candidate ([0-9a-f]{12})", completed.stdout)
        self.assertIsNotNone(match, completed.stdout)
        return match.group(1)

    def test_local_fix_with_regression_evidence_passes_without_a_new_release(self) -> None:
        (self.root / REGRESSION_TEST).write_text(self.REGRESSION, encoding="utf-8")
        before = self.run_regression()
        self.assertNotEqual(0, before.returncode, "the regression test must fail without the patch")
        self.assertIn("AssertionError", before.stderr)
        self.assert_passes()

        script = self.root / HOTFIXABLE
        original = script.read_text(encoding="utf-8")
        patched = original.replace('EXCLUDED_DIRS = {".git", "node_modules", ".claude"}', 'EXCLUDED_DIRS = {".git", "node_modules", ".claude", "vendor"}')
        self.assertNotEqual(original, patched)
        script.write_text(patched, encoding="utf-8")
        after = self.run_regression()
        self.assertEqual(0, after.returncode, after.stdout + after.stderr)
        self.assert_fails("undeclared-divergence", HOTFIXABLE)

        event = self.record_friction_event()
        self.declare(friction_event=event, defect="check_docs_links scans vendored markdown")
        output = self.assert_passes()
        self.assertIn(f"hotfix: {HOTFIXABLE} patched from platform {PLATFORM_VERSION}", output)
        self.assertEqual(
            (self.root / "dev-platform" / "platform-manifest.json").read_bytes(),
            (TEMPLATE / "dev-platform" / "platform-manifest.json").read_bytes(),
            "a hotfix must not need a new release manifest",
        )

        (self.root / RECORD_PATH).write_bytes((TEMPLATE / RECORD_PATH).read_bytes())
        self.assert_fails("undeclared-divergence", HOTFIXABLE)


if __name__ == "__main__":
    unittest.main()
