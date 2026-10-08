"""Autonomous integration contour: integration repair, non-blocking queue, friction attribution, post-merge jobs."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("candidate_lifecycle", SCRIPTS / "candidate_lifecycle.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
contour = load_platform_module("integration_contour", SCRIPTS / "integration_contour.py")
friction = load_platform_module("agent_friction", SCRIPTS / "agent_friction.py")
retrospective = load_platform_module("requirement_retrospective", SCRIPTS / "requirement_retrospective.py")

from test_pr_review_gate import IDENTITY, QueueFixture, git  # noqa: E402
from test_post_review_finalization import Remote, RemoteFixture  # noqa: E402

HEAD, BASE, MAIN = "a" * 40, "b" * 40, "c" * 40
REQUIREMENT = "acme/backlog#7"
CHILDREN = ["acme/backlog#8", "acme/backlog#9"]


class Multi:
    """GitHub I/O for several PRs; real transitions, trust and job records."""

    def __init__(self, heads: dict[int, str]):
        self.heads, self.comments, self.merged = dict(heads), {n: [] for n in heads}, set()
        self.stack = ExitStack()

    def pr(self, _root, _repo, number):
        return {"number": number, "state": "closed" if number in self.merged else "open", "merged": number in self.merged,
                "head": {"sha": self.heads[number], "ref": f"agent/br-7-t{number}-task"}, "labels": []}

    def post(self, _root, *args, data=None, **kwargs):
        number = int(re.search(r"issues/(\d+)/comments", " ".join(args)).group(1))
        self.comments[number].append({"id": len(self.comments[number]) + 1, "author_association": "OWNER",
                                      "body": data["body"]})

    def __enter__(self):
        for name, value in (("_pr", self.pr), ("_comments", lambda r, repo, n: list(self.comments[n]))):
            self.stack.enter_context(mock.patch.object(queue, name, side_effect=value))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        for name in ("_project_lifecycle_label", "_label"):
            self.stack.enter_context(mock.patch.object(queue, name))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=self.post))
        self.stack.enter_context(mock.patch.object(queue, "_repo", return_value="o/r"))
        return self

    def __exit__(self, *args):
        self.stack.close()

    def candidate(self, number):
        return queue._derive(ROOT, self.pr(ROOT, "o/r", number), self.comments[number])

    def ready(self, number, *, identity=None):
        queue._transition(ROOT, "o/r", number, "ready", self.heads[number],
                          task_identity=identity or {"branch": f"agent/br-7-t{number}-task", "head": self.heads[number]},
                          inherit_identity=False)

    def run_worker(self, *, prepare=None, checks="passed"):
        def merge(command, **kwargs):
            if command[:3] == ["gh", "pr", "merge"]:
                self.merged.add(int(command[3]))
            return subprocess.CompletedProcess(command, 0, "", "")

        order = [(n, n, {"branch": f"agent/br-7-t{n}-task"}) for n in sorted(self.heads)]
        with mock.patch.object(queue, "_queued", return_value=order), \
                mock.patch.object(queue, "_require_finalized"), \
                mock.patch.object(queue, "_prepare", side_effect=prepare or (lambda r, repo, n, a, pr: (self.heads[n], BASE))), \
                mock.patch.object(queue, "_main", return_value=BASE), \
                mock.patch.object(queue, "required_check_state_for_ref",
                                  return_value=SimpleNamespace(kind=checks, detail="validate")), \
                mock.patch.object(queue.subprocess, "run", side_effect=merge):
            return queue.worker(ROOT)


def setUpModule() -> None:
    # Local-log scenarios: durable coordinator evidence (GitHub) is covered by the
    # coordinator-operations tests, so these scenarios never reach GitHub.
    for module in {friction, sys.modules["agent_friction"]}:
        patcher = mock.patch.object(module, "read_durable_events", return_value=[])
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


def head_for(number: int) -> str:
    return f"{number:x}" * 40


class IntegrationScenarioTests(unittest.TestCase):
    def test_overlapping_but_clean_candidate_proceeds_to_checks_on_the_merged_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Remote(Path(tmp))
            root = repo.root
            git(root, "checkout", "-qb", "agent/clean")
            (root / "src.py").write_text("value = 0\nline = 1\n")
            git(root, "commit", "-qam", "candidate")
            candidate = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "-q", "main")
            (root / "src.py").write_text("main = 1\nvalue = 0\n")  # same path, different region
            git(root, "commit", "-qam", "main moves")
            git(root, "push", "-q", "origin", "HEAD:main")
            git(root, "fetch", "-q", "origin")
            main = git(root, "rev-parse", "origin/main")
            self.assertEqual(queue.merge_conflicts(root, candidate, main), [])

    def test_real_conflict_is_detected_without_touching_the_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Remote(Path(tmp))
            root = repo.root
            git(root, "checkout", "-qb", "agent/clash")
            (root / "src.py").write_text("value = 1\n")
            git(root, "commit", "-qam", "candidate")
            candidate = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "-q", "main")
            (root / "src.py").write_text("value = 2\n")
            git(root, "commit", "-qam", "main moves")
            git(root, "push", "-q", "origin", "HEAD:main")
            git(root, "fetch", "-q", "origin")
            self.assertEqual(queue.merge_conflicts(root, candidate, git(root, "rev-parse", "origin/main")), ["src.py"])

    def test_head_blocked_by_an_error_does_not_stop_the_next_ready_candidate(self):
        with Multi({7: head_for(7), 8: head_for(8)}) as multi:
            multi.ready(7), multi.ready(8)

            def prepare(root, repo, number, admission, pr):
                if number == 7:
                    raise queue.QueueError("branch protection refused the update")
                return multi.heads[number], BASE

            result = multi.run_worker(prepare=prepare)
            self.assertEqual((result["state"], result["number"]), ("merged", 8))
            self.assertEqual(multi.candidate(7)["state"], "blocked-escalation")
            self.assertTrue(any("#7" in item for item in result["skipped"]))

    def test_candidate_owned_by_other_work_is_skipped_for_the_next(self):
        with Multi({7: head_for(7), 8: head_for(8)}) as multi:
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", multi.heads[7], task_identity={"head": "x"},
                              inherit_identity=False, red_gate={"name": "review", "evidence": "rounds"})
            multi.ready(8)
            result = multi.run_worker()
            self.assertEqual((result["state"], result["number"]), ("merged", 8))

    def test_a_blocked_only_queue_still_reports_blocked(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            result = multi.run_worker(prepare=mock.Mock(side_effect=queue.QueueError("boom")))
            self.assertEqual(result["state"], "blocked")

    def test_merge_marks_the_candidate_for_post_merge_jobs(self):
        with Multi({8: head_for(8)}) as multi:
            multi.ready(8)
            self.assertEqual(multi.run_worker()["state"], "merged")
            merged = multi.candidate(8)
            self.assertEqual(merged["state"], "merged")
            self.assertEqual(workers.build_job(merged)["kind"], "retrospective")


class IntegrationRepairBoundTests(unittest.TestCase):
    def conflict(self, number=7):
        return mock.Mock(side_effect=queue.IntegrationRepairNeeded("merge of current main conflicts in: src.py"))

    def test_conflict_offers_one_bounded_job_and_reruns_are_idempotent(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            result = multi.run_worker(prepare=self.conflict())
            self.assertEqual(result["state"], "waiting")
            candidate = multi.candidate(7)
            self.assertEqual(candidate["state"], "integration-repair-pending")
            self.assertEqual(candidate["red_gate"]["name"], "integration")
            job = workers.build_job(candidate)
            self.assertEqual((job["kind"], job["attempt"]), ("integration-repair", 1))
            records = len(multi.comments[7])
            prepare = self.conflict()
            multi.run_worker(prepare=prepare)
            prepare.assert_not_called()  # owned by the repair job: skipped, not re-prepared
            self.assertEqual(len(multi.comments[7]), records)

    def test_interrupted_offer_is_completed_on_the_next_run(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "integration-repair-pending", multi.heads[7],
                              task_identity={"head": "x"}, set_attempts={"integration-repair": 1},
                              red_gate={"name": "integration", "identity": multi.heads[7], "evidence": "conflict"})
            self.assertIsNone(multi.candidate(7)["next_job"])
            multi.run_worker()
            self.assertEqual(workers.build_job(multi.candidate(7))["kind"], "integration-repair")

    def test_failing_integration_check_creates_a_repair_job_not_a_block(self):
        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            multi.run_worker(checks="failed")
            candidate = multi.candidate(7)
            self.assertEqual(candidate["state"], "integration-repair-pending")
            self.assertEqual(candidate["red_gate"]["name"], "required-checks")

    def test_bound_blocks_the_candidate_after_two_attempts_and_the_next_one_still_merges(self):
        def conflict_on_7(root, repo, number, admission, pr):
            if number == 7:
                raise queue.IntegrationRepairNeeded("conflict")
            return multi.heads[number], BASE

        with Multi({7: head_for(7)}) as multi:
            multi.ready(7)
            for attempt in (1, 2):
                multi.run_worker(prepare=conflict_on_7)
                self.assertEqual(multi.candidate(7)["attempts"]["integration-repair"], attempt)
                multi.ready(7)  # the repair finished without a content change: ready again
            multi.heads[8], multi.comments[8] = head_for(8), []
            multi.ready(8)
            result = multi.run_worker(prepare=conflict_on_7)
            self.assertEqual((result["state"], result["number"]), ("merged", 8))
            blocked = multi.candidate(7)
            self.assertEqual(blocked["state"], "blocked-escalation")
            self.assertIn("exhausted", blocked["red_gate"]["evidence"])


class RepairFixture(unittest.TestCase):
    """A real source repository whose candidate conflicts with main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Remote(Path(self.tmp.name))
        root = self.repo.root
        git(root, "checkout", "-qb", "agent/example")
        change = root / "openspec/changes/example"
        change.mkdir(parents=True)
        (change / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- y\n")
        (change / "tasks.md").write_text("- [x] implement\n")
        (change / ".managed-task.json").write_text('{"change":"example", "source_issue":"owner/backlog#1"}')
        (root / "src.py").write_text("value = 1\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "candidate")
        self.repo.push("agent/example")
        self.identity = gate.task_identity(root, "example")
        git(root, "checkout", "-q", "main")
        (root / "src.py").write_text("value = 2\n")
        git(root, "commit", "-qam", "main moves")
        git(root, "push", "-q", "origin", "HEAD:main")
        git(root, "fetch", "-q", "origin")
        git(root, "checkout", "-q", "agent/example")
        self.results = []

    def runner(self, resolve):
        def run(command, **kwargs):
            if command[0] == "git":
                return subprocess.run(command, **kwargs)
            resolve(Path(kwargs["cwd"]))
            return subprocess.CompletedProcess(command, 0, "", "")
        return run

    def offer(self, fixture, *, attempt=1):
        queue._transition(self.repo.root, "o/r", 7, "integration-repair-pending", fixture.head, task_identity=self.identity,
                          inherit_identity=False, set_attempts={"integration-repair": attempt},
                          red_gate={"name": "integration", "identity": fixture.head, "evidence": "conflict in src.py"})
        queue.publish_job(self.repo.root, "o/r", 7, "integration-repair", fixture.head,
                          task_identity=self.identity, attempt=attempt)

    def post(self, fixture):
        def post_result(body):
            fixture.comments.append({"id": len(fixture.comments) + 1, "author_association": "OWNER", "body": body})
            self.results.append(body)
        return post_result

    def repair(self, fixture, resolve, **options):
        candidate = fixture.candidate()
        job = workers.build_job(candidate)
        self.assertEqual(job["kind"], "integration-repair")
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            return contour.run_claimed_integration_repair(
                self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(), branch="agent/example",
                allowed_paths=options.pop("allowed_paths", []), llm_command=["writer"], current_head=self.repo.head,
                post_result=self.post(fixture), workdir=workdir, runner=self.runner(resolve),
                claim_current=options.pop("claim_current", lambda: True), worker="w", **options)


def resolve_value(checkout: Path) -> None:
    (checkout / "src.py").write_text("value = 12\n")


class IntegrationRepairTests(RepairFixture):
    def test_conflict_changing_task_content_returns_through_review_and_finalization(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, resolve_value)
            self.assertEqual(outcome["status"], "integrated")
            after = self.repo.head("agent/example")
            main = git(self.repo.remote, "rev-parse", "refs/heads/main")
            self.assertEqual(git(self.repo.remote, "rev-list", "--parents", "-n", "1", after).split()[1:], [before, main])
            self.assertEqual(git(self.repo.remote, "show", f"{after}:src.py"), "value = 12")
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "review-pending")
            self.assertEqual(workers.build_job(candidate)["kind"], "review")
            self.assertNotEqual(candidate["task_identity"]["task_content"]["digest"],
                                self.identity["task_content"]["digest"])
            self.assertNotIn("review", candidate["gates"])
            # The coordinator can prove the pushed head (update marker), so preparation will accept it.
            self.assertIn(after, [e.get("head") for e in queue._events(self.repo.root, "o/r", 7) if e.get("kind") == "update"])

    def test_out_of_scope_or_workflow_edits_are_refused_and_a_new_bounded_attempt_is_offered(self):
        def tamper(checkout: Path) -> None:
            (checkout / ".github/workflows").mkdir(parents=True)
            (checkout / ".github/workflows/ci.yml").write_text("on: push\n")
            (checkout / "src.py").write_text("value = 12\n")

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, tamper)
            self.assertEqual(outcome["status"], "failed")
            self.assertEqual(self.repo.head("agent/example"), before)
            job = workers.build_job(fixture.candidate())
            self.assertEqual((job["kind"], job["attempt"]), ("integration-repair", 2))

    def test_unresolved_conflicts_do_not_push_and_the_bound_blocks_after_two_attempts(self):
        with RemoteFixture(self.repo) as fixture, mock.patch.object(queue, "_label"):
            self.offer(fixture, attempt=2)
            before = self.repo.head("agent/example")
            outcome = self.repair(fixture, lambda checkout: None)
            self.assertEqual(outcome["status"], "blocked-escalation")
            self.assertEqual(self.repo.head("agent/example"), before)
            self.assertEqual(fixture.candidate()["state"], "blocked-escalation")

    def test_filters_and_textconv_planted_in_the_writer_checkout_never_execute(self):
        sentinel = Path(self.tmp.name) / "sentinel"

        def plant(checkout: Path) -> None:
            resolve_value(checkout)
            (checkout / ".gitattributes").write_text("* filter=evil diff=evil\n")
            for key in ("filter.evil.clean", "diff.evil.textconv"):
                subprocess.run(["git", "config", key, f"touch {sentinel} #"], cwd=checkout, check=True)

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            outcome = self.repair(fixture, plant, allowed_paths=[".gitattributes"])
            self.assertEqual(outcome["status"], "integrated")
            self.assertFalse(sentinel.exists())

    def test_lost_claim_prevents_the_push(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head("agent/example")
            calls = iter([True])
            outcome = self.repair(fixture, resolve_value, claim_current=lambda: next(calls, False))
            self.assertEqual(outcome["status"], "discarded")
            self.assertEqual(self.repo.head("agent/example"), before)

    def test_push_without_advancement_recovers_as_review_and_a_stale_second_run_is_discarded(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            candidate = fixture.candidate()
            with mock.patch.object(queue, "_comment", side_effect=RuntimeError("crash after push")):
                with self.assertRaisesRegex(RuntimeError, "crash after push"):
                    self.repair(fixture, resolve_value)
            self.assertNotEqual(self.repo.head("agent/example"), candidate["head"])
            recovered = fixture.candidate()
            self.assertEqual(recovered["state"], "review-pending")
            self.assertIn("recover validated", recovered["reason"])
            # The old job is no longer offered for the moved head.
            self.assertEqual(workers.build_job(recovered)["kind"], "review")
            self.assertEqual(self.repo.head("agent/example"), recovered["head"])

    def test_validated_unchanged_push_is_recovered_idempotently(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            old = fixture.candidate()
            job = workers.build_job(old)
            # A harness-pushed repair that left task content unchanged, interrupted before advancement.
            git(self.repo.root, "commit", "-q", "--allow-empty", "-m", "repair")
            self.repo.push("agent/example")
            fixture.comments.append({"id": 100, "author_association": "OWNER", "body": workers.result_body(
                job, "w", "validated-push", self.repo.head("agent/example"), task_identity=self.identity)})
            recovered = fixture.candidate()
            self.assertEqual((recovered["state"], recovered["red_gate"]), ("ready", None))
            pr = queue._pr(self.repo.root, "o/r", 7)
            self.assertTrue(contour.recover_integration_repair(self.repo.root, "o/r", 7, pr, list(fixture.comments)))
            self.assertEqual(fixture.candidate()["state"], "ready")
            count = len(fixture.comments)
            self.assertFalse(contour.recover_integration_repair(self.repo.root, "o/r", 7, pr, list(fixture.comments)))
            self.assertEqual(len(fixture.comments), count)

    def test_unchanged_identity_reuses_evidence_and_reruns_required_checks(self):
        with QueueFixture(ROOT, HEAD) as fixture:
            good = {"result": "passed", "identity": IDENTITY, "evidence": {}}
            queue._transition(ROOT, "o/r", 7, "integration-repair-pending", HEAD, task_identity=IDENTITY,
                              inherit_identity=False,
                              gates={"review": good, "required-checks": {**good, "evidence": "old"}})
            new_head = "d" * 40
            fixture.head = new_head
            state = contour.advance_after_repair(ROOT, "o/r", {**fixture.candidate(), "head": HEAD, "task_identity": IDENTITY,
                                                              "gates": {"review": good, "required-checks": good}},
                                                 new_head, IDENTITY, None)
            self.assertEqual(state, "ready")
            candidate = fixture.candidate()
            self.assertEqual(sorted(candidate["gates"]), ["review"])
            self.assertIsNone(candidate["red_gate"])

    def test_validation_refuses_results_that_skip_main_or_escape_scope(self):
        root = self.repo.root
        git(root, "fetch", "-q", "origin")
        main = git(root, "rev-parse", "origin/main")
        head = self.repo.head("agent/example")
        git(root, "checkout", "-q", "--detach", head)
        (root / "src.py").write_text("value = 12\n")
        git(root, "commit", "-qam", "fix without main")
        with self.assertRaisesRegex(workers.WorkerError, "integrate current main"):
            contour.validate_integration_result(root, head, git(root, "rev-parse", "HEAD"), main, ["src.py"])
        git(root, "checkout", "-q", "--detach", head)
        subprocess.run(["git", "merge", "--no-commit", "--no-ff", main], cwd=root, capture_output=True, stdin=subprocess.DEVNULL)
        (root / "src.py").write_text("value = 12\n")
        (root / "other.py").write_text("x = 1\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "merge")
        result = git(root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(workers.WorkerError, "outside candidate scope: other.py"):
            contour.validate_integration_result(root, head, result, main, ["src.py"])
        self.assertEqual(contour.validate_integration_result(root, head, result, main, ["src.py", "other.py"]),
                         ["other.py", "src.py"])


def merged_pr(head=HEAD):
    return {"number": 7, "state": "closed", "merged": True, "head": {"sha": head}}


def record(state, *, attempts=None, head=HEAD, identity=None):
    body = lifecycle.marker_body(lifecycle.build_handoff_record(
        number=7, state=state, head=head, task_identity=identity or {"branch": "agent/br-7-t8-task", "head": head},
        gates={}, red_gate=None, not_reverified=[], attempts=attempts or {}, next_job=None,
        at="2026-10-06T00:00:00+00:00"))
    return {"id": 1, "author_association": "OWNER", "body": body}


def receipt(job_kind, attempt, outcome, row_id, head=HEAD):
    job = {"number": 7, "kind": job_kind, "head": head, "attempt": attempt}
    return {"id": row_id, "author_association": "OWNER", "body": workers.result_body(job, "w", outcome)}


class PostMergeDerivationTests(unittest.TestCase):
    def derive(self, *rows, flagged=True):
        base = record("merged", attempts={"post-merge": 1} if flagged else {})
        return lifecycle.derive_candidate(merged_pr(), [base, *rows])

    def test_chain_is_retrospective_then_terminal_then_cleanup_then_done(self):
        self.assertEqual(self.derive()["next_job"]["kind"], "retrospective")
        rows = [receipt("retrospective", 0, "task-recorded", 2)]
        self.assertEqual(self.derive(*rows)["next_job"]["kind"], "terminal-reconciliation")
        rows.append(receipt("terminal-reconciliation", 0, "requirement-reconciled", 3))
        self.assertEqual(self.derive(*rows)["next_job"]["kind"], "cleanup")
        rows.append(receipt("cleanup", 0, "cleaned", 4))
        self.assertIsNone(self.derive(*rows)["next_job"])

    def test_candidate_not_merged_by_this_contour_offers_nothing(self):
        self.assertIsNone(self.derive(flagged=False)["next_job"])

    def test_failed_attempt_retries_a_new_attempt_and_exhaustion_stops_with_a_reason(self):
        rows = [receipt("retrospective", 0, "failed: network", 2)]
        job = self.derive(*rows)["next_job"]
        self.assertEqual((job["kind"], job["attempt"]), ("retrospective", 1))
        rows += [receipt("retrospective", 1, "blocked: ambiguous", 3), receipt("retrospective", 2, "failed: x", 4)]
        exhausted = self.derive(*rows)
        self.assertIsNone(exhausted["next_job"])
        self.assertIn("exhausted", exhausted["reason"])

    def test_derivation_is_pure_so_an_interrupted_run_is_offered_again(self):
        self.assertEqual(self.derive()["next_job"], self.derive()["next_job"])
        # A validated-push or discarded receipt completes nothing.
        rows = [receipt("retrospective", 0, "discarded: head moved", 2)]
        self.assertEqual(self.derive(*rows)["next_job"]["attempt"], 0)

    def test_work_next_claims_a_post_merge_job_of_a_merged_candidate(self):
        comments = [record("merged", attempts={"post-merge": 1})]
        posted = []
        result = workers.work_next(
            frozenset({"retrospective"}), list_prs=lambda: [merged_pr()], comments_for=lambda n: comments + posted,
            post_comment=lambda n, body: posted.append({"id": 50, "author_association": "OWNER", "body": body}),
            worker="w", trusted_apps=frozenset(), trusted_writers=frozenset())
        self.assertEqual((result["status"], result["job"]["kind"]), ("claimed", "retrospective"))


class FakeOps(contour.LifecycleOps):
    def __init__(self, *, closed=(), lineage=None):
        self.closed, self._lineage = set(closed), lineage or {"requirement": REQUIREMENT, "child": CHILDREN[0]}
        self.calls = []
        self.checkpointed = False
        self.cleanup_result = {"status": "cleaned", "removed": ["/w/x"], "errors": []}

    def lineage(self, root, branch):
        return self._lineage

    def children(self, root, requirement):
        return list(CHILDREN)

    def child_closed(self, root, child):
        return child in self.closed

    def reconcile_child(self, root, child):
        self.calls.append(("child", child))
        self.closed.add(child)

    def requirement_checkpoint(self, root, requirement, event_ids):
        self.calls.append(("requirement-checkpoint", tuple(event_ids)))
        self.checkpointed = True

    def requirement_checkpointed(self, root, requirement):
        return self.checkpointed

    def reconcile_parent(self, root, requirement, merged_children):
        self.calls.append(("parent", requirement))

    def cleanup(self, root, branch, number, merged_head):
        self.calls.append(("cleanup", branch))
        return self.cleanup_result


class FrictionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude/agent-friction.jsonl"
        self.state = self.root / ".claude/agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        for patch in (mock.patch.object(friction, "log_path", lambda: self.log),
                      mock.patch.object(friction, "state_path", lambda: self.state),
                      mock.patch.object(friction, "current_branch", lambda: "main")):
            patch.start()
            self.addCleanup(patch.stop)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def record(self, key="k1", **kw):
        values = dict(task="agent/br-7-t8-task", requirement=REQUIREMENT, category="coordinator-retry",
                      triggers=["excessive-retry"], severity="medium", observation="obs", evidence="ev",
                      hypothesis="hyp", proposal="prop", dedupe_key=key)
        return friction.append_coordinator_event(**{**values, **kw})


class FrictionAttributionTests(FrictionFixture):
    def test_coordinator_event_carries_task_and_requirement_and_is_recorded_once(self):
        first = self.record()
        again = self.record()
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(len(self.events()), 1)
        event = self.events()[0]
        self.assertEqual((event["task"], event["requirement"]), ("agent/br-7-t8-task", REQUIREMENT))
        self.assertIn(first["id"], [e["id"] for e in friction.events_for_task(REQUIREMENT)])
        self.assertIn(first["id"], [e["id"] for e in friction.events_for_task("agent/br-7-t8-task")])

    def test_lifecycle_transitions_record_friction_through_the_registered_sink(self):
        with Multi({7: HEAD}) as multi:
            queue.set_friction_sink(contour.default_friction_sink(
                ROOT, lineage=lambda root, branch: {"requirement": REQUIREMENT, "child": CHILDREN[0]}), worker="test-worker")
            self.addCleanup(queue.set_friction_sink, None)
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity={"head": "x"},
                              red_gate={"name": "review", "evidence": "material findings unresolved"})
            queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity={"head": "x"},
                              red_gate={"name": "review", "evidence": "material findings unresolved"})
            events = self.events()
            self.assertEqual(len(events), 1)
            self.assertEqual((events[0]["task"], events[0]["requirement"]), ("agent/br-7-t7-task", REQUIREMENT))
            self.assertEqual(events[0]["category"], "lifecycle-blocked-escalation")

    def test_composition_friction_lineage_is_selected_by_premerge_requirement_checkpoint(self):
        import managed_task
        with mock.patch.object(managed_task, "authoring_config", return_value=SimpleNamespace(repository="acme/backlog")):
            self.assertEqual(contour.resolve_lineage(self.root, "requirement/BR-7"),
                             {"requirement": REQUIREMENT, "child": None})
            sink = contour.default_friction_sink(self.root)
            with mock.patch.object(queue, "post_evidence", return_value={"event_id": "coordinator-0123456789abcdef"}):
                sink({"task": "requirement/BR-7", "category": "coordinator-retry", "severity": "medium",
                      "triggers": ["excessive-retry"], "observation": "retry", "evidence": "repair",
                      "hypothesis": "h", "proposal": "p", "dedupe_key": "composition-retry"})
        event = self.events()[0]
        self.assertEqual(event["requirement"], REQUIREMENT)
        ops = FakeOps()
        contour.ensure_requirement_checkpoint(ops, self.root, REQUIREMENT, CHILDREN)
        self.assertEqual(ops.calls, [("requirement-checkpoint", (event["id"],))])

    def test_friction_failure_prevents_transition_and_retry_records_event_before_handoff(self):
        with Multi({7: HEAD}) as multi:
            multi.ready(7)
            before = list(multi.comments[7])
            sink = mock.Mock(side_effect=OSError("friction storage denied"))
            queue.set_friction_sink(sink, worker="test-worker")
            self.addCleanup(queue.set_friction_sink, None)
            for failure in (OSError("friction storage denied"), SystemExit("invalid lineage")):
                sink.side_effect = failure
                with self.assertRaisesRegex(queue.QueueError, "friction recording failed.*retry transition"):
                    queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"})
                self.assertEqual(multi.comments[7], before)
            sink.side_effect = contour.default_friction_sink(
                self.root, lineage=lambda *a: {"requirement": REQUIREMENT, "child": CHILDREN[0]})
            result = queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"})
            self.assertEqual(result["state"], "repair-pending")
            self.assertEqual(len(self.events()), 1)

    def test_no_sink_means_no_friction_log(self):
        queue.set_friction_sink(None)
        with Multi({7: HEAD}) as multi:
            multi.ready(7)
            queue._transition(ROOT, "o/r", 7, "repair-pending", HEAD, task_identity={"head": "x"})
        self.assertEqual(self.events(), [])

    def test_child_attributed_event_is_accepted_by_the_requirement_retrospective(self):
        parent = {"body": "## Outcome\n\nX\n\n## Target repository\n\n`acme/project`\n\n"
                          "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n- [ ] acme/backlog#9\n"
                          "<!-- requirement-children:end -->"}
        events = [{"id": "child", "task": CHILDREN[0], "observation": "retry"},
                  {"id": "stranger", "task": "acme/backlog#99", "observation": "other"}]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent), \
                mock.patch.object(retrospective.agent_friction, "read_events", return_value=events):
            result = retrospective.checkpoint(Path(tmp), requirement=REQUIREMENT, result="findings",
                                              event_ids=["child"], review_note="Reviewed the Requirement path.")
            self.assertEqual(result["event_ids"], ["child"])  # accepted without re-recording
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "not attributed"):
                retrospective.checkpoint(Path(tmp), requirement=REQUIREMENT, result="findings",
                                         event_ids=["stranger"], review_note="Reviewed the Requirement path.")


