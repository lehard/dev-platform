"""BR-965: a developer re-handoff needs no manual board, acknowledgment, checkpoint or routing steps."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agent_board  # noqa: E402
import finish_task  # noqa: E402
import lifecycle_workers  # noqa: E402
import openspec_lifecycle  # noqa: E402
import pr_review_gate  # noqa: E402
import publication_queue  # noqa: E402
import worktree_cleanup  # noqa: E402

HEAD = "a" * 40
ACK = {"with_id": "other", "path": "docs/shared.md", "reason": "disjoint"}


class HandedOffRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.board = Path(self.tmp.name) / "agents-board.json"
        self.board.write_text(json.dumps({"items": [
            {"id": "mine", "task": "t", "branch": "agent/x", "worktree": self.tmp.name, "acknowledgments": [ACK]}]}))
        patcher = mock.patch.object(agent_board, "board_path", return_value=self.board)
        patcher.start()
        self.addCleanup(patcher.stop)

    def item(self) -> dict:
        return json.loads(self.board.read_text())["items"][0]

    def test_hand_off_keeps_the_record_and_its_acknowledgments(self) -> None:
        agent_board.cmd_hand_off(argparse.Namespace(id="mine", head=HEAD, pr=7, quiet=True))
        item = self.item()
        self.assertEqual((item["handed_off"]["head"], item["handed_off"]["pr"]), (HEAD, 7))
        self.assertEqual(item["acknowledgments"], [ACK])

    def test_reactivate_makes_only_a_handed_off_claim_active(self) -> None:
        with self.assertRaisesRegex(SystemExit, "mine is not a handed-off claim"):
            agent_board.cmd_reactivate(argparse.Namespace(id="mine"))
        agent_board.cmd_hand_off(argparse.Namespace(id="mine", head=HEAD, pr=7, quiet=True))
        agent_board.cmd_reactivate(argparse.Namespace(id="mine"))
        item = self.item()
        self.assertNotIn("handed_off", item)
        self.assertEqual(item["acknowledgments"], [ACK])


class EligibilityTests(unittest.TestCase):
    def classify(self, problems: list[str], handed_off: bool) -> str:
        item = {"id": "x", "handed_off": {"head": HEAD}} if handed_off else {"id": "x"}
        with mock.patch.object(agent_board, "_status", return_value=problems):
            return agent_board.claim_eligibility(item, ROOT, main_branch="main", stale_hours=1)[0]

    def test_a_handed_off_record_claims_no_scope_and_a_merged_one_is_terminal(self) -> None:
        self.assertEqual(self.classify([], True), "handed-off")
        self.assertEqual(self.classify(["stale-heartbeat"], True), "handed-off")
        self.assertEqual(self.classify(["merged-pr"], True), "terminal")
        self.assertEqual(self.classify([], False), "valid-active")


class CleanupTests(unittest.TestCase):
    def test_a_handed_off_claim_does_not_block_post_merge_cleanup(self) -> None:
        # friction #802: an admitted task's claim must not keep its worktree "active-board".
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude/agents-board.json").write_text(json.dumps({"items": [
                {"id": "a", "worktree": str(root / "handed"), "handed_off": {"head": HEAD}},
                {"id": "b", "worktree": str(root / "active")}]}))
            paths = worktree_cleanup._active_board_paths(root, {"paths": {"agent_board": ".claude/agents-board.json"}})
        self.assertEqual(paths, {(root / "active").resolve()})


class RehandoffAcceptanceTests(unittest.TestCase):
    ITEM = {"id": "mine", "branch": "agent/x", "handed_off": {"head": HEAD, "pr": 7}}

    def refusal(self, *, state: str = "repair-pending", pr_state: str = "OPEN", descends: bool = True,
                number: int = 7) -> str | None:
        pr = subprocess.CompletedProcess("gh", 0, stdout=json.dumps({"number": number, "state": pr_state, "headRefName": "agent/x"}), stderr="")
        with mock.patch("_platform_common.run_github_with_retry", return_value=pr), \
                mock.patch.object(publication_queue, "_repo", return_value="o/r"), \
                mock.patch.object(publication_queue, "_comments", return_value=[]), \
                mock.patch.object(publication_queue, "_latest", return_value={"state": state}), \
                mock.patch.object(publication_queue, "_is_ancestor", return_value=descends):
            return agent_board.rehandoff_refusal(ROOT, self.ITEM)

    def test_a_re_admissible_pr_on_a_descendant_head_accepts_the_claim(self) -> None:
        for state in sorted(publication_queue.READMISSION_STATES):
            with self.subTest(state=state):
                self.assertIsNone(self.refusal(state=state))

    def test_every_other_case_is_refused_with_its_reason(self) -> None:
        self.assertIn("PR #7 is integrating", self.refusal(state="integrating"))
        self.assertIn("PR #7 is merged", self.refusal(pr_state="MERGED"))
        self.assertIn("does not descend from the handed-off head", self.refusal(descends=False))
        self.assertIn("handed-off PR #7 is not a PR of branch agent/x", self.refusal(number=8))

    def test_the_scope_gate_refuses_a_handed_off_claim_naming_the_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp) / "agents-board.json"
            worktree = Path(tmp)
            board.write_text(json.dumps({"items": [{**self.ITEM, "worktree": str(worktree)}]}))
            with mock.patch.object(agent_board, "board_path", return_value=board), \
                    mock.patch.object(agent_board, "rehandoff_refusal", return_value="PR #7 is integrating"):
                with self.assertRaisesRegex(SystemExit, r"handed off to the coordinator and PR #7 is integrating.*finish --id mine"):
                    agent_board._required_scope_inputs(ROOT, worktree, "agent/x", {"main_branch": "main"})
            with mock.patch.object(agent_board, "board_path", return_value=board), \
                    mock.patch.object(agent_board, "rehandoff_refusal", return_value=None):
                _, current, _ = agent_board._required_scope_inputs(ROOT, worktree, "agent/x", {"main_branch": "main"})
            self.assertEqual(current["id"], "mine")
            self.assertIn("handed_off", json.loads(board.read_text())["items"][0], "the scope gate wrote nothing")


class FinishBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.main = Path(self.tmp.name)
        (self.main / ".claude").mkdir()
        self.board = self.main / ".claude" / "agents-board.json"
        self.config = {"paths": {"agent_board": ".claude/agents-board.json"}}

    def write(self, item: dict) -> None:
        self.board.write_text(json.dumps({"items": [{"id": "mine", "worktree": str(self.main), **item}]}))

    def test_a_first_handoff_reactivates_nothing(self) -> None:
        self.write({})
        with mock.patch.object(finish_task.subprocess, "run") as run:
            finish_task.reactivate_handed_off_board(self.main, self.main, self.config)
        run.assert_not_called()

    def test_a_re_handoff_reactivates_its_handed_off_claim(self) -> None:
        self.write({"handed_off": {"head": HEAD}})
        done = subprocess.CompletedProcess("board", 0)
        with mock.patch.object(finish_task.subprocess, "run", return_value=done) as run:
            finish_task.reactivate_handed_off_board(self.main, self.main, self.config)
        self.assertEqual(run.call_args.args[0][2:], ["reactivate", "--id", "mine"])

    def test_admission_hands_the_claim_off_at_head(self) -> None:
        self.write({})
        done = subprocess.CompletedProcess("board", 0)
        pr = subprocess.CompletedProcess("gh", 0, stdout=json.dumps({"number": 7, "headRefName": "agent/x"}), stderr="")
        with mock.patch.object(finish_task, "run_git", return_value=mock.Mock(stdout=HEAD + "\n")), \
                mock.patch.object(finish_task, "current_branch", return_value="agent/x"), \
                mock.patch("_platform_common.run_github_with_retry", return_value=pr), \
                mock.patch.object(finish_task.subprocess, "run", return_value=done) as run:
            finish_task.hand_off_board(self.main, self.main, self.config)
        self.assertEqual(run.call_args.args[0][2:], ["hand-off", "--id", "mine", "--head", HEAD, "--pr", "7", "--quiet"])


class HandoffGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.change = Path(self.tmp.name) / "openspec/changes/work"
        self.change.mkdir(parents=True)

    def gates(self, routing: Exception | None = None, checkpoint_rc: int = 0) -> tuple[mock.Mock, mock.Mock]:
        with mock.patch.object(openspec_lifecycle, "archive_content_problems", return_value=[]), \
                mock.patch.object(openspec_lifecycle, "verification_passed", return_value=True), \
                mock.patch.object(openspec_lifecycle, "require_automated_evidence"), \
                mock.patch.object(openspec_lifecycle, "require_managed_routing_evidence", side_effect=routing) as route, \
                mock.patch.object(pr_review_gate, "task_identity", return_value={"task_content": {}}), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess("c", checkpoint_rc, "", "stale")) as run:
            (Path(self.tmp.name) / "scripts").mkdir(exist_ok=True)
            (Path(self.tmp.name) / "scripts/agent_friction.py").write_text("")
            try:
                pr_review_gate.handoff_gates(Path(self.tmp.name), self.change)
            except lifecycle_workers.WorkerError:
                raise
            except Exception:  # noqa: BLE001 - later gates are out of scope here
                pass
        return route, run

    def test_a_missing_retained_outcome_fails_at_handoff(self) -> None:
        with self.assertRaisesRegex(lifecycle_workers.WorkerError, "routing archive gate blocked"):
            self.gates(routing=SystemExit("work: routing archive gate blocked: retained execution outcome missing"))

    def test_an_archived_re_admission_is_not_routed_again(self) -> None:
        self.change = Path(self.tmp.name) / "openspec/changes/archive/2026-10-31-work"
        self.change.mkdir(parents=True)
        with mock.patch.object(pr_review_gate, "_archived_handoff_change", return_value="work"):
            route, _ = self.gates()
        route.assert_not_called()

    def test_the_checkpoint_is_asserted_by_task_content_not_exact_head(self) -> None:
        route, run = self.gates()
        route.assert_called_once_with(self.change)
        commands = [call.args[0] for call in run.call_args_list if "assert-checkpoint" in call.args[0]]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][-1], "assert-checkpoint")
        self.assertNotIn("--exact-head", commands[0])


if __name__ == "__main__":
    unittest.main()
