from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("candidate_lifecycle", SCRIPTS / "candidate_lifecycle.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
overview = load_platform_module("lifecycle_overview", SCRIPTS / "lifecycle_overview.py")

HEAD = "a" * 40
OLD_HEAD = "c" * 40
IDENTITY = {"change": "example", "task_content": {"version": 1, "digest": "proof", "paths": {}, "base": HEAD,
                                                   "scope": "independent-review-v1"}}
ROUTE = {"provider": "codex", "profile": "standard", "change": "example"}
AT = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
RECORDED = AT.isoformat().replace("+00:00", "Z")


def record(state, *, head=HEAD, attempts=None, red=None, next_job=None, gates=None, at=RECORDED, number=7):
    return lifecycle.build_handoff_record(
        number=number, state=state, head=head, task_identity=IDENTITY, gates=gates or {}, red_gate=red,
        not_reverified=[], attempts=attempts or {}, next_job=next_job, at=at, route=ROUTE)


def marker(rec, ident):
    return {"id": ident, "author_association": "OWNER", "body": lifecycle.marker_body(rec)}


def job(kind="review", head=HEAD, attempt=1, **extra):
    return workers.job_record(kind, head, IDENTITY, attempt, **extra)


def pull(head=HEAD, merged=False, state="open"):
    return {"number": 7, "state": "closed" if merged else state, "merged": merged,
            "head": {"sha": head, "ref": "agent/br-5-t1-example"}, "labels": []}


def assess(comments, *, minutes_after=10, threshold=30, pr=None):
    pr = pr or pull()
    candidate = lifecycle.derive_candidate(pr, comments)
    return overview.assess_candidate(candidate, pr, comments, repo="o/r", apps=frozenset(), writers=frozenset(),
                                     now=AT + timedelta(minutes=minutes_after), threshold_minutes=threshold)


def kinds(item):
    return [finding["kind"] for finding in item["findings"]]


class SettingTests(unittest.TestCase):
    def test_threshold_is_required_and_has_no_default(self):
        for config in ({}, {"chat_coordinator": {}}, {"chat_coordinator": {"unclaimed_job_after_minutes": 0}},
                       {"chat_coordinator": {"unclaimed_job_after_minutes": "30"}}):
            with self.subTest(config=config), mock.patch.object(overview, "read_platform_config", return_value=config), \
                    self.assertRaisesRegex(overview.OverviewError, "unclaimed_job_after_minutes"):
                overview.unclaimed_threshold_minutes(ROOT)
        with mock.patch.object(overview, "read_platform_config",
                               return_value={"chat_coordinator": {"unclaimed_job_after_minutes": 45}}):
            self.assertEqual(overview.unclaimed_threshold_minutes(ROOT), 45)

    def test_cli_fails_naming_the_key_and_prints_no_classification(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(overview, "read_platform_config", return_value={}), \
                mock.patch.object(overview, "current_worktree_root", return_value=ROOT), \
                mock.patch.object(queue, "_repo", return_value="o/r"), \
                mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            self.assertEqual(overview.main([]), 2)
        self.assertIn("unclaimed_job_after_minutes", err.getvalue())
        self.assertEqual(out.getvalue(), "")


class StageTests(unittest.TestCase):
    def test_fresh_unclaimed_handoff_is_handed_off_with_unconfirmed_executor(self):
        item = assess([marker(record("review-pending", next_job=job()), 1)])
        self.assertEqual(item["stage"], "handed-off")
        self.assertEqual(item["findings"], [])
        self.assertEqual(item["executor"]["activity"], "executor not confirmed")
        self.assertEqual(item["executor"]["job_age_minutes"], 10)
        self.assertEqual([s["status"] for s in item["chain"]][:1], ["current"])

    def test_text_output_for_an_unclaimed_job_shows_not_confirmed_and_its_age(self):
        item = assess([marker(record("review-pending", next_job=job()), 1)])
        text = overview.render_candidate(item, detail=False)
        self.assertIn("executor: executor not confirmed; job published 10 min ago", text)

    def test_live_claim_is_delivering_and_never_claimed_as_running(self):
        comments = [marker(record("reviewing", next_job=job()), 1)]
        candidate = lifecycle.derive_candidate(pull(), comments)
        comments.append({"id": 2, "author_association": "OWNER", "body": workers.claim_body(
            workers.build_job(candidate), "worker-1", (AT + timedelta(minutes=40)).isoformat().replace("+00:00", "Z"))})
        pr = {**pull(), "labels": [{"name": "publication:queued"}]}
        item = assess(comments, pr=pr)
        self.assertEqual(item["stage"], "delivering")
        self.assertEqual(item["executor"]["claimed_by"], "worker-1")
        self.assertEqual(item["executor"]["activity"], "executor activity: not confirmed")
        self.assertNotIn("running", json.dumps(item["executor"]))
        self.assertEqual(item["chain"][0]["step"], "review")
        self.assertEqual(item["chain"][0]["status"], "current")
        self.assertEqual(item["actions"], [])  # a live claim is never bypassed
        self.assertIn("claimed", item["expected_automation"])

    def test_merged_pr_with_open_post_merge_obligation_is_not_closed(self):
        comments = [marker(record("integrating", attempts={"post-merge": 1}), 1)]
        item = assess(comments, pr=pull(merged=True))
        self.assertEqual(item["stage"], "merged-open-obligations")
        self.assertEqual(item["job"]["kind"], "retrospective")
        self.assertEqual({s["step"]: s["status"] for s in item["chain"]}["integration"], "done")
        self.assertEqual({s["step"]: s["status"] for s in item["chain"]}["retrospective"], "current")

    def test_merged_pr_without_obligations_is_closed(self):
        item = assess([marker(record("integrating"), 1)], pr=pull(merged=True))
        self.assertEqual(item["stage"], "closed")

    def test_requirement_with_merged_candidates_is_not_done_until_terminal(self):
        merged = [{"number": 7, "stage": "closed"}, {"number": 8, "stage": "merged-open-obligations"}]
        aggregate = {"status": "In progress", "progress": {"stage": "implementation"}}
        result = overview.assess_requirement("o/b#5", aggregate, None, merged)
        self.assertEqual((result["stage"], result["merged_not_done"]), ("merged-open-obligations", True))
        self.assertEqual(overview.assess_requirement("o/b#5", {"status": "Done", "progress": {}}, None, merged)["stage"], "closed")
        self.assertEqual(overview.assess_requirement("o/b#5", aggregate, None, [])["stage"], "in-development")
        self.assertEqual(overview.assess_requirement("o/b#5", None, "board unreadable", merged)["stage"], "unknown")
        self.assertEqual(overview.assess_requirement("o/b#5", aggregate, None, [{"number": 9, "stage": "needs-intervention"}])["stage"],
                         "needs-intervention")

    def test_repair_round_moves_the_chain_to_repair_and_re_review(self):
        repair = assess([marker(record("repair-pending", attempts={"review": 1, "repair": 1}, next_job=job("repair", providers=["codex"])), 1)])
        steps = {s["step"]: s["status"] for s in repair["chain"]}
        self.assertEqual((steps["review"], steps["repair"], steps["re-review"]), ("done", "current", "pending"))
        again = assess([marker(record("review-pending", attempts={"review": 2, "repair": 1}, next_job=job(attempt=2)), 1)])
        steps = {s["step"]: s["status"] for s in again["chain"]}
        self.assertEqual((steps["repair"], steps["re-review"]), ("done", "current"))


class ExceptionTests(unittest.TestCase):
    def test_unclaimed_job_beyond_threshold(self):
        item = assess([marker(record("review-pending", next_job=job()), 1)], minutes_after=95)
        self.assertEqual(item["stage"], "needs-intervention")
        self.assertEqual(kinds(item), ["unclaimed-next-job"])
        self.assertIn("95 min", item["findings"][0]["detail"])

    def test_overdue_claim_findings_say_a_worker_is_needed_not_a_human_decision(self):
        item = assess([marker(record("review-pending", next_job=job()), 1)], minutes_after=95)
        self.assertIn("lifecycle worker", item["human_decision"])
        self.assertTrue(item["expected_automation"].startswith("overdue"))

    def test_merged_contribution_awaits_its_requirement_composition(self):
        contribution = {"kind": "contribution", "requirement": "o/b#5", "target_branch": "requirement/br-5",
                        "contribution_base": "b" * 40, "task_content": IDENTITY["task_content"]}
        rec = lifecycle.build_handoff_record(number=7, state="contribution-integrated", head=HEAD, task_identity=contribution,
                                             gates={}, red_gate=None, not_reverified=[], attempts={}, next_job=None, at=RECORDED)
        item = assess([marker(rec, 1)], pr=pull(merged=True))
        self.assertEqual(item["stage"], "merged-open-obligations")

    def test_expired_claim_names_worker_and_provider(self):
        comments = [marker(record("repairing", next_job=job("repair", providers=["codex"])), 1)]
        candidate = lifecycle.derive_candidate(pull(), comments)
        comments.append({"id": 2, "author_association": "OWNER", "body": workers.claim_body(
            workers.build_job(candidate), "worker-9", (AT + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "codex")})
        item = assess(comments, minutes_after=90)
        self.assertEqual(kinds(item), ["expired-claim"])
        self.assertIn("worker-9", item["findings"][0]["detail"])
        self.assertIn("codex", item["findings"][0]["detail"])

    def test_claim_recorded_on_an_earlier_head_is_a_stale_head(self):
        item = assess([marker(record("reviewing", head=OLD_HEAD, next_job=job(head=OLD_HEAD)), 1)])
        self.assertEqual(kinds(item), ["stale-head"])
        self.assertIn("not applied", item["findings"][0]["detail"])

    def test_unavailable_provider_names_provider_and_limitation(self):
        red = {"name": "review", "identity": IDENTITY, "evidence": "codex limit reached"}
        item = assess([marker(record("blocked-retryable", red=red, next_job=job(providers=["codex"])), 1)])
        self.assertEqual(kinds(item), ["provider-unavailable"])
        self.assertIn("codex", item["findings"][0]["detail"])

    def test_operational_escalation_offers_resume_with_exact_head(self):
        red = {"name": "repair", "identity": IDENTITY, "evidence": {"status": "failed"}}
        item = assess([marker(record("blocked-escalation", red=red, attempts={"repair": 1}), 1)])
        self.assertEqual(kinds(item), ["escalated-operational"])
        self.assertEqual([a["action"] for a in item["actions"]], ["resume"])
        self.assertIn(f"--expected-head {HEAD}", item["actions"][0]["command"])

    def test_finding_level_escalation_offers_no_action_and_names_the_human_decision(self):
        for status in ("exhausted", "proposed-rejection"):
            with self.subTest(status=status):
                red = {"name": "repair", "identity": IDENTITY, "evidence": {"status": status}}
                item = assess([marker(record("blocked-escalation", red=red, attempts={"repair": 3}), 1)])
                self.assertEqual(kinds(item), ["escalated-finding"])
                self.assertEqual(item["actions"], [])
                self.assertIn("record a disposition", item["human_decision"])
        review = {"name": "review", "identity": IDENTITY, "evidence": "material findings"}
        item = assess([marker(record("blocked-escalation", red=review), 1)])
        self.assertEqual((kinds(item), item["actions"]), (["escalated-finding"], []))

    def test_exhausted_post_merge_obligation(self):
        outcomes = [{"id": 10 + n, "author_association": "OWNER", "body": workers.result_body(
            {"number": 7, "kind": "retrospective", "head": HEAD, "attempt": n}, "w", "failed: boom")} for n in range(3)]
        item = assess([marker(record("integrating", attempts={"post-merge": 1}), 1), *outcomes], pr=pull(merged=True))
        self.assertEqual(kinds(item), ["post-merge-exhausted"])
        self.assertEqual(item["stage"], "needs-intervention")

    def test_malformed_marker_is_unknown_never_healthy(self):
        comments = [marker(record("review-pending", next_job=job()), 1),
                    {"id": 2, "author_association": "OWNER", "body": lifecycle.PREFIX + "{not json"}]
        item = assess(comments)
        self.assertEqual((item["stage"], kinds(item)), ("unknown", ["unknown-source"]))

    def test_not_started_requirement_is_in_development_not_unknown(self):
        aggregate = {"status": "pre-authoring", "progress": {"stage": "unknown", "diagnostics": [
            {"source": "orchestrator", "reason": "pre-authoring state is missing"}]}}
        result = overview.assess_requirement("o/b#5", aggregate, None, [])
        self.assertEqual(result["stage"], "in-development")
        self.assertIn("machine-local", result["note"])
        contradictory = {"status": "pre-authoring", "progress": {"stage": "unknown", "diagnostics": [
            {"source": "children", "reason": "status unreadable"}]}}
        self.assertEqual(overview.assess_requirement("o/b#5", contradictory, None, [])["stage"], "unknown")

    def test_unreadable_pr_is_reported_unknown(self):
        pr = pull()
        with mock.patch.object(queue, "_comments", side_effect=queue.QueueError("comment history unavailable")):
            item = overview.observe_candidate(ROOT, "o/r", pr, now=AT, threshold=30)
        self.assertEqual(item["stage"], "unknown")
        self.assertIn("comment history unavailable", item["findings"][0]["detail"])


class EligibilityAgreementTests(unittest.TestCase):
    """The overview lists an action if and only if the supported command accepts the candidate state."""

    def setUp(self):
        self.stack = ExitStack()
        self.comments = []
        self.addCleanup(self.stack.close)

        def post(*args, data=None, **kwargs):
            self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER", "body": data["body"]})

        self.stack.enter_context(mock.patch.object(queue, "_pr", side_effect=lambda *a: pull()))
        self.stack.enter_context(mock.patch.object(queue, "_comments", side_effect=lambda *a: list(self.comments)))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "_project_lifecycle_label"))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=post))

    def accepted(self, action):
        before = len(self.comments)
        try:
            gate.reoffer(ROOT, "o/r", 7, action=action, providers=["codex"] if action == "switch-provider" else None,
                         reason="r", actor="tester", adapter=queue)
        except queue.QueueError as error:
            self.assertEqual(len(self.comments), before)
            return str(error)
        return None

    def test_listed_actions_equal_accepted_commands(self):
        cases = {
            "review-pending": (record("review-pending", next_job=job(providers=["codex"])), {"switch-provider"}),
            "repair-pending": (record("repair-pending", red={"name": "review", "identity": IDENTITY, "evidence": "f"},
                                      next_job=job("repair", providers=["codex"])), {"switch-provider"}),
            "operational": (record("blocked-escalation", red={"name": "repair", "identity": IDENTITY,
                                                                "evidence": {"status": "failed", "providers": ["codex"]}},
                                   gates={"review": {"result": "failed", "identity": IDENTITY, "evidence": {"x": 1}}}), {"resume"}),
            "finding-level": (record("blocked-escalation", red={"name": "repair", "identity": IDENTITY,
                                                                 "evidence": {"status": "exhausted"}}), set()),
            "ready": (record("ready"), set()),
        }
        for name, (rec, expected) in cases.items():
            with self.subTest(case=name):
                self.comments = [marker(rec, 1)]
                item = assess(self.comments)
                listed = {a["action"] for a in item["actions"]}
                self.assertEqual(listed, expected)
                for action in ("resume", "switch-provider"):
                    refusal = self.accepted(action)
                    state_refusal = refusal is not None and (
                        "applies only" in refusal or "finding-level" in refusal or "use switch-provider" in refusal)
                    self.assertEqual(action in listed, not state_refusal, (name, action, refusal))
                    self.comments = [marker(rec, 1)]


class ReofferDecisionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.comments = [marker(record("repair-pending", red={"name": "review", "identity": IDENTITY, "evidence": "f"},
                                       next_job=job("repair", providers=["codex"])), 1)]
        self.addCleanup(self.stack.close)

        def post(*args, data=None, **kwargs):
            self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER", "body": data["body"]})

        self.head = HEAD
        self.stack.enter_context(mock.patch.object(queue, "_pr", side_effect=lambda *a: pull(self.head)))
        self.stack.enter_context(mock.patch.object(queue, "_comments", side_effect=lambda *a: list(self.comments)))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "_project_lifecycle_label"))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=post))

    def reoffer(self, **kwargs):
        return gate.reoffer(ROOT, "o/r", 7, action="switch-provider", providers=["claude"], reason="codex limit",
                            adapter=queue, **{"actor": "owner-login", **kwargs})

    def test_head_changed_between_report_and_decision_refuses_before_any_write(self):
        before = len(self.comments)
        with self.assertRaisesRegex(queue.QueueError, f"{HEAD}.*{OLD_HEAD}|{OLD_HEAD}.*{HEAD}"):
            self.reoffer(expected_head=OLD_HEAD)
        self.assertEqual(len(self.comments), before)

    def test_actor_via_and_head_are_recorded_in_the_candidate_record(self):
        self.reoffer(expected_head=HEAD, via="chat-coordinator")
        latest = lifecycle.latest_record(7, self.comments, head=HEAD)
        event = latest["next_job"]["reoffer"]
        self.assertEqual((event["actor"], event["via"], event["head"], event["reason"]),
                         ("owner-login", "chat-coordinator", HEAD, "codex limit"))
        self.assertEqual(event["to"], ["claude"])

    def test_missing_actor_fails_without_writing(self):
        before = len(self.comments)
        with self.assertRaisesRegex(queue.QueueError, "acting identity"):
            self.reoffer(actor=" ")
        self.assertEqual(len(self.comments), before)

    def test_unresolved_cli_actor_fails_naming_the_identity(self):
        with mock.patch.object(queue, "_gh", return_value={}), self.assertRaisesRegex(queue.QueueError, "acting GitHub identity"):
            queue._actor(ROOT)


class AttentionCommentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.comments = []
        self.fail_attention = False
        self.addCleanup(self.stack.close)

        def post(*args, data=None, **kwargs):
            if self.fail_attention and data["body"].startswith(queue.ATTENTION_PREFIX):
                raise queue.QueueError("api down")
            self.comments.append({"id": len(self.comments) + 1, "author_association": "OWNER", "body": data["body"]})

        self.stack.enter_context(mock.patch.object(queue, "_pr", side_effect=lambda *a: pull()))
        self.stack.enter_context(mock.patch.object(queue, "_comments", side_effect=lambda *a: list(self.comments)))
        self.stack.enter_context(mock.patch.object(queue, "trusted_apps", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "trusted_writers", return_value=frozenset()))
        self.stack.enter_context(mock.patch.object(queue, "_project_lifecycle_label"))
        self.stack.enter_context(mock.patch.object(queue, "_gh", side_effect=post))

    def attention(self):
        return [c for c in self.comments if c["body"].startswith(queue.ATTENTION_PREFIX)]

    def escalate(self, status="exhausted"):
        return queue._transition(ROOT, "o/r", 7, "blocked-escalation", HEAD, task_identity=IDENTITY,
                                 red_gate={"name": "repair", "identity": IDENTITY, "evidence": {"status": status}}, route=ROUTE)

    def test_one_comment_per_exact_escalation_even_when_repeated(self):
        self.escalate()
        self.escalate()
        self.assertEqual(len(self.attention()), 1)
        body = self.attention()[0]["body"]
        self.assertIn("Needs attention", body)
        self.assertIn("record a disposition", body)
        self.assertIn("https://github.com/o/r/pull/7", body)

    def test_operational_escalation_comment_lists_the_resume_command(self):
        self.escalate("failed")
        self.assertIn(f"--expected-head {HEAD}", self.attention()[0]["body"])

    def test_normal_progress_posts_no_attention_comment(self):
        for state, extra in (("review-pending", {"next_job": job()}), ("reviewing", {}), ("finalize-pending", {}), ("ready", {})):
            queue._transition(ROOT, "o/r", 7, state, HEAD, task_identity=IDENTITY, route=ROUTE, **extra)
        self.assertEqual(self.attention(), [])

    def test_failed_posting_is_raised_after_the_transition_and_repaired_on_the_next_observation(self):
        self.fail_attention = True
        with self.assertRaises(queue.AttentionError):
            self.escalate()
        self.assertEqual(lifecycle.latest_record(7, self.comments)["state"], "blocked-escalation")
        self.assertFalse(issubclass(queue.AttentionError, queue.QueueError))
        self.fail_attention = False
        self.escalate()
        self.assertEqual(len(self.attention()), 1)

    def test_forged_untrusted_marker_does_not_suppress_the_indication(self):
        self.escalate()
        genuine = self.attention()[0]["body"]
        self.comments = [c for c in self.comments if c["body"] != genuine]
        self.comments.append({"id": 99, "author_association": "NONE", "body": genuine})
        self.escalate()
        self.assertEqual(len([c for c in self.comments if c["author_association"] == "OWNER"
                              and c["body"].startswith(queue.ATTENTION_PREFIX)]), 1)

    def test_cli_reports_a_failed_indication_with_a_message_and_nonzero_exit(self):
        out = io.StringIO()
        with mock.patch.object(queue, "current_worktree_root", return_value=ROOT), \
                mock.patch.object(queue, "admit", side_effect=queue.AttentionError("PR #7 attention comment failed")), \
                mock.patch("sys.argv", ["publication_queue", "admit", "--pr", "7", "--head", HEAD]), \
                mock.patch("sys.stdout", out):
            self.assertEqual(queue.main(), 2)
        self.assertIn("attention comment failed", out.getvalue())

    def test_post_merge_exhaustion_is_indicated_once(self):
        outcomes = [{"id": 10 + n, "author_association": "OWNER", "body": workers.result_body(
            {"number": 7, "kind": "retrospective", "head": HEAD, "attempt": n}, "w", "failed: boom")} for n in range(3)]
        self.comments = [marker(record("integrating", attempts={"post-merge": 1}), 1), *outcomes]
        merged = pull(merged=True)
        with mock.patch.object(queue, "_pr", return_value=merged):
            self.assertTrue(queue.ensure_post_merge_attention(ROOT, "o/r", 7))
            self.assertFalse(queue.ensure_post_merge_attention(ROOT, "o/r", 7))
        self.assertEqual(len(self.attention()), 1)
        self.assertIn("exhausted", self.attention()[0]["body"])


