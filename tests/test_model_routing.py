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

    def record_path(self) -> Path:
        return self.task / ".claude" / "model-routing" / "routing-change.json"

    def durable_record_path(self) -> Path:
        return self.integration / ".claude" / "model-routing" / "routing-change.json"

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
        saved = self.record_path()
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

    def test_claude_agent_hand_off_has_no_fictional_effort_or_maxturns(self) -> None:
        # The current Agent tool schema accepts only description/isolation/
        # model/prompt/run_in_background/subagent_type; effort and maxTurns
        # are not real parameters and must not be emitted as if selectable.
        route = self.prepare(provider="claude", profile="routine")
        agent = routing.claude_agent(route)
        self.assertNotIn("effort", agent)
        self.assertNotIn("maxTurns", agent)

    def test_prepare_records_supervisor_provenance_as_policy_selected(self) -> None:
        route = self.prepare(provider="codex")
        self.assertEqual(
            route.supervisor,
            {"role": "supervisor", "provider": "codex", "model": {"value": "strong-codex", "source": "selected"}},
        )

    def test_read_route_tolerates_missing_supervisor_field(self) -> None:
        # Pre-provenance route records (written before this field existed)
        # must not break resume/escalation for other in-flight tasks.
        route = self.prepare()
        saved_path = self.record_path()
        payload = json.loads(saved_path.read_text(encoding="utf-8"))
        del payload["supervisor"]
        saved_path.write_text(json.dumps(payload), encoding="utf-8")
        reread, _ = routing._read_route(self.task)
        self.assertEqual(reread.supervisor, {})

    def test_run_codex_extracts_thread_id_from_json_event_stream(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")

        def fake_run_observed_delegation(*, stdout_line_hook, **_kwargs):
            stdout_line_hook('{"type":"thread.started","thread_id":"019ff7be-6e9d-7110-98bb-2591886d55d1"}')
            stdout_line_hook('{"type":"turn.started"}')
            return SimpleNamespace(launched=True, returncode=0, violation=False)

        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=fake_run_observed_delegation),
        ):
            execution = routing.run_codex(route, "implement")

        self.assertEqual(
            execution["participant"],
            {
                "role": "executor",
                "provider": "codex",
                "profile": "standard",
                "model": {"value": "cheap-codex", "source": "selected"},
                "reasoning_effort": {"value": None, "source": "unknown"},
                "execution_id": {"value": "019ff7be-6e9d-7110-98bb-2591886d55d1", "kind": "codex-thread"},
            },
        )

    def test_run_codex_without_thread_started_event_leaves_execution_id_unknown(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")

        def fake_run_observed_delegation(*, stdout_line_hook, **_kwargs):
            stdout_line_hook("plain text output, not a json event")
            return SimpleNamespace(launched=True, returncode=0, violation=False)

        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=fake_run_observed_delegation),
        ):
            execution = routing.run_codex(route, "implement")

        self.assertEqual(execution["participant"]["execution_id"], {"value": None, "kind": None})

    def test_run_codex_records_complete_structured_usage_and_platform_timing(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")

        def fake_run_observed_delegation(*, stdout_line_hook, **_kwargs):
            stdout_line_hook('{"type":"turn.started"}')
            stdout_line_hook(
                '{"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":80,'
                '"output_tokens":30,"total_tokens":150}}'
            )
            return SimpleNamespace(launched=True, returncode=0, violation=False)

        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=fake_run_observed_delegation),
        ):
            execution = routing.run_codex(route, "implement")

        timing = execution["efficiency"]["timing"]
        self.assertEqual(timing["source"], "platform")
        self.assertEqual(timing["status"], "measured")
        self.assertGreaterEqual(timing["elapsed_ms"], 0)
        usage = execution["efficiency"]["usage"]
        self.assertEqual(usage["input_tokens"], {"value": 120, "source": "runtime-confirmed", "status": "measured"})
        self.assertEqual(usage["cache_read_tokens"]["value"], 80)
        self.assertEqual(usage["output_tokens"]["value"], 30)
        self.assertEqual(usage["total_tokens"]["value"], 150)
        self.assertEqual(usage["request_count"]["value"], 1)
        self.assertEqual(usage["fresh_input_tokens"]["status"], "unknown")

    def test_run_codex_keeps_partial_usage_unknown_without_deriving_values(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")

        def fake_run_observed_delegation(*, stdout_line_hook, **_kwargs):
            stdout_line_hook('{"type":"turn.completed","usage":{"output_tokens":9}}')
            return SimpleNamespace(launched=True, returncode=0, violation=False)

        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=fake_run_observed_delegation),
        ):
            execution = routing.run_codex(route, "implement")

        usage = execution["efficiency"]["usage"]
        self.assertEqual(usage["output_tokens"]["value"], 9)
        self.assertEqual(usage["input_tokens"], {"value": None, "source": "unknown", "status": "unknown"})
        self.assertEqual(usage["total_tokens"]["status"], "unknown")

    def test_run_codex_marks_usage_unknown_when_runtime_emits_no_supported_usage(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(
                routing,
                "run_observed_delegation",
                return_value=SimpleNamespace(launched=True, returncode=0, violation=False),
            ),
        ):
            execution = routing.run_codex(route, "implement")
        self.assertTrue(all(value["status"] == "unknown" for value in execution["efficiency"]["usage"].values()))

    def test_abnormal_codex_return_is_truthfully_recorded_and_dispatch_fails(self) -> None:
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        observed = SimpleNamespace(launched=True, returncode=None, violation=False, writer_state="released")
        abnormal = guard.GuardedChildError("timed out after cleanup", observed)
        with (
            patch.object(routing, "main_root", return_value=self.integration),
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=abnormal),
        ):
            with self.assertRaisesRegex(routing.RoutingError, "did not complete cleanly"):
                routing.dispatch_codex(
                    self.task,
                    profile="standard",
                    rationale="bounded current-spec preflight",
                    evidence=["openspec/changes/routing-change"],
                    prompt="implement",
                )

        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["execution"]["outcome"], "abnormal")
        self.assertEqual(saved["execution"]["writer_state"], "released")
        self.assertIn("timed out after cleanup", saved["execution"]["error"])
        self.assertEqual(saved["execution"]["efficiency"]["timing"]["source"], "platform")

    def test_codex_launcher_boundary_failure_is_recorded_without_a_traceback(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=PermissionError("writer receipt is unavailable")),
        ):
            execution = routing.run_codex(route, "implement")
        self.assertFalse(execution["launched"])
        self.assertEqual(execution["outcome"], "abnormal")
        self.assertEqual(execution["writer_state"], "unavailable")
        self.assertIn("writer receipt is unavailable", execution["error"])
        self.assertEqual(execution["efficiency"]["timing"]["status"], "measured")

    def test_efficiency_baseline_keeps_historical_records_missing_and_labels_small_samples_insufficient(self) -> None:
        historical = {"change": "historical", "execution": {"launched": True, "outcome": "completed"}}
        measured = {
            "change": "measured",
            "escalations": [{"reason": "bounded finding"}],
            "execution": {
                "launched": True,
                "outcome": "completed",
                "efficiency": {
                    "timing": {"elapsed_ms": 42, "source": "platform", "status": "measured"},
                    "usage": {"output_tokens": {"value": 7, "source": "runtime-confirmed", "status": "measured"}},
                },
            },
        }
        with patch.object(routing, "_local_routing_records", return_value=[historical, measured]):
            receipt = self.task / "openspec" / "changes" / "measured" / "verification.md"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n", encoding="utf-8")
            report = routing.efficiency_baseline(self.task)
        self.assertEqual(report["evidence"]["status"], "insufficient")
        self.assertEqual(report["observations"]["routing_records"], 2)
        self.assertEqual(report["observations"]["launched_executions"], 2)
        self.assertEqual(report["observations"]["escalated_routes"], 1)
        self.assertEqual(report["observations"]["verification"], {"missing": 1, "passed": 1})
        self.assertEqual(report["metrics"]["elapsed_ms"], {"measured": 1, "unknown": 0, "missing": 1, "median": 42})
        self.assertEqual(report["metrics"]["output_tokens"], {"measured": 1, "unknown": 0, "missing": 1, "median": 7})
        self.assertEqual(report["metrics"]["input_tokens"], {"measured": 0, "unknown": 0, "missing": 2})

    def test_escalation_preserves_task_context_and_uses_strong_policy(self) -> None:
        self.prepare()
        escalated = routing.escalate(self.task, "unexpected cross-cutting contract")
        self.assertEqual(escalated.profile, "complex")
        self.assertEqual(escalated.executor_model, "strong-codex")
        self.assertEqual(escalated.escalations[0]["from"], "standard")
        with self.assertRaisesRegex(routing.RoutingError, "already complex"):
            routing.escalate(self.task, "again")

    def test_escalation_preserves_supervisor_provenance_unchanged(self) -> None:
        # Escalation changes the executor's profile/model, not who the
        # strong parent supervisor is or how its identity was established.
        prepared = self.prepare()
        escalated = routing.escalate(self.task, "unexpected cross-cutting contract")
        self.assertEqual(escalated.supervisor, prepared.supervisor)

    def test_codex_route_refuses_unproven_native_boundary(self) -> None:
        route = self.prepare()
        decision = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:test", "no sandbox")
        with patch.object(routing, "determine_codex_tier", return_value=decision):
            with self.assertRaisesRegex(routing.RoutingError, "retain execution on the parent"):
                routing.codex_argv(route, "implement")
        # The unavailable route must not be recorded as an executed
        # participant; the record on disk stays exactly as prepared.
        reread, _ = routing._read_route(self.task)
        self.assertIsNone(reread.execution)

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
        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
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
        # "pending_supervisor_invocation" means exactly that: the hand-off was
        # emitted but not yet actually invoked, so there is no participant
        # to report until record_claude_execution confirms a real Agent call.
        reread, _ = routing._read_route(self.task)
        self.assertIsNone(reread.execution)

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
        self.assertEqual(
            execution["participant"],
            {
                "role": "executor",
                "provider": "claude",
                "profile": "standard",
                "model": {"value": "sonnet", "source": "selected"},
                "reasoning_effort": {"value": None, "source": "unknown"},
                "execution_id": {"value": "agent-abc123", "kind": "claude-agent-id"},
            },
        )
        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertTrue(saved["execution"]["launched"])
        self.assertEqual(saved["execution"]["postcheck"]["containment"], "clean")
        self.assertEqual(json.loads(self.durable_record_path().read_text(encoding="utf-8"))["execution"], saved["execution"])

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
        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
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

    def test_prepare_records_linked_worktree_topology(self) -> None:
        route = self.prepare()
        self.assertEqual(route.topology, routing.LINKED_WORKTREE)

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


