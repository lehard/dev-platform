from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import candidate_lifecycle  # noqa: E402
import integration_contour  # noqa: E402
import lifecycle_workers as workers  # noqa: E402
import post_review_finalization as finalization  # noqa: E402
import pr_review_gate as gate  # noqa: E402
import worker_preflight as wp  # noqa: E402

HEAD = "a" * 40
OPERATOR = {"operator": {"enabled": True}, "development_backlog": {"repository": "o/backlog"}}


def context(kinds, **fields):
    return wp.WorkerContext(ROOT, "o/r", frozenset(kinds), **fields)


def result(job, outcome, comment_id=1, login="bot"):
    body = workers.RESULT_PREFIX + json.dumps({"job": workers.job_id(job), "head": job["head"], "outcome": outcome})
    return {"id": comment_id, "body": body, "author_association": "OWNER", "user": {"login": login, "type": "User"}}


class Base(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)

    def healthy(self, config=None):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(wp, "_config", return_value=config if config is not None else OPERATOR))
        stack.enter_context(mock.patch.object(workers, "active_gh_token", return_value="t"))
        stack.enter_context(mock.patch.object(workers, "_gh_json", return_value={"permissions": {"push": True}}))
        stack.enter_context(mock.patch.object(wp, "check_shared_workspace",
                                              return_value=wp.ConditionResult(wp.PASSED, "ok")))
        stack.enter_context(mock.patch.object(wp.shutil, "which", return_value="/bin/tool"))
        return stack


class ConditionTests(Base):
    def test_all_unmet_conditions_are_named_at_once(self):
        self.healthy()
        unavailable = workers.WorkerError("no gh credential")
        import worker_credentials
        with mock.patch.object(workers, "active_gh_token", side_effect=unavailable), \
                mock.patch.object(worker_credentials, "llm_env",
                                  side_effect=worker_credentials.CredentialError("no token file")), \
                contextlib.redirect_stderr(io.StringIO()) as printed:
            with self.assertRaises(workers.PreflightRefused) as error:
                wp.run(context({"review"}, providers=("claude",)))
        self.assertIn("[github-credential]", str(error.exception))
        self.assertIn("[provider-credential]", str(error.exception))
        self.assertIn("2 condition(s)", str(error.exception))
        self.assertIn("trusted-contract: passed", printed.getvalue())

    def test_preflight_prints_nothing_on_stdout(self):
        self.healthy()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            wp.run(context({"finalize"}))
        self.assertEqual(out.getvalue(), "")

    def test_an_unevaluable_condition_refuses(self):
        self.healthy()
        with mock.patch.object(workers, "_gh_json", side_effect=ValueError("broken")), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(workers.PreflightRefused, "cannot be evaluated"):
                wp.run(context({"finalize"}))

    def test_operator_credential_without_write_access_refuses(self):
        self.healthy()
        with mock.patch.object(workers, "_gh_json", return_value={"permissions": {"push": False}}):
            with self.assertRaisesRegex(wp.PreflightRefusal, "no write access"):
                wp.check_github_credential(context({"review"}))

    def test_hosted_token_is_not_asked_for_repository_permissions(self):
        self.healthy(config={})
        with mock.patch.object(workers, "_gh_json", side_effect=AssertionError("must not read")):
            self.assertEqual(wp.check_github_credential(context({"review"})).state, wp.PASSED)

    def test_conditions_apply_by_kind(self):
        self.healthy()
        review = context({"review"})
        for check in (wp.check_finalize_tools, wp.check_process_tool, wp.check_backlog_access,
                      wp.check_post_merge_workspace, wp.check_writer_runtime):
            self.assertEqual(check(review).state, wp.NOT_APPLICABLE)
        self.assertEqual(wp.check_provider_credential(context({"finalize"})).state, wp.NOT_APPLICABLE)
        self.assertEqual(wp.check_provider_credential(review).state, wp.NOT_APPLICABLE)

    def test_missing_tools_refuse_for_their_kind(self):
        self.healthy()
        with mock.patch.object(wp.shutil, "which", return_value=None):
            with self.assertRaisesRegex(wp.PreflightRefusal, "OpenSpec"):
                wp.check_finalize_tools(context({"finalize"}))
            with self.assertRaisesRegex(wp.PreflightRefusal, "lsof"):
                wp.check_process_tool(context({"cleanup"}))

    def test_post_merge_needs_a_configured_readable_backlog(self):
        self.healthy(config={"operator": {"enabled": True}})
        with self.assertRaisesRegex(wp.PreflightRefusal, "repository is not configured"):
            wp.check_backlog_access(context({"cleanup"}))

    def test_one_usable_provider_of_several_passes(self):
        self.healthy()
        import worker_credentials
        with mock.patch.object(worker_credentials, "llm_env", side_effect=[{}, worker_credentials.CredentialError("x")]):
            self.assertEqual(wp.check_provider_credential(context({"review"}, providers=("codex", "claude"))).state,
                             wp.PASSED)

    def test_sandbox_refusal_names_the_runtime(self):
        import sandboxed_writer
        with mock.patch.object(sandboxed_writer, "require_macos",
                               side_effect=sandboxed_writer.SandboxedWriterError("proven only on macOS")):
            with self.assertRaisesRegex(wp.PreflightRefusal, "macOS"):
                wp.check_writer_runtime(context({"repair"}, writer=True))

    def test_every_environment_condition_used_in_code_is_registered(self):
        for condition in ("github-credential", "provider-credential", "writer-runtime", "process-tool"):
            self.assertIn(condition, wp.CONDITION_IDS)


