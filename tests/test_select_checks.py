from __future__ import annotations

import importlib.util
import sys
import unittest
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
            "settings": {"fallback_commands": ["git diff --check"]},
            "checks": {
                "python": {"patterns": ["**/*.py"], "commands": ["python3 -m compileall -q ."]},
            },
        }
        checks = select_checks.select(config, ["a/x.py", "b/y.py"])
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["id"], "python")
        self.assertEqual(checks[0]["paths"], ["a/x.py", "b/y.py"])

    def test_unknown_path_uses_fallback(self) -> None:
        config = {"settings": {"fallback_commands": ["git diff --check"]}, "checks": {}}
        checks = select_checks.select(config, ["Dockerfile"])
        self.assertEqual(checks[0]["id"], "fallback")
        self.assertEqual(checks[0]["commands"], ["git diff --check"])

    def test_high_impact_file_escalates_to_full_commands(self) -> None:
        config = {
            "settings": {
                "fallback_commands": ["git diff --check"],
                "full_commands": ["pytest", "npm run build"],
                "full_trigger_patterns": ["**/pyproject.toml", "**/package-lock.json"],
            },
            "checks": {
                "python": {"patterns": ["**/*.py"], "commands": ["python3 -m compileall -q ."]},
            },
        }
        checks = select_checks.select(config, ["apps/api/pyproject.toml", "apps/api/app/main.py"])
        self.assertEqual(checks, [{"id": "full-trigger", "paths": ["apps/api/pyproject.toml"], "commands": ["pytest", "npm run build"]}])

    def test_high_impact_file_without_full_commands_fails_closed(self) -> None:
        config = {
            "settings": {
                "fallback_commands": ["git diff --check"],
                "full_trigger_patterns": ["**/package.json"],
            },
            "checks": {},
        }
        with self.assertRaises(SystemExit):
            select_checks.select(config, ["apps/web/package.json"])

    def test_template_declares_common_dependency_and_ci_full_triggers(self) -> None:
        text = (ROOT / "template" / "dev-platform" / "checks.toml").read_text(encoding="utf-8")
        self.assertIn("full_trigger_patterns", text)
        for pattern in ("**/pyproject.toml", "**/package.json", "**/package-lock.json", ".github/workflows/**", "dev-platform/checks.toml"):
            self.assertIn(pattern, text)


if __name__ == "__main__":
    unittest.main()
