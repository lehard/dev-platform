from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "dogfood_task.py"
SPEC = importlib.util.spec_from_file_location("dogfood_task", SOURCE)
assert SPEC and SPEC.loader
dogfood_task = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dogfood_task
SPEC.loader.exec_module(dogfood_task)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


class CentralDogfoodLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Central lifecycle test")
        (self.root / ".gitignore").write_text(".claude/\n", encoding="utf-8")
        (self.root / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "multi-agent"\nharness_mode = "platform"\npublish_mode = "pr"\npr_merge_mode = "auto"\n'
            'source_required_paths = ["scripts/dogfood_task.py"]\n[paths]\nworktrees = ".claude/worktrees"\n',
            encoding="utf-8",
        )
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "dogfood_task.py").write_text("# adapter\n", encoding="utf-8")
        (self.root / "README.md").write_text("base\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "base")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_managed_change(self, name: str = "central-task") -> Path:
        change = self.root / "openspec" / "changes" / name
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(
            json.dumps({"change": name, "source_issue": "lehard/development-backlog#2"}), encoding="utf-8"
        )
        (change / "proposal.md").write_text("## Why\n", encoding="utf-8")
        return change

    def test_start_transfers_only_validated_import_into_isolated_worktree(self) -> None:
        source = self.add_managed_change()
        args = dogfood_task.argparse.Namespace(slug="central-task", task="Backlog #2", scope="scripts", change="central-task")

        def fake_run(command: list[str], root: Path) -> None:
            if command[1:] == ["scripts/start_task.py", "central-task", "--task", "Backlog #2", "--scope", "scripts"]:
                (root / ".claude" / "worktrees" / "central-task").mkdir(parents=True)

        with mock.patch.object(dogfood_task, "run", side_effect=fake_run) as run:
            self.assertEqual(dogfood_task.start(self.root, args), 0)

        destination = self.root / ".claude" / "worktrees" / "central-task" / "openspec" / "changes" / "central-task"
        self.assertFalse(source.exists())
        self.assertTrue((destination / ".managed-task.json").exists())
        self.assertEqual(run.call_count, 2)
        self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=self.root, text=True, capture_output=True, check=True).stdout, "")

    def test_start_refuses_unrelated_integration_mutation(self) -> None:
        self.add_managed_change()
        (self.root / "foreign.txt").write_text("do not move\n", encoding="utf-8")
        args = dogfood_task.argparse.Namespace(slug="central-task", task="Backlog #2", scope="scripts", change="central-task")
        with mock.patch.object(dogfood_task, "run") as run:
            with self.assertRaisesRegex(SystemExit, "dirty outside managed change"):
                dogfood_task.start(self.root, args)
        run.assert_not_called()

    def test_status_and_finish_delegate_to_authoritative_shared_commands(self) -> None:
        args = dogfood_task.argparse.Namespace(title="Central task", body="body")
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(dogfood_task, "run") as run:
            self.assertEqual(dogfood_task.status(args), 0)
            self.assertEqual(dogfood_task.finish(args), 0)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["python3", "scripts/finish_task.py", "--status"],
                ["python3", "scripts/finish_task.py", "--cleanup", "--title", "Central task", "--body", "body"],
            ],
        )

    def test_status_json_delegates_to_the_supported_machine_readable_child_command(self) -> None:
        args = dogfood_task.argparse.Namespace(json=True)
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(dogfood_task, "run") as run:
            self.assertEqual(dogfood_task.status(args), 0)
        self.assertEqual(run.call_args.args[0], ["python3", "scripts/finish_task.py", "--status", "--json"])

    def test_status_json_recovery_instruction_is_executable_and_returns_drift_hashes(self) -> None:
        recorded = "a" * 64
        current = "b" * 64
        payload = json.dumps(
            {
                "source_issue_drift": {
                    "source_issue": "lehard/development-backlog#2",
                    "recorded_body_sha256": recorded,
                    "current_body_sha256": current,
                }
            }
        )
        (self.root / "scripts" / "finish_task.py").write_text(
            "import sys\n"
            "if sys.argv[1:] != ['--status', '--json']:\n"
            "    raise SystemExit('expected --status --json')\n"
            f"print({payload!r})\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SOURCE), "status", "--json"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        drift = json.loads(result.stdout)["source_issue_drift"]
        self.assertEqual(drift["recorded_body_sha256"], recorded)
        self.assertEqual(drift["current_body_sha256"], current)

    def test_reconcile_delegates_to_the_explicit_shared_lifecycle_operation(self) -> None:
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(dogfood_task, "run") as run:
            self.assertEqual(dogfood_task.reconcile(dogfood_task.argparse.Namespace()), 0)
        self.assertEqual(run.call_args.args[0], ["python3", "scripts/finish_task.py", "--reconcile"])

    def test_route_codex_dispatches_the_supervisor_selected_profile(self) -> None:
        args = dogfood_task.argparse.Namespace(
            profile="standard",
            rationale="Sol supervisor completed semantic preflight",
            evidence=["openspec/changes/central-task"],
            prompt=None,
        )
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            self.assertEqual(dogfood_task.route_codex(args), 0)

        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["python3", "scripts/model_routing.py", "dispatch-codex", "--profile", "standard"])
        self.assertIn("--rationale", command)
        self.assertIn("--evidence", command)
        self.assertIn(dogfood_task.CODEX_EXECUTOR_PROMPT, command)
        self.assertEqual(run.call_args.args[1], self.root)

    def test_route_codex_omits_profile_when_confirming_authored_tier(self) -> None:
        args = dogfood_task.argparse.Namespace(
            profile=None,
            rationale="freshness check: no new hard trigger found",
            evidence=[],
            prompt=None,
        )
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            self.assertEqual(dogfood_task.route_codex(args), 0)

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["python3", "scripts/model_routing.py", "dispatch-codex"])
        self.assertNotIn("--profile", command)
        self.assertIn("--rationale", command)

    def test_route_claude_records_route_and_cannot_itself_launch(self) -> None:
        args = dogfood_task.argparse.Namespace(
            profile="standard",
            rationale="Sol supervisor completed semantic preflight",
            evidence=["openspec/changes/central-task"],
        )
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            self.assertEqual(dogfood_task.route_claude(args), 0)

        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["python3", "scripts/model_routing.py", "dispatch-claude", "--profile", "standard"])
        self.assertIn("--rationale", command)
        self.assertIn("--evidence", command)
        self.assertNotIn("--prompt", command)
        self.assertEqual(run.call_args.args[1], self.root)

    def test_route_claude_omits_profile_when_confirming_authored_tier(self) -> None:
        args = dogfood_task.argparse.Namespace(
            profile=None,
            rationale="freshness check: no new hard trigger found",
            evidence=[],
        )
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            self.assertEqual(dogfood_task.route_claude(args), 0)

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["python3", "scripts/model_routing.py", "dispatch-claude"])
        self.assertNotIn("--profile", command)
        self.assertIn("--rationale", command)

    def test_report_claude_execution_dispatches_with_agent_id(self) -> None:
        args = dogfood_task.argparse.Namespace(agent_id="agent-abc123", summary="added implemented.txt")
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            self.assertEqual(dogfood_task.report_claude_execution(args), 0)

        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                "python3",
                "scripts/model_routing.py",
                "record-claude-execution",
                "--agent-id",
                "agent-abc123",
                "--summary",
                "added implemented.txt",
            ],
        )

    def test_finish_blocks_managed_delivery_without_routing_gate(self) -> None:
        self.add_managed_change()
        args = dogfood_task.argparse.Namespace(title=None, body=None)
        with mock.patch.object(dogfood_task, "current_root", return_value=self.root), mock.patch.object(
            dogfood_task, "run"
        ) as run:
            with self.assertRaisesRegex(SystemExit, "routing gate blocked publication"):
                dogfood_task.finish(args)
        run.assert_not_called()

    def test_routing_gate_accepts_successful_standard_route(self) -> None:
        self.add_managed_change()
        record = self.root / ".claude" / "model-routing" / "central-task.json"
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps(
                {
                    "change": "central-task",
                    "provider": "codex",
                    "profile": "standard",
                    "execution": {"launched": True, "returncode": 0, "violation": False},
                }
            ),
            encoding="utf-8",
        )
        dogfood_task.require_routing_gate(self.root)

    def test_routing_gate_accepts_successful_standard_claude_route(self) -> None:
        self.add_managed_change()
        record = self.root / ".claude" / "model-routing" / "central-task.json"
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps(
                {
                    "change": "central-task",
                    "provider": "claude",
                    "profile": "standard",
                    "execution": {
                        "launched": True,
                        "agent_id": "agent-abc123",
                        "tier": "detection-only",
                        "postcheck": {"containment": "clean", "pre_existing_changes": []},
                    },
                }
            ),
            encoding="utf-8",
        )
        dogfood_task.require_routing_gate(self.root)

    def test_routing_gate_rejects_claude_route_without_clean_postcheck(self) -> None:
        self.add_managed_change()
        record = self.root / ".claude" / "model-routing" / "central-task.json"
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps(
                {
                    "change": "central-task",
                    "provider": "claude",
                    "profile": "standard",
                    "execution": {"launched": True, "agent_id": "agent-abc123"},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SystemExit, "clean successful native Claude executor postcheck"):
            dogfood_task.require_routing_gate(self.root)

    def test_source_contract_is_explicit_and_adapter_paths_are_present(self) -> None:
        import tomllib

        with (ROOT / ".dev-platform.toml").open("rb") as handle:
            config = tomllib.load(handle)
        self.assertEqual(config["workflow_profile"], "multi-agent")
        self.assertTrue(config["protected_main"])
        self.assertEqual(config["publish_mode"], "pr")
        self.assertEqual(config["pr_merge_mode"], "auto")
        self.assertEqual(config["paths"]["worktrees"], ".claude/worktrees")
        self.assertIn("scripts/dogfood_task.py", config["source_required_paths"])
        self.assertIn("scripts/managed_project_status.py", config["source_required_paths"])
        self.assertIn("scripts/shared_workspace.py", config["source_required_paths"])
        for name in (
            "agent_board.py", "agent_doctor.py", "agent_friction.py", "finish_task.py", "reconcile_task.py", "managed_project_status.py", "openspec_lifecycle.py", "independent_review.py", "shared_workspace.py",
            "project_publish.py", "project_sync.py", "select_checks.py", "start_task.py", "start_worktree.py", "worktree_cleanup.py",
        ):
            with self.subTest(name=name):
                self.assertIn("run_template", (ROOT / "scripts" / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
