from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("candidate_lifecycle", ROOT / "template/scripts/candidate_lifecycle.py")
workers = load_platform_module("lifecycle_workers", ROOT / "template/scripts/lifecycle_workers.py")
HEAD, NEW = "a" * 40, "b" * 40
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)
LATER = "2026-10-05T09:30:00Z"
PAST = "2026-10-05T08:30:00Z"
ROUTE = {"provider": "claude", "profile": "standard", "change": "c"}
JOB = {"kind": "review", "number": 7, "head": HEAD, "task_identity": "t", "attempt": 1}


def claim(worker, ident, *, head=HEAD, expires=LATER, assoc="OWNER", job=None):
    job = dict(job or JOB, head=head)
    body = workers.claim_body(job, worker, expires)
    return {"id": ident, "author_association": assoc, "body": body}


def handoff_comment(head=HEAD, state="review-pending", route=None):
    record = lifecycle.build_handoff_record(
        number=7, state=state, head=head, task_identity="t", gates={}, red_gate=None,
        not_reverified=[], attempts={"review": 1}, next_job={"kind": "review"}, at="2026-10-05T08:00:00Z",
        route=route)
    return {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}


class ClaimTests(unittest.TestCase):
    def test_race_exactly_one_wins(self):
        comments = [claim("w1", 10), claim("w2", 11)]
        self.assertTrue(workers.i_won(JOB, "w1", comments, now=NOW))
        self.assertFalse(workers.i_won(JOB, "w2", comments, now=NOW))
        # Comment order decides even when listed out of order.
        self.assertTrue(workers.i_won(JOB, "w1", list(reversed(comments)), now=NOW))

    def test_completed_job_is_not_offered_again_after_its_claim_expires(self):
        result = {"id": 12, "author_association": "OWNER", "body": workers.result_body(JOB, "w1", "reviewed")}
        comments = [claim("w1", 10, expires=PAST), result]
        self.assertFalse(workers.is_claimable(JOB, comments, now=NOW))
        discarded = {"id": 12, "author_association": "OWNER", "body": workers.result_body(JOB, "w1", "discarded: head moved")}
        self.assertTrue(workers.is_claimable(JOB, [claim("w1", 10, expires=PAST), discarded], now=NOW))
        # A forged result from an untrusted author completes nothing.
        forged = {**result, "author_association": "NONE"}
        self.assertTrue(workers.is_claimable(JOB, [claim("w1", 10, expires=PAST), forged], now=NOW))

    def test_unmanaged_pr_offers_no_job(self):
        bare = lifecycle.derive_candidate({"number": 7, "head": {"sha": HEAD}, "state": "open", "labels": []}, [])
        self.assertIsNone(workers.build_job(bare))

    def test_expired_claim_is_reclaimable(self):
        comments = [claim("w1", 10, expires=PAST)]
        self.assertTrue(workers.is_claimable(JOB, comments, now=NOW))
        comments.append(claim("w2", 11))
        self.assertTrue(workers.i_won(JOB, "w2", comments, now=NOW))

    def test_head_stale_claim_ignored_and_result_discarded(self):
        comments = [claim("w1", 10, head=NEW, job=JOB)]
        self.assertTrue(workers.is_claimable(JOB, comments, now=NOW))
        self.assertFalse(workers.result_is_current(JOB, NEW, NEW))
        self.assertFalse(workers.result_is_current(JOB, HEAD, NEW))
        self.assertTrue(workers.result_is_current(JOB, HEAD, HEAD))

    def test_untrusted_claim_ignored(self):
        comments = [claim("evil", 10, assoc="NONE"), claim("w2", 11)]
        self.assertTrue(workers.i_won(JOB, "w2", comments, now=NOW))
        self.assertTrue(workers.is_claimable(JOB, comments[:1], now=NOW))

    def test_work_next_claims_and_loses_race(self):
        posted = []
        store = {7: [handoff_comment()]}
        def post(number, body):
            posted.append(body)
            store[number].append({"id": 20 + len(posted), "author_association": "OWNER", "body": body})
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        kwargs = dict(list_prs=lambda: [pr], comments_for=lambda n: list(store[n]), post_comment=post, now=NOW)
        first = workers.work_next(frozenset({"review"}), worker="w1", **kwargs)
        self.assertEqual(first["status"], "claimed")
        second = workers.work_next(frozenset({"review"}), worker="w2", **kwargs)
        self.assertEqual(second["status"], "idle")  # already claimed, nothing claimable
        self.assertEqual(workers.work_next(frozenset({"repair"}), worker="w3", **kwargs)["status"], "idle")

    def test_work_next_loses_when_earlier_claim_appears_after_selection(self):
        store = {7: [handoff_comment()]}
        calls = []
        def comments_for(number):
            calls.append(1)
            rows = list(store[number])
            if len(calls) > 1:  # a rival's earlier-ordered claim is visible on the re-read
                rows.append(claim("rival", 5))
            return rows
        def post(number, body):
            store[number].append({"id": 30, "author_association": "OWNER", "body": body})
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        result = workers.work_next(frozenset({"review"}), list_prs=lambda: [pr], comments_for=comments_for,
                                   post_comment=post, worker="w1", now=NOW)
        self.assertEqual(result["status"], "lost")

    def test_dry_run_posts_nothing(self):
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        def post(*_):
            raise AssertionError("dry run must not post")
        result = workers.work_next(frozenset({"review"}), list_prs=lambda: [pr], comments_for=lambda n: [handoff_comment()],
                                   post_comment=post, worker="w", dry_run=True, now=NOW)
        self.assertEqual(result["status"], "dry-run")
        self.assertEqual(result["job"]["head"], HEAD)


def provider_comment(number, providers, head=HEAD):
    record = lifecycle.build_handoff_record(
        number=number, state="review-pending", head=head, task_identity="t", gates={}, red_gate=None,
        not_reverified=[], attempts={"review": 1},
        next_job={"kind": "review", "attempt": 1, "providers": providers}, at="2026-10-05T08:00:00Z")
    return {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}


