"""Deterministic tests for the bounded browser verification adapter.

These tests never require the `agent-browser` backend to be installed; the
backend seam is exercised through the explicit ``backend-unavailable`` path and
a stub binary.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SPEC = importlib.util.spec_from_file_location(
    "browser_verification", ROOT / "template" / "scripts" / "browser_verification.py"
)
assert SPEC and SPEC.loader
bv = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bv
SPEC.loader.exec_module(bv)

MANAGER_SPEC = importlib.util.spec_from_file_location(
    "capability_manager", ROOT / "template" / "scripts" / "capability_manager.py"
)
assert MANAGER_SPEC and MANAGER_SPEC.loader
manager = importlib.util.module_from_spec(MANAGER_SPEC)
sys.modules[MANAGER_SPEC.name] = manager
MANAGER_SPEC.loader.exec_module(manager)

FIXTURE_APP = ROOT / "tests" / "fixtures" / "browser-verification-app"


class OriginBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dev-platform").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_allowlist(self, *, allowlisted=(), production=()) -> None:
        (self.root / "dev-platform" / "browser-verification.toml").write_text(
            "version = 1\n"
            f"allowlisted_origins = {json.dumps(list(allowlisted))}\n"
            f"production_origins = {json.dumps(list(production))}\n",
            encoding="utf-8",
        )

    def test_localhost_and_test_tld_allowed_by_default(self) -> None:
        allowlist = bv.load_allowlist(self.root)
        for url in ("http://localhost:5173/", "http://127.0.0.1:8000", "https://app.localhost", "http://shop.test/cart"):
            self.assertEqual(bv.classify_origin(url, allowlist), "default-local", url)

    def test_unknown_origin_is_denied(self) -> None:
        allowlist = bv.load_allowlist(self.root)
        self.assertEqual(bv.classify_origin("https://example.com/", allowlist), "denied")

    def test_allowlist_file_widens_non_production_origins(self) -> None:
        self._write_allowlist(allowlisted=["https://staging.example.com"])
        allowlist = bv.load_allowlist(self.root)
        self.assertEqual(bv.classify_origin("https://staging.example.com/checkout", allowlist), "allowlisted")

    def test_production_origin_requires_membership_and_grant(self) -> None:
        self._write_allowlist(production=["https://shop.example.com"])
        allowlist = bv.load_allowlist(self.root)
        self.assertEqual(bv.classify_origin("https://shop.example.com/", allowlist), "production")


class RunPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dev-platform").mkdir(parents=True)
        self.flow = self.root / "flow.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _flow(self, steps) -> Path:
        self.flow.write_text(json.dumps({"name": "f", "steps": steps}), encoding="utf-8")
        return self.flow

    def test_denied_origin_fails_closed(self) -> None:
        flow = self._flow([{"action": "navigate", "target": "/"}])
        with self.assertRaises(bv.BrowserVerificationError):
            bv.build_run_plan(self.root, flow_file=flow, base_url="https://example.com", allow_production_origin=False)

    def test_localhost_run_plan_is_built(self) -> None:
        flow = self._flow([
            {"action": "navigate", "target": "/"},
            {"action": "fill", "ref": "#email", "value": "x@y.test"},
            {"action": "assert_text", "text": "ok"},
        ])
        plan = bv.build_run_plan(self.root, flow_file=flow, base_url="http://localhost:8000", allow_production_origin=False)
        self.assertEqual(plan["origin_classification"], "default-local")
        self.assertEqual(plan["interactive_steps"], ["fill"])
        self.assertEqual(plan["schema"], bv.RUN_PLAN_SCHEMA)

    def test_production_origin_needs_flag_then_refuses_interactive(self) -> None:
        (self.root / "dev-platform" / "browser-verification.toml").write_text(
            'version = 1\nallowlisted_origins = []\nproduction_origins = ["https://shop.example.com"]\n',
            encoding="utf-8",
        )
        read_only = self._flow([{"action": "navigate", "target": "/"}, {"action": "assert_text", "text": "Home"}])
        with self.assertRaises(bv.BrowserVerificationError):
            bv.build_run_plan(self.root, flow_file=read_only, base_url="https://shop.example.com", allow_production_origin=False)
        plan = bv.build_run_plan(self.root, flow_file=read_only, base_url="https://shop.example.com", allow_production_origin=True)
        self.assertEqual(plan["origin_classification"], "production")

        interactive = self._flow([{"action": "navigate", "target": "/"}, {"action": "click", "ref": "#buy"}])
        with self.assertRaises(bv.BrowserVerificationError):
            bv.build_run_plan(self.root, flow_file=interactive, base_url="https://shop.example.com", allow_production_origin=True)


class EvidenceHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dev-platform").mkdir(parents=True)
        self._env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        self.tmp.cleanup()

    def _run_plan(self, steps, base_url="http://localhost:8000") -> Path:
        flow = self.root / "flow.json"
        flow.write_text(json.dumps({"name": "checkout", "steps": steps}), encoding="utf-8")
        plan_path = self.root / "run-plan.json"
        plan = bv.build_run_plan(self.root, flow_file=flow, base_url=base_url, allow_production_origin=False)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return plan_path

    def test_backend_unavailable_is_distinct_from_flow_failure(self) -> None:
        os.environ["AGENT_BROWSER_BIN"] = str(self.root / "does-not-exist")
        plan = self._run_plan([{"action": "navigate", "target": "/"}])
        evidence = bv.record_run(self.root, run_plan_path=plan, evidence_dir=self.root / "evi")
        self.assertEqual(evidence["outcome"], "backend-unavailable")
        self.assertTrue((self.root / "evi" / "browser-evidence.json").is_file())
        self.assertTrue(evidence["sanitized"])

    def test_runtime_state_stays_under_ignored_directory(self) -> None:
        stub = self.root / "agent-browser-stub"
        stub.write_text("#!/bin/sh\necho stub\n", encoding="utf-8")
        stub.chmod(0o755)
        os.environ["AGENT_BROWSER_BIN"] = str(stub)
        plan = self._run_plan([{"action": "navigate", "target": "/"}, {"action": "screenshot", "name": "x"}])
        evidence = bv.record_run(self.root, run_plan_path=plan, evidence_dir=self.root / "evi")
        self.assertTrue(evidence["runtime_state_dir"].startswith(".dev-platform/browser-verification/"))
        created = list((self.root / ".dev-platform" / "browser-verification").rglob("*"))
        self.assertTrue(created, "runtime state should be written under the ignored directory")

    def test_run_refuses_evidence_dir_holding_session_state(self) -> None:
        os.environ["AGENT_BROWSER_BIN"] = str(self.root / "missing")
        evidence_dir = self.root / "evi"
        evidence_dir.mkdir()
        (evidence_dir / "cookies.json").write_text("[]", encoding="utf-8")
        plan = self._run_plan([{"action": "navigate", "target": "/"}])
        with self.assertRaises(bv.BrowserVerificationError):
            bv.record_run(self.root, run_plan_path=plan, evidence_dir=evidence_dir)

    def test_sanitizer_rejects_forbidden_keys(self) -> None:
        with self.assertRaises(bv.BrowserVerificationError):
            bv._assert_evidence_sanitized({"cookies": [{"name": "sid"}]})
        bv._assert_evidence_sanitized({"flow": "checkout", "outcome": "expected-state-observed"})


class RegressionSeamTests(unittest.TestCase):
    def test_fixture_encodes_one_controlled_regression(self) -> None:
        good = (FIXTURE_APP / "index.html").read_text(encoding="utf-8")
        broken = (FIXTURE_APP / "regression.html").read_text(encoding="utf-8")
        # Deterministic seam: the same assertion the exploratory flow makes
        # ("Order confirmed" reachable) is reproducible without a browser.
        self.assertIn("'Order confirmed'", good)
        self.assertNotIn("'Order confirmed'", broken)

    def test_promote_describes_but_never_writes_a_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "browser-evidence.json"
            evidence.write_text(json.dumps({
                "schema": bv.EVIDENCE_SCHEMA,
                "flow": "checkout",
                "origin": "http://localhost:8000",
                "outcome": "regression-detected",
                "observations": {"assertions": [
                    {"text": "Order confirmed", "expected_present": True, "observed_present": False}
                ]},
            }), encoding="utf-8")
            scaffold = bv.build_regression_scaffold(evidence)
            self.assertFalse(scaffold["applied"])
            self.assertEqual(scaffold["failed_assertions"][0]["text"], "Order confirmed")
            self.assertFalse((Path(tmp) / scaffold["suggested_test_path"]).exists())


class CapabilityMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dev-platform" / "capabilities").mkdir(parents=True)
        (self.root / "scripts").mkdir()
        (self.root / ".dev-platform.toml").write_text('agent_tools = "claude,codex"\n', encoding="utf-8")
        for name in ("browser_verification.py", "capability_manager.py"):
            (self.root / "scripts" / name).write_text("# fixture\n", encoding="utf-8")
        shutil.copyfile(ROOT / "dev-platform" / "capabilities.toml", self.root / "dev-platform" / "capabilities.toml")
        for name in ("browser-verification.toml", "browser-verification.md",
                     "capability-catalog.toml", "capability-catalog.md",
                     "repository-hygiene.toml", "repository-hygiene.md"):
            shutil.copyfile(ROOT / "dev-platform" / "capabilities" / name,
                            self.root / "dev-platform" / "capabilities" / name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_opt_out_materializes_no_browser_surface(self) -> None:
        registry = manager.load_registry(self.root)
        manager.sync(self.root, registry, manager.load_selection(self.root))
        self.assertFalse((self.root / ".claude" / "skills" / "dev-platform-browser-verification").exists())
        self.assertFalse((self.root / ".codex" / "skills" / "dev-platform-browser-verification").exists())

    def test_enable_materializes_exact_descriptor_marker(self) -> None:
        registry = manager.load_registry(self.root)
        manager.write_selection(self.root, ["browser-verification"])
        manager.sync(self.root, registry, manager.load_selection(self.root))
        skill = self.root / ".claude" / "skills" / "dev-platform-browser-verification" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertEqual(skill.read_text(encoding="utf-8"), manager.rendered_skill(registry["browser-verification"]))
        self.assertEqual(manager.audit(self.root, registry, ["browser-verification"])["status"], "ok")


if __name__ == "__main__":
    unittest.main()
