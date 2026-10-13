"""GitHub-hosted placement of lifecycle workers: plan, preflight, outcomes and workflow structure."""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402


def setUpModule() -> None:
    # Other test modules put the source-checkout scripts/ wrappers ahead of template/scripts on sys.path.
    sys.path.insert(0, str(ROOT / "template" / "scripts"))


lifecycle = load_platform_module("candidate_lifecycle", ROOT / "template/scripts/candidate_lifecycle.py")
workers = load_platform_module("lifecycle_workers", ROOT / "template/scripts/lifecycle_workers.py")
hosted = load_platform_module("hosted_workers", ROOT / "template/scripts/hosted_workers.py")

WORKFLOW = ROOT / ".github" / "workflows" / "lifecycle-workers.yml"
CANARY = "ghs_CANARY_SECRET_TOKEN_VALUE_0123456789"
PROVIDER_CANARY = "sk-ant-oat01-CANARY-PROVIDER-SECRET"
ENV = {
    "PATH": os.environ.get("PATH", ""),
    "DEV_PLATFORM_HOSTED_KINDS": "review,finalize",
    "PREFLIGHT_APP_CLIENT_ID_SET": "true", "PREFLIGHT_APP_PRIVATE_KEY_SET": "true", "PREFLIGHT_PROVIDER_SECRET_SET": "true",
    "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
    "GH_TOKEN": CANARY, "CLAUDE_CODE_OAUTH_TOKEN": PROVIDER_CANARY,
}


def env_for(name: str, **overrides: str) -> dict[str, str]:
    env = {**ENV, "DEV_PLATFORM_WORKER": f"gha-123-2-{name}"}
    env.update(overrides)
    return {key: value for key, value in env.items() if value is not None}


class FakeQueue:
    """Stands in for the publication queue's coordinator preflight, which has its own tests."""

    def __init__(self, fail_phase: str | None = None):
        self.fail_phase, self.calls = fail_phase, []

    def preflight(self, root, mode, phase, env):
        self.calls.append(phase)
        if phase == self.fail_phase:
            return {"state": "error", "mode": mode, "phase": phase, "reason": "queue says no",
                    "checks": [{"name": "queue-check", "status": "failed", "detail": "queue says no"}]}
        return {"state": "ok", "mode": mode, "phase": phase, "checks": [{"name": f"queue-{phase}", "status": "ok", "detail": "fine"}]}


class Probes:
    def __init__(self, leaks=(), limitation=None):
        self.leaks, self.limitation, self.probed, self.readied = list(leaks), limitation, 0, 0

    def probe(self, env, scratch):
        self.probed += 1
        return self.leaks

    def readiness(self, root, providers, *, workdir, home_files=()):
        self.readied += 1
        return {name: self.limitation for name in providers}


def run_preflight(name="review", phase="all", env=None, queue=None, probes=None, tools=True):
    probes = probes or Probes()
    queue = queue or FakeQueue()
    result = hosted.preflight(Path("/unused"), name, phase, env if env is not None else env_for(name), queue=queue,
                              readiness=probes.readiness, probe=probes.probe,
                              which=(lambda tool: "/bin/" + tool) if tools else (lambda tool: None))
    return result, queue, probes


