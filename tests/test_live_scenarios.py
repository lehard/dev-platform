"""Local guards of the live scenario runner. The scenarios themselves run only on real GitHub."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

load_platform_module("live_scenario_gate", ROOT / "scripts" / "live_scenario_gate.py")
live = load_platform_module("live_scenarios", ROOT / "scripts" / "live_scenarios.py")

# The real sandbox.toml is operator state and absent from public snapshots.
CONFIG = live.Config("owner/sandbox", "sandbox-app", 1, "validate", "finalize",
                     ("publication-queue.yml", "lifecycle-workers.yml"),
                     ("openspec/changes", "dev-platform/live-sandbox"), ("checks", "actions"), "Sandbox Project")


class TargetGuardTest(unittest.TestCase):
    def setUp(self):
        self.config = CONFIG

    def test_only_the_configured_private_sandbox_passes(self):
        live.assert_target(self.config, self.config.repository, source_origin="https://github.com/lehard/dev-platform.git", private=True)

    def test_another_repository_is_refused(self):
        with self.assertRaisesRegex(live.SandboxError, "not the configured sandbox"):
            live.assert_target(self.config, "lehard/dev-platform", source_origin="x", private=True)

    def test_a_public_sandbox_is_refused(self):
        with self.assertRaisesRegex(live.SandboxError, "not private"):
            live.assert_target(self.config, self.config.repository, source_origin="x", private=False)

    def test_the_platform_origin_is_refused(self):
        with self.assertRaisesRegex(live.SandboxError, "own origin"):
            live.assert_target(self.config, self.config.repository,
                               source_origin=f"https://github.com/{self.config.repository}.git", private=True)


class SnapshotTest(unittest.TestCase):
    def test_snapshot_keeps_queue_workflows_and_applies_the_overlay(self):
        config = CONFIG
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "tree"
            destination.mkdir()
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
            live.compose_snapshot(head, destination, config, ROOT)
            workflows = sorted(path.name for path in (destination / ".github" / "workflows").iterdir())
            self.assertEqual(workflows, ["ci.yml", "lifecycle-workers.yml", "publication-queue.yml"])
            self.assertEqual((destination / live.HEAD_MARKER).read_text(encoding="utf-8").strip(), head)
            self.assertIn("dev-platform-sandbox", (destination / "dev-platform" / "source-contract.toml").read_text(encoding="utf-8"))
            self.assertFalse((destination / "dev-platform" / "live-sandbox").exists())
            queue = (destination / ".github" / "workflows" / "publication-queue.yml").read_text(encoding="utf-8")
            self.assertIn("permission-checks: read", queue)
            self.assertTrue((destination / "template" / "scripts" / "publication_queue.py").is_file())
            self.assertEqual(sorted(path.name for path in Path(temporary).iterdir()), ["tree"])

    def test_the_overlay_comes_from_the_installed_head(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, destination = Path(temporary) / "source", Path(temporary) / "tree"
            destination.mkdir()
            overlay = source / "dev-platform" / "live-sandbox" / "overlay"
            workflows = source / ".github" / "workflows"
            overlay.mkdir(parents=True)
            workflows.mkdir(parents=True)
            for name in CONFIG.kept_workflows:
                (workflows / name).write_text("permission-pull-requests: write\n", encoding="utf-8")
            (overlay / "marker.txt").write_text("committed\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(["git", "add", "-A"], cwd=source, check=True)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "x"],
                           cwd=source, check=True)
            (overlay / "marker.txt").write_text("working tree\n", encoding="utf-8")
            live.compose_snapshot("HEAD", destination, CONFIG, source)
            self.assertEqual((destination / "marker.txt").read_text(encoding="utf-8"), "committed\n")


class TokenReadsTest(unittest.TestCase):
    def test_every_token_step_gets_the_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            workflow = Path(temporary) / "queue.yml"
            workflow.write_text("        with:\n          permission-pull-requests: write\n", encoding="utf-8")
            live.grant_token_reads(workflow, ("checks", "actions"))
            self.assertEqual(workflow.read_text(encoding="utf-8").splitlines()[2:],
                             ["          permission-checks: read", "          permission-actions: read"])

    def test_a_workflow_without_the_token_step_stops_the_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            workflow = Path(temporary) / "queue.yml"
            workflow.write_text("jobs: {}\n", encoding="utf-8")
            with self.assertRaisesRegex(live.SandboxError, "no `permission-pull-requests: write` line"):
                live.grant_token_reads(workflow, ("checks",))


class WorkdirTest(unittest.TestCase):
    def test_foreign_directory_is_refused_and_kept(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "precious").write_text("x", encoding="utf-8")
            sandbox = live.Sandbox(CONFIG, workdir, "a" * 40)
            with self.assertRaisesRegex(live.SandboxError, "not a runner workdir"):
                sandbox.prepare_workdir()
            self.assertTrue((workdir / "precious").exists())


class LockTest(unittest.TestCase):
    def setUp(self):
        self.lock = live.Lock(CONFIG, now=lambda: 1000)

    def test_live_lease_refuses_a_second_run(self):
        with mock.patch.object(self.lock, "_create", return_value=False), \
                mock.patch.object(live, "gh_json", return_value={"value": "other 2000"}), \
                self.assertRaisesRegex(live.SandboxError, "run other holds"):
            self.lock.acquire()

    def test_expired_lease_is_taken_over(self):
        with mock.patch.object(self.lock, "_create", side_effect=[False, True]) as create, \
                mock.patch.object(live, "gh_json", return_value={"value": "dead 500"}), \
                mock.patch.object(live, "run") as run:
            self.lock.acquire()
        self.assertEqual(create.call_count, 2)
        self.assertIn("DELETE", run.call_args.args[0])


class ResultTest(unittest.TestCase):
    def test_failed_step_is_reported_by_name(self):
        def dead_end(scenario):
            scenario.step("queue merges")
            raise scenario.fail("still open")

        with mock.patch.dict(live.SCENARIOS, {"dead-end": dead_end}):
            results = live.run_scenarios(mock.Mock(), ["dead-end"])
        self.assertEqual(results, [{"scenario": "dead-end", "result": "failed", "step": "queue merges", "observed": "still open", "seconds": 0}])

    def test_a_command_error_inside_a_scenario_names_the_step_and_keeps_results(self):
        def broken(scenario):
            scenario.step("change")
            raise live.SandboxError("git commit exited 1")

        with mock.patch.dict(live.SCENARIOS, {"broken": broken, "next": lambda scenario: None}):
            results = live.run_scenarios(mock.Mock(), ["broken", "next"])
        self.assertEqual(results, [{"scenario": "broken", "result": "failed", "step": "change", "observed": "git commit exited 1", "seconds": 0},
                                   {"scenario": "next", "result": "passed", "seconds": 0}])


class CommandErrorTest(unittest.TestCase):
    def test_both_streams_reach_the_error(self):
        script = "import sys; print('queued on stdout'); print('warning', file=sys.stderr); sys.exit(2)"
        with self.assertRaises(live.SandboxError) as caught:
            live.run([sys.executable, "-c", script], ROOT)
        self.assertIn("queued on stdout", caught.exception.output)
        self.assertIn("warning", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
