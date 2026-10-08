"""Durable coordinator friction evidence on candidate PRs and its retrospective consumption."""
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
import agent_friction as friction  # noqa: E402
import integration_contour as contour  # noqa: E402
import publication_queue as queue  # noqa: E402
import requirement_retrospective as retrospective  # noqa: E402

HEAD = "a" * 40
REQUIREMENT = "acme/backlog#7"
CHILDREN = ["acme/backlog#8", "acme/backlog#9"]
BRANCH = "agent/br-7-t8-task"
KEY = "coordinator:" + "0123456789abcdef01234567"


def event(**overrides) -> dict:
    return {"task": BRANCH, "number": 11, "head": HEAD, "stage": "blocked-escalation", "worker": "github-actions:o/r:1:1",
            "dedupe_key": KEY, "category": "lifecycle-blocked-escalation", "severity": "high",
            "triggers": ["repeated-error"], "observation": "blocked", "evidence": "PR #11 blocked",
            "hypothesis": "h", "proposal": "p", **overrides}


class FakePR:
    """One PR's comment history; the coordinator App authors posted comments."""

    def __init__(self):
        self.comments: list[dict] = []
        self.fail_post: Exception | None = None

    def post(self, _root, *args, data=None, **_kwargs):
        if self.fail_post:
            raise self.fail_post
        self.comments.append({"id": len(self.comments) + 1, "author_association": "NONE",
                              "performed_via_github_app": {"slug": "bot"}, "body": data["body"]})

    def forged(self, body: str) -> None:
        self.comments.append({"id": len(self.comments) + 1, "author_association": "NONE",
                              "performed_via_github_app": {"slug": "evil"}, "body": body})


class EvidenceFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.pr = FakePR()
        for patcher in (
            mock.patch.object(queue, "_gh", side_effect=self.pr.post),
            mock.patch.object(queue, "_comments", side_effect=lambda r, repo, n: list(self.pr.comments)),
            mock.patch.object(queue, "_repo", return_value="o/r"),
            mock.patch.object(queue, "trusted_apps", return_value=frozenset({"bot"})),
            mock.patch.object(queue, "trusted_writers", return_value=frozenset()),
            mock.patch.object(queue, "_requirement_candidate_numbers", return_value=([11], None)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)


class EvidenceRecordTests(EvidenceFixture):
    def test_record_round_trips_with_requirement_head_stage_and_worker(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        self.assertTrue(self.pr.comments[0]["body"].startswith(queue.EVIDENCE_PREFIX))
        [found] = queue.requirement_evidence(ROOT, REQUIREMENT, CHILDREN)
        self.assertEqual(found["durable"], {"number": 11, "head": HEAD, "stage": "blocked-escalation",
                                            "worker": "github-actions:o/r:1:1"})
        self.assertEqual((found["requirement"], found["task"], found["attribution"]), (REQUIREMENT, BRANCH, "coordinator"))
        self.assertEqual(found["id"], "coordinator-0123456789abcdef")

    def test_retry_posts_once(self):
        first = queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        again = queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        self.assertEqual(len(self.pr.comments), 1)
        self.assertEqual(first["event_id"], again["event_id"])
        queue.post_evidence(ROOT, event(dedupe_key="coordinator:" + "f" * 24), requirement=REQUIREMENT)
        self.assertEqual(len(self.pr.comments), 2)

    def test_forged_author_is_ignored(self):
        body = queue.EVIDENCE_PREFIX + "{not json"
        self.pr.forged(body)
        self.assertEqual(queue.requirement_evidence(ROOT, REQUIREMENT), [])

    def test_malformed_trusted_record_raises(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        good = json.loads(self.pr.comments[0]["body"][len(queue.EVIDENCE_PREFIX):])
        cases = {"not json": "{broken", "wrong pr": json.dumps({**good, "number": 12}),
                 "bad head": json.dumps({**good, "head": "abc"}), "no worker": json.dumps({**good, "worker": ""}),
                 "wrong version": json.dumps({**good, "version": 2}),
                 "id mismatch": json.dumps({**good, "event_id": "coordinator-ffffffffffffffff"})}
        for label, body in cases.items():
            with self.subTest(label), mock.patch.object(
                    queue, "_comments", return_value=[{**self.pr.comments[0], "body": queue.EVIDENCE_PREFIX + body}]):
                with self.assertRaisesRegex(queue.QueueError, "invalid coordinator evidence"):
                    queue.requirement_evidence(ROOT, REQUIREMENT)

    def test_incomplete_event_is_refused(self):
        with self.assertRaisesRegex(queue.QueueError, "lacks worker"):
            queue.post_evidence(ROOT, event(worker=""), requirement=None)
        with self.assertRaisesRegex(queue.QueueError, "full commit SHA"):
            queue.post_evidence(ROOT, event(head="abc"), requirement=None)

    def test_other_requirements_are_not_attributed(self):
        queue.post_evidence(ROOT, event(), requirement="acme/backlog#99")
        queue.post_evidence(ROOT, event(dedupe_key="coordinator:" + "e" * 24), requirement=None)
        self.assertEqual(queue.requirement_evidence(ROOT, REQUIREMENT, CHILDREN), [])


class SinkTests(EvidenceFixture):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # A dedicated subdirectory: the shared-workspace guard repairs it, never the private temp root.
        self.log = Path(self.tmp.name) / ".claude" / "log.jsonl"
        self.log.parent.mkdir()
        for patcher in (mock.patch.object(friction, "log_path", lambda: self.log),
                        mock.patch.object(friction, "state_path", lambda: self.log.parent / "state.json")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sink = contour.default_friction_sink(
            ROOT, lineage=lambda root, branch: {"requirement": REQUIREMENT, "child": CHILDREN[0]})

    def test_local_mirror_shares_the_durable_event_id(self):
        self.sink(event())
        [local] = [json.loads(line) for line in self.log.read_text().splitlines()]
        [durable] = queue.requirement_evidence(ROOT, REQUIREMENT)
        self.assertEqual(local["id"], durable["id"])
        self.sink(event())
        self.assertEqual((len(self.pr.comments), len(self.log.read_text().splitlines())), (1, 1))

    def test_durable_failure_raises_and_leaves_no_local_event(self):
        self.pr.fail_post = queue.QueueError("comment denied")
        with self.assertRaisesRegex(queue.QueueError, "comment denied"):
            self.sink(event())
        self.assertFalse(self.log.exists())

    def test_lineage_failure_raises_before_anything_is_written(self):
        sink = contour.default_friction_sink(ROOT, lineage=mock.Mock(side_effect=contour.JobBlocked("no reservation")))
        with self.assertRaises(contour.JobBlocked):
            sink(event())
        self.assertEqual(self.pr.comments, [])

    def test_local_mirror_failure_raises(self):
        with mock.patch.object(friction, "append_coordinator_event", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.sink(event())

    def test_persistence_failure_leaves_no_handoff_record_and_fails_the_run(self):
        pr = {"number": 11, "state": "open", "merged": False, "labels": [],
              "head": {"sha": HEAD, "ref": BRANCH}}
        queue.set_friction_sink(self.sink, worker="w")
        self.addCleanup(queue.set_friction_sink, None)
        self.pr.fail_post = queue.QueueError("comment denied")
        with mock.patch.object(queue, "_pr", return_value=pr), \
                mock.patch.object(queue, "_project_lifecycle_label"):
            with self.assertRaisesRegex(queue.QueueError, "friction recording failed"):
                queue._transition(ROOT, "o/r", 11, "blocked-escalation", HEAD, task_identity={"head": "x"},
                                  red_gate={"name": "review", "evidence": "x"})
        self.assertEqual(self.pr.comments, [])

    def test_sink_without_worker_identity_raises(self):
        queue.set_friction_sink(lambda e: None)
        self.addCleanup(queue.set_friction_sink, None)
        with self.assertRaisesRegex(queue.QueueError, "worker run identity"):
            queue.emit_friction(11, BRANCH, "blocked-escalation", HEAD, "d")
        with self.assertRaisesRegex(queue.QueueError, "worker run identity"):
            queue.use_default_friction_sink(ROOT, worker=" ")

    def test_emitted_event_carries_head_stage_and_worker(self):
        seen = []
        queue.set_friction_sink(seen.append, worker="w1")
        self.addCleanup(queue.set_friction_sink, None)
        queue.emit_friction(11, BRANCH, "blocked-escalation", HEAD, "d")
        self.assertEqual((seen[0]["head"], seen[0]["stage"], seen[0]["worker"]), (HEAD, "blocked-escalation", "w1"))
        self.assertRegex(seen[0]["dedupe_key"], r"^coordinator:[0-9a-f]{24}$")


def parent_issue() -> dict:
    return {"body": "## Outcome\n\nX\n\n## Target repository\n\n`acme/project`\n\n"
                    "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n- [ ] acme/backlog#9\n"
                    "<!-- requirement-children:end -->"}


class RetrospectiveDurableTests(EvidenceFixture):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude" / "empty-log.jsonl"  # clean checkout: no local coordinator events
        self.log.parent.mkdir()
        for patcher in (mock.patch.object(friction, "log_path", lambda: self.log),
                        mock.patch.object(friction, "current_worktree_root", lambda: ROOT),
                        mock.patch.object(friction, "current_branch", lambda: "main"),
                        mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent_issue())):
            patcher.start()
            self.addCleanup(patcher.stop)

    def checkpoint(self, **kw):
        return retrospective.checkpoint(self.root, requirement=REQUIREMENT, review_note="Reviewed.",
                                        result=kw.pop("result", "none"), event_ids=kw.pop("event_ids", []), **kw)

    def review_path(self) -> dict:
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with mock.patch.object(retrospective, "main_root", return_value=self.root), \
                mock.patch.object(sys, "argv", ["r", "review-path", "--requirement", REQUIREMENT]), redirect_stdout(out):
            self.assertEqual(retrospective.main(), 0)
        return json.loads(out.getvalue())

    def test_review_path_on_clean_checkout_lists_durable_events_with_provenance(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        result = self.review_path()
        self.assertEqual(result["lifecycle_failures"], ["coordinator-0123456789abcdef"])
        self.assertEqual(result["coordinator_events"][0]["durable"]["head"], HEAD)
        self.assertEqual(result["coordinator_events"][0]["durable"]["worker"], "github-actions:o/r:1:1")
        self.assertEqual(result["evidence_sources"]["coordinator-evidence"], "available")

    def test_high_severity_durable_failure_must_be_linked_or_classified(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        with self.assertRaises(retrospective.RequirementRetrospectiveError):
            self.checkpoint()
        linked = self.checkpoint(result="findings", event_ids=["coordinator-0123456789abcdef"])
        self.assertEqual(linked["event_ids"], ["coordinator-0123456789abcdef"])
        self.assertEqual(self.checkpoint(dispositions=["coordinator-0123456789abcdef=expected-behavior"])["status"], "recorded")

    def test_workaround_trigger_is_mandatory(self):
        queue.post_evidence(ROOT, event(severity="medium", stage="x", triggers=["nondefault-override"],
                                        category="coordinator-x"), requirement=REQUIREMENT)
        with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "not linked"):
            self.checkpoint()

    def test_unreadable_durable_source_is_a_named_gap_refused_unless_accepted(self):
        with mock.patch.object(queue, "_comments", side_effect=queue.QueueError("GitHub down")):
            result = self.review_path()
            self.assertEqual(result["evidence_sources"]["coordinator-evidence"], "unreadable")
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "coordinator-evidence"):
                self.checkpoint()
            self.assertEqual(self.checkpoint(accepted_gaps=["coordinator-evidence"])["status"], "recorded")
            receipt = retrospective.require_checkpoint(self.root, requirement=REQUIREMENT)
            self.assertEqual(receipt["accepted_gaps"], ["coordinator-evidence"])

    def test_malformed_trusted_record_is_a_gap_not_an_empty_source(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        self.pr.comments[0]["body"] = queue.EVIDENCE_PREFIX + "{broken"
        self.assertEqual(self.review_path()["evidence_sources"]["coordinator-evidence"], "unreadable")
        with self.assertRaises(friction.DurableEvidenceError):
            friction.events_for_task(REQUIREMENT)

    def test_developer_task_lookups_never_call_github(self):
        with mock.patch.object(queue, "requirement_evidence", side_effect=AssertionError("GitHub called")):
            self.assertEqual(friction.events_for_task(BRANCH), [])
            self.assertEqual(friction.evidence_source_status(), {"friction-log": "available"})

    def test_durable_event_replaces_the_local_mirror_by_id(self):
        queue.post_evidence(ROOT, event(), requirement=REQUIREMENT)
        mirror = friction.append_coordinator_event(
            task=BRANCH, requirement=REQUIREMENT, category="lifecycle-blocked-escalation", triggers=["repeated-error"],
            severity="high", observation="blocked", evidence="e", hypothesis="h", proposal="p", dedupe_key=KEY,
            event_id="coordinator-0123456789abcdef")
        events = friction.events_for_task(REQUIREMENT)
        self.assertEqual([e["id"] for e in events], [mirror["id"]])
        self.assertIn("durable", events[0])


if __name__ == "__main__":
    unittest.main()