class PlanTests(unittest.TestCase):
    def test_enabled_kinds_become_a_class_matrix(self):
        self.assertEqual(hosted.plan("review,finalize"), {"include": [
            {"class": "review", "kinds": "review"}, {"class": "finalize", "kinds": "finalize"}]})
        self.assertEqual(hosted.plan(" finalize , finalize "), {"include": [{"class": "finalize", "kinds": "finalize"}]})

    def test_missing_setting_is_an_error_naming_it(self):
        for raw in (None, "", " , "):
            with self.subTest(raw=raw), self.assertRaisesRegex(hosted.HostedError, "DEV_PLATFORM_HOSTED_KINDS is required"):
                hosted.plan(raw)

    def test_unknown_kind_is_named(self):
        with self.assertRaisesRegex(hosted.HostedError, "unknown job kind 'bogus'"):
            hosted.plan("review,bogus")

    def test_kinds_without_a_hosted_executor_are_refused_with_their_basis(self):
        for kind, basis in (("repair", "BR-576"), ("integration-repair", "BR-576"), ("retrospective", "machine-local"),
                            ("terminal-reconciliation", "machine-local"), ("cleanup", "machine-local")):
            with self.subTest(kind=kind), self.assertRaisesRegex(hosted.HostedError, rf"{kind}.*{basis}.*BR-433"):
                hosted.plan(f"review,{kind}")

    def test_every_lifecycle_kind_is_either_hosted_or_refused(self):
        self.assertEqual(hosted.HOSTED_KINDS | set(hosted.UNHOSTED), set(workers.JOB_KINDS) - {"contribution-integration"})
        self.assertFalse(hosted.HOSTED_KINDS & set(hosted.UNHOSTED))

    def test_cli_exit_codes(self):
        for argv, code in ((["hosted-plan", "--kinds", "review"], 0), (["hosted-plan", "--kinds", ""], 2),
                           (["hosted-plan", "--kinds", "repair"], 2)):
            with self.subTest(argv=argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(workers.main(argv), code)


class IdentityTests(unittest.TestCase):
    def test_identity_is_unique_per_attempt_and_class_and_valid(self):
        first = hosted.worker_identity({"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1"}, "review")
        again = hosted.worker_identity({"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "2"}, "review")
        other = hosted.worker_identity({"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1"}, "finalize")
        self.assertEqual(first, "gha-9-1-review")
        self.assertEqual(len({first, again, other}), 3)
        self.assertEqual(workers.validate_worker_identity(first), first)

    def test_missing_run_numbers_are_named(self):
        for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            env = {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1", name: "x"}
            with self.subTest(name=name), self.assertRaisesRegex(hosted.HostedError, name):
                hosted.worker_identity(env, "review")


class PreflightTests(unittest.TestCase):
    def test_valid_configuration_passes_every_phase_for_every_class(self):
        for name in hosted.CLASSES:
            for phase in hosted.PHASES:
                with self.subTest(name=name, phase=phase):
                    result, _, _ = run_preflight(name, phase)
                    self.assertEqual(result["state"], "ok", result)
                    self.assertTrue(all(check["status"] == "ok" for check in result["checks"]))

    def test_each_failing_input_is_named_and_stops_the_run(self):
        cases = [
            ("unknown class", "nope", "all", env_for("review"), "class"),
            ("kinds unset", "review", "all", env_for("review", DEV_PLATFORM_HOSTED_KINDS=""), "DEV_PLATFORM_HOSTED_KINDS"),
            ("kind unhosted", "review", "all", env_for("review", DEV_PLATFORM_HOSTED_KINDS="repair"), "DEV_PLATFORM_HOSTED_KINDS"),
            ("class has no enabled kind", "finalize", "all", env_for("finalize", DEV_PLATFORM_HOSTED_KINDS="review"),
             "DEV_PLATFORM_HOSTED_KINDS"),
            ("provider flag", "review", "inputs", env_for("review", PREFLIGHT_PROVIDER_SECRET_SET="false"), "PREFLIGHT_PROVIDER_SECRET_SET"),
            ("worker identity", "review", "inputs", env_for("review", DEV_PLATFORM_WORKER="someone-else"), "DEV_PLATFORM_WORKER"),
            ("run id", "review", "inputs", env_for("review", GITHUB_RUN_ID="x"), "GITHUB_RUN_ID"),
        ]
        for label, name, phase, env, expected in cases:
            with self.subTest(label):
                result, _, probes = run_preflight(name, phase, env)
                self.assertEqual(result["state"], "error")
                self.assertEqual(result["checks"][-1]["name"], expected)
                self.assertEqual((probes.probed, probes.readied), (0, 0))

    def test_finalize_does_not_need_the_provider_secret(self):
        result, _, probes = run_preflight("finalize", "all", env_for("finalize", PREFLIGHT_PROVIDER_SECRET_SET="false", CLAUDE_CODE_OAUTH_TOKEN=None))
        self.assertEqual(result["state"], "ok", result)
        self.assertEqual(probes.readied, 0)

    def test_queue_failure_stops_before_the_hosted_probes(self):
        for phase in ("inputs", "runtime"):
            with self.subTest(phase=phase):
                result, _, probes = run_preflight("review", "all", queue=FakeQueue(fail_phase=phase))
                self.assertEqual(result["checks"][-1]["name"], "queue-check")
                self.assertEqual((probes.probed, probes.readied), (0, 0))

    def test_missing_tool_is_named(self):
        result, _, probes = run_preflight("finalize", "runtime", tools=False)
        self.assertEqual(result["checks"][-1]["name"], "tool:openspec")
        self.assertEqual(probes.probed, 0)

    def test_credential_leak_in_a_child_fails_with_categories_only(self):
        result, _, probes = run_preflight("review", "runtime", probes=Probes(leaks=["github-environment-credential", "git-credential-configuration"]))
        failed = result["checks"][-1]
        self.assertEqual(failed["name"], "credential-boundary")
        self.assertIn("github-environment-credential", failed["detail"])
        self.assertEqual(probes.readied, 0)

    def test_empty_provider_secret_is_named_at_runtime(self):
        result, _, probes = run_preflight("review", "runtime", env_for("review", CLAUDE_CODE_OAUTH_TOKEN=""))
        self.assertEqual(result["checks"][-1]["name"], "CLAUDE_CODE_OAUTH_TOKEN")
        self.assertEqual(probes.readied, 0)

    def test_provider_limitation_fails_and_is_redacted(self):
        probes = Probes(limitation=f"claude exited 1: invalid token {PROVIDER_CANARY} and {CANARY}")
        result, _, _ = run_preflight("review", "runtime", probes=probes)
        self.assertEqual(result["checks"][-1]["name"], "claude-runtime")
        text = json.dumps(result)
        self.assertNotIn(PROVIDER_CANARY, text)
        self.assertNotIn(CANARY, text)

    def test_no_secret_value_appears_in_any_result(self):
        for phase in hosted.PHASES:
            result, _, _ = run_preflight("review", phase)
            text = json.dumps(result)
            self.assertNotIn(CANARY, text)
            self.assertNotIn(PROVIDER_CANARY, text)

    def test_mode_and_phase_are_validated(self):
        with self.assertRaises(hosted.HostedError):
            hosted.preflight(Path("/unused"), "review", "all", ENV, mode="local", queue=FakeQueue())
        with self.assertRaises(hosted.HostedError):
            hosted.preflight(Path("/unused"), "review", "weird", ENV, queue=FakeQueue())

    def test_cli_exit_code_follows_the_result(self):
        args = SimpleNamespace(command="hosted-preflight", mode="ci", hosted_class="review", phase="inputs")
        with patch.object(hosted, "preflight", return_value={"state": "ok"}), redirect_stdout(io.StringIO()):
            self.assertEqual(hosted.run_command(args, Path("/unused"), ENV), 0)
        with patch.object(hosted, "preflight", return_value={"state": "error"}), redirect_stdout(io.StringIO()):
            self.assertEqual(hosted.run_command(args, Path("/unused"), ENV), 1)


class CredentialBoundaryTests(unittest.TestCase):
    def test_a_real_child_of_the_credential_free_environment_sees_no_credential(self):
        env = {**os.environ, "GH_TOKEN": CANARY, "GITHUB_TOKEN": CANARY, "GITHUB_PAT": CANARY, "SSH_AUTH_SOCK": "/tmp/agent",
               "GIT_ASKPASS": "/bin/echo", "GCM_CREDENTIAL_CACHE_OPTIONS": "x", "GIT_CONFIG_COUNT": "1",
               "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": "store", "GH_ENTERPRISE_TOKEN": CANARY}
        with tempfile.TemporaryDirectory() as scratch:
            self.assertEqual(hosted.probe_credential_boundary(env, Path(scratch)), [])

    def test_violations_are_categories_never_values(self):
        report = {"env": ["PATH", "GH_TOKEN", "SSH_AUTH_SOCK", "GIT_CONFIG_COUNT"], "git": ["credential.helper", "user.name"],
                  "gh_config": "/nonexistent-gh-dir-for-test"}
        found = hosted.credential_boundary_violations(report)
        self.assertEqual(sorted(found), ["askpass-or-ssh-agent", "git-config-injection", "git-credential-configuration",
                                         "github-environment-credential"])
        self.assertEqual(hosted.credential_boundary_violations({"env": ["PATH", "HOME", "GIT_CONFIG_GLOBAL", "GH_CONFIG_DIR"],
                                                                "git": ["user.name"], "gh_config": "/nonexistent-gh-dir-for-test"}), [])

    def test_an_existing_gh_configuration_directory_is_a_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {"env": [], "git": [], "gh_config": directory}
            self.assertEqual(hosted.credential_boundary_violations(report), ["gh-configuration"])

    def test_a_child_that_cannot_report_fails_explicitly(self):
        class Done:
            returncode, stdout = 0, "not json"

        with tempfile.TemporaryDirectory() as scratch, self.assertRaisesRegex(hosted.HostedError, "unreadable report"):
            hosted.probe_credential_boundary({}, Path(scratch), runner=lambda *a, **k: Done())
        with tempfile.TemporaryDirectory() as scratch, self.assertRaisesRegex(hosted.HostedError, "could not start"):
            hosted.probe_credential_boundary({}, Path(scratch), runner=lambda *a, **k: (_ for _ in ()).throw(OSError("x")))


class OutcomeTests(unittest.TestCase):
    JOB = {"kind": "review", "number": 7, "head": "a" * 40}

    def test_outcomes_are_distinct_and_failures_are_red(self):
        cases = [
            ({"status": "idle", "job": None}, 0, "idle", False),
            ({"status": "lost", "job": self.JOB}, 0, "abandoned-lost", False),
            ({"status": "stale", "job": self.JOB}, 0, "abandoned-stale", False),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "reviewed"}}, 0, "job-reviewed", False),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "reused"}}, 0, "job-reused", False),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "finalized"}}, 0, "job-finalized", False),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "discarded"}}, 0, "job-discarded", False),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "blocked-retryable"}}, 0, "job-blocked-retryable", True),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "blocked-escalation"}}, 0, "job-blocked-escalation", True),
            ({"status": "claimed", "job": self.JOB, "execution": {"status": "weird"}}, 0, "job-unknown", True),
            ({"status": "idle", "providers": {"ready": [], "unavailable": {"claude": "cannot authenticate"}}}, 0, "provider-unavailable", True),
            (None, 2, "refused-or-failed", True),
            (None, 0, "refused-or-failed", True),
        ]
        for result, code, outcome, failed in cases:
            with self.subTest(outcome=outcome, result=result):
                self.assertEqual(hosted.classify(result, code)[:2], (outcome, failed))

    def test_provider_unavailable_names_the_limitation(self):
        text, failed = hosted.summarize({"status": "idle", "providers": {"unavailable": {"claude": "cannot authenticate"}}}, 0,
                                        "review", "gha-1-1-review")
        self.assertTrue(failed)
        self.assertIn("cannot authenticate", text)

    def test_no_summary_claims_a_candidate_is_done(self):
        for execution in ("reviewed", "reused", "finalized", "returned-to-review"):
            text, _ = hosted.summarize({"status": "claimed", "job": self.JOB, "execution": {"status": execution}}, 0, "review", "w")
            self.assertNotRegex(text.lower().replace("does not assert the candidate is done", ""), r"\bdone\b|\bmerged\b|\bcomplete")

    def test_last_json_line_of_a_log_is_the_result(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "log"
            log.write_text('diagnostic line\n{"status": "idle", "job": null}\n', encoding="utf-8")
            self.assertEqual(hosted.last_json_object(log), {"status": "idle", "job": None})
            log.write_text("no json here\n", encoding="utf-8")
            self.assertIsNone(hosted.last_json_object(log))
            self.assertIsNone(hosted.last_json_object(Path(directory) / "missing"))

    def test_cli_writes_the_summary_and_follows_failure(self):
        env = {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1"}
        with tempfile.TemporaryDirectory() as directory:
            log, summary = Path(directory) / "log", Path(directory) / "summary.md"
            log.write_text('{"status": "idle", "job": null}\n', encoding="utf-8")
            args = SimpleNamespace(command="hosted-outcome", hosted_class="review", result=str(log), exit_code=0, summary=str(summary))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(hosted.run_command(args, Path("/unused"), env), 0)
            self.assertIn("gha-9-1-review", summary.read_text(encoding="utf-8"))
            args.exit_code = 2
            with redirect_stdout(io.StringIO()):
                self.assertEqual(hosted.run_command(args, Path("/unused"), env), 1)

    def test_redaction_removes_values_and_token_shapes(self):
        text = hosted.redact(f"a {CANARY} b {PROVIDER_CANARY} c ghp_{'x' * 30} d", ENV)
        for secret in (CANARY, PROVIDER_CANARY, "ghp_"):
            self.assertNotIn(secret, text)


HEAD, NEW = "a" * 40, "b" * 40
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)


def handoff_comment(head=HEAD, number=7):
    record = lifecycle.build_handoff_record(
        number=number, state="review-pending", head=head, task_identity="t", gates={}, red_gate=None,
        not_reverified=[], attempts={"review": 1}, next_job={"kind": "review"}, at="2026-10-05T08:00:00Z")
    return {"id": 1, "author_association": "OWNER", "body": lifecycle.marker_body(record)}


class HostedRestartAndDuplicateTests(unittest.TestCase):
    """Hosted runs inherit the head-bound claim contract; these pin it for run-attempt identities."""

    def setUp(self):
        self.store = {7: [handoff_comment()]}
        self.pr = {"number": 7, "head": {"sha": HEAD}, "state": "open"}

    def post(self, number, body):
        self.store[number].append({"id": 100 + len(self.store[number]), "author_association": "OWNER", "body": body})

    def work(self, worker, now=NOW, **extra):
        return workers.work_next(frozenset({"review"}), list_prs=lambda: [self.pr], comments_for=lambda n: list(self.store[n]),
                                 post_comment=self.post, worker=worker, now=now, **extra)

    def test_overlapping_hosted_runs_have_one_owner(self):
        self.assertEqual(self.work("gha-1-1-review")["status"], "claimed")
        self.assertEqual(self.work("gha-2-1-review")["status"], "idle")

    def test_a_killed_run_is_reclaimed_after_its_claim_expires_by_the_next_attempt(self):
        first = self.work("gha-1-1-review", ttl_seconds=1800)
        self.assertEqual(first["status"], "claimed")
        self.assertEqual(self.work("gha-1-2-review", now=NOW + timedelta(minutes=29))["status"], "idle")
        self.assertEqual(self.work("gha-1-2-review", now=NOW + timedelta(minutes=31))["status"], "claimed")

    def test_the_workflow_timeout_is_shorter_than_the_claim_lifetime(self):
        timeout = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["work"]["timeout-minutes"]
        self.assertLess(timeout * 60, 1800)

    def test_a_moved_head_abandons_the_claim_and_discards_old_results(self):
        result = self.work("gha-3-1-review", current_head=lambda number: NEW)
        self.assertEqual(result["status"], "stale")
        self.assertFalse(workers.result_is_current(result["job"], HEAD, NEW))

    def test_hosted_kinds_never_reach_a_merge_call(self):
        # Merging belongs to the publication queue alone; the modules a hosted worker runs for its kinds
        # contain no merge request to GitHub.
        for module in ("lifecycle_workers.py", "hosted_workers.py", "pr_review_gate.py", "post_review_finalization.py"):
            text = (ROOT / "template" / "scripts" / module).read_text(encoding="utf-8")
            self.assertNotRegex(text, r'"pr",\s*"merge"|/merge\b|enablePullRequestAutoMerge', module)


class WorkflowStructureTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.triggers = self.workflow.get("on", self.workflow.get(True))
        self.work = self.workflow["jobs"]["work"]
        self.steps = self.work["steps"]

    def index(self, fragment):
        return next(i for i, step in enumerate(self.steps)
                    if fragment in str(step.get("run", "")) or fragment in str(step.get("uses", "")) or fragment == step.get("name"))

    def test_trigger_set_is_exactly_dispatch_queue_completion_and_schedule(self):
        self.assertEqual(set(self.triggers), {"workflow_dispatch", "workflow_run", "schedule"})

    def test_workflow_run_names_only_the_publication_queue_completed(self):
        run = self.triggers["workflow_run"]
        self.assertEqual(run["workflows"], ["Dev Platform publication queue"])
        self.assertEqual(run["types"], ["completed"])
        self.assertEqual(set(run), {"workflows", "types"})

    def test_schedule_is_one_ten_minute_cron(self):
        self.assertEqual(self.triggers["schedule"], [{"cron": "*/10 * * * *"}])

    def test_no_pull_request_style_trigger(self):
        for forbidden in ("pull_request", "pull_request_target", "issue_comment", "push"):
            self.assertNotIn(forbidden, self.triggers)

    def test_triggering_event_payload_is_never_used(self):
        self.assertNotIn("github.event.workflow_run", self.text)

    def test_node_satisfies_the_claude_cli_engine(self):
        versions = [
            str(step["with"]["node-version"])
            for job in self.workflow["jobs"].values()
            for step in job["steps"]
            if "actions/setup-node" in str(step.get("uses", ""))
        ]
        self.assertTrue(versions, "no setup-node step found")
        for version in versions:
            with self.subTest(version=version):
                self.assertRegex(version, r"^\d+\.\d+\.\d+$")
                self.assertGreaterEqual(int(version.split(".")[0]), 22)

    def test_every_job_runs_default_branch_code_only(self):
        for name, job in self.workflow["jobs"].items():
            with self.subTest(job=name):
                self.assertIn("default_branch", job["if"])
                for step in job["steps"]:
                    if "actions/checkout" in str(step.get("uses", "")):
                        self.assertEqual(step["with"]["ref"], "${{ github.event.repository.default_branch }}")
                        self.assertIs(step["with"]["persist-credentials"], False)
        self.assertNotRegex(self.text, r"github\.head_ref|github\.event\.pull_request|pull_request\.head|refs/pull/")

    def test_no_expression_is_interpolated_into_a_shell_script(self):
        for name, job in self.workflow["jobs"].items():
            for step in job["steps"]:
                with self.subTest(job=name, step=step.get("name")):
                    self.assertNotIn("${{", str(step.get("run", "")))

    def test_plan_job_has_no_token_and_no_secret(self):
        plan = self.workflow["jobs"]["plan"]
        text = yaml.safe_dump(plan)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("create-github-app-token", text)

    def test_token_rights_match_the_class_table_and_nothing_wider(self):
        token = self.steps[self.index("actions/create-github-app-token")]["with"]
        granted = {key.removeprefix("permission-"): value for key, value in token.items() if key.startswith("permission-")}
        for name, spec in hosted.CLASSES.items():
            with self.subTest(name=name):
                self.assertEqual(granted, spec["permissions"])
        self.assertEqual(token["repositories"], "${{ steps.repo.outputs.name }}")
        for forbidden in ("workflows", "administration", "actions", "id-token"):
            self.assertNotIn(f"permission-{forbidden}", token)
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.work["permissions"], {"contents": "read"})

    def test_class_matrix_comes_from_the_plan_and_serialises_per_class(self):
        self.assertEqual(self.work["strategy"]["matrix"], "${{ fromJSON(needs.plan.outputs.matrix) }}")
        self.assertIs(self.work["concurrency"]["cancel-in-progress"], False)
        self.assertIn("matrix.class", self.work["concurrency"]["group"])

    def test_worker_identity_is_the_hosted_format(self):
        identity = self.work["env"]["DEV_PLATFORM_WORKER"]
        self.assertEqual(identity, "gha-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.class }}")
        self.assertEqual(hosted.worker_identity({"GITHUB_RUN_ID": "5", "GITHUB_RUN_ATTEMPT": "1"}, "review"), "gha-5-1-review")

    def test_preflight_order_and_presence_flags_only(self):
        inputs = self.index("--phase inputs")
        token = self.index("actions/create-github-app-token")
        runtime = self.index("--phase runtime")
        worker = self.index("Run one claimed job")
        outcome = self.index("Report the outcome")
        self.assertLess(inputs, token)
        self.assertLess(token, runtime)
        self.assertLess(runtime, worker)
        self.assertLess(worker, outcome)
        env = self.steps[inputs]["env"]
        self.assertEqual(set(env), {"PREFLIGHT_APP_CLIENT_ID_SET", "PREFLIGHT_APP_PRIVATE_KEY_SET", "PREFLIGHT_PROVIDER_SECRET_SET"})
        for value in env.values():
            self.assertRegex(value, r"^\$\{\{ (vars|secrets)\.[A-Z_]+ != '' \}\}$")

    def test_provider_secret_reaches_only_the_review_class_steps(self):
        holders = [step["name"] for step in self.steps if "CLAUDE_CODE_OAUTH_TOKEN" in (step.get("env") or {})]
        self.assertEqual(holders, ["Preflight runtime", "Run one claimed job"])
        for step in self.steps:
            value = (step.get("env") or {}).get("CLAUDE_CODE_OAUTH_TOKEN")
            if value is not None:
                self.assertEqual(value, "${{ matrix.class == 'review' && secrets.CLAUDE_CODE_OAUTH_TOKEN || '' }}")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", yaml.safe_dump(self.workflow["jobs"]["plan"]))

    def test_third_party_actions_and_tools_are_pinned(self):
        for job in self.workflow["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
        install = " ".join(str(step.get("run", "")) for step in self.steps if "Install the pinned" in step.get("name", ""))
        self.assertRegex(install, r"@anthropic-ai/claude-code@\d+\.\d+\.\d+")
        self.assertRegex(install, r"@fission-ai/openspec@\d+\.\d+\.\d+")

    def test_worker_step_asks_only_for_the_class_kinds_and_the_review_provider(self):
        run = self.steps[self.index("Run one claimed job")]["run"]
        self.assertIn('--kinds "$HOSTED_KINDS"', run)
        self.assertIn("--run", run)
        self.assertIn("--providers claude", run)
        self.assertNotIn("--llm-command", run)
        self.assertNotIn("repair", run)

    def test_classes_in_the_table_have_a_workflow_branch(self):
        self.assertEqual(set(hosted.CLASSES), {"review", "finalize"})
        for name, spec in hosted.CLASSES.items():
            self.assertTrue(set(spec["kinds"]) <= hosted.HOSTED_KINDS)
            self.assertEqual(spec["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertTrue(re.search(r"matrix\.class == 'review'", self.text))
        self.assertTrue(re.search(r"matrix\.class == 'finalize'", self.text))


if __name__ == "__main__":
    unittest.main()