class StandaloneStandardCloneRoutingTests(unittest.TestCase):
    """Standard-profile projects have no linked worktree: the task checkout

    and the integration copy are the same directory. Routing preflight must
    still be able to record a parent-only route there (spec scenario
    "Supervisor records standard-clone preflight"), but must refuse to ever
    launch a write-capable child from it (spec scenario "Child writer is
    requested from a standard clone").
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.clone = Path(self.tmp.name) / "clone"
        self.clone.mkdir()
        git(self.clone, "init", "-q", "-b", "main")
        git(self.clone, "config", "user.email", "routing@example.test")
        git(self.clone, "config", "user.name", "Routing Test")
        (self.clone / "README.md").write_text("base\n", encoding="utf-8")
        git(self.clone, "add", "README.md")
        git(self.clone, "commit", "-qm", "base")
        git(self.clone, "switch", "-c", "agent/routing")
        change = self.clone / "openspec" / "changes" / "routing-change"
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(json.dumps({"source_issue": "owner/backlog#7", "change": "routing-change"}), encoding="utf-8")
        (self.clone / ".dev-platform.toml").write_text(
            "workflow_profile = \"standard\"\n"
            "[model_routing.codex]\nstandard_model = \"cheap-codex\"\ncomplex_model = \"strong-codex\"\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def prepare(self, provider: str = "codex", profile: str = "standard"):
        with patch.object(routing, "main_root", return_value=self.clone):
            return routing.prepare(self.clone, provider=provider, profile=profile, rationale="bounded current-spec preflight", evidence=["openspec/changes/routing-change"])

    def test_prepare_records_the_standalone_clone_as_a_truthful_parent_only_route(self) -> None:
        route = self.prepare()
        self.assertEqual(route.topology, routing.STANDALONE_CLONE)
        self.assertEqual(route.task_worktree, str(self.clone.resolve()))
        self.assertEqual(route.integration_root, str(self.clone.resolve()))

    def test_dispatch_codex_refuses_child_writer_from_standalone_clone(self) -> None:
        with patch.object(routing, "main_root", return_value=self.clone):
            with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
                routing.dispatch_codex(
                    self.clone, profile="standard", rationale="bounded current-spec preflight",
                    evidence=["openspec/changes/routing-change"], prompt="implement",
                )
        # The route was still recorded (parent-only), just never delegated.
        reread, _ = routing._read_route(self.clone)
        self.assertEqual(reread.topology, routing.STANDALONE_CLONE)
        self.assertIsNone(reread.execution)

    def test_dispatch_codex_complex_profile_is_unaffected_by_standalone_topology(self) -> None:
        with patch.object(routing, "main_root", return_value=self.clone):
            result = routing.dispatch_codex(
                self.clone, profile="complex", rationale="material cross-cutting contract boundary",
                evidence=["openspec/changes/routing-change"], prompt="unused",
            )
        self.assertFalse(result["delegated"])
        self.assertIn("remains on the strong", result["reason"])

    def test_claude_handoff_refuses_child_writer_from_standalone_clone(self) -> None:
        with patch.object(routing, "main_root", return_value=self.clone):
            with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
                routing.prepare_claude_handoff(
                    self.clone, profile="standard", rationale="bounded current-spec preflight",
                    evidence=["openspec/changes/routing-change"],
                )

    def test_codex_argv_refuses_a_standalone_clone_route_read_back_from_disk(self) -> None:
        # Covers the raw `codex-argv`/`run-codex` CLI paths, which read an
        # already-prepared route from disk instead of going through
        # dispatch_codex's own early refusal.
        self.prepare()
        reread, _ = routing._read_route(self.clone)
        with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
            routing.codex_argv(reread, "implement")

    def test_claude_agent_refuses_a_standalone_clone_route_read_back_from_disk(self) -> None:
        self.prepare(provider="claude")
        reread, _ = routing._read_route(self.clone)
        with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
            routing.claude_agent(reread)

    def test_record_claude_execution_refuses_a_standalone_clone_route_prepared_directly(self) -> None:
        # A caller could prepare a route through the raw `prepare` CLI/API
        # (not `prepare_claude_handoff`) and then try to mark it executed
        # directly -- this must be refused too, not only the hand-off emit.
        self.prepare(provider="claude")
        with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
            routing.record_claude_execution(self.clone, agent_id="agent-abc123")
        reread, _ = routing._read_route(self.clone)
        self.assertIsNone(reread.execution)

    def test_read_route_defaults_missing_topology_to_linked_worktree(self) -> None:
        # A routing record written before this field existed must be read
        # back as the strict topology it was always recorded under, not
        # silently reinterpreted as a standalone parent-only route.
        route = self.prepare()
        saved_path = self.clone / ".claude" / "model-routing" / "routing-change.json"
        payload = json.loads(saved_path.read_text(encoding="utf-8"))
        del payload["topology"]
        saved_path.write_text(json.dumps(payload), encoding="utf-8")
        reread, _ = routing._read_route(self.clone)
        self.assertEqual(reread.topology, routing.LINKED_WORKTREE)


if __name__ == "__main__":
    unittest.main()
