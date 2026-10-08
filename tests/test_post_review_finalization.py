from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")
final = load_platform_module("post_review_finalization", SCRIPTS / "post_review_finalization.py")
lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
finish = load_platform_module("finish_task", SCRIPTS / "finish_task.py")

from test_pr_review_gate import QueueFixture, git  # noqa: E402

SPEC = """# cap Specification

## Purpose
Fixture capability used to exercise archive-derived spec re-derivation in tests.

## Requirements

### Requirement: Base behavior

The system SHALL keep the base behavior.

#### Scenario: Base
- **WHEN** it runs
- **THEN** it keeps the base behavior
"""


def requirement(name: str, text: str, scenario: str | None = None) -> str:
    return (f"### Requirement: {name}\n\n{text}\n\n#### Scenario: {scenario or name}\n"
            f"- **WHEN** it runs\n- **THEN** {text}\n")


def tasks_state(root: Path, name: str, body: str) -> None:
    change = root / "openspec/changes" / name
    change.mkdir(parents=True, exist_ok=True)
    (change / "tasks.md").write_text(body)


class HygieneStageTests(unittest.TestCase):
    def make(self, root: Path, managed: bool) -> None:
        tasks_state(root, "done", "- [x] one\n")
        if managed:
            (root / "openspec/changes/done/.managed-task.json").write_text("{}")

    def test_completed_active_blocks_at_integration_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make(root, managed=True)
            self.assertEqual(lifecycle.check_hygiene(root, "integration"), 1)

    def test_coordinator_candidate_may_carry_completed_managed_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make(root, managed=True)
            self.assertEqual(lifecycle.check_hygiene(root, "candidate"), 0)
            plain = root / "openspec/changes/done/.managed-task.json"
            plain.unlink()
            self.assertEqual(lifecycle.check_hygiene(root, "candidate"), 1)

    def test_default_stage_is_strict_outside_a_source_work_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make(root, managed=True)
            with mock.patch.object(lifecycle, "read_platform_config", return_value={"platform_version": "source"}), \
                    mock.patch.dict("os.environ", {"GITHUB_REF": "refs/heads/main"}):
                self.assertEqual(lifecycle.check_hygiene(root), 1)
            with mock.patch.object(lifecycle, "read_platform_config", return_value={"platform_version": "source"}), \
                    mock.patch.dict("os.environ", {"GITHUB_REF": "refs/pull/9/merge"}):
                self.assertEqual(lifecycle.check_hygiene(root), 0)
            with mock.patch.object(lifecycle, "read_platform_config", return_value={"platform_version": "1.0"}), \
                    mock.patch.dict("os.environ", {"GITHUB_REF": "refs/pull/9/merge"}):
                self.assertEqual(lifecycle.check_hygiene(root), 1)

    def test_incomplete_change_stays_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_state(root, "work", "- [x] a\n- [ ] b\n")
            self.assertEqual(lifecycle.check_hygiene(root, "integration"), 0)

    def test_tree_scan_and_non_coordinator_finish_use_the_strict_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-qb", "main")
            git(root, "config", "user.name", "F")
            git(root, "config", "user.email", "f@localhost")
            tasks_state(root, "done", "- [x] one\n")
            tasks_state(root, "open", "- [ ] one\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "x")
            self.assertEqual(lifecycle.completed_active_changes_at(root, "HEAD"), ["done"])
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(finish.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            self.assertIsNone(finish.run_openspec_hygiene(Path(tmp)))
            self.assertEqual(run.call_args.args[0][-3:], ["check", "--stage", "integration"])

    def test_admission_requires_finalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-qb", "main")
            git(root, "config", "user.name", "F")
            git(root, "config", "user.email", "f@localhost")
            tasks_state(root, "done", "- [x] one\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "x")
            head = git(root, "rev-parse", "HEAD")
            real = queue.run_git

            def fake(args, **kwargs):
                if args[:1] == ["fetch"]:
                    return subprocess.CompletedProcess(args, 0, "", "")
                if args[:2] == ["rev-parse", "FETCH_HEAD"]:
                    return subprocess.CompletedProcess(args, 0, head + "\n", "")
                return real(args, **kwargs)

            with mock.patch.object(queue, "run_git", side_effect=fake):
                with self.assertRaisesRegex(queue.QueueError, "still active at integration: done"):
                    queue._require_finalized(root, 7, head)


class ArchiveFinalizeModeTests(unittest.TestCase):
    def test_finalize_reuses_evidence_and_skips_checkout_identity_and_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_state(root, "work", "- [x] done\n")
            (root / "openspec/changes/work/.managed-task.json").write_text("{}")
            with mock.patch.object(lifecycle, "read_platform_config", return_value={"harness_mode": "platform"}), \
                    mock.patch.object(lifecycle, "require_static_archive_readiness") as static, \
                    mock.patch.object(lifecycle, "require_managed_checkout_identity") as identity, \
                    mock.patch.object(lifecycle, "require_applicable_committed_diff") as diff, \
                    mock.patch.object(lifecycle, "ensure_review_evidence") as launch, \
                    mock.patch.object(lifecycle, "require_review_evidence") as review, \
                    mock.patch.object(lifecycle, "require_ready") as ready, \
                    mock.patch.object(lifecycle.shutil, "which", return_value="openspec"), \
                    mock.patch.object(lifecycle, "run_checked") as run_checked:
                self.assertEqual(lifecycle.archive_change(root, "work", finalize=True), 0)
            identity.assert_not_called()
            diff.assert_not_called()
            launch.assert_not_called()
            review.assert_called_once()
            self.assertFalse(static.call_args.kwargs["routing"])
            self.assertFalse(ready.call_args.kwargs["platform_owned"])
            self.assertIn("archive", run_checked.call_args_list[1].args[0])


class ContributionFreshnessTests(unittest.TestCase):
    def test_trusted_runner_passes_the_exact_contribution_base(self):
        done = subprocess.CompletedProcess("checks", 0, stdout="", stderr="")
        with mock.patch.object(final.subprocess, "run", return_value=done) as run:
            final.trusted_checks_runner(Path("/checkout"), {}, contribution_base="abc123")
            final.trusted_checks_runner(Path("/checkout"), {})
        contribution, main = (call.args[0] for call in run.call_args_list)
        self.assertEqual(contribution[-2:], ["--contribution-base", "abc123"])
        self.assertNotIn("--contribution-base", main)

    def finalize_runner(self, identity):
        seen = []

        def capture(checkout, gates, actual, head, runner):
            seen.append(runner)
            raise workers.WorkerError("stop after runner selection")

        job = {"head": "h", "task_identity": identity}
        with mock.patch.object(final.review_gate, "refresh_identity", return_value=identity), \
                mock.patch.object(final, "equivalent_proofs", return_value=True), \
                mock.patch.object(final, "reestablish_gates", side_effect=capture):
            with self.assertRaises(workers.WorkerError):
                final.execute_finalize(Path("/checkout"), job, {}, source_repo="r", branch="b", current_head=lambda: "h")
        return seen

    def test_contribution_finalize_checks_freshness_against_its_contribution_base(self):
        identity = {"kind": "contribution", "change": "c", "task_content": {}, "contribution_base": "abc123"}
        runner, = self.finalize_runner(identity)
        self.assertIs(runner.func, final.trusted_checks_runner)
        self.assertEqual(runner.keywords, {"contribution_base": "abc123"})

    def test_contribution_without_base_fails_loudly(self):
        identity = {"kind": "contribution", "change": "c", "task_content": {}}
        with mock.patch.object(final.review_gate, "refresh_identity", return_value=identity), \
                mock.patch.object(final, "equivalent_proofs", return_value=True):
            with self.assertRaisesRegex(workers.WorkerError, "lacks its exact contribution base"):
                final.execute_finalize(Path("/checkout"), {"head": "h", "task_identity": identity}, {},
                                       source_repo="r", branch="b", current_head=lambda: "h")

    def test_main_task_finalize_keeps_main_freshness(self):
        runner, = self.finalize_runner({"change": "c", "task_content": {}})
        self.assertIs(runner, final.trusted_checks_runner)


class Remote:
    """A source repository with a bare remote carrying main and the candidate branch."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.root = tmp / "source"
        self.root.mkdir()
        git(self.root, "init", "-qb", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@localhost")
        (self.root / ".dev-platform.toml").write_text("")
        (self.root / "src.py").write_text("value = 0\n")
        self.write_spec(SPEC)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        self.remote = tmp / "remote.git"
        git(self.root, "clone", "--bare", str(self.root), str(self.remote))
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "fetch", "-q", "origin")

    def write_spec(self, text: str, cap: str = "cap") -> None:
        path = self.root / "openspec/specs" / cap / "spec.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def head(self, ref: str = "agent/example") -> str:
        return git(self.remote, "rev-parse", f"refs/heads/{ref}")

    def push(self, ref: str) -> None:
        git(self.root, "push", "-q", "origin", f"HEAD:refs/heads/{ref}")


class RemoteFixture(QueueFixture):
    """GitHub observes the real pushed head of the local remote immediately."""

    def __init__(self, repo: Remote):
        super().__init__(repo.root, repo.head())
        self._repo = repo

    @property
    def head(self):
        return self._repo.head()

    @head.setter
    def head(self, value):
        pass


class FinalizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Remote(Path(self.tmp.name))
        root = self.repo.root
        git(root, "checkout", "-qb", "agent/example")
        change = root / "openspec/changes/example"
        (change / "specs/cap").mkdir(parents=True)
        (change / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- y\n")
        (change / "tasks.md").write_text("- [x] implement\n")
        (change / ".managed-task.json").write_text('{"change":"example", "source_issue":"owner/backlog#1"}')
        (change / "specs/cap/spec.md").write_text(
            "## ADDED Requirements\n\n" + requirement("Candidate behavior", "The system SHALL do the candidate behavior."))
        (change / "verification.md").write_text("OpenSpec-Verify: PASS\nVerification-Method: fixture\n")
        (change / "automated-checks.json").write_text('{"outcome":"success"}')
        (root / "src.py").write_text("value = 1\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "candidate")
        self.repo.push("agent/example")
        self.identity = gate.task_identity(root, "example")

    def gates(self, identity=None, omit=()):
        identity = identity or self.identity
        change = self.repo.root / "openspec/changes/example"
        evidence = {"review": {}, "selected-checks": gate.file_reference(self.repo.root, change / "automated-checks.json"),
                    "semantic-verification": gate.file_reference(self.repo.root, change / "verification.md")}
        return {name: {"result": "passed", "identity": identity, "evidence": value}
                for name, value in evidence.items() if name not in omit}

    @staticmethod
    def archiver(checkout: Path, change: str, env) -> None:
        source = checkout / "openspec/changes" / change
        target = checkout / "openspec/changes/archive" / f"2026-10-06-{change}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        spec = checkout / "openspec/specs/cap/spec.md"
        spec.write_text(spec.read_text() + "\n" + requirement("Candidate behavior", "The system SHALL do the candidate behavior."))

    def finalize(self, fixture, *, archiver=None, post=None, checks_runner=None):
        candidate = fixture.candidate()
        job = workers.build_job(candidate)
        self.assertEqual(job["kind"], "finalize")
        results = []
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            outcome = final.run_claimed_finalize(
                self.repo.root, "o/r", candidate, job, source_repo=self.repo.remote.as_uri(),
                branch="agent/example", current_head=self.repo.head, workdir=workdir,
                post_result=post or results.append, archiver=archiver or self.archiver,
                claim_current=lambda: True, checks_runner=checks_runner)
        fixture.head = self.repo.head()
        return outcome, results

    def offer(self, fixture, gates=None):
        queue._transition(self.repo.root, "o/r", 7, "finalize-pending", fixture.head, task_identity=self.identity,
                          inherit_identity=False, gates=self.gates() if gates is None else gates)

    def test_review_passes_then_finalize_archives_and_candidate_is_ready(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head()
            outcome, results = self.finalize(fixture)
            self.assertEqual(outcome["status"], "finalized")
            self.assertNotEqual(self.repo.head(), before)
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "ready")
            self.assertEqual(candidate["head"], self.repo.head())
            # Finalization never changes the task-content identity or the proven gates.
            self.assertEqual(candidate["task_identity"]["task_content"]["digest"], self.identity["task_content"]["digest"])
            self.assertEqual(sorted(candidate["gates"]), ["review", "selected-checks", "semantic-verification"])
            self.assertTrue(gate.reusable(self.repo.root, candidate["gates"]["review"], candidate["task_identity"]))
            tree = git(self.repo.remote, "ls-tree", "-r", "--name-only", self.repo.head())
            self.assertIn("openspec/changes/archive/2026-10-06-example/tasks.md", tree)
            self.assertNotIn("openspec/changes/example/", tree)
            self.assertEqual(lifecycle.completed_active_changes_at(self.repo.remote, self.repo.head()), [])
            self.assertEqual(json.loads(results[-1][len(workers.RESULT_PREFIX):])["outcome"], "finalized")

    def test_finalize_is_idempotent_when_already_archived(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            self.finalize(fixture)
            # Back to a pending finalization at the archived head: no new commit, still ready.
            archived = self.repo.head()
            queue._transition(self.repo.root, "o/r", 7, "finalize-pending", archived, task_identity=self.identity,
                              inherit_identity=False, gates=fixture.candidate()["gates"])
            git(self.repo.root, "fetch", "-q", "origin")
            git(self.repo.root, "reset", "-q", "--hard", archived)
            fixture.head = archived
            outcome, _ = self.finalize(fixture, archiver=lambda *a: self.fail("must not archive again"))
            self.assertEqual(outcome["status"], "finalized")
            self.assertEqual(self.repo.head(), archived)
            self.assertEqual(fixture.candidate()["state"], "ready")

    def test_checkout_failure_produces_a_blocked_result(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            with mock.patch.object(workers, "prepare_checkout", side_effect=workers.WorkerError("clone failed")):
                outcome, results = self.finalize(fixture)
            self.assertEqual(outcome["status"], "blocked-escalation")
            self.assertEqual(fixture.candidate()["state"], "blocked-escalation")
            self.assertIn("failed: clone failed", results[-1])

    def test_repaired_candidate_requires_developer_semantic_handoff(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture, gates={"review": self.gates()["review"]})
            ran = []
            outcome, _ = self.finalize(fixture, checks_runner=lambda checkout, env: ran.append(checkout))
            self.assertEqual(outcome["status"], "blocked-retryable")
            self.assertEqual(len(ran), 1)
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "blocked-retryable")
            self.assertEqual(candidate["red_gate"]["name"], "semantic-verification")
            self.assertNotIn("semantic-verification", candidate["gates"])
            self.assertIsNone(candidate["next_job"])

    def test_failing_checks_or_missing_review_block_without_archiving(self):
        def failing(checkout, env):
            raise workers.WorkerError("selected checks failed")

        for gates, runner in (({"review": self.gates()["review"]}, failing), ({}, lambda *a: None)):
            with self.subTest(gates=sorted(gates)), RemoteFixture(self.repo) as fixture:
                self.offer(fixture, gates=gates)
                before = self.repo.head()
                outcome, _ = self.finalize(fixture, archiver=lambda *a: self.fail("must not archive"),
                                           checks_runner=runner)
                self.assertEqual(outcome["status"], "blocked-escalation")
                self.assertEqual(self.repo.head(), before)
                self.assertEqual(fixture.candidate()["state"], "blocked-escalation")

    def test_tampered_evidence_file_is_not_reused(self):
        with RemoteFixture(self.repo) as fixture:
            gates = self.gates()
            gates["semantic-verification"]["evidence"]["sha256"] = "0" * 64
            self.offer(fixture, gates=gates)
            outcome, _ = self.finalize(fixture, archiver=lambda *a: self.fail("must not archive"))
            self.assertEqual(outcome["status"], "blocked-escalation")

    def test_archive_touching_other_paths_is_refused(self):
        def archiver(checkout, change, env):
            self.archiver(checkout, change, env)
            (checkout / "openspec/specs/other.md").write_text("x\n")
            (checkout / "src.py").write_text("value = 9\n")

        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            before = self.repo.head()
            outcome, _ = self.finalize(fixture, archiver=archiver)
            self.assertEqual(outcome["status"], "blocked-escalation")
            self.assertEqual(self.repo.head(), before)

    def test_changed_task_content_returns_candidate_to_review(self):
        with RemoteFixture(self.repo) as fixture:
            # A task-content change lands on the branch; the record still carries the reviewed identity.
            (self.repo.root / "src.py").write_text("value = 5\n")
            git(self.repo.root, "commit", "-qam", "later content change")
            self.repo.push("agent/example")
            self.offer(fixture)
            outcome, _ = self.finalize(fixture, archiver=lambda *a: self.fail("must not archive"))
            self.assertEqual(outcome["status"], "returned-to-review")
            moved = fixture.candidate()
            self.assertEqual(moved["state"], "review-pending")
            self.assertNotEqual(moved["task_identity"]["task_content"]["digest"], self.identity["task_content"]["digest"])
            self.assertNotIn("review", moved["gates"])
            self.assertEqual(moved["next_job"]["kind"], "review")

    def test_push_without_ready_transition_recovers_as_ready(self):
        with RemoteFixture(self.repo) as fixture:
            self.offer(fixture)
            original = queue._transition

            def interrupted(root, repo, number, state, *args, **kwargs):
                if state == "ready":
                    raise RuntimeError("coordinator interrupted")
                return original(root, repo, number, state, *args, **kwargs)

            def post(body):
                fixture.comments.append({"id": len(fixture.comments) + 1, "author_association": "OWNER", "body": body})

            with mock.patch.object(queue, "_transition", side_effect=interrupted):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    self.finalize(fixture, post=post)
            fixture.head = self.repo.head()
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "ready")
            self.assertEqual(candidate["next_action"], "await integration")
            self.assertEqual(sorted(candidate["gates"]), ["review", "selected-checks", "semantic-verification"])


class RederivationTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("openspec"):
            self.skipTest("OpenSpec CLI is not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Remote(Path(self.tmp.name))
        root = self.repo.root
        (root / "openspec").mkdir(exist_ok=True)
        (root / "openspec/config.yaml").write_text("schema: spec-driven\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "openspec config")
        git(root, "push", "-q", "origin", "HEAD:main")
        git(root, "fetch", "-q", "origin")
        # Candidate B, archived against the old main.
        git(root, "checkout", "-qb", "agent/b")
        self.make_change("b", "Candidate B behavior")
        self.archive(root, "b")
        self.repo.push("agent/b")
        self.paths = {line for line in git(root, "diff", "--name-only", "origin/main...HEAD").splitlines()}
        # Candidate A then merged to main, extending the same capability.
        git(root, "checkout", "-q", "main")
        self.make_change("a", "Candidate A behavior")
        self.archive(root, "a")
        git(root, "push", "-q", "origin", "HEAD:main")
        git(root, "checkout", "-q", "agent/b")

    def make_change(self, name: str, text: str) -> None:
        change = self.repo.root / "openspec/changes" / name
        (change / "specs/cap").mkdir(parents=True)
        (change / "proposal.md").write_text(f"## Why\nBecause {name}.\n\n## What Changes\n- {text}\n")
        (change / "tasks.md").write_text("- [x] done\n")
        (change / "specs/cap/spec.md").write_text("## ADDED Requirements\n\n" + requirement(text, f"The system SHALL provide {text}."))

    def archive(self, root: Path, name: str) -> None:
        subprocess.run(["openspec", "archive", name, "--yes"], cwd=root, check=True, stdin=subprocess.DEVNULL,
                       capture_output=True)
        git(root, "add", "-A")
        git(root, "commit", "-qm", f"archive {name}")

    def rederive(self, **options):
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            return final.rederive_archived_specs(
                source_repo=self.repo.remote.as_uri(), branch="agent/b", head=self.repo.head("agent/b"),
                task_paths=self.paths, workdir=workdir, **options)

    def test_two_candidates_extending_one_capability_integrate_without_manual_resolution(self):
        before = self.repo.head("agent/b")
        new_head, main_sha = self.rederive()
        self.assertEqual(self.repo.head("agent/b"), new_head)
        parents = git(self.repo.remote, "rev-list", "--parents", "-n", "1", new_head).split()[1:]
        self.assertEqual(parents, [before, main_sha])
        spec = git(self.repo.remote, "show", f"{new_head}:openspec/specs/cap/spec.md")
        for name in ("Base behavior", "Candidate A behavior", "Candidate B behavior"):
            self.assertIn(f"### Requirement: {name}", spec)
        # B's own archive is preserved byte for byte.
        archived = git(self.repo.remote, "ls-tree", "-r", "--name-only", new_head, "openspec/changes/archive")
        self.assertEqual(len([line for line in archived.splitlines() if line.endswith("-b/proposal.md")]), 1)
        self.assertEqual(git(self.repo.remote, "diff", "--name-only", before, f"{new_head}^1"), "")

    def test_lost_update_marker_shape_is_recognized_and_other_merges_are_not(self):
        before = self.repo.head("agent/b")
        new_head, main_sha = self.rederive()
        root = self.repo.root
        git(root, "fetch", "-q", "origin")
        self.assertTrue(final.derived_merge_only(root, new_head, before, main_sha, self.paths))
        # A merge that also changes task content is not accepted.
        git(root, "checkout", "-q", "-b", "tamper", new_head)
        (root / "src.py").write_text("value = 7\n")
        git(root, "commit", "-qam", "tamper")
        self.assertFalse(final.derived_merge_only(root, git(root, "rev-parse", "HEAD"), before, main_sha, {"src.py"}))

    def test_second_run_after_re_derivation_is_a_no_op(self):
        new_head, main_sha = self.rederive()
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir:
            again = final.rederive_archived_specs(
                source_repo=self.repo.remote.as_uri(), branch="agent/b", head=new_head, task_paths=self.paths,
                workdir=workdir, claim_current=lambda: self.fail("must not push"))
        self.assertEqual(again, (new_head, main_sha))
        self.assertEqual(self.repo.head("agent/b"), new_head)

    def test_semantic_conflict_fails_re_derivation_without_pushing(self):
        root = self.repo.root
        # Rebuild B so that it MODIFIES a requirement main has since removed.
        git(root, "checkout", "-q", "main")
        git(root, "checkout", "-qb", "agent/c", "main~1")
        change = root / "openspec/changes/c"
        (change / "specs/cap").mkdir(parents=True)
        (change / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- y\n")
        (change / "tasks.md").write_text("- [x] done\n")
        (change / "specs/cap/spec.md").write_text(
            "## MODIFIED Requirements\n\n" + requirement("Base behavior", "The system SHALL keep the modified base behavior.", "Base"))
        self.archive(root, "c")
        self.repo.push("agent/c")
        paths = set(git(root, "diff", "--name-only", "main~1...HEAD").splitlines())
        # Main drops the base requirement entirely.
        git(root, "checkout", "-q", "main")
        change = root / "openspec/changes/d"
        (change / "specs/cap").mkdir(parents=True)
        (change / "proposal.md").write_text("## Why\nx\n\n## What Changes\n- remove\n")
        (change / "tasks.md").write_text("- [x] done\n")
        (change / "specs/cap/spec.md").write_text("## REMOVED Requirements\n\n### Requirement: Base behavior\n**Reason**: gone\n**Migration**: none\n")
        self.archive(root, "d")
        git(root, "push", "-q", "origin", "HEAD:main")
        before = self.repo.head("agent/c")
        with tempfile.TemporaryDirectory(dir=self.tmp.name) as workdir, \
                self.assertRaises(final.RederivationFailed):
            final.rederive_archived_specs(source_repo=self.repo.remote.as_uri(), branch="agent/c", head=before,
                                          task_paths=paths, workdir=workdir)
        self.assertEqual(self.repo.head("agent/c"), before)

    def test_replay_is_bookkeeping_only_and_strict_validation_failure_stops_it(self):
        before = self.repo.head("agent/b")

        def invalid(checkout):
            raise final.RederivationFailed("strict validation failed")

        with self.assertRaisesRegex(final.RederivationFailed, "strict validation"):
            self.rederive(validate=invalid)
        self.assertEqual(self.repo.head("agent/b"), before)

    def test_lost_claim_prevents_the_push(self):
        before = self.repo.head("agent/b")
        with self.assertRaisesRegex(final.RederivationFailed, "claim lost"):
            self.rederive(claim_current=lambda: False)
        self.assertEqual(self.repo.head("agent/b"), before)


class PreparationTests(unittest.TestCase):
    HEAD, BASE, MAIN = "a" * 40, "b" * 40, "c" * 40
    DELTA = {"openspec/changes/archive/2026-10-06-x/specs/cap/spec.md", "openspec/specs/cap/spec.md", "src.py"}

    def test_derived_paths_are_only_the_candidates_own_capabilities(self):
        overlap = {"openspec/specs/cap/spec.md", "openspec/specs/other/spec.md", "src.py"}
        self.assertEqual(final.derived_spec_paths(self.DELTA, overlap), {"openspec/specs/cap/spec.md"})
        self.assertEqual(final.derived_spec_paths({"src.py"}, overlap), set())

    def prepare(self, overlap, rederive, contains_main=1):
        def run_git(args, **kwargs):
            out = ""
            if args[:2] == ["merge-base", "--is-ancestor"]:
                return subprocess.CompletedProcess(args, 0 if args[2] == self.BASE else contains_main, "", "")
            if args[:2] == ["diff", "--name-only"]:
                out = "\n".join(overlap) + "\n"
            return subprocess.CompletedProcess(args, 0, out, "")

        pr = {"head": {"sha": self.HEAD, "ref": "agent/x"}}
        with mock.patch.object(queue, "run_git", side_effect=run_git), \
                mock.patch.object(queue, "_events", return_value=[]), \
                mock.patch.object(queue, "_main", return_value=self.MAIN), \
                mock.patch.object(queue, "_task_paths", return_value=set(self.DELTA)), \
                mock.patch.object(queue, "_raise_if_owned_elsewhere"), \
                mock.patch.object(final, "prepare_derived_specs", side_effect=rederive) as derived:
            result = queue._prepare(ROOT, "o/r", 7, {"head": self.HEAD, "base": self.BASE, "comment_id": 1}, pr)
        return result, derived

    def test_overlap_confined_to_derived_specs_is_re_derived(self):
        result, derived = self.prepare(["openspec/specs/cap/spec.md"], lambda *a, **k: ("d" * 40, self.MAIN))
        self.assertEqual(result, ("d" * 40, self.MAIN))
        derived.assert_called_once()

    def test_rerun_on_an_already_re_derived_head_does_not_redo_or_fail(self):
        result, derived = self.prepare(["openspec/specs/cap/spec.md"], lambda *a, **k: self.fail("no redo"),
                                       contains_main=0)
        self.assertEqual(result, (self.HEAD, self.MAIN))
        derived.assert_not_called()

    def test_overlap_with_task_content_is_judged_by_the_merge_not_refused(self):
        # Overlap beyond archive-derived specs skips re-derivation; the merge result decides.
        with mock.patch.object(queue, "merge_conflicts", return_value=[]), \
                mock.patch.object(queue, "_gh"), mock.patch.object(queue.time, "sleep"), \
                mock.patch.object(queue, "_comment"), \
                mock.patch.object(queue, "_pr", return_value={"number": 7, "head": {"sha": "d" * 40}}):
            result, derived = self.prepare(["openspec/specs/cap/spec.md", "src.py"],
                                           lambda *a, **k: self.fail("must not re-derive"))
        self.assertEqual(result, ("d" * 40, self.MAIN))
        derived.assert_not_called()

    def test_failed_re_derivation_becomes_integration_repair(self):
        def failing(*args, **kwargs):
            raise final.RederivationFailed("replay failed")

        with self.assertRaisesRegex(queue.IntegrationRepairNeeded, "replay failed"):
            self.prepare(["openspec/specs/cap/spec.md"], failing)

    def test_worker_records_integration_repair_instead_of_blocking(self):
        identity = {"branch": "agent/x", "head": self.HEAD}
        with QueueFixture(ROOT, self.HEAD) as fixture:
            queue._transition(ROOT, "o/r", 7, "ready", self.HEAD, task_identity=identity, inherit_identity=False)
            with mock.patch.object(queue, "_repo", return_value="o/r"), \
                    mock.patch.object(queue, "_queued", return_value=[(1, 7, {"branch": "agent/x"})]), \
                    mock.patch.object(queue, "_require_finalized"), \
                    mock.patch.object(queue, "_prepare", side_effect=queue.IntegrationRepairNeeded("replay failed")), \
                    mock.patch.object(queue, "_label"), \
                    mock.patch.object(queue, "_block") as block:
                result = queue.worker(ROOT)
            block.assert_not_called()
            self.assertEqual(result["state"], "waiting")
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "integration-repair-pending")
            self.assertEqual(candidate["red_gate"]["name"], "integration")

    def test_unfinalized_candidate_returns_to_finalize_pending(self):
        identity = {"change": "example", "task_content": {"version": 1, "digest": "d", "paths": {}, "base": self.BASE}}
        with QueueFixture(ROOT, self.HEAD) as fixture:
            queue._transition(ROOT, "o/r", 7, "ready", self.HEAD, task_identity=identity, inherit_identity=False)
            with mock.patch.object(queue, "_repo", return_value="o/r"), \
                    mock.patch.object(queue, "_queued", return_value=[(1, 7, {"branch": "agent/x"})]), \
                    mock.patch.object(queue, "_require_finalized", side_effect=queue.NotFinalized("still active")), \
                    mock.patch.object(queue, "_prepare") as prepare, \
                    mock.patch.object(queue, "_label"), \
                    mock.patch.object(queue, "_block") as block:
                result = queue.worker(ROOT)
            prepare.assert_not_called()
            block.assert_not_called()
            self.assertEqual(result["state"], "waiting")
            candidate = fixture.candidate()
            self.assertEqual(candidate["state"], "finalize-pending")
            self.assertEqual(workers.build_job(candidate)["kind"], "finalize")

    def test_worker_blocks_an_unfinalized_candidate_before_integration(self):
        identity = {"branch": "agent/x", "head": self.HEAD}
        with QueueFixture(ROOT, self.HEAD) as fixture:
            queue._transition(ROOT, "o/r", 7, "ready", self.HEAD, task_identity=identity, inherit_identity=False)
            with mock.patch.object(queue, "_repo", return_value="o/r"), \
                    mock.patch.object(queue, "_queued", return_value=[(1, 7, {"branch": "agent/x"})]), \
                    mock.patch.object(queue, "_require_finalized", side_effect=queue.QueueError("completed OpenSpec change is still active")), \
                    mock.patch.object(queue, "_prepare") as prepare, \
                    mock.patch.object(queue, "_label"), \
                    mock.patch.object(queue, "_block", return_value={"state": "blocked"}) as block:
                queue.worker(ROOT)
            prepare.assert_not_called()
            self.assertIn("still active", block.call_args.args[3])
            del fixture


if __name__ == "__main__":
    unittest.main()
