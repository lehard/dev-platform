from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "template" / "scripts" / "project_terminal_reconciliation.py"


def load_helper(*, merged: bool):
    platform = types.ModuleType("_platform_common")
    platform.github_cli_env = lambda root: {}
    platform.read_platform_config = lambda root: {"main_branch": "main"}
    exact = types.ModuleType("exact_head_safety")
    exact.exact_pr = lambda root, branch, base, env: ({"number": 1}, "a" * 40)
    exact.exact_state = lambda root, pr, head, env: merged
    status = types.ModuleType("managed_project_status")
    class Error(RuntimeError):
        pass
    status.ManagedProjectStatusError = Error
    status.discover_source_issue = lambda root: types.SimpleNamespace(reference="owner/backlog#9", repository="owner/backlog", number=9)
    status.reconcile = Mock(return_value=types.SimpleNamespace(changed=True))
    status.parse_source_issue = lambda value: types.SimpleNamespace(reference=value, repository="owner/backlog", number=9)
    name = "project_terminal_reconciliation_test"
    spec = importlib.util.spec_from_file_location(name, HELPER)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"_platform_common": platform, "exact_head_safety": exact, "managed_project_status": status}):
        assert spec and spec.loader
        spec.loader.exec_module(module)
    return module, status


class ProjectTerminalReconciliationTests(unittest.TestCase):
    def test_confirmed_exact_merge_sets_done_and_closes_bound_source(self) -> None:
        module, status = load_helper(merged=True)
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            self.assertTrue(module.reconcile_if_exact_merged(Path("."), "agent/task", "owner/backlog#9"))
        status.reconcile.assert_called_once_with(Path("."), "Done", source_issue="owner/backlog#9")
        self.assertIn("repos/owner/backlog/issues/9", run.call_args.args[0])

    def test_unmerged_pr_cannot_mutate_terminal_state(self) -> None:
        module, status = load_helper(merged=False)
        self.assertFalse(module.reconcile_if_exact_merged(Path("."), "agent/task", "owner/backlog#9"))
        status.reconcile.assert_not_called()

    def test_issue_mutation_failure_is_resumable_error(self) -> None:
        module, _ = load_helper(merged=True)
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "temporary outage")):
            with self.assertRaisesRegex(Exception, "terminal Issue reconciliation failed"):
                module.reconcile_if_exact_merged(Path("."), "agent/task", "owner/backlog#9")
