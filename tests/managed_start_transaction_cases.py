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
spec = importlib.util.spec_from_file_location("managed_start_transaction_cases_impl", SCRIPTS / "start_managed_task.py")
assert spec and spec.loader
managed_start = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = managed_start
spec.loader.exec_module(managed_start)
import managed_task  # noqa: E402


def package() -> managed_task.Package:
    return managed_task.Package(
        source_issue="lehard/development-backlog#43",
        target_repository="lehard/dev-platform",
        change="parallel-start-regression",
        prepared_against="a" * 40,
        artifacts=("proposal.md", "design.md", "tasks.md", "specs/recovery/spec.md"),
        contents={"proposal.md": "why", "design.md": "design", "tasks.md": "tasks", "specs/recovery/spec.md": "spec"},
        revision="b" * 64,
    )


class ManagedStartTransactionTests(unittest.TestCase):
    def test_transaction_precedes_workspace_mutation_and_retires_on_success(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root, worktrees = Path(tmp) / "root", Path(tmp) / "worktrees"
            root.mkdir(); worktrees.mkdir()
            receipt = worktrees / managed_start.START_TRANSACTION_DIR / f"{pkg.change}.json"
            task_root = worktrees / pkg.change
            started = managed_start.StartedTask("multi-agent", f"agent/{pkg.change}", task_root, "board-43")

            def machine_path(key: str, _root: Path) -> Path:
                return worktrees if key == "worktrees" else Path(tmp) / "board.json"

            def fake_start(*_args, **_kwargs):
                self.assertTrue(receipt.is_file())
                self.assertEqual(json.loads(receipt.read_text())["source_issue"], pkg.source_issue)
                task_root.mkdir()
                return started

            with (
                patch.object(managed_start, "discover_task", return_value=pkg),
                patch.object(managed_start, "read_platform_config", return_value={"workflow_profile": "multi-agent", "main_branch": "main"}),
                patch.object(managed_start, "machine_path", side_effect=machine_path),
                patch.object(managed_start, "_branch_exists", return_value=False),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "start_task", side_effect=fake_start),
                patch.object(managed_start, "import_task", return_value=(pkg, "c" * 40, False)),
                patch.object(managed_start, "admit_task", return_value={"decision": "RUN", "claims": []}),
                patch.object(managed_start, "reconcile", return_value=SimpleNamespace(changed=True)),
            ):
                managed_start.start_managed_task(root, pkg.source_issue)
            self.assertFalse(receipt.exists())

    def test_interrupted_start_keeps_retry_receipt(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root, worktrees = Path(tmp) / "root", Path(tmp) / "worktrees"
            root.mkdir(); worktrees.mkdir()
            receipt = worktrees / managed_start.START_TRANSACTION_DIR / f"{pkg.change}.json"
            with (
                patch.object(managed_start, "discover_task", return_value=pkg),
                patch.object(managed_start, "read_platform_config", return_value={"workflow_profile": "multi-agent", "main_branch": "main"}),
                patch.object(managed_start, "machine_path", side_effect=lambda key, _root: worktrees if key == "worktrees" else Path(tmp) / "board.json"),
                patch.object(managed_start, "_branch_exists", return_value=False),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "start_task", side_effect=RuntimeError("interrupted")),
            ):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    managed_start.start_managed_task(root, pkg.source_issue)
            self.assertEqual(json.loads(receipt.read_text())["state"], "creating")

    def test_recovery_preserves_unrelated_dirty_worktree(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            (root / "README").write_text("base\n"); subprocess.run(["git", "add", "README"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            worktrees = Path(tmp) / "worktrees"; worktrees.mkdir()
            target, sibling = worktrees / pkg.change, worktrees / "sibling"
            branch = f"agent/{pkg.change}"
            subprocess.run(["git", "worktree", "add", "-q", "-b", branch, str(target), "main"], cwd=root, check=True)
            subprocess.run(["git", "worktree", "add", "-q", "-b", "agent/sibling", str(sibling), "main"], cwd=root, check=True)
            partial = target / "openspec" / "changes" / pkg.change; partial.mkdir(parents=True)
            (partial / "proposal.md").write_text("partial\n")
            sentinel = sibling / "keep.txt"; sentinel.write_text("sibling work\n")
            transaction = {"worktree": str(target), "branch": branch}
            with (
                patch.object(managed_start, "read_platform_config", return_value={"main_branch": "main"}),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
            ):
                self.assertTrue(managed_start.recover_incomplete_managed_start(root, pkg, transaction))
            self.assertFalse(target.exists())
            self.assertEqual(sentinel.read_text(), "sibling work\n")

    def test_board_lookup_is_fenced_to_exact_task_identity(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root, worktrees = Path(tmp) / "root", Path(tmp) / "worktrees"
            root.mkdir(); worktrees.mkdir()
            target, sibling = worktrees / pkg.change, worktrees / "sibling"; target.mkdir(); sibling.mkdir()
            board = Path(tmp) / "board.json"
            board.write_text(json.dumps({"items": [
                {"id": "stale-44", "task": "Managed task #44", "branch": "agent/sibling", "worktree": str(sibling)},
                {"id": "partial-43", "task": f"Managed task {pkg.source_issue}", "branch": f"agent/{pkg.change}", "worktree": str(target)},
            ]}))
            with patch.object(managed_start, "machine_path", return_value=board):
                item = managed_start._board_item_for_identity(root, target, f"agent/{pkg.change}")
            self.assertIsNotNone(item)
            self.assertEqual(item["id"], "partial-43")

    def test_unregistered_path_is_never_deleted_as_retry_debris(self) -> None:
        pkg = package()
        with tempfile.TemporaryDirectory() as tmp:
            root, target = Path(tmp) / "root", Path(tmp) / "worktrees" / pkg.change
            root.mkdir(); target.mkdir(parents=True)
            sentinel = target / "manual.txt"; sentinel.write_text("keep\n")
            transaction = {"worktree": str(target), "branch": f"agent/{pkg.change}"}
            with (
                patch.object(managed_start, "read_platform_config", return_value={"main_branch": "main"}),
                patch.object(managed_start, "_branch_exists", return_value=True),
                patch.object(managed_start, "_board_item_for_identity", return_value=None),
                patch.object(managed_start, "_registered_worktrees", return_value=set()),
            ):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, "ownership cannot be proven"):
                    managed_start.recover_incomplete_managed_start(root, pkg, transaction)
            self.assertEqual(sentinel.read_text(), "keep\n")
