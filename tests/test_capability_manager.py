from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("capability_manager", ROOT / "template" / "scripts" / "capability_manager.py")
assert SPEC and SPEC.loader
manager = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manager
SPEC.loader.exec_module(manager)

EVAL_SPEC = importlib.util.spec_from_file_location("capability_evals", ROOT / "template" / "scripts" / "capability_evals.py")
assert EVAL_SPEC and EVAL_SPEC.loader
evals = importlib.util.module_from_spec(EVAL_SPEC)
sys.modules[EVAL_SPEC.name] = evals
EVAL_SPEC.loader.exec_module(evals)


class CapabilityManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "dev-platform" / "capabilities").mkdir(parents=True)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "capability_manager.py").write_text("# isolated adapter fixture\n", encoding="utf-8")
        (self.root / "dev-platform" / "evals").mkdir()
        (self.root / ".dev-platform.toml").write_text('agent_tools = "claude,codex"\n', encoding="utf-8")
        shutil.copyfile(ROOT / "dev-platform" / "capabilities.toml", self.root / "dev-platform" / "capabilities.toml")
        for name in (
            "repository-hygiene.toml",
            "repository-hygiene.md",
            "capability-catalog.toml",
            "capability-catalog.md",
            "architecture-health-review.toml",
            "architecture-health-review.md",
            "systematic-bug-diagnosis.toml",
            "systematic-bug-diagnosis.md",
            "selective-domain-interrogation.toml",
            "selective-domain-interrogation.md",
            "interoperable-agent-handoff.toml",
            "interoperable-agent-handoff.md",
            "bounded-prototype.toml",
            "bounded-prototype.md",
            "frontend-design.toml",
            "frontend-design.md",
            "high-end-visual-design.toml",
            "high-end-visual-design.md",
            "react-next-best-practices.toml",
            "react-next-best-practices.md",
            "ui-quality-review.toml",
            "ui-quality-review.md",
        ):
            shutil.copyfile(ROOT / "dev-platform" / "capabilities" / name, self.root / "dev-platform" / "capabilities" / name)
        react_group = self.root / "dev-platform" / "capabilities" / "react-next-best-practices"
        react_group.mkdir()
        for name in (
            "server-client-components.md",
            "data-fetching-and-waterfalls.md",
            "bundle-and-code-splitting.md",
            "rendering-and-re-renders.md",
        ):
            shutil.copyfile(
                ROOT / "dev-platform" / "capabilities" / "react-next-best-practices" / name,
                react_group / name,
            )
        for name in (
            "capability-catalog-pilot.json",
            "architecture-health-review-pilot.json",
            "systematic-bug-diagnosis-pilot.json",
            "selective-domain-interrogation-pilot.json",
            "interoperable-agent-handoff-pilot.json",
            "bounded-prototype-pilot.json",
            "frontend-design-pilot.json",
            "high-end-visual-design-pilot.json",
            "react-next-best-practices-pilot.json",
            "ui-quality-review-pilot.json",
        ):
            shutil.copyfile(ROOT / "dev-platform" / "evals" / name, self.root / "dev-platform" / "evals" / name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def registry(self):
        return manager.load_registry(self.root)

    def test_opt_out_materializes_no_provider_surface(self) -> None:
        result = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(result["changes"], [])
        self.assertFalse((self.root / ".codex").exists())
        self.assertEqual(manager.audit(self.root, self.registry(), []), {"status": "ok", "enabled": [], "issues": [], "unsupported": []})

    def test_enable_sync_audit_and_disable_are_idempotent(self) -> None:
        registry = self.registry()
        manager.write_selection(self.root, ["repository-hygiene"])
        materialized = manager.sync(self.root, registry, manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        codex = self.root / ".codex" / "skills" / "dev-platform-repository-hygiene" / "SKILL.md"
        self.assertIn("dev-platform-capability:id=repository-hygiene", codex.read_text(encoding="utf-8"))
        self.assertEqual(manager.audit(self.root, registry, ["repository-hygiene"])["status"], "ok")
        manager.write_selection(self.root, [])
        removed = manager.sync(self.root, registry, [])
        self.assertEqual(len(removed["changes"]), 2)
        self.assertFalse(codex.exists())
        self.assertEqual(manager.sync(self.root, registry, [])["changes"], [])

    def test_unsupported_invocation_is_reported_without_emulation(self) -> None:
        instruction = self.root / "dev-platform" / "capabilities" / "explicit-only.md"
        instruction.write_text("# Explicit only\n", encoding="utf-8")
        digest = hashlib.sha256(instruction.read_bytes()).hexdigest()
        (self.root / "dev-platform" / "capabilities" / "explicit-only.toml").write_text(
            "[capability]\n"
            'id = "explicit-only"\nname = "Explicit only"\ndescription = "Explicit fixture."\n'
            'kind = "instruction-only"\napplicability = "Fixture"\ninvocation = "explicit-only"\nvisibility = "project"\nowner = "test"\n'
            'safety_boundary = "No authority."\ndependencies = []\nmaterialization = "provider-skill-markdown"\nupdate_policy = "replace-derived"\nremoval_policy = "remove-derived-only"\n\n'
            "[provenance]\n"
            'source = "test"\nrevision = "pinned"\npath = "dev-platform/capabilities/explicit-only.md"\nlicense = "Apache-2.0"\n'
            f'content_sha256 = "{digest}"\n',
            encoding="utf-8",
        )
        registry = self.registry()
        manager.write_selection(self.root, ["explicit-only"])
        result = manager.sync(self.root, registry, ["explicit-only"])
        self.assertEqual({item["provider"] for item in result["unsupported"]}, {"claude", "codex"})
        self.assertFalse((self.root / ".codex").exists())

    def test_unowned_surface_is_never_removed(self) -> None:
        registry = self.registry()
        path = self.root / ".codex" / "skills" / "dev-platform-repository-hygiene" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("user-owned skill\n", encoding="utf-8")
        with self.assertRaisesRegex(manager.CapabilityError, "unowned provider skill"):
            manager.sync(self.root, registry, [])
        self.assertEqual(path.read_text(encoding="utf-8"), "user-owned skill\n")

    def test_tool_backed_fixture_stays_in_development_surface(self) -> None:
        registry = self.registry()
        config_before = (self.root / ".dev-platform.toml").read_text(encoding="utf-8")
        manager.write_selection(self.root, ["capability-catalog"])
        result = manager.sync(self.root, registry, ["capability-catalog"])
        self.assertEqual(result["unsupported"], [])
        self.assertTrue((self.root / ".claude" / "skills" / "dev-platform-capability-catalog" / "SKILL.md").exists())
        self.assertEqual((self.root / ".dev-platform.toml").read_text(encoding="utf-8"), config_before)
        self.assertFalse((self.root / "requirements.txt").exists())

    def test_architecture_health_review_is_revision_bound_read_only_and_has_false_positive_control(self) -> None:
        capability = self.registry()["architecture-health-review"]
        self.assertEqual(capability.kind, "instruction-only")
        self.assertEqual(capability.dependencies, ())
        for required in (
            "full immutable revision",
            "## Observations",
            "## Uncertainty and counter-evidence",
            "## Advisory improvements",
            "at least two materially distinct options",
            "Do not modify repository files",
        ):
            self.assertIn(required, capability.instruction)
        manager.write_selection(self.root, [capability.identifier])
        result = manager.sync(self.root, self.registry(), [capability.identifier])
        self.assertEqual(result["unsupported"], [])
        derived = self.root / ".codex" / "skills" / "dev-platform-architecture-health-review" / "SKILL.md"
        self.assertIn("Do not modify repository files", derived.read_text(encoding="utf-8"))
        report = manager.evaluate_existing(
            capability,
            self.root / "dev-platform" / "evals" / "architecture-health-review-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        result_ids = {item["case_id"] for item in report["results"]}
        self.assertIn("positive-controlled-shallow-smell", result_ids)
        self.assertIn("positive-healthy-control", result_ids)

    def test_hash_tampering_is_rejected_before_materialization(self) -> None:
        instruction = self.root / "dev-platform" / "capabilities" / "repository-hygiene.md"
        instruction.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(manager.CapabilityError, "instruction hash"):
            self.registry()

    def test_eval_decisions_cover_new_material_and_metadata_lifecycle_cases(self) -> None:
        self.assertEqual(manager.eval_decision("new"), {
            "decision": "blocked/unavailable",
            "reason": "material capability change requires live eval, but no supported provider adapter/runtime is available",
        })
        self.assertEqual(manager.eval_decision("trigger"), {
            "decision": "blocked/unavailable",
            "reason": "material capability change requires live eval, but no supported provider adapter/runtime is available",
        })
        self.assertEqual(manager.eval_decision("metadata")["decision"], "skip-with-reason")
        self.assertEqual(manager.eval_decision("material", runtime="fixture")["decision"], "run")

    def test_direct_deterministic_eval_has_positive_negative_and_quality_evidence(self) -> None:
        report = manager.evaluate_existing(
            self.registry()["capability-catalog"],
            self.root / "dev-platform" / "evals" / "capability-catalog-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["adapter"]["runtime"], "deterministic-fixture")
        self.assertEqual(report["candidate"]["content_sha256"], self.registry()["capability-catalog"].provenance["content_sha256"])
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        self.assertNotIn("prompt", report["results"][0])
        self.assertEqual(report["quality_comparisons"][0]["improved"], True)

    def test_unsupported_provider_is_not_counted_as_negative_trigger(self) -> None:
        fixture = evals.load_fixture(self.root / "dev-platform" / "evals" / "capability-catalog-pilot.json")
        report = evals.run_fixture(fixture, runtime="codex", runs=3)
        self.assertEqual(report["adapter"]["status"], "unsupported")
        self.assertEqual(report["summary"]["incomplete"], 20)
        self.assertEqual(report["summary"]["status_distribution"], {"unsupported": 60})
        self.assertTrue(all(result["trigger_rate"] is None for result in report["results"]))

    def test_timeout_remains_incomplete_not_a_negative_trigger(self) -> None:
        fixture = evals.load_fixture(self.root / "dev-platform" / "evals" / "capability-catalog-pilot.json")
        fixture["cases"][0]["samples"] = ["timeout", "timeout", "timeout"]
        report = evals.run_fixture(fixture, runtime="fixture", runs=3)
        self.assertEqual(report["results"][0]["status_distribution"], {"timeout": 3})
        self.assertIsNone(report["results"][0]["trigger_rate"])
        self.assertIsNone(report["results"][0]["passed"])

    def test_frontend_design_capabilities_are_declared_and_opt_in(self) -> None:
        registry = self.registry()
        for identifier in ("frontend-design", "high-end-visual-design"):
            self.assertIn(identifier, registry)
            self.assertEqual(registry[identifier].kind, "instruction-only")
            self.assertEqual(registry[identifier].invocation, "auto+explicit")
        # Not selected by the default project selection file.
        self.assertEqual(manager.load_selection(self.root), [])
        audit = manager.audit(self.root, registry, manager.load_selection(self.root))
        self.assertEqual(audit["status"], "ok")
        self.assertEqual(manager.sync(self.root, registry, [])["changes"], [])

    def test_specialized_profile_declares_general_dependency_and_records_provenance(self) -> None:
        registry = self.registry()
        specialized = registry["high-end-visual-design"]
        self.assertIn("dev-platform/capabilities/frontend-design.toml", specialized.dependencies)
        self.assertEqual(specialized.provenance["license"], "MIT")
        self.assertEqual(registry["frontend-design"].provenance["license"], "Apache-2.0")
        # Both provenance revisions are pinned, not a mutable branch name.
        for identifier in ("frontend-design", "high-end-visual-design"):
            self.assertRegex(registry[identifier].provenance["revision"], r"^[0-9a-f]{40}$")

    def test_high_end_profile_only_materializes_when_a_project_opts_in(self) -> None:
        registry = self.registry()
        manager.write_selection(self.root, ["high-end-visual-design"])
        result = manager.sync(self.root, registry, manager.load_selection(self.root))
        self.assertEqual(result["unsupported"], [])
        self.assertEqual(len(result["changes"]), 2)
        self.assertEqual(manager.audit(self.root, registry, ["high-end-visual-design"])["status"], "ok")
        for provider in ("claude", "codex"):
            self.assertTrue(
                (self.root / f".{provider}" / "skills" / "dev-platform-high-end-visual-design" / "SKILL.md").exists()
            )
        manager.write_selection(self.root, [])
        removed = manager.sync(self.root, registry, [])
        self.assertEqual(len(removed["changes"]), 2)
        for provider in ("claude", "codex"):
            self.assertFalse(
                (self.root / f".{provider}" / "skills" / "dev-platform-high-end-visual-design" / "SKILL.md").exists()
            )
        self.assertEqual(manager.sync(self.root, registry, [])["changes"], [])

    def test_frontend_design_pilots_have_positive_and_control_evidence(self) -> None:
        registry = self.registry()
        for identifier, triggered, not_triggered in (
            ("frontend-design", 30, 30),
            ("high-end-visual-design", 18, 24),
        ):
            report = manager.evaluate_existing(
                registry[identifier],
                self.root / "dev-platform" / "evals" / f"{identifier}-pilot.json",
                runtime="fixture",
                runs=3,
            )
            self.assertEqual(report["summary"]["failed"], 0)
            self.assertEqual(report["summary"]["incomplete"], 0)
            self.assertEqual(
                report["summary"]["status_distribution"],
                {"triggered": triggered, "not-triggered": not_triggered},
            )
            self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))

    def test_systematic_diagnosis_records_evidence_without_forcing_quick_corrections(self) -> None:
        capability = self.registry()["systematic-bug-diagnosis"]
        self.assertEqual(capability.kind, "instruction-only")
        self.assertEqual(capability.invocation, "auto+explicit")
        manager.write_selection(self.root, [capability.identifier])
        materialized = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        self.assertIn(
            "dev-platform-capability:id=systematic-bug-diagnosis",
            (self.root / ".codex" / "skills" / "dev-platform-systematic-bug-diagnosis" / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(manager.audit(self.root, self.registry(), manager.load_selection(self.root))["status"], "ok")
        for required in (
            "unknown** defect",
            "report the diagnosis as **unconfirmed**",
            "Hypothesis | A concise possible cause.",
            "test would be disproportionate",
            "Re-run the original failure condition",
            "does not create a parallel bug tracker or hidden-reasoning log",
            "rejects a suspected timeout",
        ):
            with self.subTest(required=required):
                self.assertIn(required, capability.instruction)
        report = manager.evaluate_existing(
            capability,
            self.root / "dev-platform" / "evals" / "systematic-bug-diagnosis-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))

    def test_selective_domain_interrogation_is_evidence_first_and_optional(self) -> None:
        capability = self.registry()["selective-domain-interrogation"]
        self.assertEqual(capability.kind, "instruction-only")
        self.assertEqual(capability.invocation, "auto+explicit")
        manager.write_selection(self.root, [capability.identifier])
        materialized = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        self.assertIn(
            "dev-platform-capability:id=selective-domain-interrogation",
            (self.root / ".claude" / "skills" / "dev-platform-selective-domain-interrogation" / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(manager.audit(self.root, self.registry(), manager.load_selection(self.root))["status"], "ok")
        for required in (
            "materially ambiguous",
            "grill-with-docs` pattern informs this approach; it is a reference",
            "A clear task does not get an interrogation ceremony.",
            "Do not turn it into a user question.",
            "invent new product requirements",
            "Do not create a `CONTEXT.md`, an ADR ledger",
            "remains the single canonical implementation contract",
        ):
            with self.subTest(required=required):
                self.assertIn(required, capability.instruction)
        report = manager.evaluate_existing(
            capability,
            self.root / "dev-platform" / "evals" / "selective-domain-interrogation-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))

    def test_bounded_prototype_is_isolated_optional_and_non_promoting(self) -> None:
        capability = self.registry()["bounded-prototype"]
        self.assertEqual(capability.kind, "instruction-only")
        self.assertEqual(capability.invocation, "auto+explicit")
        self.assertEqual(capability.dependencies, ())
        manager.write_selection(self.root, [capability.identifier])
        materialized = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        self.assertIn(
            "dev-platform-capability:id=bounded-prototype",
            (self.root / ".claude" / "skills" / "dev-platform-bounded-prototype" / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(manager.audit(self.root, self.registry(), manager.load_selection(self.root))["status"], "ok")
        for required in (
            "**observable experiment** would resolve faster than more",
            "clear task gets no prototype ceremony.",
            "temporary throwaway workspace",
            "refuse and report the boundary",
            "Prototype code is disposable.",
            "not a starting commit",
            "second backlog",
        ):
            with self.subTest(required=required):
                self.assertIn(required, capability.instruction)
        report = manager.evaluate_existing(
            capability,
            self.root / "dev-platform" / "evals" / "bounded-prototype-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))

    def test_interoperable_agent_handoff_is_navigation_only_and_optional(self) -> None:
        capability = self.registry()["interoperable-agent-handoff"]
        self.assertEqual(capability.kind, "instruction-only")
        self.assertEqual(capability.invocation, "auto+explicit")
        self.assertEqual(capability.dependencies, ())
        manager.write_selection(self.root, [capability.identifier])
        materialized = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        self.assertIn(
            "dev-platform-capability:id=interoperable-agent-handoff",
            (self.root / ".claude" / "skills" / "dev-platform-interoperable-agent-handoff" / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(manager.audit(self.root, self.registry(), manager.load_selection(self.root))["status"], "ok")
        for required in (
            "Do not produce a handoff for ordinary same-context continuation",
            "does **not** duplicate or replace it and starts no executor",
            "Verified facts, unresolved assumptions, blockers, and next intent are kept",
            "chain-of-thought or private reasoning transcripts",
            "is **stale**",
            "grants no execution authority and no write access",
            "**Changed HEAD.**",
        ):
            with self.subTest(required=required):
                self.assertIn(required, capability.instruction)
        report = manager.evaluate_existing(
            capability,
            self.root / "dev-platform" / "evals" / "interoperable-agent-handoff-pilot.json",
            runtime="fixture",
            runs=3,
        )
        self.assertEqual(report["summary"], {
            "case_count": 20,
            "passed": 20,
            "failed": 0,
            "incomplete": 0,
            "status_distribution": {"not-triggered": 30, "triggered": 30},
        })
        self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))


    def test_web_engineering_pack_is_declared_opt_in_and_bounded(self) -> None:
        registry = self.registry()
        for identifier in ("react-next-best-practices", "ui-quality-review"):
            self.assertIn(identifier, registry)
            self.assertEqual(registry[identifier].kind, "instruction-only")
            self.assertEqual(registry[identifier].invocation, "auto+explicit")
            self.assertEqual(registry[identifier].provenance["revision"], "platform-managed")
        # Not selected by the default project selection file.
        self.assertEqual(manager.load_selection(self.root), [])
        self.assertEqual(manager.audit(self.root, registry, [])["status"], "ok")
        self.assertEqual(manager.sync(self.root, registry, [])["changes"], [])
        # The React index declares its bounded topic groups as dependencies.
        react = registry["react-next-best-practices"]
        self.assertEqual(
            react.dependencies,
            (
                "dev-platform/capabilities/react-next-best-practices/server-client-components.md",
                "dev-platform/capabilities/react-next-best-practices/data-fetching-and-waterfalls.md",
                "dev-platform/capabilities/react-next-best-practices/bundle-and-code-splitting.md",
                "dev-platform/capabilities/react-next-best-practices/rendering-and-re-renders.md",
            ),
        )
        for required in ("Read only the group that matches the task", "adds no", "Precedence"):
            self.assertIn(required, react.instruction)
        # A missing topic group is an audit failure, not silent partial guidance.
        (self.root / "dev-platform" / "capabilities" / "react-next-best-practices" / "bundle-and-code-splitting.md").unlink()
        broken = manager.audit(self.root, self.registry(), [])
        self.assertEqual(broken["status"], "error")
        self.assertTrue(any("bundle-and-code-splitting.md" in issue for issue in broken["issues"]))

    def test_react_guidance_only_materializes_for_an_opted_in_project(self) -> None:
        registry = self.registry()
        manager.write_selection(self.root, ["react-next-best-practices"])
        result = manager.sync(self.root, registry, manager.load_selection(self.root))
        self.assertEqual(result["unsupported"], [])
        self.assertEqual(len(result["changes"]), 2)
        self.assertEqual(manager.audit(self.root, registry, ["react-next-best-practices"])["status"], "ok")
        for provider in ("claude", "codex"):
            surface = self.root / f".{provider}" / "skills" / "dev-platform-react-next-best-practices" / "SKILL.md"
            self.assertTrue(surface.exists())
            self.assertIn("dev-platform-capability:id=react-next-best-practices", surface.read_text(encoding="utf-8"))
        manager.write_selection(self.root, [])
        removed = manager.sync(self.root, registry, [])
        self.assertEqual(len(removed["changes"]), 2)
        for provider in ("claude", "codex"):
            self.assertFalse(
                (self.root / f".{provider}" / "skills" / "dev-platform-react-next-best-practices" / "SKILL.md").exists()
            )
        self.assertEqual(manager.sync(self.root, registry, [])["changes"], [])

    def test_ui_quality_review_is_evidence_backed_advisory_and_optional(self) -> None:
        capability = self.registry()["ui-quality-review"]
        self.assertEqual(capability.dependencies, ())
        manager.write_selection(self.root, [capability.identifier])
        materialized = manager.sync(self.root, self.registry(), manager.load_selection(self.root))
        self.assertEqual(len(materialized["changes"]), 2)
        self.assertEqual(manager.audit(self.root, self.registry(), manager.load_selection(self.root))["status"], "ok")
        for required in (
            "never redesigns the surface and never opens work items",
            "recommendation: <smallest change that resolves it, no redesign>",
            "## Healthy checks",
            "do not manufacture cosmetic work to fill\nthe report",
            "do not by themselves block a merge",
        ):
            with self.subTest(required=required):
                self.assertIn(required, capability.instruction)

    def test_web_engineering_pilots_have_positive_and_control_evidence(self) -> None:
        registry = self.registry()
        for identifier in ("react-next-best-practices", "ui-quality-review"):
            report = manager.evaluate_existing(
                registry[identifier],
                self.root / "dev-platform" / "evals" / f"{identifier}-pilot.json",
                runtime="fixture",
                runs=3,
            )
            self.assertEqual(report["summary"], {
                "case_count": 20,
                "passed": 20,
                "failed": 0,
                "incomplete": 0,
                "status_distribution": {"not-triggered": 30, "triggered": 30},
            })
            self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))


if __name__ == "__main__":
    unittest.main()