class CliTests(Base):
    def test_refusal_exits_3_and_posts_no_claim(self):
        with mock.patch("worker_preflight.run", side_effect=workers.PreflightRefused("[github-credential] none")), \
                mock.patch.object(workers, "read_platform_config", return_value={}), \
                mock.patch.object(workers, "work_next") as work_next, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = workers.main(["work-next", "--kinds", "finalize", "--repo", "o/r", "--run"])
        self.assertEqual(code, workers.ENVIRONMENT_EXIT)
        self.assertIn("[github-credential]", err.getvalue())
        work_next.assert_not_called()

    def test_dry_run_runs_no_preflight(self):
        with mock.patch("worker_preflight.run") as run, \
                mock.patch.object(workers, "read_platform_config", return_value={}), \
                mock.patch.object(workers, "work_next", return_value={"status": "idle", "job": None}), \
                mock.patch.object(workers, "_coordinator_trust", return_value={}), \
                contextlib.redirect_stdout(io.StringIO()):
            workers.main(["work-next", "--kinds", "finalize", "--repo", "o/r", "--dry-run"])
        run.assert_not_called()

    def test_standalone_command_reads_no_job(self):
        with mock.patch("worker_preflight.run") as run, \
                mock.patch.object(workers, "read_platform_config", return_value={}), \
                mock.patch.object(workers, "work_next") as work_next:
            self.assertEqual(workers.main(["worker-preflight", "--kinds", "review", "--repo", "o/r",
                                           "--provider", "claude"]), 0)
        work_next.assert_not_called()
        self.assertEqual(run.call_args.args[0].providers, ("claude",))

    def test_standalone_refusal_exits_3(self):
        with mock.patch("worker_preflight.run", side_effect=workers.PreflightRefused("x")), \
                mock.patch.object(workers, "read_platform_config", return_value={}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(workers.main(["worker-preflight", "--kinds", "review", "--repo", "o/r"]),
                             workers.ENVIRONMENT_EXIT)


class ExecutedScriptTests(Base):
    def test_a_refusal_of_the_real_script_exits_3_without_a_traceback(self):
        import subprocess

        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "lifecycle_workers.py"), "worker-preflight",
                               "--kinds", "finalize", "--repo", "o/r"], cwd=ROOT, capture_output=True, text=True,
                              env={"PATH": str(bin_dir), "HOME": str(self.tmp)}, check=False)
        self.assertEqual(done.returncode, workers.ENVIRONMENT_EXIT, done.stderr)
        self.assertIn("[finalize-tools]", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_the_script_runs_through_the_importable_module(self):
        source = (ROOT / "template" / "scripts" / "lifecycle_workers.py").read_text()
        self.assertIn("raise SystemExit(lifecycle_workers.main())", source)


class ProviderGateTests(Base):
    JOB = {"kind": "review", "number": 7, "head": HEAD, "providers": ["claude"]}

    def test_unready_provider_is_refused_before_claim_and_probed_once(self):
        refused: list[dict] = []
        with mock.patch.object(workers, "provider_readiness", return_value={"claude": "Not logged in"}) as probe:
            check, _ = workers.review_provider_gate(ROOT, workdir=str(self.tmp), home_files=(), refused=refused)
            self.assertFalse(check(self.JOB))
            self.assertFalse(check(self.JOB))
        probe.assert_called_once()
        self.assertIn("Not logged in", refused[0]["error"])

    def test_ready_provider_passes_and_other_kinds_are_untouched(self):
        with mock.patch.object(workers, "provider_readiness", return_value={"claude": None}) as probe:
            check, readiness = workers.review_provider_gate(ROOT, workdir=str(self.tmp), home_files=(), refused=[])
            self.assertTrue(check({"kind": "finalize"}))
            probe.assert_not_called()
            self.assertTrue(check(self.JOB))
        self.assertEqual(readiness, {"claude": None})


class EnvironmentClassTests(Base):
    JOB = {"kind": "review", "number": 7, "head": HEAD, "attempt": 0}

    def comments(self, *outcomes):
        return [result(self.JOB, outcome, index + 1) for index, outcome in enumerate(outcomes)]

    def trust(self):
        return {"trusted_apps": frozenset(), "trusted_writers": frozenset({"bot"})}

    def test_environment_releases_are_counted_apart(self):
        rows = self.comments("released: environment: github-credential: gone", "released: WorkerError: x")
        self.assertEqual(workers.release_count(self.JOB, rows, **self.trust()), 1)
        self.assertEqual(workers.environment_release_count(self.JOB, rows, **self.trust()), 1)

    def test_old_release_comments_count_as_before(self):
        rows = self.comments("released: RuntimeError: a", "released: WorkerError: b")
        self.assertEqual(workers.release_count(self.JOB, rows, **self.trust()), 2)

    def test_environment_releases_leave_the_job_claimable_up_to_their_bound(self):
        three = self.comments(*["released: environment: provider-credential: x"] * workers.MAX_RELEASES)
        self.assertTrue(workers.is_claimable(self.JOB, three, **self.trust()))
        spent = self.comments(*["released: environment: provider-credential: x"] * workers.MAX_ENVIRONMENT_RELEASES)
        self.assertFalse(workers.is_claimable(self.JOB, spent, **self.trust()))

    def test_release_claim_writes_the_class_and_counts_its_own_kind(self):
        posted = []
        rows = self.comments("released: WorkerError: earlier")
        with mock.patch.object(workers, "i_won", return_value=True):
            count = workers.release_claim(self.JOB, "w", workers.EnvironmentFailure("github-credential", "gone"),
                                          comments_for=lambda _: rows, post_comment=lambda _, body: posted.append(body),
                                          **self.trust())
            ordinary = workers.release_claim(self.JOB, "w", workers.WorkerError("defect"), comments_for=lambda _: rows,
                                             post_comment=lambda _, body: posted.append(body), **self.trust())
        self.assertEqual((count, ordinary), (1, 2))
        self.assertIn("released: environment: github-credential: gone", posted[0])
        self.assertIn("released: WorkerError: defect", posted[1])

    def test_gate_function_reports_its_condition(self):
        with self.assertRaises(workers.EnvironmentFailure) as error:
            with mock.patch.object(workers.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")):
                workers.active_gh_token(self.tmp, {})
        self.assertEqual(error.exception.condition, "github-credential")

    def test_environment_bound_is_an_operational_escalation(self):
        red = {"name": "review", "evidence": {"cause": workers.ENVIRONMENT_RELEASE_CAUSE, "releases": 5}}
        self.assertTrue(gate.operational_escalation(red))
        self.assertFalse(gate.operational_escalation({"name": "review", "evidence": {"cause": "other"}}))

    def test_post_merge_limit_counts_each_class_against_its_own_bound(self):
        job = {"kind": "cleanup", "number": 7, "head": HEAD, "attempt": 0}
        candidate = {"number": 7}

        def rows(*outcomes):
            return [result(job, outcome, index + 1) for index, outcome in enumerate(outcomes)]

        env = "released: environment: process-tool: x"
        limit = candidate_lifecycle.post_merge_release_limit
        self.assertIsNone(limit(candidate, job, rows(env, env, env), frozenset(), frozenset({"bot"})))
        spent = limit(candidate, job, rows(*[env] * workers.MAX_ENVIRONMENT_RELEASES), frozenset(), frozenset({"bot"}))
        self.assertEqual(spent["releases"], workers.MAX_ENVIRONMENT_RELEASES)
        failed = limit(candidate, job, rows(env, *["released: WorkerError: x"] * workers.MAX_RELEASES),
                       frozenset(), frozenset({"bot"}))
        self.assertEqual(failed["releases"], workers.MAX_RELEASES)

    def test_post_merge_environment_error_is_the_same_class(self):
        self.assertTrue(issubclass(integration_contour.PostMergeEnvironmentError, workers.EnvironmentFailure))

    def test_finalize_environment_failure_is_no_block(self):
        adapter = mock.Mock()
        adapter._derive.return_value = {}
        job = {"kind": "finalize", "number": 7, "head": HEAD, "task_identity": {"change": "c"}, "attempt": 0}
        with mock.patch.object(workers, "prepare_checkout",
                               side_effect=workers.EnvironmentFailure("github-credential", "gone")), \
                mock.patch.object(workers, "build_job", return_value=job):
            with self.assertRaises(workers.EnvironmentFailure):
                finalization.run_claimed_finalize(
                    self.tmp, "o/r", {"gates": {}}, job, source_repo="s", branch="b", current_head=lambda: HEAD,
                    post_result=mock.Mock(), workdir=str(self.tmp), worker="w", adapter=adapter, claim_current=lambda: True)
        adapter._transition.assert_not_called()


class RunnerTests(Base):
    def test_runner_constant_matches_the_worker(self):
        source = (ROOT / "scripts" / "post_merge_runner.py").read_text()
        self.assertIn(f"ENVIRONMENT_EXIT = {workers.ENVIRONMENT_EXIT}", source)


if __name__ == "__main__":
    unittest.main()
