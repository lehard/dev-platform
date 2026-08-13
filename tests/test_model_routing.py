from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def write_routing_receipt(self, tier: str, *, strong_trigger: str | None = None) -> None:
        provenance = self.task / "openspec" / "changes" / "routing-change" / ".managed-task.json"
        provenance.write_text(
            json.dumps(
                {
                    "source_issue": "owner/backlog#7",
                    "change": "routing-change",
                    "routing_receipt": {
                        "recommended_start_tier": tier,
                        "rubric_version": "v1",
                        "task_family": "general",
                        "routing_confidence": "medium",
                        "assurance": "standard",
                        "effort_hint": "medium",
                        "strong_trigger": strong_trigger,
                    },
                }
            ),
            encoding="utf-8",
        )

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

    def test_prepare_without_profile_confirms_authored_r2_tier(self) -> None:
        self.write_routing_receipt("R2")
        with patch.object(routing, "main_root", return_value=self.integration):
            route = routing.prepare(self.task, provider="codex", profile=None, rationale="freshness check: no new trigger found", evidence=[])
        self.assertEqual(route.profile, "standard")
        self.assertEqual(route.start_tier, "R2")
        self.assertEqual(route.freshness, "confirmed")

    def test_prepare_without_profile_confirms_authored_r3_tier(self) -> None:
        self.write_routing_receipt("R3", strong_trigger="unresolved_architecture")
        with patch.object(routing, "main_root", return_value=self.integration):
            route = routing.prepare(self.task, provider="codex", profile=None, rationale="freshness check: trigger still holds", evidence=[])
        self.assertEqual(route.profile, "complex")
        self.assertEqual(route.start_tier, "R3")

    def test_prepare_without_profile_and_without_receipt_requires_explicit_profile(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "pass --profile explicitly"):
                routing.prepare(self.task, provider="codex", profile=None, rationale="no receipt available", evidence=[])

    def test_explicit_profile_override_still_records_authored_tier(self) -> None:
        self.write_routing_receipt("R2")
        with patch.object(routing, "main_root", return_value=self.integration):
            route = routing.prepare(self.task, provider="codex", profile="complex", rationale="override to strong on new evidence", evidence=[])
        self.assertEqual(route.profile, "complex")
        self.assertEqual(route.start_tier, "R2")

    def test_escalate_marks_route_as_freshness_escalated(self) -> None:
        self.write_routing_receipt("R2")
        with patch.object(routing, "main_root", return_value=self.integration):
            routing.prepare(self.task, provider="codex", profile=None, rationale="freshness check: no new trigger found", evidence=[])
            escalated = routing.escalate(self.task, "freshness check found a new unresolved architecture trigger")
        self.assertEqual(escalated.profile, "complex")
        self.assertEqual(escalated.freshness, "escalated")
        self.assertEqual(escalated.start_tier, "R2")

    def test_claude_agent_hand_off_has_no_isolation_and_runs_in_place(self) -> None:
        route = self.prepare(provider="claude", profile="routine")
        agent = routing.claude_agent(route)
        self.assertNotIn("isolation", agent)
        self.assertEqual(agent["model"], "haiku")
        self.assertIn("current working directory", agent["prompt"])
        self.assertIn(str(self.task.resolve()), agent["prompt"])

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

    def test_dogfood_standard_dispatch_records_terra_and_launches_executor(self) -> None:
        (self.task / ".dev-platform.toml").write_text(
            "[model_routing.codex]\nstandard_model = \"gpt-5.6-terra\"\ncomplex_model = \"gpt-5.6-sol\"\n",
            encoding="utf-8",
        )
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(
                routing,
                "run_observed_delegation",
                return_value=SimpleNamespace(launched=True, returncode=0, violation=False),
            ) as launched,
        ):
            result = routing.dispatch_codex(
                self.task,
                profile="standard",
                rationale="Sol supervisor completed bounded current-spec preflight",
                evidence=["openspec/changes/routing-change"],
                prompt="implement the materialized managed task",
            )

        self.assertTrue(result["delegated"])
        self.assertEqual(result["route"]["executor_model"], "gpt-5.6-terra")
        saved = json.loads((self.task / ".claude" / "model-routing" / "routing-change.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["profile"], "standard")
        self.assertEqual(saved["executor_model"], "gpt-5.6-terra")
        self.assertTrue(saved["execution"]["launched"])
        self.assertEqual(launched.call_count, 1)
        self.assertIn("gpt-5.6-terra", launched.call_args.kwargs["argv"])

    def test_dogfood_complex_dispatch_remains_on_sol(self) -> None:
        (self.task / ".dev-platform.toml").write_text(
            "[model_routing.codex]\nstandard_model = \"gpt-5.6-terra\"\ncomplex_model = \"gpt-5.6-sol\"\n",
            encoding="utf-8",
        )
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(
            routing, "run_observed_delegation"
        ) as launched:
            result = routing.dispatch_codex(
                self.task,
                profile="complex",
                rationale="Sol supervisor found a material cross-cutting contract boundary",
                evidence=["openspec/specs/model-routing/spec.md"],
                prompt="unused",
            )

        self.assertFalse(result["delegated"])
        self.assertEqual(result["route"]["executor_model"], "gpt-5.6-sol")
        self.assertIn("remains on the strong", result["reason"])
        launched.assert_not_called()

    def test_claude_handoff_emits_in_place_spec_for_standard(self) -> None:
        detection_only = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox")
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_claude_tier", return_value=detection_only),
        ):
            result = routing.prepare_claude_handoff(
                self.task,
                profile="standard",
                rationale="Sol supervisor completed bounded current-spec preflight",
                evidence=["openspec/changes/routing-change"],
            )
        self.assertEqual(result["delegated"], "pending_supervisor_invocation")
        self.assertEqual(result["tier"], "detection-only")
        self.assertNotIn("isolation", result["handoff"])
        self.assertEqual(result["handoff"]["model"], "sonnet")

    def test_claude_handoff_refuses_to_start_over_dirty_integration(self) -> None:
        (self.integration / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        detection_only = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox")
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_claude_tier", return_value=detection_only),
        ):
            with self.assertRaisesRegex(routing.RoutingError, "already has uncommitted state"):
                routing.prepare_claude_handoff(
                    self.task,
                    profile="standard",
                    rationale="Sol supervisor completed bounded current-spec preflight",
                    evidence=["openspec/changes/routing-change"],
                )

    def test_claude_handoff_complex_remains_on_sol(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration):
            result = routing.prepare_claude_handoff(
                self.task,
                profile="complex",
                rationale="Sol supervisor found a material cross-cutting contract boundary",
                evidence=["openspec/specs/model-routing/spec.md"],
            )
        self.assertFalse(result["delegated"])
        self.assertNotIn("handoff", result)
        self.assertIn("remains on the strong", result["reason"])

    def test_record_claude_execution_persists_evidence_after_real_invocation(self) -> None:
        detection_only = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox")
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_claude_tier", return_value=detection_only),
        ):
            routing.prepare_claude_handoff(
                self.task,
                profile="standard",
                rationale="Sol supervisor completed bounded current-spec preflight",
                evidence=["openspec/changes/routing-change"],
            )
            # Simulate the supervisor having actually invoked the emitted hand-off
            # and made a real change inside the assigned task worktree (not integration).
            (self.task / "implemented.txt").write_text("real subagent work\n", encoding="utf-8")
            execution = routing.record_claude_execution(self.task, agent_id="agent-abc123", summary="added implemented.txt")
        self.assertTrue(execution["launched"])
        self.assertEqual(execution["agent_id"], "agent-abc123")
        self.assertEqual(execution["postcheck"]["containment"], "clean")
        saved = json.loads((self.task / ".claude" / "model-routing" / "routing-change.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["execution"]["launched"])
        self.assertEqual(saved["execution"]["postcheck"]["containment"], "clean")

    def test_record_claude_execution_fails_closed_on_integration_mutation(self) -> None:
        detection_only = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox")
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_claude_tier", return_value=detection_only),
        ):
            routing.prepare_claude_handoff(
                self.task,
                profile="standard",
                rationale="Sol supervisor completed bounded current-spec preflight",
                evidence=["openspec/changes/routing-change"],
            )
            (self.integration / "escape.txt").write_text("unexpected\n", encoding="utf-8")
            with patch.object(routing, "record_containment_friction") as recorded:
                with self.assertRaisesRegex(routing.RoutingError, "containment violation"):
                    routing.record_claude_execution(self.task, agent_id="agent-abc123")
            recorded.assert_called_once()
        saved = json.loads((self.task / ".claude" / "model-routing" / "routing-change.json").read_text(encoding="utf-8"))
        self.assertIsNone(saved["execution"])

    def test_record_claude_execution_rejects_complex_profile(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration):
            routing.prepare_claude_handoff(
                self.task,
                profile="complex",
                rationale="Sol supervisor found a material cross-cutting contract boundary",
                evidence=["openspec/specs/model-routing/spec.md"],
            )
            with self.assertRaisesRegex(routing.RoutingError, "not delegated"):
                routing.record_claude_execution(self.task, agent_id="agent-abc123")

    def test_postcheck_reports_native_worktree_escape(self) -> None:
        route = self.prepare(provider="claude", profile="standard")
        (self.integration / "escape.txt").write_text("unexpected\n", encoding="utf-8")
        with patch.object(routing, "record_containment_friction") as recorded:
            with self.assertRaisesRegex(routing.RoutingError, "containment violation"):
                routing.postcheck(route)
        recorded.assert_called_once()

    def test_cli_reports_missing_active_managed_change_without_traceback(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "model_routing.py"), "context"],
            cwd=self.task,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Model routing blocked:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
