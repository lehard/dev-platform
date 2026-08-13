from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("managed_start_transaction_under_test", SCRIPTS / "start_managed_task.py")
assert spec and spec.loader
managed_start = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = managed_start
spec.loader.exec_module(managed_start)

import managed_task  # noqa: E402


def package(change: str = "parallel-start-regression") -> managed_task.Package:
    return managed_task.Package(
        source_issue="lehard/development-backlog#43",
        target_repository="lehard/dev-platform",
        change=change,
        prepared_against="a" * 40,
        artifacts=("proposal.md", "design.md", "tasks.md", "specs/recovery/spec.md"),
        contents={
            "proposal.md": "## Why\n",
            "design.md": "## Design\n",
            "tasks.md": "## Tasks\n",
            "specs/recovery/spec.md": "## ADDED Requirements\n",
        },
        revision="b" * 64,
    )


class ManagedStartTransactionTests(unittest.TestCase):
    def test_transaction_exists_before_workspace_start_and_is_removed_after_success(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "integration"
            worktrees = Path(tmp) / "worktrees"
            root.mkdir()
            worktrees.mkdir()
            transaction = worktrees / managed_start.START_TRANSACTION_DIR / f"{pkg.change}.json"
            task_root = worktrees / pkg.change
            started = managed_start.StartedTask(
                profile="multi-agent",
                branch=f"agent/{pkg.change}",
                task_root=task_root,
                board_id="board-43",
            )

            def machine_path(key: str, _root: Path) -> Path:
                if key == "worktrees":
                    return worktrees
                if key == "agent_board":
                    return Path(tmp) / "agents-board.json"
                raise KeyError(key)

            def fake_start(*_args, **_kwargs):
                self.assertTrue(transaction.is_file(), "transaction must exist before start_task mutates worktree/board state")
                payload = json.loads(transaction.read_text(encoding="utf-8"))
                self.assertEqual(payload["source_issue"], pkg.source_issue)
                self.assertEqual(payload["package_revision"], pkg.revision)
                task_root.mkdir()
                return started

            with (
                patch.object(managed_start, "discover_task", return_value=pkg),
                patch.object(
                    managed_start,
                    "read_platform_config",
                    return_value={"workflow_profile": "multi-agent", "main_branch": "main"},
                ),
                patch.object(managed_start, "machine_path", side_effect=machine_path),
                patch.object(managed_start, "_branch_exists", return_value=False),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "start_task", side_effect=fake_start),
                patch.object(managed_start, "import_task", return_value=(pkg, "c" * 40, False)),
                patch.object(managed_start, "admit_task", return_value={"decision": "RUN", "claims": []}),
                patch.object(managed_start, "reconcile", return_value=SimpleNamespace(changed=True)),
            ):
                result, current_main, reused = managed_start.start_managed_task(root, pkg.source_issue)

            self.assertEqual(result, started)
            self.assertEqual(current_main, "c" * 40)
            self.assertFalse(reused)
            self.assertFalse(transaction.exists(), "successful start must retire the creation transaction")

    def test_failed_start_keeps_transaction_for_retry(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "integration"
            worktrees = Path(tmp) / "worktrees"
            root.mkdir()
            worktrees.mkdir()
            transaction = worktrees / managed_start.START_TRANSACTION_DIR / f"{pkg.change}.json"

            def machine_path(key: str, _root: Path) -> Path:
                if key == "worktrees":
                    return worktrees
                if key == "agent_board":
                    return Path(tmp) / "agents-board.json"
                raise KeyError(key)

            with (
                patch.object(managed_start, "discover_task", return_value=pkg),
                patch.object(
                    managed_start,
                    "read_platform_config",
                    return_value={"workflow_profile": "multi-agent", "main_branch": "main"},
                ),
                patch.object(managed_start, "machine_path", side_effect=machine_path),
                patch.object(managed_start, "_branch_exists", return_value=False),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "start_task", side_effect=RuntimeError("crash after transaction")),
            ):
                with self.assertRaisesRegex(RuntimeError, "crash after transaction"):
                    managed_start.start_managed_task(root, pkg.source_issue)

            self.assertTrue(transaction.is_file())
            payload = json.loads(transaction.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "creating")
            self.assertEqual(payload["source_issue"], pkg.source_issue)

    def test_recovery_removes_only_exact_partial_worktree_and_preserves_dirty_sibling(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)

            worktrees = Path(tmp) / "worktrees"
            worktrees.mkdir()
            target = worktrees / pkg.change
            sibling = worktrees / "unrelated-task"
            target_branch = f"agent/{pkg.change}"
            sibling_branch = "agent/unrelated-task"
            subprocess.run(["git", "worktree", "add", "-q", "-b", target_branch, str(target), "main"], cwd=root, check=True)
            subprocess.run(["git", "worktree", "add", "-q", "-b", sibling_branch, str(sibling), "main"], cwd=root, check=True)

            partial = target / "openspec" / "changes" / pkg.change
            partial.mkdir(parents=True)
            (partial / "proposal.md").write_text("partial\n", encoding="utf-8")
            sibling_sentinel = sibling / "do-not-touch.txt"
            sibling_sentinel.write_text("important sibling work\n", encoding="utf-8")

            transaction = {
                "version": 1,
                "state": "creating",
                "attempt_id": "attempt-43",
                "source_issue": pkg.source_issue,
                "target_repository": pkg.target_repository,
                "change": pkg.change,
                "package_revision": pkg.revision,
                "branch": target_branch,
                "worktree": str(target),
            }

            with (
                patch.object(managed_start, "read_platform_config", return_value={"main_branch": "main"}),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
            ):
                recovered = managed_start.recover_incomplete_managed_start(root, pkg, transaction)

            self.assertTrue(recovered)
            self.assertFalse(target.exists())
            self.assertNotEqual(
                subprocess.run(
                    ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
                    cwd=root,
                    check=False,
                ).returncode,
                0,
            )
            self.assertTrue(sibling.exists())
            self.assertEqual(sibling_sentinel.read_text(encoding="utf-8"), "important sibling work\n")
            self.assertEqual(
                subprocess.run(
                    ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{sibling_branch}"],
                    cwd=root,
                    check=False,
                ).returncode,
                0,
            )

    def test_recovery_targets_exact_board_identity_and_ignores_stale_sibling_entry(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "integration"
            worktrees = Path(tmp) / "worktrees"
            root.mkdir()
            worktrees.mkdir()
            target = worktrees / pkg.change
            sibling = worktrees / "sibling"
            target.mkdir()
            sibling.mkdir()
            board = Path(tmp) / "agents-board.json"
            board.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "items": [
                            {
                                "id": "stale-44",
                                "task": "Managed task lehard/development-backlog#44",
                                "branch": "agent/sibling",
                                "worktree": str(sibling),
                            },
                            {
                                "id": "partial-43",
                                "task": f"Managed task {pkg.source_issue}",
                                "branch": f"agent/{pkg.change}",
                                "worktree": str(target),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            def machine_path(key: str, _root: Path) -> Path:
                if key == "agent_board":
                    return board
                if key == "worktrees":
                    return worktrees
                raise KeyError(key)

            with patch.object(managed_start, "machine_path", side_effect=machine_path):
                item = managed_start._board_item_for_identity(root, target, f"agent/{pkg.change}")
                sibling_item = managed_start._board_item_for_identity(root, sibling, "agent/sibling")

            assert item is not None and sibling_item is not None
            self.assertEqual(item["id"], "partial-43")
            self.assertEqual(sibling_item["id"], "stale-44")

    def test_unregistered_noncanonical_path_is_left_untouched(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "integration"
            target = Path(tmp) / "worktrees" / pkg.change
            root.mkdir()
            target.mkdir(parents=True)
            sentinel = target / "manual.txt"
            sentinel.write_text("keep me\n", encoding="utf-8")
            transaction = {
                "version": 1,
                "state": "creating",
                "attempt_id": "attempt-43",
                "source_issue": pkg.source_issue,
                "target_repository": pkg.target_repository,
                "change": pkg.change,
                "package_revision": pkg.revision,
                "branch": f"agent/{pkg.change}",
                "worktree": str(target),
            }

            with (
                patch.object(managed_start, "read_platform_config", return_value={"main_branch": "main"}),
                patch.object(managed_start, "_branch_exists", return_value=True),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "_registered_worktrees", return_value=set()),
            ):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, "ownership cannot be proven"):
                    managed_start.recover_incomplete_managed_start(root, pkg, transaction)

            self.assertTrue(target.exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me\n")


if __name__ == "__main__":
    unittest.main()
