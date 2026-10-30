"""The shared lifecycle preflight: conditions call the gate functions, report every result, refuse together."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from test_worktree_hygiene import ROOT, WorktreeHarnessCase, agent_board, finish_task, git

sys.path.insert(0, str(ROOT / "template" / "scripts"))

import lifecycle_preflight as preflight  # noqa: E402
import select_checks  # noqa: E402
import shared_workspace  # noqa: E402
import task_reconciliation  # noqa: E402
from _platform_common import RECONCILE_COMMAND  # noqa: E402


def context(root: Path, branch: str = "agent/only", **overrides) -> preflight.PreflightContext:
    values = dict(root=root, integration=root, branch=branch, entry="test")
    values.update(overrides)
    return preflight.PreflightContext(**values)


class BoardClaimAndScopeTests(WorktreeHarnessCase):
    def setUp(self) -> None:
        super().setUp()
        self.worktree = self.add_worktree("only")
        self.board = self.root / ".claude" / "agents-board.json"
        self.board.parent.mkdir(parents=True, exist_ok=True)

    def write_board(self, items: list[dict]) -> None:
        self.board.write_text(json.dumps({"version": 1, "items": items}), encoding="utf-8")

    def claim(self) -> dict:
        from datetime import datetime, timezone

        return {"id": "only-id", "task": "t", "scope": "", "branch": "agent/only", "worktree": str(self.worktree),
                "heartbeat": datetime.now(timezone.utc).isoformat()}

    def check(self, **overrides) -> preflight.ConditionResult:
        return preflight.check_board_claim_and_scope(context(self.worktree, integration=self.root, **overrides))

    def test_a_missing_claim_is_refused_with_the_gate_message_and_the_restoring_command(self) -> None:
        self.write_board([])
        with self.assertRaises(SystemExit) as gate:
            agent_board.enforce_scope_gate(self.root, self.worktree, "agent/only")
        with self.assertRaises(preflight.PreflightRefusal) as refused:
            self.check()
        self.assertIn(str(gate.exception.code), str(refused.exception))  # same answer as the gate
        self.assertIn("has no claim for worktree", str(refused.exception))
        self.assertIn('agent_board.py start --task "<task>" --branch agent/only', str(refused.exception))

    def test_a_claimed_task_passes(self) -> None:
        self.write_board([self.claim()])
        self.assertEqual(preflight.PASSED, self.check().state)

    def test_a_corrupt_board_is_a_refusal_not_a_pass(self) -> None:
        self.board.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(preflight.PreflightRefusal, "unreadable or invalid JSON"):
            self.check()

    def test_a_declared_waiver_is_reported_as_not_applicable_with_its_reason(self) -> None:
        result = self.check(scope_gate_waiver="declared by test")
        self.assertEqual((preflight.NOT_APPLICABLE, "declared by test"), (result.state, result.detail))

    def test_a_project_without_the_board_capability_is_not_applicable(self) -> None:
        from _platform_config import write_platform_config

        write_platform_config(self.worktree, capabilities={"agent_board": False})
        self.assertEqual(preflight.NOT_APPLICABLE, self.check().state)


class SharedWorkspaceConditionTests(unittest.TestCase):
    def test_own_paths_are_repaired_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worktree-metadata"
            path.mkdir()
            group = shared_workspace.SharedGroup(os.getgid(), "g", "test")
            findings = [shared_workspace.Finding(path, "mode=0755, missing group rwx+setgid", True)]
            with mock.patch.object(shared_workspace, "shared_workspace_applicable", return_value=True), \
                    mock.patch.object(shared_workspace, "audit", return_value=(group, findings)), \
                    mock.patch.object(shared_workspace, "preflight") as repair:
                result = preflight.check_shared_workspace(context(Path(tmp), integration=Path(tmp)))
            repair.assert_called_once()
            self.assertEqual(preflight.REPAIRED, result.state)
            self.assertIn(str(path), result.detail)

    def test_foreign_paths_are_refused_with_the_owner_and_the_command_and_not_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worktree-metadata"
            path.mkdir()
            group = shared_workspace.SharedGroup(os.getgid(), "g", "test")
            findings = [shared_workspace.Finding(path, "mode=0755, missing group rwx+setgid", True)]
            with mock.patch.object(shared_workspace, "shared_workspace_applicable", return_value=True), \
                    mock.patch.object(shared_workspace, "audit", return_value=(group, findings)), \
                    mock.patch.object(shared_workspace, "preflight") as repair, \
                    mock.patch.object(os, "geteuid", return_value=os.geteuid() + 1):
                with self.assertRaises(preflight.PreflightRefusal) as refused:
                    preflight.check_shared_workspace(context(Path(tmp), integration=Path(tmp)))
            repair.assert_not_called()
            self.assertIn("owner", str(refused.exception))
            self.assertIn(f"chgrp g {path}", str(refused.exception))
            self.assertIn("shared-workspace-admission", str(refused.exception))

    def test_no_findings_passes_and_a_checkout_without_a_contract_is_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            group = shared_workspace.SharedGroup(os.getgid(), "g", "test")
            with mock.patch.object(shared_workspace, "shared_workspace_applicable", return_value=True), \
                    mock.patch.object(shared_workspace, "audit", return_value=(group, [])), \
                    mock.patch.object(shared_workspace, "preflight"):
                self.assertEqual(preflight.PASSED, preflight.check_shared_workspace(context(Path(tmp), integration=Path(tmp))).state)
            with mock.patch.object(shared_workspace, "shared_workspace_applicable", return_value=False):
                self.assertEqual(preflight.NOT_APPLICABLE, preflight.check_shared_workspace(context(Path(tmp))).state)

    def test_an_audit_that_cannot_run_is_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(shared_workspace, "shared_workspace_applicable", return_value=True), \
                mock.patch.object(shared_workspace, "audit", return_value=(None, [shared_workspace.Finding(Path(tmp), "POSIX group-mode enforcement unavailable", False)])):
            with self.assertRaisesRegex(preflight.PreflightRefusal, "unavailable"):
                preflight.check_shared_workspace(context(Path(tmp), integration=Path(tmp)))


class TaskBaseTests(unittest.TestCase):
    def check(self, freshness: task_reconciliation.Freshness, **overrides) -> preflight.ConditionResult:
        with mock.patch.object(task_reconciliation, "observe_candidate", return_value=freshness):
            return preflight.check_task_base(context(Path("."), **overrides))

    def test_behind_mergeable_passes_like_the_gate(self) -> None:
        self.assertEqual(preflight.PASSED, self.check(task_reconciliation.Freshness("behind-mergeable", "abc", merge_base="def")).state)

    def test_a_conflict_with_main_is_refused_with_the_files_and_the_reconcile_command(self) -> None:
        freshness = task_reconciliation.Freshness("diverged", "abc", detail="a trial merge conflicts in a.py, b.py")
        with self.assertRaises(preflight.PreflightRefusal) as refused:
            self.check(freshness)
        self.assertIn("a.py, b.py", str(refused.exception))
        self.assertIn(RECONCILE_COMMAND, str(refused.exception))

    def test_a_waiver_is_reported_not_silently_skipped(self) -> None:
        result = self.check(task_reconciliation.Freshness("diverged", "abc"), task_base_waiver="declared")
        self.assertEqual((preflight.NOT_APPLICABLE, "declared"), (result.state, result.detail))


class ProjectCheapGatesTests(unittest.TestCase):
    def check(self, commands) -> preflight.ConditionResult:
        settings = {} if commands is None else {"preflight_commands": commands}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(preflight, "load_checks_config", return_value={"settings": settings}), mock.patch.object(Path, "exists", return_value=True), mock.patch("_platform_common.read_platform_config", return_value={"paths": {"checks": "dev-platform/checks.toml"}}):
            return preflight.check_project_cheap_gates(context(Path(tmp)))

    def test_not_configured_is_reported_not_applicable(self) -> None:
        result = self.check(None)
        self.assertEqual(preflight.NOT_APPLICABLE, result.state)
        self.assertIn("preflight_commands", result.detail)

    def test_a_project_without_a_checks_file_reports_why_nothing_is_configured(self) -> None:
        from _platform_config import write_platform_config

        with tempfile.TemporaryDirectory() as tmp:
            write_platform_config(Path(tmp))
            result = preflight.check_project_cheap_gates(context(Path(tmp)))
        self.assertEqual(preflight.NOT_APPLICABLE, result.state)
        self.assertIn("is not present", result.detail)

    def test_passing_commands_pass(self) -> None:
        self.assertEqual(preflight.PASSED, self.check(["true"]).state)

    def test_a_failing_command_is_refused_with_its_name_and_output(self) -> None:
        with self.assertRaises(preflight.PreflightRefusal) as refused:
            self.check(["echo unregistered-site >&2; exit 3"])
        self.assertIn("exit 3", str(refused.exception))
        self.assertIn("unregistered-site", str(refused.exception))

    def test_a_malformed_setting_is_refused(self) -> None:
        with self.assertRaisesRegex(preflight.PreflightRefusal, "list of non-empty command strings"):
            self.check("true")


class RunPreflightTests(unittest.TestCase):
    def test_every_condition_is_printed_and_all_refusals_are_reported_together(self) -> None:
        def fine(_):
            return preflight.ConditionResult(preflight.PASSED, "ok")

        def refuse(name):
            def check(_):
                raise preflight.PreflightRefusal(f"{name} violated; run fix-{name}")
            return check

        conditions = (
            preflight.Condition("one", (), fine),
            preflight.Condition("two", (), refuse("two")),
            preflight.Condition("three", (), refuse("three")),
        )
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            preflight.run_preflight(context(Path(".")), conditions=conditions)
        printed = out.getvalue()
        self.assertIn("DEV_PLATFORM_PREFLIGHT: one: passed", printed)
        self.assertIn("DEV_PLATFORM_PREFLIGHT: two: refused", printed)
        message = str(raised.exception.code)
        self.assertIn("[two] two violated; run fix-two", message)
        self.assertIn("[three] three violated; run fix-three", message)
        self.assertIn("2 condition(s)", message)

    def test_a_clean_run_returns_each_result(self) -> None:
        conditions = (preflight.Condition("one", (), lambda _: preflight.ConditionResult(preflight.PASSED, "ok")),)
        with redirect_stdout(io.StringIO()):
            self.assertEqual([("one", preflight.ConditionResult(preflight.PASSED, "ok"))],
                             preflight.run_preflight(context(Path(".")), conditions=conditions))


    def test_an_unexpected_failure_of_a_condition_is_a_refusal_and_the_others_still_run(self) -> None:
        def fine(_):
            return preflight.ConditionResult(preflight.PASSED, "ok")

        def broken(_):
            raise ValueError("checks.toml is not valid TOML")

        def exits(_):
            raise SystemExit("Check configuration not found")

        conditions = (
            preflight.Condition("broken", (), broken),
            preflight.Condition("exits", (), exits),
            preflight.Condition("after", (), fine),
        )
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            preflight.run_preflight(context(Path(".")), conditions=conditions)
        printed = out.getvalue()
        self.assertIn("DEV_PLATFORM_PREFLIGHT: broken: refused: cannot be evaluated: checks.toml is not valid TOML", printed)
        self.assertIn("DEV_PLATFORM_PREFLIGHT: exits: refused: cannot be evaluated: Check configuration not found", printed)
        self.assertIn("DEV_PLATFORM_PREFLIGHT: after: passed", printed)
        message = str(raised.exception.code)
        self.assertIn("[broken] cannot be evaluated", message)
        self.assertIn("[exits] cannot be evaluated", message)
        self.assertIn("2 condition(s)", message)

    def test_a_malformed_checks_file_refuses_the_cheap_gate_condition_through_the_registry(self) -> None:
        from _platform_config import write_platform_config

        with tempfile.TemporaryDirectory() as tmp:
            write_platform_config(Path(tmp))
            (Path(tmp) / "dev-platform").mkdir()
            (Path(tmp) / "dev-platform" / "checks.toml").write_text("not = [valid", encoding="utf-8")
            conditions = tuple(c for c in preflight.CONDITIONS if c.id == "project-cheap-gates")
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
                preflight.run_preflight(context(Path(tmp)), conditions=conditions)
        self.assertIn("[project-cheap-gates] cannot be evaluated", str(raised.exception.code))


class FinishWiringTests(unittest.TestCase):
    def run_main(self, provider: str, mode_patches: dict) -> list[str]:
        order: list[str] = []
        config = {"main_branch": "main", "scm_provider": provider, "pr_merge_mode": "manual"}

        def refuse(*_a, **_k):
            order.append("preflight")
            raise SystemExit("preflight refused")

        with mock.patch.multiple(
            finish_task,
            current_worktree_root=mock.Mock(return_value=Path("/work")),
            main_root=mock.Mock(return_value=Path("/work")),
            read_platform_config=mock.Mock(return_value=config),
            lifecycle_mode=mock.Mock(return_value="portable"),
            scm_provider=mock.Mock(return_value=provider),
            harness_mode=mock.Mock(return_value="platform"),
            profile=mock.Mock(return_value="multi-agent"),
            preflight_with_report=mock.Mock(return_value=[]),
            publish_mode=mock.Mock(return_value="pr"),
            current_branch=mock.Mock(return_value="task/x"),
            require_managed_checkout_identity=mock.Mock(return_value=None),
            validate_publication_config=mock.Mock(),
            require_no_orphan_active_openspec=mock.Mock(),
            require_delivery_provenance=mock.Mock(return_value=None),
            observe_source_issue_drift=mock.Mock(return_value=None),
            run_finish_preflight=refuse,
            run_checks=mock.Mock(side_effect=lambda *a, **k: order.append("checks")),
            **mode_patches,
        ), mock.patch.object(sys, "argv", ["finish_task.py"]):
            with self.assertRaisesRegex(SystemExit, "preflight refused"):
                finish_task.main()
        return order

    def test_the_gitlab_path_runs_the_preflight_before_any_check(self) -> None:
        order = self.run_main("gitlab", {})
        self.assertEqual(["preflight"], order)

    def test_the_github_path_runs_the_preflight_before_any_check(self) -> None:
        order = self.run_main("github", {
            "task_pr_is_already_merged": mock.Mock(return_value=False),
            "find_existing_exact_open_pr": mock.Mock(return_value=None),
            "fetch_main": mock.Mock(),
            "emit_finish_stage": mock.Mock(),
        })
        self.assertEqual(["preflight"], order)


class SelectorWiringTests(unittest.TestCase):
    def args(self, **overrides) -> Namespace:
        values = dict(proven_base=None, contribution_base=None, scope_gate="enforce", task_evidence=False, mode="local-affected")
        values.update(overrides)
        return Namespace(**values)

    def test_the_waiver_reasons_follow_the_declared_mode(self) -> None:
        root = Path(".")
        self.assertIn("proven-base", select_checks.selector_scope_waiver(root, self.args(proven_base="abc"), True))
        self.assertIsNone(select_checks.selector_scope_waiver(root, self.args(), True))
        self.assertIn("neither starts the full validation set", select_checks.selector_scope_waiver(root, self.args(), False))

    def test_a_full_validation_run_gets_the_board_condition_and_a_narrow_run_does_not(self) -> None:
        captured = []
        with mock.patch.object(preflight, "run_preflight", side_effect=lambda ctx: captured.append(ctx)), \
                mock.patch.object(select_checks, "main_root", return_value=Path(".")), \
                mock.patch.object(select_checks, "run_git") as run_git, \
                mock.patch.object(select_checks, "coordinator_contract", return_value=False):
            run_git.return_value.stdout = "agent/x\n"
            select_checks.run_selector_preflight(Path("."), self.args(), [{"id": "c", "commands": ["x"], "selection_reason": "unknown-path"}], None)
            select_checks.run_selector_preflight(Path("."), self.args(), [{"id": "c", "commands": ["x"], "selection_reason": "mapped"}], None)
        self.assertIsNone(captured[0].scope_gate_waiver)
        self.assertIsNotNone(captured[1].scope_gate_waiver)

    def test_main_runs_the_preflight_before_any_command(self) -> None:
        order: list[str] = []
        with mock.patch.object(select_checks, "run_selector_preflight", side_effect=lambda *a: order.append("preflight")), \
                mock.patch.object(select_checks, "execute", side_effect=lambda *a, **k: order.append("execute") or 0), \
                mock.patch.object(select_checks, "current_worktree_root", return_value=ROOT), \
                mock.patch.object(select_checks, "load_config", return_value={"settings": {"full_commands": ["true"]}}), \
                mock.patch.object(select_checks, "read_platform_config", return_value={"harness_mode": "platform", "main_branch": "main"}), \
                mock.patch.object(select_checks, "require_managed_checkout_identity", return_value=None), \
                mock.patch.object(select_checks, "require_clean_private_lineage"), \
                mock.patch.object(select_checks, "coordinator_contract", return_value=False), \
                mock.patch.object(select_checks, "require_fresh_task_base", return_value="abc"), \
                mock.patch.object(sys, "argv", ["select_checks.py", "--execute", "--mode", "protected-full", "--scope-gate", "not-applicable"]), \
                redirect_stdout(io.StringIO()):
            with mock.patch.object(select_checks, "require_disposable_checkout"):
                select_checks.main()
        self.assertEqual(["preflight", "execute"], order)


if __name__ == "__main__":
    unittest.main()
