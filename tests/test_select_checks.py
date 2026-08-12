from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("select_checks", SCRIPTS / "select_checks.py")
assert SPEC and SPEC.loader
select_checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(select_checks)


class SelectChecksTests(unittest.TestCase):
    def test_match_any_supports_recursive_glob(self) -> None:
        self.assertTrue(select_checks.match_any("backend/app/service.py", ["**/*.py"]))
        self.assertTrue(select_checks.match_any("docs/engineering/a.md", ["docs/**"]))
        self.assertFalse(select_checks.match_any("frontend/page.tsx", ["**/*.py"]))

    def test_select_deduplicates_rule_and_collects_paths(self) -> None:
        config = {
            "settings": {},
            "checks": {
                "python": {"patterns": ["**/*.py"], "commands": ["python3 -m compileall -q ."]},
            },
        }
        checks = select_checks.select(config, ["a/x.py", "b/y.py"])
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["id"], "python")
        self.assertEqual(checks[0]["paths"], ["a/x.py", "b/y.py"])

    def test_unknown_path_fails_closed_to_full_commands(self) -> None:
        config = {"settings": {"full_commands": ["pytest"]}, "checks": {}}
        checks = select_checks.select(config, ["Dockerfile"])
        self.assertEqual(checks[0]["id"], "full-fallback")
        self.assertEqual(checks[0]["commands"], ["pytest"])
        self.assertEqual(checks[0]["selection_reason"], "unknown-path")

    def test_high_impact_file_escalates_to_full_commands(self) -> None:
        config = {
            "settings": {
                "full_commands": ["pytest", "npm run build"],
                "full_trigger_patterns": ["**/pyproject.toml", "**/package-lock.json"],
            },
            "checks": {
                "python": {"patterns": ["**/*.py"], "commands": ["python3 -m compileall -q ."]},
            },
        }
        checks = select_checks.select(config, ["apps/api/pyproject.toml", "apps/api/app/main.py"])
        self.assertEqual(
            checks,
            [{"id": "full-trigger", "paths": ["apps/api/pyproject.toml"], "commands": ["pytest", "npm run build"], "selection_reason": "high-impact-path"}],
        )

    def test_high_impact_file_without_full_commands_fails_closed(self) -> None:
        config = {
            "settings": {
                "full_trigger_patterns": ["**/package.json"],
            },
            "checks": {},
        }
        with self.assertRaises(SystemExit):
            select_checks.select(config, ["apps/web/package.json"])

    def test_protected_full_is_independent_of_changed_paths(self) -> None:
        config = {"settings": {"full_commands": ["pytest"]}}
        self.assertEqual(
            select_checks.full_checks(config),
            [{"id": "full", "paths": [], "commands": ["pytest"], "selection_reason": "protected-full"}],
        )

    def test_applicable_empty_group_is_invalid_while_no_group_is_not_applicable(self) -> None:
        empty = select_checks.select(
            {"settings": {}, "checks": {"frontend": {"patterns": ["**/*.tsx"], "commands": []}}},
            ["apps/web/page.tsx"],
        )
        self.assertEqual(select_checks.selection_status(empty)["state"], "invalid-coverage")
        with self.assertRaises(SystemExit):
            select_checks.validate_platform_selection(empty, "platform")
        self.assertEqual(select_checks.selection_status([]), {"state": "not-applicable", "command_count": 0, "check_count": 0})
        self.assertEqual(select_checks.validate_platform_selection(empty, "project")["state"], "invalid-coverage")

    def test_required_test_evidence_cannot_be_satisfied_by_syntax_only(self) -> None:
        checks = select_checks.select(
            {
                "settings": {},
                "checks": {
                    "python": {
                        "patterns": ["**/*.py"],
                        "commands": ["python3 -m compileall -q ."],
                        "evidence_types": ["syntax"],
                        "required_evidence_types": ["test"],
                    }
                },
            },
            ["app/service.py"],
        )
        status = select_checks.selection_status(checks)
        self.assertEqual(status["state"], "invalid-coverage")
        self.assertEqual(status["missing_required_evidence"], {"python": ["test"]})

    def test_execution_evidence_records_exact_successful_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "evidence.json"
            outcome = select_checks.execute(Path(directory), [{"id": "test", "commands": ["printf ok"]}], evidence_path)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(outcome, 0)
        self.assertEqual(evidence["selection"]["state"], "ready")
        self.assertEqual(evidence["outcome"], "success")
        self.assertEqual(evidence["executed_commands"][0]["command"], "printf ok")

    def test_successful_command_emits_compact_machine_readable_timing(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(select_checks, "time") as clock:
            clock.monotonic.side_effect = [10.0, 11.2345]
            with mock.patch("sys.stdout") as stdout:
                outcome = select_checks.execute(Path(directory), [{"commands": ["printf noisy"]}])
        self.assertEqual(outcome, 0)
        lines = "".join(call.args[0] for call in stdout.write.call_args_list)
        evidence_line = next(line for line in lines.splitlines() if line.startswith("DEV_PLATFORM_CHECK_RESULT: "))
        evidence = json.loads(evidence_line.split(": ", 1)[1])
        self.assertEqual(evidence, {"command": "printf noisy", "duration_seconds": 1.235, "outcome": "success", "exit_code": 0})
        self.assertNotIn("\nnoisy\n", lines)

    def test_failed_command_emits_bounded_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch("sys.stdout") as stdout:
            outcome = select_checks.execute(Path(directory), [{"commands": ["printf failure-detail; exit 7"]}])
        self.assertEqual(outcome, 7)
        lines = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn('"outcome": "failure"', lines)
        self.assertIn("DEV_PLATFORM_CHECK_DIAGNOSTIC:\nfailure-detail", lines)

    def test_template_declares_common_dependency_and_ci_full_triggers(self) -> None:
        text = (ROOT / "template" / "dev-platform" / "checks.toml").read_text(encoding="utf-8")
        self.assertIn("full_trigger_patterns", text)
        self.assertNotIn("fallback_commands", text)
        for pattern in ("**/pyproject.toml", "**/package.json", "**/package-lock.json", ".github/workflows/**", "openspec/**", "scripts/select_checks.py", "dev-platform/checks.toml"):
            self.assertIn(pattern, text)
        self.assertIn("[checks.javascript]", text)
        self.assertIn("commands = []", text)

    def test_reusable_pr_gate_uses_protected_full_mode(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "project-ci.yml").read_text(encoding="utf-8")
        self.assertIn("--mode protected-full --execute", workflow)
        self.assertNotIn("--base \"origin/${{ github.base_ref }}\" --execute", workflow)


if __name__ == "__main__":
    unittest.main()
