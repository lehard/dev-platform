from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location("independent_review", SCRIPTS / "independent_review.py")
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review
SPEC.loader.exec_module(review)

RUNNER_SPEC = importlib.util.spec_from_file_location("independent_review_runner", SCRIPTS / "independent_review_runner.py")
assert RUNNER_SPEC and RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = runner
RUNNER_SPEC.loader.exec_module(runner)

LIFECYCLE_SPEC = importlib.util.spec_from_file_location("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
lifecycle = importlib.util.module_from_spec(LIFECYCLE_SPEC)
sys.modules[LIFECYCLE_SPEC.name] = lifecycle
LIFECYCLE_SPEC.loader.exec_module(lifecycle)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def material(finding_id: str) -> dict:
    return {"id": finding_id, "severity": "material", "summary": "reviewer found a meaningful mismatch", "evidence": "src.py:1"}


class FakeLauncher:
    """Stand-in for a provider CLI; never launches a real process."""

    def __init__(self, findings: list[dict] | None = None, *, returncode: int = 0, output: str | None = None,
                 raises: Exception | None = None, mutate: Path | None = None, claude_stdout: str | None = None) -> None:
        self.findings = findings or []
        self.returncode = returncode
        self.output = output
        self.raises = raises
        self.mutate = mutate
        self.claude_stdout = claude_stdout
        self.calls: list[tuple[list[str], Path, float]] = []

    def __call__(self, argv: list[str], cwd: Path, timeout: float) -> runner.LaunchResult:
        self.calls.append((list(argv), cwd, timeout))
        if self.raises is not None:
            raise self.raises
        if self.mutate is not None:
            self.mutate.write_text(f"reviewer wrote here {len(self.calls)}\n", encoding="utf-8")
        payload = self.output if self.output is not None else json.dumps({"findings": self.findings})
        if "--output-last-message" in argv:
            Path(argv[argv.index("--output-last-message") + 1]).write_text(payload, encoding="utf-8")
            stdout = json.dumps({"type": "thread.started", "thread_id": f"thread-{len(self.calls)}"}) + "\n"
        else:
            stdout = self.claude_stdout if self.claude_stdout is not None else json.dumps(
                {"type": "result", "is_error": False, "session_id": f"session-{len(self.calls)}",
                 "structured_output": json.loads(payload) if self.output is None else None, "result": payload}
            )
        return runner.LaunchResult(self.returncode, stdout)


class IndependentReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "review@example.test")
        git(self.root, "config", "user.name", "Review Test")
        (self.root / "README.md").write_text("base\n", encoding="utf-8")
        self.write_config()
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "update-ref", "refs/remotes/origin/main", "main")
        git(self.root, "checkout", "-qb", "feature")
        self.change = self.root / "openspec" / "changes" / "review-change"
        (self.change / "specs" / "review-cap").mkdir(parents=True)
        (self.change / ".managed-task.json").write_text(
            '{"source_issue": "owner/backlog#1", "change": "review-change"}\n', encoding="utf-8"
        )
        (self.change / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
        (self.change / "design.md").write_text("# Design\n", encoding="utf-8")
        (self.change / "tasks.md").write_text("- [x] task\n", encoding="utf-8")
        (self.change / "specs" / "review-cap" / "spec.md").write_text("## ADDED Requirements\n", encoding="utf-8")
        (self.root / "src.py").write_text("value = 1\n", encoding="utf-8")
        self.commit("candidate")
        self.which = mock.patch.object(runner.shutil, "which", side_effect=lambda name: f"/fake/bin/{name}")
        self.which.start()
        self.addCleanup(self.which.stop)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self, extra: str = 'provider = "codex"\n', enabled: str = "true") -> None:
        (self.root / ".dev-platform.toml").write_text(f"[independent_review]\nenabled = {enabled}\n{extra}", encoding="utf-8")

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", message)

    def run_review(self, launcher: FakeLauncher | None = None, change: Path | None = None) -> dict:
        return runner.run_review(self.root, change or self.change, launcher=launcher or FakeLauncher())

    def state(self, change: Path | None = None) -> dict:
        return review.review_state(self.root, change or self.change)

    # Request and adapters -------------------------------------------------

    def test_request_is_provider_neutral_and_requires_fresh_read_only_context(self) -> None:
        request = review.prepare_request(self.root, self.change, "origin/main")
        self.assertTrue(request["fresh_context_required"])
        self.assertEqual(set(request["perspectives"]), set(review.PERSPECTIVES))
        self.assertEqual(request["reviewer_constraints"]["write_access"], False)
        self.assertNotIn("provider", request)
        self.assertNotIn("model", request)
        self.assertEqual(request["task_content"]["scope"], "independent-review-v1")

    def test_codex_adapter_launches_each_perspective_in_its_read_only_sandbox(self) -> None:
        launcher = FakeLauncher()
        reports = self.run_review(launcher)
        self.assertEqual(len(launcher.calls), 2)
        for argv, cwd, timeout in launcher.calls:
            self.assertEqual(argv[:2], ["/fake/bin/codex", "exec"])
            self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
            self.assertIn("--ephemeral", argv)
            self.assertEqual(argv[argv.index("--cd") + 1], str(self.root))
            self.assertIn("--output-schema", argv)
            self.assertEqual(argv[argv.index("--model") + 1], "gpt-6-sol")
            self.assertEqual(cwd, self.root)
            self.assertEqual(timeout, runner.DEFAULT_TIMEOUT_SECONDS)
            self.assertFalse(Path(argv[argv.index("--output-last-message") + 1]).is_relative_to(self.root))
        for perspective, report in reports.items():
            reviewer = report["reviewer"]
            self.assertEqual(report["availability"], "available")
            self.assertEqual(reviewer["launch_evidence"], "platform-observed")
            self.assertEqual(reviewer["model"], {"value": "gpt-6-sol", "source": "selected"})
            self.assertTrue(reviewer["context_id"].startswith("thread-"))
            self.assertTrue(reviewer["fresh_context"])
            self.assertFalse(reviewer["write_access"])
            self.assertIn("--sandbox read-only", reviewer["read_only_mechanism"])
            self.assertRegex(report["output_sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(self.state()["state"], "ready")
        review.validate_evidence(self.root, self.change)

    def test_claude_adapter_uses_only_read_only_tools_without_session_persistence(self) -> None:
        self.write_config('provider = "claude"\n')
        self.commit("claude provider")
        binary = self.root.parent / f"{self.root.name}-claude"
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
        self.addCleanup(binary.unlink)
        launcher = FakeLauncher([{"id": "note", "severity": "advisory", "summary": "minor", "evidence": "src.py:1"}])
        with mock.patch.dict(os.environ, {runner.CLAUDE_BIN_ENV: str(binary)}):
            reports = self.run_review(launcher)
        for argv, cwd, _ in launcher.calls:
            self.assertEqual(argv[:2], [str(binary), "-p"])
            self.assertEqual(argv[argv.index("--tools") + 1], "Read,Grep,Glob")
            self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
            self.assertIn("--no-session-persistence", argv)
            self.assertIn("--strict-mcp-config", argv)
            self.assertEqual(argv[argv.index("--output-format") + 1], "json")
            self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), runner.FINDINGS_SCHEMA)
            self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
            for write_tool in ("Bash", "Edit", "Write", "NotebookEdit"):
                self.assertNotIn(write_tool, " ".join(argv[:-1]))
            self.assertEqual(cwd, self.root)
        report = reports["spec-fidelity"]
        self.assertEqual(report["reviewer"]["provider"], "claude")
        self.assertTrue(report["reviewer"]["context_id"].startswith("session-"))
        self.assertEqual(report["findings"][0]["id"], "note")
        self.assertEqual(self.state()["state"], "ready")

    def test_claude_result_string_is_parsed_defensively(self) -> None:
        raw, session = runner.parse_claude_output(json.dumps({"is_error": False, "session_id": "s", "result": '{"findings": []}'}))
        self.assertEqual(runner.parse_findings(raw), [])
        self.assertEqual(session, "s")
        with self.assertRaises(runner.ReviewOutputError):
            runner.parse_claude_output(json.dumps({"is_error": True, "subtype": "error_max_turns"}))

    def test_provider_defaults_to_task_route_and_unknown_route_is_unavailable(self) -> None:
        self.write_config("")
        self.commit("no explicit provider")
        fake_route = mock.Mock(provider="claude")
        with mock.patch("model_routing.read_current_durable_route", return_value=(fake_route, Path("x"))):
            self.assertEqual(runner.resolve_provider(self.root, {}), ("claude", "task-route"))
        launcher = FakeLauncher()
        with mock.patch("model_routing.read_current_durable_route", side_effect=RuntimeError("no route")):
            reports = self.run_review(launcher)
        self.assertEqual(launcher.calls, [])
        self.assertIn("route provider is unknown", reports["spec-fidelity"]["limitation"])
        self.assertEqual(self.state()["state"], "blocked")

    # Failure modes --------------------------------------------------------

    def assert_unavailable(self, reports: dict, text: str) -> None:
        for report in reports.values():
            self.assertEqual(report["availability"], "unavailable")
            self.assertEqual(report["findings"], [])
            self.assertIn(text, report["limitation"])
        with self.assertRaisesRegex(review.IndependentReviewError, "independent review unavailable"):
            review.validate_evidence(self.root, self.change)

    def test_missing_codex_binary_is_an_actionable_unavailable_report(self) -> None:
        launcher = FakeLauncher()
        with mock.patch.object(runner.shutil, "which", return_value=None):
            reports = self.run_review(launcher)
        self.assertEqual(launcher.calls, [])
        self.assert_unavailable(reports, "not on PATH")

    def test_claude_binary_override_must_be_executable_and_missing_binary_is_unavailable(self) -> None:
        self.write_config('provider = "claude"\n')
        self.commit("claude provider")
        with mock.patch.dict(os.environ, {runner.CLAUDE_BIN_ENV: str(self.root / "missing-claude")}):
            self.assert_unavailable(self.run_review(), runner.CLAUDE_BIN_ENV)
        with mock.patch.dict(os.environ, {runner.CLAUDE_BIN_ENV: ""}), mock.patch.object(runner.shutil, "which", return_value=None):
            self.assert_unavailable(self.run_review(), runner.CLAUDE_BIN_ENV)

    def test_timeout_nonzero_exit_and_malformed_output_are_unavailable(self) -> None:
        self.assert_unavailable(self.run_review(FakeLauncher(raises=runner.LaunchTimeout("reviewer exceeded 1800s"))), "timed out")
        self.assert_unavailable(self.run_review(FakeLauncher(returncode=3)), "exited with status 3")
        self.assert_unavailable(self.run_review(FakeLauncher(output="not json")), "malformed output")
        self.assert_unavailable(
            self.run_review(FakeLauncher(output=json.dumps({"findings": [{"id": "x", "severity": "fatal", "summary": "s", "evidence": "e"}]}))),
            "malformed output",
        )

    def test_workspace_mutation_invalidates_the_report_without_repair(self) -> None:
        mutated = self.root / "reviewer-output.txt"
        reports = self.run_review(FakeLauncher([material("x")], mutate=mutated))
        self.assert_unavailable(reports, "reviewer mutated the workspace")
        self.assertIn("reviewer-output.txt", reports["spec-fidelity"]["limitation"])
        self.assertTrue(mutated.is_file(), "the platform must not clean a reviewer mutation")

    def test_uncommitted_candidate_is_refused_before_launch(self) -> None:
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        launcher = FakeLauncher()
        with self.assertRaisesRegex(review.IndependentReviewError, "commit the candidate"):
            self.run_review(launcher)
        self.assertEqual(launcher.calls, [])

    # Evidence acceptance ----------------------------------------------------

    def test_hand_recorded_report_does_not_satisfy_required_review(self) -> None:
        self.run_review()
        request = json.loads(review.request_path(self.change).read_text(encoding="utf-8"))
        for perspective in review.PERSPECTIVES:
            path = review.report_path(self.change, perspective)
            data = {
                "schema_version": 1, "perspective": perspective, "request_id": request["request_id"],
                "candidate": request["candidate"], "availability": "available", "findings": [],
                "reviewer": {"runtime": "self", "context_id": "claimed", "fresh_context": True, "write_access": False},
            }
            path.write_text(json.dumps(data), encoding="utf-8")
        state = self.state()
        self.assertEqual(state["state"], "stale")
        self.assertIn("platform-observed", state["detail"])
        with self.assertRaisesRegex(SystemExit, "platform-observed"):
            review.require_review_evidence(self.root, self.change)

    def test_task_change_after_review_makes_evidence_stale(self) -> None:
        self.run_review()
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self.commit("change candidate")
        with self.assertRaisesRegex(review.IndependentReviewError, "stale"):
            review.validate_evidence(self.root, self.change)
        self.assertEqual(self.state()["state"], "stale")

    def test_lifecycle_receipts_do_not_change_review_identity(self) -> None:
        self.run_review()
        (self.change / "verification.md").write_text("OpenSpec-Verify: PASS\n", encoding="utf-8")
        (self.change / "automated-checks.json").write_text("{}\n", encoding="utf-8")
        self.commit("receipts and evidence")
        self.assertEqual(self.state()["state"], "ready")

    def test_evidence_survives_archive_move_and_irrelevant_main_merge(self) -> None:
        self.run_review()
        self.commit("review evidence")
        git(self.root, "checkout", "-q", "main")
        (self.root / "unrelated.txt").write_text("main moved\n", encoding="utf-8")
        self.commit("unrelated main work")
        git(self.root, "update-ref", "refs/remotes/origin/main", "main")
        git(self.root, "checkout", "-q", "feature")
        git(self.root, "merge", "-q", "--no-edit", "main")
        self.assertEqual(self.state()["state"], "ready")
        archived = self.root / "openspec" / "changes" / "archive" / "2026-09-29-review-change"
        archived.parent.mkdir(parents=True)
        shutil.move(str(self.change), str(archived))
        (self.root / "openspec" / "specs" / "review-cap").mkdir(parents=True)
        (self.root / "openspec" / "specs" / "review-cap" / "spec.md").write_text("# materialized\n", encoding="utf-8")
        self.commit("archive")
        self.assertEqual(review.resolve_change(self.root, "review-change"), archived)
        self.assertEqual(self.state(archived)["state"], "ready")
        lifecycle.require_publication_review_evidence(archived, root=self.root)

    def test_main_merge_touching_task_path_is_not_accepted(self) -> None:
        self.run_review()
        self.commit("review evidence")
        git(self.root, "checkout", "-q", "main")
        (self.root / "src.py").write_text("value = 1\n", encoding="utf-8")
        self.commit("main adds the same task path")
        git(self.root, "update-ref", "refs/remotes/origin/main", "main")
        git(self.root, "checkout", "-q", "feature")
        git(self.root, "merge", "-q", "--no-edit", "main")
        self.assertEqual(self.state()["state"], "stale")

    # Dispositions -----------------------------------------------------------

    def test_material_finding_blocks_until_rejected_with_rationale_bound_to_report(self) -> None:
        self.run_review(FakeLauncher([material("missing-contract-behavior")]))
        state = self.state()
        self.assertEqual(state["state"], "blocked")
        self.assertIn("dispose review-change --perspective spec-fidelity --finding missing-contract-behavior", state["next"])
        with self.assertRaisesRegex(review.IndependentReviewError, "spec-fidelity:missing-contract-behavior"):
            review.validate_evidence(self.root, self.change)
        before = review.report_path(self.change, "spec-fidelity").read_bytes()
        for perspective in review.PERSPECTIVES:
            review.dispose(self.root, self.change, perspective=perspective, finding="missing-contract-behavior",
                           status="rejected", rationale="the contract excludes this case")
        self.assertEqual(review.report_path(self.change, "spec-fidelity").read_bytes(), before, "reports stay immutable")
        self.assertEqual(self.state()["state"], "ready")

    def test_blocker_disposition_and_unrecordable_fixed_status(self) -> None:
        self.run_review(FakeLauncher([material("unsafe-maintenance-pattern")]))
        review.dispose(self.root, self.change, perspective="engineering-quality", finding="unsafe-maintenance-pattern",
                       status="blocker", rationale="needs a design change")
        review.dispose(self.root, self.change, perspective="spec-fidelity", finding="unsafe-maintenance-pattern",
                       status="rejected", rationale="not a contract issue")
        with self.assertRaisesRegex(review.IndependentReviewError, "engineering-quality:unsafe-maintenance-pattern"):
            review.validate_evidence(self.root, self.change)
        with self.assertRaisesRegex(review.IndependentReviewError, "rerun the review"):
            review.dispose(self.root, self.change, perspective="spec-fidelity", finding="unsafe-maintenance-pattern",
                           status="fixed", rationale="fixed it")
        with self.assertRaisesRegex(review.IndependentReviewError, "non-empty rationale"):
            review.dispose(self.root, self.change, perspective="spec-fidelity", finding="unsafe-maintenance-pattern",
                           status="rejected", rationale="  ")
        with self.assertRaisesRegex(review.IndependentReviewError, "no finding"):
            review.dispose(self.root, self.change, perspective="spec-fidelity", finding="unknown", status="rejected", rationale="x")

    def test_disposition_bound_to_a_superseded_report_digest_is_rejected(self) -> None:
        self.run_review(FakeLauncher([material("finding")]))
        for perspective in review.PERSPECTIVES:
            review.dispose(self.root, self.change, perspective=perspective, finding="finding", status="rejected", rationale="ok")
        self.assertEqual(self.state()["state"], "ready")
        self.run_review(FakeLauncher([material("finding")]))
        self.assertEqual(self.state()["state"], "blocked")

    def test_advisory_findings_do_not_block(self) -> None:
        self.run_review(FakeLauncher([{"id": "style", "severity": "advisory", "summary": "nit", "evidence": "src.py:1"}]))
        self.assertEqual(self.state()["state"], "ready")

    def test_reviewer_cannot_write_dispositions(self) -> None:
        finding = dict(material("x"), disposition={"status": "rejected", "rationale": "self-cleared"})
        self.assert_unavailable(self.run_review(FakeLauncher(output=json.dumps({"findings": [finding]}))), "must not write finding dispositions")

    # Lifecycle gate -----------------------------------------------------------

    def platform_archive(self, launcher: FakeLauncher):
        (self.change / "verification.md").write_text(
            "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            "Automated-Checks-Evidence: automated-checks.json\n"
            "Independent-Review-Evidence: independent-review-request.json\n",
            encoding="utf-8",
        )
        self.commit("verification")
        patches = [
            mock.patch.object(lifecycle, "harness_mode", return_value="platform"),
            mock.patch.object(lifecycle, "source_issue_for_provenance", return_value="owner/backlog#1"),
            mock.patch.object(lifecycle, "require_managed_checkout_identity"),
            mock.patch.object(lifecycle, "require_managed_routing_evidence"),
            mock.patch.object(lifecycle, "require_applicable_committed_diff"),
            mock.patch.object(lifecycle, "require_ready"),
            mock.patch.object(runner, "subprocess_launcher", launcher),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return mock.patch.object(lifecycle, "run_checked")

    def test_archive_auto_runs_missing_review_and_blocks_on_findings_before_validation(self) -> None:
        launcher = FakeLauncher([material("missing-contract-behavior")])
        with self.platform_archive(launcher) as run_checked:
            with self.assertRaises(SystemExit) as raised:
                lifecycle.archive_change(self.root, "review-change")
        message = str(raised.exception)
        self.assertEqual(len(launcher.calls), 2)
        run_checked.assert_not_called()
        self.assertIn("spec-fidelity:missing-contract-behavior", message)
        self.assertIn("python3 scripts/independent_review.py dispose review-change", message)
        self.assertIn("python3 scripts/independent_review.py run review-change", message)

    def test_archive_runs_review_then_continues_to_expensive_validation(self) -> None:
        launcher = FakeLauncher()
        with self.platform_archive(launcher) as run_checked:
            self.assertEqual(lifecycle.archive_change(self.root, "review-change"), 0)
        self.assertEqual(len(launcher.calls), 2)
        self.assertIn("select_checks.py", " ".join(run_checked.call_args_list[0].args[0]))
        # Current evidence is reused, not relaunched.
        with self.platform_archive(launcher):
            lifecycle.archive_change(self.root, "review-change")
        self.assertEqual(len(launcher.calls), 2)

    def test_finish_gate_refuses_stale_review_before_publication(self) -> None:
        self.run_review()
        self.commit("review evidence")
        lifecycle.require_publication_review_evidence(self.change, root=self.root)
        (self.root / "src.py").write_text("value = 3\n", encoding="utf-8")
        self.commit("late candidate change")
        with self.assertRaisesRegex(SystemExit, "Publication refused before any remote mutation(.|\n)*independent_review.py run review-change"):
            lifecycle.require_publication_review_evidence(self.change, root=self.root)
        finish = (SCRIPTS / "finish_task.py").read_text(encoding="utf-8")
        self.assertIn(
            "require_automated_evidence(delivery.path, root=work)\n            require_publication_review_evidence(delivery.path, root=work)",
            finish,
        )

    def test_quick_task_without_managed_provenance_is_never_reviewed(self) -> None:
        (self.change / ".managed-task.json").unlink()
        self.commit("quick task")
        self.assertFalse(review.review_is_required(self.root, self.change))
        self.assertEqual(self.state()["state"], "not-required")
        launcher = FakeLauncher()
        with mock.patch.object(runner, "subprocess_launcher", launcher):
            review.ensure_review_evidence(self.root, self.change)
        self.assertEqual(launcher.calls, [])

    def test_template_default_disables_review(self) -> None:
        self.write_config("", enabled="false")
        self.assertFalse(review.review_is_required(self.root, self.change))

    # Resume surfaces ----------------------------------------------------------

    def test_status_surfaces_derived_state_and_next_command(self) -> None:
        state = self.state()
        self.assertEqual(state["state"], "missing")
        self.assertEqual(state["next"], "python3 scripts/independent_review.py run review-change")
        self.assertIn("archive helper runs a missing or stale review automatically", state["note"])
        import finish_task

        observed = finish_task.observe_independent_review(self.root)
        self.assertEqual(observed["state"], "missing")
        self.run_review(FakeLauncher([material("gap")]))
        observed = finish_task.observe_independent_review(self.root)
        self.assertEqual(observed["state"], "blocked")
        self.assertEqual(observed["blockers"][0]["id"], "gap")
        with mock.patch("builtins.print") as printed:
            finish_task.print_independent_review(observed)
        self.assertIn("independent review: blocked; next: python3 scripts/independent_review.py dispose", printed.call_args_list[0].args[0])

    def test_requirement_advance_surfaces_child_review_state(self) -> None:
        import execute_requirement

        state = execute_requirement._child_review_state(self.root, "owner/backlog#1", "review-change")
        self.assertEqual(state["state"], "missing")
        source = (SCRIPTS / "execute_requirement.py").read_text(encoding="utf-8")
        self.assertIn('"independent_review": _child_review_state(', source)
        self.assertIn("archive runs it automatically", source)

    # Boundaries ---------------------------------------------------------------

    def test_platform_review_adapter_has_no_publish_or_completion_operation(self) -> None:
        source = (SCRIPTS / "independent_review.py").read_text(encoding="utf-8")
        for forbidden in ("project_publish", "managed_project_status", "openspec_lifecycle", "subprocess"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_runner_has_no_publish_archive_or_cleanup_operation(self) -> None:
        source = (SCRIPTS / "independent_review_runner.py").read_text(encoding="utf-8")
        for forbidden in ("project_publish", "managed_project_status", "openspec_lifecycle", "archive_change", '"reset"', '"clean"', '"stash"'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_legacy_in_report_dispositions_remain_readable_when_review_is_not_required(self) -> None:
        self.write_config("", enabled="false")
        request = review.prepare_request(self.root, self.change, "origin/main")
        for perspective, status in zip(review.PERSPECTIVES, ("fixed", "rejected")):
            finding = dict(material(status), disposition={"status": status, "rationale": "controlled"})
            data = {
                "schema_version": 1, "perspective": perspective, "request_id": request["request_id"],
                "candidate": request["candidate"], "availability": "available", "findings": [finding],
                "reviewer": {"runtime": "legacy", "context_id": "ctx", "fresh_context": True, "write_access": False},
            }
            path = review.report_path(self.change, perspective)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
        review.validate_evidence(self.root, self.change)


if __name__ == "__main__":
    unittest.main()
