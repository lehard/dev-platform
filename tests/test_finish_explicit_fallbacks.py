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

import finish_task  # noqa: E402
import private_lineage  # noqa: E402

CONFIG = {"paths": {"agent_board": ".claude/agents-board.json"}}


class BoardReleaseTests(unittest.TestCase):
    """BR-772: releasing the board claim never treats a broken board as unclaimed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.main = Path(self.tmp.name) / "main"
        self.work = Path(self.tmp.name) / "work"
        (self.main / ".claude").mkdir(parents=True)
        self.work.mkdir()
        self.board = self.main / ".claude" / "agents-board.json"

    def test_corrupt_board_stops_naming_the_board(self) -> None:
        self.board.write_text("{not json")
        with self.assertRaisesRegex(SystemExit, "agents-board.json is unreadable"):
            finish_task.finish_board(self.main, self.work, CONFIG)

    def test_board_without_an_item_list_stops(self) -> None:
        for data in ([], {"items": {}}):
            with self.subTest(data=data):
                self.board.write_text(json.dumps(data))
                with self.assertRaisesRegex(SystemExit, "has no item list"):
                    finish_task.find_board_id(self.main, self.work, CONFIG)

    def test_failed_release_stops_with_the_rerun_command_in_every_path(self) -> None:
        self.board.write_text(json.dumps({"items": [{"id": "abc123", "worktree": str(self.work)}]}))
        with mock.patch.object(finish_task.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(SystemExit, "releasing board claim abc123 failed; rerun scripts/agent_board.py finish --id abc123"):
                finish_task.finish_board(self.main, self.work, CONFIG)

    def test_no_board_or_no_claim_releases_nothing(self) -> None:
        with mock.patch.object(finish_task.subprocess, "run") as run:
            finish_task.finish_board(self.main, self.work, CONFIG)
            self.board.write_text(json.dumps({"items": [{"id": "other", "worktree": str(self.main)}]}))
            finish_task.finish_board(self.main, self.work, CONFIG)
        run.assert_not_called()


class PrivateReferenceGuardTests(unittest.TestCase):
    """BR-772: the guard applies by the private-lineage rule, never by the presence of a file."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_enabled_without_the_guard_is_a_named_blocker(self) -> None:
        with mock.patch.object(private_lineage, "enabled", return_value=True):
            blocker = finish_task.observe_private_reference_blocker(self.root, "title", "body")
        self.assertEqual(blocker, "private lineage is enabled but scripts/check_private_backlog_refs.py is missing")

    def test_disabled_does_not_apply_and_runs_nothing(self) -> None:
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "check_private_backlog_refs.py").write_text("raise SystemExit(1)\n")
        with mock.patch.object(private_lineage, "enabled", return_value=False), \
                mock.patch.object(finish_task.subprocess, "run") as run:
            self.assertIsNone(finish_task.observe_private_reference_blocker(self.root, "title", "body"))
        run.assert_not_called()

    def test_enabled_guard_failure_is_a_blocker(self) -> None:
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "check_private_backlog_refs.py").write_text(
            "import sys\nsys.stderr.write('private reference found')\nraise SystemExit(1)\n")
        with mock.patch.object(private_lineage, "enabled", return_value=True):
            self.assertEqual(finish_task.observe_private_reference_blocker(self.root, "title", "body"),
                             "private reference found")


class SelectChecksImportTests(unittest.TestCase):
    def test_scope_conflict_status_is_imported_without_a_stub(self) -> None:
        source = (SCRIPTS / "select_checks.py").read_text(encoding="utf-8")
        self.assertIn("from managed_project_status import block_for_scope_conflict\n", source)
        self.assertNotIn("def block_for_scope_conflict", source)


if __name__ == "__main__":
    unittest.main()
