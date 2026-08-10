from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import run as subprocess_run

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_diagnostic  # noqa: E402


class BuildEnvelopeTests(unittest.TestCase):
    def test_safety_guard_blocker_is_classified_pointless(self) -> None:
        log = (
            "+ git status --porcelain\n"
            "Managed rollout: BLOCKED: downstream checkout is dirty before rollout\n"
        )
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=2, repository="lehard/cuby", version="v1.4.19"
        )
        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["project"], "lehard/cuby")
        self.assertEqual(envelope["target_release"], "v1.4.19")
        self.assertEqual(envelope["stage"], "prepare")
        self.assertEqual(envelope["category"], "safety_guard")
        self.assertEqual(envelope["exit_code"], 2)
        self.assertEqual(envelope["retry_same_inputs"], "pointless")
        self.assertIn("downstream checkout is dirty", envelope["reason"])
        self.assertIsNone(envelope["command"])

    def test_copier_conflict_blocker_includes_conflict_paths(self) -> None:
        log = (
            "Managed rollout: BLOCKED: Copier left unresolved .rej files: "
            "scripts/finish_task.py.rej, tests/test_git_lifecycle.py.rej; "
            "non-recoverable conflicts: scripts/finish_task.py\n"
        )
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=2, repository="lehard/cuby", version="v1.4.19"
        )
        self.assertEqual(envelope["stage"], "recovery")
        self.assertEqual(envelope["category"], "copier_conflict")
        self.assertEqual(
            envelope["evidence"]["conflict_paths"],
            ["scripts/finish_task.py.rej", "tests/test_git_lifecycle.py.rej"],
        )

    def test_selected_check_failure_uses_reserved_marker_only(self) -> None:
        log = (
            "DEV_PLATFORM_CHECK_COMMAND: npm run build\n"
            "+ Foo() { throw new Error('unrelated compiler noise') }\n"
        )
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=1, repository="lehard/cuby", version="v1.4.19"
        )
        self.assertEqual(envelope["stage"], "downstream_check")
        self.assertEqual(envelope["category"], "downstream_check")
        self.assertEqual(envelope["command"], "npm run build")
        self.assertEqual(envelope["exit_code"], 1)
        self.assertNotIn("unrelated compiler noise", envelope["reason"])

    def test_runtime_environment_mismatch_is_classified_pointless(self) -> None:
        log = "Managed rollout: BLOCKED: node: command not found\n"
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=2, repository="lehard/cuby", version="v1.4.19"
        )
        self.assertEqual(envelope["stage"], "prepare")
        self.assertEqual(envelope["category"], "runtime_environment")
        self.assertEqual(envelope["retry_same_inputs"], "pointless")

    def test_unclassifiable_failure_defaults_to_unknown(self) -> None:
        log = "some unrelated output\n"
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=3, repository="lehard/cuby", version="v1.4.19"
        )
        self.assertEqual(envelope["stage"], "unknown")
        self.assertEqual(envelope["category"], "unknown")
        self.assertEqual(envelope["retry_same_inputs"], "unknown")
        self.assertIsNone(envelope["command"])
        self.assertEqual(envelope["evidence"]["marker"], None)

    def test_envelope_excludes_raw_log_text_and_secrets(self) -> None:
        log = (
            "GH_TOKEN=super-secret-token\n"
            "Managed rollout: BLOCKED: downstream checkout is dirty before rollout\n"
        )
        envelope = rollout_diagnostic.build_envelope(
            log_text=log, exit_code=2, repository="lehard/cuby", version="v1.4.19"
        )
        serialized = json.dumps(envelope)
        self.assertNotIn("super-secret-token", serialized)
        self.assertNotIn("GH_TOKEN", serialized)

    def test_render_summary_is_compact_markdown(self) -> None:
        envelope = rollout_diagnostic.build_envelope(
            log_text="Managed rollout: BLOCKED: downstream checkout is dirty before rollout\n",
            exit_code=2,
            repository="lehard/cuby",
            version="v1.4.19",
        )
        summary = rollout_diagnostic.render_summary(envelope)
        self.assertIn("stage:", summary)
        self.assertIn("category:", summary)
        self.assertIn("retry_same_inputs:", summary)


class CliTests(unittest.TestCase):
    def test_cli_writes_json_and_appends_summary_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "log.txt"
            log_file.write_text(
                "Managed rollout: BLOCKED: downstream checkout is dirty before rollout\n",
                encoding="utf-8",
            )
            output = root / "rollout-diagnostic.json"
            summary = root / "summary.md"
            summary.write_text("", encoding="utf-8")
            result = subprocess_run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "rollout_diagnostic.py"),
                    "--log-file",
                    str(log_file),
                    "--exit-code",
                    "2",
                    "--repository",
                    "lehard/cuby",
                    "--version",
                    "v1.4.19",
                    "--output",
                    str(output),
                    "--summary-output",
                    str(summary),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["category"], "safety_guard")
            self.assertIn("stage:", summary.read_text(encoding="utf-8"))

    def test_cli_never_fails_even_with_unreadable_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess_run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "rollout_diagnostic.py"),
                    "--log-file",
                    str(root / "does-not-exist.txt"),
                    "--exit-code",
                    "2",
                    "--repository",
                    "lehard/cuby",
                    "--version",
                    "v1.4.19",
                    "--output",
                    str(root / "rollout-diagnostic.json"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)


class WorkflowIntegrationTests(unittest.TestCase):
    def test_prepare_generates_diagnostic_without_replacing_original_exit(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("platform/scripts/rollout_diagnostic.py", text)
        # Diagnostic generation happens before exit "$rc" and cannot mask it.
        prepare_block = text.split("Prepare exact-version Copier update", 1)[1]
        prepare_block = prepare_block.split("Upload rollout diagnostic artifact", 1)[0]
        diagnostic_call_index = prepare_block.index("rollout_diagnostic.py")
        exit_index = prepare_block.index('exit "$rc"')
        self.assertLess(diagnostic_call_index, exit_index)
        self.assertIn("rollout_diagnostic.py", prepare_block)
        diagnostic_call = prepare_block[diagnostic_call_index:exit_index]
        self.assertIn("|| true", diagnostic_call)

    def test_diagnostic_artifact_upload_is_best_effort_and_gated_on_failure(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        upload_block = text.split("Upload rollout diagnostic artifact", 1)[1]
        upload_block = upload_block.split("Push rollout branch", 1)[0]
        self.assertIn("continue-on-error: true", upload_block)
        self.assertIn("if: steps.pending.outputs.found != 'true' && failure()", upload_block)
        self.assertIn("if-no-files-found: ignore", upload_block)

    def test_only_one_diagnostic_artifact_step_exists(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("Upload rollout diagnostic artifact"), 1)


if __name__ == "__main__":
    unittest.main()
