from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))


def load(name: str):
    path = SCRIPT_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


agent_board = load("agent_board")
worktree_cleanup = load("worktree_cleanup")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


class WorktreeHarnessCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / ".gitignore").write_text(".claude/\n", encoding="utf-8")
        (self.root / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "multi-agent"\nharness_mode = "platform"\n\n[paths]\nworktrees = ".claude/worktrees"\nagent_board = ".claude/agents-board.json"\npending_worktrees = ".claude/pending-worktrees.md"\n',
            encoding="utf-8",
        )
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "base")
        self.managed = self.root / ".claude" / "worktrees"
        self.managed.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def add_worktree(self, slug: str) -> Path:
        path = self.managed / slug
        git(self.root, "worktree", "add", "-b", f"agent/{slug}", str(path), "main")
        git(path, "config", "user.name", "Test")
        git(path, "config", "user.email", "test@example.invalid")
        (path / f"{slug}.txt").write_text(f"{slug}\n", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-m", slug)
        return path

    def listed(self, path: Path):
        return next(item for item in worktree_cleanup._list_worktrees(self.root) if item.path == path.resolve())


class WorktreeCleanupTests(WorktreeHarnessCase):
    def test_old_clean_merged_managed_worktree_is_eligible(self) -> None:
        path = self.add_worktree("merged")
        git(self.root, "merge", "--ff-only", "agent/merged")
        worktree = self.listed(path)
        activity = worktree_cleanup._activity_timestamp(self.root, worktree)
        decision = worktree_cleanup.classify(
            self.root,
            worktree,
            managed_root=self.managed,
            main_branch="main",
            active_board=set(),
            active_cwds=set(),
            older_than_days=7,
            now=activity + 8 * 86400,
        )
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.reason, "merged-clean-inactive")

    def test_active_board_and_active_process_are_never_eligible(self) -> None:
        path = self.add_worktree("active")
        git(self.root, "merge", "--ff-only", "agent/active")
        worktree = self.listed(path)
        activity = worktree_cleanup._activity_timestamp(self.root, worktree)
        board_decision = worktree_cleanup.classify(
            self.root,
            worktree,
            managed_root=self.managed,
            main_branch="main",
            active_board={path.resolve()},
            active_cwds=set(),
            older_than_days=7,
            now=activity + 8 * 86400,
        )
        self.assertEqual(board_decision.reason, "active-board")
        process_decision = worktree_cleanup.classify(
            self.root,
            worktree,
            managed_root=self.managed,
            main_branch="main",
            active_board=set(),
            active_cwds={path.resolve() / "nested"},
            older_than_days=7,
            now=activity + 8 * 86400,
        )
        self.assertEqual(process_decision.reason, "active-process")

    def test_dirty_and_unmerged_worktrees_are_reported_not_deleted(self) -> None:
        dirty = self.add_worktree("dirty")
        (dirty / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        dirty_decision = worktree_cleanup.classify(
            self.root,
            self.listed(dirty),
            managed_root=self.managed,
            main_branch="main",
            active_board=set(),
            active_cwds=set(),
            older_than_days=7,
            now=10**10,
        )
        self.assertEqual(dirty_decision.reason, "dirty")

        unmerged = self.add_worktree("unmerged")
        unmerged_decision = worktree_cleanup.classify(
            self.root,
            self.listed(unmerged),
            managed_root=self.managed,
            main_branch="main",
            active_board=set(),
            active_cwds=set(),
            older_than_days=7,
            now=10**10,
        )
        self.assertEqual(unmerged_decision.reason, "not-merged")
        report = worktree_cleanup.write_pending_report(self.root, [dirty_decision, unmerged_decision])
        text = report.read_text(encoding="utf-8")
        self.assertIn("agent/dirty", text)
        self.assertIn("agent/unmerged", text)

    def test_process_check_unavailable_fails_closed(self) -> None:
        path = self.add_worktree("no-process-check")
        git(self.root, "merge", "--ff-only", "agent/no-process-check")
        worktree = self.listed(path)
        activity = worktree_cleanup._activity_timestamp(self.root, worktree)
        decision = worktree_cleanup.classify(
            self.root,
            worktree,
            managed_root=self.managed,
            main_branch="main",
            active_board=set(),
            active_cwds=None,
            older_than_days=7,
            now=activity + 8 * 86400,
        )
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "process-check-unavailable")


