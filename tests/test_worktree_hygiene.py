from __future__ import annotations

import importlib.util
import json
import os
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
publication_state = agent_board.publication_state
worktree_cleanup = load("worktree_cleanup")
finish_task = load("finish_task")


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
        # finish_task cleanup intentionally changes its own process cwd to the
        # surviving integration checkout.  Restore a durable location before
        # removing this temporary repository so later cases never inherit a
        # deleted cwd.
        os.chdir(ROOT)
        self.tmp.cleanup()

    def add_worktree(self, slug: str, *, content: str | None = None) -> Path:
        path = self.managed / slug
        git(self.root, "worktree", "add", "-b", f"agent/{slug}", str(path), "main")
        git(path, "config", "user.name", "Test")
        git(path, "config", "user.email", "test@example.invalid")
        (path / f"{slug}.txt").write_text(f"{content or slug}\n", encoding="utf-8")
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


class DeferredCompletedWorktreeCleanupTests(WorktreeHarnessCase):
    def _merged_task(self, slug: str, *, content: str | None = None) -> Path:
        worktree = self.add_worktree(slug, content=content)
        git(self.root, "merge", "--ff-only", f"agent/{slug}")
        return worktree

    def test_caller_worktree_cleanup_is_deferred_then_recovered_idempotently(self) -> None:
        worktree = self._merged_task("caller-cwd")
        with mock.patch.dict(finish_task.os.environ, {"PWD": str(worktree)}, clear=False), redirect_stdout(StringIO()) as output:
            finish_task.cleanup_completed_task(worktree, self.root, "agent/caller-cwd", squash_merged=True)
        self.assertIn("deferred cleanup", output.getvalue())
        self.assertIn("--worktree", output.getvalue())
        self.assertIn(str(worktree.resolve()), output.getvalue())
        self.assertIn("--branch agent/caller-cwd", output.getvalue())
        self.assertIn(git(self.root, "rev-parse", "agent/caller-cwd").stdout.strip(), output.getvalue())
        self.assertTrue(worktree.exists())
        record = worktree_cleanup.deferred_cleanup_path(self.root, worktree_cleanup.read_platform_config(self.root))
        self.assertTrue(record.exists())
        target = worktree_cleanup.DeferredCleanupTarget.from_entry(
            worktree_cleanup._read_deferred_cleanup(self.root, worktree_cleanup.read_platform_config(self.root))[0]
        )

        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value={worktree}):
            blocked = worktree_cleanup.cleanup(self.root, older_than_days=7, target=target)
        self.assertTrue(worktree.exists())
        self.assertIn({"path": str(worktree.resolve()), "error": "active-process"}, blocked["errors"])

        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            recovered = worktree_cleanup.cleanup(self.root, older_than_days=7, target=target)
            repeated = worktree_cleanup.cleanup(self.root, older_than_days=7, target=target)
        self.assertIn(str(worktree.resolve()), recovered["removed"])
        self.assertFalse(worktree.exists())
        self.assertFalse(record.exists())
        self.assertEqual(repeated["removed"], [])
        self.assertEqual(repeated["status"], "already-cleaned")

    def test_targeted_cleanup_cannot_remove_another_deferred_worktree(self) -> None:
        first = self._merged_task("first-deferred")
        second = self._merged_task("second-deferred")
        config = worktree_cleanup.read_platform_config(self.root)
        worktree_cleanup.defer_completed_task(self.root, first, "agent/first-deferred")
        worktree_cleanup.defer_completed_task(self.root, second, "agent/second-deferred")
        first_target = worktree_cleanup.DeferredCleanupTarget.from_entry(
            next(entry for entry in worktree_cleanup._read_deferred_cleanup(self.root, config) if entry["path"] == str(first.resolve()))
        )

        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            result = worktree_cleanup.cleanup(self.root, older_than_days=7, target=first_target)

        self.assertEqual(result["removed"], [str(first.resolve())])
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertEqual(
            worktree_cleanup._read_deferred_cleanup(self.root, config),
            [
                {
                    "path": str(second.resolve()),
                    "branch": "agent/second-deferred",
                    "head": git(self.root, "rev-parse", "agent/second-deferred").stdout.strip(),
                }
            ],
        )

        replacement = self._merged_task("first-deferred", content="replacement")
        worktree_cleanup.defer_completed_task(self.root, replacement, "agent/first-deferred")
        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            repeated = worktree_cleanup.cleanup(self.root, older_than_days=7, target=first_target)
        self.assertEqual(repeated["status"], "already-cleaned")
        self.assertTrue(replacement.exists())

    def test_global_cleanup_requires_explicit_preview_then_apply(self) -> None:
        first = self._merged_task("global-first")
        second = self._merged_task("global-second")
        worktree_cleanup.defer_completed_task(self.root, first, "agent/global-first")
        worktree_cleanup.defer_completed_task(self.root, second, "agent/global-second")

        with self.assertRaisesRegex(SystemExit, "exact deferred target or --all"):
            worktree_cleanup.cleanup(self.root, older_than_days=7)
        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            preview = worktree_cleanup.cleanup(self.root, older_than_days=7, all=True)
        self.assertEqual(preview["status"], "preview")
        self.assertEqual(preview["candidate_count"], 2)
        self.assertEqual({item["path"] for item in preview["deferred"]["candidates"]}, {str(first.resolve()), str(second.resolve())})
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            applied = worktree_cleanup.cleanup(self.root, older_than_days=7, all=True, apply=True)
        self.assertEqual(set(applied["removed"]), {str(first.resolve()), str(second.resolve())})
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())

    def test_mismatched_target_record_fails_closed_without_removal(self) -> None:
        worktree = self._merged_task("identity-mismatch")
        config = worktree_cleanup.read_platform_config(self.root)
        worktree_cleanup.defer_completed_task(self.root, worktree, "agent/identity-mismatch")
        mismatched = worktree_cleanup._read_deferred_cleanup(self.root, config)
        mismatched[0]["head"] = "0" * 40
        worktree_cleanup._write_deferred_cleanup(self.root, config, mismatched)
        target = worktree_cleanup.DeferredCleanupTarget.from_entry(mismatched[0])

        with mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()):
            result = worktree_cleanup.cleanup(self.root, older_than_days=7, target=target)

        self.assertEqual(result["removed"], [])
        self.assertIn({"path": str(worktree.resolve()), "error": "identity-mismatch"}, result["errors"])
        self.assertTrue(worktree.exists())

        # A stale deferred record must remain protected from the generic
        # old-worktree pass even when global cleanup was explicitly requested.
        # This makes the failure closed rather than silently reclassifying it.
        with (
            mock.patch.object(worktree_cleanup, "_active_cwds", return_value=set()),
            mock.patch.object(worktree_cleanup, "_activity_timestamp", return_value=0),
        ):
            global_result = worktree_cleanup.cleanup(self.root, older_than_days=7, all=True, apply=True)
        self.assertIn({"path": str(worktree.resolve()), "error": "identity-mismatch"}, global_result["errors"])
        self.assertNotIn(str(worktree.resolve()), global_result["removed"])
        self.assertTrue(worktree.exists())
        self.assertEqual(worktree_cleanup._read_deferred_cleanup(self.root, config), mismatched)

    def test_ambiguous_deferred_records_fail_closed(self) -> None:
        worktree = self._merged_task("ambiguous-record")
        config = worktree_cleanup.read_platform_config(self.root)
        worktree_cleanup.defer_completed_task(self.root, worktree, "agent/ambiguous-record")
        record_path = worktree_cleanup.deferred_cleanup_path(self.root, config)
        entry = worktree_cleanup._read_deferred_cleanup(self.root, config)[0]
        record_path.write_text(json.dumps({"version": 1, "entries": [entry, entry]}), encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "ambiguous duplicate"):
            worktree_cleanup.cleanup(self.root, older_than_days=7, all=True, apply=True)
        self.assertTrue(worktree.exists())

    def test_cleanup_stays_synchronous_when_the_caller_uses_integration(self) -> None:
        worktree = self._merged_task("safe-caller")
        with mock.patch.dict(finish_task.os.environ, {"PWD": str(self.root)}, clear=False), redirect_stdout(StringIO()) as output:
            finish_task.cleanup_completed_task(worktree, self.root, "agent/safe-caller", squash_merged=True)
        self.assertIn("Removed completed worktree", output.getvalue())
        self.assertFalse(worktree.exists())


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
        self.assertEqual(
            agent_board.claim_eligibility(item, self.root, main_branch="main", stale_hours=72)[0],
            "degraded",
        )


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

    def acknowledge(self, board: Path, worktree: Path, *, with_id: str, paths: list[str], reason: str) -> int:
        args = Namespace(branch=f"agent/{worktree.name}", worktree=str(worktree), with_id=with_id, path=paths, reason=reason)
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(agent_board, "board_path", return_value=board):
            return agent_board.cmd_acknowledge(args)

    def hard_conflicts(self, board: Path, worktree: Path):
        with mock.patch.object(agent_board, "board_path", return_value=board):
            return agent_board.hard_scope_conflicts(self.root, worktree, f"agent/{worktree.name}")

    def enforce_gate(self, board: Path, worktree: Path) -> None:
        with mock.patch.object(agent_board, "board_path", return_value=board):
            agent_board.enforce_scope_gate(self.root, worktree, f"agent/{worktree.name}")

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

    def test_degraded_branch_path_sibling_is_diagnostic_only_and_untouched(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        degraded = self.board_item("first-id", "first task", first, scope="shared.py")
        degraded["branch"] = "agent/not-first"
        original = dict(degraded)
        board = self.register_board(degraded, self.board_item("second-id", "second task", second))

        self.assertEqual(self.admit(board, second, "shared.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")
        self.assertEqual(items["first-id"], original)

        output = StringIO()
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(
            agent_board, "board_path", return_value=board
        ), redirect_stdout(output):
            self.assertEqual(agent_board.cmd_doctor(Namespace(fix=True, stale_hours=72, format="json")), 1)
        diagnostic = json.loads(output.getvalue())
        self.assertEqual(diagnostic["entries"], [{"id": "first-id", "eligibility": "degraded", "problems": ["branch-path-mismatch", "branch-missing"]}])

    def test_terminal_dirty_sibling_is_diagnostic_only_and_untouched(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        git(self.root, "merge", "--ff-only", "agent/first")
        (first / "keep-sibling-state.txt").write_text("do not alter\n", encoding="utf-8")
        terminal = self.board_item("first-id", "first task", first, scope="shared.py")
        original = dict(terminal)
        board = self.register_board(terminal, self.board_item("second-id", "second task", second))

        self.assertEqual(self.admit(board, second, "shared.py"), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")
        self.assertEqual(items["first-id"], original)
        self.assertEqual((first / "keep-sibling-state.txt").read_text(encoding="utf-8"), "do not alter\n")
        self.assertEqual(
            agent_board.claim_eligibility(items["first-id"], self.root, main_branch="main", stale_hours=72)[0],
            "terminal",
        )

    def test_unreadable_board_fails_admission_closed(self) -> None:
        first = self.add_worktree("first")
        board = self.root / ".claude" / "agents-board.json"
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text("{not json", encoding="utf-8")
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(
            agent_board, "board_path", return_value=board
        ), self.assertRaisesRegex(RuntimeError, "Invalid JSON"):
            self.admit(board, first, "shared.py")

    def test_lock_failure_fails_admission_closed(self) -> None:
        first = self.add_worktree("first")
        board = self.register_board(self.board_item("first-id", "first task", first))
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(
            agent_board, "board_path", return_value=board
        ), mock.patch.object(agent_board, "locked_json", side_effect=OSError("board lock unavailable")), self.assertRaisesRegex(
            OSError, "board lock unavailable"
        ):
            self.admit(board, first, "shared.py")

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


class AgentBoardAcknowledgmentTests(WorktreeHarnessCase):
    """Regression coverage for dev-platform#203, #220 and #224."""

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

    def acknowledge(self, board: Path, worktree: Path, *, with_id: str, paths: list[str], reason: str) -> int:
        args = Namespace(branch=f"agent/{worktree.name}", worktree=str(worktree), with_id=with_id, path=paths, reason=reason)
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(agent_board, "board_path", return_value=board):
            return agent_board.cmd_acknowledge(args)

    def hard_conflicts(self, board: Path, worktree: Path):
        with mock.patch.object(agent_board, "board_path", return_value=board):
            return agent_board.hard_scope_conflicts(self.root, worktree, f"agent/{worktree.name}")

    def enforce_gate(self, board: Path, worktree: Path) -> None:
        with mock.patch.object(agent_board, "board_path", return_value=board):
            agent_board.enforce_scope_gate(self.root, worktree, f"agent/{worktree.name}")

    def test_acknowledged_overlap_allows_run_without_narrowing_declared_scope(self) -> None:
        """dev-platform#203: a verified-safe same-file overlap must not force a narrower --scope."""
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="shared.py"),
            self.board_item("second-id", "second task", second, scope="shared.py"),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "WAIT")

        self.assertEqual(
            self.acknowledge(board, second, with_id="first-id", paths=["shared.py"], reason="verified independent edits"),
            0,
        )
        self.assertEqual(self.admit(board, second), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")
        # The truthful declared/factual scope is preserved -- the path is still claimed.
        self.assertIn("shared.py", items["second-id"]["claims"])

    def test_acknowledge_rejects_paths_that_are_not_currently_conflicting(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="shared.py"),
            self.board_item("second-id", "second task", second, scope=""),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second), 0)  # No overlap -> RUN.
        with self.assertRaisesRegex(SystemExit, "not a currently conflicting path"):
            self.acknowledge(board, second, with_id="first-id", paths=["shared.py"], reason="premature")

    def test_acknowledge_requires_bounded_reason_and_at_least_one_path(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="shared.py"),
            self.board_item("second-id", "second task", second, scope="shared.py"),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second), 0)
        with self.assertRaisesRegex(SystemExit, "non-empty bounded justification"):
            self.acknowledge(board, second, with_id="first-id", paths=["shared.py"], reason="   ")
        with self.assertRaisesRegex(SystemExit, "at least one --path"):
            self.acknowledge(board, second, with_id="first-id", paths=[], reason="fine")

    def test_acknowledge_rejects_unknown_or_inactive_conflicting_task(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        stale = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="shared.py", heartbeat=stale),
            self.board_item("second-id", "second task", second, scope="shared.py"),
        )
        with self.assertRaisesRegex(SystemExit, "unknown conflicting board id"):
            self.acknowledge(board, second, with_id="ghost-id", paths=["shared.py"], reason="fine")
        with self.assertRaisesRegex(SystemExit, "not a currently active task"):
            self.acknowledge(board, second, with_id="first-id", paths=["shared.py"], reason="fine")

    def test_acknowledgment_does_not_cover_a_later_unacknowledged_path(self) -> None:
        """Spec scenario: an acknowledgment for file x does not authorize new file y."""
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree in (first, second):
            shared = worktree / "shared.py"
            shared.write_text(f"{worktree.name}\n", encoding="utf-8")
            git(worktree, "add", "shared.py")
            git(worktree, "commit", "-m", f"{worktree.name} touches shared.py")
        (first / "other.py").write_text("first other\n", encoding="utf-8")
        git(first, "add", "other.py")
        git(first, "commit", "-m", "first also touches other.py")

        board = self.register_board(
            self.board_item("first-id", "first task", first),
            self.board_item("second-id", "second task", second),
        )
        self.assertEqual(self.admit(board, first), 0)
        self.assertEqual(self.admit(board, second), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "WAIT")

        self.assertEqual(
            self.acknowledge(board, second, with_id="first-id", paths=["shared.py"], reason="verified shared.py is safe"),
            0,
        )
        self.assertEqual(self.admit(board, second), 0)
        items = {item["id"]: item for item in json.loads(board.read_text(encoding="utf-8"))["items"]}
        self.assertEqual(items["second-id"]["admission"]["decision"], "RUN")

        # Scope evolves after admission: second's factual diff now also touches
        # other.py, which the earlier shared.py acknowledgment never covered.
        (second / "other.py").write_text("second other\n", encoding="utf-8")
        git(second, "add", "other.py")
        git(second, "commit", "-m", "second scope evolved onto other.py")

        conflicts = self.hard_conflicts(board, second)
        self.assertEqual(conflicts, [("first-id", "first task", "other.py")])
        with self.assertRaises(agent_board.HardScopeOverlap):
            self.enforce_gate(board, second)

    def test_hard_scope_gate_ignores_completed_sibling_claim(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree in (first, second):
            shared = worktree / "shared.py"
            shared.write_text(f"{worktree.name}\n", encoding="utf-8")
            git(worktree, "add", "shared.py")
            git(worktree, "commit", "-m", f"{worktree.name} touches shared.py")
        stale = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        board = self.register_board(
            self.board_item("first-id", "first task", first, heartbeat=stale),
            self.board_item("second-id", "second task", second),
        )
        self.assertEqual(self.hard_conflicts(board, second), [])
        self.enforce_gate(board, second)  # Does not raise.

    def test_hard_scope_gate_reconciles_exact_squash_merged_sibling_claim(self) -> None:
        """An exact merged PR releases scope even when its branch is not in main."""
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree in (first, second):
            shared = worktree / "shared.py"
            shared.write_text(f"{worktree.name}\n", encoding="utf-8")
            git(worktree, "add", "shared.py")
            git(worktree, "commit", "-m", f"{worktree.name} touches shared.py")
        self.assertNotEqual(
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", "agent/first", "main"],
                cwd=self.root,
                text=True,
                capture_output=True,
                check=False,
            ).returncode,
            0,
            "fixture must model squash merge's missing branch ancestry",
        )
        board = self.register_board(
            self.board_item("first-id", "first task", first),
            self.board_item("second-id", "second task", second),
        )
        merged = publication_state.ExactHeadPrLookup(
            available=True,
            exact_merged={"number": 9, "state": "MERGED"},
        )
        with mock.patch.object(agent_board, "github_cli_env", return_value={}), mock.patch.object(
            agent_board.publication_state, "find_exact_local_branch_pr", return_value=merged
        ) as lookup:
            self.assertEqual(self.hard_conflicts(board, second), [])
            self.enforce_gate(board, second)
        lookup.assert_called_with(self.root, {}, "agent/first", "main")
        self.assertEqual(lookup.call_count, 2)

    def test_hard_scope_gate_keeps_active_or_unavailable_sibling_claims_fail_closed(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree in (first, second):
            shared = worktree / "shared.py"
            shared.write_text(f"{worktree.name}\n", encoding="utf-8")
            git(worktree, "add", "shared.py")
            git(worktree, "commit", "-m", f"{worktree.name} touches shared.py")
        board = self.register_board(
            self.board_item("first-id", "first task", first),
            self.board_item("second-id", "second task", second),
        )
        for lookup_result in (
            publication_state.ExactHeadPrLookup(available=True, exact_open={"number": 9, "state": "OPEN"}),
            publication_state.ExactHeadPrLookup(available=True, stale_open={"number": 10, "state": "OPEN"}),
            publication_state.ExactHeadPrLookup(available=False, detail="GitHub unavailable"),
        ):
            with self.subTest(lookup=lookup_result), mock.patch.object(agent_board, "github_cli_env", return_value={}), mock.patch.object(
                agent_board.publication_state, "find_exact_local_branch_pr", return_value=lookup_result
            ):
                self.assertEqual(self.hard_conflicts(board, second), [("first-id", "first task", "shared.py")])
                with self.assertRaises(agent_board.HardScopeOverlap):
                    self.enforce_gate(board, second)

    def test_squash_merge_scope_reconciliation_leaves_dirty_sibling_worktree_untouched(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        for worktree in (first, second):
            shared = worktree / "shared.py"
            shared.write_text(f"{worktree.name}\n", encoding="utf-8")
            git(worktree, "add", "shared.py")
            git(worktree, "commit", "-m", f"{worktree.name} touches shared.py")
        dirty = first / "keep-me.txt"
        dirty.write_text("local sibling state\n", encoding="utf-8")
        board = self.register_board(
            self.board_item("first-id", "first task", first),
            self.board_item("second-id", "second task", second),
        )
        merged = publication_state.ExactHeadPrLookup(available=True, exact_merged={"number": 9})
        with mock.patch.object(agent_board, "github_cli_env", return_value={}), mock.patch.object(
            agent_board.publication_state, "find_exact_local_branch_pr", return_value=merged
        ):
            self.enforce_gate(board, second)
        self.assertEqual(dirty.read_text(encoding="utf-8"), "local sibling state\n")
        self.assertTrue((first / ".git").exists())
        self.assertIn("?? keep-me.txt", git(first, "status", "--short").stdout)
        self.assertEqual(len(json.loads(board.read_text(encoding="utf-8"))["items"]), 2)

    def test_doctor_releases_clean_exact_merged_claim_idempotently(self) -> None:
        first = self.add_worktree("first")
        board = self.register_board(self.board_item("first-id", "first task", first, scope="shared.py"))
        merged = publication_state.ExactHeadPrLookup(available=True, exact_merged={"number": 9})
        args = Namespace(fix=True, stale_hours=agent_board.DEFAULT_STALE_HOURS)
        with mock.patch.object(agent_board, "main_root", return_value=self.root), mock.patch.object(
            agent_board, "board_path", return_value=board
        ), mock.patch.object(agent_board, "github_cli_env", return_value={}), mock.patch.object(
            agent_board.publication_state, "find_exact_local_branch_pr", return_value=merged
        ):
            self.assertEqual(agent_board.cmd_doctor(args), 0)
            self.assertEqual(agent_board.cmd_doctor(args), 0)
        self.assertTrue(first.exists())
        self.assertEqual(json.loads(board.read_text(encoding="utf-8"))["items"], [])

    def test_hard_scope_gate_is_clean_when_no_active_overlap_exists(self) -> None:
        first = self.add_worktree("first")
        second = self.add_worktree("second")
        board = self.register_board(
            self.board_item("first-id", "first task", first, scope="only_first.py"),
            self.board_item("second-id", "second task", second, scope="only_second.py"),
        )
        self.assertEqual(self.hard_conflicts(board, second), [])
        self.enforce_gate(board, second)  # Does not raise.


if __name__ == "__main__":
    unittest.main()