class PostMergeJobTests(FrictionFixture):
    branch = "agent/br-7-t8-task"

    def run_job(self, kind, ops, *, attempt=0):
        merged = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1})])
        job = {"number": 7, "kind": kind, "head": HEAD, "task_identity": merged["task_identity"], "attempt": attempt}
        posted = []
        with mock.patch.object(workers, "build_job", return_value=job):
            outcome = contour.run_claimed_post_merge(
                ROOT, "o/r", merged, job, branch=self.branch, post_result=posted.append, ops=ops,
                claim_current=lambda: True)
        return outcome, posted

    def test_retrospective_links_recorded_events_instead_of_inventing_none(self):
        event = self.record(task=self.branch)
        outcome, posted = self.run_job("retrospective", FakeOps(closed=[CHILDREN[1]]))
        self.assertEqual(outcome["status"], "done")
        checkpoint = json.loads(self.state.read_text())["checkpoints"][self.branch]
        self.assertEqual(checkpoint["event_ids"], [event["id"]])
        self.assertIn("task-and-requirement-recorded", outcome["outcome"])
        self.assertEqual(len(posted), 1)

    def test_clean_path_records_none_and_defers_the_requirement_until_children_are_delivered(self):
        ops = FakeOps()
        outcome, _ = self.run_job("retrospective", ops)
        self.assertEqual(json.loads(self.state.read_text())["checkpoints"][self.branch]["result"], "none")
        self.assertIn("awaits remaining children", outcome["outcome"])
        self.assertEqual(ops.calls, [])

    def test_ambiguous_attribution_blocks_instead_of_recording_none(self):
        self.log.write_text(json.dumps({"id": "amb", "at": friction.utc_now(), "category": "x", "severity": "medium",
                                        "triggers": ["excessive-retry"]}) + "\n")
        outcome, posted = self.run_job("retrospective", FakeOps())
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("ambiguous", posted[0])
        self.assertFalse(self.state.exists())

    def test_unreadable_friction_log_is_not_a_clean_result(self):
        self.log.write_text("{broken\n")
        outcome, _ = self.run_job("retrospective", FakeOps())
        self.assertEqual(outcome["status"], "blocked")

    def test_terminal_reconciliation_closes_child_then_parent_once_all_children_are_done(self):
        ops = FakeOps(closed=[CHILDREN[1]])
        outcome, _ = self.run_job("terminal-reconciliation", ops)
        self.assertEqual(outcome["outcome"], "requirement-reconciled")
        self.assertEqual([c[0] for c in ops.calls], ["child", "requirement-checkpoint", "parent"])
        rerun = FakeOps(closed=[CHILDREN[0], CHILDREN[1]])
        rerun.checkpointed = True
        self.run_job("terminal-reconciliation", rerun)
        self.assertEqual([c[0] for c in rerun.calls], ["child", "parent"])  # idempotent re-run

    def test_terminal_reconciliation_waits_for_remaining_children(self):
        ops = FakeOps()
        outcome, _ = self.run_job("terminal-reconciliation", ops)
        self.assertIn("awaits remaining children", outcome["outcome"])
        self.assertEqual([c[0] for c in ops.calls], ["child"])

    def test_unresolvable_source_issue_is_blocked_not_guessed(self):
        outcome, _ = self.run_job("terminal-reconciliation", FakeOps(lineage={"requirement": None, "child": None}))
        self.assertEqual(outcome["status"], "blocked")

    def test_operator_errors_are_failed_receipts_that_get_retried(self):
        ops = FakeOps()
        ops.reconcile_child = mock.Mock(side_effect=RuntimeError("no GitHub authentication"))
        outcome, posted = self.run_job("terminal-reconciliation", ops)
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("failed: no GitHub authentication", posted[0])

    def test_cleanup_reports_removed_clean_and_refused_states(self):
        ops = FakeOps()
        self.assertEqual(self.run_job("cleanup", ops)[0]["outcome"], "cleaned")
        ops.cleanup_result = {"status": "already-clean", "removed": [], "errors": []}
        self.assertEqual(self.run_job("cleanup", ops)[0]["outcome"], "already-clean")
        ops.cleanup_result = {"status": "blocked", "removed": [], "errors": [{"path": "/w/x", "error": "dirty"}]}
        outcome, _ = self.run_job("cleanup", ops)
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("dirty", outcome["outcome"])

    def test_a_job_for_a_stale_candidate_is_discarded(self):
        merged = lifecycle.derive_candidate(merged_pr(), [record("merged", attempts={"post-merge": 1})])
        job = {**workers.build_job(merged), "attempt": 5}
        outcome = contour.run_claimed_post_merge(ROOT, "o/r", merged, job, branch=self.branch,
                                                 post_result=lambda body: self.fail("no receipt"), ops=FakeOps(),
                                                 claim_current=lambda: True)
        self.assertEqual(outcome["status"], "discarded")


