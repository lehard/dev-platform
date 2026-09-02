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
        self.assertEqual(usage["model_request_count"]["status"], "unknown")
        self.assertEqual(execution["efficiency"]["runtime_counters"]["codex_turn_started"]["value"], 1)
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

    def test_codex_receipt_classifies_external_interrupt_and_carries_retained_work(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        interrupted = SimpleNamespace(
            launched=True, returncode=None, violation=False, writer_state="released",
            abnormal_kind=guard.ABNORMAL_EXTERNAL_INTERRUPT,
            retained_work=guard.RetainedWork("present", 3),
        )
        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(
                routing,
                "run_observed_delegation",
                side_effect=guard.GuardedChildError("interrupted after cleanup", interrupted),
            ),
        ):
            execution = routing.run_codex(route, "implement")
        self.assertEqual(execution["outcome"], "abnormal")
        self.assertEqual(execution["abnormal_kind"], "external-interrupt")
        self.assertEqual(execution["retained_work"], {"state": "present", "changed_path_count": 3})

    def test_codex_receipt_classifies_timeout_distinctly(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        timed_out = SimpleNamespace(
            launched=True, returncode=None, violation=False, writer_state="released",
            abnormal_kind=guard.ABNORMAL_TIMEOUT, retained_work=guard.RetainedWork("absent", 0),
        )
        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(
                routing,
                "run_observed_delegation",
                side_effect=guard.GuardedChildError("timed out after cleanup", timed_out),
            ),
        ):
            execution = routing.run_codex(route, "implement")
        self.assertEqual(execution["abnormal_kind"], "timeout")
        self.assertEqual(execution["retained_work"], {"state": "absent", "changed_path_count": 0})

    def test_codex_launcher_boundary_failure_receipt_marks_launch_unavailable(self) -> None:
        route = self.prepare()
        hard = guard.EnforcementDecision(guard.EnforcementTier.HARD, "codex-workspace-write-sandbox", "safe")
        with (
            patch.object(routing, "determine_codex_tier", return_value=hard),
            patch.object(routing, "run_observed_delegation", side_effect=PermissionError("writer receipt unavailable")),
        ):
            execution = routing.run_codex(route, "implement")
        self.assertEqual(execution["outcome"], "abnormal")
        self.assertEqual(execution["abnormal_kind"], "launch-unavailable")
        self.assertNotIn("retained_work", execution)

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
        self.assertEqual(report["observations"]["verified_eligible_executions"], 1)
        self.assertEqual(report["observations"]["missing_verification_executions"], 1)
        self.assertEqual(report["observations"]["escalated_routes"], 1)
        self.assertEqual(report["observations"]["verification"], {"missing": 1, "passed": 1})
        self.assertEqual(report["metrics"]["elapsed_ms"], {"measured": 1, "unknown": 0, "missing": 1, "median": 42})
        self.assertEqual(report["metrics"]["model_request_count"], {"measured": 0, "unknown": 0, "missing": 2})
        self.assertEqual(report["runtime_local_metrics"]["unknown"]["output_tokens"], {"measured": 1, "unknown": 0, "missing": 1, "median": 7})
        self.assertEqual(report["runtime_local_metrics"]["unknown"]["input_tokens"], {"measured": 0, "unknown": 0, "missing": 2})

    def test_efficiency_baseline_requires_verified_eligible_executions(self) -> None:
        records = [
            {
                "change": "eligible-sample",
                "execution": {
                    "launched": True,
                    "outcome": "completed",
                    "efficiency": {"timing": {"elapsed_ms": 40 + index, "source": "platform", "status": "measured"}},
                },
            }
            for index in range(routing.EFFICIENCY_MIN_BASELINE_EXECUTIONS)
        ]
        with patch.object(routing, "_local_routing_records", return_value=records):
            unverified = routing.efficiency_baseline(self.task)
            receipt = self.task / "openspec" / "changes" / "eligible-sample" / "verification.md"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n", encoding="utf-8")
            verified = routing.efficiency_baseline(self.task)

        self.assertEqual(unverified["evidence"]["status"], "insufficient")
        self.assertEqual(unverified["observations"]["launched_executions"], 15)
        self.assertEqual(unverified["observations"]["verified_eligible_executions"], 0)
        self.assertEqual(unverified["observations"]["missing_verification_executions"], 15)
        self.assertEqual(verified["evidence"]["status"], "sufficient")
        self.assertEqual(verified["observations"]["verified_eligible_executions"], 15)
        self.assertEqual(verified["qualified_comparable_fields"], ["elapsed_ms"])

    def test_efficiency_baseline_separates_legacy_and_runtime_local_counters(self) -> None:
        legacy = {
            "change": "legacy",
            "execution": {
                "launched": True,
                "efficiency": {"usage": {"request_count": {"value": 2, "source": "runtime-confirmed", "status": "measured"}}},
            },
        }
        current = {
            "change": "current",
            "execution": {
                "launched": True,
                "efficiency": {
                    "usage": {"model_request_count": {"value": None, "source": "unknown", "status": "unknown"}},
                    "runtime_counters": {"codex_turn_started": {"value": 3, "source": "runtime-confirmed", "status": "measured"}},
                },
            },
        }
        with patch.object(routing, "_local_routing_records", return_value=[legacy, current]):
            report = routing.efficiency_baseline(self.task)

        self.assertNotIn("request_count", report["metrics"])
        self.assertEqual(report["legacy_ambiguous_counters"]["request_count"]["measured"], 1)
        self.assertEqual(report["runtime_local_counters"]["codex_turn_started"], {"measured": 1, "unknown": 0, "missing": 1, "median": 3})

    def test_efficiency_baseline_uses_durable_integration_receipt(self) -> None:
        record = {
            "change": "durable-receipt",
            "integration_root": str(self.integration),
            "execution": {
                "launched": True,
                "efficiency": {"timing": {"elapsed_ms": 7, "source": "platform", "status": "measured"}},
            },
        }
        receipt = self.integration / "openspec" / "changes" / "archive" / "2026-08-24-durable-receipt" / "verification.md"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n", encoding="utf-8")
        with patch.object(routing, "_local_routing_records", return_value=[record]):
            report = routing.efficiency_baseline(self.task)

        self.assertEqual(report["observations"]["verification"], {"passed": 1})
        self.assertEqual(report["observations"]["verified_eligible_executions"], 1)

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


