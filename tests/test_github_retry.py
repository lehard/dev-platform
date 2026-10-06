from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

common = load_platform_module("_platform_common", SCRIPTS / "_platform_common.py")
managed = load_platform_module("managed_task", SCRIPTS / "managed_task.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
project_status = load_platform_module("managed_project_status", SCRIPTS / "managed_project_status.py")
publication_state = load_platform_module("publication_state", SCRIPTS / "publication_state.py")


class GithubRetryTests(unittest.TestCase):
    def run_retry(self, command: list[str], results: list[subprocess.CompletedProcess], attempts: int = 4):
        pause = mock.Mock()
        with mock.patch.object(common.subprocess, "run", side_effect=results) as run:
            result = common.run_github_with_retry(command, cwd=Path("/tmp"), attempts=attempts, sleep=pause)
        return result, run, pause

    def failure(self, detail: str):
        return subprocess.CompletedProcess([], 1, "", detail)

    def test_project_graphql_queries_retry_but_mutations_run_once(self):
        reset = self.failure("read tcp: connection reset by peer")
        success = subprocess.CompletedProcess([], 0, '{"data": {"ok": true}}', "")
        with mock.patch.object(common.subprocess, "run", side_effect=[reset, success]) as run, \
             mock.patch("time.sleep"):
            project_status._graphql(Path("/tmp"), {}, "query { viewer { login } }", {})
        self.assertEqual(run.call_count, 2)
        with mock.patch.object(common.subprocess, "run", side_effect=[reset]) as run:
            with self.assertRaises(project_status.ManagedProjectStatusError):
                project_status._graphql(Path("/tmp"), {}, "mutation { x }", {})
        self.assertEqual(run.call_count, 1)

    def test_auth_status_transient_failure_is_retried_not_treated_as_stale_credential(self):
        reset = self.failure("dial tcp: i/o timeout")
        ok = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(common.subprocess, "run", side_effect=[reset, ok]) as run, mock.patch("time.sleep"):
            self.assertTrue(common._gh_auth_ok(Path("/tmp"), {}))
        self.assertEqual(run.call_count, 2)

    def test_required_check_reads_retry_and_failed_check_names_are_not_transient(self):
        head = "a" * 40
        reset = self.failure("read tcp: connection reset by peer")
        view = subprocess.CompletedProcess([], 0, '{"state": "OPEN", "headRefOid": "%s"}' % head, "")
        checks = subprocess.CompletedProcess([], 1, '[{"name": "timeout guard", "state": "FAILURE", "workflow": "ci", "link": ""}]', "")
        calls: list[list[str]] = []
        responses = {"view": [reset, view], "checks": [checks]}

        def fake(command, **_kwargs):
            calls.append(command)
            return responses[command[2]].pop(0) if responses[command[2]] else checks

        with mock.patch.object(common.subprocess, "run", side_effect=fake), mock.patch("time.sleep"):
            state = publication_state.required_check_state_for_ref(Path("/tmp"), {}, "7", head)
        # The reset view is retried once; the failed checks payload (whose check name
        # contains "timeout") is classified from stderr only and not retried.
        self.assertEqual([command[2] for command in calls], ["view", "view", "checks"])
        self.assertIsNotNone(state)

    def test_queue_main_read_retries_transient_git_failure(self):
        ok = subprocess.CompletedProcess([], 0, "%s\trefs/heads/main\n" % ("c" * 40), "")
        args = ["ls-remote", "origin", "refs/heads/main"]
        reset = common.GitCommandError(args, None, subprocess.CompletedProcess(args, 128, "", "Connection reset by peer"))
        with mock.patch.object(queue, "run_git", side_effect=[reset, ok]) as run, mock.patch("time.sleep"):
            self.assertEqual(queue._main(Path("/tmp")), "c" * 40)
        self.assertEqual(run.call_count, 2)
        missing = common.GitCommandError(args, None, subprocess.CompletedProcess(args, 128, "", "fatal: repository not found"))
        with mock.patch.object(queue, "run_git", side_effect=[missing]):
            with self.assertRaises(queue.QueueError):
                queue._main(Path("/tmp"))

    def test_connection_reset_then_success_retries(self):
        success = subprocess.CompletedProcess([], 0, "{}", "")
        result, run, pause = self.run_retry(["gh", "api", "repos/acme/project"], [self.failure("connection reset by peer"), success])
        self.assertIs(result, success)
        self.assertEqual(run.call_count, 2)
        pause.assert_called_once_with(1)

    def test_non_transient_fails_immediately(self):
        failure = self.failure("HTTP 403: Resource not accessible")
        result, run, pause = self.run_retry(["gh", "issue", "view", "7"], [failure])
        self.assertIs(result, failure)
        self.assertEqual(run.call_count, 1)
        pause.assert_not_called()

    def test_persistent_transient_stops_at_bound_and_backoff_caps(self):
        failure = self.failure("TLS handshake timeout")
        result, run, pause = self.run_retry(["gh", "pr", "view", "7"], [failure] * 6, attempts=6)
        self.assertIs(result, failure)
        self.assertEqual(run.call_count, 6)
        self.assertEqual(pause.call_args_list, [mock.call(n) for n in (1, 2, 4, 8, 8)])

    def test_post_is_never_retried(self):
        for flags in (["-X", "POST"], ["--method=POST"], ["-XPOST"], ["-f", "body=hello"], ["-fbody=hello"], ["--input=data.json"]):
            with self.subTest(flags=flags):
                _, run, pause = self.run_retry(["gh", "api", "repos/acme/project/issues", *flags], [self.failure("HTTP 503")])
                self.assertEqual(run.call_count, 1)
                pause.assert_not_called()

    def test_read_classifier_and_transient_diagnostics(self):
        self.assertTrue(common.is_github_read(["gh", "api", "-X", "GET", "repos/acme/project", "-f", "page=1"]))
        self.assertFalse(common.is_github_read(["gh", "issue", "create"]))
        self.assertFalse(common.is_github_read(["git", "status"]))
        for detail in ("unexpected EOF", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "secondary rate limit"):
            self.assertTrue(common.is_transient_github_failure(detail), detail)

    def test_attempt_configuration(self):
        for value, expected in (("2", 2), ("0", 1), ("invalid", 4)):
            with mock.patch.dict(os.environ, {common.GITHUB_RETRY_ATTEMPTS_ENV: value}):
                self.assertEqual(common.github_retry_attempts(), expected)

    def test_managed_and_queue_reads_use_retry(self):
        for invoke in (
            lambda: managed.run_json(["gh", "api", "repos/acme/project/issues/7"], Path("/tmp")),
            lambda: queue._gh(Path("/tmp"), "api", "repos/acme/project/issues/7"),
        ):
            with mock.patch.object(common.subprocess, "run", side_effect=[self.failure("connection reset"), subprocess.CompletedProcess([], 0, '{"number":7}', "")]) as run, mock.patch("time.sleep") as pause:
                self.assertEqual(invoke(), {"number": 7})
                self.assertEqual(run.call_count, 2)
                pause.assert_called_once_with(1)

    def test_managed_and_queue_mutations_run_once(self):
        for invoke, error in (
            (lambda: managed.run(["gh", "api", "-X", "POST", "repos/acme/project/issues"], Path("/tmp")), managed.ManagedTaskError),
            (lambda: queue._gh(Path("/tmp"), "api", "repos/acme/project/issues", data={"body": "hello"}), queue.QueueError),
        ):
            with mock.patch.object(common.subprocess, "run", return_value=self.failure("connection reset")) as run, mock.patch("time.sleep") as pause:
                with self.assertRaises(error):
                    invoke()
                self.assertEqual(run.call_count, 1)
                pause.assert_not_called()
