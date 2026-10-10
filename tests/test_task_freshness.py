from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _platform_common  # noqa: E402
import project_publish  # noqa: E402
import task_reconciliation  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "freshness@example.invalid", cwd=root)
    git("config", "user.name", "Freshness Test", cwd=root)


class TaskFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"
        run("git", "init", "-b", "main", str(self.seed), cwd=self.base)
        configure(self.seed)
        (self.seed / "README.md").write_text("seed\n", encoding="utf-8")
        git("add", "README.md", cwd=self.seed)
        git("commit", "-m", "seed", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.task = self.base / "task"
        run("git", "clone", str(self.remote), str(self.task), cwd=self.base)
        configure(self.task)
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\n', encoding="utf-8"
        )
        checks = self.task / "dev-platform" / "checks.toml"
        checks.parent.mkdir()
        checks.write_text(
            '[settings]\nfull_commands = ["printf full-validation-ran > validation-ran.txt"]\n', encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def selector(self) -> subprocess.CompletedProcess[str]:
        return run(
            "python3", str(SCRIPTS / "select_checks.py"), "--mode", "protected-full", "--execute", cwd=self.task, check=False
        )

    def advance_main(self) -> None:
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / "main.txt").write_text("advanced\n", encoding="utf-8")
        git("add", "main.txt", cwd=other)
        git("commit", "-m", "advance main", cwd=other)
        git("push", cwd=other)

    def test_fresh_task_runs_the_selected_full_command(self) -> None:
        result = self.selector()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Task freshness gate passed", result.stdout)
        self.assertIn("DEV_PLATFORM_CHECK_COMMAND: printf full-validation-ran", result.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_stale_task_stops_before_full_validation_and_retry_after_reconciliation_runs_it(self) -> None:
        self.advance_main()

        stale = self.selector()
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("Task freshness gate blocked full/protected validation before any expensive command started", stale.stderr + stale.stdout)
        self.assertIn("behind relative", stale.stderr + stale.stdout)
        self.assertFalse((self.task / "validation-ran.txt").exists())
        self.assertNotIn("DEV_PLATFORM_CHECK_COMMAND", stale.stdout)

        git("merge", "--ff-only", "origin/main", cwd=self.task)
        retried = self.selector()
        self.assertEqual(retried.returncode, 0, retried.stderr + retried.stdout)
        self.assertIn("Task freshness gate passed", retried.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_contribution_is_fresh_against_its_exact_base_while_main_moves(self) -> None:
        base = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        (self.task / "task.txt").write_text("contribution\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task)
        git("commit", "-m", "contribution", cwd=self.task)
        self.advance_main()

        result = run(
            "python3", str(SCRIPTS / "select_checks.py"), "--mode", "protected-full", "--execute",
            "--contribution-base", base, cwd=self.task, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(f"HEAD contains its exact contribution base ({base})", result.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_contribution_missing_its_exact_base_stops_before_validation(self) -> None:
        self.advance_main()
        git("fetch", "origin", cwd=self.task)
        foreign = git("rev-parse", "origin/main", cwd=self.task).stdout.strip()

        result = run(
            "python3", str(SCRIPTS / "select_checks.py"), "--mode", "protected-full", "--execute",
            "--contribution-base", foreign, cwd=self.task, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"HEAD does not contain its exact contribution base {foreign}", result.stderr + result.stdout)
        self.assertFalse((self.task / "validation-ran.txt").exists())

    def test_unavailable_remote_never_claims_the_task_is_fresh(self) -> None:
        git("remote", "set-url", "origin", str(self.base / "missing.git"), cwd=self.task)

        result = self.selector()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unable to refresh authoritative origin/main", result.stderr + result.stdout)
        self.assertFalse((self.task / "validation-ran.txt").exists())

    def test_project_harness_keeps_its_existing_validation_runner_ownership(self) -> None:
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "project"\n', encoding="utf-8"
        )
        git("remote", "set-url", "origin", str(self.base / "missing.git"), cwd=self.task)

        result = self.selector()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn("Task freshness gate", result.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_helper_reports_diverged_task_without_reconciliation(self) -> None:
        self.advance_main()
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task)
        git("commit", "-m", "task diverges", cwd=self.task)

        with self.assertRaisesRegex(_platform_common.TaskFreshnessError, "diverged relative"):
            _platform_common.require_fresh_task_base(self.task, "origin", "main")
        self.assertEqual(git("log", "-1", "--format=%s", cwd=self.task).stdout.strip(), "task diverges")

    def test_issue_219_readonly_observation_reports_new_main_without_updating_tracking_refs(self) -> None:
        before = git("rev-parse", "origin/main", cwd=self.task).stdout.strip()
        self.advance_main()

        state, observed = _platform_common.observe_task_base_freshness_readonly(self.task, "origin", "main")

        self.assertEqual(state, "behind")
        self.assertNotEqual(observed, before)
        self.assertEqual(git("rev-parse", "origin/main", cwd=self.task).stdout.strip(), before)


class TaskBaseCurrencyTests(unittest.TestCase):
    """The behind-disjoint classifier and the coordinator handoff gates, on real Git history."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "-q", "--bare", "-b", "main", str(self.remote), cwd=self.base)
        self.task = self.base / "task"
        run("git", "clone", "-q", str(self.remote), str(self.task), cwd=self.base)
        configure(self.task)
        git("checkout", "-q", "-b", "main", cwd=self.task)
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\npublish_mode = "pr"\n',
            encoding="utf-8",
        )
        (self.task / "shared.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        git("add", "-A", cwd=self.task)
        git("commit", "-qm", "seed", cwd=self.task)
        git("push", "-q", "-u", "origin", "main", cwd=self.task)
        self.seed = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        git("checkout", "-q", "-b", "agent/task", cwd=self.task)
        self.other = self.base / "other"
        run("git", "clone", "-q", str(self.remote), str(self.other), cwd=self.base)
        configure(self.other)

    def commit(self, root: Path, message: str, files: dict[str, str | None]) -> None:
        for name, content in files.items():
            if content is None:
                git("rm", "-q", name, cwd=root)
                continue
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(content, encoding="utf-8")
            git("add", name, cwd=root)
        git("commit", "-qm", message, cwd=root)

    def advance_main(self, files: dict[str, str | None]) -> str:
        self.commit(self.other, "advance main", files)
        git("push", "-q", "origin", "HEAD:main", cwd=self.other)
        return git("rev-parse", "HEAD", cwd=self.other).stdout.strip()

    def classify(self) -> _platform_common.TaskBaseCurrency:
        return _platform_common.observe_task_base_currency(self.task, "origin", "main")

    def test_head_containing_main_is_fresh(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})

        currency = self.classify()

        self.assertEqual(currency.state, "fresh")
        self.assertEqual(currency.main, self.seed)

    def test_disjoint_main_with_a_clean_trial_merge_is_behind_disjoint(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        main = self.advance_main({"main.txt": "main\n"})

        currency = self.classify()

        self.assertEqual(currency.state, "behind-disjoint")
        self.assertEqual((currency.main, currency.base), (main, self.seed))
        self.assertEqual(currency.evidence(), {"contract": "behind-disjoint", "main": main, "base": self.seed})
        # Classification never merges or moves the task head.
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.task).stdout.strip(), head)

    def test_a_file_both_sides_changed_requires_reconcile_even_when_it_merges_cleanly(self) -> None:
        self.commit(self.task, "task", {"shared.txt": "ONE\ntwo\nthree\n"})
        self.advance_main({"shared.txt": "one\ntwo\nTHREE\n", "main.txt": "main\n"})

        currency = self.classify()

        self.assertEqual(currency.state, "reconcile-required")
        self.assertEqual(currency.overlapping, ("shared.txt",))
        self.assertIn("main and the task both changed shared.txt", currency.describe("origin/main"))
        with self.assertRaises(ValueError):
            currency.evidence()

    def test_a_rename_on_main_counts_its_old_path(self) -> None:
        self.commit(self.task, "task", {"shared.txt": "ONE\ntwo\nthree\n"})
        self.advance_main({"shared.txt": None, "moved.txt": "one\ntwo\nthree\n"})

        currency = self.classify()

        self.assertEqual(currency.state, "reconcile-required")
        self.assertEqual(currency.overlapping, ("shared.txt",))

    def test_a_conflicting_trial_merge_of_disjoint_files_requires_reconcile(self) -> None:
        # Disjoint paths that still conflict: main adds a file where the task adds a directory.
        self.commit(self.task, "task", {"entry/inner.txt": "task\n"})
        self.advance_main({"entry": "main\n"})

        currency = self.classify()

        self.assertEqual(currency.state, "reconcile-required")
        self.assertEqual(currency.overlapping, ())
        self.assertTrue(currency.conflicts)
        self.assertIn("a trial merge conflicts", currency.describe("origin/main"))

    def test_no_merge_base_fails_explicitly(self) -> None:
        git("checkout", "-q", "--orphan", "agent/unrelated", cwd=self.task)
        self.commit(self.task, "unrelated", {"task.txt": "task\n"})
        self.advance_main({"main.txt": "main\n"})

        with self.assertRaisesRegex(_platform_common.TaskFreshnessError, "has no merge base with main"):
            self.classify()

    def test_git_without_trial_merge_support_fails_explicitly(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        self.advance_main({"main.txt": "main\n"})
        real = _platform_common.run_git

        def old_git(args, *rest, **kwargs):
            if args == ["version"]:
                return subprocess.CompletedProcess(["git", "version"], 0, "git version 2.37.1\n", "")
            return real(args, *rest, **kwargs)

        with mock.patch.object(_platform_common, "run_git", side_effect=old_git):
            with self.assertRaisesRegex(_platform_common.TaskFreshnessError, "git 2.37 cannot run a trial merge"):
                self.classify()

    def test_handoff_gate_accepts_behind_disjoint_only_for_a_coordinator_candidate(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        self.advance_main({"main.txt": "main\n"})

        with mock.patch.object(_platform_common, "coordinator_candidate", return_value=True):
            currency = _platform_common.require_handoff_task_base(self.task, "origin", "main")
        self.assertEqual(currency.state, "behind-disjoint")
        with mock.patch.object(_platform_common, "coordinator_candidate", return_value=False):
            with self.assertRaisesRegex(_platform_common.TaskFreshnessError, "diverged relative to freshly observed origin/main"):
                _platform_common.require_handoff_task_base(self.task, "origin", "main")

    def test_handoff_gate_names_the_overlap_and_the_reconcile_command(self) -> None:
        self.commit(self.task, "task", {"shared.txt": "ONE\ntwo\nthree\n"})
        self.advance_main({"shared.txt": "one\ntwo\nTHREE\n"})

        with mock.patch.object(_platform_common, "coordinator_candidate", return_value=True):
            with self.assertRaisesRegex(_platform_common.TaskFreshnessError,
                                        r"both changed shared.txt; reconcile first \(python3 scripts/finish_task.py --reconcile\)"):
                _platform_common.require_handoff_task_base(self.task, "origin", "main")

    def push(self, *, coordinator_handoff: bool) -> str:
        output = StringIO()
        with mock.patch.object(project_publish, "preflight"), redirect_stdout(output):
            project_publish.push_feature_branch(self.task, "origin", "main", require_fresh_base=True,
                                                coordinator_handoff=coordinator_handoff)
        return output.getvalue()

    def remote_branch(self) -> str:
        return run("git", "--git-dir", str(self.remote), "rev-parse", "--verify", "-q", "refs/heads/agent/task",
                   cwd=self.base, check=False).stdout.strip()

    def test_developer_handoff_pushes_a_behind_disjoint_candidate_and_names_the_contract(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        main = self.advance_main({"main.txt": "main\n"})

        output = self.push(coordinator_handoff=True)

        self.assertIn("Task base contract behind-disjoint", output)
        self.assertIn(f"origin/main ({main})", output)
        self.assertIn(f"merge base {self.seed}", output)
        self.assertEqual(self.remote_branch(), head)

    def test_developer_handoff_of_an_overlapping_candidate_is_blocked_before_push(self) -> None:
        self.commit(self.task, "task", {"shared.txt": "ONE\ntwo\nthree\n"})
        self.advance_main({"shared.txt": "one\ntwo\nTHREE\n"})

        with self.assertRaisesRegex(SystemExit, r"both changed shared.txt\. Reconcile explicitly \(python3 scripts/finish_task.py --reconcile\)"):
            self.push(coordinator_handoff=True)
        self.assertEqual(self.remote_branch(), "")

    def test_publication_outside_the_coordinator_handoff_keeps_the_fresh_base_rule(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        self.advance_main({"main.txt": "main\n"})

        with self.assertRaisesRegex(SystemExit, "does not contain current origin/main"):
            self.push(coordinator_handoff=False)
        self.assertEqual(self.remote_branch(), "")

    def test_status_reports_behind_disjoint_candidate_without_reconcile_or_moving_origin_main(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        main = self.advance_main({"main.txt": "main\n"})

        with mock.patch.object(task_reconciliation, "coordinator_candidate", return_value=True):
            payload = task_reconciliation.status_payload(self.task)

        self.assertEqual(payload["task_freshness"], "behind-disjoint")
        self.assertFalse(payload["reconcile_required"])
        self.assertIsNone(payload["reconcile_command"])
        self.assertEqual((payload["authoritative_main"], payload["task_merge_base"]), (main, self.seed))
        # Read-only status fetched only objects: the remote-tracking ref did not move.
        self.assertEqual(git("rev-parse", "origin/main", cwd=self.task).stdout.strip(), self.seed)

    def test_status_of_an_overlapping_candidate_requires_reconcile_and_names_the_file(self) -> None:
        self.commit(self.task, "task", {"shared.txt": "ONE\ntwo\nthree\n"})
        self.advance_main({"shared.txt": "one\ntwo\nTHREE\n"})

        with mock.patch.object(task_reconciliation, "coordinator_candidate", return_value=True):
            payload = task_reconciliation.status_payload(self.task)

        self.assertEqual(payload["task_freshness"], "diverged")
        self.assertTrue(payload["reconcile_required"])
        self.assertIn("both changed shared.txt", payload["freshness_detail"])

    def test_status_of_a_non_candidate_behind_main_still_requires_reconcile(self) -> None:
        self.commit(self.task, "task", {"task.txt": "task\n"})
        self.advance_main({"main.txt": "main\n"})

        with mock.patch.object(task_reconciliation, "coordinator_candidate", return_value=False):
            payload = task_reconciliation.status_payload(self.task)

        # Unchanged read-only status: main's commit is absent locally, so it reports "behind".
        self.assertEqual(payload["task_freshness"], "behind")
        self.assertTrue(payload["reconcile_required"])


if __name__ == "__main__":
    unittest.main()
