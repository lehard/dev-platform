from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from _platform_modules import load_platform_module  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    return load_platform_module(name, SCRIPTS / filename)


containment = load("delegation_containment", "delegation_containment.py")
guard = load("delegated_write_guard", "delegated_write_guard.py")
routing = load("model_routing", "model_routing.py")
agent_friction = load("agent_friction", "agent_friction.py")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


def route_ready(repo: Path) -> None:
    """Give a temporary repo the origin/main review base and the untracked local config a managed task has.

    A real task has an `origin/main` base and a git-ignored `.dev-platform.toml`;
    routing refuses to establish task content without the former and would read
    the latter as diverged task content.
    """
    git(repo, "update-ref", "refs/remotes/origin/main", "main")
    exclude = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()
    with open(exclude, "a", encoding="utf-8") as handle:
        handle.write(".dev-platform.toml\n.claude/\n")


class ModelRoutingTests(unittest.TestCase):
    def test_opaque_managed_provenance_uses_verified_private_identity(self) -> None:
        import managed_task

        provenance = self.task / "openspec/changes/routing-change/.managed-task.json"
        provenance.write_text(json.dumps({"private_lineage_handle": "pln_" + "a" * 32, "change": "routing-change"}), encoding="utf-8")
        (self.task / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "owner/backlog#7", "change": "routing-change"}), encoding="utf-8"
        )
        with patch.object(managed_task, "source_issue_for_provenance", return_value="owner/backlog#7") as verified:
            self.assertEqual(routing.current_managed_identity(self.task), ("owner/backlog#7", "routing-change"))
            self.assertEqual(routing._managed_identity(self.task), ("owner/backlog#7", "routing-change"))
            self.assertEqual(routing.resolve_managed_provenance(self.task, "owner/backlog#7", "routing-change")[2], "active")
        self.assertEqual(verified.call_count, 2)
        with patch.object(managed_task, "source_issue_for_provenance", side_effect=managed_task.ManagedTaskError("mismatch")):
            with self.assertRaisesRegex(routing.RoutingError, "could not be verified"):
                routing.resolve_managed_provenance(self.task, "owner/backlog#7", "routing-change")

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
        route_ready(self.integration)
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

    def test_durable_gate_resolves_only_the_exact_archived_task(self) -> None:
        route = self.prepare()
        completed = routing.Route(
            **{
                **routing.asdict(route),
                "execution": {"outcome": "completed", "launched": True, "returncode": 0, "violation": False},
            }
        )
        routing._write_route(self.record_path(), completed)
        routing._persist_completed_execution(completed)
        archived = self.task / "openspec" / "changes" / "archive" / "2026-09-19-routing-change"
        archived.parent.mkdir(parents=True)
        shutil.move(str(self.task / "openspec" / "changes" / "routing-change"), str(archived))
        unrelated = self.task / "openspec" / "changes" / "unrelated"
        unrelated.mkdir()
        (unrelated / ".managed-task.json").write_text(
            json.dumps({"source_issue": "owner/backlog#8", "change": "unrelated"}), encoding="utf-8"
        )
        with patch.object(routing, "main_root", return_value=self.integration):
            resolved = routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")
        self.assertEqual(resolved.change, "routing-change")
        self.assertEqual(resolved.source_issue, "owner/backlog#7")

    def test_complex_route_requires_explicit_retained_outcome(self) -> None:
        route = self.prepare(profile="complex")
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "explicit retained execution"):
                routing.require_routing_gate(self.task, route.source_issue, route.change)
            execution = routing.record_retained_execution(self.task, reason="R3 implementation completed by the current supervisor")
            resolved = routing.require_routing_gate(self.task, route.source_issue, route.change)
        self.assertEqual(execution["outcome"], "retained")
        self.assertFalse(execution["launched"])
        self.assertEqual(resolved.execution["retained"]["policy"], "complex-parent")

    def test_routine_child_writer_cannot_claim_parent_retention(self) -> None:
        self.prepare(profile="standard")
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "not supervisor-retained"):
                routing.record_retained_execution(
                    self.task,
                    reason="the supervisor preferred not to dispatch the available child",
                )

    def test_route_preparation_remains_rejected_after_archive(self) -> None:
        archived = self.task / "openspec" / "changes" / "archive" / "2026-09-19-routing-change"
        archived.parent.mkdir(parents=True)
        shutil.move(str(self.task / "openspec" / "changes" / "routing-change"), str(archived))
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "exactly one materialized managed OpenSpec change"):
                routing.prepare(self.task, provider="codex", profile="standard", rationale="too late", evidence=[])

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

    def test_efficiency_baseline_excludes_self_reported_claude_from_launched(self) -> None:
        codex_launched = {"change": "codex-real", "execution": {"launched": True, "outcome": "completed"}}
        claude_claimed = {
            "change": "claude-claimed",
            "execution": {
                "outcome": "claimed", "launch_evidence": "self-reported", "launched": None,
                "claimed_agent_id": "agent-abc123",
            },
        }
        claude_legacy = {"change": "claude-legacy", "execution": {"launched": True, "agent_id": "x"}}
        with patch.object(routing, "_local_routing_records", return_value=[codex_launched, claude_claimed, claude_legacy]):
            report = routing.efficiency_baseline(self.task)
        self.assertEqual(report["observations"]["launched_executions"], 1)

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
        self.assertEqual(result["delegated"], "pending_begin_delegation")
        self.assertIn("begin-claude-delegation", result["next_steps"][0])
        self.assertEqual(result["tier"], "detection-only")
        self.assertNotIn("isolation", result["handoff"])
        self.assertEqual(result["handoff"]["model"], "sonnet")
        # "pending_begin_delegation" means exactly that: the hand-off was
        # emitted but no delegation was opened and nothing was invoked, so there is no participant
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
            routing.begin_claude_delegation(self.task)
            (self.task / "implemented.txt").write_text("real subagent work\n", encoding="utf-8")
            execution = routing.record_claude_execution(self.task, agent_id="agent-abc123", summary="added implemented.txt")
        self.assertIsNone(execution["launched"])
        self.assertEqual(execution["outcome"], "claimed")
        self.assertEqual(execution["launch_evidence"], "self-reported")
        self.assertEqual(execution["claimed_agent_id"], "agent-abc123")
        self.assertNotIn("agent_id", execution)
        self.assertNotIn("participant", execution)
        self.assertEqual(execution["postcheck"]["containment"], "clean")
        self.assertEqual(
            execution["claimed_participant"],
            {
                "role": "executor",
                "provider": "claude",
                "profile": "standard",
                "model": {"value": "sonnet", "source": "self-reported"},
                "reasoning_effort": {"value": None, "source": "unknown"},
                "execution_id": {"value": "agent-abc123", "kind": "claude-agent-id"},
            },
        )
        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIsNone(saved["execution"]["launched"])
        self.assertEqual(saved["execution"]["outcome"], "claimed")
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
            routing.begin_claude_delegation(self.task)
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

    def test_arbitrary_agent_id_is_not_launch_proof(self) -> None:
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
            routing.begin_claude_delegation(self.task)
            execution = routing.record_claude_execution(self.task, agent_id="anything-made-up")
            self.assertIsNone(execution["launched"])
            self.assertEqual(execution["outcome"], "claimed")
            self.assertEqual(execution["launch_evidence"], "self-reported")
            self.assertNotIn("participant", execution)
            self.assertEqual(execution["claimed_participant"]["model"]["source"], "self-reported")
            self.assertFalse(routing._launch_confirmed(execution))
            gate_route = routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")
        self.assertEqual(gate_route.change, "routing-change")
        self.assertEqual(routing._execution_outcome_label({"execution": execution}), "claimed")

    def test_routing_gate_refuses_legacy_self_reported_claude_launch(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration):
            route = self.prepare(provider="claude", profile="standard")
            legacy_execution = {
                "launched": True,
                "agent_id": "x",
                "postcheck": {"containment": "clean", "pre_existing_changes": []},
                "participant": {
                    "role": "executor", "provider": "claude", "profile": "standard",
                    "model": {"value": "sonnet", "source": "selected"},
                    "reasoning_effort": {"value": None, "source": "unknown"},
                    "execution_id": {"value": "x", "kind": "claude-agent-id"},
                },
            }
            next_route = routing.Route(**{**routing.asdict(route), "execution": legacy_execution})
            routing._write_route(self.record_path(), next_route)
            routing._persist_completed_execution(next_route)
            with self.assertRaisesRegex(routing.RoutingError, "cannot verify"):
                routing.require_routing_gate(self.task, route.source_issue, route.change)

    def test_legacy_claude_claim_can_be_normalized_without_retrospective_delegation(self) -> None:
        route = self.prepare(provider="claude", profile="standard")
        legacy = routing.Route(**{**routing.asdict(route), "execution_plan": None,
                                "execution": {"launched": True, "agent_id": "legacy-agent"}})
        routing._write_route(self.record_path(), legacy)
        (self.task / "implemented.txt").write_text("legacy child work\n", encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "re-route"):
            routing.record_claude_execution(self.task, agent_id="different-agent")
        with patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            execution = routing.record_claude_execution(self.task, agent_id="legacy-agent")
        self.assertEqual(execution["outcome"], "claimed")
        self.assertIsNone(execution["launched"])
        self.assertNotIn("participant", execution)
        normalized, _ = routing._read_route(self.task)
        self.assertIsNone(normalized.execution_plan)
        routing.require_early_routing_gate(self.task)
        routing.require_routing_gate(self.task, route.source_issue, route.change)

    def test_legacy_claude_normalization_still_requires_clean_containment(self) -> None:
        route = self.prepare(provider="claude", profile="standard")
        legacy = routing.Route(**{**routing.asdict(route), "execution_plan": None,
                                "execution": {"launched": True, "agent_id": "legacy-agent"}})
        routing._write_route(self.record_path(), legacy)
        (self.integration / "README.md").write_text("escaped work\n", encoding="utf-8")
        with patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            with self.assertRaises(routing.RoutingError):
                routing.record_claude_execution(self.task, agent_id="legacy-agent")
        unchanged, _ = routing._read_route(self.task)
        self.assertEqual(unchanged.execution, legacy.execution)

    def test_routing_gate_refuses_claimed_claude_execution_with_dirty_postcheck(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration):
            route = self.prepare(provider="claude", profile="standard")
            claimed_execution = {
                "outcome": "claimed",
                "launch_evidence": "self-reported",
                "launched": None,
                "claimed_agent_id": "agent-abc123",
                "postcheck": {"containment": "violation", "pre_existing_changes": []},
            }
            next_route = routing.Route(**{**routing.asdict(route), "execution": claimed_execution})
            routing._write_route(self.record_path(), next_route)
            routing._persist_completed_execution(next_route)
            with self.assertRaisesRegex(routing.RoutingError, "clean containment postcheck"):
                routing.require_routing_gate(self.task, route.source_issue, route.change)

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

    def enable_context_delegation(self) -> None:
        (self.task / ".dev-platform.toml").write_text(
            "[model_routing.codex]\nstandard_model = \"cheap-codex\"\ncomplex_model = \"strong-codex\"\n"
            "[context_delegation]\nenabled = true\n",
            encoding="utf-8",
        )

    def context_request(self) -> dict[str, object]:
        return {"question": "Where is the routing model selected?", "scope": [{"path": "README.md"}]}

    def test_codex_context_worker_uses_read_only_routine_profile_and_records_bounded_evidence(self) -> None:
        self.enable_context_delegation()
        route = self.prepare()
        captured: list[str] = []

        def fake_run(argv, **_kwargs):
            captured.extend(argv)
            destination = Path(argv[argv.index("--output-last-message") + 1])
            destination.write_text(
                json.dumps(
                    {
                        "confidence": "high",
                        "synthesis": "The bounded file is only the test README.",
                        "findings": [{"path": "README.md", "finding": "README exists", "uncertainty": "No symbol-level detail was requested."}],
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"type":"turn.completed","usage":{"input_tokens":12,"cached_input_tokens":4,"output_tokens":3,"total_tokens":15}}',
            )

        with patch.object(routing.subprocess, "run", side_effect=fake_run):
            observation = routing.delegate_codex_context(self.task, self.context_request(), codex_bin="codex-test")

        self.assertEqual(observation["outcome"], "completed")
        self.assertEqual(observation["profile"], "routine")
        self.assertEqual(observation["model"], {"value": "gpt-6-luna", "source": "selected"})
        self.assertEqual(observation["request"]["question_chars"], len(self.context_request()["question"]))
        self.assertNotIn("question", observation["request"])
        self.assertIn("read-only", captured)
        self.assertNotIn("workspace-write", captured)
        self.assertEqual(observation["source_payload"]["lines"], 1)
        self.assertGreater(observation["source_payload"]["bytes"], 0)
        self.assertEqual(observation["returned_payload"]["bytes"], len(json.dumps({"confidence": "high", "synthesis": "The bounded file is only the test README.", "findings": [{"path": "README.md", "finding": "README exists", "uncertainty": "No symbol-level detail was requested."}]}).encode("utf-8")))
        self.assertEqual(observation["usage"]["input_tokens"], {"value": 12, "source": "runtime-confirmed", "status": "measured"})
        self.assertEqual(observation["usage"]["cache_read_tokens"]["value"], 4)
        self.assertEqual(observation["usage"]["fresh_input_tokens"]["status"], "unknown")
        saved, _ = routing._read_route(self.task)
        self.assertEqual(saved.context_delegations, (observation,))
        durable = json.loads(self.durable_record_path().read_text(encoding="utf-8"))
        self.assertEqual(durable["context_delegations"], [observation])
        self.assertIsNone(route.execution)

    def test_low_confidence_and_worker_unavailability_fall_open_to_direct_read(self) -> None:
        self.enable_context_delegation()
        self.prepare()

        def low_confidence(argv, **_kwargs):
            destination = Path(argv[argv.index("--output-last-message") + 1])
            destination.write_text(json.dumps({"confidence": "low", "synthesis": "Uncertain.", "findings": []}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        with patch.object(routing.subprocess, "run", side_effect=low_confidence):
            low = routing.delegate_codex_context(self.task, self.context_request(), codex_bin="codex-test")
        with patch.object(routing.subprocess, "run", side_effect=FileNotFoundError()):
            unavailable = routing.delegate_codex_context(self.task, self.context_request(), codex_bin="missing-codex")

        self.assertEqual(low["outcome"], "low-confidence")
        self.assertTrue(low["fallback"]["direct_read_available"])
        self.assertEqual(unavailable["outcome"], "runtime-unavailable")
        self.assertTrue(unavailable["fallback"]["direct_read_available"])

    def test_claude_context_honestly_reports_missing_read_only_agent_boundary(self) -> None:
        self.enable_context_delegation()
        self.prepare(provider="claude")
        observation = routing.delegate_claude_context(self.task, self.context_request())
        self.assertEqual(observation["outcome"], "runtime-unavailable")
        self.assertIn("no supported read-only permission boundary", observation["fallback"]["reason"])
        self.assertTrue(observation["fallback"]["direct_read_available"])

    def test_context_reread_counts_explicit_targeted_follow_up_without_a_second_state_machine(self) -> None:
        self.enable_context_delegation()
        self.prepare()
        with patch.object(routing.subprocess, "run", side_effect=FileNotFoundError()):
            observation = routing.delegate_codex_context(self.task, self.context_request(), codex_bin="missing-codex")
        updated = routing.record_context_reread(self.task, observation["id"], [{"path": "README.md"}])
        self.assertEqual(updated["reread_payload"]["lines"], 1)
        self.assertGreater(updated["reread_payload"]["bytes"], 0)
        saved, _ = routing._read_route(self.task)
        self.assertEqual(len(saved.context_delegations), 1)
        self.assertEqual(saved.context_delegations[0]["reread_payload"], updated["reread_payload"])

    def test_context_request_rejects_scope_outside_repository(self) -> None:
        self.prepare()
        with self.assertRaisesRegex(routing.ContextDelegationError, "inside the repository"):
            routing.context_request(self.task, {"question": "Read elsewhere", "scope": [{"path": "../outside.txt"}]})

    def enable_observation_lifecycle(self, min_bytes: int | None = None) -> None:
        body = (
            "[model_routing.codex]\nstandard_model = \"cheap-codex\"\ncomplex_model = \"strong-codex\"\n"
            "[observation_lifecycle]\nenabled = true\n"
        )
        if min_bytes is not None:
            body += f"min_bytes = {min_bytes}\n"
        (self.task / ".dev-platform.toml").write_text(body, encoding="utf-8")

    def observation_store_path(self, handle: str) -> Path:
        return self.task / ".claude" / "observations" / "routing-change" / f"{handle}.json"

    def test_small_observation_takes_the_existing_direct_path_without_ceremony(self) -> None:
        self.enable_observation_lifecycle(min_bytes=200)
        self.prepare()
        result = routing.cool_observation(self.task, {"source": "read:README.md", "kind": "file_read", "payload": "short output\n"})
        self.assertEqual(result["status"], "below-threshold")
        self.assertIsNone(result["handle"])
        saved, _ = routing._read_route(self.task)
        self.assertEqual(saved.observations, ())
        self.assertFalse((self.task / ".claude" / "observations").exists())

    def test_disabled_lifecycle_also_takes_the_existing_direct_path(self) -> None:
        self.prepare()  # observation_lifecycle left unconfigured/disabled
        payload = "x" * 20000
        result = routing.cool_observation(self.task, {"source": "command:pytest", "kind": "test_output", "payload": payload})
        self.assertEqual(result["status"], "disabled")
        self.assertIsNone(result["handle"])
        saved, _ = routing._read_route(self.task)
        self.assertEqual(saved.observations, ())

    def test_large_observation_is_cooled_into_bounded_local_storage_with_a_stable_handle(self) -> None:
        self.enable_observation_lifecycle(min_bytes=50)
        self.prepare()
        payload = "line of output\n" * 300  # exceeds OBSERVATION_MAX_EXCERPT_BYTES so hot < source
        result = routing.cool_observation(self.task, {"source": "command:pytest", "kind": "test_output", "payload": payload})
        self.assertEqual(result["status"], "cold")
        self.assertIsInstance(result["handle"], str)
        self.assertTrue(result["handle"])
        self.assertEqual(result["source_payload"]["bytes"], len(payload.encode("utf-8")))
        self.assertLess(result["hot_payload"]["bytes"], result["source_payload"]["bytes"])
        self.assertLessEqual(result["hot_payload"]["bytes"], routing.OBSERVATION_MAX_EXCERPT_BYTES)
        self.assertEqual(result["usage"]["input_tokens"]["status"], "unknown")
        saved, _ = routing._read_route(self.task)
        self.assertEqual(len(saved.observations), 1)
        self.assertEqual(saved.observations[0]["handle"], result["handle"])
        self.assertNotIn("payload", saved.observations[0])
        store_path = self.observation_store_path(result["handle"])
        self.assertTrue(store_path.is_file())
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["payload"], payload)
        durable = json.loads(self.durable_record_path().read_text(encoding="utf-8"))
        self.assertEqual(durable["observations"][0]["handle"], result["handle"])

    def test_exact_recall_returns_the_precise_requested_byte_region(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "0123456789ABCDEFGHIJ"
        cold = routing.cool_observation(self.task, {"source": "search:grep", "kind": "search_result", "payload": payload})
        recalled = routing.recall_observation(self.task, cold["handle"], {"start_byte": 5, "end_byte": 10})
        self.assertEqual(recalled["status"], "resolved")
        self.assertEqual(recalled["content"], "56789")
        self.assertEqual(recalled["recall_payload"]["bytes"], 5)
        saved, _ = routing._read_route(self.task)
        self.assertEqual(saved.observations[0]["recall_payload"], recalled["recall_payload"])

    def test_exact_recall_by_query_returns_bounded_context_around_the_match(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "before " + "TARGET" + " after " * 5
        cold = routing.cool_observation(self.task, {"source": "search:grep", "kind": "search_result", "payload": payload})
        recalled = routing.recall_observation(self.task, cold["handle"], {"query": "TARGET", "context_chars": 3})
        self.assertEqual(recalled["status"], "resolved")
        self.assertIn("TARGET", recalled["content"])
        self.assertLess(len(recalled["content"]), len(payload))

    def test_recall_without_explicit_bound_is_rejected(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        cold = routing.cool_observation(self.task, {"source": "search:grep", "kind": "search_result", "payload": "0123456789ABCDEF"})
        with self.assertRaisesRegex(routing.ObservationLifecycleError, "explicit bounded range/query"):
            routing.recall_observation(self.task, cold["handle"], {})

    def test_full_recall_escape_hatch_returns_the_entire_preserved_original(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "full payload text " * 5
        cold = routing.cool_observation(self.task, {"source": "command:build", "kind": "command_output", "payload": payload})
        recalled = routing.recall_observation(self.task, cold["handle"], {"full": True})
        self.assertTrue(recalled["full"])
        self.assertEqual(recalled["content"], payload)

    def test_recall_reports_unknown_handle_explicitly_without_fabricating_content(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        with self.assertRaisesRegex(routing.ObservationLifecycleError, "no cold observation has handle"):
            routing.recall_observation(self.task, "nonexistent-handle", {"full": True})

    def test_recall_reports_stale_handle_explicitly_without_fabricating_content(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "payload big enough to cool " * 3
        cold = routing.cool_observation(self.task, {"source": "read:big.txt", "kind": "file_read", "payload": payload})
        self.observation_store_path(cold["handle"]).unlink()
        with self.assertRaisesRegex(routing.ObservationLifecycleError, "stale"):
            routing.recall_observation(self.task, cold["handle"], {"full": True})

    def test_storage_failure_fails_open_to_the_current_full_observation_path(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "payload big enough to attempt cooling " * 3
        with patch.object(routing, "atomic_write_text", side_effect=OSError("disk full")):
            result = routing.cool_observation(self.task, {"source": "command:build", "kind": "command_output", "payload": payload})
        self.assertEqual(result["status"], "storage-failed")
        self.assertIn("disk full", result["reason"])
        self.assertIsNone(result["handle"])
        self.assertEqual(result["source_payload"]["bytes"], len(payload.encode("utf-8")))
        saved, _ = routing._read_route(self.task)
        self.assertEqual(saved.observations, ())

    def test_route_payload_without_observations_field_defaults_to_empty_tuple(self) -> None:
        """Backward compatibility: a record written before this field existed."""
        self.prepare()
        path = self.record_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("observations", payload)
        del payload["observations"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        reloaded, _ = routing._read_route(self.task)
        self.assertEqual(reloaded.observations, ())

    def cold_execution_log(self, *, exit_status: int = 1) -> tuple[dict[str, object], str]:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = "running tests\n" + ("progress: still running\n" * 600) + "ERROR expected green but got red\nsummary: failed\n"
        cold = routing.cool_observation(
            self.task,
            {
                "source": "command:pytest",
                "kind": "test_output",
                "payload": payload,
                "command_result": {"command": "pytest -q", "exit_status": exit_status},
            },
        )
        return cold, payload

    @staticmethod
    def reducer_receipt(cold: dict[str, object], payload: str, *, exit_status: int = 1) -> dict[str, object]:
        quote = "ERROR expected green but got red"
        start = len(payload[: payload.index(quote)].encode("utf-8"))
        return {
            "source_handle": cold["handle"],
            "source_digest": routing._source_digest(payload),
            "command_result": {"command": "pytest -q", "exit_status": exit_status, "status": "passed" if exit_status == 0 else "failed"},
            "confidence": "high",
            "evidence": [{"start_byte": start, "end_byte": start + len(quote.encode("utf-8")), "quote": quote}],
            "findings": [{"text": "pytest reported one failure", "evidence_indexes": [0]}],
            "uncertainty": ["The receipt does not diagnose the underlying cause."],
        }

    def test_execution_log_reducer_verifies_bound_receipt_and_preserves_exact_recall(self) -> None:
        cold, payload = self.cold_execution_log()
        receipt = self.reducer_receipt(cold, payload)
        result = routing.reduce_execution_log(self.task, cold["handle"], receipt, participant="routine-adapter")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["receipt"]["command_result"]["status"], "failed")
        recalled = routing.recall_observation(self.task, cold["handle"], {"query": "ERROR", "context_chars": 0})
        self.assertEqual(recalled["content"], "ERROR")
        saved, _ = routing._read_route(self.task)
        reducer = saved.observations[0]["reducer"]
        self.assertEqual(reducer["verification"]["status"], "verified")
        self.assertEqual(reducer["participant"], "routine-adapter")
        self.assertLess(reducer["receipt_payload"]["bytes"], reducer["source_payload"]["bytes"])
        self.assertEqual(reducer["usage"]["input_tokens"]["status"], "unknown")

    def test_execution_log_reducer_falls_back_for_wrong_digest_fabricated_quote_and_low_confidence(self) -> None:
        cold, payload = self.cold_execution_log()
        receipt = self.reducer_receipt(cold, payload)
        receipt["source_digest"] = "0" * 64
        result = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(result["status"], "fallback-exact-source")
        self.assertIn("source_digest", result["reason"])
        receipt = self.reducer_receipt(cold, payload)
        receipt["evidence"] = [{"start_byte": 0, "end_byte": 7, "quote": "invented"}]
        result = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(result["status"], "fallback-exact-source")
        self.assertIn("quote", result["reason"])
        receipt = self.reducer_receipt(cold, payload)
        receipt["confidence"] = "low"
        result = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(result["status"], "fallback-exact-source")
        self.assertIn("confidence", result["reason"])

    def test_contradictory_reducer_cannot_turn_a_failing_canonical_result_green(self) -> None:
        cold, payload = self.cold_execution_log(exit_status=1)
        receipt = self.reducer_receipt(cold, payload, exit_status=0)
        result = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(result["status"], "fallback-exact-source")
        self.assertIn("command_result", result["reason"])
        saved, _ = routing._read_route(self.task)
        self.assertIsNone(saved.execution, "reducer receipts must not create or change canonical execution outcomes")
        self.assertEqual(saved.observations[0]["command_result"]["status"], "failed")

    def test_reducer_unavailable_and_non_execution_logs_keep_exact_source_path(self) -> None:
        cold, _ = self.cold_execution_log()
        deterministic = routing.reduce_execution_log(self.task, cold["handle"])
        self.assertEqual(deterministic["status"], "verified")
        self.assertEqual(deterministic["provenance"]["participant"], "deterministic-parser")
        self.enable_observation_lifecycle(min_bytes=10)
        search = routing.cool_observation(
            self.task, {"source": "search:rg", "kind": "search_result", "payload": "result " * 20}
        )
        unsupported = routing.reduce_execution_log(self.task, search["handle"])
        self.assertEqual(unsupported["status"], "fallback-exact-source")
        self.assertIn("only cold command_output", unsupported["reason"])

    def test_reducer_returns_exact_source_for_tampered_storage_and_oversized_receipt(self) -> None:
        cold, payload = self.cold_execution_log()
        receipt = self.reducer_receipt(cold, payload)
        receipt["uncertainty"] = ["x" * 4000]
        oversized = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(oversized["status"], "fallback-exact-source")
        self.assertIn("does not reduce", oversized["reason"])
        store_path = self.observation_store_path(cold["handle"])
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        stored["payload"] += "injected\n"
        store_path.write_text(json.dumps(stored), encoding="utf-8")
        tampered = routing.reduce_execution_log(self.task, cold["handle"], receipt)
        self.assertEqual(tampered["status"], "source-unavailable")
        self.assertIn("archive-time digest", tampered["reason"])
        self.assertNotIn("exact_source", tampered)

    def test_long_passing_log_uses_deterministic_receipt_and_exact_recall(self) -> None:
        self.enable_observation_lifecycle(min_bytes=10)
        self.prepare()
        payload = ("progress line\n" * 600) + "42 passed in 3.2s\n"
        cold = routing.cool_observation(self.task, {
            "source": "command:pytest", "kind": "test_output", "payload": payload,
            "command_result": {"command": "pytest -q", "exit_status": 0},
        })
        reduced = routing.reduce_execution_log(self.task, cold["handle"])
        self.assertEqual(reduced["status"], "verified")
        self.assertEqual(reduced["receipt"]["command_result"]["status"], "passed")
        self.assertEqual(reduced["receipt"]["evidence"][0]["quote"], "42 passed in 3.2s")
        self.assertLess(reduced["provenance"]["receipt_payload"]["bytes"], cold["hot_payload"]["bytes"])
        self.assertEqual(routing.recall_observation(self.task, cold["handle"], {"full": True})["content"], payload)

    def enable_same_context_compaction(self, *, observations: bool = False) -> None:
        body = (
            "[model_routing.codex]\nstandard_model = \"cheap-codex\"\ncomplex_model = \"strong-codex\"\n"
            "[same_context_compaction]\nenabled = true\n"
        )
        if observations:
            body += "[observation_lifecycle]\nenabled = true\nmin_bytes = 10\n"
        (self.task / ".dev-platform.toml").write_text(body, encoding="utf-8")

    def compaction_request(self, **overrides):
        request = {
            "opportunity": "subtask-complete",
            "live_history": "x" * 1000,
            "compacted_payload": "next step only",
            "static_reductions": {
                "repeated_instructions_bytes": 100,
                "eager_capability_bytes": 50,
                "prompt_boundary_bytes": 50,
            },
            "expected_future_replays": 3,
            "rebuild_risk_bytes": 10,
            "observed_subsequent_replay_bytes": 12,
            "continuation": {
                "verified_facts": [{"statement": "The repository has its README.", "evidence": [{"path": "README.md"}]}],
                "assumptions": ["No runtime cache measurement is available."],
                "blockers": ["Await the verification phase."],
                "cold_observation_handles": [],
                "next_intent": "Run the focused verification check.",
            },
        }
        request.update(overrides)
        return request

    def test_same_context_compaction_records_keep_and_compact_gate_outcomes(self) -> None:
        self.enable_same_context_compaction()
        self.prepare()
        kept = routing.evaluate_same_context_compaction(
            self.task, self.compaction_request(expected_future_replays=0, compacted_payload="x" * 900)
        )
        compacted = routing.evaluate_same_context_compaction(self.task, self.compaction_request())
        self.assertEqual(kept["decision"], "keep")
        self.assertIn("does not materially", kept["reason"])
        self.assertEqual(compacted["decision"], "compact")
        self.assertEqual(compacted["continuation"]["managed_task"], {"source_issue": "owner/backlog#7", "change": "routing-change"})
        self.assertEqual(compacted["continuation"]["blockers"], ["Await the verification phase."])
        self.assertEqual(compacted["runtime_usage"]["input_tokens"]["status"], "unknown")
        self.assertIsNone(compacted["observed_subsequent_replay_bytes"])
        self.assertEqual(routing.resume_same_context_compaction(self.task)["status"], "ready")
        saved, _ = routing._read_route(self.task)
        self.assertEqual(len(saved.compactions), 2)

    def test_same_context_compaction_validates_cold_handles_and_fails_open_when_stale(self) -> None:
        self.enable_same_context_compaction(observations=True)
        self.prepare()
        cold = routing.cool_observation(self.task, {"source": "command:pytest", "kind": "test_output", "payload": "result " * 20})
        request = self.compaction_request()
        request["continuation"]["cold_observation_handles"] = [cold["handle"]]
        compacted = routing.evaluate_same_context_compaction(self.task, request)
        self.assertEqual(compacted["decision"], "compact")
        self.observation_store_path(cold["handle"]).unlink()
        stale = routing.evaluate_same_context_compaction(self.task, request)
        self.assertEqual(stale["decision"], "keep")
        self.assertIn("stale", stale["reason"])
        self.assertIsNone(stale["continuation"])
        self.assertEqual(routing.resume_same_context_compaction(self.task)["status"], "stale")

    def test_same_context_resume_rejects_changed_repository_evidence(self) -> None:
        self.enable_same_context_compaction()
        self.prepare()
        routing.evaluate_same_context_compaction(self.task, self.compaction_request())
        (self.task / "README.md").write_text("Changed after compaction", encoding="utf-8")
        resumed = routing.resume_same_context_compaction(self.task)
        self.assertEqual(resumed["status"], "stale")
        self.assertIsNone(resumed["continuation"])

    def test_same_context_compaction_rejects_unbounded_continuation(self) -> None:
        self.enable_same_context_compaction()
        self.prepare()
        request = self.compaction_request()
        request["continuation"]["next_intent"] = "x" * (routing.COMPACTION_MAX_TEXT_BYTES + 1)
        result = routing.evaluate_same_context_compaction(self.task, request)
        self.assertEqual(result["decision"], "keep")
        self.assertIn("at most", result["reason"])
        self.assertIsNone(result["continuation"])


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
        route_ready(self.clone)
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

    def test_parent_only_topology_declares_retention_up_front_and_finalizes(self) -> None:
        # As in a real checkout, machine-local `.claude/` state is git-ignored here.
        with (self.clone / ".git" / "info" / "exclude").open("a", encoding="utf-8") as exclude:
            exclude.write(".claude/\n")
        route = self.prepare()
        self.assertEqual(route.execution_plan["mode"], routing.PLAN_RETAINED)
        self.assertEqual(route.execution_plan["policy"], "parent-only-topology")
        routing.require_early_routing_gate(self.clone)
        with patch.object(routing, "main_root", return_value=self.clone):
            execution = routing.record_retained_execution(self.clone, reason="standalone clone has no child-writer boundary")
        self.assertEqual(execution["retained"]["policy"], "parent-only-topology")
        routing.require_early_routing_gate(self.clone)

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


class ExternalAdvanceRecoveryTests(unittest.TestCase):
    """Task 3.3: exact successful historical recovery, and mismatched/insufficient
    friction evidence rejection, for `model_routing.recover_external_advance`."""

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
        route_ready(self.integration)
        self.task = Path(self.tmp.name) / "task"
        git(self.integration, "worktree", "add", "-qb", "agent/recovery", str(self.task), "main")
        change = self.task / "openspec" / "changes" / "recovery-change"
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(
            json.dumps({"source_issue": "owner/backlog#135", "change": "recovery-change"}), encoding="utf-8"
        )
        (self.task / ".dev-platform.toml").write_text('main_branch = "main"\n', encoding="utf-8")
        with patch.object(routing, "main_root", return_value=self.integration):
            self.route = routing.prepare(
                self.task, provider="codex", profile="standard",
                rationale="bounded current-spec preflight", evidence=["openspec/changes/recovery-change"],
            )
        self.before_head = self.route.pre_snapshot["head"]
        (self.integration / "concurrent.txt").write_text("advance\n", encoding="utf-8")
        git(self.integration, "add", "concurrent.txt")
        git(self.integration, "commit", "-qm", "concurrent lifecycle advance")
        self.after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.integration, text=True, capture_output=True, check=True
        ).stdout.strip()
        self.started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        git(self.integration, "update-ref", "refs/remotes/origin/main", self.after_head)
        self.ended_at = datetime.now(timezone.utc).isoformat()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def record_path(self) -> Path:
        return self.task / ".claude" / "model-routing" / "recovery-change.json"

    def write_flagged_execution(self, **overrides) -> None:
        route_path = self.record_path()
        payload = json.loads(route_path.read_text(encoding="utf-8"))
        execution = {
            "mechanism": "codex-workspace-write-sandbox",
            "launched": True,
            "returncode": 0,
            "violation": True,
            "writer_state": "released",
            "classification": "violation",
            "before_head": self.before_head,
            "after_head": self.after_head,
            "outcome": "failed",
            "efficiency": {"timing": {"started_at": self.started_at, "ended_at": self.ended_at}},
            "participant": {
                "role": "executor", "provider": "codex", "profile": "standard",
                "model": {"value": "gpt-5.6-terra", "source": "selected"},
                "execution_id": {"kind": "codex-thread", "value": "thread-abc"},
                "reasoning_effort": {"value": None, "source": "unknown"},
            },
        }
        execution.update(overrides)
        payload["execution"] = execution
        route_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def write_friction_event(self, **overrides) -> str:
        friction_path = self.integration / ".claude" / "agent-friction.jsonl"
        friction_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "id": "fixture-event-1",
            "at": "2026-09-20T05:14:25+00:00",
            "category": "delegated-write-containment-violation",
            "classification": "process-friction",
            "task": "owner/backlog#135",
            "observation": (
                "Delegated write containment violation: changes appeared outside assigned worktree "
                f"{self.task.resolve()}. Integration HEAD moved during delegation (something was committed there)."
            ),
            "evidence": "new_changes=[] disappeared_changes=[] head_moved=True enforcement_tier='hard'",
            "run": {"change": None, "participant": None, "role": "unknown", "source_issue": None, "supervisor": None},
        }
        entry.update(overrides)
        with friction_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        return entry["id"]

    def recover(self, **kwargs):
        defaults = {"friction_event": "fixture-event-1", "before_head": self.before_head, "after_head": self.after_head}
        defaults.update(kwargs)
        with patch.object(agent_friction, "main_root", return_value=self.integration):
            return routing.recover_external_advance(self.task, **defaults)

    def test_recovery_succeeds_for_an_exact_matching_friction_event(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        recovery = self.recover()
        self.assertEqual(recovery["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        route, _ = routing._read_route(self.task)
        self.assertEqual(route.execution["recovery"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        self.assertEqual(route.execution["recovery"]["friction_event"], "fixture-event-1")
        # The original failed observation is preserved, never rewritten.
        self.assertTrue(route.execution["violation"])
        self.assertEqual(route.execution["returncode"], 0)
        self.assertEqual(route.execution["outcome"], "failed")

    def test_recovery_lets_the_terminal_routing_gate_pass(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        self.recover()
        route = routing.require_routing_gate(self.task, "owner/backlog#135", "recovery-change")
        self.assertEqual(route.execution["recovery"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)

    def test_routing_gate_still_blocks_an_unrecovered_violation(self) -> None:
        self.write_flagged_execution()
        with self.assertRaisesRegex(routing.RoutingError, "requires a clean successful native Codex executor launch"):
            routing.require_routing_gate(self.task, "owner/backlog#135", "recovery-change")

    def test_recovery_rejects_mismatched_source_issue(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event(task="owner/backlog#999")
        with self.assertRaisesRegex(routing.RoutingError, "does not identify this exact managed task"):
            self.recover()

    def test_recovery_rejects_mismatched_worktree(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event(observation="unrelated worktree path only")
        with self.assertRaisesRegex(routing.RoutingError, "does not identify this exact assigned worktree"):
            self.recover()

    def test_recovery_rejects_prose_evidence_that_does_not_match_the_deterministic_format(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event(
            evidence=(
                "Routing record ... records launched=true, returncode=0, violation=true; postcheck reports "
                f"integration HEAD moved during delegation; git log identifies {self.after_head[:7]}."
            )
        )
        with self.assertRaisesRegex(routing.RoutingError, "not the exact structured containment format"):
            self.recover()

    def test_recovery_rejects_a_path_mutation_evidence_shape(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event(
            evidence="new_changes=['escaped.txt'] disappeared_changes=[] head_moved=True enforcement_tier='hard'"
        )
        with self.assertRaisesRegex(routing.RoutingError, "pure integration-head move"):
            self.recover()

    def test_recovery_rejects_detection_only_tier_evidence(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event(
            evidence="new_changes=[] disappeared_changes=[] head_moved=True enforcement_tier='detection-only'"
        )
        with self.assertRaisesRegex(routing.RoutingError, "not native hard containment"):
            self.recover()

    def test_recovery_rejects_before_head_mismatch(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        with self.assertRaisesRegex(routing.RoutingError, "does not match this route's recorded pre-execution head"):
            self.recover(before_head="0" * 40)

    def test_recovery_rejects_unproven_after_head(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        with self.assertRaisesRegex(routing.RoutingError, "cannot prove"):
            self.recover(after_head="1" * 40)

    def test_recovery_refuses_a_clean_execution_with_nothing_to_recover(self) -> None:
        self.write_flagged_execution(violation=False, outcome="completed")
        self.write_friction_event()
        with self.assertRaisesRegex(routing.RoutingError, "not in that exact shape"):
            self.recover()

    def test_recovery_is_not_repeatable(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        self.recover()
        with self.assertRaisesRegex(routing.RoutingError, "already has a recorded recovery"):
            self.recover()

    def test_missing_friction_event_refuses(self) -> None:
        self.write_flagged_execution()
        with self.assertRaisesRegex(routing.RoutingError, "no machine-local friction event"):
            self.recover(friction_event="does-not-exist")

    def test_recovery_succeeds_when_main_advances_again_after_the_flagged_execution(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        # Simulate an unrelated later merge: main keeps moving past after_head, exactly
        # the scenario that made the real Development Backlog #135 recovery attempt fail
        # under the old exact-current-tip verifier. Recovery must still succeed.
        (self.integration / "later.txt").write_text("later merge\n", encoding="utf-8")
        git(self.integration, "add", "later.txt")
        git(self.integration, "commit", "-qm", "unrelated later merge")
        newest_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.integration, text=True, capture_output=True, check=True
        ).stdout.strip()
        git(self.integration, "update-ref", "refs/remotes/origin/main", newest_head)
        recovery = self.recover()
        self.assertEqual(recovery["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        route, _ = routing._read_route(self.task)
        self.assertEqual(
            route.execution["recovery"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE
        )
        # The original flagged execution facts remain unmodified by a successful recovery.
        self.assertTrue(route.execution["violation"])
        self.assertEqual(route.execution["returncode"], 0)
        self.assertEqual(route.execution["outcome"], "failed")

    def test_recovery_refuses_without_recorded_execution_timing(self) -> None:
        self.write_flagged_execution(efficiency=None)
        self.write_friction_event()
        with self.assertRaisesRegex(routing.RoutingError, "recorded start/end timing"):
            self.recover()

    def durable_record_path(self) -> Path:
        return self.integration / ".claude" / "model-routing" / "recovery-change.json"

    def write_durable_flagged_execution(self) -> None:
        """Simulate dispatch_codex's own durable mirror already existing for the
        original flagged run, exactly as it would before any recovery attempt --
        this reproduces the real Development Backlog #135 shape."""
        durable_path = self.durable_record_path()
        durable_path.parent.mkdir(parents=True, exist_ok=True)
        durable_path.write_text(self.record_path().read_text(encoding="utf-8"), encoding="utf-8")

    def test_recovery_mirrors_into_the_durable_integration_root_record(self) -> None:
        self.write_flagged_execution()
        self.write_durable_flagged_execution()
        self.write_friction_event()

        recovery = self.recover()
        self.assertEqual(recovery["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)

        durable_payload = json.loads(self.durable_record_path().read_text(encoding="utf-8"))
        durable_execution = durable_payload["execution"]
        self.assertEqual(durable_execution["recovery"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        # The original flagged execution facts are preserved in the durable copy too.
        self.assertTrue(durable_execution["violation"])
        self.assertEqual(durable_execution["returncode"], 0)
        self.assertEqual(durable_execution["outcome"], "failed")

        # A repeat recovery attempt is still refused as already-recovered.
        with self.assertRaisesRegex(routing.RoutingError, "already has a recorded recovery"):
            self.recover()

        # Prove the terminal gate reads the durable copy specifically -- not merely
        # falling back to a task-local copy that happens to also carry the recovery --
        # by reverting the task-local file to its pre-recovery state first. The
        # durable payload minus "recovery" is exactly the original flagged execution
        # recorded before this test's recovery ran.
        original_execution = {k: v for k, v in durable_execution.items() if k != "recovery"}
        task_payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        task_payload["execution"] = original_execution
        self.record_path().write_text(json.dumps(task_payload, indent=2, sort_keys=True), encoding="utf-8")
        with patch.object(routing, "main_root", return_value=self.integration):
            gate_route = routing.require_routing_gate(self.task, "owner/backlog#135", "recovery-change")
        self.assertEqual(
            gate_route.execution["recovery"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE
        )

    def test_recovery_refuses_closed_when_durable_persistence_fails(self) -> None:
        self.write_flagged_execution()
        self.write_friction_event()
        original_task_payload = self.record_path().read_text(encoding="utf-8")
        with patch.object(routing, "_persist_completed_execution", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(routing.RoutingError, "durable integration-root routing record"):
                self.recover()
        # Neither copy shows a false success: task-local is byte-for-byte unchanged,
        # and no durable copy was ever created.
        self.assertEqual(self.record_path().read_text(encoding="utf-8"), original_task_payload)
        self.assertFalse(self.durable_record_path().exists())
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "requires a clean successful native Codex executor launch"):
                routing.require_routing_gate(self.task, "owner/backlog#135", "recovery-change")


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

    def test_self_reported_claude_records_are_not_launched_in_calibration(self) -> None:
        codex_record = self.seed("codex-real", outcome="completed")
        claude_claimed = self.seed("claude-claimed", provider="claude", launched=False, outcome=None)
        claude_claimed["execution"] = {
            "outcome": "claimed", "launch_evidence": "self-reported", "launched": None,
            "claimed_agent_id": "agent-abc123",
        }
        claude_legacy = self.seed("claude-legacy", provider="claude", launched=False, outcome=None)
        claude_legacy["execution"] = {"launched": True, "agent_id": "x"}
        report = self.run_report([codex_record, claude_claimed, claude_legacy])
        self.assertEqual(report["sample"]["launched_executions"], 1)
        self.assertEqual(report["sample"]["planned_only_routes"], 2)
        self.assertEqual(
            routing._execution_outcome_label(claude_claimed), "claimed"
        )
        self.assertEqual(
            routing._execution_outcome_label(claude_legacy), "claimed"
        )

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


dogfood_task = load("dogfood_task_early_gate", "../../scripts/dogfood_task.py")

DETECTION_ONLY = guard.EnforcementDecision(guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox")


class EarlyRoutingGateTests(unittest.TestCase):
    """Execution plan, delegation lifecycle and the early gate (early-routing-gate)."""

    setUp = ModelRoutingTests.setUp
    tearDown = ModelRoutingTests.tearDown
    prepare = ModelRoutingTests.prepare
    record_path = ModelRoutingTests.record_path
    durable_record_path = ModelRoutingTests.durable_record_path

    def handoff(self, profile: str = "standard"):
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            return routing.prepare_claude_handoff(self.task, profile=profile, rationale="bounded current-spec preflight", evidence=["openspec/changes/routing-change"])

    def gate(self):
        return routing.require_early_routing_gate(self.task)

    def archive_gate(self):
        with patch.object(routing, "main_root", return_value=self.integration):
            return routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")

    def write_content(self, name: str = "implemented.txt") -> None:
        (self.task / name).write_text("task content\n", encoding="utf-8")

    def plan(self) -> dict:
        return json.loads(self.record_path().read_text(encoding="utf-8"))["execution_plan"]

    def fake_codex(self, outcome: str, *, write: str | None = None):
        def run(route, prompt, codex_bin=None, *, launch_hook):
            launch_hook()
            if write:
                self.write_content(write)
            return {"outcome": outcome, "launched": True, "returncode": 0 if outcome == "completed" else 1, "violation": False, "writer_state": "released"}

        return patch.object(routing, "run_codex", side_effect=run)

    # --- 1. execution plan and pre-snapshot

    def test_policy_requiring_child_records_delegated_plan_separate_from_tier_and_execution(self) -> None:
        self.write_routing_receipt("R2")
        with patch.object(routing, "main_root", return_value=self.integration):
            route = routing.prepare(self.task, provider="codex", profile=None, rationale="freshness check: no new trigger", evidence=[])
        self.assertEqual(route.execution_plan["mode"], routing.PLAN_DELEGATED)
        self.assertNotIn("policy", route.execution_plan)
        self.assertIsNone(route.execution_plan["delegation"])
        self.assertEqual(route.execution_plan["task_content_pre"]["paths"], {})
        self.assertEqual(route.execution_plan["task_content_pre"]["committed"], {})
        self.assertEqual(route.start_tier, "R2")
        self.assertIsNone(route.execution)
        self.assertEqual(self.plan()["mode"], "delegated-child")

    write_routing_receipt = ModelRoutingTests.write_routing_receipt

    def test_complex_route_records_supervisor_retained_plan_with_policy(self) -> None:
        route = self.prepare(profile="complex")
        self.assertEqual(route.execution_plan["mode"], routing.PLAN_RETAINED)
        self.assertEqual(route.execution_plan["policy"], "complex-parent")
        self.assertIsNone(route.execution_plan["delegation"])
        self.assertIsNone(route.execution)
        self.assertEqual(route.escalations, ())

    def test_prepare_refuses_pre_diverged_content_and_records_no_route(self) -> None:
        self.write_content("early.txt")
        (self.task / "tracked-later.txt").write_text("x\n", encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, r"routing must precede task content.*early\.txt"):
            self.prepare()
        self.assertFalse(self.record_path().exists())

    def test_prepare_refuses_committed_content_ahead_of_base(self) -> None:
        self.write_content("committed.txt")
        git(self.task, "add", "committed.txt")
        git(self.task, "commit", "-qm", "supervisor wrote first")
        with self.assertRaisesRegex(routing.RoutingError, r"committed\.txt"):
            self.prepare()
        self.assertFalse(self.record_path().exists())

    def test_lifecycle_allow_list_is_not_task_content(self) -> None:
        (self.task / ".managed-task-state.json").write_text("{}", encoding="utf-8")
        context = self.task / ".claude" / "requirement-child-context"
        context.mkdir(parents=True)
        (context / "routing-change.json").write_text("{}", encoding="utf-8")
        package = self.task / "openspec" / "changes" / "routing-change"
        (package / "tasks.md").write_text("- [x] 1\n", encoding="utf-8")
        (package / "verification.md").write_text("receipt\n", encoding="utf-8")
        (package / "specs").mkdir()
        (package / "specs" / "spec.md").write_text("spec\n", encoding="utf-8")
        route = self.prepare()
        self.assertEqual(route.execution_plan["task_content_pre"]["paths"], {})
        self.assertEqual(routing._task_content_diverged(route), [])
        self.write_content()
        self.assertEqual(routing._task_content_diverged(route), ["implemented.txt"])

    def test_invalid_plan_fails_naming_the_field(self) -> None:
        self.prepare()
        payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        payload["execution_plan"]["mode"] = "whatever"
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "execution_plan.mode"):
            routing._read_route(self.task)
        del payload["execution_plan"]["task_content_pre"]
        payload["execution_plan"]["mode"] = "delegated-child"
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "task_content_pre"):
            routing._read_route(self.task)

    # --- 2/4.1 delegated Claude path

    def test_delegated_claude_path_passes_early_and_archive_gates(self) -> None:
        result = self.handoff()
        self.assertEqual(result["delegated"], "pending_begin_delegation")
        self.assertEqual(result["route"]["execution_plan"]["mode"], "delegated-child")
        self.gate()
        delegation = routing.begin_claude_delegation(self.task)
        self.assertEqual(delegation["state"], "open")
        self.assertEqual(delegation["launch_evidence"], "self-reported")
        self.write_content()
        self.gate()  # child content under an open delegation
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            execution = routing.record_claude_execution(self.task, agent_id="agent-1", summary="child work")
        self.assertIsNone(execution["launched"])
        self.assertEqual(execution["outcome"], "claimed")
        plan = self.plan()
        self.assertEqual(plan["delegation"]["state"], "closed")
        self.assertEqual(plan["delegation"]["launch_evidence"], "self-reported")
        self.assertIn("implemented.txt", plan["delegation"]["task_content_post"]["paths"])
        self.gate()
        self.assertEqual(self.archive_gate().change, "routing-change")

    def test_begin_refused_for_retained_plan_and_for_an_already_recorded_delegation(self) -> None:
        self.handoff(profile="complex")
        with self.assertRaisesRegex(routing.RoutingError, "supervisor-retained"):
            routing.begin_claude_delegation(self.task)
        self.handoff()
        routing.begin_claude_delegation(self.task)
        with self.assertRaisesRegex(routing.RoutingError, "already recorded"):
            routing.begin_claude_delegation(self.task)

    def test_begin_refuses_non_claude_route(self) -> None:
        self.prepare(provider="codex")
        with self.assertRaisesRegex(routing.RoutingError, "not a Claude route"):
            routing.begin_claude_delegation(self.task)

    # --- 4.3 early block

    def test_supervisor_content_under_delegated_plan_blocks_every_routing_adjacent_command(self) -> None:
        self.handoff()
        self.write_content()
        with self.assertRaisesRegex(routing.RoutingError, r"implemented\.txt.*begin-claude-delegation"):
            self.gate()
        # lifecycle status / finish
        for command in (dogfood_task.status, dogfood_task.finish):
            with (
                patch.object(dogfood_task, "current_root", return_value=self.task),
                patch.object(dogfood_task, "verify_source_contract"),
                patch.object(dogfood_task, "run") as run,
            ):
                with self.assertRaisesRegex(SystemExit, "Early routing gate blocked"):
                    command(SimpleNamespace(json=False, title=None, body=None))
            run.assert_not_called()
        # check/test entrypoint: fails before any group executes
        groups = {"g": {"targets": ["test_x"], "mode": "serial"}}
        # A private, unregistered instance: registering "run_test_groups" here would
        # substitute the instance tests/test_run_test_groups.py holds.
        spec = importlib.util.spec_from_file_location("_early_gate_run_test_groups", SCRIPTS / "run_test_groups.py")
        assert spec and spec.loader
        run_test_groups = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_test_groups)
        with (
            patch.object(run_test_groups, "current_worktree_root", return_value=self.task),
            patch.object(run_test_groups, "load_check_config", return_value={}),
            patch.object(run_test_groups, "read_groups", return_value=groups),
            patch.object(run_test_groups, "execute") as execute,
            patch.object(sys, "argv", ["run_test_groups.py", "--group", "g"]),
        ):
            self.assertEqual(run_test_groups.main(), 2)
        execute.assert_not_called()
        # verify-routing for the active change
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "model_routing.py"), "verify-routing", "--source-issue", "owner/backlog#7", "--change", "routing-change"],
            cwd=self.task, text=True, capture_output=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("no delegation is open", completed.stderr)

    def test_record_after_the_fact_and_late_begin_are_refused(self) -> None:
        self.handoff()
        self.write_content()
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            with self.assertRaisesRegex(routing.RoutingError, "requires an open delegation.*begin-claude-delegation"):
                routing.record_claude_execution(self.task, agent_id="agent-late")
        with self.assertRaisesRegex(routing.RoutingError, "after task content diverged"):
            routing.begin_claude_delegation(self.task)
        self.assertIsNone(self.plan()["delegation"])
        self.assertIsNone(routing._read_route(self.task)[0].execution)

    def test_early_gate_requires_route_before_content_and_is_silent_on_clean_unrouted_task(self) -> None:
        self.gate()
        self.write_content()
        with self.assertRaisesRegex(routing.RoutingError, "route before task content"):
            self.gate()

    def test_early_gate_is_not_applicable_without_managed_state(self) -> None:
        shutil.rmtree(self.task / "openspec")
        self.assertIsNone(routing.require_early_routing_gate(self.task))

    # --- 4.2 retained

    def test_complex_retained_plan_declared_up_front_then_finalized(self) -> None:
        self.prepare(profile="complex")
        self.write_content()
        self.gate()
        with patch.object(routing, "main_root", return_value=self.integration):
            execution = routing.record_retained_execution(self.task, reason="R3 work completed by the current supervisor")
        self.assertEqual(execution["outcome"], "retained")
        self.assertIs(execution["launched"], False)
        self.gate()
        self.assertEqual(self.archive_gate().execution["retained"]["policy"], "complex-parent")

    def test_retained_recording_refused_without_up_front_plan_and_never_converts_plan(self) -> None:
        self.prepare(profile="standard")
        self.write_content()
        with patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaisesRegex(routing.RoutingError, "declared up front"):
                routing.record_retained_execution(self.task, reason="late retention")
        self.assertEqual(self.plan()["mode"], "delegated-child")
        self.assertIsNone(routing._read_route(self.task)[0].execution)

    # --- 4.4 recovery

    def test_escalation_without_delegation_on_diverged_content_is_refused(self) -> None:
        self.prepare()
        self.write_content()
        with self.assertRaisesRegex(routing.RoutingError, "no delegation was ever opened.*invented"):
            routing.escalate(self.task, "invented trigger after supervisor work")
        self.assertEqual(routing._read_route(self.task)[0].profile, "standard")
        self.assertEqual(self.plan()["mode"], "delegated-child")

    def test_escalation_with_unchanged_content_switches_plan_to_retention(self) -> None:
        self.prepare()
        route = routing.escalate(self.task, "new unresolved architecture trigger found before any write")
        self.assertEqual(route.execution_plan["mode"], routing.PLAN_RETAINED)
        self.assertEqual(route.execution_plan["policy"], "complex-parent")
        self.assertFalse(route.execution_plan["switched_from"]["delegation_recorded"])

    def test_escalation_after_real_delegation_keeps_delegation_and_escalation_distinct(self) -> None:
        self.handoff()
        routing.begin_claude_delegation(self.task)
        self.write_content()
        route = routing.escalate(self.task, "child hit a material cross-cutting contract conflict; reviewed")
        plan = route.execution_plan
        self.assertEqual(plan["mode"], routing.PLAN_RETAINED)
        self.assertEqual(plan["delegation"]["state"], "open")
        self.assertEqual(plan["delegation"]["launch_evidence"], "self-reported")
        self.assertTrue(plan["switched_from"]["delegation_recorded"])
        self.assertEqual(len(route.escalations), 1)
        self.assertIsNone(route.execution)
        self.gate()

    def test_no_path_writes_a_launch_claim_without_a_delegation(self) -> None:
        self.handoff()
        self.write_content()
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            with self.assertRaises(routing.RoutingError):
                routing.record_claude_execution(self.task, agent_id="agent-x")
            with self.assertRaises(routing.RoutingError):
                routing.record_retained_execution(self.task, reason="late")
        saved = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIsNone(saved["execution"])
        self.assertIsNone(saved["execution_plan"]["delegation"])
        self.assertEqual(saved["escalations"], [])

    # --- 4.5a re-route after a failed platform-observed Codex delegation

    def test_reroute_permitted_after_failed_platform_observed_codex_with_unchanged_post_content(self) -> None:
        for outcome in ("failed", "abnormal"):
            with self.subTest(outcome=outcome):
                with self.fake_codex(outcome, write=f"partial-{outcome}.txt"), patch.object(routing, "main_root", return_value=self.integration):
                    with self.assertRaisesRegex(routing.RoutingError, "did not complete cleanly"):
                        routing.dispatch_codex(self.task, profile="standard", rationale="bounded preflight", evidence=[], prompt="implement")
                    delegation = self.plan()["delegation"]
                    self.assertEqual(delegation["launch_evidence"], "platform-observed")
                    self.assertEqual(delegation["outcome"], outcome)
                    rerouted = routing.prepare(self.task, provider="codex", profile="standard", rationale="re-route after failed child", evidence=[])
                self.assertEqual(rerouted.execution_plan["rerouted_from"]["outcome"], outcome)
                self.assertIsNone(rerouted.execution_plan["delegation"])
                self.assertIn(f"partial-{outcome}.txt", rerouted.execution_plan["task_content_pre"]["paths"])
                self.assertEqual(routing._task_content_diverged(rerouted), [])
                (self.task / f"partial-{outcome}.txt").unlink()

    def test_recovery_refuses_unresolved_containment_and_writer(self) -> None:
        with self.fake_codex("failed", write="partial.txt"), patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaises(routing.RoutingError):
                routing.dispatch_codex(self.task, profile="standard", rationale="preflight", evidence=[], prompt="implement")
            original = self.record_path().read_text()
            for field, value, diagnostic in (("violation", True, "containment violation"), ("writer_state", "ambiguous", "released Codex writer")):
                with self.subTest(field=field):
                    payload = json.loads(original)
                    payload["execution"][field] = value
                    self.record_path().write_text(json.dumps(payload))
                    before = self.record_path().read_text()
                    with self.assertRaisesRegex(routing.RoutingError, diagnostic):
                        routing.prepare(self.task, provider="codex", profile="complex", rationale="reviewed failure", evidence=[])
                    with self.assertRaisesRegex(routing.RoutingError, diagnostic):
                        routing.escalate(self.task, "reviewed child failure")
                    self.assertEqual(self.record_path().read_text(), before)
            self.record_path().write_text(original)
            escaped = self.integration / "escaped.txt"
            escaped.write_text("escaped child writes")
            with self.assertRaises(routing.RoutingError):
                routing.prepare(self.task, provider="codex", profile="complex", rationale="reviewed failure", evidence=[])

    def test_escalated_failed_child_finalizes_retention_preserving_provenance(self) -> None:
        with self.fake_codex("failed", write="partial.txt"), patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaises(routing.RoutingError):
                routing.dispatch_codex(self.task, profile="standard", rationale="preflight", evidence=[], prompt="implement")
            prior, _ = routing._read_route(self.task)
            escalated = routing.escalate(self.task, "reviewed child failure needs architecture decision")
            self.write_content("supervisor-completion.txt")
            execution = routing.record_retained_execution(self.task, reason="completed after reviewed escalation")
            self.assertEqual(execution["prior_execution"], prior.execution)
            final = self.archive_gate()
            self.assertEqual(final.execution_plan["delegation"], prior.execution_plan["delegation"])
            self.assertEqual(final.escalations, escalated.escalations)
            with self.assertRaises(routing.RoutingError):
                routing.record_retained_execution(self.task, reason="duplicate")

    def test_retained_finalization_rechecks_original_child_safety(self) -> None:
        with self.fake_codex("failed", write="partial.txt"), patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaises(routing.RoutingError):
                routing.dispatch_codex(self.task, profile="standard", rationale="preflight", evidence=[], prompt="implement")
            routing.escalate(self.task, "reviewed child failure")
            original = self.record_path().read_text()
            for field, value in (("violation", True), ("writer_state", "ambiguous")):
                payload = json.loads(original)
                payload["execution"][field] = value
                self.record_path().write_text(json.dumps(payload))
                with self.assertRaises(routing.RoutingError):
                    routing.record_retained_execution(self.task, reason="supervisor completion")
            self.record_path().write_text(original)
            (self.integration / "escaped.txt").write_text("escaped writes")
            with self.assertRaises(routing.RoutingError):
                routing.record_retained_execution(self.task, reason="supervisor completion")

    def test_reroute_refused_when_content_changed_after_the_failed_child(self) -> None:
        with self.fake_codex("failed", write="partial.txt"), patch.object(routing, "main_root", return_value=self.integration):
            with self.assertRaises(routing.RoutingError):
                routing.dispatch_codex(self.task, profile="standard", rationale="bounded preflight", evidence=[], prompt="implement")
            self.write_content("supervisor-after.txt")
            with self.assertRaisesRegex(routing.RoutingError, r"routing must precede task content.*supervisor-after\.txt"):
                routing.prepare(self.task, provider="codex", profile="standard", rationale="re-route", evidence=[])

    def test_reroute_refused_after_completed_codex_or_self_reported_claude_delegation(self) -> None:
        with self.fake_codex("completed", write="done.txt"), patch.object(routing, "main_root", return_value=self.integration):
            routing.dispatch_codex(self.task, profile="standard", rationale="bounded preflight", evidence=[], prompt="implement")
            with self.assertRaisesRegex(routing.RoutingError, "routing must precede task content"):
                routing.prepare(self.task, provider="codex", profile="standard", rationale="re-route", evidence=[])
        (self.task / "done.txt").unlink()
        self.record_path().unlink()
        self.durable_record_path().unlink()
        self.handoff()
        routing.begin_claude_delegation(self.task)
        self.write_content()
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(routing, "determine_claude_tier", return_value=DETECTION_ONLY):
            routing.record_claude_execution(self.task, agent_id="agent-1")
            with self.assertRaisesRegex(routing.RoutingError, "routing must precede task content"):
                routing.prepare(self.task, provider="claude", profile="standard", rationale="re-route", evidence=[])

    def test_reroute_refused_after_codex_failure_with_claude_provider_record(self) -> None:
        # A self-reported Claude delegation never qualifies even if its record later reads as a failure.
        self.handoff()
        routing.begin_claude_delegation(self.task)
        self.write_content()
        payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        payload["execution"] = {"outcome": "failed"}
        payload["execution_plan"]["delegation"].update({"state": "closed", "outcome": "failed", "task_content_post": routing._task_content_state(self.task, "routing-change")})
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "routing must precede task content"):
            self.prepare(provider="claude")

    # --- 4.5 Codex consistency and legacy records

    def test_codex_preflight_failure_cannot_authorize_supervisor_work(self) -> None:
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(
            routing, "determine_codex_tier", return_value=DETECTION_ONLY
        ), patch.object(routing, "run_observed_delegation") as launch:
            with self.assertRaisesRegex(routing.RoutingError, "containment is not provable"):
                routing.dispatch_codex(self.task, profile="standard", rationale="bounded preflight", evidence=[], prompt="implement")
        launch.assert_not_called()
        self.assertEqual(self.plan()["delegation"]["outcome"], "not-launched")
        route, _ = routing._read_route(self.task)
        self.assertIsNone(route.execution)
        self.write_content()
        with self.assertRaisesRegex(routing.RoutingError, "supervisor-written"):
            self.gate()
        with self.assertRaisesRegex(routing.RoutingError, "refusing to escalate"):
            routing.escalate(self.task, "preflight failed")
        with self.assertRaises(routing.RoutingError):
            routing.record_retained_execution(self.task, reason="supervisor completed work")

    def test_unlaunched_codex_delegation_survives_preflight(self) -> None:
        for error in (routing.ContainmentError("ownership refused"), routing.RoutingError("login refused"), OSError("spawn failed")):
            with self.subTest(error=error):
                route = self.prepare()
                with patch.object(routing, "run_codex", side_effect=error):
                    with self.assertRaises(type(error)):
                        routing._run_delegated_codex(self.task, route, "implement", None)
                self.assertEqual(self.plan()["delegation"]["outcome"], "not-launched")
                self.assertNotIn("opened_at", self.plan()["delegation"])
        self.write_content()
        with self.assertRaises(routing.RoutingError):
            self.gate()
        with self.assertRaises(routing.RoutingError):
            routing.escalate(self.task, "failed preflight")
        with self.assertRaises(routing.RoutingError):
            routing.record_retained_execution(self.task, reason="finished")

    def test_unlaunched_codex_attempt_bypasses_early_gate(self) -> None:
        route = self.prepare()
        with patch.object(routing, "run_codex", return_value={"launched": False, "outcome": "abnormal"}):
            routing._run_delegated_codex(self.task, route, "implement", None)
        self.assertEqual(self.plan()["delegation"]["outcome"], "not-launched")
        self.write_content()
        with self.assertRaises(routing.RoutingError):
            self.gate()
        with self.assertRaises(routing.RoutingError):
            routing.escalate(self.task, "spawn failed")
        with self.assertRaises(routing.RoutingError):
            routing.record_retained_execution(self.task, reason="finished")

    def test_lifecycle_renames_hide_source_deletions(self) -> None:
        source = self.task / "tool.py"
        source.write_text("implementation\n", encoding="utf-8")
        git(self.task, "add", "tool.py")
        git(self.task, "commit", "-m", "baseline source")
        git(self.task, "update-ref", "refs/remotes/origin/main", "HEAD")
        for destination in (".claude/tool.py", "openspec/changes/routing-change/tool.py"):
            with self.subTest(destination=destination):
                self.handoff()
                target = self.task / destination
                target.parent.mkdir(parents=True, exist_ok=True)
                git(self.task, "mv", "tool.py", destination)
                route, _ = routing._read_route(self.task)
                self.assertIn("tool.py", routing._task_content_diverged(route))
                with self.assertRaises(routing.RoutingError):
                    self.gate()
                with self.assertRaises(routing.RoutingError):
                    routing.begin_claude_delegation(self.task)
                with self.assertRaises(routing.RoutingError):
                    routing.escalate(self.task, "late")
                with self.assertRaises(routing.RoutingError):
                    self.prepare()
                git(self.task, "commit", "-m", "move into lifecycle")
                self.assertIn("tool.py", routing._task_content_diverged(route))
                for operation in (self.gate, lambda: routing.begin_claude_delegation(self.task), lambda: routing.escalate(self.task, "committed late move"), self.prepare):
                    with self.assertRaises(routing.RoutingError):
                        operation()
                git(self.task, "mv", destination, "tool.py")
                git(self.task, "commit", "-m", "restore source")

    def test_codex_dispatch_records_plan_and_platform_observed_delegation(self) -> None:
        with self.fake_codex("completed", write="codex-work.txt"), patch.object(routing, "main_root", return_value=self.integration):
            result = routing.dispatch_codex(self.task, profile="standard", rationale="bounded preflight", evidence=[], prompt="implement")
        plan = result["route"]["execution_plan"]
        self.assertEqual(plan["mode"], "delegated-child")
        self.assertEqual(plan["delegation"]["state"], "closed")
        self.assertEqual(plan["delegation"]["launch_evidence"], "platform-observed")
        self.assertEqual(plan["delegation"]["provider"], "codex")
        self.assertEqual(plan["delegation"]["outcome"], "completed")
        self.assertTrue(result["execution"]["launched"])
        self.gate()
        self.archive_gate()

    def test_codex_dispatch_complex_declares_retention_and_launches_nothing(self) -> None:
        with patch.object(routing, "run_codex") as run, patch.object(routing, "main_root", return_value=self.integration):
            result = routing.dispatch_codex(self.task, profile="complex", rationale="strong trigger", evidence=[], prompt="unused")
        run.assert_not_called()
        self.assertEqual(result["route"]["execution_plan"]["mode"], "supervisor-retained")

    def test_codex_launch_refused_under_retained_plan_or_after_divergence(self) -> None:
        route = self.prepare(profile="complex")
        with self.assertRaisesRegex(routing.RoutingError, "cannot be launched under it"):
            routing._run_delegated_codex(self.task, route, "x", None)
        self.prepare(profile="standard")
        self.write_content()
        route, _ = routing._read_route(self.task)
        with self.assertRaisesRegex(routing.RoutingError, "after task content diverged"):
            routing._run_delegated_codex(self.task, route, "x", None)

    def test_legacy_plan_less_record_is_handled_explicitly(self) -> None:
        self.prepare()
        payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        del payload["execution_plan"]
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "re-route required"):
            self.gate()
        with self.assertRaisesRegex(routing.RoutingError, "no execution plan"):
            routing.escalate(self.task, "x reason")
        # with a final execution outcome the existing archive semantics are kept
        payload["execution"] = {"outcome": "completed", "launched": True, "returncode": 0, "violation": False}
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(self.gate().change, "routing-change")

    def test_legacy_plan_less_record_cannot_be_rerouted_over_diverged_content(self) -> None:
        self.prepare()
        payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        del payload["execution_plan"]
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        self.write_content()
        with self.assertRaisesRegex(routing.RoutingError, "routing must precede task content.*cannot be legalized"):
            self.prepare()

    def test_cli_begin_claude_delegation_opens_delegation(self) -> None:
        self.handoff()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "model_routing.py"), "begin-claude-delegation"], cwd=self.task, text=True, capture_output=True
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["launch_evidence"], "self-reported")
        self.assertEqual(self.plan()["delegation"]["state"], "open")


class EarlyRoutingGateTemplateParityTests(unittest.TestCase):
    """The template scripts alone (as rendered into a downstream project) enforce the early gate."""

    def test_rendered_scripts_directory_enforces_the_early_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            git(project, "init", "-q", "-b", "main")
            git(project, "config", "user.email", "routing@example.test")
            git(project, "config", "user.name", "Routing Test")
            shutil.copytree(SCRIPTS, project / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.jinja"))
            (project / ".gitignore").write_text(".claude/\n.managed-task-state.json\n__pycache__/\n", encoding="utf-8")
            (project / ".dev-platform.toml").write_text('workflow_profile = "multi-agent"\nmain_branch = "main"\n', encoding="utf-8")
            git(project, "add", "-A")
            git(project, "commit", "-qm", "rendered project")
            git(project, "update-ref", "refs/remotes/origin/main", "main")
            task = Path(tmp) / "task"
            git(project, "worktree", "add", "-qb", "agent/parity", str(task), "main")
            change = task / "openspec" / "changes" / "parity-change"
            change.mkdir(parents=True)
            (change / ".managed-task.json").write_text(json.dumps({"source_issue": "owner/backlog#9", "change": "parity-change"}), encoding="utf-8")

            def run(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, "scripts/model_routing.py", *args], cwd=task, text=True, capture_output=True)

            routed = run("prepare", "--provider", "claude", "--profile", "standard", "--rationale", "parity preflight")
            self.assertEqual(routed.returncode, 0, routed.stderr)
            self.assertEqual(json.loads(routed.stdout)["execution_plan"]["mode"], "delegated-child")
            verify = ("verify-routing", "--source-issue", "owner/backlog#9", "--change", "parity-change")
            self.assertNotIn("no delegation is open", run(*verify).stderr)
            (task / "supervisor.txt").write_text("written by the supervisor\n", encoding="utf-8")
            blocked = run(*verify)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("supervisor.txt", blocked.stderr)
            self.assertIn("no delegation is open", blocked.stderr)
            late = run("begin-claude-delegation")
            self.assertEqual(late.returncode, 2)
            self.assertIn("after task content diverged", late.stderr)


if __name__ == "__main__":
    unittest.main()
