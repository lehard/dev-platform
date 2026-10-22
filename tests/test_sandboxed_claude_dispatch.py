from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import test_model_routing as base  # noqa: E402  (fixtures only; its TestCases stay in their own module)

routing = base.routing
sandboxed_writer = base.load("sandboxed_writer", "sandboxed_writer.py")


def writer_script(body: str, result: dict | None = None) -> str:
    payload = json.dumps(result if result is not None else {"type": "result", "is_error": False, "session_id": "sess-1"})
    return "import json, pathlib\n" + body + f"\nprint({payload!r})\n"


class SandboxedClaudeDispatchTests(unittest.TestCase):
    setUp = base.ModelRoutingTests.setUp
    tearDown = base.ModelRoutingTests.tearDown
    prepare = base.ModelRoutingTests.prepare
    record_path = base.ModelRoutingTests.record_path
    durable_record_path = base.ModelRoutingTests.durable_record_path

    def launcher(self, body: str, *, result: dict | None = None, returncode: int = 0, during=None):
        """A launch stand-in that runs a real child process in the writer checkout through the given runner."""
        calls = []

        def launch(argv, checkout, *, integration_root, platform_root, workdir, home, tmp, config, runner):
            calls.append({"argv": argv, "checkout": checkout, "integration_root": integration_root})
            code = writer_script(body, result) + (f"\nraise SystemExit({returncode})\n" if returncode else "")
            done = runner([sys.executable, "-c", code], cwd=checkout, env=None, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, check=False, timeout=60)
            if during is not None:
                during()
            return done

        return launch, calls

    def dispatch(self, launcher):
        with patch.object(routing, "main_root", return_value=self.integration):
            return routing.dispatch_claude_sandboxed(self.task, prompt="implement the change", launcher=launcher)

    def saved(self) -> dict:
        return json.loads(self.record_path().read_text(encoding="utf-8"))

    def test_completed_writer_patch_is_applied_and_launch_is_platform_observed(self) -> None:
        self.prepare(provider="claude")
        launch, calls = self.launcher(
            "pathlib.Path('README.md').write_text('changed by writer\\n')\n"
            "pathlib.Path('src').mkdir()\npathlib.Path('src/new.py').write_text('x = 1\\n')\n"
            "assert pathlib.Path('openspec/changes/routing-change/.managed-task.json').is_file()\n")
        output = self.dispatch(launch)
        self.assertEqual((self.task / "README.md").read_text(), "changed by writer\n")
        self.assertEqual((self.task / "src" / "new.py").read_text(), "x = 1\n")
        self.assertEqual(calls[0]["argv"][:2], ["claude", "-p"])
        self.assertIn("--permission-mode", calls[0]["argv"])
        self.assertEqual(calls[0]["argv"][-1], "implement the change")
        self.assertNotEqual(Path(calls[0]["checkout"]).resolve(), self.task.resolve())
        record = self.saved()
        execution, delegation = record["execution"], record["execution_plan"]["delegation"]
        self.assertEqual(execution["outcome"], "completed")
        self.assertTrue(execution["launched"])
        self.assertEqual(execution["mechanism"], "sandbox-runtime")
        self.assertEqual(execution["launch_evidence"], "platform-observed")
        self.assertEqual(execution["participant"]["provider"], "claude")
        self.assertEqual(execution["participant"]["execution_id"], {"value": "sess-1", "kind": "claude-session"})
        self.assertEqual(sorted(execution["changed_paths"]), ["README.md", "src/new.py"])
        self.assertEqual(delegation["state"], "closed")
        self.assertEqual(delegation["launch_evidence"], "platform-observed")
        self.assertTrue(Path(execution["patch"]["path"]).is_file())
        self.assertEqual(output["execution"]["outcome"], "completed")
        self.assertIsNone(output["workdir"])
        self.assertFalse(Path(calls[0]["checkout"]).exists())
        self.assertIsNotNone(routing.require_early_routing_gate(self.task))
        with patch.object(routing, "main_root", return_value=self.integration):
            routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")
        self.assertTrue(routing._launch_confirmed(execution))

    def test_integration_advance_during_run_is_not_a_violation(self) -> None:
        self.prepare(provider="claude")

        def advance():
            (self.integration / "other.txt").write_text("sibling\n")
            base.git(self.integration, "add", "other.txt")
            base.git(self.integration, "commit", "-qm", "sibling advance")

        launch, _ = self.launcher("pathlib.Path('README.md').write_text('w\\n')\n", during=advance)
        self.dispatch(launch)
        self.assertEqual(self.saved()["execution"]["outcome"], "completed")
        with patch.object(routing, "main_root", return_value=self.integration):
            routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")

    def test_lifecycle_state_edit_is_rejected_and_nothing_is_applied(self) -> None:
        self.prepare(provider="claude")
        launch, _ = self.launcher(
            "pathlib.Path('README.md').write_text('w\\n')\n"
            "pathlib.Path('openspec/changes/routing-change/.managed-task.json').write_text('{}')\n")
        with self.assertRaisesRegex(routing.RoutingError, "rejected"):
            self.dispatch(launch)
        self.assertEqual((self.task / "README.md").read_text(), "base\n")
        record = self.saved()
        self.assertEqual(record["execution"]["outcome"], "rejected")
        self.assertIn("lifecycle", record["execution"]["error"])
        self.assertEqual(record["execution_plan"]["delegation"]["outcome"], "rejected")
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaises(routing.RoutingError):
                routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")

    def test_task_content_change_during_run_retains_the_patch(self) -> None:
        self.prepare(provider="claude")
        launch, _ = self.launcher("pathlib.Path('README.md').write_text('w\\n')\n",
                                  during=lambda: (self.task / "supervisor.txt").write_text("late\n"))
        with self.assertRaisesRegex(routing.RoutingError, "rejected"):
            self.dispatch(launch)
        record = self.saved()
        self.assertEqual(record["execution"]["outcome"], "rejected")
        self.assertIn("supervisor.txt", record["execution"]["error"])
        self.assertTrue(Path(record["execution"]["patch"]["path"]).is_file())
        self.assertEqual((self.task / "README.md").read_text(), "base\n")

    def test_failed_writer_records_failure(self) -> None:
        self.prepare(provider="claude")
        launch, _ = self.launcher("pass\n", returncode=3)
        with self.assertRaisesRegex(routing.RoutingError, "failed"):
            self.dispatch(launch)
        record = self.saved()
        self.assertEqual(record["execution"]["outcome"], "failed")
        self.assertTrue(record["execution"]["launched"])
        self.assertEqual(record["execution_plan"]["delegation"]["outcome"], "failed")

    def test_pre_launch_refusal_records_not_launched(self) -> None:
        self.prepare(provider="claude")

        def refuse(*args, **kwargs):
            raise sandboxed_writer.SandboxedWriterError("the sandboxed writer is proven only on macOS; refusing to launch on platform 'linux'")

        with self.assertRaisesRegex(routing.RoutingError, "only on macOS"):
            self.dispatch(refuse)
        record = self.saved()
        self.assertIsNone(record["execution"])
        self.assertEqual(record["execution_plan"]["delegation"]["outcome"], "not-launched")
        self.assertEqual(record["execution_plan"]["delegation"]["state"], "closed")

    def test_retained_plan_and_existing_execution_are_refused(self) -> None:
        self.prepare(provider="claude", profile="complex")
        launch, calls = self.launcher("pass\n")
        with self.assertRaisesRegex(routing.RoutingError, "supervisor-retained"):
            self.dispatch(launch)
        self.assertEqual(calls, [])

    def test_codex_route_is_refused(self) -> None:
        self.prepare(provider="codex")
        launch, calls = self.launcher("pass\n")
        with self.assertRaisesRegex(routing.RoutingError, "not a Claude route"):
            self.dispatch(launch)
        self.assertEqual(calls, [])

    def test_empty_prompt_is_refused(self) -> None:
        route = self.prepare(provider="claude")
        with self.assertRaisesRegex(routing.RoutingError, "empty"):
            routing.claude_sandboxed_argv(route, "  ")


if __name__ == "__main__":
    unittest.main()
