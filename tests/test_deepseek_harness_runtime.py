from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(TEMPLATE_SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "deepseek_harness_runtime_under_test",
    TEMPLATE_SCRIPTS / "deepseek_harness_adapter.py",
)
assert SPEC and SPEC.loader
dsh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dsh
SPEC.loader.exec_module(dsh)


def write_config(root: Path, *, enabled: bool = False, version: str = dsh.PINNED_SDK_VERSION) -> None:
    (root / ".dev-platform.toml").write_text(
        textwrap.dedent(
            f"""\
            schema_version = 2

            [experimental_runtime.deepseek_harness]
            enabled = {str(enabled).lower()}
            sdk_version = "{version}"
            profile = "observation"
            """
        ),
        encoding="utf-8",
    )


def available_capability() -> dict[str, object]:
    return {
        "status": "available",
        "selection": "enabled",
        "write_capability": {"status": "unavailable", "reason": "no attestation"},
    }


class DeepSeekHarnessCapabilityTests(unittest.TestCase):
    def test_backend_is_disabled_by_default_even_when_exact_runtime_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_config(root)
            capability = dsh.inspect_capability(
                root,
                version_reader=lambda _name: dsh.PINNED_SDK_VERSION,
                runtime_resolver=lambda: ("/runtime",),
                system="Linux",
                machine="x86_64",
            )
        self.assertEqual(capability["status"], "available")
        self.assertEqual(capability["selection"], "disabled")
        self.assertFalse(capability["default"])
        self.assertEqual(capability["write_capability"]["status"], "unavailable")

    def test_explicit_opt_in_does_not_relax_exact_version_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_config(root, version="0.1.1rc2")
            capability = dsh.inspect_capability(
                root,
                explicit_opt_in=True,
                version_reader=lambda _name: dsh.PINNED_SDK_VERSION,
                runtime_resolver=lambda: ("/runtime",),
                system="Linux",
                machine="x86_64",
            )
        self.assertEqual(capability["selection"], "enabled")
        self.assertEqual(capability["status"], "incompatible")
        self.assertIn("exact version", capability["diagnostic"])

    def test_missing_and_mismatched_installations_are_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_config(root)
            missing = dsh.inspect_capability(
                root,
                explicit_opt_in=True,
                version_reader=lambda _name: None,
                runtime_resolver=lambda: ("/runtime",),
                system="Linux",
                machine="x86_64",
            )
            mismatched = dsh.inspect_capability(
                root,
                explicit_opt_in=True,
                version_reader=lambda name: "0.1.1rc2" if name == dsh.SDK_DISTRIBUTION else dsh.PINNED_SDK_VERSION,
                runtime_resolver=lambda: ("/runtime",),
                system="Linux",
                machine="x86_64",
            )
        self.assertEqual(missing["status"], "missing")
        self.assertIn("pip install -r", missing["diagnostic"])
        self.assertEqual(mismatched["status"], "incompatible")
        self.assertIn("do not match", mismatched["diagnostic"])

    def test_unpublished_host_wheel_is_an_explicit_capability_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_config(root)
            capability = dsh.inspect_capability(
                root,
                explicit_opt_in=True,
                version_reader=lambda _name: dsh.PINNED_SDK_VERSION,
                runtime_resolver=lambda: ("/runtime",),
                system="Darwin",
                machine="x86_64",
            )
        self.assertEqual(capability["status"], "incompatible")
        self.assertIn("no supported wheel", capability["diagnostic"])


