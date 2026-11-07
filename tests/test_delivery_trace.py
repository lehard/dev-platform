"""The trace finish leaves on the published head and the required check that reads it (DEC-0011)."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import delivery_trace  # noqa: E402
import project_publish  # noqa: E402


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


class TraceRepository(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "trace@example.invalid")
        git(self.root, "config", "user.name", "Trace Test")
        self.write("base\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "Do the task")

    def write(self, text: str) -> None:
        (self.root / "task.txt").write_text(text, encoding="utf-8")

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD")

    def stamp(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            delivery_trace.stamp(self.root)

    def check(self, head: str) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "delivery_trace.py"), "check", "--head", head],
            cwd=self.root, text=True, capture_output=True, check=False,
        )
        return result.returncode, result.stdout + result.stderr


class CheckTests(TraceRepository):
    def test_a_stamped_head_passes(self) -> None:
        self.stamp()
        self.assertEqual(self.check(self.head())[0], 0)

    def test_a_head_without_a_trace_is_refused_with_the_reason_and_next_command(self) -> None:
        code, output = self.check(self.head())
        self.assertEqual(code, 1)
        self.assertIn("did not pass through finish", output)
        self.assertIn("python3 scripts/dogfood_task.py finish", output)

    def test_a_commit_on_top_of_the_trace_is_refused(self) -> None:
        self.stamp()
        self.write("late\n")
        git(self.root, "commit", "-qam", "Late edit")
        self.assertEqual(self.check(self.head())[0], 1)

    def test_an_amend_that_keeps_the_message_is_refused_naming_both_trees(self) -> None:
        self.stamp()
        recorded = git(self.root, "rev-parse", "HEAD^{tree}")
        self.write("amended\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--amend", "--no-edit")
        code, output = self.check(self.head())
        self.assertEqual(code, 1)
        self.assertIn(recorded, output)
        self.assertIn(git(self.root, "rev-parse", "HEAD^{tree}"), output)
        self.assertIn("changed after finish", output)

    def test_two_trailers_are_refused(self) -> None:
        tree = git(self.root, "rev-parse", "HEAD^{tree}")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "Twice", "-m",
            f"{delivery_trace.TRAILER}: {tree}\n{delivery_trace.TRAILER}: {tree}")
        code, output = self.check(self.head())
        self.assertEqual(code, 1)
        self.assertIn("2 Dev-Platform-Finish trailers", output)

    def test_an_unknown_head_stops_with_the_git_error(self) -> None:
        code, output = self.check("0" * 40)
        self.assertNotEqual(code, 0)
        self.assertIn("rev-parse", output)

    def test_the_check_reads_the_named_head_not_the_checked_out_merge(self) -> None:
        git(self.root, "switch", "-q", "-c", "agent/task")
        self.write("task\n")
        git(self.root, "commit", "-qam", "Task")
        self.stamp()
        head = self.head()
        git(self.root, "switch", "-q", "main")
        (self.root / "main.txt").write_text("main\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "Advance main")
        git(self.root, "merge", "-q", "--no-ff", "--no-edit", "agent/task")
        self.assertEqual(self.check(head)[0], 0)
        self.assertEqual(self.check("HEAD")[0], 1, "a merge commit carries no trace, so reading HEAD would refuse every PR")


class EnsureTests(TraceRepository):
    def setting(self, value: object) -> mock._patch:
        return mock.patch.object(delivery_trace, "_settings", return_value=value)

    def ensure(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            delivery_trace.ensure(self.root)

    def test_the_trace_is_empty_and_keeps_the_subject(self) -> None:
        before = self.head()
        tree = git(self.root, "rev-parse", "HEAD^{tree}")
        with self.setting({"delivery_trace": True}):
            self.ensure()
        self.assertEqual(git(self.root, "rev-parse", "HEAD~1"), before)
        self.assertEqual(git(self.root, "rev-parse", "HEAD^{tree}"), tree)
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "Do the task")

    def test_a_traced_head_gets_no_second_commit(self) -> None:
        with self.setting({"delivery_trace": True}):
            self.ensure()
            head = self.head()
            self.ensure()
        self.assertEqual(self.head(), head)

    def test_a_project_without_the_setting_gets_no_commit(self) -> None:
        head = self.head()
        with self.setting({}):
            self.ensure()
        self.assertEqual(self.head(), head)

    def test_a_project_without_a_check_configuration_gets_no_commit(self) -> None:
        head = self.head()
        with mock.patch("_platform_common.read_platform_config", return_value={"paths": {"checks": "dev-platform/checks.toml"}}):
            self.ensure()
        self.assertEqual(self.head(), head)

    def test_a_setting_that_is_not_a_boolean_stops_naming_it(self) -> None:
        with self.setting({"delivery_trace": "yes"}), self.assertRaisesRegex(SystemExit, "delivery_trace must be a boolean"):
            self.ensure()

    def test_publication_binds_the_traced_head(self) -> None:
        with (
            self.setting({"delivery_trace": True}),
            mock.patch.object(project_publish, "require_delivery_provenance", return_value=None),
            mock.patch.object(project_publish, "_private_reference_guard", return_value=None),
            mock.patch.object(project_publish, "_validate_feature_branch", return_value="main"),
            mock.patch.object(project_publish, "require_gh_environment", return_value={}),
            mock.patch.object(project_publish, "find_exact_head_pr", side_effect=SystemExit("stop")) as lookup,
            self.assertRaises(SystemExit),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            project_publish.publish_pr(self.root, "origin", "main", None, None, "auto", config={})
        self.assertEqual(lookup.call_args.args[4], self.head())
        self.assertIsNone(delivery_trace.refusal(self.root, self.head()))


class BoundaryTests(unittest.TestCase):
    def test_this_repository_enables_the_trace_and_the_template_does_not(self) -> None:
        checks = tomllib.loads((ROOT / "dev-platform" / "checks.toml").read_text(encoding="utf-8"))
        template = tomllib.loads((ROOT / "template" / "dev-platform" / "checks.toml").read_text(encoding="utf-8"))
        self.assertIs(checks["settings"]["delivery_trace"], True)
        self.assertNotIn("delivery_trace", template.get("settings", {}))

    def test_the_guard_reads_the_event_head_and_runs_before_the_expensive_steps(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}", workflow)
        self.assertIn('scripts/delivery_trace.py check --head "$PR_HEAD_SHA"', workflow)
        self.assertLess(workflow.index("delivery_trace.py check"), workflow.index("name: Unit tests"))

    def test_no_rendered_workflow_contains_the_guard(self) -> None:
        for workflow in (ROOT / "template" / ".github" / "workflows").iterdir():
            self.assertNotIn("delivery_trace", workflow.read_text(encoding="utf-8"), workflow.name)


if __name__ == "__main__":
    unittest.main()
