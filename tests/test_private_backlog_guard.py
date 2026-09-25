from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("private_backlog_guard", ROOT / "scripts" / "check_private_backlog_refs.py")
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class PrivateBacklogGuardTests(unittest.TestCase):
    def test_explicit_repository_runs_without_local_source_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "sys.argv", ["guard", "--root", directory, "--repository", "lehard/development-backlog"]
        ), mock.patch.object(guard, "violations", return_value=[]) as files, mock.patch.object(
            guard, "publication_text_violation", return_value=False
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(guard.main(), 0)
            self.assertEqual(files.call_args.args[1], "lehard/development-backlog")

    def test_scans_tracked_and_untracked_files_without_reporting_private_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "safe.txt").write_text("https://github.com/acme/development-backlog/issues/42\n", encoding="utf-8")
            subprocess.run(["git", "add", "safe.txt"], cwd=root, check=True)
            self.assertEqual(guard.violations(root, "lehard/development-backlog"), [])

            secret = "https://github.com/lehard/development-backlog/issues/" + "216"
            (root / "untracked.txt").write_text(secret, encoding="utf-8")
            self.assertEqual(len(guard.violations(root, "lehard/development-backlog")), 1)
            self.assertNotIn("216", str(guard.violations(root, "lehard/development-backlog")))

    def test_detects_short_reference_and_issue_number_in_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "note.txt").write_text("lehard/development-backlog" + "#217", encoding="utf-8")
            (root / "development-backlog").mkdir()
            (root / "development-backlog" / "issues").mkdir()
            (root / "development-backlog" / "issues" / "218").write_text("safe text", encoding="utf-8")
            self.assertEqual(len(guard.violations(root, "lehard/development-backlog")), 2)


if __name__ == "__main__":
    unittest.main()
