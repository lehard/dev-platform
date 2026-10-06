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
JOB = {"kind": "review", "number": 7, "head": HEAD, "task_identity": "t", "attempt": 1}


def claim(worker, ident, *, head=HEAD, expires=LATER, assoc="OWNER", job=None):
    job = dict(job or JOB, head=head)
    body = workers.claim_body(job, worker, expires)
    return {"id": ident, "author_association": assoc, "body": body}


def handoff_comment(head=HEAD, state="review-pending"):
    record = lifecycle.build_handoff_record(
        number=7, state=state, head=head, task_identity="t", gates={}, red_gate=None,
        not_reverified=[], attempts={"review": 1}, next_job={"kind": "review"}, at="2026-10-05T08:00:00Z")
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
        with patch.object(queue, "_pr", return_value=pr), patch.object(queue, "_comments", return_value=[handoff_comment()]), \
                patch.object(queue, "_derive", wraps=lambda r, p, c, checks=None: lifecycle.derive_candidate(p, c)), \
                patch.object(queue, "_transition", return_value={}) as transition:
            queue.publish_job(Path("."), "o/r", 7, "repair", HEAD, task_identity="t", providers=["claude"])
        args, kwargs = transition.call_args
        self.assertEqual(args[3], "review-pending")
        self.assertEqual(kwargs["next_job"], workers.job_record("repair", HEAD, "t", 0, providers=["claude"]))


FAKE_LLM = r"""
import os, subprocess, sys
mode = os.environ.get("FAKE_MODE", "commit")
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
        self.job = {"kind": "repair", "number": 7, "head": self.head, "task_identity": "t", "attempt": 1}
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
            post_result=self.posted.append, workdir=str(self.work), worker="w1",
            env={**os.environ}, push_env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})

    def test_repair_pushes_through_harness(self):
        result = self.run_job("commit")
        self.assertEqual(result["status"], "pushed")
        remote = git(self.src, "rev-parse", "refs/heads/task")
        self.assertEqual(remote, result["pushed_head"])
        self.assertNotEqual(remote, self.head)
        self.assertTrue(self.posted[-1].startswith(workers.RESULT_PREFIX))
        self.assertEqual(json.loads(self.posted[-1][len(workers.RESULT_PREFIX):])["pushed_head"], remote)

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
