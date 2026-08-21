from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


managed_task = load("managed_task")
start_managed_task = load("start_managed_task")
task_start = sys.modules["start_task"]
routing = load("model_routing")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


class StandardProfileManagedStartCompositionTests(unittest.TestCase):
    """Deterministic profile-matrix coverage for dev-platform#62 / #298 / #300.

    Builds a real standard-profile Git checkout (no linked worktree) and
    drives it through the actual public `start_managed_task.start_managed_task`
    composition, mocking only the GitHub-touching package adapters
    (`discover_task`, `import_task`, `reconcile`). Everything else --
    `start_task`, `cleanup_started_task`, `admit_task`, and
    `model_routing.prepare` -- runs for real against real Git state, proving
    package discovery, callable task start, branch semantics, and routing
    record creation compose correctly for this profile.
    """

    def _bare_platform_repo(self, tmp: str) -> Path:
        root = Path(tmp)
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.name", "test")
        git(root, "config", "user.email", "test@example.invalid")
        (root / "README.md").write_text("test\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-qm", "initial")
        (root / ".dev-platform.toml").write_text(
            'workflow_profile = "standard"\nharness_mode = "platform"\nmain_branch = "main"\n', encoding="utf-8"
        )
        scripts = root / "scripts"
        scripts.mkdir()
        for name in ("agent_doctor.py", "project_sync.py"):
            (scripts / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        return root

    def _package(self) -> managed_task.Package:
        return managed_task.Package(
            source_issue="lehard/development-backlog#62",
            target_repository="lehard/dev-platform",
            change="standard-profile-lifecycle-compatibility",
            prepared_against="a" * 40,
            artifacts=("proposal.md",),
            contents={},
            revision="deadbeef",
        )

    def _materialize(self, package: managed_task.Package):
        def materialize(destination: Path, reference: str, *, expected_revision: str, acknowledge_source_issue_revision: str | None = None):
            self.assertEqual(destination, destination.resolve())
            change = destination / "openspec" / "changes" / package.change
            change.mkdir(parents=True)
            (change / ".managed-task.json").write_text(
                json.dumps({"source_issue": package.source_issue, "change": package.change}), encoding="utf-8"
            )
            return package, "b" * 40, False

        return materialize

    def test_managed_start_composes_standard_task_start_and_routing_record_creation(self) -> None:
        package = self._package()
        with tempfile.TemporaryDirectory() as tmp:
            root = self._bare_platform_repo(tmp)
            with (
                patch.object(start_managed_task, "discover_task", return_value=package),
                patch.object(start_managed_task, "import_task", side_effect=self._materialize(package)),
                patch.object(start_managed_task, "reconcile") as reconcile,
                patch.object(task_start, "require_fresh_task_base", return_value="a" * 40),
            ):
                reconcile.return_value = __import__("types").SimpleNamespace(changed=True)
                started, current_main, reused = start_managed_task.start_managed_task(root, "lehard/development-backlog#62")

            self.assertEqual(started.profile, "standard")
            self.assertEqual(started.branch, f"agent/{package.change}")
            self.assertEqual(started.task_root, root.resolve())
            self.assertFalse(reused)
            self.assertEqual(current_main, "b" * 40)
            self.assertTrue((root / "openspec" / "changes" / package.change / ".managed-task.json").is_file())
            self.assertEqual(
                subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip(),
                started.branch,
            )

            # Immediately after materialization, the supervisor runs the
            # mandatory routing preflight from the assigned task checkout --
            # here, the standalone clone itself (dev-platform#300). Real
            # standard-profile checkouts have no linked worktree, so
            # main_root() naturally resolves back to the clone itself; only
            # the process-cwd dependency of that git call is stubbed here.
            with patch.object(routing, "main_root", return_value=root.resolve()):
                route = routing.prepare(
                    started.task_root, provider="codex", profile="standard",
                    rationale="bounded current-spec preflight", evidence=[f"openspec/changes/{package.change}"],
                )
                self.assertEqual(route.topology, routing.STANDALONE_CLONE)
                self.assertEqual(route.task_worktree, str(root.resolve()))
                self.assertEqual(route.integration_root, str(root.resolve()))

                with self.assertRaisesRegex(routing.RoutingError, "standalone standard-profile clone"):
                    routing.dispatch_codex(
                        started.task_root, profile="standard", rationale="bounded current-spec preflight",
                        evidence=[f"openspec/changes/{package.change}"], prompt="implement",
                    )

    def test_managed_start_leaves_main_untouched_when_project_reconciliation_fails(self) -> None:
        # Mirrors the multi-agent cleanup contract: a failed managed-start
        # must not leave a half-created standard-profile task branch behind.
        package = self._package()
        with tempfile.TemporaryDirectory() as tmp:
            root = self._bare_platform_repo(tmp)
            with (
                patch.object(start_managed_task, "discover_task", return_value=package),
                patch.object(start_managed_task, "import_task", side_effect=self._materialize(package)),
                patch.object(
                    start_managed_task, "reconcile",
                    side_effect=start_managed_task.ManagedProjectStatusError("missing project scope"),
                ),
                patch.object(task_start, "require_fresh_task_base", return_value="a" * 40),
            ):
                with self.assertRaisesRegex(start_managed_task.ManagedProjectStatusError, "missing project scope"):
                    start_managed_task.start_managed_task(root, "lehard/development-backlog#62")
            self.assertEqual(
                subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip(),
                "main",
            )
            branches = subprocess.run(["git", "branch"], cwd=root, text=True, capture_output=True, check=True).stdout
            self.assertNotIn(package.change, branches)


class LightProfileControlTests(unittest.TestCase):
    """Light is a compatibility control: it must stay on main with no task branch."""

    def test_light_profile_start_task_stays_on_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.name", "test")
            git(root, "config", "user.email", "test@example.invalid")
            (root / "README.md").write_text("test\n", encoding="utf-8")
            git(root, "add", "README.md")
            git(root, "commit", "-qm", "initial")
            (root / ".dev-platform.toml").write_text(
                'workflow_profile = "light"\nharness_mode = "platform"\nmain_branch = "main"\n', encoding="utf-8"
            )
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("agent_doctor.py", "project_sync.py"):
                (scripts / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            with patch.object(task_start, "require_fresh_task_base", return_value="a" * 40):
                started = task_start.start_task(root, "quick-fix", "Quick fix")
            self.assertEqual(started.profile, "light")
            self.assertEqual(started.branch, "main")
            self.assertEqual(started.task_root, root.resolve())


if __name__ == "__main__":
    unittest.main()
