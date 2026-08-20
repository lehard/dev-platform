from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


managed_task = load("managed_task")
execute_managed_task = load("execute_managed_task")


class ManagedExecutionIntakeTests(unittest.TestCase):
    def args(self) -> SimpleNamespace:
        return SimpleNamespace(
            bundle="/bundle", priority=None, confirm_distinct=False, strong_trigger=None,
            task_family="general", routing_confidence="medium", assurance="standard",
            effort_hint=None, process_evidence=None, scope="docs/engineering", acknowledge_source_issue_revision=None,
        )

    def test_fresh_execution_composes_authoring_then_exact_managed_start(self) -> None:
        package = SimpleNamespace(source_issue="owner/backlog#42")
        started = SimpleNamespace(task_root=Path("/task"), branch="agent/change")
        with patch.object(execute_managed_task, "create_task", return_value=(package, False, False)) as create, patch.object(
            execute_managed_task, "start_managed_task", return_value=(started, "a" * 40, False)
        ) as start:
            result = execute_managed_task.execute_managed_task(Path("/root"), self.args())
        self.assertEqual(result[0], "owner/backlog#42")
        self.assertFalse(result[1])
        self.assertEqual(create.call_args.args[:4], (Path("/root"), "/bundle", None, False))
        self.assertEqual(start.call_args.args[:3], (Path("/root"), "owner/backlog#42", "docs/engineering"))

    def test_exact_existing_issue_is_reused_instead_of_creating_a_duplicate(self) -> None:
        started = SimpleNamespace(task_root=Path("/task"), branch="agent/change")
        duplicate = managed_task.ManagedTaskError("clear duplicate already exists: owner/backlog#42; no issue was created")
        with patch.object(execute_managed_task, "create_task", side_effect=duplicate), patch.object(
            execute_managed_task, "start_managed_task", return_value=(started, "a" * 40, True)
        ) as start:
            result = execute_managed_task.execute_managed_task(Path("/root"), self.args())
        self.assertEqual(result[:3], ("owner/backlog#42", True, True))
        self.assertEqual(start.call_args.args[1], "owner/backlog#42")

    def test_orphan_active_openspec_blocks_terminal_lifecycle_but_quick_work_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            managed_task.require_no_orphan_active_openspec(root)
            orphan = root / "openspec" / "changes" / "orphan"
            orphan.mkdir(parents=True)
            with self.assertRaisesRegex(managed_task.ManagedTaskError, "lacks managed-task provenance"):
                managed_task.require_no_orphan_active_openspec(root)
            (orphan / ".managed-task.json").write_text("{}", encoding="utf-8")
            managed_task.require_no_orphan_active_openspec(root)


if __name__ == "__main__":
    unittest.main()
