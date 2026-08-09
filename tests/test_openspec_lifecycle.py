from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_archive_readiness_accepts_exact_pass_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n- [x] two\n",
                "# Verification\n\nOpenSpec-Verify: PASS\n",
            )
            lifecycle.require_ready(change)

    def test_archive_directory_is_not_scanned_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archived = root / "openspec" / "changes" / "archive" / "2026-08-09-done"
            archived.mkdir(parents=True)
            (archived / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
            self.assertEqual([], lifecycle.completed_active_changes(root))


if __name__ == "__main__":
    unittest.main()
