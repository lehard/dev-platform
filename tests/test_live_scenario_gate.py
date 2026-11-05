"""The handoff gate of queue and lifecycle changes against a real git history."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

gate = load_platform_module("live_scenario_gate", ROOT / "scripts" / "live_scenario_gate.py")
live = load_platform_module("live_scenarios", ROOT / "scripts" / "live_scenarios.py")

DECLARATION = 'paths = ["queue.py"]\nscenarios = ["one", "two"]\n\n[known_failures]\ntwo = "defect 7"\n'


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=root,
                          text=True, capture_output=True, check=True).stdout.strip()


class GateTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "dev-platform").mkdir()
        (self.root / gate.GATE_FILE).write_text(DECLARATION, encoding="utf-8")
        (self.root / "queue.py").write_text("base\n", encoding="utf-8")
        (self.root / "other.py").write_text("base\n", encoding="utf-8")
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")

    def commit(self, name):
        (self.root / name).write_text("changed\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", name)
        return git(self.root, "rev-parse", "HEAD")

    def test_a_change_outside_the_declared_paths_needs_no_receipt(self):
        self.commit("other.py")
        self.assertEqual(gate.require_receipt(self.root, "main"), [])

    def test_a_missing_receipt_is_refused_by_name(self):
        self.commit("queue.py")
        with self.assertRaisesRegex(gate.LiveGateError, "no live scenario receipt for the content of queue.py"):
            gate.require_receipt(self.root, "main")

    def test_a_green_receipt_survives_a_later_commit_outside_the_paths(self):
        head = self.commit("queue.py")
        gate.write_receipt(self.root, head, [{"scenario": "one", "result": "passed"}, {"scenario": "two", "result": "passed"}])
        self.commit("other.py")
        self.assertEqual(gate.require_receipt(self.root, "main"), [])

    def test_a_receipt_of_other_content_is_refused(self):
        head = self.commit("queue.py")
        gate.write_receipt(self.root, head, [{"scenario": "one", "result": "passed"}, {"scenario": "two", "result": "passed"}])
        (self.root / "queue.py").write_text("again\n", encoding="utf-8")
        git(self.root, "commit", "-qam", "again")
        with self.assertRaisesRegex(gate.LiveGateError, "no live scenario receipt"):
            gate.require_receipt(self.root, "main")

    def test_a_partial_receipt_names_the_missing_scenario(self):
        head = self.commit("queue.py")
        gate.write_receipt(self.root, head, [{"scenario": "one", "result": "passed"}])
        with self.assertRaisesRegex(gate.LiveGateError, "lacks two"):
            gate.require_receipt(self.root, "main")

    def test_a_new_red_scenario_is_refused_and_a_known_one_is_reported(self):
        head = self.commit("queue.py")
        red = {"result": "failed", "step": "merge", "observed": "open"}
        path = gate.write_receipt(self.root, head, [{"scenario": "one", "result": "passed"}, {"scenario": "two", **red}])
        self.assertEqual(gate.require_receipt(self.root, "main"), ["known live scenario failure two: defect 7"])
        path.write_text(json.dumps({"results": [{"scenario": "one", **red}, {"scenario": "two", "result": "passed"}]}), encoding="utf-8")
        with self.assertRaisesRegex(gate.LiveGateError, "one is red at step 'merge'"):
            gate.require_receipt(self.root, "main")


class HandoffTest(unittest.TestCase):
    def test_finish_refuses_through_the_gate_error(self):
        dogfood = load_platform_module("dogfood_task", ROOT / "scripts" / "dogfood_task.py")
        with mock.patch.object(gate, "require_receipt", side_effect=gate.LiveGateError("no receipt")), \
                self.assertRaisesRegex(SystemExit, "Live scenario gate blocked publication: no receipt"):
            dogfood.require_live_receipt(ROOT)

    def test_finish_prints_a_known_failure(self):
        dogfood = load_platform_module("dogfood_task", ROOT / "scripts" / "dogfood_task.py")
        with mock.patch.object(gate, "require_receipt", return_value=["known live scenario failure two: defect 7"]), \
                mock.patch("builtins.print") as printed:
            dogfood.require_live_receipt(ROOT)
        printed.assert_called_once_with("known live scenario failure two: defect 7")


class DeclarationTest(unittest.TestCase):
    def test_every_declared_path_exists_and_the_queue_modules_are_declared(self):
        declared = gate.load_gate(ROOT)
        self.assertEqual([path for path in declared.paths if not (ROOT / path).is_file()], [])
        for module in ("publication_queue", "lifecycle_workers", "integration_contour", "pr_review_gate"):
            self.assertIn(f"template/scripts/{module}.py", declared.paths)

    def test_the_gate_requires_exactly_the_runner_scenarios(self):
        self.assertEqual(sorted(gate.load_gate(ROOT).scenarios), sorted(live.SCENARIOS))


if __name__ == "__main__":
    unittest.main()