class ColdSessionTests(unittest.TestCase):
    def test_summary_is_reproduced_from_github_state_alone_and_writes_nothing(self):
        comments = {7: [marker(record("review-pending", next_job=job()), 1)],
                    8: [marker(record("integrating", attempts={"post-merge": 1}, number=8), 1)]}
        prs = [pull(), {**pull(merged=True), "number": 8, "head": {"sha": HEAD, "ref": "agent/br-5-t2-other"}},
               {**pull(), "number": 9}]
        comments[9] = []
        writes = []

        def comments_for(root, repo, number):
            return list(comments[number])

        aggregate = {"requirement": "o/b#5", "status": "In progress", "children": [], "progress": {"stage": "implementation"}}
        with mock.patch.object(overview, "read_platform_config", return_value={
                    "chat_coordinator": {"unclaimed_job_after_minutes": 30},
                    "development_backlog": {"repository": "o/b"}}), \
                mock.patch.object(queue, "_repo", return_value="o/r"), \
                mock.patch.object(workers, "candidate_prs", return_value=prs), \
                mock.patch.object(queue, "_comments", side_effect=comments_for), \
                mock.patch.object(queue, "trusted_apps", return_value=frozenset()), \
                mock.patch.object(queue, "trusted_writers", return_value=frozenset()), \
                mock.patch.object(queue, "_gh", side_effect=lambda *a, **k: writes.append(a)), \
                mock.patch.object(overview, "_open_requirements", return_value=["o/b#5"]), \
                mock.patch.object(overview, "_observe_requirement", side_effect=lambda root, req, cands:
                                  overview.assess_requirement(req, aggregate, None, cands)):
            result = overview.overview(ROOT, now=AT + timedelta(minutes=10))
        self.assertEqual(writes, [])
        self.assertEqual(result["bounds"]["prs_without_lifecycle_record"], 1)
        self.assertEqual({c["number"]: c["stage"] for c in result["candidates"]},
                         {7: "handed-off", 8: "merged-open-obligations"})
        requirement = result["requirements"][0]
        self.assertEqual(requirement["candidates"], [7, 8])
        text = overview.render(result)
        self.assertIn("PR #7 [handed-off]", text)
        self.assertIn("executor not confirmed", text)


if __name__ == "__main__":
    unittest.main()
