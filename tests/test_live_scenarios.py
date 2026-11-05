"""Local guards of the live scenario runner. The scenarios themselves run only on real GitHub."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("live_scenarios", ROOT / "scripts" / "live_scenarios.py")
live = importlib.util.module_from_spec(spec)
sys.modules["live_scenarios"] = live
spec.loader.exec_module(live)


class TargetGuardTest(unittest.TestCase):
    def setUp(self):
        self.config = live.load_config()

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
        config = live.load_config()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "tree"
            destination.mkdir()
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
            live.compose_snapshot(head, destination, config, ROOT)
            workflows = sorted(path.name for path in (destination / ".github" / "workflows").iterdir())
            self.assertEqual(workflows, ["ci.yml", "lifecycle-workers.yml", "publication-queue.yml"])
            self.assertEqual((destination / live.HEAD_MARKER).read_text(encoding="utf-8").strip(), head)
            self.assertIn("dev-platform-sandbox", (destination / "dev-platform" / "source-contract.toml").read_text(encoding="utf-8"))
            self.assertFalse((destination / "tests").exists())
            self.assertTrue((destination / "template" / "scripts" / "publication_queue.py").is_file())


class WorkdirTest(unittest.TestCase):
    def test_foreign_directory_is_refused_and_kept(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "precious").write_text("x", encoding="utf-8")
            sandbox = live.Sandbox(live.load_config(), workdir, "a" * 40)
            with self.assertRaisesRegex(live.SandboxError, "not a runner workdir"):
                sandbox.prepare_workdir()
            self.assertTrue((workdir / "precious").exists())


class LockTest(unittest.TestCase):
    def setUp(self):
        self.lock = live.Lock(live.load_config(), now=lambda: 1000)

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
        self.assertEqual(results, [{"scenario": "dead-end", "result": "failed", "step": "queue merges", "observed": "still open"}])


if __name__ == "__main__":
    unittest.main()
