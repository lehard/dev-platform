from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from _platform_config import write_platform_config
from _platform_modules import load_platform_module

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

private_lineage = load_platform_module("private_lineage", SCRIPTS / "private_lineage.py")
lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
finish_task = load_platform_module("finish_task", SCRIPTS / "finish_task.py")
project_publish = load_platform_module("project_publish", SCRIPTS / "project_publish.py")
integration = load_platform_module("requirement_integration", SCRIPTS / "requirement_integration.py")

REPOSITORY = "example/internal-tasks"
PRIVATE_REF = "https://github.com/example/internal-tasks/issues/" + "216"


def make_candidate(root: Path, *, enabled: bool = True, guard: bool = True) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    extra = f'[development_backlog]\nrepository = "{REPOSITORY}"'
    if enabled:
        extra += "\n\n[private_lineage]\nenabled = true"
    write_platform_config(root, platform_version="customer", extra=extra)
    if guard:
        (root / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "check_private_backlog_refs.py", root / "scripts")
    change = root / "openspec" / "changes" / "work"
    change.mkdir(parents=True)
    (change / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
    (change / "proposal.md").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init"], cwd=root, check=True)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=root, check=True)


class EarlyPrivateReferenceGuardTests(unittest.TestCase):
    def archive(self, root: Path):
        with mock.patch.object(lifecycle, "require_existing_archive_target"), \
                mock.patch.object(lifecycle, "static_archive_problems", return_value=[]) as readiness:
            try:
                return lifecycle.archive_change(root, "work"), readiness
            except SystemExit as exc:
                return exc, readiness

    def test_proposal_reference_blocks_archive_before_any_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            (root / "openspec/changes/work/proposal.md").write_text(PRIVATE_REF, encoding="utf-8")
            outcome, readiness = self.archive(root)
            self.assertIsInstance(outcome, SystemExit)
            self.assertIn("archive blocked by private lineage", str(outcome))
            self.assertNotIn("216", str(outcome))
            # Read-only readiness may be listed too; nothing is archived.
            self.assertTrue((root / "openspec/changes/work").is_dir())

    def test_archived_artifact_reference_blocks_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            archived = root / "openspec/changes/archive/2026-01-01-old"
            archived.mkdir(parents=True)
            (archived / "design.md").write_text(PRIVATE_REF, encoding="utf-8")
            outcome, readiness = self.archive(root)
            self.assertIsInstance(outcome, SystemExit)
            # Read-only readiness may be listed too; nothing is archived.
            self.assertTrue((root / "openspec/changes/work").is_dir())

    def test_missing_guard_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root, guard=False)
            with self.assertRaisesRegex(private_lineage.PrivateLineageError, "is missing"):
                private_lineage.require_clean_candidate(root)

    def test_clean_candidate_proceeds_to_existing_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            outcome, readiness = self.archive(root)
            self.assertIsInstance(outcome, BaseException)  # later gates still run
            readiness.assert_called_once()

    def test_opted_out_checkout_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root, enabled=False, guard=False)
            (root / "openspec/changes/work/proposal.md").write_text(PRIVATE_REF, encoding="utf-8")
            private_lineage.require_clean_candidate(root)

    def test_shared_candidate_blocks_before_full_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            (root / "openspec/changes/work/design.md").write_text(PRIVATE_REF, encoding="utf-8")
            with self.assertRaisesRegex(integration.RequirementIntegrationError, "before full validation") as ctx:
                integration._require_early_privacy(root)
            self.assertNotIn("216", str(ctx.exception))


class GuardByConfigurationTests(unittest.TestCase):
    """Finish and publish run the guard where private lineage is enabled and say so elsewhere."""

    def test_enabled_without_guard_blocks_finish_and_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root, guard=False)
            blocker = finish_task.observe_private_reference_blocker(root, "title", "body")
            self.assertEqual(blocker, "private lineage is enabled but scripts/check_private_backlog_refs.py is missing")
            with self.assertRaisesRegex(SystemExit, "check_private_backlog_refs.py is missing"):
                project_publish._private_reference_guard(root)

    def test_disabled_reports_not_applicable_and_runs_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root, enabled=False, guard=True)
            output = StringIO()
            with redirect_stdout(output), mock.patch.object(finish_task.subprocess, "run") as run:
                self.assertIsNone(finish_task.observe_private_reference_blocker(root, "title", "body"))
                self.assertIsNone(project_publish._private_reference_guard(root))
            run.assert_not_called()
            self.assertEqual(output.getvalue().count(private_lineage.GUARD_NOT_APPLICABLE), 2)

    def test_enabled_with_guard_blocks_a_private_reference_in_the_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            blocker = finish_task.observe_private_reference_blocker(root, "fix " + PRIVATE_REF, "body")
            self.assertIsNotNone(blocker)
            self.assertNotIn("216", blocker)


if __name__ == "__main__":
    unittest.main()
