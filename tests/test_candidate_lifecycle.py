from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("candidate_lifecycle", ROOT / "template/scripts/candidate_lifecycle.py")
queue = load_platform_module("publication_queue", ROOT / "template/scripts/publication_queue.py")
from publication_state import RequiredCheckState  # noqa: E402

HEAD = "a" * 40
NEW_HEAD = "b" * 40


def pr(head=HEAD, labels=()):
    return {"number": 7, "head": {"sha": head}, "state": "open",
            "labels": [{"name": name} for name in labels]}


def handoff(state="reviewing", head=HEAD):
    return lifecycle.build_handoff_record(
        number=7, state=state, head=head, task_identity="task-content-digest",
        gates={"tests": {"result": "passed", "identity": head, "evidence": "test log"}},
        red_gate=None, not_reverified=["browser"], attempts={"review": 1},
        next_job={"kind": "review", "claim": "worker-1"}, at="2026-10-05T08:00:00Z")


def comment(record, ident=1):
    return {"id": ident, "author_association": "OWNER", "body": lifecycle.marker_body(record)}


class CandidateLifecycleTests(unittest.TestCase):
    def test_interrupted_composition_finalization_reoffers_finalize_job(self):
        import lifecycle_workers as workers
        identity = {"kind": "requirement-composition", "change": "br-7", "requirement": "owner/backlog#7",
                    "children": [{"change": "child", "head": HEAD}],
                    "task_content": {"digest": "d" * 64, "paths": {"app.py": "blob"}}}
        gates = {name: {"result": "passed", "identity": identity, "evidence": {"checked": True}}
                 for name in ("review", "selected-checks", "semantic-verification")}
        record = lifecycle.build_handoff_record(number=7, state="finalize-pending", head=HEAD,
            task_identity=identity, gates=gates, red_gate=None, not_reverified=[], attempts={"finalize": 1},
            next_job=workers.job_record("finalize", HEAD, identity, 1), at="2026-10-05T08:00:00Z")
        job = workers.build_job({**record, "number": 7})
        receipt = {"id": 2, "author_association": "OWNER", "body": workers.result_body(
            job, "worker", "validated-push", NEW_HEAD, task_identity=identity)}
        candidate = lifecycle.derive_candidate(pr(NEW_HEAD), [comment(record), receipt])
        recovered = workers.build_job(candidate)
        self.assertEqual(candidate["state"], "finalize-pending")
        self.assertEqual(recovered["kind"], "finalize")
        self.assertEqual(recovered["head"], NEW_HEAD)
        self.assertEqual(candidate["gates"], gates)

    def test_restart_derives_identical_state_without_mutation(self):
        snapshot = (pr(labels=("lifecycle:ready",)), [comment(handoff())])
        before = deepcopy(snapshot)
        first = lifecycle.derive_candidate(*snapshot)
        self.assertEqual(first, lifecycle.derive_candidate(*deepcopy(snapshot)))
        self.assertEqual(first["state"], "reviewing")
        self.assertEqual(first["next_action"]["claim"], "worker-1")
        self.assertEqual(snapshot, before)

    def test_every_state_roundtrips_and_projects_one_label(self):
        for state in lifecycle.STATES:
            with self.subTest(state=state):
                result = lifecycle.derive_candidate(pr(), [comment(handoff(state))])
                self.assertEqual(result["state"], state)
                self.assertEqual(result["lifecycle_labels"], ["lifecycle:" + state])

    def test_latest_exact_head_marker_uses_comment_order(self):
        rows = [comment(handoff("repairing"), 2), comment(handoff(), 1),
                comment(handoff("ready", NEW_HEAD), 3)]
        self.assertEqual(lifecycle.derive_candidate(pr(), rows)["state"], "repairing")

    def test_head_change_drops_gates_claims_and_next_job(self):
        result = lifecycle.derive_candidate(pr(NEW_HEAD, ("lifecycle:ready",)), [comment(handoff("ready"))])
        self.assertEqual(result["state"], "review-pending")
        self.assertEqual(result["gates"], {})
        self.assertIsNone(result["next_job"])
        self.assertEqual(result["next_action"], "start review")

    def test_claim_on_an_earlier_head_stays_visible_without_its_gates(self):
        result = lifecycle.derive_candidate(pr(NEW_HEAD), [comment(handoff("reviewing"))])
        self.assertEqual(result["state"], "reviewing")
        self.assertEqual(result["next_job"], {"kind": "review", "claim": "worker-1"})
        self.assertEqual(result["attempts"], {"review": 1})
        self.assertEqual(result["gates"], {})
        self.assertIn("earlier head", result["reason"])

    def test_v1_admissions_ready_or_integrating_with_no_invented_gates(self):
        record = {"version": 1, "number": 7, "kind": "admit", "head": HEAD}
        rows = [{"id": 1, "author_association": "OWNER", "body": lifecycle.V1_PREFIX + json.dumps(record)}]
        for labels, state in [((), "ready"), (("publication:active",), "integrating")]:
            result = lifecycle.derive_candidate(pr(labels=labels), rows)
            self.assertEqual(result["state"], state)
            self.assertEqual(result["gates"], {})
        self.assertEqual(lifecycle.derive_candidate(pr(NEW_HEAD), rows)["state"], "review-pending")

    def test_v1_update_binds_new_head_and_block_remains_visible(self):
        events = [{"version": 1, "number": 7, "kind": "admit", "head": HEAD},
                  {"version": 1, "number": 7, "kind": "update", "head": NEW_HEAD}]
        rows = [{"id": i, "author_association": "OWNER", "body": lifecycle.V1_PREFIX + json.dumps(row)} for i, row in enumerate(events)]
        self.assertEqual(lifecycle.derive_candidate(pr(NEW_HEAD), rows)["state"], "ready")
        events.append({"version": 1, "number": 7, "kind": "block", "reason": "conflict"})
        rows.append({"id": 3, "author_association": "OWNER", "body": lifecycle.V1_PREFIX + json.dumps(events[-1])})
        self.assertEqual(lifecycle.derive_candidate(pr(NEW_HEAD), rows)["reason"], "conflict")

    def test_malformed_markers_block_with_reason(self):
        broken = handoff()
        broken["attempts"] = {"review": -1}
        for value in ["{", "null", json.dumps(broken), json.dumps({**handoff(), "number": 9}),
                      json.dumps({**handoff(), "state": []})]:
            with self.subTest(value=value):
                result = lifecycle.derive_candidate(pr(), [comment(handoff()),
                    {"id": 9, "author_association": "OWNER", "body": lifecycle.PREFIX + value}])
                self.assertEqual(result["state"], "blocked-escalation")
                self.assertIn("malformed marker comment 9", result["reason"])
                self.assertEqual(result["gates"], {})

    def test_handoff_fields_and_input_copy(self):
        record = handoff("repair-pending")
        record["red_gate"] = {"name": "review", "identity": HEAD, "evidence": "finding 3"}
        clone = lifecycle.build_handoff_record(**{key: value for key, value in record.items() if key != "version"})
        record["gates"]["tests"]["evidence"] = "changed"
        self.assertEqual(clone["gates"]["tests"]["evidence"], "test log")
        self.assertEqual(set(clone), {"version", "number", "state", "head", "task_identity", "gates",
                                    "red_gate", "not_reverified", "attempts", "next_job", "at"})
        self.assertEqual(json.loads(lifecycle.marker_body(clone)[len(lifecycle.PREFIX):]), clone)

    def test_required_checks_invalidate_ready_and_integration(self):
        for state, expected in [("ready", "repair-pending"), ("integrating", "integration-repair-pending")]:
            result = lifecycle.derive_candidate(pr(), [comment(handoff(state))],
                {"head": HEAD, "kind": "failed", "detail": "tests failed"})
            self.assertEqual(result["state"], expected)
            self.assertEqual(result["red_gate"]["identity"], "task-content-digest")
            self.assertIsNone(result["next_job"])
        result = lifecycle.derive_candidate(pr(), [comment(handoff("ready"))], {"head": NEW_HEAD, "kind": "passed"})
        self.assertEqual(result["state"], "blocked-retryable")
        self.assertEqual(result["gates"], {})

    def test_pending_checks_and_merged_pr(self):
        rows = [comment(handoff("ready"))]
        result = lifecycle.derive_candidate(pr(), rows, {"head": HEAD, "kind": "pending"})
        self.assertEqual(result["state"], "blocked-retryable")
        self.assertEqual(lifecycle.derive_candidate({**pr(), "merged": True}, rows)["state"], "merged")

    def test_required_check_reuse_needs_same_proven_content_and_keeps_failure_authoritative(self):
        record = handoff("ready")
        identity = {"change": "example", "task_content": {"version": 1, "paths": {}, "base": HEAD, "digest": "a" * 64}}
        record["task_identity"] = identity
        record["gates"]["required-checks"] = {"result": "passed", "identity": deepcopy(identity), "evidence": "log"}
        checks = {"head": HEAD, "kind": "pending"}
        self.assertEqual(lifecycle.derive_candidate(pr(), [comment(record)], checks)["state"], "ready")
        checks["kind"] = "failed"
        self.assertEqual(lifecycle.derive_candidate(pr(), [comment(record)], checks)["state"], "repair-pending")
        checks["kind"] = "pending"
        record["task_identity"] = {"change": "example", "task_content": {"digest": "b" * 64}}
        self.assertEqual(lifecycle.derive_candidate(pr(), [comment(record)], checks)["state"], "blocked-retryable")
        record["task_identity"] = "unproven"
        self.assertFalse(lifecycle.passed_content_gate(record, "required-checks"))
        record["task_identity"] = {"task_content": {}}
        record["gates"]["required-checks"]["identity"] = record["task_identity"]
        self.assertFalse(lifecycle.passed_content_gate(record, "required-checks"))

    def test_status_rendering(self):
        result = lifecycle.derive_candidate(pr(), [comment(handoff())])
        text = lifecycle.render_status(result)
        for part in ["PR #7: reviewing", "red gate:", '"review": 1', "next action:",
                     "worker-1", HEAD, "test log", "not re-verified:"]:
            self.assertIn(part, text)

    def test_candidate_status_only_reads(self):
        with patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue, "_pr", return_value=pr()), \
             patch.object(queue, "_comments", return_value=[comment(handoff())]), \
             patch.object(queue, "required_check_state_for_ref",
                          return_value=RequiredCheckState("passed", checks=({"name": "tests", "state": "SUCCESS"},))):
            result = queue.candidate_status(ROOT, 7)
        self.assertEqual(result["state"], "reviewing")

    def test_status_reads_failed_checks_and_rejects_concurrent_push(self):
        failed = RequiredCheckState("failed", "tests", ({"name": "tests", "state": "FAILURE"},))
        moved = RequiredCheckState("unknown", "PR head moved", cause="head-mismatch")
        with patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue, "_pr", return_value=pr()), \
             patch.object(queue, "_comments", return_value=[comment(handoff("ready"))]), \
             patch.object(queue, "required_check_state_for_ref", side_effect=[failed, moved]) as classify:
            result = queue.candidate_status(ROOT, 7)
            self.assertEqual(result["state"], "repair-pending")
            self.assertEqual(result["red_gate"]["name"], "required-checks")
            result = queue.candidate_status(ROOT, 7)
            self.assertEqual(result["gates"], {})
            self.assertEqual(result["state"], "blocked-retryable")
            self.assertEqual(classify.call_args.args[2:], ("7", HEAD))

    def test_status_carries_cause_for_a_base_whose_required_checks_cannot_be_resolved(self):
        with patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue, "_pr", return_value=pr()), \
             patch.object(queue, "_comments", return_value=[comment(handoff("ready"))]), \
             patch.object(queue, "required_check_state_for_ref", return_value=RequiredCheckState("unknown", "unsupported base", cause="unsupported-state")):
            result = queue.candidate_status(ROOT, 7)
        self.assertEqual(result["state"], "blocked-retryable")

    def test_requirement_inventory_includes_generations_with_deleted_branches(self):
        from requirement_integration import _candidate_slug
        branch = "agent/" + _candidate_slug("owner/backlog#3")
        # Generation 8 was merged and its branch deleted; its PR still lists it.
        listing = CompletedProcess([], 0, f"7\t{branch}\n8\t{branch}-abcdef012345\n9\t{branch}-other\n10\tagent/unrelated\n"
                                   "12\tagent/br-3-t1-single-child\n13\tagent/br-31-t1-other-requirement\n", "")
        with patch("private_lineage.enabled", return_value=False), \
             patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue.subprocess, "run", return_value=listing) as run, \
             patch.object(queue, "candidate_status", side_effect=lambda root, number, **kw: {"number": number}):
            result = queue.requirement_status(ROOT, "owner/backlog#3")
        self.assertEqual(result["candidates"], [{"number": 7}, {"number": 8}, {"number": 12}])
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertNotIn("-X", run.call_args.args[0])

    def test_private_lineage_requirement_uses_its_private_candidate_slug(self):
        from requirement_integration import _candidate_slug
        handle = "pln_" + "0" * 32
        branch = "agent/" + _candidate_slug(handle)
        listing = CompletedProcess([], 0, f"11\t{branch}\n", "")
        with patch("private_lineage.enabled", return_value=True), \
             patch("private_lineage.handle_for_issue", return_value=handle) as handle_for, \
             patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue.subprocess, "run", return_value=listing), \
             patch.object(queue, "candidate_status", side_effect=lambda root, number, **kw: {"number": number}):
            result = queue.requirement_status(ROOT, "owner/backlog#3")
        self.assertEqual(result["candidates"], [{"number": 11}])
        self.assertEqual(handle_for.call_args.kwargs, {"create": False})

    def test_v1_block_after_the_latest_record_still_blocks(self):
        block = {"id": 9, "author_association": "OWNER",
                 "body": lifecycle.V1_PREFIX + json.dumps({"version": 1, "number": 7, "kind": "block", "reason": "check failed"})}
        derived = lifecycle.derive_candidate(pr(), [comment(handoff("integrating"), 5), block])
        self.assertEqual(derived["state"], "blocked-escalation")
        self.assertEqual(derived["red_gate"]["evidence"], "check failed")
        later = comment(handoff("ready"), 12)
        self.assertEqual(lifecycle.derive_candidate(pr(), [comment(handoff("integrating"), 5), block, later])["state"], "ready")

    def test_pending_checks_keep_the_integration_claim_and_merge_clears_jobs(self):
        integrating = comment(handoff("integrating"))
        pending = lifecycle.derive_candidate(pr(), [integrating], {"head": HEAD, "kind": "pending", "detail": "ci running"})
        self.assertEqual(pending["state"], "integrating")
        self.assertEqual(pending["next_job"], {"kind": "review", "claim": "worker-1"})
        merged = lifecycle.derive_candidate({**pr(), "merged": True}, [integrating])
        self.assertEqual((merged["state"], merged["next_job"], merged["next_action"]), ("merged", None, "reconcile delivery"))

    def test_failed_checks_replace_a_passed_required_checks_gate(self):
        record = lifecycle.build_handoff_record(
            number=7, state="integrating", head=HEAD, task_identity="digest",
            gates={"required-checks": {"result": "passed", "identity": HEAD, "evidence": "old"}},
            red_gate=None, not_reverified=[], attempts={}, next_job=None, at="2026-10-05T08:00:00Z")
        derived = lifecycle.derive_candidate(pr(), [comment(record)], {"head": HEAD, "kind": "failed", "detail": "x"})
        self.assertEqual(derived["gates"]["required-checks"]["result"], "failed")

    def test_private_requirement_without_shared_lineage_lists_child_branches(self):
        import private_lineage
        listing = CompletedProcess([], 0, "12\tagent/br-3-t1-single-child\n", "")
        with patch("private_lineage.enabled", return_value=True), \
             patch("private_lineage.handle_for_issue", side_effect=private_lineage.PrivateLineageError("no handle")), \
             patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue.subprocess, "run", return_value=listing), \
             patch.object(queue, "candidate_status", side_effect=lambda root, number, **kw: {"number": number}):
            result = queue.requirement_status(ROOT, "owner/backlog#3")
        self.assertEqual(result["candidates"], [{"number": 12}])
        self.assertIn("no handle", result["shared_lineage"])

    def test_unprovable_marker_author_fails_closed(self):
        member = {**comment(handoff("reviewing"), 4), "author_association": "MEMBER", "user": {"login": "someone"}}
        queue._writer_cache.clear()
        with patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue, "_gh", side_effect=queue.QueueError("HTTP 502")):
            with self.assertRaisesRegex(queue.QueueError, "cannot prove write permission"):
                queue.trusted_writers(ROOT, [member])
        self.assertEqual(queue._writer_cache, {})

    def test_untrusted_marker_comments_are_ignored(self):
        forged = {**comment(handoff("reviewing"), 5), "author_association": "NONE"}
        self.assertEqual(lifecycle.derive_candidate(pr(), [forged])["state"], "review-pending")
        app = {**forged, "performed_via_github_app": {"slug": "coordinator-app"}}
        # An App comment counts only when it is the configured coordinator App.
        self.assertEqual(lifecycle.derive_candidate(pr(), [app])["state"], "review-pending")
        self.assertEqual(lifecycle.derive_candidate(pr(), [app], trusted_apps=frozenset({"other-app"}))["state"], "review-pending")
        self.assertEqual(lifecycle.derive_candidate(pr(), [app], trusted_apps=frozenset({"coordinator-app"}))["state"], "reviewing")
        broken = {"id": 6, "author_association": "NONE", "body": lifecycle.PREFIX + "{broken"}
        self.assertNotEqual(lifecycle.derive_candidate(pr(), [broken])["state"], "blocked-escalation")

    def test_cli_status_rendering_and_json(self):
        result = lifecycle.derive_candidate(pr(), [comment(handoff())])
        for flag in [[], ["--json"]]:
            with patch.object(sys, "argv", ["publication_queue.py", "status", "--pr", "7", *flag]), \
                 patch.object(queue, "current_worktree_root", return_value=ROOT), \
                 patch.object(queue, "candidate_status", return_value=result), \
                 patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(queue.main(), 0)
            if flag:
                self.assertEqual(json.loads(output.getvalue()), result)
            else:
                self.assertIn("PR #7: reviewing", output.getvalue())


