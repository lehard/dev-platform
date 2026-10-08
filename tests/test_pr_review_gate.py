from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
reviewer = load_platform_module("independent_review_runner", SCRIPTS / "independent_review_runner.py")
identity_module = load_platform_module("task_content_identity", SCRIPTS / "task_content_identity.py")
finish = load_platform_module("finish_task", SCRIPTS / "finish_task.py")
checks = load_platform_module("select_checks", SCRIPTS / "select_checks.py")
openspec = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
managed = load_platform_module("managed_task", SCRIPTS / "managed_task.py")

HEAD = "a" * 40
IDENTITY = {"change": "example", "task_content": {"version": 1, "digest": "proof", "paths": {}, "base": HEAD,
                                                   "scope": "independent-review-v1"}}


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL, text=True,
                          capture_output=True, check=True).stdout.strip()


class QueueFixture:
    """Inject only GitHub I/O; exercise real transitions, trust and job records."""

    def __init__(self, root, head):
        self.root, self.head = root, head
        self.comments = []
        self.stack = ExitStack()

    def __enter__(self):
        self.stack.enter_context(mock.patch.object(queue, "_pr", side_effect=lambda *a: {
            "number": 7, "state": "open", "head": {"sha": self.head, "ref": "agent/example"}, "labels": []}))
        self.stack.enter_context(mock.patch.object(queue, "_comments", side_effect=lambda *a: list(self.comments)))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "_project_lifecycle_label"))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=self.post))
        return self

    def post(self, *args, data=None, **kwargs):
        self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER", "body": data["body"]})

    def candidate(self):
        return queue._derive(self.root, queue._pr(self.root, "o/r", 7), self.comments)

    def __exit__(self, *args):
        self.stack.close()


