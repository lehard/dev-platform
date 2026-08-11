from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "template" / "scripts" / "managed_task.py"
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("managed_task", SOURCE)
assert spec and spec.loader
managed_task = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = managed_task
spec.loader.exec_module(managed_task)


def package_body(*, target: str = "lehard/dev-platform", artifact: str = "proposal.md", version: str = "v1") -> str:
    fence = chr(96) * 3
    manifest = {
        "version": 1,
        "source_issue": "lehard/development-backlog#1",
        "target_repository": target,
        "change": "add-managed-backlog-intake",
        "prepared_against": "a" * 40,
        "artifacts": [artifact, "specs/intake/spec.md", "design.md", "tasks.md"],
    }
    blocks = {
        artifact: "## Why\n",
        "specs/intake/spec.md": "## ADDED Requirements\n\n### Requirement: Intake\n\n#### Scenario: Valid\n\n- **WHEN** valid\n- **THEN** import\n",
        "design.md": "## Design\n",
        "tasks.md": "## Tasks\n",
    }
    return (
        f"<!-- managed-openspec:{version} -->\n{fence}json\n{json.dumps(manifest)}\n{fence}\n"
        + "".join(f"<!-- managed-openspec:file:{path} -->\n{content}<!-- managed-openspec:endfile -->\n" for path, content in blocks.items())
    )


class ManagedPackageTests(unittest.TestCase):
    def test_parse_valid_package_and_revision_is_stable(self) -> None:
        body = package_body()
        first = managed_task.parse_package([body], "lehard/development-backlog#1")
        second = managed_task.parse_package([body], "lehard/development-backlog#1")
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(first.artifacts[0], "proposal.md")

    def test_rejects_missing_duplicate_unsupported_and_unsafe_packages(self) -> None:
        valid = package_body()
        cases = [
            ([], "found 0"),
            ([valid, valid], "found 2"),
            ([package_body(version="v2")], "unsupported"),
            ([package_body(artifact="../escape.md")], "unsafe"),
        ]
        for bodies, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, expected):
                    managed_task.parse_package(bodies, "lehard/development-backlog#1")

    def test_issue_and_origin_normalization(self) -> None:
        self.assertEqual(managed_task.issue_ref("https://github.com/Lehard/Development-Backlog/issues/1"), ("lehard/development-backlog", 1))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess = __import__("subprocess")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin", "git@github.com:Lehard/Dev-Platform.git"], cwd=root, check=True)
            self.assertEqual(managed_task.origin_repository(root), "lehard/dev-platform")

    def test_import_is_idempotent_and_never_invokes_execution_lifecycle(self) -> None:
        package = managed_task.parse_package([package_body()], "lehard/development-backlog#1")
        schema = {
            "artifactPaths": {
                "proposal": {"outputPath": "proposal.md"},
                "specs": {"outputPath": "specs/**/*.md"},
                "design": {"outputPath": "design.md"},
                "tasks": {"outputPath": "tasks.md"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls: list[list[str]] = []

            def fake_json(command: list[str], cwd: Path, env=None):
                calls.append(command)
                if command[:3] == ["openspec", "new", "change"]:
                    (root / "openspec" / "changes" / package.change).mkdir(parents=True)
                    return {"change": {"id": package.change}}
                raise AssertionError(command)

            with (
                patch.object(managed_task, "issue_bodies", return_value=[package_body()]),
                patch.object(managed_task, "origin_repository", return_value="lehard/dev-platform"),
                patch.object(managed_task, "target_main", return_value="b" * 40),
                patch.object(managed_task, "openspec_status", return_value=schema),
                patch.object(managed_task, "validate_change"),
                patch.object(managed_task, "run_json", side_effect=fake_json),
                patch.object(managed_task.shutil, "which", return_value="/usr/bin/openspec"),
            ):
                imported, freshness, reused = managed_task.import_task(root, "lehard/development-backlog#1")
                self.assertFalse(reused)
                self.assertEqual(freshness, "b" * 40)
                self.assertEqual(imported.revision, package.revision)
                self.assertTrue((root / "openspec" / "changes" / package.change / ".managed-task.json").is_file())
                _, _, reused = managed_task.import_task(root, "lehard/development-backlog#1")
                self.assertTrue(reused)
            joined = " ".join(" ".join(call) for call in calls)
            for forbidden in ("apply", "start_task", "finish_task", "project_publish", "gh-aw"):
                self.assertNotIn(forbidden, joined)

    def test_wrong_target_stops_before_openspec_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.object(managed_task, "issue_bodies", return_value=[package_body(target="other/repo")]),
                patch.object(managed_task, "origin_repository", return_value="lehard/dev-platform"),
                patch.object(managed_task, "target_main") as target_main,
            ):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, "not this checkout"):
                    managed_task.import_task(root, "lehard/development-backlog#1")
            target_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