class ProviderSelectionTests(unittest.TestCase):
    def work(self, providers_by_pr, **options):
        prs = [{"number": n, "head": {"sha": HEAD}, "state": "open"} for n in providers_by_pr]
        store = {n: [provider_comment(n, p)] for n, p in providers_by_pr.items()}
        posted = []
        def post(number, body):
            posted.append(number)
            store[number].append({"id": 50 + len(posted), "author_association": "OWNER", "body": body})
        result = workers.work_next(frozenset({"review"}), list_prs=lambda: prs, comments_for=lambda n: list(store[n]),
                                   post_comment=post, worker="w", now=NOW, **options)
        return result, posted

    def test_reoffer_changes_job_identity_only_when_present(self):
        job = {"kind": "repair", "number": 7, "head": HEAD, "attempt": 2}
        reoffer = {"seq": 1, "action": "switch-provider", "from": ["codex"], "to": ["claude"], "reason": "r", "at": "x"}
        self.assertEqual(workers.job_id(job), f"pr7:repair:{HEAD}:a2")
        self.assertEqual(workers.job_id({**job, "reoffer": reoffer}), f"pr7:repair:{HEAD}:a2:r1")
        with self.assertRaises(ValueError):
            workers.job_record("finalize", HEAD, "t", 0, reoffer=reoffer)
        with self.assertRaises(ValueError):
            workers.job_record("review", HEAD, "t", 0, reoffer={"seq": 0})

    def test_unavailable_result_does_not_complete_the_job(self):
        row = {"id": 9, "author_association": "OWNER", "body": workers.result_body(JOB, "w", "unavailable: login")}
        self.assertFalse(workers.job_completed(JOB, [row], trusted_apps=frozenset(), trusted_writers=frozenset()))
        done = {**row, "body": workers.result_body(JOB, "w", "reviewed")}
        self.assertTrue(workers.job_completed(JOB, [done], trusted_apps=frozenset(), trusted_writers=frozenset()))

    def test_unrunnable_lowest_job_does_not_block_a_runnable_one(self):
        eligible = lambda job: workers.job_eligible(job, review_ready=frozenset({"claude"}))
        result, posted = self.work({5: ["codex"], 9: ["claude", "codex"]}, eligible=eligible)
        self.assertEqual((result["status"], result["job"]["number"]), ("claimed", 9))
        self.assertEqual(posted, [9])  # no claim, hold or comment on the unrunnable job

    def test_unresolved_provider_is_not_eligible_for_a_filtering_worker(self):
        eligible = lambda job: workers.job_eligible(job, review_ready=frozenset({"claude"}))
        result, posted = self.work({5: ["unresolved-originating-task-route"]}, eligible=eligible)
        self.assertEqual((result["status"], posted), ("idle", []))

    def test_selection_by_pr_and_unfiltered_default(self):
        self.assertEqual(self.work({5: ["codex"], 9: ["claude"]}, only_prs=frozenset({9}))[0]["job"]["number"], 9)
        self.assertEqual(self.work({5: ["codex"], 9: ["claude"]})[0]["job"]["number"], 5)
        self.assertEqual(self.work({5: ["codex"]}, only_prs=frozenset({9}))[0]["status"], "idle")

    def test_repair_eligibility_uses_the_declared_writer_provider(self):
        job = {"kind": "repair", "providers": ["codex"]}
        self.assertTrue(workers.job_eligible(job, repair_ready=frozenset({"codex"})))
        self.assertFalse(workers.job_eligible(job, repair_ready=frozenset()))
        self.assertTrue(workers.job_eligible(job))

    def test_readiness_reports_each_provider_from_the_probe(self):
        calls = []
        def probe(root, config, launcher):
            calls.append(config["provider"])
            return {"ready": config["provider"] == "claude", "limitation": "codex usage limit"}
        with tempfile.TemporaryDirectory() as scratch:
            readiness = workers.provider_readiness(ROOT, ["codex", "claude", "codex"], workdir=scratch, probe=probe)
            self.assertEqual(readiness, {"codex": "codex usage limit", "claude": None})
            self.assertEqual(calls, ["codex", "claude"])
            with self.assertRaisesRegex(workers.WorkerError, "unsupported provider"):
                workers.provider_readiness(ROOT, ["gemini"], workdir=scratch, probe=probe)

    def test_cli_requires_repair_provider_and_reports_unready_providers(self):
        with mock.patch.object(workers, "_gh_json", return_value=[]):
            self.assertEqual(workers.main(["work-next", "--kinds", "repair", "--repo", "o/r", "--run",
                                           "--llm-command", "x", "--allow", "src/"]), 2)
            with mock.patch.object(workers, "_coordinator_trust", return_value={"trusted_apps": frozenset(),
                                                                                  "trusted_writers": frozenset()}), \
                 mock.patch.object(workers, "provider_readiness", return_value={"codex": "logged out", "claude": None}), \
                 mock.patch("sys.stdout") as out:
                self.assertEqual(workers.main(["work-next", "--kinds", "review", "--repo", "o/r", "--dry-run",
                                               "--providers", "codex,claude", "--pr", "7"]), 0)
            printed = "".join(call.args[0] for call in out.write.call_args_list)
            self.assertIn('"unavailable": {"codex": "logged out"}', printed)
            self.assertIn('"ready": ["claude"]', printed)

def repair_comment(providers=("codex",), *, provider=None, reoffer=None):
    job = workers.job_record("repair", HEAD, "t", 1, providers=list(providers), reoffer=reoffer)
    if provider is not None:
        job["provider"] = provider
    record = lifecycle.build_handoff_record(
        number=7, state="repair-pending", head=HEAD, task_identity="t", gates={}, red_gate=None,
        not_reverified=[], attempts={"repair": 1}, next_job=job, at="2026-10-05T08:00:00Z",
        route={"provider": "codex", "profile": "standard", "change": "c"})
    return {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}


