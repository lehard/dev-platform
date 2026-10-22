from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402

load_platform_module("lifecycle_workers", ROOT / "template/scripts/lifecycle_workers.py")
load_platform_module("sandboxed_writer", ROOT / "template/scripts/sandboxed_writer.py")
_spec = importlib.util.spec_from_file_location("sandboxed_writer_probes", ROOT / "scripts" / "sandboxed_writer_probes.py")
probes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probes)

TOKEN = "sk-ant-oat01-SECRETVALUE"
SNAPSHOT = {"integration_tree": "a", "linked_worktree_tree": "b", "integration_refs": "c", "remote_refs": "d"}


def writer_stdout(exits: dict[str, int] | None = None, *, drop: tuple[str, ...] = (), output: str = "denied") -> str:
    exits = exits or {}
    mapping = {name: {"exit": exits.get(name, 1), "output": output} for name in probes.PROBE_NAMES if name not in drop}
    return json.dumps({"result": f"done\n{probes.MARKER}{json.dumps(mapping)}\n"})


class EvaluateTests(unittest.TestCase):
    def evaluate(self, stdout=None, *, after=None, returncode=0, stderr=""):
        return probes.evaluate(SNAPSHOT, after or dict(SNAPSHOT), writer_stdout() if stdout is None else stdout,
                               stderr, returncode, TOKEN)

    def test_all_refused_and_unchanged_is_ok(self):
        report = self.evaluate()
        self.assertTrue(report["ok"])
        self.assertEqual({p["status"] for p in report["probes"].values()}, {"refused"})
        self.assertEqual(probes.failures(report), [])

    def test_succeeded_probe_fails_and_is_named(self):
        report = self.evaluate(writer_stdout({"push_remote": 0}))
        self.assertFalse(report["ok"])
        self.assertEqual(report["probes"]["push_remote"]["status"], "succeeded")
        self.assertIn("probe push_remote succeeded", probes.failures(report))

    def test_changed_ref_or_tree_fails(self):
        for key in probes.HARNESS_CHECKS:
            with self.subTest(key=key):
                report = self.evaluate(after={**SNAPSHOT, key: "changed"})
                self.assertFalse(report["ok"])
                self.assertEqual(report["harness_checks"][key], "changed")

    def test_missing_probe_fails(self):
        report = self.evaluate(writer_stdout(drop=("keychain",)))
        self.assertFalse(report["ok"])
        self.assertEqual(report["probes"]["keychain"]["status"], "missing")

    def test_token_in_output_fails_and_is_not_reported(self):
        for where in ("stdout", "stderr"):
            with self.subTest(where=where):
                if where == "stdout":
                    report = self.evaluate(writer_stdout(output=f"leak {TOKEN}"))
                else:
                    report = self.evaluate(stderr=f"leak {TOKEN}")
                self.assertFalse(report["ok"])
                self.assertTrue(report["token_leaked"])
                self.assertNotIn(TOKEN, json.dumps(report))

    def test_malformed_or_absent_probes_json_fails_with_error(self):
        cases = ["not json", json.dumps({"result": "no marker"}), json.dumps({"result": f"{probes.MARKER}{{oops"}),
                 json.dumps({"result": f"{probes.MARKER}[1]"}), json.dumps({"other": 1})]
        for stdout in cases:
            with self.subTest(stdout=stdout):
                report = self.evaluate(stdout)
                self.assertFalse(report["ok"])
                self.assertIn("error", report)

    def test_non_integer_exit_fails_with_error(self):
        entries = {name: {"exit": "1", "output": ""} for name in probes.PROBE_NAMES}
        report = self.evaluate(json.dumps({"result": f"{probes.MARKER}{json.dumps(entries)}"}))
        self.assertFalse(report["ok"])
        self.assertIn("error", report)

    def test_writer_nonzero_returncode_fails(self):
        report = self.evaluate(returncode=2)
        self.assertFalse(report["ok"])
        self.assertIn("writer exited 2", probes.failures(report))

    def test_empty_token_is_refused(self):
        with self.assertRaises(ValueError):
            probes.evaluate(SNAPSHOT, SNAPSHOT, writer_stdout(), "", 0, "")


class PromptTests(unittest.TestCase):
    def test_prompt_names_every_probe_without_tilde(self):
        commands = probes.probe_commands(integration=Path("/w/integration"), linked=Path("/w/integration-wt"),
                                         remote=Path("/w/remote.git"), operator_home=Path("/Users/op"),
                                         token_file=Path("/Users/op/.config/token"))
        prompt = probes.build_prompt(commands)
        for name, command in commands.items():
            self.assertIn(name, prompt)
            self.assertIn(command, prompt)
        self.assertNotIn("~", prompt)
        self.assertIn(probes.MARKER, prompt)
        self.assertNotIn("~", " ".join(probes.writer_argv(prompt)))


if __name__ == "__main__":
    unittest.main()
