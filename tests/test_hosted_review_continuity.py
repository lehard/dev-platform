"""Hosted review transitions keep friction attribution and content-bound gates (2026-10-19 regression)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_pr_review_gate import QueueFixture, gate, queue, workers, PROVIDER  # noqa: E402

import agent_friction as friction  # noqa: E402
import candidate_lifecycle as lifecycle  # noqa: E402
import integration_contour as contour  # noqa: E402
import managed_task  # noqa: E402
import post_review_finalization as final  # noqa: E402

HEAD = "a" * 40
PUSHED = "b" * 40
FOREIGN = "c" * 40
BRANCH = "agent/br-7-t1-example"
IDENTITY = {"change": "example", "task_content": {"version": 1, "digest": "proof", "paths": {}, "base": HEAD,
                                                   "scope": "independent-review-v1"}}
ADMISSION = ("developer-friction", "selected-checks", "semantic-verification")
MATERIAL = {"semantic": {"availability": "available", "findings": [{"id": "bug", "severity": "material"}]}}
ADVISORY = {"semantic": {"availability": "available", "findings": [{"id": "nit", "severity": "advisory"}]}}


class Fixture(QueueFixture):
    """The queue fixture for a managed child branch, with the evidence channel wired in."""

    def __enter__(self):
        super().__enter__()
        self.stack.enter_context(mock.patch.object(queue, "_pr", side_effect=lambda *a: {
            "number": 7, "state": "open", "head": {"sha": self.head, "ref": BRANCH}, "labels": []}))
        self.stack.enter_context(mock.patch.object(queue, "_repo", return_value="o/r"))
        self.stack.enter_context(mock.patch.object(queue, "_requirement_candidate_numbers", return_value=([7], None)))
        return self

    def records(self, prefix):
        return [json.loads(row["body"][len(prefix):]) for row in self.comments if row["body"].startswith(prefix)]

    def receipt(self, previous, pushed, identity=IDENTITY, job="pr7:review:x:a0"):
        self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER",
                              "body": workers.RESULT_PREFIX + json.dumps({
                                  "job": job, "head": previous, "outcome": "validated-push",
                                  "pushed_head": pushed, "task_identity": identity, "worker": "w"})})


class HostedCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / ".claude" / "log.jsonl"
        log.parent.mkdir()
        for patcher in (mock.patch.object(friction, "log_path", lambda: log),
                        mock.patch.object(friction, "state_path", lambda: log.parent / "state.json"),
                        # The hosted contract has no [development_backlog]: any Backlog lookup would fail.
                        mock.patch.object(managed_task, "authoring_config",
                                          side_effect=SystemExit("Development Backlog authoring is not configured")),
                        mock.patch.object(workers, "PUSH_CONVERGENCE_INTERVAL", 0)):
            patcher.start()
            self.addCleanup(patcher.stop)
        queue.set_friction_sink(contour.default_friction_sink(ROOT), worker="gha-1-1-review")
        self.addCleanup(queue.set_friction_sink, None)

    def admitted(self, fixture):
        gates = {name: {"result": "passed", "identity": IDENTITY, "evidence": {"head": HEAD}} for name in ADMISSION}
        queue._transition(ROOT, "o/r", 7, "review-pending", HEAD, task_identity=IDENTITY, inherit_identity=False,
                          gates=gates)
        gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=[PROVIDER])
        return workers.build_job(fixture.candidate())

    def review(self, fixture, job, reports, *, heads, claims=(True, True), execute=None):
        observed = iter(heads)

        def current_head():
            value = next(observed)
            fixture.head = value
            return value

        outcome = {"status": "reviewed", "pushed_head": PUSHED, "reports": reports, "rejected": False}
        with mock.patch.object(workers, "execute_job", side_effect=execute or (lambda *a, **k: outcome)) as run:
            result = gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture", branch=BRANCH,
                                      allowed_paths=[], llm_command=[], current_head=current_head,
                                      post_result=lambda body: None, workdir="/unused", worker="w",
                                      claim_current=mock.Mock(side_effect=list(claims)))
        return result, run


class HostedReviewTransitionTests(HostedCase):
    def test_material_findings_record_repair_pending_with_durable_friction_in_one_run(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            # The PR API still reports the job head right after the push, then the pushed head.
            result, _ = self.review(fixture, job, MATERIAL, heads=[HEAD, HEAD, PUSHED])
            self.assertEqual(result["status"], "reviewed")
            candidate = fixture.candidate()
            self.assertEqual((candidate["state"], candidate["head"]), ("repair-pending", PUSHED))
            self.assertEqual(workers.build_job(candidate)["kind"], "repair")
            [evidence] = fixture.records(queue.EVIDENCE_PREFIX)
            self.assertEqual((evidence["work_identity"], evidence["child_identity"], evidence["stage"]),
                             ("BR-7", "BR-7/T1", "repair-pending"))
            self.assertNotIn("requirement", evidence)
            self.assertEqual(len(queue.requirement_evidence(ROOT, "acme/backlog#7")), 1)
            self.assertEqual(sum(record.get("kind") == "update" for record in fixture.records(lifecycle.V1_PREFIX)), 1)

    def test_review_without_material_findings_keeps_admission_gates(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            self.review(fixture, job, ADVISORY, heads=[PUSHED])
            candidate = fixture.candidate()
            self.assertEqual((candidate["state"], candidate["head"]), ("finalize-pending", PUSHED))
            self.assertEqual(sorted(candidate["gates"]), sorted([*ADMISSION, "review"]))
            # Finalization with unchanged content needs no fresh semantic verification.
            gates = final.reestablish_gates(ROOT, candidate["gates"], IDENTITY, PUSHED,
                                            checks_runner=mock.Mock(side_effect=AssertionError("checks rerun")))
            self.assertEqual(sorted(gates), sorted(candidate["gates"]))

    def test_unattributable_candidate_fails_before_the_reviewer_runs(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            before = list(fixture.comments)
            with mock.patch.object(workers, "execute_job") as run:
                with self.assertRaisesRegex(workers.WorkerError, "malformed work identity"):
                    gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture",
                                     branch="agent/br-7-example", allowed_paths=[], llm_command=[],
                                     current_head=lambda: HEAD, post_result=lambda body: None, workdir="/unused",
                                     worker="w", claim_current=lambda: True)
            run.assert_not_called()
            self.assertEqual(fixture.comments, before)

    def test_evidence_write_failure_publishes_no_transition(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            real_post = fixture.post

            def post(*args, data=None, **kwargs):
                if data["body"].startswith(queue.EVIDENCE_PREFIX):
                    raise queue.QueueError("comment denied")
                real_post(*args, data=data, **kwargs)

            with mock.patch.object(queue, "_gh", side_effect=post):
                with self.assertRaisesRegex(queue.QueueError, "friction recording failed"):
                    self.review(fixture, job, MATERIAL, heads=[PUSHED])
            self.assertFalse([r for r in fixture.records(queue.V2_PREFIX) if r["state"] == "repair-pending"])


class OwnPushTests(HostedCase):
    def test_foreign_head_after_push_is_still_discarded(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            result, _ = self.review(fixture, job, MATERIAL, heads=[HEAD, FOREIGN])
            self.assertEqual(result["status"], "discarded")
            self.assertFalse([r for r in fixture.records(queue.V2_PREFIX) if r["head"] != HEAD])

    def test_changed_claim_after_push_is_still_discarded(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            result, _ = self.review(fixture, job, MATERIAL, heads=[PUSHED], claims=(True, False))
            self.assertEqual(result["status"], "discarded")
            self.assertFalse(fixture.records(queue.EVIDENCE_PREFIX))

    def test_head_that_never_converges_fails_explicitly(self):
        with mock.patch.object(workers, "PUSH_CONVERGENCE_SECONDS", 0):
            with self.assertRaisesRegex(workers.WorkerError, "did not converge to pushed head"):
                workers.own_result_landed(lambda: HEAD, HEAD, PUSHED)

    def test_convergence_outcomes(self):
        heads = iter([HEAD, HEAD, PUSHED])
        self.assertTrue(workers.own_result_landed(lambda: next(heads), HEAD, PUSHED))
        self.assertFalse(workers.own_result_landed(lambda: FOREIGN, HEAD, PUSHED))
        self.assertTrue(workers.own_result_landed(lambda: HEAD, HEAD, HEAD))
        self.assertFalse(workers.own_result_landed(lambda: PUSHED, HEAD, HEAD))


class GateContinuityTests(HostedCase):
    def test_interrupted_review_push_keeps_content_bound_gates_through_the_next_claim(self):
        with Fixture(ROOT, HEAD) as fixture:
            job = self.admitted(fixture)
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY, inherit_identity=False,
                              next_job={k: v for k, v in job.items() if k != "number"})
            # The harness pushed evidence, then the run died before any transition.
            fixture.receipt(HEAD, PUSHED, job=workers.job_id(job))
            fixture.head = PUSHED
            recovered = fixture.candidate()
            self.assertEqual((recovered["state"], sorted(recovered["gates"])), ("review-pending", sorted(ADMISSION)))
            again = workers.build_job(recovered)
            self.review(fixture, again, ADVISORY, heads=[PUSHED], execute=lambda *a, **k: {
                "status": "reviewed", "pushed_head": PUSHED, "reports": ADVISORY, "rejected": False})
            self.assertEqual(sorted(fixture.candidate()["gates"]), sorted([*ADMISSION, "review"]))

    def test_changed_content_drops_gates(self):
        changed = {**IDENTITY, "task_content": {**IDENTITY["task_content"], "digest": "other"}}
        gates = {"semantic-verification": {"result": "passed", "identity": IDENTITY}}
        self.assertEqual(lifecycle.content_bound_gates(gates, changed), {})
        self.assertEqual(lifecycle.content_bound_gates({"legacy": {"result": "passed", "identity": HEAD}}, IDENTITY), {})


class RestoreGatesTests(HostedCase):
    def damaged(self, fixture, *, identity=IDENTITY, receipt=True):
        """The 2026-10-19 history: admission gates lost across a review-evidence push."""
        job = self.admitted(fixture)
        queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY, inherit_identity=False,
                          next_job={k: v for k, v in job.items() if k != "number"})
        if receipt:
            fixture.receipt(HEAD, PUSHED, identity=identity, job=workers.job_id(job))
        fixture.head = PUSHED
        review = {"result": "passed", "identity": IDENTITY, "evidence": ADVISORY}
        queue._transition(ROOT, "o/r", 7, "finalize-pending", PUSHED, task_identity=IDENTITY,
                          inherit_identity=False, gates={"review": review})
        self.assertEqual(sorted(fixture.candidate()["gates"]), ["review"])

    def test_restores_proven_admission_gates_without_changing_state(self):
        with Fixture(ROOT, HEAD) as fixture:
            self.damaged(fixture)
            result = queue.restore_gates(ROOT, "o/r", 7, expected_head=PUSHED)
            self.assertEqual(result["restored"], sorted(ADMISSION))
            candidate = fixture.candidate()
            self.assertEqual((candidate["state"], candidate["head"]), ("finalize-pending", PUSHED))
            self.assertEqual(sorted(candidate["gates"]), sorted([*ADMISSION, "review"]))
            count = len(fixture.comments)
            with self.assertRaisesRegex(queue.QueueError, "cannot be restored"):
                queue.restore_gates(ROOT, "o/r", 7)
            self.assertEqual(len(fixture.comments), count)

    def test_refuses_a_head_not_reached_by_a_trusted_harness_push(self):
        with Fixture(ROOT, HEAD) as fixture:
            self.damaged(fixture, receipt=False)
            count = len(fixture.comments)
            with self.assertRaisesRegex(queue.QueueError, "not reached by a trusted harness push"):
                queue.restore_gates(ROOT, "o/r", 7)
            self.assertEqual(len(fixture.comments), count)

    def test_refuses_a_push_that_changed_task_content(self):
        changed = {**IDENTITY, "task_content": {**IDENTITY["task_content"], "digest": "other"}}
        with Fixture(ROOT, HEAD) as fixture:
            self.damaged(fixture, identity=changed)
            with self.assertRaisesRegex(queue.QueueError, "changed the task content"):
                queue.restore_gates(ROOT, "o/r", 7)

    def test_refuses_another_head_than_expected(self):
        with Fixture(ROOT, HEAD) as fixture:
            self.damaged(fixture)
            with self.assertRaisesRegex(queue.QueueError, "not the expected"):
                queue.restore_gates(ROOT, "o/r", 7, expected_head=FOREIGN)


if __name__ == "__main__":
    unittest.main()
