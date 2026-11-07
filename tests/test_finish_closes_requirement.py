"""The finish of the last child closes the Requirement, or names what stops it (BR-1009)."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_config import platform_config_text  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402

finish_task = load_platform_module("finish_task", SCRIPTS / "finish_task.py")
import requirement_terminal as terminal  # noqa: E402

PARENT = "acme/backlog#10"
CHILD = "acme/backlog#11"
OTHER = "acme/backlog#12"
WORK = Path("/tmp/task")
INTEGRATION = Path("/tmp/integration")


class ClosureCase(unittest.TestCase):
    def closing(self, *, state: str = "OPEN", children: tuple[str, ...] = (CHILD,), statuses: dict | None = None,
                acceptance: tuple[str, ...] = (), retrospective: Exception | None = None) -> mock.Mock:
        """Patch every read; return the ``reconcile_parent`` mock."""
        statuses = statuses if statuses is not None else {}

        def observe(_root, *, source_issue):
            status = statuses[source_issue]
            return None if status is None else SimpleNamespace(current_status=status)

        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for target, name, kwargs in (
            (terminal, "parent_for_child", {"return_value": PARENT}),
            (terminal.requirement_intake, "fetch_issue", {"return_value": {"state": state, "body": "body"}}),
            (terminal.requirement_intake, "parse_requirement_body", {"return_value": {"children": list(children)}}),
            (terminal.managed_project_status, "observe", {"side_effect": observe}),
            (terminal, "open_acceptance_items", {"return_value": list(acceptance)}),
            (terminal.requirement_retrospective, "require_checkpoint",
             {"side_effect": retrospective} if retrospective else {"return_value": {"result": "none"}}),
        ):
            stack.enter_context(mock.patch.object(target, name, **kwargs))
        return stack.enter_context(mock.patch.object(terminal, "reconcile_parent", return_value={
            "status": "done", "requirement": PARENT, "children": list(children), "retrospective": "none"}))


class ParentClosureTests(ClosureCase):
    def test_no_parent_means_nothing_to_close(self) -> None:
        with mock.patch.object(terminal, "parent_for_child", return_value=None):
            self.assertIsNone(terminal.parent_closure(INTEGRATION, CHILD))
            self.assertIsNone(terminal.close_after_delivery(INTEGRATION, child=CHILD))

    def test_the_last_child_closes_the_requirement_and_reports_it(self) -> None:
        reconcile = self.closing(children=(CHILD, OTHER), statuses={OTHER: "Done"})
        message = terminal.close_after_delivery(INTEGRATION, child=CHILD)
        reconcile.assert_called_once_with(INTEGRATION, requirement=PARENT, merged_children={CHILD})
        self.assertEqual(message, f"Requirement {PARENT} closed: 2 child(ren) delivered, retrospective none.")

    def test_open_children_are_named_and_nothing_closes(self) -> None:
        reconcile = self.closing(children=(CHILD, OTHER), statuses={OTHER: "In progress"})
        message = terminal.close_after_delivery(INTEGRATION, child=CHILD)
        reconcile.assert_not_called()
        self.assertIn(f"{OTHER} (In progress)", message)
        self.assertIn("stays open", message)

    def test_an_unreadable_child_status_is_an_error_and_not_a_wait(self) -> None:
        reconcile = self.closing(children=(CHILD, OTHER), statuses={OTHER: None})
        with self.assertRaisesRegex(terminal.RequirementTerminalError, f"{OTHER} has no readable Project status"):
            terminal.close_after_delivery(INTEGRATION, child=CHILD)
        reconcile.assert_not_called()

    def test_an_already_closed_issue_is_reported_only_as_closed(self) -> None:
        reconcile = self.closing(state="CLOSED", retrospective=AssertionError("a closed Issue is not rechecked"))
        message = terminal.close_after_delivery(INTEGRATION, child=CHILD)
        reconcile.assert_not_called()
        self.assertEqual(message, f"Requirement {PARENT}: the Issue is already closed.")

    def test_blocked_closure_names_every_missing_item(self) -> None:
        self.closing(acceptance=("owner-check",),
                     retrospective=terminal.requirement_retrospective.RetrospectivePending("Requirement retrospective is missing; run X", "X"))
        closure = terminal.parent_closure(INTEGRATION, CHILD)
        self.assertEqual(closure["state"], "blocked")
        self.assertIn("owner-check", closure["missing"][0])
        self.assertIn("retrospective is missing", closure["missing"][1])

    def test_a_missing_retrospective_reaches_reconcile_and_stops_there(self) -> None:
        pending = terminal.requirement_retrospective.RetrospectivePending("Requirement retrospective is missing; run X", "X")
        reconcile = self.closing(retrospective=pending)
        reconcile.side_effect = pending
        with self.assertRaisesRegex(terminal.requirement_retrospective.RetrospectivePending, "is missing"):
            terminal.close_after_delivery(INTEGRATION, child=CHILD)


class FinishClosureTests(ClosureCase):
    def outcome(self) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            finish_task.reconcile_linked_parent(INTEGRATION, SimpleNamespace(source_issue=CHILD), WORK)
        return output.getvalue()

    def test_quick_task_has_no_parent_step(self) -> None:
        finish_task.reconcile_linked_parent(INTEGRATION, None, WORK)

    def test_closure_is_printed(self) -> None:
        self.closing()
        self.assertIn(f"Requirement {PARENT} closed", self.outcome())

    def test_a_refused_closure_names_the_merge_the_cause_and_the_retry(self) -> None:
        reconcile = self.closing()
        reconcile.side_effect = terminal.RequirementTerminalError("Issue closure failed: HTTP 502")
        with self.assertRaises(SystemExit) as stopped:
            self.outcome()
        text = str(stopped.exception)
        self.assertIn(f"{CHILD} is merged and stays merged", text)
        self.assertIn("HTTP 502", text)
        self.assertIn(f"retry from {WORK}: python3 scripts/finish_task.py --cleanup", text)

    def test_retry_after_a_refusal_closes_and_a_second_retry_does_not_fail(self) -> None:
        reconcile = self.closing()
        reconcile.side_effect = terminal.RequirementTerminalError("Issue closure failed: HTTP 502")
        with self.assertRaises(SystemExit):
            self.outcome()
        reconcile.side_effect = None
        self.assertIn("closed:", self.outcome())
        terminal.requirement_intake.fetch_issue.return_value = {"state": "CLOSED", "body": "body"}
        self.assertIn("already closed", self.outcome())
        self.assertEqual(reconcile.call_count, 2)


class NoticeTests(ClosureCase):
    def notice(self, identity: object) -> str:
        output = io.StringIO()
        with mock.patch.object(finish_task, "delivery_identity", **identity), contextlib.redirect_stdout(output):
            finish_task.notice_closure_gaps(INTEGRATION, WORK)
        return output.getvalue()

    def test_a_gap_is_printed_and_does_not_stop_publication(self) -> None:
        self.closing(retrospective=terminal.requirement_retrospective.RetrospectivePending("retrospective is missing; run X", "X"))
        self.assertIn(f"After the merge {PARENT} will not close: retrospective is missing; run X",
                      self.notice({"return_value": SimpleNamespace(source_issue=CHILD)}))

    def test_nothing_is_printed_when_closure_would_happen_or_for_a_quick_task(self) -> None:
        self.closing()
        self.assertEqual(self.notice({"return_value": SimpleNamespace(source_issue=CHILD)}), "")
        self.assertEqual(self.notice({"return_value": None}), "")

    def test_a_failed_check_is_said_aloud_and_does_not_stop_publication(self) -> None:
        self.assertIn("could not check", self.notice({"side_effect": RuntimeError("HTTP 502")}))


class StatusTests(unittest.TestCase):
    def status(self, closure: dict | None) -> dict:
        merged = SimpleNamespace(bucket="complete", remote_merged=True)
        printed = io.StringIO()
        with contextlib.ExitStack() as stack:
            for name, value in (("current_branch", "agent/managed"), ("github_cli_env", {}), ("profile", "standard"),
                                ("delivery_identity", SimpleNamespace(source_issue=CHILD, process_evidence=())),
                                ("observe_managed_project", SimpleNamespace(current_status="Done")),
                                ("observe_process_evidence_obligations", []), ("require_managed_checkout_identity", None),
                                ("observe_source_issue_drift", None)):
                stack.enter_context(mock.patch.object(finish_task, name, return_value=value))
            state = finish_task.publication_state
            stack.enter_context(mock.patch.object(state, "observe_publication", return_value=merged))
            stack.enter_context(mock.patch.object(state, "merge_durability_capability", return_value="full"))
            stack.enter_context(mock.patch.object(state, "status_payload", return_value={"status": "complete", "remote_merged": True}))
            stack.enter_context(mock.patch.object(terminal, "parent_closure", return_value=closure))
            stack.enter_context(contextlib.redirect_stdout(printed))
            finish_task.run_status(WORK, WORK, tomllib.loads(platform_config_text()), as_json=True)
        return json.loads(printed.getvalue())

    def test_an_open_parent_is_a_pending_obligation(self) -> None:
        payload = self.status({"parent": PARENT, "state": "blocked", "missing": ["retrospective is missing"]})
        self.assertEqual(payload["status"], "terminal_pending")
        self.assertEqual(payload["terminal_obligations"], [
            {"kind": "requirement", "state": "pending", "detail": f"{PARENT} is open: retrospective is missing"}])

    def test_a_closable_parent_says_to_rerun_finish(self) -> None:
        payload = self.status({"parent": PARENT, "state": "closable", "missing": []})
        self.assertEqual(payload["status"], "terminal_pending")
        self.assertIn("rerun finish", payload["terminal_obligations"][0]["detail"])

    def test_waiting_for_other_children_is_only_a_warning(self) -> None:
        payload = self.status({"parent": PARENT, "state": "waiting", "missing": [f"{OTHER} (In progress)"]})
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["terminal_obligations"][0]["state"], "warning")

    def test_a_closed_or_absent_parent_adds_nothing(self) -> None:
        self.assertEqual(self.status({"parent": PARENT, "state": "closed", "missing": []})["terminal_obligations"], [])
        self.assertEqual(self.status(None)["terminal_obligations"], [])


class EarlierCleanupOutputTests(unittest.TestCase):
    def report(self, **kwargs) -> str:
        output = io.StringIO()
        with mock.patch.object(finish_task, "cleanup_earlier_deferred", **kwargs), contextlib.redirect_stdout(output):
            finish_task.cleanup_earlier_tasks(INTEGRATION, WORK)
        return output.getvalue()

    def test_each_removed_and_kept_record_is_named(self) -> None:
        text = self.report(return_value=(["/w/one"], [{"path": "/w/two", "error": "dirty", "command": "cleanup two"}]))
        self.assertIn("Removed deferred worktree of an earlier task: /w/one", text)
        self.assertIn("/w/two kept (dirty)", text)
        self.assertIn("cleanup two", text)

    def test_a_failure_is_a_warning_and_delivery_stands(self) -> None:
        self.assertIn("WARNING", self.report(side_effect=SystemExit("invalid JSON")))


if __name__ == "__main__":
    unittest.main()