class MarkerSizeTests(unittest.TestCase):
    def record(self, evidence="ok"):
        identity = {"change": "c", "task_content": {"version": 1, "digest": "d", "base": HEAD,
                                                    "paths": {f"src/file{i}.py": "x" * 40 for i in range(100)}}}
        gates = {name: {"result": "passed", "identity": identity, "evidence": evidence}
                 for name in ("a", "b", "c", "d")}
        return lifecycle.build_handoff_record(
            number=7, state="reviewing", head=HEAD, task_identity=identity, gates=gates,
            red_gate={"name": "review", "identity": identity, "evidence": "e"}, not_reverified=[],
            attempts={}, next_job={"kind": "review", "head": HEAD, "task_identity": identity, "attempt": 0},
            at="2026-10-05T08:00:00Z")

    def test_identity_is_referenced_not_repeated_and_round_trips(self):
        record = self.record()
        body = lifecycle.marker_body(record)
        self.assertLess(len(body), len(json.dumps(record)) // 3)
        row = {"id": 1, "author_association": "OWNER", "body": body}
        self.assertEqual(lifecycle.latest_record(7, [row]), record)
        derived = lifecycle.derive_candidate({"number": 7, "head": {"sha": HEAD}, "state": "open"}, [row])
        self.assertEqual(derived["gates"], record["gates"])
        self.assertEqual(derived["next_job"], record["next_job"])

    def test_oversized_record_is_rejected_before_posting(self):
        with self.assertRaisesRegex(ValueError, "above the"):
            lifecycle.marker_body(self.record("x" * 70000))


class CoordinatorAppTrustTests(unittest.TestCase):
    def test_trusted_apps_come_from_workflow_env_or_config_only(self):
        with patch.dict("os.environ", {"DEV_PLATFORM_COORDINATOR_APP": "coordinator-app"}), \
             patch("_platform_common.read_project_config", return_value={}), \
             patch("_platform_common.read_operator_config", return_value={}):
            self.assertEqual(queue.trusted_apps(ROOT), frozenset({"coordinator-app"}))
        with patch.dict("os.environ", {"DEV_PLATFORM_COORDINATOR_APP": ""}), \
             patch("_platform_common.read_project_config", return_value={"publication": {"coordinator_app": "local-app"}}), \
             patch("_platform_common.read_operator_config", return_value={}):
            self.assertEqual(queue.trusted_apps(ROOT), frozenset({"local-app"}))
        with patch.dict("os.environ", {"DEV_PLATFORM_COORDINATOR_APP": ""}), \
             patch("_platform_common.read_project_config", return_value={}), \
             patch("_platform_common.read_operator_config", return_value={}):
            self.assertEqual(queue.trusted_apps(ROOT), frozenset())
        with patch.dict("os.environ", {"DEV_PLATFORM_COORDINATOR_APP": ""}), \
             patch.object(queue, "read_platform_config", return_value={}), \
             patch("_platform_common.read_operator_config", return_value={"publication": {"coordinator_app": "operator-app"}}):
            self.assertEqual(queue.trusted_apps(ROOT), frozenset({"operator-app"}))

    def test_queue_workflow_exports_the_minted_app_slug(self):
        workflow = (ROOT / ".github" / "workflows" / "publication-queue.yml").read_text(encoding="utf-8")
        self.assertIn("DEV_PLATFORM_COORDINATOR_APP: ${{ steps.app-token.outputs.app-slug }}", workflow)


class TaskStatusSummaryTests(unittest.TestCase):
    def test_lifecycle_summary_includes_exact_head_check_failures(self):
        derived = lifecycle.derive_candidate(pr(), [comment(handoff("integrating"))],
                                             {"head": HEAD, "kind": "failed", "detail": "validate failed"})
        with patch.object(queue, "candidate_status", return_value=derived) as status:
            summary = queue.lifecycle_summary(Path("/unused"), 7)
        status.assert_called_once()
        self.assertEqual(summary["state"], "integration-repair-pending")
        self.assertEqual(summary["red_gate"]["name"], "required-checks")


class TrustAndMergeTests(unittest.TestCase):
    def test_member_or_collaborator_needs_proven_write_permission(self):
        member = {**comment(handoff("blocked-escalation"), 4), "author_association": "MEMBER", "user": {"login": "reader"}}
        self.assertEqual(lifecycle.derive_candidate(pr(), [member])["state"], "review-pending")
        writer = {**member, "user": {"login": "writer"}}
        self.assertEqual(lifecycle.derive_candidate(pr(), [writer], trusted_writers=frozenset({"writer"}))["state"],
                         "blocked-escalation")
        queue._writer_cache.clear()
        with patch.object(queue, "_repo", return_value="owner/repo"), \
             patch.object(queue, "_gh", side_effect=lambda _r, _api, path: {"permission": "read" if "reader" in path else "write"}):
            self.assertEqual(queue.trusted_writers(ROOT, [member, writer]), frozenset({"writer"}))

    def test_confirmed_merge_wins_over_a_malformed_record(self):
        broken = {"id": 3, "author_association": "OWNER", "body": lifecycle.PREFIX + "{broken"}
        derived = lifecycle.derive_candidate({**pr(), "merged": True}, [broken])
        self.assertEqual(derived["state"], "merged")


if __name__ == "__main__":
    unittest.main()
