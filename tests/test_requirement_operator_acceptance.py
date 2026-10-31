"""BR-943: an operator acceptance item keeps a Requirement open until the owner confirms or waives it."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import integration_contour as contour  # noqa: E402
import lifecycle_overview as overview  # noqa: E402
import requirement_intake  # noqa: E402
import requirement_terminal as terminal  # noqa: E402
from _platform_config import platform_config_text  # noqa: E402

REQUIREMENT = "acme/backlog#7"
ITEMS = ("- pool-config: Apply the recommended pool configuration on the owner Mac. "
         "Check: `python3 scripts/machine_pool.py doctor`\n"
         "- token: Rotate the reviewer token. Check: `gh auth status`")


def parent(items: str | None = ITEMS, state: str = "OPEN") -> dict:
    section = f"## Operator acceptance\n\n{items}\n\n" if items is not None else ""
    return {"state": state, "labels": [{"name": "type:requirement"}],
            "body": f"## Outcome\n\nImprove process\n\n{section}## Target repository\n\n`acme/project`\n\n"
                    "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n<!-- requirement-children:end -->"}


def decision(item: str, value: str = "confirmed", *, comment_id: int = 1, association: str = "OWNER") -> dict:
    record = {"item": item, "decision": value, "actor": "owner", "reason": "done on the Mac", "at": "2026-10-31T12:00:00+00:00"}
    return {"id": comment_id, "author_association": association, "body": terminal.ACCEPTANCE_PREFIX + json.dumps(record)}


class DeclarationTests(unittest.TestCase):
    def test_items_are_parsed_in_order_with_their_check(self) -> None:
        items = terminal.operator_items(parent()["body"])
        self.assertEqual([item["id"] for item in items], ["pool-config", "token"])
        self.assertEqual(items[0]["check"], "python3 scripts/machine_pool.py doctor")
        self.assertEqual(terminal.operator_items(parent(None)["body"]), [])

    def test_malformed_duplicate_or_empty_sections_fail_naming_the_cause(self) -> None:
        for items, message in (("- pool-config: Apply it without a check", "malformed"),
                               ("- a: x Check: `y`\n- a: z Check: `w`", "repeats item id 'a'"),
                               ("", "has no items")):
            with self.subTest(items=items), self.assertRaisesRegex(terminal.RequirementTerminalError, message):
                terminal.operator_items(parent(items)["body"])

    def test_created_requirement_body_carries_the_section(self) -> None:
        body = requirement_intake.render_requirement_body(outcome="Improve", target_repository="acme/project",
                                                          operator_acceptance=ITEMS)
        self.assertEqual(len(terminal.operator_items(body)), 2)

    def test_issue_state_is_explicit(self) -> None:
        self.assertEqual(terminal.issue_state({"state": "open"}, REQUIREMENT), "OPEN")
        for issue in ({}, {"state": "merged"}):
            with self.subTest(issue=issue), self.assertRaisesRegex(terminal.RequirementTerminalError, "expected OPEN or CLOSED"):
                terminal.issue_state(issue, REQUIREMENT)


class DecisionTests(unittest.TestCase):
    def test_latest_trusted_decision_wins_and_untrusted_markers_are_ignored(self) -> None:
        comments = [decision("token", "confirmed", comment_id=2), decision("token", "waived", comment_id=3),
                    decision("pool-config", comment_id=4, association="NONE")]
        decisions = terminal.acceptance_decisions(comments)
        self.assertEqual(set(decisions), {"token"})
        self.assertEqual(decisions["token"]["decision"], "waived")

    def test_malformed_trusted_marker_fails(self) -> None:
        broken = {"id": 5, "author_association": "OWNER", "body": terminal.ACCEPTANCE_PREFIX + '{"item": "token"}'}
        with self.assertRaisesRegex(terminal.RequirementTerminalError, "comment 5 is malformed"):
            terminal.acceptance_decisions([broken])

    def test_open_items_need_a_decision(self) -> None:
        with mock.patch.object(terminal.managed_task, "issue_comments", return_value=[decision("token")]):
            self.assertEqual(terminal.open_acceptance_items(Path("/r"), REQUIREMENT, parent()), ["pool-config"])
        with mock.patch.object(terminal.managed_task, "issue_comments", side_effect=AssertionError("no read without items")):
            self.assertEqual(terminal.open_acceptance_items(Path("/r"), REQUIREMENT, parent(None)), [])


class GateTests(unittest.TestCase):
    def test_terminal_reconciliation_refuses_open_items_before_checkpoint_and_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(platform_config_text(), encoding="utf-8")
            with mock.patch.object(terminal.subprocess, "run", return_value=mock.Mock(stdout="main", returncode=0)), \
                    mock.patch.object(terminal.requirement_target_lifecycle, "require_local_target_support"), \
                    mock.patch.object(terminal.requirement_intake, "fetch_issue", return_value=parent()), \
                    mock.patch.object(terminal.managed_task, "issue_comments", return_value=[decision("token")]), \
                    mock.patch.object(terminal.requirement_retrospective, "require_checkpoint") as checkpoint, \
                    mock.patch.object(terminal.managed_project_status, "reconcile") as project:
                with self.assertRaises(terminal.OwnerAcceptancePending) as raised:
                    terminal.reconcile_parent(root, requirement=REQUIREMENT)
            self.assertEqual(raised.exception.items, ["pool-config"])
            checkpoint.assert_not_called()
            project.assert_not_called()

    def test_post_merge_terminal_job_records_a_completed_outcome(self) -> None:
        ops = mock.Mock()
        ops.lineage.return_value = {"requirement": REQUIREMENT, "child": "acme/backlog#8"}
        ops.children.return_value = ["acme/backlog#8"]
        ops.requirement_checkpointed.return_value = True
        ops.reconcile_parent.side_effect = terminal.OwnerAcceptancePending(["pool-config"])
        outcome = contour.run_terminal(ops, Path("/r"), 11, "agent/br-7-t1-x", "a" * 40, task_identity={"change": "x"})
        self.assertEqual(outcome, "requirement-awaits-owner-acceptance: pool-config")
        self.assertFalse(outcome.startswith(("failed", "blocked")))


class AcceptTests(unittest.TestCase):
    def run_accept(self, issue: dict, comments: list[dict], item: str = "pool-config"):
        posted = []

        def post(root, requirement, record):
            posted.append(record)
            comments.append(decision(record["item"], record["decision"], comment_id=100 + len(posted)))
        with mock.patch.object(terminal.requirement_intake, "fetch_issue", return_value=issue), \
                mock.patch.object(terminal.managed_task, "issue_comments", side_effect=lambda *a: list(comments)), \
                mock.patch.object(terminal, "reconcile_parent", return_value={"status": "done"}) as close:
            result = terminal.accept(Path("/r"), requirement=REQUIREMENT, item=item, decision="confirmed",
                                     reason="owner confirmed in chat", via="chat-coordinator", actor="owner", post=post)
        return result, posted, close

    def test_last_open_item_closes_through_the_single_closer(self) -> None:
        result, posted, close = self.run_accept(parent(), [decision("token")])
        self.assertEqual((result["status"], posted[0]["via"], posted[0]["actor"]), ("done", "chat-coordinator", "owner"))
        close.assert_called_once_with(Path("/r"), requirement=REQUIREMENT, merged_children={"acme/backlog#8"})

    def test_other_open_items_are_reported_without_closing(self) -> None:
        result, posted, close = self.run_accept(parent(), [])
        self.assertEqual((result["status"], result["open"]), ("awaits-owner-acceptance", ["token"]))
        close.assert_not_called()

    def test_unknown_item_or_closed_requirement_is_refused_without_writing(self) -> None:
        for issue, item, message in ((parent(), "other", "declares no operator acceptance item 'other'"),
                                     (parent(state="CLOSED"), "pool-config", "already closed")):
            with self.subTest(message=message), self.assertRaisesRegex(terminal.RequirementTerminalError, message):
                self.run_accept(issue, [], item=item)


class OverviewTests(unittest.TestCase):
    def test_open_items_are_listed_with_check_and_decision_command(self) -> None:
        items = terminal.operator_items(parent()["body"])
        pending = overview.owner_acceptance(REQUIREMENT, items, ["pool-config"])
        lines = overview._owner_acceptance_lines({"owner_acceptance": pending})
        self.assertEqual(lines[1], "    check: python3 scripts/machine_pool.py doctor")
        self.assertIn(f"requirement_terminal.py accept --requirement {REQUIREMENT} --item pool-config", lines[2])


if __name__ == "__main__":
    unittest.main()
