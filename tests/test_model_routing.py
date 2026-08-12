from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


containment = load("delegation_containment", "delegation_containment.py")
guard = load("delegated_write_guard", "delegated_write_guard.py")
routing = load("model_routing", "model_routing.py")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


class ModelRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.integration = Path(self.tmp.name) / "integration"
        self.integration.mkdir()
        git(self.integration, "init", "-q", "-b", "main")
        git(self.integration, "config", "user.email", "routing@example.test")
        git(self.integration, "config", "user.name", "Routing Test")
        (self.integration / "README.md").write_text("base\n", encoding="utf-8")
        git(self.integration, "add", "README.md")
        git(self.integration, "commit", "-qm", "base")
        self.task = Path(self.tmp.name) / "task"
        git(self.integration, "worktree", "add", "-qb", "agent/routing", str(self.task), "main")
        change = self.task / "openspec" / "changes" / "routing-change"
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(json.dumps({"source_issue": "owner/backlog#7", "change": "routing-change"}), encoding="utf-8")
        (self.task / ".dev-platform.toml").write_text("[model_routing.codex]\nstandard_model = \"cheap-codex\"\ncomplex_model = \"strong-codex\"\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def prepare(self, provider: str = "codex", profile: str = "standard"):
        with patch.object(routing, "main_root", return_value=self.integration):
            return routing.prepare(self.task, provider=provider, profile=profile, rationale="bounded current-spec preflight", evidence=["openspec/changes/routing-change"])

    def test_prepare_persists_replaceable_policy_and_context(self) -> None:
        route = self.prepare()
        self.assertEqual(route.executor_model, "cheap-codex")
        self.assertEqual(route.task_worktree, str(self.task.resolve()))
        saved = self.task / ".claude" / "model-routing" / "routing-change.json"
        self.assertTrue(saved.is_file())
        context = routing.escalation_context(routing._read_route(self.task)[0])
        self.assertEqual(context["source_issue"], "owner/backlog#7")
        self.assertIn("Escalate", " ".join(context["required_parent_actions"]))
        self.assertEqual(routing.postcheck(route)["containment"], "clean")

    def test_claude_route_uses_native_worktree_agent(self) -> None:
        route = self.prepare(provider="claude", profile="routine")
        agent = routing.claude_agent(route)
        self.assertEqual(agent["isolation"], "worktree")
        self.assertEqual(agent["model"], "haiku")

    def test_escalation_preserves_task_context_and_uses_strong_policy(self) -> None:
        self.prepare()
        escalated = routing.escalate(self.task, "unexpected cross-cutting contract")
        self.assertEqual(escalated.profile, "complex")
        self.assertEqual(escalated.executor_model, "strong-codex")
        self.assertEqual(escalated.escalations[0]["from"], "standard")
        with self.assertRaisesRegex(routing.RoutingError, "already complex"):
            routing.escalate(self.task, "again")

    def test_codex_route_refuses_unproven_native_boundary(self) -> None:
        route = self.prepare()
        decision = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:test", "no sandbox")
        with patch.object(routing, "determine_codex_tier", return_value=decision):
            with self.assertRaisesRegex(routing.RoutingError, "retain execution on the parent"):
                routing.codex_argv(route, "implement")

    def test_codex_route_uses_native_sandbox_with_selected_model(self) -> None:
        route = self.prepare()
        decision = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        with patch.object(routing, "determine_codex_tier", return_value=decision):
            argv, mechanism = routing.codex_argv(route, "implement", "codex")
        self.assertEqual(mechanism, "codex-workspace-write-sandbox")
        self.assertIn("workspace-write", argv)
        self.assertIn("cheap-codex", argv)
        self.assertEqual(argv[-1], "implement")

    def test_postcheck_reports_native_worktree_escape(self) -> None:
        route = self.prepare(provider="claude", profile="standard")
        (self.integration / "escape.txt").write_text("unexpected\n", encoding="utf-8")
        with patch.object(routing, "record_containment_friction") as recorded:
            with self.assertRaisesRegex(routing.RoutingError, "containment violation"):
                routing.postcheck(route)
        recorded.assert_called_once()


if __name__ == "__main__":
    unittest.main()