class GateTests(unittest.TestCase):
    def test_queue_reuses_content_bound_required_checks_after_evidence_head_update(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            passed = {"result": "passed", "identity": IDENTITY, "evidence": "prior check log"}
            queue._transition(ROOT, "o/r", 7, "ready", HEAD, task_identity=IDENTITY,
                              inherit_identity=False, gates={"required-checks": passed})
            fixture.head = "b" * 40
            with mock.patch.object(queue, "_repo", return_value="o/r"), \
                    mock.patch.object(queue, "_queued", return_value=[(1, 7, {"branch": "agent/example"})]), \
                    mock.patch.object(queue, "_prepare", return_value=(fixture.head, HEAD)), \
                    mock.patch.object(queue, "_require_finalized"), \
                    mock.patch.object(queue, "_main", return_value=HEAD), \
                    mock.patch.object(queue, "_label"), \
                    mock.patch.object(queue, "required_check_state_for_ref") as check, \
                    mock.patch.object(queue.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                result = queue.worker(ROOT)
            self.assertEqual(result["state"], "waiting")
            check.assert_not_called()
            self.assertEqual(fixture.candidate()["gates"]["required-checks"], passed)

    def test_published_review_repair_retry_and_escalation_are_worker_jobs(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review")
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "review-pending")
            self.assertEqual(workers.build_job(candidate)["kind"], "review")
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            reports = {"semantic": {"availability": "available", "findings": [{"severity": "material"}]}}
            gate.complete_review(ROOT, "o/r", fixture.candidate(), reports, HEAD)
            self.assertEqual(fixture.candidate()["state"], "repair-pending")
            self.assertEqual(workers.build_job(fixture.candidate())["kind"], "repair")
            self.assertEqual(gate.review_outcome(reports, 3), "blocked-escalation")
            self.assertEqual(gate.review_outcome(reports, 1, rejected=True), "blocked-escalation")
            gate.complete_review(ROOT, "o/r", fixture.candidate(), {"s": {"availability": "unavailable"}}, HEAD)
            self.assertEqual(fixture.candidate()["state"], "blocked-retryable")
            job = workers.build_job(fixture.candidate())
            self.assertEqual(job["kind"], "review")
            self.assertEqual(job["attempt"], 2)
            # A moved PR head cannot receive an old review result.
            fixture.head = "b" * 40
            self.assertIsNone(gate.complete_review(ROOT, "o/r", candidate, reports, HEAD))

    def test_running_job_keeps_claim_and_new_jobs_increment_attempt(self):
        for kind, state in (("review", "reviewing"), ("repair", "repairing")):
            with self.subTest(kind=kind), QueueFixture(ROOT, HEAD) as fixture:
                gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, kind)
                job = workers.build_job(fixture.candidate())
                claim = {"id": 100, "author_association": "OWNER",
                         "body": workers.claim_body(job, "first", "2099-01-01T00:00:00Z")}
                fixture.comments.append({**claim, "body": workers.claim_body(job, "worker", "2099-01-01T00:00:00Z")})
                with mock.patch.object(workers, "execute_job", side_effect=RuntimeError("paused")):
                    with self.assertRaisesRegex(RuntimeError, "paused"):
                        gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture",
                                         branch="agent/example", allowed_paths=["src.py"], llm_command=["writer"],
                                         current_head=lambda: HEAD, post_result=lambda body: None, workdir="/unused")
                self.assertEqual(fixture.candidate()["state"], state)
                running_job = workers.build_job(fixture.candidate())
                self.assertEqual(running_job, job)
                self.assertFalse(workers.is_claimable(running_job, [claim]))
                gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, kind)
                self.assertEqual(workers.build_job(fixture.candidate())["attempt"], job["attempt"] + 1)

    def test_rejections_are_bound_to_current_material_finding_and_report(self):
        independent = load_platform_module("independent_review", SCRIPTS / "independent_review.py")
        report = {"availability": "available", "findings": [{"id": "bug", "severity": "material"}]}
        disposition = {"perspective": "spec-fidelity", "finding": "bug", "status": "rejected",
                       "report_sha256": independent.report_digest(report), "rationale": "reason"}
        self.assertTrue(gate.current_rejections({"spec-fidelity": report}, [disposition]))
        for update in ({"report_sha256": "stale"}, {"finding": "other"}, {"perspective": "other"}):
            self.assertFalse(gate.current_rejections({"spec-fidelity": report}, [{**disposition, **update}]))
        clean = {"availability": "available", "findings": []}
        rejected = gate.current_rejections({"spec-fidelity": clean}, [disposition])
        self.assertEqual(gate.review_outcome({"spec-fidelity": clean}, 1, rejected=rejected), "finalize-pending")

    def test_validated_push_recovers_when_post_push_handoff_is_interrupted(self):
        for kind, state in (("review", "reviewing"), ("repair", "repairing")):
            with self.subTest(kind=kind), QueueFixture(ROOT, HEAD) as fixture:
                gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, kind)
                job = workers.build_job(fixture.candidate())
                queue._transition(ROOT, "o/r", 7, state, HEAD, task_identity=IDENTITY)
                fresh = {**IDENTITY, "task_content": {**IDENTITY["task_content"], "digest": "fresh"}}
                receipt = {"id": 100, "author_association": "OWNER", "body": workers.result_body(
                    job, "worker", "validated-push", "b" * 40, task_identity=fresh)}
                fixture.comments.append(receipt)
                self.assertFalse(workers.job_completed(job, fixture.comments))
                self.assertEqual(workers.build_job(fixture.candidate()), job)
                fixture.head = "b" * 40
                recovered = fixture.candidate()
                self.assertEqual(recovered["state"], "review-pending")
                self.assertEqual(recovered["task_identity"], fresh)
                recovery_job = workers.build_job(recovered)
                self.assertEqual(recovery_job["head"], fixture.head)
                self.assertEqual(recovery_job["kind"], "review")
                self.assertTrue(workers.is_claimable(recovery_job, fixture.comments))
                receipt["author_association"] = "NONE"
                self.assertIsNone(workers.build_job(fixture.candidate()))
                receipt["author_association"] = "OWNER"
                fixture.head = "c" * 40
                self.assertIsNone(workers.build_job(fixture.candidate()))

    def test_review_jobs_carry_task_providers_and_unavailable_retries_are_bounded(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["claude"])
            self.assertEqual(workers.build_job(fixture.candidate())["providers"], ["claude"])
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            material = {"s": {"availability": "available", "findings": [{"severity": "material"}]}}
            gate.complete_review(ROOT, "o/r", fixture.candidate(), material, HEAD)
            self.assertEqual(workers.build_job(fixture.candidate())["providers"], ["claude"])
            unavailable = {"s": {"availability": "unavailable"}}
            gate.complete_review(ROOT, "o/r", {**fixture.candidate(), "attempts": {"review": 1}}, unavailable, HEAD)
            self.assertEqual(workers.build_job(fixture.candidate())["providers"], ["claude"])
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            gate.complete_review(ROOT, "o/r", {**fixture.candidate(), "attempts": {"review": 3, "review-unavailable": 2}}, unavailable, HEAD)
            self.assertEqual(fixture.candidate()["state"], "blocked-retryable")
            self.assertIsNone(workers.build_job(fixture.candidate()))

    def test_available_reviews_do_not_spend_the_unavailable_retry_budget(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["claude"])
            unavailable = {"s": {"availability": "unavailable"}}
            material = {"s": {"availability": "available", "findings": [{"severity": "material"}]}}
            for _ in range(2):
                queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
                gate.complete_review(ROOT, "o/r", fixture.candidate(), unavailable, HEAD)
            self.assertEqual(fixture.candidate()["attempts"]["review-unavailable"], 2)
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            gate.complete_review(ROOT, "o/r", fixture.candidate(), material, HEAD)
            self.assertEqual(fixture.candidate()["attempts"]["review-unavailable"], 0)
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            gate.complete_review(ROOT, "o/r", fixture.candidate(), unavailable, HEAD)
            self.assertIsNotNone(workers.build_job(fixture.candidate()))

    def test_recovered_review_keeps_providers_and_repaired_identity(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "repair", providers=["claude"])
            job = workers.build_job(fixture.candidate())
            queue._transition(ROOT, "o/r", 7, "repairing", HEAD, task_identity=IDENTITY,
                              next_job={k: v for k, v in job.items() if k != "number"})
            fresh = {**IDENTITY, "task_content": {**IDENTITY["task_content"], "digest": "fresh"}}
            fixture.comments.append({"id": 100, "author_association": "OWNER", "body": workers.result_body(
                job, "worker", "validated-push", "b" * 40, task_identity=fresh)})
            fixture.head = "b" * 40
            recovered = workers.build_job(fixture.candidate())
            self.assertEqual(recovered["providers"], ["claude"])
            self.assertEqual(recovered["task_identity"], fresh)
            fixture.comments.append({"id": 101, "author_association": "OWNER",
                                     "body": workers.claim_body(recovered, "worker", "2099-01-01T00:00:00Z")})
            with mock.patch.object(workers, "execute_job", side_effect=RuntimeError("paused")):
                with self.assertRaisesRegex(RuntimeError, "paused"):
                    gate.run_claimed(ROOT, "o/r", fixture.candidate(), recovered, source_repo="fixture",
                                     branch="agent/example", allowed_paths=[], llm_command=None,
                                     current_head=lambda: fixture.head, post_result=lambda body: None,
                                     workdir="/unused")
            running = fixture.candidate()
            self.assertEqual(running["state"], "reviewing")
            self.assertEqual(running["task_identity"], fresh)

    def test_review_gate_evidence_is_compact_and_repair_brief_is_small(self):
        full = {"availability": "available", "findings": [
            {"id": "f1", "severity": "material", "summary": "s" * 900, "evidence": "e" * 5000, "extra": "z" * 9000}]}
        compact = gate.compact_reports({"spec": full})
        self.assertLess(len(json.dumps(compact)), 1500)
        self.assertEqual(gate.compact_reports(compact), compact)
        self.assertEqual(gate.review_outcome(compact, 1), "repair-pending")
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review")
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            gate.complete_review(ROOT, "o/r", fixture.candidate(), {"spec": full}, HEAD)
            recorded = fixture.candidate()
            self.assertEqual(recorded["gates"]["review"]["evidence"], compact)
            brief = gate.repair_brief(recorded)
            self.assertEqual([f["id"] for f in brief["findings"]], ["f1"])
            self.assertLess(len(json.dumps(brief)), 2000)
            self.assertNotIn("paths", json.dumps(brief))

    def test_review_result_posted_before_interruption_repeats_review(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["claude"])
            job = workers.build_job(fixture.candidate())
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY,
                              next_job={k: v for k, v in job.items() if k != "number"})
            self.assertEqual(fixture.candidate()["state"], "reviewing")
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.result_body(job, "worker", "reviewed", HEAD)})
            recovered = fixture.candidate()
            self.assertEqual(recovered["state"], "review-pending")
            again = workers.build_job(recovered)
            self.assertEqual((again["kind"], again["attempt"], again["providers"]),
                             ("review", job["attempt"] + 1, ["claude"]))
            self.assertTrue(workers.is_claimable(again, fixture.comments))

    def test_worker_without_unexpired_exact_claim_has_no_write_authority(self):
        with QueueFixture(ROOT, HEAD) as fixture, mock.patch.object(workers, "execute_job") as execute:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "repair")
            job = workers.build_job(fixture.candidate())
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "first", "2000-01-01T00:00:00Z")})
            fixture.comments.append({"id": 101, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "second", "2099-01-01T00:00:00Z")})
            kwargs = dict(source_repo="fixture", branch="agent/example", allowed_paths=["src.py"],
                          llm_command=["writer"], current_head=lambda: HEAD, post_result=lambda body: None,
                          workdir="/unused")
            outcome = gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, worker="first", **kwargs)
            self.assertEqual(outcome["status"], "discarded")
            execute.assert_not_called()
            execute.return_value = {"status": "pushed", "pushed_head": HEAD}
            outcome = gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, worker="first",
                                       claim_current=lambda: execute.called is False, **kwargs)
            self.assertEqual(outcome["status"], "discarded")

    def test_repair_result_posted_before_interruption_is_recovered(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "repair")
            job = workers.build_job(fixture.candidate())
            queue._transition(ROOT, "o/r", 7, "repairing", HEAD, task_identity=IDENTITY,
                              next_job={k: v for k, v in job.items() if k != "number"})
            self.assertEqual(fixture.candidate()["state"], "repairing")
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.result_body(job, "worker", "no-change")})
            recovered = fixture.candidate()
            self.assertEqual(recovered["state"], "blocked-escalation")
            self.assertIsNone(workers.build_job(recovered))

    def test_identity_change_discards_prior_gates(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            old = {"result": "passed", "identity": IDENTITY, "evidence": "check"}
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", gates={"selected-checks": old})
            fresh = {**IDENTITY, "task_content": {**IDENTITY["task_content"], "digest": "new"}}
            gate.offer(ROOT, "o/r", 7, HEAD, fresh, "review", gates={})
            self.assertEqual(fixture.candidate()["task_identity"], fresh)
            self.assertEqual(fixture.candidate()["gates"], {})

    def test_reuse_requires_proven_content_not_head_or_empty_identity(self):
        passed = {"result": "passed", "identity": IDENTITY, "evidence": "check"}
        self.assertTrue(gate.reusable(ROOT, passed, IDENTITY))
        self.assertFalse(gate.reusable(ROOT, passed, {"change": "example"}))
        self.assertFalse(gate.reusable(ROOT, {**passed, "identity": HEAD}, IDENTITY))
        self.assertFalse(gate.reusable(ROOT, {**passed, "result": "failed"}, IDENTITY))

    def test_reused_review_does_not_launch_and_outages_do_not_exhaust_repairs(self):
        reports = {"perspective": {"availability": "available", "findings": []}}
        passed = {"result": "passed", "identity": IDENTITY, "evidence": reports}
        with QueueFixture(ROOT, HEAD) as fixture, mock.patch.object(workers, "execute_job") as execute:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", gates={"review": passed})
            candidate = fixture.candidate()
            outcome = gate.run_claimed(ROOT, "o/r", candidate, workers.build_job(candidate),
                                       source_repo="fixture", branch="agent/example", allowed_paths=[],
                                       llm_command=None, current_head=lambda: HEAD, post_result=lambda body: None,
                                       workdir="/unused", claim_current=lambda: True)
            self.assertEqual(outcome["status"], "reused")
            execute.assert_not_called()
            self.assertEqual(fixture.candidate()["state"], "finalize-pending")
            candidate = {**fixture.candidate(), "attempts": {"review": 50, "repair": 0}}
            material = {"p": {"availability": "available", "findings": [{"severity": "material"}]}}
            gate.complete_review(ROOT, "o/r", candidate, material, HEAD)
            self.assertEqual(fixture.candidate()["state"], "repair-pending")
            candidate = {**fixture.candidate(), "attempts": {"repair": 2}}
            gate.complete_review(ROOT, "o/r", candidate, material, HEAD)
            self.assertEqual(fixture.candidate()["state"], "blocked-escalation")

    def test_handoff_admission_is_confirmed_and_idempotently_publishes_job(self):
        with QueueFixture(ROOT, HEAD) as fixture, ExitStack() as stack:
            stack.enter_context(mock.patch.object(queue, "_repo", return_value="o/r"))
            stack.enter_context(mock.patch.object(queue, "_ensure_labels"))
            stack.enter_context(mock.patch.object(queue, "_label"))
            stack.enter_context(mock.patch.object(queue, "_main", return_value=HEAD))
            original_pr = queue._pr.side_effect
            queue._pr.side_effect = lambda *a: {**original_pr(*a), "base": {"ref": "main"}}
            handoff = {"task_identity": IDENTITY, "gates": {}}
            queue.admit(ROOT, 7, HEAD, handoff=handoff)
            self.assertEqual(fixture.candidate()["state"], "review-pending")
            self.assertEqual(workers.build_job(fixture.candidate())["kind"], "review")
            count = len(fixture.comments)
            queue.admit(ROOT, 7, HEAD, handoff=handoff)
            self.assertEqual(len(fixture.comments), count)

    def test_finish_releases_claim_only_after_successful_publication(self):
        publication = load_platform_module("project_publish", SCRIPTS / "project_publish.py")
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(finish, "require_no_orphan_active_openspec"))
            stack.enter_context(mock.patch.object(managed, "resolve_canonical_provenance", return_value=mock.Mock(path=ROOT)))
            stack.enter_context(mock.patch.object(gate, "handoff_gates", return_value=(IDENTITY, {})))
            stack.enter_context(mock.patch.object(finish, "observe_friction_checkpoint_blocker", return_value=None))
            stack.enter_context(mock.patch.object(finish, "clean", return_value=True))
            stack.enter_context(mock.patch.object(finish, "enforce_scope_gate"))
            stack.enter_context(mock.patch.object(finish, "observe_private_reference_blocker", return_value=None))
            publish = stack.enter_context(mock.patch.object(publication, "publish_pr", return_value=0))
            release = stack.enter_context(mock.patch.object(finish, "finish_board"))
            config = {"pr_merge_mode": "auto"}
            self.assertEqual(finish.finish_developer_handoff(ROOT, ROOT, config, "agent/example", None, None), 0)
            self.assertTrue(publish.call_args.kwargs["developer_handoff"])
            release.assert_called_once()
            release.reset_mock()
            publish.side_effect = RuntimeError("admission unavailable")
            with self.assertRaises(RuntimeError):
                finish.finish_developer_handoff(ROOT, ROOT, config, "agent/example", None, None)
            release.assert_not_called()


