from __future__ import annotations

import subprocess
import sys
import os
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cloud_maintenance_preflight as preflight  # noqa: E402


def completed(arguments: tuple[str, ...], stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(("gh", *arguments), returncode, stdout=stdout, stderr="")


class CloudMaintenancePreflightTests(unittest.TestCase):
    def _runner(self, responses: list[tuple[str, int]]) -> tuple[list[tuple[str, ...]], object]:
        calls: list[tuple[str, ...]] = []

        def run(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
            calls.append(tuple(arguments))
            stdout, returncode = responses.pop(0)
            return completed(tuple(arguments), stdout, returncode)

        return calls, run

    @staticmethod
    def workflows(*, state: str = "active") -> str:
        return "[" + ",".join(
            f'{{"path":".github/workflows/{name}","state":"{state}","name":"{name}"}}'
            for name in preflight.CLOUD_MAINTENANCE_WORKFLOWS
        ) + "]"

    def test_missing_secret_reports_name_and_skips_probe(self) -> None:
        calls, runner = self._runner([(self.workflows(), 0), ("[]", 0)])
        result = preflight.preflight(repo="example/repo", ref="main", runner=runner)
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing required Actions secret OPENAI_API_KEY", "\n".join(result.messages))
        self.assertIn("No provider probe was dispatched.", result.messages)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("workflow", calls[-1])

    def test_disabled_workflows_skip_secret_lookup_and_succeed(self) -> None:
        calls, runner = self._runner([(self.workflows(state="disabled_manually"), 0)])
        result = preflight.preflight(repo=None, ref="main", runner=runner)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Disabled cloud maintenance workflows:", "\n".join(result.messages))
        self.assertIn("No provider probe was dispatched", "\n".join(result.messages))
        self.assertEqual(len(calls), 1)

    def test_present_secret_dispatches_only_dedicated_probe(self) -> None:
        calls, runner = self._runner([(self.workflows(), 0), ('[{"name":"OPENAI_API_KEY"}]', 0), ("", 0)])
        result = preflight.preflight(repo="example/repo", ref="candidate", runner=runner)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("dispatched the secret-safe provider probe", "\n".join(result.messages))
        self.assertEqual(calls[-1], ("workflow", "run", preflight.PROBE_WORKFLOW, "--ref", "candidate", "--repo", "example/repo"))
        self.assertNotIn("process-issue-triage", " ".join(calls[-1]))

    def test_unavailable_metadata_does_not_expose_command_output(self) -> None:
        calls, runner = self._runner([("sensitive remote detail", 1)])
        with self.assertRaises(preflight.PreflightError) as caught:
            preflight.preflight(repo=None, ref="main", runner=runner)
        self.assertNotIn("sensitive remote detail", str(caught.exception))
        self.assertEqual(len(calls), 1)

    def test_probe_workflow_is_manual_bounded_and_secret_safe(self) -> None:
        text = (ROOT / ".github" / "workflows" / preflight.PROBE_WORKFLOW).read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)
        self.assertEqual(workflow[True], {"workflow_dispatch": None})
        self.assertEqual(workflow["jobs"]["provider-probe"]["timeout-minutes"], 2)
        self.assertIn("--output /dev/null", text)
        self.assertIn("--max-time 20", text)
        self.assertIn("OPENAI_PROVIDER_INVALID_CREDENTIAL", text)
        self.assertNotIn("set -x", text)
        self.assertNotIn('echo "${OPENAI_API_KEY', text)
        self.assertNotIn("--verbose", text)

    def test_probe_classifies_invalid_credential_without_secret_disclosure(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / preflight.PROBE_WORKFLOW).read_text(encoding="utf-8"))
        script = workflow["jobs"]["provider-probe"]["steps"][0]["run"]
        with tempfile.TemporaryDirectory() as directory:
            fake_curl = Path(directory) / "curl"
            fake_curl.write_text("#!/bin/sh\nprintf 401\n", encoding="utf-8")
            fake_curl.chmod(0o755)
            env = dict(os.environ, PATH=f"{directory}:{os.environ['PATH']}", OPENAI_API_KEY="secret-sentinel")
            result = subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("OPENAI_PROVIDER_INVALID_CREDENTIAL", result.stdout)
        self.assertNotIn("secret-sentinel", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