class WorkerIdentityTests(unittest.TestCase):
    def resolve(self, explicit=None, environ=None, **kwargs):
        values = dict(hostname="host-a", pid=10, nonce="aa11")
        values.update(kwargs)
        return workers.resolve_worker_identity(explicit, environ or {}, **values)

    def test_generated_identities_differ_by_host_pid_and_nonce(self):
        base = self.resolve()
        self.assertEqual(base, "worker-host-a-10-aa11")
        self.assertEqual(len({base, self.resolve(hostname="host-b"), self.resolve(pid=11), self.resolve(nonce="bb22")}), 4)

    def test_hostname_is_sanitized_and_empty_hostname_fails(self):
        self.assertEqual(self.resolve(hostname="My Host/1"), "worker-my-host-1-10-aa11")
        self.assertLessEqual(len(self.resolve(hostname="h" * 100)), 56)
        with self.assertRaises(workers.WorkerError):
            self.resolve(hostname="  ")

    def test_option_wins_over_variable_and_variable_over_generated(self):
        env = {"DEV_PLATFORM_WORKER": "from-env"}
        self.assertEqual(self.resolve("from-flag", env), "from-flag")
        self.assertEqual(self.resolve(None, env), "from-env")

    def test_invalid_explicit_identities_fail_without_replacement(self):
        for bad in ("", "x" * 65, "has space", "a/b", "-lead", "tab\tx", "new\nline"):
            with self.subTest(bad=bad):
                with self.assertRaises(workers.WorkerError):
                    self.resolve(bad)
        with self.assertRaises(workers.WorkerError):
            self.resolve(None, {"DEV_PLATFORM_WORKER": ""})

    def test_claim_and_result_bodies_validate_the_identity(self):
        with self.assertRaises(workers.WorkerError):
            workers.claim_body(JOB, "bad worker", LATER)
        with self.assertRaises(workers.WorkerError):
            workers.result_body(JOB, "", "reviewed")

    def test_executors_have_no_worker_default(self):
        import inspect

        gate = load_platform_module("pr_review_gate", ROOT / "template/scripts/pr_review_gate.py")
        contour = load_platform_module("integration_contour", ROOT / "template/scripts/integration_contour.py")
        for function in (workers.execute_job, gate.run_claimed, contour.run_claimed_integration_repair,
                         contour.run_claimed_post_merge):
            self.assertIs(inspect.signature(function).parameters["worker"].default, inspect.Parameter.empty, function)

    def test_earlier_identities_still_replay(self):
        comments = [claim("worker-1234", 3)]
        self.assertTrue(workers.i_won(JOB, "worker-1234", comments, now=NOW))
        self.assertFalse(workers.i_won(JOB, "worker-1235", comments, now=NOW))

    def test_cli_exits_2_on_invalid_identity_before_any_github_call(self):
        with mock.patch.object(workers, "_gh_json", side_effect=AssertionError("no GitHub call")):
            self.assertEqual(workers.main(["work-next", "--kinds", "review", "--repo", "o/r", "--worker", "bad worker"]), 2)

    def test_cli_prints_the_resolved_identity(self):
        out = mock.MagicMock()
        with mock.patch.object(workers, "_coordinator_trust", return_value={}), \
             mock.patch.object(workers, "_gh_json", return_value=[]), \
             mock.patch("builtins.print", out):
            self.assertEqual(workers.main(["work-next", "--kinds", "review", "--repo", "o/r", "--worker", "w-print"]), 0)
        self.assertEqual(json.loads(out.call_args.args[0])["worker"], "w-print")