class ProviderSwitchTests(unittest.TestCase):
    MATERIAL = {"s": {"availability": "available", "findings": [{"id": "f1", "severity": "material", "summary": "bug"}]}}

    def repair_pending(self, fixture, providers=("codex",)):
        gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=list(providers))
        queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
        gate.complete_review(ROOT, "o/r", fixture.candidate(), self.MATERIAL, HEAD)
        self.assertEqual(fixture.candidate()["state"], "repair-pending")

    def switch(self, **kwargs):
        return gate.reoffer(ROOT, "o/r", 7, action=kwargs.pop("action", "switch-provider"),
                            providers=kwargs.pop("providers", ["claude"]), reason=kwargs.pop("reason", "codex limit"))

    def test_switching_an_open_review_keeps_state_attempts_and_records_provenance(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["codex"])
            before = fixture.candidate()
            old_job = workers.build_job(before)
            published = len(fixture.comments)
            result = self.switch()
            after = fixture.candidate()
            job = workers.build_job(after)
            self.assertTrue(result["changed"])
            self.assertEqual((after["state"], job["providers"], job["attempt"]), ("review-pending", ["claude"], old_job["attempt"]))
            spent = lambda attempts: {k: v for k, v in attempts.items() if k != "reoffers" and not k.endswith("-unavailable")}
            self.assertEqual(spent(after["attempts"]), spent(before["attempts"]))
            self.assertEqual(job["reoffer"]["from"], ["codex"])
            self.assertEqual((job["reoffer"]["to"], job["reoffer"]["reason"]), (["claude"], "codex limit"))
            self.assertNotEqual(workers.job_id(job), workers.job_id(old_job))
            self.assertEqual(after["task_identity"], before["task_identity"])
            # The earlier record stays in the append-only history and a repeat changes nothing.
            self.assertEqual(len(fixture.comments), published + 1)
            self.assertFalse(self.switch()["changed"])
            self.assertEqual(len(fixture.comments), published + 1)

    def test_switching_a_repair_keeps_findings_gates_and_the_repair_round(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            self.repair_pending(fixture)
            before = fixture.candidate()
            self.switch(providers=["claude", "codex"])
            after = fixture.candidate()
            self.assertEqual((after["state"], after["attempts"]["repair"]), ("repair-pending", before["attempts"]["repair"]))
            self.assertEqual(after["gates"], before["gates"])
            self.assertEqual(workers.build_job(after)["providers"], ["claude", "codex"])
            self.assertEqual(gate.repair_brief(after)["findings"][0]["id"], "f1")
            # Later review of the repaired content follows the new providers.
            self.assertEqual(workers.build_job(after)["kind"], "repair")

    def test_new_providers_follow_the_candidate_into_later_retries(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["codex"])
            self.switch()
            queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
            gate.complete_review(ROOT, "o/r", fixture.candidate(), {"s": {"availability": "unavailable"}}, HEAD)
            self.assertEqual(workers.build_job(fixture.candidate())["providers"], ["claude"])

    def test_switch_refuses_live_claim_wrong_state_and_bad_providers(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["codex"])
            job = workers.build_job(fixture.candidate())
            fixture.comments.append({"id": 90, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "busy", "2099-01-01T00:00:00Z")})
            with self.assertRaisesRegex(queue.QueueError, "claimed by busy"):
                self.switch()
            fixture.comments[-1]["body"] = workers.claim_body(job, "busy", "2000-01-01T00:00:00Z")
            for providers in ([], ["gemini"], ["claude", "claude"]):
                with self.assertRaisesRegex(queue.QueueError, "providers must be"):
                    self.switch(providers=providers)
            with self.assertRaisesRegex(queue.QueueError, "reason"):
                self.switch(reason=" ")
            queue._transition(ROOT, "o/r", 7, "ready", HEAD, task_identity=IDENTITY)
            with self.assertRaisesRegex(queue.QueueError, "unfinished review or repair"):
                self.switch()

    def test_unavailable_repair_runtime_is_retryable_names_the_cause_and_spends_no_round(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            self.repair_pending(fixture)
            rounds = fixture.candidate()["attempts"]["repair"]
            for expected_streak in (1, 2):
                job = workers.build_job(fixture.candidate())
                fixture.comments.append({"id": 100 + expected_streak, "author_association": "OWNER",
                                         "body": workers.claim_body(job, "w", "2099-01-01T00:00:00Z")})
                with mock.patch.object(workers, "execute_job", return_value={
                        "status": "unavailable", "outcome": "unavailable: codex usage limit reached"}):
                    outcome = gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture",
                                               branch="agent/example", allowed_paths=["src.py"], llm_command=["writer"],
                                               current_head=lambda: HEAD, post_result=lambda body: None,
                                               workdir="/unused", claim_current=lambda: True)
                self.assertEqual(outcome["status"], "unavailable")
                candidate = fixture.candidate()
                self.assertEqual(candidate["state"], "blocked-retryable")
                self.assertEqual(candidate["attempts"]["repair"], rounds)
                self.assertEqual(candidate["attempts"]["repair-unavailable"], expected_streak)
                self.assertEqual(candidate["gates"]["repair"]["evidence"]["cause"], "provider-unavailable")
                self.assertIn("usage limit", candidate["gates"]["repair"]["evidence"]["limitation"])
                self.assertEqual(queue.retry_job_kind(candidate), "repair")
                retry = workers.build_job(candidate)
                self.assertEqual((retry["kind"], retry["attempt"]), ("repair", rounds))
                self.assertNotEqual(workers.job_id(retry), workers.job_id(job))
                self.assertEqual(gate.repair_brief(candidate)["findings"][0]["id"], "f1")
            job = workers.build_job(fixture.candidate())
            with mock.patch.object(workers, "execute_job", return_value={
                    "status": "unavailable", "outcome": "unavailable: still limited"}):
                gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture", branch="agent/example",
                                 allowed_paths=["src.py"], llm_command=["writer"], current_head=lambda: HEAD,
                                 post_result=lambda body: None, workdir="/unused", claim_current=lambda: True)
            exhausted = fixture.candidate()
            self.assertEqual((exhausted["state"], exhausted["attempts"]["repair"]), ("blocked-retryable", rounds))
            self.assertIsNone(workers.build_job(exhausted))  # bounded: no automatic job, never escalated
            self.assertEqual(queue.retry_job_kind(exhausted), "repair")
            # The operator resumes the same round, restoring the automatic retry budget.
            self.switch(action="resume", providers=["claude"])
            resumed = fixture.candidate()
            self.assertEqual((resumed["state"], resumed["attempts"]["repair"], resumed["attempts"]["repair-unavailable"]),
                             ("repair-pending", rounds, 0))

    def test_successful_repair_resets_the_unavailable_streak(self):
        new_head = "c" * 40
        with QueueFixture(ROOT, HEAD) as fixture:
            self.repair_pending(fixture)
            queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity=IDENTITY, set_attempts={"repair-unavailable": 2})
            job = workers.build_job(fixture.candidate())
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "w", "2099-01-01T00:00:00Z")})
            def push(*args, **kwargs):
                fixture.head = new_head
                return {"status": "pushed", "pushed_head": new_head}
            with mock.patch.object(workers, "execute_job", side_effect=push), mock.patch.object(workers, "_git"), \
                    mock.patch.object(gate, "refresh_identity", return_value=IDENTITY):
                gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture", branch="agent/example",
                                 allowed_paths=["src.py"], llm_command=["writer"], current_head=lambda: new_head,
                                 post_result=lambda body: None, workdir="/unused", claim_current=lambda: True)
            after = fixture.candidate()
            self.assertEqual((after["state"], after["attempts"]["repair-unavailable"]), ("review-pending", 0))

    def test_failed_writer_with_usable_runtime_still_escalates_and_records_providers(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            self.repair_pending(fixture, providers=("codex",))
            job = workers.build_job(fixture.candidate())
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "w", "2099-01-01T00:00:00Z")})
            with mock.patch.object(workers, "execute_job", return_value={"status": "failed", "outcome": "failed: llm exited 1"}):
                gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture", branch="agent/example",
                                 allowed_paths=["src.py"], llm_command=["writer"], current_head=lambda: HEAD,
                                 post_result=lambda body: None, workdir="/unused", claim_current=lambda: True)
            escalated = fixture.candidate()
            self.assertEqual(escalated["state"], "blocked-escalation")
            self.assertEqual(escalated["red_gate"]["providers"], ["codex"])
            # Documented exit after a human decision: same round, new provider, findings restored.
            rounds = escalated["attempts"]["repair"]
            self.switch(action="resume", providers=["claude"], reason="codex limit reset not before tomorrow")
            resumed = fixture.candidate()
            self.assertEqual((resumed["state"], resumed["attempts"]["repair"]), ("repair-pending", rounds))
            self.assertEqual(gate.repair_brief(resumed)["findings"][0]["id"], "f1")
            self.assertEqual(workers.build_job(resumed)["reoffer"]["action"], "resume")
            # Resume keeps the recorded providers when none is given.
            self.assertEqual(workers.build_job(resumed)["providers"], ["claude"])

    def test_resume_without_recorded_providers_needs_an_explicit_one_and_refuses_finding_level_escalation(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            self.repair_pending(fixture)
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity=IDENTITY,
                              red_gate={"name": "repair", "evidence": {"status": "failed", "outcome": "failed: llm exited 1"}})
            with self.assertRaisesRegex(queue.QueueError, "pass --provider"):
                gate.reoffer(ROOT, "o/r", 7, action="resume", providers=None, reason="retry")
            with self.assertRaisesRegex(queue.QueueError, "use switch-provider|applies only"):
                self.switch()  # switch-provider does not decide an escalation
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity=IDENTITY,
                              red_gate={"name": "review", "evidence": self.MATERIAL})
            with self.assertRaisesRegex(queue.QueueError, "finding-level reason \\(review\\).*push a fix"):
                self.switch(action="resume")
            for evidence in ("rounds exhausted", {"status": "proposed-rejection"}):
                queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity=IDENTITY,
                                  red_gate={"name": "repair", "evidence": evidence})
                with self.assertRaisesRegex(queue.QueueError, "push a fix, record a disposition"):
                    self.switch(action="resume")

    def test_filtering_worker_reviews_on_the_ready_subset_in_job_order(self):
        with QueueFixture(ROOT, HEAD) as fixture, tempfile.TemporaryDirectory() as workdir:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["claude", "codex"])
            job = workers.build_job(fixture.candidate())
            fixture.comments.append({"id": 100, "author_association": "OWNER",
                                     "body": workers.claim_body(job, "w", "2099-01-01T00:00:00Z")})
            seen = []
            def execute(job_, **kwargs):
                kwargs["review_handler"](Path(workdir))
                return {"status": "discarded"}
            with mock.patch.object(workers, "execute_job", side_effect=execute), \
                    mock.patch.object(gate, "execute_review", side_effect=lambda *a, **k: seen.append(k["review_config"]) or {"status": "discarded"}):
                gate.run_claimed(ROOT, "o/r", fixture.candidate(), job, source_repo="fixture", branch="agent/example",
                                 allowed_paths=[], llm_command=None, current_head=lambda: HEAD,
                                 post_result=lambda body: None, workdir=workdir, claim_current=lambda: True,
                                 review_ready=frozenset({"codex"}))
            self.assertEqual(seen[0]["providers"], ["codex"])

    def test_resume_review_streak_exhaustion_and_pending_state_rules(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            gate.offer(ROOT, "o/r", 7, HEAD, IDENTITY, "review", providers=["codex"])
            with self.assertRaisesRegex(queue.QueueError, "use switch-provider"):
                self.switch(action="resume")
            unavailable = {"s": {"availability": "unavailable", "limitation": "codex login expired"}}
            for _ in range(3):
                queue._transition(ROOT, "o/r", 7, "reviewing", HEAD, task_identity=IDENTITY)
                gate.complete_review(ROOT, "o/r", fixture.candidate(), unavailable, HEAD)
            exhausted = fixture.candidate()
            self.assertEqual(exhausted["state"], "blocked-retryable")
            self.assertEqual(exhausted["red_gate"]["cause"], "provider-unavailable")
            self.assertIn("login expired", exhausted["red_gate"]["limitation"])
            self.assertIsNone(workers.build_job(exhausted))
            self.switch(action="resume", providers=["claude"])
            resumed = fixture.candidate()
            self.assertEqual((resumed["state"], resumed["attempts"]["review-unavailable"]), ("review-pending", 0))
            self.assertEqual(workers.build_job(resumed)["providers"], ["claude"])


class ProviderSwitchCommandTests(unittest.TestCase):
    def test_cli_switch_and_resume_call_the_gate_with_the_operator_reason(self):
        for command, extra, provider_required in (("switch-provider", ["--provider", "claude", "--provider", "codex"], True),
                                                  ("resume", [], False)):
            with self.subTest(command=command), mock.patch.object(queue, "current_worktree_root", return_value=ROOT), \
                    mock.patch.object(queue, "_repo", return_value="o/r"), \
                    mock.patch.object(gate, "reoffer", return_value={"state": "repair-pending", "changed": True}) as reoffer, \
                    mock.patch.object(sys, "argv", ["publication_queue", command, "--pr", "7", "--reason", "why", *extra]):
                self.assertEqual(queue.main(), 0)
                reoffer.assert_called_once()
                self.assertEqual(reoffer.call_args.kwargs["reason"], "why")
                self.assertEqual(reoffer.call_args.kwargs["providers"], ["claude", "codex"] if provider_required else None)
        with mock.patch.object(queue, "current_worktree_root", return_value=ROOT), \
                mock.patch.object(sys, "argv", ["publication_queue", "switch-provider", "--pr", "7", "--reason", "why"]), \
                self.assertRaises(SystemExit):
            queue.main()  # a provider is required to switch


class ProviderTests(unittest.TestCase):
    def test_ordered_fallback_and_single_provider_never_substituted(self):
        def probe(root, *, config, **kwargs):
            provider = config["provider"]
            return {"ready": provider == "claude", "provider": provider, "model": provider + "-model",
                    "binary": provider, "provider_source": "configured", "limitation": "codex unavailable"}
        with mock.patch.object(reviewer, "_preflight_one", side_effect=probe) as launch:
            result = reviewer.preflight(ROOT, config={"providers": ["codex", "claude"]})
            self.assertTrue(result["ready"])
            self.assertEqual(result["requested_provider"], "codex")
            self.assertEqual(result["executed_provider"], "claude")
            self.assertEqual(result["fallback_reason"], "codex unavailable")
            self.assertEqual([call.kwargs["config"]["provider"] for call in launch.call_args_list], ["codex", "claude"])
            launch.reset_mock()
            result = reviewer.preflight(ROOT, config={"provider": "codex"})
            self.assertFalse(result["ready"])
            self.assertIsNone(result["executed_provider"])
            launch.assert_called_once()

    def test_invalid_lists_and_all_unavailable_fail_closed(self):
        with mock.patch.object(reviewer, "_preflight_one") as launch:
            for providers in ([], "codex", ["unknown"], ["codex", "codex"]):
                self.assertFalse(reviewer.preflight(ROOT, config={"providers": providers})["ready"])
            launch.assert_not_called()
            launch.return_value = {"ready": False, "provider": "codex", "model": "model", "binary": None,
                                   "provider_source": "configured", "limitation": "runtime unavailable"}
            result = reviewer.preflight(ROOT, config={"providers": ["codex", "claude"]})
            self.assertFalse(result["ready"])
            self.assertEqual(launch.call_count, 2)

    def test_mutation_does_not_launch_fallback(self):
        with mock.patch.object(reviewer, "_preflight_one", return_value={
                "ready": False, "provider": "codex", "limitation": "probe mutated workspace"}) as launch:
            self.assertFalse(reviewer.preflight(ROOT, config={"providers": ["codex", "claude"]})["ready"])
            launch.assert_called_once()


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        git(self.root, "init", "-qb", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@localhost")
        (self.root / ".dev-platform.toml").write_text('[independent_review]\nenabled = true\nprovider = "codex"\n')
        (self.root / "src.py").write_text("value = 0\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.root, "checkout", "-qb", "agent/example")
        change = self.root / "openspec/changes/example"
        change.mkdir(parents=True)
        (change / "proposal.md").write_text("# Fix value\n")
        (change / "tasks.md").write_text("- [x] implement\n")
        (change / "design.md").write_text("Set value correctly\n")
        (change / ".managed-task.json").write_text('{"change":"example", "source_issue":"owner/backlog#1"}')
        (self.root / "src.py").write_text("value = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "candidate")
        self.remote = Path(self.tmp.name) / "remote.git"
        git(self.root, "clone", "--bare", str(self.root), str(self.remote))
        git(self.root, "remote", "add", "origin", str(self.remote))

    def remote_head(self):
        return git(self.remote, "rev-parse", "refs/heads/agent/example")

    def launcher(self, findings):
        calls = []
        def launch(argv, cwd, timeout):
            if argv[-1] == reviewer.PREFLIGHT_PROMPT:
                return reviewer.LaunchResult(0, '{"type":"thread.started","thread_id":"probe"}')
            calls.append(argv)
            Path(argv[argv.index("--output-last-message") + 1]).write_text(json.dumps({"findings": findings}))
            return reviewer.LaunchResult(0, json.dumps({"type": "thread.started", "thread_id": str(len(calls))}))
        return launch, calls

    def test_real_review_push_recovers_after_result_publication_failure(self):
        identity = gate.task_identity(self.root, "example")
        with QueueFixture(self.root, self.remote_head()) as fixture, \
                mock.patch.object(reviewer, "resolve_binary", return_value=("fake-codex", None)):
            gate.offer(self.root, "o/r", 7, fixture.head, identity, "review")
            job = workers.build_job(fixture.candidate())
            launch, _ = self.launcher([])
            def post(body):
                receipt = json.loads(body[len(workers.RESULT_PREFIX):])
                if receipt["outcome"] != "validated-push":
                    raise RuntimeError("result publication interrupted")
                fixture.comments.append({"id": len(fixture.comments) + 1,
                                         "author_association": "OWNER", "body": body})
            with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
                with self.assertRaisesRegex(RuntimeError, "publication interrupted"):
                    gate.run_claimed(self.root, "o/r", fixture.candidate(), job,
                                     source_repo=self.remote.as_uri(), branch="agent/example",
                                     allowed_paths=[], llm_command=None, current_head=self.remote_head,
                                     post_result=post, workdir=workdir, launcher=launch, claim_current=lambda: True)
            fixture.head = self.remote_head()
            self.assertNotEqual(fixture.head, job["head"])
            recovery = workers.build_job(fixture.candidate())
            self.assertEqual(recovery["kind"], "review")
            self.assertEqual(recovery["head"], fixture.head)
            self.assertEqual(recovery["task_identity"], identity)
            self.assertTrue(workers.is_claimable(recovery, fixture.comments))

    def test_worker_route_is_explicit_without_routing_file_in_clone(self):
        identity = gate.task_identity(self.root, "example")
        job = {"kind": "review", "number": 7, "head": self.remote_head(), "attempt": 1,
               "task_identity": identity}
        launch, calls = self.launcher([])
        with mock.patch.object(reviewer, "resolve_binary", return_value=("fake-codex", None)):
            with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
                checkout = workers.prepare_checkout(self.remote.as_uri(), workdir, "review", job["head"])
                self.assertFalse((checkout / ".claude/model-routing").exists())
                outcome = gate.execute_review(checkout, job, source_repo=self.remote.as_uri(),
                                              branch="agent/example", current_head=self.remote_head,
                                              runner=subprocess.run, launcher=launch, review_config={"provider": "codex"})
                self.assertEqual(outcome["status"], "reviewed")
                self.assertEqual(len(calls), 2)
            job["head"] = self.remote_head()
            with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
                checkout = workers.prepare_checkout(self.remote.as_uri(), workdir, "review", job["head"])
                outcome = gate.execute_review(checkout, job, source_repo=self.remote.as_uri(),
                                              branch="agent/example", current_head=self.remote_head,
                                              runner=subprocess.run, launcher=launch,
                                              review_config={"provider": "unresolved-worker-route"})
                self.assertTrue(all(r["availability"] == "unavailable" for r in outcome["reports"].values()))
                self.assertTrue(all("unresolved-worker-route" in r["limitation"] for r in outcome["reports"].values()))

    def test_developer_review_repair_review_and_evidence_reuse(self):
        identity = gate.task_identity(self.root, "example")
        with QueueFixture(self.root, self.remote_head()) as fixture, \
                mock.patch.object(reviewer, "resolve_binary", return_value=("fake-codex", None)):
            # Handoff uses real coordinator transition and publishes the shared review job.
            gate.offer(self.root, "o/r", 7, fixture.head, identity, "review")
            launch, calls = self.launcher([{"id": "value", "severity": "material", "summary": "wrong value", "evidence": "src.py:1"}])
            def run(kind, launcher=None, command=None):
                candidate = fixture.candidate()
                job = workers.build_job(candidate)
                self.assertEqual(job["kind"], kind)
                with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
                    outcome = gate.run_claimed(
                        self.root, "o/r", candidate, job, source_repo=self.remote.as_uri(), branch="agent/example",
                        allowed_paths=["src.py"], llm_command=command,
                        current_head=self.remote_head, post_result=lambda body: None,
                        workdir=workdir, launcher=launcher, claim_current=lambda: True)
                fixture.head = self.remote_head()
                return outcome
            # Model commands are fake; Git I/O is local to the fixture.
            # GitHub PR observation sees the real locally pushed head immediately.
            with mock.patch.object(queue, "_pr", side_effect=lambda *a: {
                    "number": 7, "state": "open", "head": {"sha": self.remote_head(), "ref": "agent/example"}, "labels": []}):
                outcome = run("review", launch)
                self.assertEqual(outcome["status"], "reviewed")
                self.assertEqual(fixture.candidate()["state"], "repair-pending")
                self.assertEqual(len(calls), 2)
                review_gate = fixture.candidate()["gates"]["review"]
                self.assertEqual(review_gate["identity"], identity)
                # Repair commits are produced by a fake writer subprocess in its disposable checkout.
                code = ("from pathlib import Path; import subprocess; Path('src.py').write_text('value = 2\\n'); "
                        "subprocess.run(['git','add','src.py'],check=True,stdin=subprocess.DEVNULL); "
                        "subprocess.run(['git','-c','user.name=Repair','-c','user.email=repair@localhost',"
                        "'commit','-m','Repair value'],check=True,stdin=subprocess.DEVNULL)")
                outcome = run("repair", command=[sys.executable, "-c", code])
                self.assertEqual(outcome["status"], "pushed")
                self.assertEqual(fixture.candidate()["state"], "review-pending")
                self.assertNotEqual(fixture.candidate()["task_identity"], identity)
                self.assertNotIn("review", fixture.candidate()["gates"])
                launch, calls = self.launcher([])
                outcome = run("review", launch)
                self.assertEqual(outcome["status"], "reviewed")
                self.assertEqual(fixture.candidate()["state"], "finalize-pending")
                proof = fixture.candidate()["task_identity"]
                passed = fixture.candidate()["gates"]["review"]
                self.assertTrue(gate.reusable(self.root, passed, proof))
                self.assertEqual(fixture.candidate()["attempts"], {"review": 2, "repair": 1, "review-unavailable": 0})

    def test_finalized_candidate_returning_to_review_is_reviewed_against_its_archive(self):
        # Integration repair changes the content of an already archived change: review must still run.
        root = self.root
        archive = root / "openspec/changes/archive"
        archive.mkdir(parents=True)
        git(root, "mv", "openspec/changes/example", str(archive.relative_to(root) / "2026-01-01-example"))
        git(root, "commit", "-qm", "archive example")
        git(root, "push", "-q", "origin", "HEAD:refs/heads/agent/example")
        identity = gate.task_identity(root, "example")
        job = {"kind": "review", "number": 7, "head": self.remote_head(), "attempt": 1, "task_identity": identity}
        launch, calls = self.launcher([])
        with mock.patch.object(reviewer, "resolve_binary", return_value=("fake-codex", None)), \
                tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            checkout = workers.prepare_checkout(self.remote.as_uri(), workdir, "review", job["head"])
            self.assertFalse((checkout / "openspec/changes/example").exists())
            outcome = gate.execute_review(checkout, job, source_repo=self.remote.as_uri(), branch="agent/example",
                                          current_head=self.remote_head, runner=subprocess.run, launcher=launch,
                                          review_config={"provider": "codex"})
            self.assertEqual(outcome["status"], "reviewed")
            self.assertEqual(len(calls), 2)
            tree = git(self.remote, "ls-tree", "-r", "--name-only", self.remote_head())
            self.assertIn("openspec/changes/archive/2026-01-01-example/independent-reviews/", tree + "/")
            self.assertNotIn("openspec/changes/example/", tree)

    def test_selected_check_binding_survives_evidence_commit_but_not_source_edit(self):
        change = self.root / "openspec/changes/example"
        checkout = managed.ManagedCheckoutIdentity("owner/backlog#1", "example", self.root, "agent/example",
                                                   git(self.root, "rev-parse", "HEAD"))
        path = change / "automated-checks.json"
        checks.write_evidence(path, [{"name": "fixture"}], {"state": "ready", "command_count": 1},
                              [{"outcome": "success"}], "success", checkout)
        gate_proof = json.loads(path.read_text())["gate_task_content"]
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "record checks")
        current = managed.ManagedCheckoutIdentity("owner/backlog#1", "example", self.root, "agent/example",
                                                  git(self.root, "rev-parse", "HEAD"))
        self.assertTrue(openspec.evidence_matches_checkout(change, self.root, current, checkout.evidence_payload()))
        self.assertTrue(identity_module.equivalent_proofs(self.root, gate_proof, gate.task_identity(self.root, "example")["task_content"]))
        (self.root / "src.py").write_text("value = 3\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "change source")
        current = managed.ManagedCheckoutIdentity("owner/backlog#1", "example", self.root, "agent/example",
                                                  git(self.root, "rev-parse", "HEAD"))
        self.assertFalse(openspec.evidence_matches_checkout(change, self.root, current, checkout.evidence_payload()))


if __name__ == "__main__":
    unittest.main()
