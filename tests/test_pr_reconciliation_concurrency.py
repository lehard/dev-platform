from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import finish_task  # noqa: E402
import project_publish  # noqa: E402


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


class StructuredRequiredCheckStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git("init", "-b", "main", cwd=self.root)
        git("config", "user.name", "Test", cwd=self.root)
        git("config", "user.email", "test@example.invalid", cwd=self.root)
        (self.root / "file.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.root)
        git("commit", "-m", "base", cwd=self.root)
        git("switch", "-c", "agent/checks", cwd=self.root)
        (self.root / "file.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=self.root)
        self.head = git("rev-parse", "agent/checks", cwd=self.root)
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def state(self, checks: str, *, head: str | None = None, checks_exit: int = 0, stderr: str = "") -> project_publish.RequiredCheckState:
        gh = self.bin / "gh"
        gh.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = pr ] && [ \"$2\" = view ]; then\n"
            f"  printf '%s\\n' '{{\"state\":\"OPEN\",\"headRefOid\":\"{head or self.head}\"}}'; exit 0\n"
            "fi\n"
            "if [ \"$1\" = pr ] && [ \"$2\" = checks ]; then\n"
            f"  printf '%s\\n' '{checks}'; printf '%s\\n' '{stderr}' >&2; exit {checks_exit}\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return project_publish.required_check_state(self.root, env, "agent/checks")

    def test_classifies_structured_required_check_states_for_current_head(self) -> None:
        cases = {
            "[]": "not_registered",
            '[{"name":"platform-ci","state":"PENDING","workflow":"ci","link":""}]': "pending",
            '[{"name":"platform-ci","state":"SUCCESS","workflow":"ci","link":""}]': "passed",
            '[{"name":"platform-ci","state":"FAILURE","workflow":"ci","link":""}]': "failed",
        }
        for payload, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(self.state(payload).kind, expected)

    def test_does_not_infer_registration_from_human_readable_error_text(self) -> None:
        result = self.state("not json", checks_exit=1, stderr="no checks reported")
        self.assertEqual(result.kind, "unknown")

    def test_rejects_checks_when_pr_head_does_not_match_local_task_head(self) -> None:
        self.assertEqual(self.state("[]", head="0" * 40).kind, "unknown")

    def test_registration_and_pending_timeouts_are_explicitly_resumable(self) -> None:
        with mock.patch.object(project_publish, "required_check_state", return_value=project_publish.RequiredCheckState("not_registered")), mock.patch.object(project_publish, "CHECK_REGISTRATION_TIMEOUT_SECONDS", 0):
            with self.assertRaisesRegex(SystemExit, "resumable"):
                project_publish.wait_for_pr_checks(self.root, {}, "agent/checks")
        with mock.patch.object(project_publish, "required_check_state", return_value=project_publish.RequiredCheckState("pending")), mock.patch.object(project_publish, "CHECK_COMPLETION_TIMEOUT_SECONDS", 0):
            with self.assertRaisesRegex(SystemExit, "resumable"):
                project_publish.wait_for_pr_checks(self.root, {}, "agent/checks")


class ReconciliationLockTests(unittest.TestCase):
    def test_two_confirmed_merges_serialize_local_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "remote.git"
            integration = base / "integration"
            git("init", "--bare", str(remote), cwd=base)
            git("init", "-b", "main", str(integration), cwd=base)
            git("config", "user.name", "Test", cwd=integration)
            git("config", "user.email", "test@example.invalid", cwd=integration)
            (integration / "file.txt").write_text("merged remote state\n", encoding="utf-8")
            git("add", ".", cwd=integration)
            git("commit", "-m", "merged", cwd=integration)
            git("remote", "add", "origin", str(remote), cwd=integration)
            git("push", "-u", "origin", "main", cwd=integration)

            worker = (
                "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                "from finish_task import reconcile_confirmed_remote_pr_merge; root=Path(sys.argv[2]); "
                "reconcile_confirmed_remote_pr_merge(root, root, {'paths': {'main_merge_lock': '.claude/main-merge.lock'}}, sys.argv[3], 'main', 'standard', cleanup=False, timeout_seconds=2)"
            )
            first = subprocess.Popen([sys.executable, "-c", worker, str(SCRIPTS), str(integration), "agent/task-a"])
            second = subprocess.Popen([sys.executable, "-c", worker, str(SCRIPTS), str(integration), "agent/task-b"])
            try:
                self.assertEqual(first.wait(timeout=3), 0)
                self.assertEqual(second.wait(timeout=3), 0)
            finally:
                for process in (first, second):
                    if process.poll() is None:
                        process.kill()
                        process.wait()

    def test_already_merged_reconciliation_waits_for_existing_integration_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            integration = Path(tmp)
            config = {"paths": {"main_merge_lock": ".claude/main-merge.lock"}}
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys,time; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from finish_task import serialized_integration; lock=serialized_integration(Path(sys.argv[2]), {'paths': {'main_merge_lock': '.claude/main-merge.lock'}}, 2); lock.__enter__(); time.sleep(.35); lock.__exit__(None,None,None)",
                    str(SCRIPTS),
                    str(integration),
                ]
            )
            time.sleep(0.08)
            started = time.monotonic()
            with mock.patch.object(finish_task, "sync_after_remote_pr_merge") as sync, mock.patch.object(finish_task, "finish_board") as board:
                finish_task.reconcile_confirmed_remote_pr_merge(
                    integration, integration, config, "agent/already-merged", "main", "multi-agent", cleanup=False, timeout_seconds=2
                )
            holder.wait(timeout=2)
            self.assertGreaterEqual(time.monotonic() - started, 0.2)
            sync.assert_called_once_with(integration, integration, config, "main")
            board.assert_called_once()


if __name__ == "__main__":
    unittest.main()
