from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
assert spec and spec.loader
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class OpenSpecLifecycleTests(unittest.TestCase):
    def make_change(self, root: Path, name: str, tasks: str, verification: str | None = None) -> Path:
        change = root / "openspec" / "changes" / name
        change.mkdir(parents=True)
        (change / "tasks.md").write_text(tasks, encoding="utf-8")
        if verification is not None:
            (change / "verification.md").write_text(verification, encoding="utf-8")
        return change

    def test_incomplete_change_is_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "work", "- [x] done\n- [ ] pending\n")
            self.assertEqual([], lifecycle.completed_active_changes(root))
            self.assertEqual(0, lifecycle.check_hygiene(root))

    def test_completed_active_change_blocks_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] one\n- [x] two\n")
            self.assertEqual(["done"], lifecycle.completed_active_changes(root))
            self.assertEqual(1, lifecycle.check_hygiene(root))

    def test_archive_readiness_requires_verify_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(Path(tmp), "done", "- [x] one\n")
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_pass_without_method_is_not_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(Path(tmp), "done", "- [x] one\n", "OpenSpec-Verify: PASS\n")
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_embedded_pass_text_is_not_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "Do not write OpenSpec-Verify: PASS unless verification succeeds.\nVerification-Method: equivalent-review\n",
            )
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_archive_readiness_accepts_pass_and_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n- [x] two\n",
                "# Verification\n\nOpenSpec-Verify: PASS\nVerification-Method: opsx-verify\n",
            )
            lifecycle.require_ready(change)

    def test_platform_archive_readiness_requires_generated_automated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n",
            )
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change, platform_owned=True)

    def test_platform_archive_readiness_accepts_executed_automated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            (change / "automated-checks.json").write_text(
                '{"selection":{"state":"ready","command_count":1},"outcome":"success","executed_commands":[{"command":"pytest","outcome":"success"}]}\n',
                encoding="utf-8",
            )
            lifecycle.require_ready(change, platform_owned=True)

    def test_static_platform_readiness_rejects_missing_evidence_marker_before_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp), "done", "- [x] one\n", "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            )
            with self.assertRaisesRegex(SystemExit, "Automated-Checks-Evidence"):
                lifecycle.require_static_archive_readiness(change, platform_owned=True)

    def test_uncommitted_only_state_is_not_an_applicable_archive_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            lifecycle, "run_git", return_value=mock.Mock(returncode=0)
        ):
            with self.assertRaisesRegex(SystemExit, "committed diff"):
                lifecycle.require_applicable_committed_diff(Path(tmp))

    def test_archive_rejects_static_receipt_before_running_checks_or_rewriting_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(
                root, "done", "- [x] one\n", "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            )
            stale = change / "automated-checks.json"
            stale.write_text('{"outcome":"stale"}\n', encoding="utf-8")
            with (
                mock.patch.object(lifecycle, "read_platform_config", return_value={}),
                mock.patch.object(lifecycle, "harness_mode", return_value="platform"),
                mock.patch.object(lifecycle, "run_checked") as run_checked,
            ):
                with self.assertRaisesRegex(SystemExit, "Automated-Checks-Evidence"):
                    lifecycle.archive_change(root, "done")
            run_checked.assert_not_called()
            self.assertEqual(stale.read_text(encoding="utf-8"), '{"outcome":"stale"}\n')

    def test_archive_rejects_no_committed_diff_before_running_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(
                root,
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            with (
                mock.patch.object(lifecycle, "read_platform_config", return_value={}),
                mock.patch.object(lifecycle, "harness_mode", return_value="platform"),
                mock.patch.object(lifecycle, "run_git", return_value=mock.Mock(returncode=0)),
                mock.patch.object(lifecycle, "run_checked") as run_checked,
            ):
                with self.assertRaisesRegex(SystemExit, "committed diff"):
                    lifecycle.archive_change(root, "done")
            run_checked.assert_not_called()

    def test_archive_directory_is_not_scanned_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archived = root / "openspec" / "changes" / "archive" / "2026-08-09-done"
            archived.mkdir(parents=True)
            (archived / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
            self.assertEqual([], lifecycle.completed_active_changes(root))


if __name__ == "__main__":
    unittest.main()
