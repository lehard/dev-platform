"""BR-949: one finalize function reports every unmet archive precondition at once and never launches review."""
from __future__ import annotations

import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_config import platform_config_text, write_platform_config  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")


def make_change(root: Path, *, tasks: str, verification: str | None) -> Path:
    write_platform_config(root, platform_version="customer")
    change = root / "openspec" / "changes" / "work"
    change.mkdir(parents=True)
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    if verification is not None:
        (change / "verification.md").write_text(verification, encoding="utf-8")
    return change


class FinalizePreconditionTests(unittest.TestCase):
    def _archive(self, root: Path, *, review_error: str | None, finalize: bool = False):
        import private_lineage
        config = tomllib.loads(platform_config_text(platform_version="customer"))
        review = mock.Mock(side_effect=SystemExit(review_error) if review_error else None)
        with mock.patch.object(lifecycle, "read_platform_config", return_value=config), \
                mock.patch.object(private_lineage, "require_clean_candidate"), \
                mock.patch.object(lifecycle, "require_committed_package"), \
                mock.patch.object(lifecycle, "require_applicable_committed_diff"), \
                mock.patch.object(lifecycle, "require_review_evidence", review), \
                mock.patch.object(lifecycle, "run_checked") as run_checked, \
                mock.patch.object(lifecycle, "archive_with_recovery") as archive:
            with self.assertRaises(SystemExit) as raised:
                lifecycle.archive_change(root, "work", finalize=finalize)
        return str(raised.exception), review, run_checked, archive

    def test_every_unmet_precondition_is_reported_in_one_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_change(root, tasks="- [x] done\n- [ ] open\n", verification=None)
            message, review, run_checked, archive = self._archive(root, review_error="work: independent review is required but missing")
        self.assertIn("every unmet precondition", message)
        for expected in ("task(s) remain incomplete", "missing successful semantic verification receipt",
                         "independent review is required but missing", "Automated-Checks-Evidence"):
            self.assertIn(expected, message)
        self.assertEqual(message.count("\n- "), len([line for line in message.splitlines() if line.startswith("- ")]))
        review.assert_called_once()
        run_checked.assert_not_called()
        archive.assert_not_called()

    def test_finalize_lists_missing_review_without_launching_one(self) -> None:
        import independent_review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_change(root, tasks="- [x] done\n", verification="OpenSpec-Verify: PASS\nVerification-Method: review\n")
            with mock.patch.object(independent_review, "ensure_review_evidence") as launch:
                message, _, run_checked, archive = self._archive(
                    root, review_error="work: independent review is required but stale", finalize=True)
        launch.assert_not_called()
        self.assertIn("independent review is required but stale", message)
        run_checked.assert_not_called()
        archive.assert_not_called()

    def test_archive_module_has_no_review_launcher(self) -> None:
        self.assertFalse(hasattr(lifecycle, "ensure_review_evidence"))


if __name__ == "__main__":
    unittest.main()
