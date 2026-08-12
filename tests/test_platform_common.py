from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _platform_common  # noqa: E402


class PlatformCommonTests(unittest.TestCase):
    def test_checked_git_failure_is_actionable_bounded_and_redacted(self) -> None:
        result = subprocess.CompletedProcess(
            ["git", "push"],
            23,
            stdout="server said token=stdout-secret\n",
            stderr=(
                "fatal: denied https://x-access-token:url-secret@example.invalid/repo; password=stderr-secret\n"
                + "x" * (_platform_common.GIT_DIAGNOSTIC_LIMIT + 50)
            ),
        )
        with mock.patch.object(_platform_common.subprocess, "run", return_value=result) as run:
            with self.assertRaises(_platform_common.GitCommandError) as raised:
                _platform_common.run_git(
                    ["push", "https://x-access-token:command-secret@example.invalid/repo"], cwd=Path("/tmp/platform-common")
                )

        message = str(raised.exception)
        self.assertIn("Git command failed: git push", message)
        self.assertIn("cwd: /tmp/platform-common", message)
        self.assertIn("exit code: 23", message)
        self.assertIn("stderr:", message)
        self.assertIn("stdout:", message)
        self.assertNotIn("CalledProcessError", message)
        for secret in ("command-secret", "url-secret", "stderr-secret", "stdout-secret"):
            self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)
        self.assertIn("[output truncated]", message)
        self.assertLess(len(message), _platform_common.GIT_DIAGNOSTIC_LIMIT + 1800)
        self.assertTrue(run.call_args.kwargs["check"] is False)

    def test_non_raising_git_call_keeps_the_completed_process(self) -> None:
        result = subprocess.CompletedProcess(["git", "merge-base"], 1, stdout="", stderr="not an ancestor\n")
        with mock.patch.object(_platform_common.subprocess, "run", return_value=result):
            observed = _platform_common.run_git(["merge-base", "--is-ancestor", "a", "b"], check=False)

        self.assertIs(observed, result)
        self.assertEqual(observed.returncode, 1)


if __name__ == "__main__":
    unittest.main()
