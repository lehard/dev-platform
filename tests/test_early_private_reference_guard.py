from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _platform_modules import load_platform_module

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

private_lineage = load_platform_module("private_lineage", SCRIPTS / "private_lineage.py")
lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
integration = load_platform_module("requirement_integration", SCRIPTS / "requirement_integration.py")

REPOSITORY = "example/internal-tasks"
PRIVATE_REF = "https://github.com/example/internal-tasks/issues/" + "216"


def make_candidate(root: Path, *, enabled: bool = True, guard: bool = True) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    config = f'[development_backlog]\nrepository = "{REPOSITORY}"\n'
    if enabled:
        config += "[private_lineage]\nenabled = true\n"
    (root / ".dev-platform.toml").write_text(config, encoding="utf-8")
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
        with mock.patch.object(lifecycle, "require_archive_target"), \
                mock.patch.object(lifecycle, "require_static_archive_readiness") as readiness:
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
            self.assertIn("archive blocked before review", str(outcome))
            self.assertNotIn("216", str(outcome))
            readiness.assert_not_called()

    def test_archived_artifact_reference_blocks_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_candidate(root)
            archived = root / "openspec/changes/archive/2026-01-01-old"
            archived.mkdir(parents=True)
            (archived / "design.md").write_text(PRIVATE_REF, encoding="utf-8")
            outcome, readiness = self.archive(root)
            self.assertIsInstance(outcome, SystemExit)
            readiness.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