class RepairProviderTests(unittest.TestCase):
    def poll(self, provider, comments, **extra):
        posted = []
        def post(number, body):
            posted.append(body)
            comments.append({"id": 20 + len(posted), "author_association": "OWNER", "body": body})
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        result = workers.work_next(frozenset({"repair"}), list_prs=lambda: [pr], comments_for=lambda n: list(comments),
                                   post_comment=post, worker="w1", provider=provider, now=NOW, **extra)
        return result, posted

    def test_matching_worker_claims_and_records_provider(self):
        result, posted = self.poll("codex", [repair_comment()])
        self.assertEqual(result["status"], "claimed")
        self.assertEqual(json.loads(posted[0][len(workers.CLAIM_PREFIX):])["provider"], "codex")
        self.assertEqual(json.loads(workers.result_body(result["job"], "w1", "pushed", provider="codex")[len(workers.RESULT_PREFIX):])["provider"], "codex")

    def test_mismatched_worker_reports_unauthorized_and_posts_nothing(self):
        comments = [repair_comment()]
        result, posted = self.poll("claude", comments)
        self.assertEqual((result["status"], posted), ("idle", []))
        self.assertEqual(result["unauthorized"], [{"number": 7, "kind": "repair", "required_provider": "codex"}])
        self.assertEqual(self.poll("codex", comments)[0]["status"], "claimed")

    def test_recorded_operator_switch_authorizes_the_named_provider(self):
        event = {"seq": 1, "action": "switch-provider", "from": ["codex"], "to": ["claude"], "reason": "quota"}
        comments = [repair_comment(("claude",), reoffer=event)]
        result, posted = self.poll("claude", comments)
        self.assertEqual(result["status"], "claimed")
        self.assertIn(":r1", workers.job_id(result["job"]))
        self.assertEqual(json.loads(posted[0][len(workers.CLAIM_PREFIX):])["provider"], "claude")
        # the route provider's worker is now unauthorized: exactly one provider runs the job
        result, posted = self.poll("codex", [repair_comment(("claude",), reoffer=event)])
        self.assertEqual((result["status"], posted), ("idle", []))
        self.assertEqual(result["unauthorized"], [{"number": 7, "kind": "repair", "required_provider": "claude"}])

    def test_non_route_provider_without_matching_recorded_switch_fails(self):
        wrong = {"seq": 1, "action": "switch-provider", "from": ["codex"], "to": ["codex"], "reason": "x"}
        unrelated = {"seq": 1, "action": "resume", "from": ["codex"], "to": ["claude"], "reason": "x"}
        for reoffer in (None, wrong, unrelated):
            with self.subTest(reoffer=reoffer), self.assertRaisesRegex(workers.WorkerError, "PR #7.*re-offer"):
                self.poll("claude", [repair_comment(("claude",), reoffer=reoffer)])

    def test_provider_is_required_for_repair_kinds(self):
        with self.assertRaisesRegex(workers.WorkerError, "--provider is required"):
            self.poll(None, [repair_comment()])
        with mock.patch.object(workers, "_gh_json", side_effect=AssertionError("no GitHub call")):
            self.assertEqual(workers.main(["work-next", "--kinds", "review,repair", "--repo", "o/r"]), 2)

    def test_missing_unknown_or_contradictory_provider_fails_naming_the_pr(self):
        bad = [workers.job_record("repair", HEAD, "t", 1, providers=[]),
               workers.job_record("repair", HEAD, "t", 1, providers=["gemini"]),
               workers.job_record("repair", HEAD, "t", 1, providers=["codex", "claude"]),
               {**workers.job_record("repair", HEAD, "t", 1, providers=["codex"]), "provider": "claude"}]
        for job in bad:
            record = lifecycle.build_handoff_record(
                number=7, state="repair-pending", head=HEAD, task_identity="t", gates={}, red_gate=None,
                not_reverified=[], attempts={}, next_job=job, at="2026-10-05T08:00:00Z")
            row = {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}
            with self.subTest(job=job), self.assertRaisesRegex(workers.WorkerError, "PR #7"):
                self.poll("codex", [row])
        record = lifecycle.build_handoff_record(
            number=7, state="repair-pending", head=HEAD, task_identity="t", gates={}, red_gate=None,
            not_reverified=[], attempts={}, next_job={"kind": "repair", "head": HEAD}, at="2026-10-05T08:00:00Z")
        with self.assertRaisesRegex(workers.WorkerError, "PR #7 repair job has no provider"):
            self.poll("codex", [{"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}])

    def test_executor_refuses_a_job_for_another_provider(self):
        job = {**JOB, "kind": "repair", "providers": ["codex"]}
        with self.assertRaisesRegex(workers.WorkerError, "requires provider codex"):
            workers.execute_job(job, source_repo="x", branch="b", allowed_paths=["a"], llm_command=["x"],
                                current_head=lambda: HEAD, post_result=lambda b: None, workdir="w", worker="w1",
                                provider="claude")


class TrustResolutionTests(unittest.TestCase):
    def test_app_records_and_member_claims_count_with_coordinator_trust(self):
        app_record = {**handoff_comment(), "author_association": "NONE",
                      "performed_via_github_app": {"slug": "coordinator-app"}}
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open", "labels": []}
        posted: list[dict] = []

        def post(number, body):
            posted.append({"id": 50 + len(posted), "author_association": "MEMBER", "user": {"login": "member"}, "body": body})

        def resolve(comments):
            return frozenset(row["user"]["login"] for row in comments
                             if row.get("author_association") == "MEMBER" and row.get("user", {}).get("login") == "member")

        result = workers.work_next(frozenset({"review"}), list_prs=lambda: [pr],
                                   comments_for=lambda n: [app_record, *posted], post_comment=post, worker="w1",
                                   now=NOW, trusted_apps=frozenset({"coordinator-app"}), trusted_writers=resolve)
        self.assertEqual(result["status"], "claimed")
        # Without the coordinator's trust the App record is ignored, so no job is offered at all.
        posted.clear()
        self.assertEqual(workers.work_next(frozenset({"review"}), list_prs=lambda: [pr],
                                           comments_for=lambda n: [app_record, *posted], post_comment=post,
                                           worker="w2", now=NOW)["status"], "idle")

    def test_coordinator_trust_proves_claim_authors(self):
        from unittest import mock

        queue = load_platform_module("publication_queue", ROOT / "template/scripts/publication_queue.py")
        claim_row = {"id": 9, "author_association": "COLLABORATOR", "user": {"login": "remote-worker"},
                     "body": workers.claim_body(JOB, "remote-worker", LATER)}
        queue._writer_cache.clear()
        with mock.patch.object(queue, "_repo", return_value="o/r"), \
             mock.patch.object(queue, "_gh", return_value={"permission": "write"}), \
             mock.patch.object(queue, "trusted_apps", return_value=frozenset()):
            trust = workers._coordinator_trust(Path("."))
            self.assertEqual(trust["trusted_writers"]([claim_row]), frozenset({"remote-worker"}))
        queue._writer_cache.clear()
        with mock.patch.object(queue, "_repo", side_effect=AssertionError("cwd repo must not be used")), \
             mock.patch.object(queue, "_gh", return_value={"permission": "write"}) as gh, \
             mock.patch.object(queue, "trusted_apps", return_value=frozenset()):
            trust = workers._coordinator_trust(Path("."), "other/repo")
            self.assertEqual(trust["trusted_writers"]([claim_row]), frozenset({"remote-worker"}))
        self.assertIn("repos/other/repo/collaborators/remote-worker/permission", gh.call_args.args)

    def test_cli_uses_the_coordinator_trust_model(self):
        from unittest import mock

        with mock.patch.object(workers, "_coordinator_trust", return_value={"trusted_apps": frozenset({"x"}),
                                                                             "trusted_writers": frozenset()}) as trust, \
             mock.patch.object(workers, "_gh_json", return_value=[]):
            self.assertEqual(workers.main(["work-next", "--kinds", "review", "--repo", "o/r", "--dry-run"]), 0)
        trust.assert_called_once()


class EnvironmentTests(unittest.TestCase):
    def test_credentials_scrubbed(self):
        env = {"PATH": "/bin", "GH_TOKEN": "x", "GITHUB_TOKEN": "x", "GH_ENTERPRISE_TOKEN": "x",
               "GITHUB_ENTERPRISE_TOKEN": "x", "GIT_ASKPASS": "/a", "SSH_AUTH_SOCK": "/s",
               "MY_GITHUB_API_KEY": "x", "ANTHROPIC_API_KEY": "llm", "GIT_CONFIG_GLOBAL": "/home/.gitconfig"}
        clean = workers.credential_free_env(env)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                     "GIT_ASKPASS", "SSH_AUTH_SOCK", "MY_GITHUB_API_KEY"):
            self.assertNotIn(name, clean)
        self.assertEqual(clean["ANTHROPIC_API_KEY"], "llm")
        self.assertEqual(clean["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(clean["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(clean["GIT_CONFIG_SYSTEM"], os.devnull)
        self.assertIn("GH_TOKEN", env)  # input untouched

    def test_llm_runs_with_scrubbed_env_and_devnull_stdin(self):
        seen = {}
        def runner(command, **kwargs):
            seen.update(kwargs, command=command)
            return subprocess.CompletedProcess(command, 0, "", "")
        workers.run_llm(["llm"], Path("/x"), env={"GH_TOKEN": "t", "PATH": "/bin"}, runner=runner)
        self.assertIs(seen["stdin"], subprocess.DEVNULL)
        self.assertNotIn("GH_TOKEN", seen["env"])
        self.assertEqual(seen["cwd"], Path("/x"))

    def test_scratch_home_hides_operator_github_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, work = Path(tmp) / "real", Path(tmp) / "work"
            (real / ".config" / "gh").mkdir(parents=True)
            (real / ".config" / "gh" / "hosts.yml").write_text("oauth_token: secret\n", encoding="utf-8")
            (real / ".codex").mkdir()
            (real / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
            home = workers.scratch_home(work, [".codex/auth.json"], source_home=real)
            self.assertTrue((home / ".codex" / "auth.json").is_file())
            self.assertFalse((home / ".config" / "gh" / "hosts.yml").exists())
            with self.assertRaises(workers.WorkerError):
                workers.scratch_home(work, [".config/gh/hosts.yml"], source_home=real)
            env = workers.credential_free_env({"HOME": str(real)}, home)
            self.assertEqual(env["HOME"], str(home))
            self.assertTrue(env["GH_CONFIG_DIR"].startswith(str(home)))

    def test_real_child_sees_no_credentials(self):
        code = "import os,json;print(json.dumps([k for k in os.environ if 'TOKEN' in k or k=='SSH_AUTH_SOCK']))"
        done = workers.run_llm([sys.executable, "-c", code], Path.cwd(),
                               env={"PATH": os.environ.get("PATH", ""), "GH_TOKEN": "t", "SSH_AUTH_SOCK": "/s"})
        self.assertEqual(json.loads(done.stdout), [])


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    return subprocess.run(["git", *args], cwd=repo, env=env, text=True, capture_output=True, check=True).stdout.strip()


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        self.write("src/a.py", "1")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "remote", "add", "origin", self.repo.as_uri())

    def write(self, path, text):
        full = self.repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text)

    def commit(self, path):
        self.write(path, "changed")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "work")
        return git(self.repo, "rev-parse", "HEAD")

    def test_accepts_in_scope_fast_forward(self):
        result = self.commit("src/a.py")
        self.assertEqual(workers.validate_worker_result(self.repo, self.base, result, ["src/"]), ["src/a.py"])

    def test_rejects_non_fast_forward(self):
        self.commit("src/a.py")
        git(self.repo, "checkout", "-q", "--detach", self.base)
        sibling = self.commit("src/b.py")
        other = self.base
        git(self.repo, "checkout", "-q", "--detach", self.base)
        diverged = self.commit("src/c.py")
        with self.assertRaisesRegex(workers.WorkerError, "fast-forward"):
            workers.validate_worker_result(self.repo, sibling, diverged, ["src/"])
        with self.assertRaises(workers.WorkerError):
            workers.validate_worker_result(self.repo, self.base, other, ["src/"])  # no new commits

    def test_rejects_out_of_scope_workflow_and_evidence(self):
        cases = [("docs/x.md", "outside candidate scope"), (".github/workflows/ci.yml", "workflow"),
                 ("openspec/changes/c/verification.md", "evidence"), ("openspec/changes/c/automated-checks.json", "evidence"),
                 ("openspec/changes/c/independent-review-1.json", "evidence"),
                 ("openspec/changes/c/independent-reviews/r.json", "evidence"),
                 ("openspec/changes/c/evidence/test-result.json", "evidence"),
                 ("openspec/changes/c/nested/evidence/deep.json", "evidence")]
        for path, message in cases:
            with self.subTest(path=path):
                git(self.repo, "checkout", "-q", "--detach", self.base)
                result = self.commit(path)
                with self.assertRaisesRegex(workers.WorkerError, message):
                    workers.validate_worker_result(self.repo, self.base, result, ["src/", ".github/", "openspec/"])

    def test_review_has_no_write_path(self):
        result = self.commit("src/a.py")
        with self.assertRaisesRegex(workers.WorkerError, "no write path"):
            workers.validate_worker_result(self.repo, self.base, result, ["src/"], kind="review")

    def test_default_harness_push_auth_is_scoped_and_errors_do_not_log_credentials(self):
        import base64
        origin = "https://github.com/acme/project.git"
        token = "coordinator-secret"
        encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
        git(self.repo, "remote", "set-url", "origin", origin)
        before = (self.repo / ".git/config").read_bytes()
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        with mock.patch.dict(os.environ, {"GH_TOKEN": token}, clear=True):
            workers.push_validated(self.repo, "task/x", self.base, NEW, runner=runner)
            command, kwargs = runner.call_args.args[0], runner.call_args.kwargs
            self.assertNotIn(token, str(command))
            self.assertEqual(kwargs["env"]["GIT_CONFIG_KEY_1"], f"http.{origin}.extraheader")
            self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_1"], "AUTHORIZATION: basic " + encoded)
            self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual((self.repo / ".git/config").read_bytes(), before)
            runner.return_value = subprocess.CompletedProcess([], 1, token, encoded)
            with self.assertRaises(workers.WorkerError) as error:
                workers.push_validated(self.repo, "task/x", self.base, NEW, runner=runner)
            self.assertNotIn(token, str(error.exception))
            self.assertNotIn(encoded, str(error.exception))
        explicit = {"explicit": "environment"}
        with mock.patch.object(workers, "harness_push_env") as auth:
            runner.return_value = subprocess.CompletedProcess([], 0, "", "")
            workers.push_validated(self.repo, "task/x", self.base, NEW, runner=runner, env=explicit)
            auth.assert_not_called()
            self.assertIs(runner.call_args.kwargs["env"], explicit)

    def test_push_uses_expected_head_lease(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "", "")
        workers.push_validated(self.repo, "task/x", self.base, NEW, runner=runner)
        command, kwargs = calls[0]
        self.assertEqual(command[:5], ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"])
        self.assertEqual(command[-3:], ["origin", f"{NEW}:refs/heads/task/x",
                                        f"--force-with-lease=refs/heads/task/x:{self.base}"])
        self.assertIn("push", command)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)

    def test_push_rejection_raises(self):
        runner = lambda command, **kw: subprocess.CompletedProcess(command, 1, "", "stale info")
        with self.assertRaisesRegex(workers.WorkerError, "push rejected"):
            workers.push_validated(self.repo, "b", self.base, NEW, runner=runner)


class JobRecordTests(unittest.TestCase):
    def test_published_record_round_trips_into_job(self):
        record = workers.job_record("cleanup", HEAD, "ident", 3)
        row = lifecycle.build_handoff_record(
            number=7, state="ready", head=HEAD, task_identity="ident", gates={}, red_gate=None,
            not_reverified=[], attempts={"cleanup": 1}, next_job=record, at="2026-10-05T08:00:00Z")
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        candidate = lifecycle.derive_candidate(pr, [{"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(row)}])
        self.assertEqual(workers.build_job(candidate),
                         {"kind": "cleanup", "number": 7, "head": HEAD, "task_identity": "ident", "attempt": 3})

    def test_stale_published_head_offers_nothing(self):
        candidate = {"number": 7, "head": HEAD, "state": "ready", "attempts": {},
                     "next_job": workers.job_record("review", NEW, "i", 0)}
        self.assertIsNone(workers.build_job(candidate))

    def test_publish_job_uses_transition_for_current_state(self):
        queue = load_platform_module("publication_queue", ROOT / "template/scripts/publication_queue.py")
        from unittest.mock import patch
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        with patch.object(queue, "_pr", return_value=pr), patch.object(queue, "_comments", return_value=[handoff_comment(route=ROUTE)]), \
                patch.object(queue, "_derive", wraps=lambda r, p, c, checks=None: lifecycle.derive_candidate(p, c)), \
                patch.object(queue, "_transition", return_value={}) as transition:
            queue.publish_job(Path("."), "o/r", 7, "repair", HEAD, task_identity="t")
        args, kwargs = transition.call_args
        self.assertEqual(args[3], "review-pending")
        self.assertEqual(kwargs["next_job"], workers.job_record("repair", HEAD, "t", 0, providers=["claude"]))


class PublishJobRouteTests(unittest.TestCase):
    """Provider resolution of published jobs comes from the candidate's recorded originating route."""

    def setUp(self):
        self.queue = load_platform_module("publication_queue", ROOT / "template/scripts/publication_queue.py")

    def publish(self, kind, comments, *, settings=None, **kwargs):
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        runner = load_platform_module("independent_review_runner", ROOT / "template/scripts/independent_review_runner.py")
        with mock.patch.object(self.queue, "_pr", return_value=pr), \
             mock.patch.object(self.queue, "_comments", return_value=comments), \
             mock.patch.object(self.queue, "_derive", wraps=lambda r, p, c, checks=None: lifecycle.derive_candidate(p, c)), \
             mock.patch.object(self.queue, "emit_friction") as friction, \
             mock.patch.object(runner, "settings", return_value=settings or {}), \
             mock.patch.object(self.queue, "_transition", return_value={}) as transition:
            self.queue.publish_job(Path("."), "o/r", 7, kind, HEAD, task_identity="t", **kwargs)
        friction.assert_not_called()
        return transition.call_args.kwargs["next_job"]

    def test_coordinator_publishes_repair_and_integration_repair_from_the_recorded_route(self):
        comments = [handoff_comment(route={"provider": "codex", "profile": "standard", "change": "c"})]
        for kind in ("repair", "integration-repair"):
            with self.subTest(kind):
                job = self.publish(kind, comments)
                self.assertEqual(job["providers"], ["codex"])
                self.assertNotIn("unresolved-originating-task-route", json.dumps(job))

    def test_repair_ignores_review_configuration(self):
        comments = [handoff_comment(route=ROUTE)]
        job = self.publish("repair", comments, settings={"providers": ["codex", "claude"]})
        self.assertEqual(job["providers"], ["claude"])

    def test_missing_unsupported_and_contradictory_routes_publish_nothing(self):
        for kind in ("repair", "integration-repair"):
            with self.subTest(kind, case="missing"), self.assertRaisesRegex(self.queue.QueueError, "no originating task route"):
                self.publish(kind, [handoff_comment()])
        with self.assertRaisesRegex(self.queue.QueueError, "unsupported"):
            self.publish("repair", [handoff_comment(route={"provider": "gemini", "profile": "p", "change": "c"})])
        with self.assertRaisesRegex(self.queue.QueueError, "neither the originating route provider"):
            self.publish("repair", [handoff_comment(route=ROUTE)], providers=["codex"])
        with self.assertRaisesRegex(self.queue.QueueError, "exactly one provider"):
            self.publish("repair", [handoff_comment(route=ROUTE)], providers=["claude", "codex"])

    def test_publish_accepts_a_non_route_provider_only_with_its_recorded_switch(self):
        comments = [handoff_comment(route=ROUTE)]
        event = {"seq": 2, "action": "switch-provider", "from": ["claude"], "to": ["codex"], "reason": "quota"}
        job = self.publish("repair", comments, providers=["codex"], reoffer=event)
        self.assertEqual((job["providers"], job["reoffer"]), (["codex"], event))
        with self.assertRaisesRegex(self.queue.QueueError, "neither the originating route provider"):
            self.publish("repair", comments, providers=["codex"], reoffer={**event, "to": ["claude"]})

    def test_task_change_without_matching_route_is_contradictory(self):
        identity = {"change": "other", "task_content": {"digest": "d"}}
        record = lifecycle.build_handoff_record(
            number=7, state="review-pending", head=HEAD, task_identity=identity, gates={}, red_gate=None,
            not_reverified=[], attempts={}, next_job={"kind": "review"}, at="2026-10-05T08:00:00Z", route=ROUTE)
        comments = [{"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}]
        with self.assertRaisesRegex(self.queue.QueueError, "contradicts"):
            self.publish("repair", comments)

    def test_review_uses_configured_ordered_list_else_the_route_and_never_a_default(self):
        route_comments = [handoff_comment(route=ROUTE)]
        self.assertEqual(self.publish("review", route_comments, settings={"providers": ["codex", "claude"]})["providers"],
                         ["codex", "claude"])
        self.assertEqual(self.publish("review", route_comments)["providers"], ["claude"])
        with self.assertRaisesRegex(self.queue.QueueError, "no originating task route"):
            self.publish("review", [handoff_comment()])

    def test_transition_records_and_inherits_the_route_across_heads(self):
        queue = self.queue
        posted = []
        first = lifecycle.build_handoff_record(
            number=7, state="review-pending", head=HEAD, task_identity={"change": "c"}, gates={}, red_gate=None,
            not_reverified=[], attempts={}, next_job=None, at="2026-10-05T08:00:00Z", route=ROUTE)
        comments = [{"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(first)}]
        def run(head, identity):
            observed = {"number": 7, "state": "open", "head": {"sha": head}, "labels": []}
            with mock.patch.object(queue, "_gh", side_effect=lambda _r, *a, data=None: posted.append(data["body"])), \
                 mock.patch.object(queue, "_label"), mock.patch.object(queue, "_pr", return_value=observed), \
                 mock.patch.object(queue, "_comments", return_value=comments), \
                 mock.patch.object(queue, "trusted_apps", return_value=frozenset()), \
                 mock.patch.object(queue, "trusted_writers", return_value=frozenset()), \
                 mock.patch.object(queue.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                return queue._transition(Path("."), "o/r", 7, "review-pending", head, task_identity=identity, inherit_identity=False)
        moved = run(NEW, {"change": "c", "task_content": {"digest": "e"}})
        self.assertEqual(moved["route"], ROUTE)
        with self.assertRaisesRegex(queue.QueueError, "contradicts"):
            run(NEW, {"change": "other", "task_content": {"digest": "e"}})
        self.assertEqual(len(posted), 1)


FAKE_LLM = r"""
import os, subprocess, sys
mode = os.environ.get("FAKE_MODE", "commit")
if mode == "fail":
    sys.exit(1)
def g(*a): subprocess.run(["git", *a], check=True, env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
if mode == "review-write":
    open("src/a.py", "w").write("dirty")
elif mode == "review-filter":
    open("src/a.py", "w").write("dirty")
    open(".gitattributes", "w").write("* filter=evil diff=evil\n")
    g("config", "filter.evil.clean", "touch " + os.environ["HOOK_MARK"] + " #")
    g("config", "diff.evil.textconv", "touch " + os.environ["HOOK_MARK"] + " #")
elif mode in ("commit", "malicious", "workflow"):
    path = ".github/workflows/ci.yml" if mode == "workflow" else "src/a.py"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("fixed")
    if mode == "malicious":
        hook = ".git/hooks/pre-push"
        open(hook, "w").write("#!/bin/sh\ntouch %s\n" % os.environ["HOOK_MARK"]); os.chmod(hook, 0o755)
        g("config", "remote.origin.pushurl", "/nonexistent/evil.git")
        g("config", "credential.helper", "!touch " + os.environ["HOOK_MARK"])
        g("config", "core.hooksPath", ".git/hooks")
    g("add", "-A"); g("commit", "-qm", "fix")
"""


class ExecuteJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.src = base / "src.git"
        seed = base / "seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "task")
        (seed / "src").mkdir()
        (seed / "src/a.py").write_text("1")
        git(seed, "add", "-A"); git(seed, "commit", "-qm", "base")
        self.head = git(seed, "rev-parse", "HEAD")
        subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(self.src)], check=True)
        self.work = base / "work"
        self.work.mkdir()
        self.mark = base / "mark"
        self.job = {"kind": "repair", "number": 7, "head": self.head, "task_identity": "t", "attempt": 1,
                    "providers": ["codex"]}
        self.posted = []
        script = base / "llm.py"
        script.write_text(FAKE_LLM)
        self.script = script

    def run_job(self, mode, *, kind="repair", head=None, allow=("src/",)):
        os.environ["FAKE_MODE"] = mode
        os.environ["HOOK_MARK"] = str(self.mark)
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("FAKE_MODE", "HOOK_MARK")])
        job = dict(self.job, kind=kind)
        return workers.execute_job(
            job, source_repo=str(self.src), branch="task", allowed_paths=list(allow),
            llm_command=[sys.executable, str(self.script)], current_head=lambda: head or self.head,
            post_result=self.posted.append, workdir=str(self.work), worker="w1", provider="codex",
            env={**os.environ}, push_env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})

    def test_repair_pushes_through_harness(self):
        result = self.run_job("commit")
        self.assertEqual(result["status"], "pushed")
        remote = git(self.src, "rev-parse", "refs/heads/task")
        self.assertEqual(remote, result["pushed_head"])
        self.assertNotEqual(remote, self.head)
        self.assertTrue(self.posted[-1].startswith(workers.RESULT_PREFIX))
        self.assertEqual(json.loads(self.posted[-1][len(workers.RESULT_PREFIX):])["pushed_head"], remote)

    def test_unusable_runtime_after_failure_is_unavailable_and_claimable_again(self):
        os.environ["FAKE_MODE"] = "fail"
        self.addCleanup(lambda: os.environ.pop("FAKE_MODE", None))
        def run(check):
            workdir = Path(tempfile.mkdtemp(dir=self.tmp.name))
            return workers.execute_job(
                self.job, source_repo=str(self.src), branch="task", allowed_paths=["src/"],
                llm_command=[sys.executable, str(self.script)], current_head=lambda: self.head,
                post_result=self.posted.append, workdir=str(workdir), worker="w1", provider="codex", env={**os.environ},
                runtime_check=check)
        usable = run(lambda: None)
        self.assertEqual(usable["status"], "failed")  # a usable runtime keeps the failure real
        limited = run(lambda: "codex usage limit reached")
        self.assertEqual(limited["status"], "unavailable")
        row = {"id": 1, "author_association": "OWNER", "body": self.posted[-1]}
        self.assertIn("usage limit", self.posted[-1])
        self.assertTrue(workers.is_claimable(self.job, [], trusted_apps=frozenset(), trusted_writers=frozenset()))
        self.assertFalse(workers.job_completed(self.job, [row], trusted_apps=frozenset(), trusted_writers=frozenset()))

    def test_command_that_cannot_start_is_unavailable(self):
        result = workers.execute_job(
            self.job, source_repo=str(self.src), branch="task", allowed_paths=["src/"],
            llm_command=["/nonexistent/writer"], current_head=lambda: self.head, post_result=self.posted.append,
            workdir=str(self.work), worker="w1", provider="codex", env={**os.environ}, runtime_check=lambda: None)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("cannot start", self.posted[-1])

    def test_unstartable_command_outside_the_repair_gate_still_raises(self):
        with self.assertRaises(OSError):
            workers.execute_job(
                dict(self.job, kind="integration-repair"), source_repo=str(self.src), branch="task",
                allowed_paths=["src/"], llm_command=["/nonexistent/writer"], current_head=lambda: self.head,
                post_result=self.posted.append, workdir=str(self.work), worker="w1", provider="codex", env={**os.environ})

    def test_head_moved_discards_result(self):
        result = self.run_job("commit", head=NEW)
        self.assertEqual(result["status"], "discarded")
        self.assertIn("discarded: head moved", self.posted[-1])
        self.assertEqual(git(self.src, "rev-parse", "refs/heads/task"), self.head)

    def test_malicious_checkout_config_is_never_used(self):
        result = self.run_job("malicious")
        self.assertEqual(result["status"], "pushed")
        self.assertFalse(self.mark.exists())
        self.assertEqual(git(self.src, "rev-parse", "refs/heads/task"), result["pushed_head"])

    def test_workflow_edit_rejected_nothing_pushed(self):
        result = self.run_job("workflow", allow=("src/", ".github/"))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(git(self.src, "rev-parse", "refs/heads/task"), self.head)

    def test_review_is_read_only(self):
        self.assertEqual(self.run_job("noop", kind="review")["status"], "reviewed")

    def test_review_that_modifies_checkout_fails(self):
        result = self.run_job("review-write", kind="review")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(git(self.src, "rev-parse", "refs/heads/task"), self.head)

    def test_review_filters_planted_in_the_checkout_never_execute(self):
        result = self.run_job("review-filter", kind="review")
        self.assertEqual(result["status"], "failed")
        self.assertFalse(self.mark.exists())

    def test_import_worktree_copies_content_without_reading_git(self):
        src, dst = Path(self.tmp.name) / "a", Path(self.tmp.name) / "b"
        (src / ".git").mkdir(parents=True), (dst / ".git").mkdir(parents=True)
        (src / ".git/config").write_text("[filter \"x\"]\n clean = touch " + str(self.mark) + "\n")
        (src / "d").mkdir()
        (src / "d/f.sh").write_text("x")
        (src / "d/f.sh").chmod(0o755)
        (dst / "stale.txt").write_text("old")
        (dst / ".git/keep").write_text("k")
        workers.import_worktree(src, dst)
        self.assertEqual((dst / "d/f.sh").read_text(), "x")
        self.assertTrue((dst / "d/f.sh").stat().st_mode & 0o111)
        self.assertFalse((dst / "stale.txt").exists())
        self.assertTrue((dst / ".git/keep").exists())
        self.assertFalse((dst / ".git/config").exists())
        self.assertFalse(self.mark.exists())

    def test_import_worktree_never_writes_through_symlinks(self):
        root = Path(self.tmp.name)
        src, dst, outside = root / "a", root / "b", root / "outside"
        for path in (src, dst, outside):
            path.mkdir()
        (dst / "a").symlink_to(outside)          # candidate head: directory symlink
        (src / "a").mkdir()                       # writer replaces it with a real directory
        (src / "a/payload").write_text("evil")
        (src / "link").symlink_to(outside)        # writer adds a directory symlink
        workers.import_worktree(src, dst)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((dst / "a").is_symlink())
        self.assertEqual((dst / "a/payload").read_text(), "evil")
        self.assertTrue((dst / "link").is_symlink())
        self.assertEqual(os.readlink(dst / "link"), str(outside))

    def test_work_next_abandons_when_head_moved_after_claim(self):
        pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}
        store = [handoff_comment()]
        post = lambda n, body: store.append({"id": 50, "author_association": "OWNER", "body": body})
        result = workers.work_next(frozenset({"review"}), list_prs=lambda: [pr], comments_for=lambda n: list(store),
                                   post_comment=post, worker="w", now=NOW, current_head=lambda n: NEW)
        self.assertEqual(result["status"], "stale")


if __name__ == "__main__":
    unittest.main()
