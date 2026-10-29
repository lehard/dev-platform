from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import execute_requirement  # noqa: E402
import managed_task  # noqa: E402
import requirement_terminal  # noqa: E402
from _platform_config import platform_config_text  # noqa: E402

REQUIREMENT = "acme/backlog#7"
CHILD = "acme/backlog#8"
CHANGE = "fresh-change"
ARCHIVE = Path("openspec/changes/archive") / f"2026-10-27-{CHANGE}"
PARENT_BODY = (
    "## Outcome\n\nImprove process\n\n## Target repository\n\n`acme/project`\n\n"
    f"<!-- requirement-children:start -->\n- [x] {CHILD}\n<!-- requirement-children:end -->"
)


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def commit_archive(repo: Path, *, source: str = CHILD, verified: bool = True) -> None:
    archived = repo / ARCHIVE
    archived.mkdir(parents=True)
    (archived / managed_task.PROVENANCE).write_text(json.dumps({"change": CHANGE, "source_issue": source}), encoding="utf-8")
    if verified:
        (archived / "verification.md").write_text("# Verification\n", encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "archive", cwd=repo)


class FreshMainTerminalTests(unittest.TestCase):
    """Terminal reconciliation proves archived lineage from fetched origin main, not the checkout."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        remote = base / "remote.git"
        git("init", "-q", "--bare", "-b", "main", str(remote), cwd=base)
        self.integration = base / "integration"
        git("init", "-q", "-b", "main", str(self.integration), cwd=base)
        git("config", "user.email", "test@example.com", cwd=self.integration)
        git("config", "user.name", "Terminal Test", cwd=self.integration)
        (self.integration / ".dev-platform.toml").write_text(platform_config_text(), encoding="utf-8")
        git("add", ".", cwd=self.integration)
        git("commit", "-q", "-m", "seed", cwd=self.integration)
        git("remote", "add", "origin", str(remote), cwd=self.integration)
        git("push", "-q", "origin", "main", cwd=self.integration)
        # A second clone stands for the queue merge that advances origin main only.
        self.merger = base / "merger"
        git("clone", "-q", str(remote), str(self.merger), cwd=base)
        git("config", "user.email", "test@example.com", cwd=self.merger)
        git("config", "user.name", "Queue Merge", cwd=self.merger)

    def merge_on_origin(self, **archive: object) -> None:
        commit_archive(self.merger, **archive)
        git("push", "-q", "origin", "main", cwd=self.merger)

    def reconcile(self) -> tuple[dict, mock.Mock]:
        issues = {
            REQUIREMENT: {"body": PARENT_BODY, "labels": [{"name": "type:requirement"}], "state": "OPEN"},
            CHILD: {"body": f"Requirement: {REQUIREMENT}\n", "labels": [{"name": "type:internal-change"}], "state": "CLOSED"},
        }
        done = SimpleNamespace(current_status="Done")
        with mock.patch.object(requirement_terminal.requirement_intake, "fetch_issue",
                               side_effect=lambda _root, repository, number: issues[f"{repository}#{number}"]), \
             mock.patch.object(requirement_terminal.requirement_target_lifecycle, "require_local_target_support"), \
             mock.patch.object(requirement_terminal.requirement_retrospective, "require_checkpoint"), \
             mock.patch.object(requirement_terminal.managed_task, "discover_task", return_value=SimpleNamespace(change=CHANGE)), \
             mock.patch.object(requirement_terminal.managed_project_status, "observe", return_value=done), \
             mock.patch.object(requirement_terminal.managed_project_status, "reconcile", return_value=done) as project, \
             mock.patch.object(requirement_terminal, "_close_issue") as close:
            result = requirement_terminal.reconcile_parent(self.integration, requirement=REQUIREMENT)
        close.assert_called_once_with(self.integration.resolve(), REQUIREMENT)
        return result, project

    def test_archive_merged_only_on_origin_main_proves_delivery_without_moving_local_main(self) -> None:
        local_head = git("rev-parse", "HEAD", cwd=self.integration)
        self.merge_on_origin()
        self.assertFalse((self.integration / ARCHIVE).exists())
        result, project = self.reconcile()
        self.assertEqual(result["status"], "done")
        project.assert_called_once()
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.integration), local_head)
        self.assertEqual(git("status", "--porcelain", cwd=self.integration), "")
        self.assertFalse((self.integration / ARCHIVE).exists())

    def test_archive_only_in_the_local_checkout_does_not_prove_delivery(self) -> None:
        commit_archive(self.integration)
        with self.assertRaisesRegex(requirement_terminal.RequirementTerminalError, f"{CHILD} has no archived verified contract on origin main"):
            self.reconcile()

    def test_archive_without_verification_receipt_on_origin_main_is_refused(self) -> None:
        self.merge_on_origin(verified=False)
        with self.assertRaisesRegex(requirement_terminal.RequirementTerminalError, "no archived verified contract"):
            self.reconcile()

    def test_committed_lineage_of_another_source_fails_closed(self) -> None:
        self.merge_on_origin(source="acme/backlog#99")
        commit = managed_task.target_main(self.integration)
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "belongs to acme/backlog#99"):
            managed_task.resolve_committed_lineage(self.integration, commit, source_issue=CHILD, change=CHANGE)

    def test_committed_lineage_reports_archived_verified_location(self) -> None:
        self.merge_on_origin()
        commit = managed_task.target_main(self.integration)
        lineage = managed_task.resolve_committed_lineage(self.integration, commit, source_issue=CHILD, change=CHANGE)
        self.assertEqual((lineage.source_issue, lineage.lifecycle, lineage.verified, lineage.path),
                         (CHILD, "archived", True, ARCHIVE.as_posix()))
        self.assertIsNone(managed_task.resolve_committed_lineage(self.integration, commit, source_issue=CHILD, change="other-change"))

    def test_done_child_check_reads_origin_main(self) -> None:
        closed = {"state": "CLOSED"}
        with mock.patch.object(execute_requirement.requirement_intake, "fetch_issue", return_value=closed):
            with self.assertRaisesRegex(execute_requirement.RequirementExecutionError, "no archived contract on origin main"):
                execute_requirement._done_child_is_delivered(self.integration, CHILD, CHANGE)
            self.merge_on_origin()
            execute_requirement._done_child_is_delivered(self.integration, CHILD, CHANGE)


class CloseIssueTests(unittest.TestCase):
    """``_close_issue`` reads the Issue state first: closed already means reconciled; every other failure stays explicit."""

    def close(self, issue: dict | Exception, patch_result: SimpleNamespace | None = None) -> mock.Mock:
        fetch = mock.patch.object(requirement_terminal.requirement_intake, "fetch_issue",
                                  side_effect=issue if isinstance(issue, Exception) else None,
                                  return_value=None if isinstance(issue, Exception) else issue)
        with fetch, mock.patch.object(requirement_terminal, "github_cli_env", return_value={}), \
             mock.patch.object(requirement_terminal.subprocess, "run", return_value=patch_result) as run:
            requirement_terminal._close_issue(Path("."), REQUIREMENT)
        return run

    def test_already_closed_issue_is_reconciled_without_a_patch(self) -> None:
        for state in ("closed", "CLOSED"):
            with self.subTest(state):
                self.close({"state": state}).assert_not_called()

    def test_open_issue_is_closed_as_completed(self) -> None:
        run = self.close({"state": "open"}, SimpleNamespace(returncode=0, stdout="", stderr=""))
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["gh", "api", "--method", "PATCH", "repos/acme/backlog/issues/7"])
        self.assertIn("state=closed", command)

    def test_other_closure_failures_stay_explicit(self) -> None:
        failed = SimpleNamespace(returncode=1, stdout="", stderr="HTTP 422: Validation Failed")
        with self.assertRaisesRegex(requirement_terminal.RequirementTerminalError, "Issue closure failed: HTTP 422"):
            self.close({"state": "open"}, failed)

    def test_unreadable_issue_state_is_not_swallowed_and_nothing_is_patched(self) -> None:
        with mock.patch.object(requirement_terminal.subprocess, "run") as run, \
             mock.patch.object(requirement_terminal, "github_cli_env", return_value={}), \
             mock.patch.object(requirement_terminal.requirement_intake, "fetch_issue",
                               side_effect=managed_task.ManagedTaskError("HTTP 502")):
            with self.assertRaisesRegex(managed_task.ManagedTaskError, "HTTP 502"):
                requirement_terminal._close_issue(Path("."), REQUIREMENT)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