class LocalCleanupTests(unittest.TestCase):
    def worktree(self, path="/managed/w1", head="1" * 40):
        return SimpleNamespace(path=Path(path), head=head, branch="agent/br-7-t8-task")

    def run_cleanup(self, worktrees, *, ancestor, managed="/managed", target_result=None):
        import worktree_cleanup as cleanup

        calls = []

        def run_git(args, **kwargs):
            calls.append(args[0])
            if args[0] == "rev-parse":
                return SimpleNamespace(stdout=HEAD + "\n", returncode=0)
            return SimpleNamespace(stdout="", returncode=0 if ancestor else 1)

        with mock.patch.object(cleanup, "_list_worktrees", return_value=worktrees), \
                mock.patch("_platform_common.run_git", side_effect=run_git), \
                mock.patch("_platform_common.machine_path", return_value=Path(managed)), \
                mock.patch.object(cleanup, "defer_completed_task", return_value=(Path("/x"), "target")) as defer, \
                mock.patch.object(cleanup, "_cleanup_target",
                                  return_value=target_result or {"removed": ["/managed/w1"], "errors": []}) as target:
            return contour.local_cleanup(ROOT, "agent/br-7-t8-task", 7, HEAD), defer, target

    def test_no_local_worktree_is_already_clean(self):
        result, defer, _ = self.run_cleanup([], ancestor=True)
        self.assertEqual(result["status"], "already-clean")
        defer.assert_not_called()

    def test_delivered_worktree_is_removed_through_the_exact_target_path(self):
        result, defer, target = self.run_cleanup([self.worktree()], ancestor=True)
        self.assertEqual((result["status"], result["removed"]), ("cleaned", ["/managed/w1"]))
        target.assert_called_once()

    def test_commits_missing_from_the_merged_pr_and_foreign_paths_are_refused(self):
        result, defer, _ = self.run_cleanup([self.worktree()], ancestor=False)
        self.assertEqual(result["errors"][0]["error"], "local-commits-not-in-merged-pr")
        result, defer, _ = self.run_cleanup([self.worktree("/elsewhere/w")], ancestor=True)
        self.assertEqual(result["errors"][0]["error"], "outside-managed-directory")
        defer.assert_not_called()

    def test_dirty_or_active_state_reported_by_the_cleanup_target_is_surfaced(self):
        result, _, _ = self.run_cleanup([self.worktree()], ancestor=True,
                                        target_result={"removed": [], "errors": [{"path": "/managed/w1", "error": "dirty"}]})
        self.assertEqual(result["status"], "blocked")


class LineageTests(unittest.TestCase):
    def test_branch_identity_resolves_requirement_and_child_or_nothing(self):
        self.assertIsNone(contour.resolve_lineage(ROOT, "agent/example"))
        body = "<!-- br-child:acme/backlog#8:6 -->\n"
        with mock.patch("managed_task.authoring_config", return_value=SimpleNamespace(repository="acme/backlog")), \
                mock.patch("requirement_intake.fetch_issue", return_value={"body": body}):
            self.assertEqual(contour.resolve_lineage(ROOT, "agent/br-7-t6-change"),
                             {"requirement": "acme/backlog#7", "child": "acme/backlog#8"})
        with mock.patch("managed_task.authoring_config", side_effect=RuntimeError("no config")):
            with self.assertRaisesRegex(RuntimeError, "no config"):
                contour.resolve_lineage(ROOT, "agent/br-7-t6-change")


if __name__ == "__main__":
    unittest.main()