class AgentBoardDoctorTests(WorktreeHarnessCase):
    def test_status_detects_merged_branch_and_stale_heartbeat(self) -> None:
        path = self.add_worktree("board")
        git(self.root, "merge", "--ff-only", "agent/board")
        stale = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        item = {"branch": "agent/board", "worktree": str(path), "heartbeat": stale}
        problems = agent_board._status(item, self.root, main_branch="main", stale_hours=72)
        self.assertIn("merged-branch", problems)
        self.assertIn("stale-heartbeat", problems)
        self.assertTrue(agent_board._safe_to_remove(item, problems))

    def test_status_detects_branch_path_mismatch(self) -> None:
        path = self.add_worktree("actual")
        fresh = datetime.now(timezone.utc).isoformat()
        item = {"branch": "agent/not-actual", "worktree": str(path), "heartbeat": fresh}
        problems = agent_board._status(item, self.root, main_branch="main", stale_hours=72)
        self.assertIn("branch-path-mismatch", problems)
        self.assertIn("branch-missing", problems)


class AgentBoardRegistrationTests(WorktreeHarnessCase):
    def register_board(self, *items: dict) -> Path:
        board = self.root / ".claude" / "agents-board.json"
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(json.dumps({"version": 1, "items": list(items)}), encoding="utf-8")
        return board

    def board_item(self, item_id: str, task: str, worktree: Path, *, scope: str = "", heartbeat: str | None = None) -> dict:
        return {
            "id": item_id,
            "task": task,
            "scope": scope,
            "branch": f"agent/{worktree.name}",
            "worktree": str(worktree),
            "heartbeat": heartbeat or datetime.now(timezone.utc).isoformat(),
        }

    def admit(self, board: Path, worktree: Path, scope: str | None = None) -> int:
        args = Namespace(branch=f"agent/{worktree.name}", worktree=str(worktree), scope=scope)
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(agent_board, "board_path", return_value=board):
            return agent_board.cmd_admit(args)

    def test_relative_worktree_is_rejected_before_board_file_or_git_lookup(self) -> None:
        board = self.root / ".claude" / "agents-board.json"
        with mock.patch.object(agent_board, "_registered_worktrees") as registered:
            with self.assertRaisesRegex(SystemExit, "absolute registered worktree path"):
                agent_board.validate_worktree_identity(".claude/worktrees/agent", "agent/example", self.root)
        registered.assert_not_called()
        self.assertFalse(board.exists())

    def test_main_and_branch_mismatch_are_rejected(self) -> None:
        path = self.add_worktree("actual")
        with self.assertRaisesRegex(SystemExit, "integration main"):
            agent_board.validate_worktree_identity(str(self.root), "main", self.root)
        nested = path / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(SystemExit, "exact registered Git worktree root"):
            agent_board.validate_worktree_identity(str(nested), "agent/actual", self.root)
        with self.assertRaisesRegex(SystemExit, "branch/worktree mismatch"):
            agent_board.validate_worktree_identity(str(path), "agent/not-actual", self.root)

    def test_registration_warns_for_declared_overlap_without_blocking(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.root / ".claude" / "agents-board.json"
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {
                            "id": "first-id",
                            "task": "first task",
                            "scope": "template/scripts/agent_board.py",
                            "branch": "agent/first",
                            "worktree": str(first),
                            "heartbeat": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        args = Namespace(
            task="second task",
            scope="template/scripts/agent_board.py",
            branch="agent/second",
            worktree=str(second),
            id="second-id",
        )
        stdout, stderr = StringIO(), StringIO()
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(agent_board, "board_path", return_value=board):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(agent_board.cmd_start(args), 0)
        self.assertEqual(stdout.getvalue().strip(), "second-id")
        self.assertIn("Scope-overlap warning", stderr.getvalue())
        self.assertIn("first-id (first task): template/scripts/agent_board.py", stderr.getvalue())
        items = json.loads(board.read_text(encoding="utf-8"))["items"]
        self.assertEqual(len(items), 2)

    def test_factual_non_overlap_has_no_diagnostic(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        first_file = first / "first.txt"
        first_file.write_text("changed\n", encoding="utf-8")
        git(first, "add", "first.txt")
        git(first, "commit", "-m", "first factual scope")
        second_file = second / "second.txt"
        second_file.write_text("changed\n", encoding="utf-8")
        git(second, "add", "second.txt")
        git(second, "commit", "-m", "second factual scope")
        item = {
            "id": "first-id",
            "task": "first task",
            "scope": "",
            "branch": "agent/first",
            "worktree": str(first),
            "heartbeat": datetime.now(timezone.utc).isoformat(),
        }
        conflicts = agent_board.scope_overlap_diagnostics(
            self.root, second, "agent/second", "", [item]
        )
        self.assertEqual(conflicts, [])

    def test_factual_overlap_is_reported(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree, content in ((first, "first\n"), (second, "second\n")):
            shared = worktree / "shared.txt"
            shared.write_text(content, encoding="utf-8")
            git(worktree, "add", "shared.txt")
            git(worktree, "commit", "-m", f"{worktree.name} factual scope")
        item = {
            "id": "first-id",
            "task": "first task",
            "scope": "",
            "branch": "agent/first",
            "worktree": str(first),
            "heartbeat": datetime.now(timezone.utc).isoformat(),
        }
        conflicts = agent_board.scope_overlap_diagnostics(
            self.root, second, "agent/second", "", [item]
        )
        self.assertEqual(conflicts, [("first-id", "first task", "shared.txt")])

    def test_admission_blocks_exact_concrete_claim_and_preserves_soft_overlap(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="template/scripts/shared.py"),
            self.board_item("second-id", "second task", second, scope="template/scripts"),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second, "template/scripts/shared.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["first-id"]["admission"]["decision"], "RUN")
        self.assertEqual(items["second-id"]["admission"]["decision"], "WAIT")
        self.assertEqual(items["second-id"]["admission"]["conflicts"], [["first-id", "first task", "template/scripts/shared.py"]])

        # A shared directory is advisory only: a distinct concrete file still
        # receives RUN and may execute in parallel.
        self.assertEqual(self.admit(board, second, "template/scripts/other.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")

    def test_admission_uses_factual_file_scope_and_ignores_stale_owners(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        shared = first / "shared.py"
        shared.write_text("shared\n", encoding="utf-8")
        git(first, "add", "shared.py")
        git(first, "commit", "-m", "factual shared scope")
        stale = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="template/scripts", heartbeat=stale),
            self.board_item("second-id", "second task", second),
        )
        # An invalid/stale owner has no live claim, even when its old declared
        # scope is broad and its factual diff contains the requested file.
        self.assertEqual(self.admit(board, second, "shared.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")

        # In a fresh admission state the active factual file wins over a broad
        # declaration and blocks the same explicit file claim.
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="template/scripts"),
            self.board_item("second-id", "second task", second),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second, "shared.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["first-id"]["admission"]["decision"], "RUN")
        self.assertEqual(items["second-id"]["admission"]["decision"], "WAIT")

    def test_concurrent_exact_claims_cannot_both_run(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first),
            self.board_item("second-id", "second task", second),
        )

        def claim(worktree: Path) -> str:
            # Exercise the same locked read-and-claim primitive from two
            # callers.  The CLI delegates to this primitive after identity
            # validation, so this isolates the actual race boundary.
            with agent_board.locked_json(board) as data:
                current = next(item for item in data["items"] if item["worktree"] == str(worktree))
                current["scope"] = "shared.py"
                return agent_board._admit_item(self.root, current, data["items"], main_branch="main")["decision"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(claim, (first, second))), ["RUN", "WAIT"])
        decisions = [item["admission"]["decision"] for item in json.loads(board.read_text(encoding="utf-8"))["items"]]
        self.assertEqual(sorted(decisions), ["RUN", "WAIT"])


if __name__ == "__main__":
    unittest.main()
