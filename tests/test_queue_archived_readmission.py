"""A developer re-handoff over an archived change's waiting candidate (BR-837 contract).

After a coordinator finalize archived the change, a developer fix on top of the proven head
is accepted for re-admission while the candidate waits in ``integration-repair-pending``,
``repair-pending``, ``blocked-escalation`` or an unclaimed ``finalize-pending`` (BR-933), or when its proven head stopped ``blocked-retryable``
on the ``semantic-verification`` red gate; a head that does not continue the proven head is
still refused.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import _platform_common  # noqa: E402
import publication_queue as queue  # noqa: E402

BASE = "a" * 40
HEAD = "b" * 40
PROVEN = "c" * 40
FIX = "d" * 40
REPO = "owner/repo"
ROOT_PATH = Path("/unused")
WAITING_STATES = ("integration-repair-pending", "repair-pending", "blocked-escalation", "finalize-pending")


def events() -> list[dict]:
    admit = {"version": 1, "number": 1, "kind": "admit", "comment_id": 20, "head": HEAD, "base": BASE, "branch": "agent/1"}
    update = {"version": 1, "number": 1, "kind": "update", "comment_id": 30, "previous": HEAD, "head": PROVEN, "base": BASE}
    return [admit, update]


class LocalStatusDeveloperFixTests(unittest.TestCase):
    def observe(self, lineage: dict | None, *, descends: bool = True) -> dict | None:
        view = subprocess.CompletedProcess([], 0, json.dumps({"number": 1, "baseRefName": "main", "headRefName": "agent/1"}), "")
        git = subprocess.CompletedProcess([], 0, FIX + "\n", "")
        plain = {"state": "waiting", "number": 1, "position": 1, "owner": None}
        with patch.object(_platform_common, "run_github_with_retry", return_value=view), \
             patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_events", return_value=events()), \
             patch.object(queue, "run_git", return_value=git), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_latest", return_value=lineage), \
             patch.object(queue, "_is_ancestor", return_value=descends) as self.descends, \
             patch.object(queue, "status", return_value=plain):
            return queue.local_status(ROOT_PATH, "agent/1")

    def test_descendant_fix_over_each_waiting_state_is_observed_for_readmission(self) -> None:
        for state in WAITING_STATES:
            with self.subTest(state=state):
                observed = self.observe({"state": state, "head": PROVEN})
                self.descends.assert_called_once_with(ROOT_PATH, PROVEN, FIX)
                self.assertEqual((observed["state"], observed["proven_head"], observed["head"]),
                                 ("readmission", PROVEN, FIX))

    def test_head_that_does_not_continue_the_proven_head_is_refused(self) -> None:
        for state in WAITING_STATES:
            with self.subTest(state=state), \
                 self.assertRaisesRegex(queue.QueueError, "not the admitted or proven coordinator head"):
                self.observe({"state": state, "head": PROVEN}, descends=False)

    def test_other_states_and_other_heads_still_refuse(self) -> None:
        for lineage in ({"state": "repairing", "head": PROVEN}, {"state": "reviewing", "head": PROVEN},
                        {"state": "repair-pending", "head": HEAD}, None):
            with self.subTest(lineage=lineage), \
                 self.assertRaisesRegex(queue.QueueError, "not the admitted or proven coordinator head"):
                self.observe(lineage)


    def test_semantic_blocked_retryable_proven_head_is_observed_for_readmission(self) -> None:
        observed = self.observe({"state": "blocked-retryable", "head": PROVEN,
                                 "red_gate": {"name": "semantic-verification"}})
        self.descends.assert_called_once_with(ROOT_PATH, PROVEN, FIX)
        self.assertEqual((observed["state"], observed["proven_head"], observed["head"]),
                         ("readmission", PROVEN, FIX))

    def test_other_blocked_retryable_red_gates_still_refuse(self) -> None:
        for red_gate in ({"name": "review"}, {"name": "selected-checks"}, {}, None):
            with self.subTest(red_gate=red_gate), \
                 self.assertRaisesRegex(queue.QueueError, "not the admitted or proven coordinator head"):
                self.observe({"state": "blocked-retryable", "head": PROVEN, "red_gate": red_gate})

    def test_semantic_blocked_retryable_off_the_proven_head_still_refuses(self) -> None:
        semantic = {"state": "blocked-retryable", "red_gate": {"name": "semantic-verification"}}
        for lineage, descends in (({**semantic, "head": HEAD}, True), ({**semantic, "head": PROVEN}, False)):
            with self.subTest(lineage=lineage, descends=descends), \
                 self.assertRaisesRegex(queue.QueueError, "not the admitted or proven coordinator head"):
                self.observe(lineage, descends=descends)


class SemanticReadmissionTests(unittest.TestCase):
    def run_with(self, lineage: dict | None) -> dict | None:
        observed = {"state": "readmission", "number": 7, "proven_head": PROVEN, "head": FIX}
        with patch.object(queue, "local_status", return_value=observed), \
             patch.object(queue, "_repo", return_value=REPO), \
             patch.object(queue, "_comments", return_value=[]), \
             patch.object(queue, "_latest", return_value=lineage):
            return queue.semantic_readmission(ROOT_PATH, "agent/example")

    def test_semantic_blocked_retryable_reopens_the_archived_handoff(self) -> None:
        lineage = {"state": "blocked-retryable", "head": PROVEN, "red_gate": {"name": "semantic-verification"}}
        self.assertEqual(self.run_with(lineage)["lineage"], lineage)

    def test_waiting_states_reopen_the_archived_handoff(self) -> None:
        for state in WAITING_STATES:
            with self.subTest(state=state):
                lineage = {"state": state, "head": PROVEN}
                self.assertEqual(self.run_with(lineage)["lineage"], lineage)

    def test_other_states_do_not_reopen_it(self) -> None:
        for lineage in ({"state": "repairing"}, {"state": "review-pending"},
                        {"state": "blocked-retryable", "red_gate": {"name": "review"}}, None):
            with self.subTest(lineage=lineage):
                self.assertIsNone(self.run_with(lineage))


if __name__ == "__main__":
    unittest.main()
