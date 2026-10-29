from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402

signal = load_platform_module("agent_signal", ROOT / "template" / "scripts" / "agent_signal.py")
overview = load_platform_module("lifecycle_overview", ROOT / "template" / "scripts" / "lifecycle_overview.py")

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
RAISED = "2026-10-29T11:50:00+00:00"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class SignalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.root = base / "proj"
        self.root.mkdir()
        git("init", "-q", "-b", "main", cwd=self.root)
        git("-c", "user.email=a@b", "-c", "user.name=n", "commit", "-q", "--allow-empty", "-m", "i", cwd=self.root)
        self.worktree = base / "wt"
        git("worktree", "add", "-q", "-b", "agent/t1", str(self.worktree), cwd=self.root)
        self.other = base / "other"
        git("worktree", "add", "-q", "-b", "agent/t2", str(self.other), cwd=self.root)
        self.board = base / "board.json"
        self.write_board([{"id": "aaa", "task": "task one", "branch": "agent/t1", "worktree": str(self.worktree)},
                          {"id": "bbb", "task": "task two", "branch": "agent/t2", "worktree": str(self.other)}])
        for patcher in (mock.patch.object(signal, "board_path", return_value=self.board),
                        mock.patch.object(signal, "scope_gate_required", return_value=True),
                        mock.patch.object(signal, "read_platform_config", return_value={}),
                        mock.patch.dict(signal.locked_json.__globals__, {"ensure_shared_path": lambda *a, **k: None})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_board(self, items):
        self.board.write_text(json.dumps({"version": 1, "items": items}), encoding="utf-8")

    def items(self):
        return json.loads(self.board.read_text(encoding="utf-8"))["items"]

    def raise_(self, question="Which option?", worktree=None, now=RAISED):
        return signal.raise_signal(question, root=self.root, worktree=worktree or self.worktree, now=now)

    def test_raise_stores_question_project_and_task_on_the_entry(self):
        result = self.raise_()
        stored = self.items()[0]["signals"]
        self.assertEqual(len(stored), 1)
        self.assertEqual((stored[0]["question"], stored[0]["project"], stored[0]["task"]), ("Which option?", "proj", "task one"))
        self.assertFalse(result["repeat"])
        self.assertNotIn("signals", self.items()[1])

    def test_same_question_collapses_even_with_other_whitespace(self):
        first = self.raise_()
        again = self.raise_("  Which   option? ", now="2026-10-29T11:55:00+00:00")
        self.assertTrue(again["repeat"])
        self.assertEqual(again["id"], first["id"])
        stored = self.items()[0]["signals"]
        self.assertEqual((len(stored), stored[0]["count"], stored[0]["last_raised_at"]), (1, 2, "2026-10-29T11:55:00+00:00"))

    def test_same_question_on_another_task_is_a_separate_signal(self):
        self.assertNotEqual(self.raise_()["id"], self.raise_(worktree=self.other)["id"])

    def test_resolve_clears_and_the_same_text_opens_a_new_signal(self):
        first = self.raise_()
        resolved = signal.resolve_signal(first["id"], "owner", root=self.root, now="2026-10-29T11:58:00+00:00")
        self.assertEqual((resolved["resolved_by"], resolved["resolved_at"]), ("owner", "2026-10-29T11:58:00+00:00"))
        self.assertEqual(signal.open_signals(self.root, now=NOW)["signals"], [])
        self.raise_()
        self.assertEqual(len(signal.open_signals(self.root, now=NOW)["signals"]), 1)
        self.assertEqual(len(self.items()[0]["signals"]), 2)

    def test_resolve_unknown_or_resolved_signal_fails(self):
        with self.assertRaisesRegex(signal.SignalError, "no open signal nope"):
            signal.resolve_signal("nope", "owner", root=self.root)
        first = self.raise_()
        signal.resolve_signal(first["id"], "owner", root=self.root)
        with self.assertRaisesRegex(signal.SignalError, "no open signal"):
            signal.resolve_signal(first["id"], "owner", root=self.root)

    def test_task_without_board_entry_is_rejected_and_nothing_is_stored(self):
        self.write_board([self.items()[1]])
        with self.assertRaisesRegex(signal.SignalError, "no active agent-board entry"):
            self.raise_()
        self.assertEqual(self.items(), [{"id": "bbb", "task": "task two", "branch": "agent/t2", "worktree": str(self.other)}])

    def test_empty_question_and_missing_capability_or_board_fail_explicitly(self):
        with self.assertRaisesRegex(signal.SignalError, "question is empty"):
            self.raise_("   ")
        with mock.patch.object(signal, "scope_gate_required", return_value=False):
            with self.assertRaisesRegex(signal.SignalError, "agent_board = true"):
                self.raise_()
        self.board.unlink()
        with self.assertRaisesRegex(signal.SignalError, "does not exist"):
            self.raise_()

    def test_open_signals_report_age_and_explicit_board_problems(self):
        self.raise_()
        listed = signal.open_signals(self.root, now=NOW)
        self.assertEqual([(s["task"], s["age_minutes"]) for s in listed["signals"]], [("task one", 10)])
        with mock.patch.object(signal, "scope_gate_required", return_value=False):
            self.assertEqual(signal.open_signals(self.root, now=NOW), {"configured": False, "signals": []})
        self.board.write_text("{", encoding="utf-8")
        self.assertIn("agent board unreadable", signal.open_signals(self.root, now=NOW)["error"])

    def test_overview_renders_open_signals_and_board_problems(self):
        self.raise_()
        text = "\n".join(overview._owner_needed_lines(signal.open_signals(self.root, now=NOW)))
        self.assertIn("Owner needed:", text)
        self.assertIn("[proj] task one: Which option?", text)
        self.assertIn("10 min ago", text)
        self.assertIn("cannot be shown", "\n".join(overview._owner_needed_lines({"configured": True, "error": "x", "signals": []})))
        self.assertIn("not shown", "\n".join(overview._owner_needed_lines({"configured": False, "signals": []})))

    def test_unclassified_capabilities_is_an_explicit_error_not_an_exit(self):
        from agent_board import scope_gate_required
        with mock.patch.object(signal, "scope_gate_required", scope_gate_required):
            with self.assertRaisesRegex(signal.SignalError, "not classified"):
                self.raise_()
            with self.assertRaisesRegex(signal.SignalError, "not classified"):
                signal.resolve_signal("x", "owner", root=self.root)
            listed = signal.open_signals(self.root, now=NOW)
            self.assertIn("cannot be shown", listed["error"])
            with mock.patch.object(signal, "main_root", return_value=self.root), \
                    mock.patch.object(signal, "current_worktree_root", return_value=self.worktree):
                self.assertEqual(signal.main(["raise", "--question", "Q?"]), 1)

    def test_malformed_entry_or_signal_is_an_error_in_the_cli_and_in_the_overview(self):
        cases = {
            "signals not a list": {"signals": "oops"},
            "signal not a dict": {"signals": ["oops"]},
            "signal without id": {"signals": [{"question": "Q"}]},
            "signal without raised_at": {"signals": [{"id": "x1", "question": "Q"}]},
        }
        for name, extra in cases.items():
            with self.subTest(name):
                items = self.items()
                items[0].update(extra)
                self.write_board(items)
                listed = signal.open_signals(self.root, now=NOW)
                self.assertTrue(listed["error"] and not listed["signals"], listed)
                if name != "signal without raised_at":
                    with self.assertRaises(signal.SignalError):
                        self.raise_()
                    with self.assertRaises(signal.SignalError):
                        signal.resolve_signal("x1", "owner", root=self.root)
        items = self.items()
        items[0] = {"id": "aaa", "task": "task one", "branch": "agent/t1", "worktree": str(self.worktree)}
        items.append("not an entry")
        self.write_board(items)
        self.assertIn("malformed entry", signal.open_signals(self.root, now=NOW)["error"])
        with self.assertRaisesRegex(signal.SignalError, "malformed entry"):
            signal.resolve_signal("x1", "owner", root=self.root)

    def test_open_signal_without_count_cannot_be_raised_again(self):
        self.raise_()
        items = self.items()
        del items[0]["signals"][0]["count"]
        self.write_board(items)
        with self.assertRaisesRegex(signal.SignalError, "has no count"):
            self.raise_()
        self.assertNotIn("count", self.items()[0]["signals"][0])

    def test_cli_failure_exits_nonzero_with_the_cause(self):
        with mock.patch.object(signal, "main_root", return_value=self.root), \
                mock.patch.object(signal, "current_worktree_root", return_value=self.worktree):
            self.assertEqual(signal.main(["raise", "--question", "Q?"]), 0)
            self.assertEqual(signal.main(["resolve", "--id", "missing", "--by", "owner"]), 1)


if __name__ == "__main__":
    unittest.main()