class DeepSeekHarnessUsageTests(unittest.TestCase):
    def test_complete_usage_is_runtime_confirmed_and_disjoint(self) -> None:
        usage = dsh.normalize_usage(
            [
                {
                    "type": "assistant/message",
                    "data": {
                        "usage": {
                            "inputTokens": 7,
                            "cacheReadTokens": 11,
                            "outputTokens": 3,
                            "reasoningTokens": 2,
                        }
                    },
                },
                {
                    "type": "assistant/message",
                    "data": {"usage": {"inputTokens": 5, "cacheReadTokens": 13, "outputTokens": 4}},
                },
            ]
        )
        self.assertEqual(
            set(usage),
            {"input_tokens", "cache_read_tokens", "fresh_input_tokens", "output_tokens", "total_tokens", "request_count"},
        )
        self.assertEqual(usage["request_count"]["value"], 2)
        self.assertEqual(usage["fresh_input_tokens"]["value"], 12)
        self.assertEqual(usage["cache_read_tokens"]["value"], 24)
        self.assertEqual(usage["output_tokens"]["value"], 7)
        self.assertEqual(usage["input_tokens"]["status"], "unknown")
        self.assertEqual(usage["total_tokens"]["status"], "unknown")
        self.assertTrue(all(measurement["source"] in {"runtime-confirmed", "unknown"} for measurement in usage.values()))

    def test_partial_and_unknown_usage_never_become_zero(self) -> None:
        partial = dsh.normalize_usage(
            [
                {"type": "assistant/message", "data": {"usage": {"outputTokens": 4}}},
                {"type": "assistant/message", "data": {}},
            ]
        )
        unknown = dsh.normalize_usage([])
        self.assertEqual(partial["request_count"]["value"], 2)
        self.assertEqual(partial["output_tokens"], {"value": None, "source": "unknown", "status": "unknown"})
        self.assertTrue(all(measurement["status"] == "unknown" for measurement in unknown.values()))

    def test_invalid_boolean_or_negative_usage_is_not_accepted_as_a_count(self) -> None:
        usage = dsh.normalize_usage(
            [
                {
                    "type": "assistant/message",
                    "data": {"usage": {"inputTokens": True, "outputTokens": -1}},
                }
            ]
        )
        self.assertEqual(usage["request_count"]["value"], 1)
        self.assertEqual(usage["fresh_input_tokens"]["status"], "unknown")
        self.assertEqual(usage["output_tokens"]["status"], "unknown")


