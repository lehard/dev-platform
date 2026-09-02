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
        ):
            shutil.copyfile(ROOT / "dev-platform" / "capabilities" / name, self.root / "dev-platform" / "capabilities" / name)
        shutil.copyfile(
            ROOT / "dev-platform" / "evals" / "capability-catalog-pilot.json",
            self.root / "dev-platform" / "evals" / "capability-catalog-pilot.json",
        )
        shutil.copyfile(
            ROOT / "dev-platform" / "evals" / "architecture-health-review-pilot.json",
            self.root / "dev-platform" / "evals" / "architecture-health-review-pilot.json",
        )

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


if __name__ == "__main__":
    unittest.main()
