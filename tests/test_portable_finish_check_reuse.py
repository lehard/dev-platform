"""Finish reuses check evidence for unchanged task content (portable managed path; BR-692, BR-785).

The decision tests and the execution-count tests run the real ``select_checks.py`` (as a subprocess,
exactly as ``openspec_lifecycle.finalize_change`` and ``finish_task.run_checks`` do), the real
``openspec_lifecycle.require_automated_evidence`` / ``automated_evidence_reuse`` and the real
``finish_task.validate_or_reuse`` in temporary Git repositories with a bare ``origin``.  Only the
OpenSpec CLI archive move (done by hand, mirroring what archive commits) and the independent review
are not exercised.  The wiring tests mock the decision and ``run_checks`` seams only.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_config import platform_config_text  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402

lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
finish_task = load_platform_module("finish_task", SCRIPTS / "finish_task.py")

CHANGE = "feature"
ARCHIVE = f"2026-10-21-{CHANGE}"
REUSE_PREFIX = "DEV_PLATFORM_CHECK_REUSE: "

PLATFORM_CONFIG = platform_config_text(platform_version="test", workflow_profile="standard")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdin=subprocess.DEVNULL, text=True, capture_output=True, check=True
    ).stdout.strip()


def clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("DEV_PLATFORM_MACHINE_POOL", "DEV_PLATFORM_MACHINE_POOL_LEASE"):
        env.pop(name, None)
    return env


class PortableProject:
    """A downstream-shaped project: bare origin, integration clone and one managed task worktree."""

    def __init__(self, base: Path, *, extra_check: bool = False) -> None:
        self.counter = base / "counter.txt"
        self.counter.write_text("", encoding="utf-8")
        self.command = f"echo run >> {shlex.quote(str(self.counter))}"
        self.specs_command = f"echo specs >> {shlex.quote(str(self.counter))}"
        origin = base / "origin.git"
        git(base, "init", "-q", "--bare", "-b", "main", str(origin))
        self.integration = base / "integration"
        git(base, "clone", "-q", str(origin), str(self.integration))
        git(self.integration, "config", "user.name", "Test")
        git(self.integration, "config", "user.email", "test@example.invalid")
        shutil.copytree(SCRIPTS, self.integration / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.integration / ".dev-platform.toml").write_text(PLATFORM_CONFIG, encoding="utf-8")
        checks = (
            f"[settings]\nfull_commands = [{json.dumps(self.command)}]\n\n"
            f"[checks.all]\npatterns = [\"*\"]\ncommands = [{json.dumps(self.command)}]\n"
        )
        if extra_check:
            # Selected only once archive materializes openspec/specs/..., i.e. not at archive validation time.
            checks += f"\n[checks.specs]\npatterns = [\"openspec/specs/*\"]\ncommands = [{json.dumps(self.specs_command)}]\n"
        (self.integration / "dev-platform").mkdir()
        (self.integration / "dev-platform" / "checks.toml").write_text(checks, encoding="utf-8")
        (self.integration / "feature.txt").write_text("base\n", encoding="utf-8")
        git(self.integration, "add", "-A")
        git(self.integration, "commit", "-qm", "base")
        git(self.integration, "push", "-q", "-u", "origin", "main")
        self.worktree = base / "task"
        git(self.integration, "worktree", "add", "-q", "-b", f"agent/{CHANGE}", str(self.worktree))
        exclude = Path(git(self.integration, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(".managed-task-state.json\n__pycache__/\n")
        (self.worktree / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "example-org/backlog#7", "change": CHANGE}) + "\n", encoding="utf-8"
        )

    @property
    def change(self) -> Path:
        return self.worktree / "openspec" / "changes" / CHANGE

    @property
    def archived(self) -> Path:
        return self.worktree / "openspec" / "changes" / "archive" / ARCHIVE

    def executions(self, label: str = "run") -> int:
        return self.counter.read_text(encoding="utf-8").splitlines().count(label)

    def implement(self) -> None:
        (self.worktree / "feature.txt").write_text("implemented\n", encoding="utf-8")
        (self.change / "specs" / "cap").mkdir(parents=True)
        (self.change / "specs" / "cap" / "spec.md").write_text("## Purpose\n\nFixture capability.\n\n## ADDED Requirements\n", encoding="utf-8")
        (self.change / "tasks.md").write_text("- [x] 1.1 done\n", encoding="utf-8")
        (self.change / ".managed-task.json").write_text(
            json.dumps({"source_issue": "example-org/backlog#7", "change": CHANGE}) + "\n", encoding="utf-8"
        )
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-qm", "implement")

    def validate_for_archive(self) -> None:
        """The command finalize_change runs for a portable, platform-owned change."""
        result = subprocess.run(
            ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute",
             "--evidence", str(self.change / "automated-checks.json")],
            cwd=self.worktree, stdin=subprocess.DEVNULL, text=True, capture_output=True, env=clean_environment(),
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def archive(self) -> None:
        """Receipt, archive move and spec materialization, committed like a real archive."""
        (self.change / "verification.md").write_text(
            "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            "Automated-Checks-Evidence: automated-checks.json\n",
            encoding="utf-8",
        )
        self.archived.parent.mkdir(parents=True)
        self.change.rename(self.archived)
        (self.worktree / "openspec" / "specs" / "cap").mkdir(parents=True)
        (self.worktree / "openspec" / "specs" / "cap" / "spec.md").write_text("materialized\n", encoding="utf-8")
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-qm", "archive")

    def archived_ready(self) -> None:
        self.implement()
        self.validate_for_archive()
        self.archive()

    def advance_main(self, *, merge: bool, path: str = "other.txt", text: str = "other\n") -> None:
        (self.integration / path).write_text(text, encoding="utf-8")
        git(self.integration, "add", "-A")
        git(self.integration, "commit", "-qm", "main advances")
        git(self.integration, "push", "-q", "origin", "main")
        git(self.worktree, "fetch", "-q", "origin")
        if merge:
            git(self.worktree, "merge", "-q", "--no-edit", "origin/main")

    def add_quick_task(self) -> Path:
        """A quick task (no managed provenance) with the same own change as the managed task."""
        quick = self.worktree.parent / "quick"
        git(self.integration, "worktree", "add", "-q", "-b", "agent/quick", str(quick), "origin/main")
        (quick / "feature.txt").write_text("implemented\n", encoding="utf-8")
        git(quick, "commit", "-qam", "quick implement")
        result = subprocess.run(
            ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute", "--task-evidence"],
            cwd=quick, stdin=subprocess.DEVNULL, text=True, capture_output=True, env=clean_environment(),
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return quick

    def edit_evidence(self, mutate) -> None:
        path = self.archived / "automated-checks.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def require_evidence(self) -> None:
        lifecycle.require_automated_evidence(self.archived, root=self.worktree)

    def reuse(self, base_ref: str = "origin/main") -> dict:
        return lifecycle.automated_evidence_reuse(self.archived, root=self.worktree, base_ref=base_ref)


class ProjectTestCase(unittest.TestCase):
    def setUp(self) -> None:
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("DEV_PLATFORM_MACHINE_POOL", "DEV_PLATFORM_MACHINE_POOL_LEASE"):
            os.environ.pop(name, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def project(self, **kwargs) -> PortableProject:
        return PortableProject(self.base, **kwargs)


class ReuseDecisionTests(ProjectTestCase):
    def test_reused_for_unchanged_archived_content_without_running_any_command(self) -> None:
        project = self.project()
        project.archived_ready()
        validated_head = json.loads((project.archived / "automated-checks.json").read_text())["managed_checkout"]["head"]
        project.require_evidence()
        decision = project.reuse()
        self.assertEqual(decision["decision"], "reused", decision)
        self.assertEqual(decision["commands"], [project.command])
        self.assertEqual(decision["validated_head"], validated_head)
        self.assertEqual(decision["base"], git(project.worktree, "rev-parse", "origin/main"))
        self.assertEqual(decision["evidence"], f"openspec/changes/archive/{ARCHIVE}/automated-checks.json")
        self.assertEqual(project.executions(), 1, "deciding must not execute a check command")

    def test_reused_after_a_clean_merge_of_a_main_that_touched_no_task_path(self) -> None:
        project = self.project()
        project.archived_ready()
        project.advance_main(merge=True)
        project.require_evidence()
        decision = project.reuse()  # BR-785: required CI on the exact PR head tests the integrated tree
        self.assertEqual(decision["decision"], "reused", decision)
        self.assertEqual(decision["base"], git(project.worktree, "rev-parse", "origin/main"))
        self.assertEqual(project.executions(), 1)

    def test_main_behind_head_leaves_publishability_to_the_freshness_gate(self) -> None:
        project = self.project()
        project.archived_ready()
        project.advance_main(merge=False)
        decision = project.reuse()  # the task content is unchanged; finish's preflight decides whether it may publish
        self.assertEqual(decision["decision"], "reused", decision)

    def test_not_reusable_when_main_changed_a_task_path_even_with_a_clean_merge(self) -> None:
        project = self.project()
        project.archived_ready()
        project.advance_main(merge=True, path="feature.txt", text="implemented\n")  # same bytes: the merge is clean
        decision = project.reuse()
        self.assertEqual(decision["decision"], "not-reusable")
        self.assertIn("main changed a task path", decision["reason"])

    def test_not_reusable_when_current_selection_needs_a_command_the_archive_did_not_run(self) -> None:
        project = self.project(extra_check=True)
        project.archived_ready()
        project.require_evidence()
        decision = project.reuse()
        self.assertEqual(decision["decision"], "not-reusable")
        self.assertIn(project.specs_command, decision["reason"])
        self.assertEqual(decision["commands"], [project.command, project.specs_command])

    def test_not_reusable_when_a_required_command_record_is_not_success(self) -> None:
        project = self.project()
        project.archived_ready()
        project.edit_evidence(lambda payload: payload["executed_commands"][0].update(outcome="failure"))
        decision = project.reuse()
        self.assertEqual(decision["decision"], "not-reusable")
        self.assertIn(project.command, decision["reason"])

    def test_not_reusable_when_the_required_command_is_absent_from_evidence(self) -> None:
        project = self.project()
        project.archived_ready()
        project.edit_evidence(lambda payload: payload["executed_commands"][0].update(command="echo other"))
        decision = project.reuse()
        self.assertEqual(decision["decision"], "not-reusable")
        self.assertIn(project.command, decision["reason"])

    def test_not_reusable_when_evidence_outcome_is_not_success(self) -> None:
        project = self.project()
        project.archived_ready()
        project.edit_evidence(lambda payload: payload.update(outcome="failure"))
        self.assertEqual(project.reuse()["reason"], "evidence outcome is not success")

    def test_not_reusable_for_evidence_without_task_binding(self) -> None:
        project = self.project()
        project.archived_ready()

        def version_one(payload: dict) -> None:
            payload.pop("managed_checkout")
            payload.pop("gate_task_content")
            payload["version"] = 1

        project.edit_evidence(version_one)
        decision = project.reuse()
        self.assertEqual(decision["decision"], "not-reusable")
        self.assertIn("managed_checkout", decision["reason"])
        self.assertIn("version 1", decision["reason"])
        project.edit_evidence(lambda payload: payload.update(managed_checkout={"head": "x"}))
        self.assertIn("gate_task_content", project.reuse()["reason"])

    def test_existing_evidence_gate_still_stops_changed_task_content(self) -> None:
        project = self.project()
        project.archived_ready()
        (project.worktree / "feature.txt").write_text("edited after archive\n", encoding="utf-8")
        git(project.worktree, "commit", "-qam", "late code change")
        with self.assertRaisesRegex(SystemExit, "checkout identity does not match"):
            project.require_evidence()


class ReuseErrorTests(ProjectTestCase):
    def test_unknown_base_ref_raises_instead_of_reporting_not_reusable(self) -> None:
        project = self.project()
        project.archived_ready()
        with self.assertRaisesRegex(SystemExit, "cannot compute merge-base"):
            project.reuse("origin/does-not-exist")

    def test_unreadable_evidence_raises(self) -> None:
        project = self.project()
        project.archived_ready()
        (project.archived / "automated-checks.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "missing readable automated check evidence"):
            project.reuse()

    def test_selection_failure_unparseable_and_malformed_output_raise(self) -> None:
        project = self.project()
        project.archived_ready()
        cases = (
            (subprocess.CompletedProcess([], 2, "", "boom"), "cannot recompute the required check selection.*exited 2.*boom"),
            (subprocess.CompletedProcess([], 0, "not json\n", ""), "cannot parse the required check selection"),
            (subprocess.CompletedProcess([], 0, "{}\n", ""), "unexpected shape"),
        )
        for result, message in cases:
            # Only the selection subprocess is replaced; the module's git calls (run_git) are untouched.
            fake = types.SimpleNamespace(run=mock.Mock(return_value=result), DEVNULL=subprocess.DEVNULL)
            with self.subTest(message=message), mock.patch.object(lifecycle, "subprocess", fake):
                with self.assertRaisesRegex(SystemExit, message):
                    project.reuse()


class FinishWiringTests(unittest.TestCase):
    """validate_or_reuse with only the decision and run_checks mocked."""

    work = Path("/nonexistent/work")
    delivery = mock.Mock(path=Path("/nonexistent/work/openspec/changes/archive/x"))

    def call(self, mode: str, *, reuse: dict | None = None, delivery: object | None = delivery, no_checks: bool = False):
        decision = mock.Mock(return_value=reuse)
        out = io.StringIO()
        with mock.patch.object(lifecycle, "automated_evidence_reuse", decision), \
                mock.patch.object(finish_task, "run_checks") as run_checks, contextlib.redirect_stdout(out):
            finish_task.validate_or_reuse(self.work, "origin/main", no_checks, mode, delivery, quick_task=False)
        return decision, run_checks, out.getvalue()

    def test_portable_reused_skips_checks_and_prints_the_decision(self) -> None:
        reuse = {"decision": "reused", "reason": "covered", "evidence": "e", "validated_head": "h", "base": "b", "commands": ["c"]}
        decision, run_checks, out = self.call("portable", reuse=reuse)
        run_checks.assert_not_called()
        decision.assert_called_once_with(self.delivery.path, root=self.work, base_ref="origin/main")
        self.assertIn(REUSE_PREFIX + json.dumps(reuse, sort_keys=True), out.splitlines())
        self.assertIn("DEV_PLATFORM_FINISH_STAGE: preflight clear: reusing recorded check evidence", out)
        self.assertNotIn("starting required validation", out)

    def test_portable_not_reusable_runs_the_required_checks(self) -> None:
        reuse = {"decision": "not-reusable", "reason": "validated base a differs from current base b"}
        _, run_checks, out = self.call("portable", reuse=reuse)
        run_checks.assert_called_once_with(self.work, "origin/main", False, task_evidence=False)
        self.assertIn(REUSE_PREFIX + json.dumps(reuse, sort_keys=True), out.splitlines())
        self.assertIn("DEV_PLATFORM_FINISH_STAGE: preflight clear: starting required validation", out)

    def test_coordinator_makes_no_reuse_decision(self) -> None:
        decision, run_checks, out = self.call("coordinator", reuse={"decision": "reused"})
        decision.assert_not_called()
        run_checks.assert_called_once_with(self.work, "origin/main", False, task_evidence=False)
        self.assertNotIn(REUSE_PREFIX, out)
        self.assertIn("starting required validation", out)

    def test_queue_merged_delivery_makes_no_reuse_decision(self) -> None:
        decision, run_checks, _ = self.call("portable", reuse={"decision": "reused"}, delivery=None)
        decision.assert_not_called()
        run_checks.assert_called_once_with(self.work, "origin/main", False, task_evidence=False)

    def test_no_checks_override_keeps_its_existing_path(self) -> None:
        decision, run_checks, out = self.call("portable", reuse={"decision": "reused"}, no_checks=True)
        decision.assert_not_called()
        run_checks.assert_called_once_with(self.work, "origin/main", True, task_evidence=False)
        self.assertNotIn(REUSE_PREFIX, out)

    def test_decision_error_stops_finish_without_running_checks(self) -> None:
        decision = mock.Mock(side_effect=SystemExit("cannot compute merge-base"))
        with mock.patch.object(lifecycle, "automated_evidence_reuse", decision), \
                mock.patch.object(finish_task, "run_checks") as run_checks, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "cannot compute merge-base"):
                finish_task.validate_or_reuse(self.work, "origin/main", False, "portable", self.delivery, quick_task=False)
        run_checks.assert_not_called()

    def test_main_validates_through_the_wrapper_on_the_github_path_only(self) -> None:
        import inspect

        source = inspect.getsource(finish_task.main)
        self.assertEqual(source.count("validate_or_reuse("), 1)
        # The only other direct call is the GitLab branch, which stays unchanged.
        self.assertEqual(source.count("run_checks("), 1)
        self.assertLess(source.index("run_checks("), source.index("validate_or_reuse("))


class ExecutionCountTests(ProjectTestCase):
    """Full local executions over archive -> finish, counted by the project's own selected command.

    Archive's execution is ``validate_for_archive``; finish's decision and (when not reused) validation
    are the real ``finish_task.validate_or_reuse``, whose ``run_checks`` starts the real select_checks.
    """

    def finish(self, project: PortableProject, mode: str = "portable") -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            project.require_evidence()
            finish_task.validate_or_reuse(
                project.worktree, "origin/main", False, mode, types.SimpleNamespace(path=project.archived), quick_task=False
            )
        return out.getvalue()

    def test_unchanged_content_executes_the_checks_once(self) -> None:
        project = self.project()
        project.archived_ready()
        self.assertEqual(project.executions(), 1)  # archive
        out = self.finish(project)
        self.assertIn("reusing recorded check evidence", out)
        self.assertEqual(project.executions(), 1)

    def test_coordinator_style_always_validating_path_executes_twice(self) -> None:
        """The pre-change behaviour: finish runs the checks again after the archive run."""
        project = self.project()
        project.archived_ready()
        out = self.finish(project, mode="coordinator")
        self.assertNotIn(REUSE_PREFIX, out)
        self.assertEqual(project.executions(), 2)

    def test_clean_rebase_with_unchanged_own_diff_executes_once(self) -> None:
        project = self.project()
        project.archived_ready()
        project.advance_main(merge=True)
        out = self.finish(project)
        self.assertIn('"decision": "reused"', out)
        self.assertEqual(project.executions(), 1)

    def test_main_changing_a_task_path_stops_at_the_evidence_gate(self) -> None:
        project = self.project()
        project.archived_ready()
        project.advance_main(merge=True, path="feature.txt", text="implemented\n")
        with self.assertRaisesRegex(SystemExit, "automated evidence checkout identity does not match"):
            self.finish(project)
        self.assertEqual(project.executions(), 1)

    def test_widened_selection_executes_twice(self) -> None:
        project = self.project(extra_check=True)
        project.archived_ready()
        out = self.finish(project)
        self.assertIn("not-reusable", out)
        self.assertEqual(project.executions(), 2)
        self.assertEqual(project.executions("specs"), 1)

    def test_code_change_after_archive_stops_with_a_named_error_and_no_extra_execution(self) -> None:
        project = self.project()
        project.archived_ready()
        (project.worktree / "feature.txt").write_text("late change\n", encoding="utf-8")
        git(project.worktree, "commit", "-qam", "late code change")
        with self.assertRaisesRegex(SystemExit, "automated evidence checkout identity does not match"):
            self.finish(project)
        self.assertEqual(project.executions(), 1)


class ReuseMatrixTests(ProjectTestCase):
    """BR-785: one answer for a managed and a quick task, in the portable finish and the coordinator handoff.

    Both tasks make the same own change and are validated once. Each scenario then applies the same main
    advance or own edit to both; the portable managed decision, the quick decision (the same call in either
    lifecycle, see ``QuickFinishWiringTests``) and the coordinator handoff's acceptance proof
    (``equivalent_proofs`` of the evidence gate and the current review proof, as ``pr_review_gate.handoff_gates``
    checks it) must agree.
    """

    def setUp(self) -> None:
        super().setUp()
        self.p = self.project()
        self.p.archived_ready()
        self.quick = self.p.add_quick_task()
        self.validated = self.p.executions()

    def merge_main(self, path: str, text: str) -> None:
        self.p.advance_main(merge=True, path=path, text=text)
        git(self.quick, "fetch", "-q", "origin")
        git(self.quick, "merge", "-q", "--no-edit", "origin/main")

    def answers(self) -> dict[str, str]:
        from task_content_identity import equivalent_proofs, review_content_identity

        managed = self.p.reuse()["decision"]
        quick = lifecycle.quick_evidence_reuse(self.quick, base_ref="origin/main")["decision"]
        gate = json.loads((self.p.archived / "automated-checks.json").read_text())["gate_task_content"]
        accepted = equivalent_proofs(self.p.worktree, gate, review_content_identity(self.p.worktree, CHANGE))
        self.assertEqual(self.p.executions(), self.validated, "deciding must not execute a check command")
        return {"managed": managed, "quick": quick, "coordinator-handoff": "reused" if accepted else "not-reusable"}

    def assertAnswer(self, expected: str) -> None:
        self.assertEqual(self.answers(), {"managed": expected, "quick": expected, "coordinator-handoff": expected})

    def test_unchanged(self) -> None:
        self.assertAnswer("reused")

    def test_clean_rebase_with_unchanged_own_diff(self) -> None:
        self.merge_main("other.txt", "other\n")
        self.assertAnswer("reused")

    def test_main_changed_a_task_path(self) -> None:
        self.merge_main("feature.txt", "implemented\n")  # same bytes: a clean merge, but main touched a task path
        self.assertAnswer("not-reusable")

    def test_own_diff_changed(self) -> None:
        for worktree in (self.p.worktree, self.quick):
            (worktree / "feature.txt").write_text("edited after validation\n", encoding="utf-8")
            git(worktree, "commit", "-qam", "late change")
        self.assertAnswer("not-reusable")

    def test_quick_reason_names_the_task_content_and_absent_evidence(self) -> None:
        self.merge_main("feature.txt", "implemented\n")
        self.assertIn("main changed a task path", lifecycle.quick_evidence_reuse(self.quick, base_ref="origin/main")["reason"])
        evidence_path = Path(git(self.quick, "rev-parse", "--path-format=absolute", "--git-path", "dev-platform/check-evidence.json"))
        evidence_path.unlink()
        self.assertEqual(lifecycle.quick_evidence_reuse(self.quick, base_ref="origin/main")["reason"], "no recorded quick-task evidence")

    def test_quick_evidence_lives_outside_the_tree(self) -> None:
        self.assertEqual(git(self.quick, "status", "--porcelain"), "")
        payload = json.loads(Path(git(self.quick, "rev-parse", "--path-format=absolute", "--git-path",
                                      "dev-platform/check-evidence.json")).read_text())
        self.assertEqual(payload["head"], git(self.quick, "rev-parse", "HEAD"))
        self.assertEqual(payload["gate_task_content"]["scope"], "quick-task-v1")
        self.assertEqual(set(payload["gate_task_content"]["paths"]), {"feature.txt"})

    def test_task_evidence_is_refused_on_a_managed_checkout(self) -> None:
        result = subprocess.run(
            ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute", "--task-evidence"],
            cwd=self.p.worktree, stdin=subprocess.DEVNULL, text=True, capture_output=True, env=clean_environment(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--task-evidence is for a quick task", result.stdout + result.stderr)


class QuickFinishWiringTests(unittest.TestCase):
    """A quick task reuses through the same call in the portable and the coordinator lifecycle."""

    work = Path("/nonexistent/work")

    def call(self, mode: str, reuse: dict):
        decision = mock.Mock(return_value=reuse)
        out = io.StringIO()
        with mock.patch.object(lifecycle, "quick_evidence_reuse", decision), \
                mock.patch.object(lifecycle, "automated_evidence_reuse") as managed, \
                mock.patch.object(finish_task, "run_checks") as run_checks, contextlib.redirect_stdout(out):
            finish_task.validate_or_reuse(self.work, "origin/main", False, mode, None, quick_task=True)
        managed.assert_not_called()
        decision.assert_called_once_with(self.work, base_ref="origin/main")
        return run_checks, out.getvalue()

    def test_reused_in_both_lifecycles(self) -> None:
        for mode in ("portable", "coordinator"):
            with self.subTest(mode=mode):
                run_checks, out = self.call(mode, {"decision": "reused", "reason": "covered"})
                run_checks.assert_not_called()
                self.assertIn("reusing recorded check evidence", out)

    def test_not_reusable_runs_checks_recording_quick_evidence_in_both_lifecycles(self) -> None:
        for mode in ("portable", "coordinator"):
            with self.subTest(mode=mode):
                run_checks, out = self.call(mode, {"decision": "not-reusable", "reason": "no recorded quick-task evidence"})
                run_checks.assert_called_once_with(self.work, "origin/main", False, task_evidence=True)
                self.assertIn(REUSE_PREFIX, out)


if __name__ == "__main__":
    unittest.main()