class DeepSeekHarnessHandleTests(unittest.TestCase):
    def test_start_and_terminal_result_use_one_bounded_worker_record(self) -> None:
        worker = textwrap.dedent(
            """\
            import json, sys
            request = json.load(sys.stdin)
            print(json.dumps({
                "terminal": {"status": "completed", "reason": "completed"},
                "result": {"text": request["prompt"], "truncated": False},
                "cleanup": {"status": "clean"},
            }))
            """
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            handle = dsh.start_runtime(
                root,
                workspace=workspace,
                session_root=workspace / ".sessions",
                prompt="bounded result",
                capability_override=available_capability(),
                worker_command=(sys.executable, "-c", worker),
            )
            result = handle.wait(timeout_seconds=5)
        self.assertEqual(result["terminal"]["status"], "completed")
        self.assertEqual(result["result"]["text"], "bounded result")

    def test_failed_worker_is_normalized_without_treating_it_as_success(self) -> None:
        worker = "import json,sys; json.load(sys.stdin); sys.stderr.write('runtime failed'); raise SystemExit(7)"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            result = dsh.start_runtime(
                root,
                workspace=workspace,
                session_root=workspace / ".sessions",
                prompt="fail",
                capability_override=available_capability(),
                worker_command=(sys.executable, "-c", worker),
            ).wait(timeout_seconds=5)
        self.assertEqual(result["terminal"]["status"], "failed")
        self.assertEqual(result["terminal"]["reason"], "invalid-worker-output")
        self.assertIn("runtime failed", result["diagnostic"])
        self.assertEqual(result["cleanup"]["status"], "clean")

    def test_cancel_terminates_and_reaps_the_worker_process_group(self) -> None:
        worker = "import json,sys,time; json.load(sys.stdin); time.sleep(30)"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            handle = dsh.start_runtime(
                root,
                workspace=workspace,
                session_root=workspace / ".sessions",
                prompt="cancel",
                capability_override=available_capability(),
                worker_command=(sys.executable, "-c", worker),
            )
            result = handle.cancel()
        self.assertEqual(result["terminal"]["status"], "cancelled")
        self.assertEqual(result["cleanup"]["status"], "clean")
        self.assertTrue(result["cleanup"]["process_group_reaped"])
        efficiency = result["execution"]["efficiency"]
        self.assertEqual(efficiency["timing"]["source"], "platform")
        self.assertEqual(efficiency["timing"]["status"], "measured")
        self.assertTrue(all(measurement["status"] == "unknown" for measurement in efficiency["usage"].values()))
        self.assertNotIn("timing", result)
        self.assertNotIn("usage", result)

    def test_workspace_write_refuses_before_worker_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            with self.assertRaisesRegex(dsh.AdapterError, "no attestation") as caught:
                dsh.start_runtime(
                    root,
                    workspace=workspace,
                    session_root=workspace / ".sessions",
                    prompt="write",
                    profile_name=dsh.WRITE_PROFILE,
                    capability_override=available_capability(),
                    worker_command=("/must-not-launch",),
                )
        self.assertEqual(caught.exception.code, "containment_unavailable")

    def test_session_state_must_stay_inside_assigned_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            with self.assertRaisesRegex(dsh.AdapterError, "inside the assigned workspace") as caught:
                dsh.start_runtime(
                    root,
                    workspace=workspace,
                    session_root=root / "outside",
                    prompt="observe",
                    capability_override=available_capability(),
                    worker_command=("/must-not-launch",),
                )
        self.assertEqual(caught.exception.code, "invalid_session_root")


class DeepSeekHarnessDistributionTests(unittest.TestCase):
    def test_adapter_entrypoint_does_not_shadow_upstream_runtime_carrier(self) -> None:
        probe = textwrap.dedent(
            f"""\
            import importlib.util
            import sys
            from pathlib import Path

            path = Path({str(TEMPLATE_SCRIPTS / 'deepseek_harness_adapter.py')!r})
            spec = importlib.util.spec_from_file_location("adapter_shadow_probe", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            print(module._resolve_bundled_runtime())
            """
        )
        with tempfile.TemporaryDirectory() as temporary:
            fake_package = Path(temporary) / "deepseek_harness_runtime"
            fake_package.mkdir()
            (fake_package / "__init__.py").write_text(
                "def resolve_bundled_launch_args():\n    return ('/fake-bundled-runtime',)\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join((str(TEMPLATE_SCRIPTS), temporary))
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/fake-bundled-runtime", result.stdout)

    def test_dependency_profile_and_config_are_exact_and_disabled(self) -> None:
        requirements = (ROOT / "template" / "requirements" / "deepseek-harness.txt").read_text(encoding="utf-8")
        central_config = (ROOT / ".dev-platform.toml").read_text(encoding="utf-8")
        template_config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        profile = (ROOT / "template" / "dev-platform" / "deepseek-harness-observation.cordis.yml").read_text(encoding="utf-8")
        self.assertIn(f"deepseek-harness-sdk=={dsh.PINNED_SDK_VERSION}", requirements)
        for config in (central_config, template_config):
            self.assertIn("[experimental_runtime.deepseek_harness]", config)
            self.assertIn("enabled = false", config)
            self.assertIn(f'sdk_version = "{dsh.PINNED_SDK_VERSION}"', config)
        for write_capability in (
            "dsh-bash-local",
            "dsh-bash-sandbox",
            "dsh-fs-local",
            "dsh-fs-sandbox",
            "dsh-tool-fs",
            "dsh-subagent",
            "dsh-mcp-client",
        ):
            self.assertNotIn(f"name: '@deepseek-ai/{write_capability}'", profile)

    def test_central_and_rendered_runtime_guidance_stay_identical(self) -> None:
        central = (ROOT / "docs" / "engineering" / "deepseek-harness-runtime.md").read_text(encoding="utf-8")
        rendered = (ROOT / "template" / "docs" / "engineering" / "deepseek-harness-runtime.md").read_text(encoding="utf-8")
        self.assertEqual(central, rendered)
        self.assertIn("workspace-write", central)
        self.assertIn("fails closed", central)
        self.assertIn("Exact-version update procedure", central)

    def test_source_entrypoint_reports_current_host_capability_as_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deepseek_harness_adapter.py"), "capability"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(result.returncode, (0, 2), result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["backend"], dsh.BACKEND)
        self.assertEqual(payload["selection"], "disabled")


if __name__ == "__main__":
    unittest.main()
