from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