class RoutingCalibrationTests(unittest.TestCase):
    """Bounded read-only R2/R3 calibration over the existing routing records.

    Every fixture is a routing record plus, where the case needs it, an
    OpenSpec verification receipt and managed-task provenance under the task
    checkout -- the same evidence path ``efficiency_baseline`` already reads.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.task = Path(self.tmp.name) / "task"
        self.task.mkdir()
        git(self.task, "init", "-q", "-b", "main")
        git(self.task, "config", "user.email", "routing@example.test")
        git(self.task, "config", "user.name", "Routing Test")
        (self.task / "openspec" / "changes").mkdir(parents=True)
        (self.task / "README.md").write_text("base\n", encoding="utf-8")
        git(self.task, "add", "README.md")
        git(self.task, "commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seed(
        self,
        change: str,
        *,
        tier: str | None = "R2",
        profile: str = "standard",
        launched: bool = True,
        outcome: str | None = "completed",
        escalations: list[dict[str, str]] | None = None,
        freshness: str = "confirmed",
        verified: bool = True,
        provider: str = "codex",
        executor_model: str = "gpt-5.6-terra",
        task_family: str | None = "model-routing",
        rubric_version: str | None = "v1",
    ) -> dict[str, object]:
        record: dict[str, object] = {
            "change": change,
            "provider": provider,
            "executor_model": executor_model,
            "profile": profile,
            "freshness": freshness,
            "escalations": escalations or [],
        }
        if tier is not None:
            record["start_tier"] = tier
        if launched:
            record["execution"] = {"launched": True, "outcome": outcome}
        if verified:
            receipt = self.task / "openspec" / "changes" / change / "verification.md"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text("OpenSpec-Verify: PASS\n", encoding="utf-8")
        if task_family is not None or rubric_version is not None:
            provenance = self.task / "openspec" / "changes" / change / ".managed-task.json"
            provenance.parent.mkdir(parents=True, exist_ok=True)
            provenance.write_text(
                json.dumps(
                    {
                        "source_issue": f"owner/backlog#{abs(hash(change)) % 900 + 1}",
                        "change": change,
                        "routing_receipt": {"task_family": task_family, "rubric_version": rubric_version},
                    }
                ),
                encoding="utf-8",
            )
        return record

    def run_report(self, records: list[dict[str, object]]) -> dict[str, object]:
        with patch.object(routing, "_local_routing_records", return_value=records), patch.object(
            routing, "main_root", side_effect=RuntimeError("no integration root in test")
        ):
            return routing.routing_calibration(self.task)

    def test_small_real_sample_is_insufficient_but_still_reported(self) -> None:
        records = [self.seed(f"c{i}", outcome="completed") for i in range(4)]
        records.append(self.seed("abn", outcome="abnormal"))
        report = self.run_report(records)
        self.assertEqual(report["sample"]["adequacy"], "insufficient")
        self.assertEqual(report["sample"]["usable_observations"], 5)
        self.assertEqual(report["global"]["authored_r2_verified_success_without_escalation"], 4)
        self.assertEqual(report["global"]["outcomes_usable"], {"abnormal": 1, "completed": 4})
        self.assertEqual(report["advice"]["candidate_decision"], "insufficient evidence / no policy change")
        self.assertTrue(report["advice"]["requires_separate_managed_change"])

    def test_authored_r2_success_without_escalation_is_positive_evidence(self) -> None:
        report = self.run_report([self.seed("clean-r2", outcome="completed")])
        self.assertEqual(report["global"]["authored_r2_verified_success_without_escalation"], 1)
        self.assertEqual(report["global"]["frontier_exposure_usable"], 0)
        self.assertEqual(report["global"]["r2_to_r3_escalation"]["escalated_usable"], 0)

    def test_r2_escalation_then_success_keeps_both_paths_and_reason(self) -> None:
        record = self.seed(
            "escalated-r2",
            profile="complex",
            freshness="escalated",
            outcome="completed",
            escalations=[{"at": "t", "from": "standard", "reason": "bounded verification failure"}],
        )
        report = self.run_report([record])
        escalation = report["global"]["r2_to_r3_escalation"]
        self.assertEqual(escalation["escalated_usable"], 1)
        self.assertEqual(escalation["success_after_escalation"], 1)
        self.assertEqual(escalation["recorded_reasons"], {"bounded verification failure": 1})
        self.assertEqual(escalation["unknown_reason"], 0)
        # An escalated route is a real R2 attempt, not an R2 clean success.
        self.assertEqual(report["global"]["authored_r2_verified_success_without_escalation"], 0)
        self.assertEqual(report["global"]["frontier_exposure_usable"], 1)

    def test_escalation_without_recorded_reason_stays_unknown(self) -> None:
        record = self.seed(
            "escalated-noreason",
            profile="complex",
            freshness="escalated",
            outcome="completed",
            escalations=[{"at": "t", "from": "standard"}],
        )
        report = self.run_report([record])
        escalation = report["global"]["r2_to_r3_escalation"]
        self.assertEqual(escalation["recorded_reasons"], {})
        self.assertEqual(escalation["unknown_reason"], 1)

    def test_direct_r3_success_is_not_labelled_over_routed(self) -> None:
        record = self.seed("direct-r3", tier="R3", profile="complex", outcome="completed")
        report = self.run_report([record])
        direct = report["global"]["direct_frontier"]
        self.assertEqual(direct["authored_r3_records"], 1)
        self.assertEqual(direct["launched"], 1)
        self.assertEqual(direct["verified_success"], 1)
        self.assertIn("not evidence that R2 would have failed", direct["counterfactual_note"])
        # A direct R3 record is not an R2 observation and not an escalation.
        self.assertEqual(report["global"]["r2_to_r3_escalation"]["usable_r2_observations"], 0)
        self.assertEqual(report["global"]["authored_r2_verified_success_without_escalation"], 0)

    def test_abnormal_and_unknown_outcomes_are_not_folded_into_success_or_failure(self) -> None:
        records = [
            self.seed("ok", outcome="completed"),
            self.seed("abn", outcome="abnormal"),
            self.seed("unk", outcome=None),
        ]
        report = self.run_report(records)
        self.assertEqual(report["global"]["outcomes_usable"], {"abnormal": 1, "completed": 1, "unknown": 1})
        self.assertEqual(report["global"]["authored_r2_verified_success_without_escalation"], 1)

    def test_planned_only_and_unverified_records_are_excluded_from_usable(self) -> None:
        records = [
            self.seed("verified-launched", outcome="completed"),
            self.seed("planned-only", launched=False, outcome=None),
            self.seed("launched-unverified", outcome="completed", verified=False),
            self.seed("legacy-no-tier", tier=None, outcome="completed"),
        ]
        report = self.run_report(records)
        self.assertEqual(report["sample"]["routing_records"], 4)
        self.assertEqual(report["sample"]["planned_only_routes"], 1)
        self.assertEqual(report["sample"]["usable_observations"], 1)
        self.assertEqual(report["verification_signals"]["passed"], 3)
        self.assertEqual(report["verification_signals"]["missing"], 1)

    def test_missing_metadata_stays_unknown_not_defaulted(self) -> None:
        record = self.seed("no-meta", task_family=None, rubric_version=None, outcome="completed")
        report = self.run_report([record])
        self.assertIn("unknown", report["breakdowns"]["task_family"])
        self.assertIn("unknown", report["breakdowns"]["rubric_version"])
        self.assertEqual(report["unavailable_signals"]["human_intervention"].startswith("No deterministic"), True)

    def test_breakdowns_carry_counts_and_mixed_generations_are_not_merged(self) -> None:
        records = [
            self.seed("terra-a", executor_model="gpt-5.6-terra", task_family="model-routing", outcome="completed"),
            self.seed("terra-b", executor_model="gpt-5.6-terra", task_family="model-routing", outcome="failed"),
            self.seed("sonnet-a", provider="claude", executor_model="sonnet", task_family="lifecycle", outcome="completed"),
        ]
        report = self.run_report(records)
        pmg = report["breakdowns"]["provider_model_generation"]
        self.assertEqual(set(pmg), {"codex:gpt-5.6-terra", "claude:sonnet"})
        self.assertEqual(pmg["codex:gpt-5.6-terra"]["usable_observations"], 2)
        self.assertEqual(pmg["codex:gpt-5.6-terra"]["adequacy"], "insufficient")
        self.assertEqual(report["breakdowns"]["task_family"]["model-routing"]["usable_observations"], 2)
        self.assertEqual(report["breakdowns"]["task_family"]["lifecycle"]["usable_observations"], 1)

    def test_adequate_low_escalation_sample_yields_no_change_candidate(self) -> None:
        records = [self.seed(f"big{i}", outcome="completed") for i in range(routing.ROUTING_CALIBRATION_MIN_OBSERVATIONS)]
        report = self.run_report(records)
        self.assertEqual(report["sample"]["adequacy"], "adequate")
        self.assertEqual(report["advice"]["candidate_decision"], "no change")
        self.assertTrue(report["advice"]["requires_separate_managed_change"])

    def test_adequate_high_escalation_sample_yields_review_candidate(self) -> None:
        records = [self.seed(f"ok{i}", outcome="completed") for i in range(10)]
        records += [
            self.seed(
                f"esc{i}",
                profile="complex",
                freshness="escalated",
                outcome="completed",
                escalations=[{"at": "t", "from": "standard", "reason": "recurring contract conflict"}],
            )
            for i in range(6)
        ]
        report = self.run_report(records)
        self.assertEqual(report["sample"]["adequacy"], "adequate")
        self.assertIn("review", report["advice"]["candidate_decision"])

    def test_cli_routing_calibration_emits_json(self) -> None:
        (self.task / "openspec" / "changes" / "routing-change").mkdir(parents=True)
        (self.task / "openspec" / "changes" / "routing-change" / ".managed-task.json").write_text(
            json.dumps({"source_issue": "owner/backlog#7", "change": "routing-change"}), encoding="utf-8"
        )
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "model_routing.py"), "routing-calibration"],
            cwd=self.task,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("advice", payload)


if __name__ == "__main__":
    unittest.main()
