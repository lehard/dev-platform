"""Contract-first lifecycle selection: downstream stays portable, source selects the coordinator."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_modules import load_platform_module  # noqa: E402

common = load_platform_module("_platform_common", SCRIPTS / "_platform_common.py")
execution = load_platform_module("execute_requirement", SCRIPTS / "execute_requirement.py")

COORDINATOR_MODULES = ("pr_review_gate", "publication_queue", "lifecycle_workers")

BLOCKER = textwrap.dedent(
    """
    import importlib.abc, sys
    BLOCKED = %r
    class Blocker(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in BLOCKED:
                raise ImportError("coordinator module blocked: " + name)
            return None
    sys.meta_path.insert(0, Blocker())
    """
) % (COORDINATOR_MODULES,)

ARCHIVE_DRIVER = BLOCKER + textwrap.dedent(
    """
    import os, sys
    from pathlib import Path
    from unittest import mock
    sys.path.insert(0, "scripts")
    import openspec_lifecycle as lifecycle
    root = Path.cwd()
    with mock.patch.object(lifecycle, "require_static_archive_readiness"), \\
            mock.patch.object(lifecycle, "require_applicable_committed_diff"), \\
            mock.patch.object(lifecycle, "ensure_review_evidence") as review, \\
            mock.patch.object(lifecycle, "require_ready"), \\
            mock.patch.object(lifecycle, "run_checked") as run, \\
            mock.patch.object(lifecycle.shutil, "which", return_value="openspec"):
        code = lifecycle.archive_change(root, "work")
    review.assert_called_once()
    assert code == 0, code
    loaded = [name for name in %r if name in sys.modules]
    assert not loaded, loaded
    print("ARCHIVE-OK")
    """
) % (COORDINATOR_MODULES,)

IMPORT_DRIVER = BLOCKER + textwrap.dedent(
    """
    import sys
    sys.path.insert(0, "scripts")
    import openspec_lifecycle, execute_requirement, requirement_terminal, finish_task, project_publish
    loaded = [name for name in %r if name in sys.modules]
    assert not loaded, loaded
    print("IMPORT-OK")
    """
) % (COORDINATOR_MODULES,)


def contract(version: str, **extra: str) -> str:
    lines = [f'platform_version = "{version}"', 'harness_mode = "platform"']
    lines += [f'{key} = "{value}"' for key, value in extra.items()]
    return "\n".join(lines) + "\n"


class SelectorTests(unittest.TestCase):
    def test_downstream_is_portable(self) -> None:
        self.assertEqual("portable", common.lifecycle_mode({"platform_version": "1.0.0"}))

    def test_downstream_ignores_other_keys(self) -> None:
        config = {"platform_version": "1.0.0", "scm_provider": "gitlab", "publish_mode": "direct"}
        self.assertEqual("portable", common.lifecycle_mode(config))

    def test_supported_source_is_coordinator(self) -> None:
        self.assertEqual("coordinator", common.lifecycle_mode({
            "platform_version": "source", "harness_mode": "platform", "publish_mode": "pr", "scm_provider": "github",
        }))
        self.assertEqual("coordinator", common.lifecycle_mode({"platform_version": "source"}))

    def test_unsupported_source_combinations_raise_named_error(self) -> None:
        for key, value in (("scm_provider", "gitlab"), ("publish_mode", "direct"), ("harness_mode", "project")):
            with self.subTest(key=key):
                with self.assertRaisesRegex(common.PlatformConfigError, f"{key}.*{value}"):
                    common.lifecycle_mode({"platform_version": "source", key: value})

    def test_missing_or_invalid_platform_version_raises(self) -> None:
        for config in ({}, {"platform_version": ""}, {"platform_version": 3}):
            with self.subTest(config=config):
                with self.assertRaisesRegex(common.PlatformConfigError, "platform_version"):
                    common.lifecycle_mode(config)


class DownstreamCheckoutTests(unittest.TestCase):
    def make_checkout(self, toml: str) -> Path:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (root / ".dev-platform.toml").write_text(toml, encoding="utf-8")
        change = root / "openspec" / "changes" / "work"
        change.mkdir(parents=True)
        (change / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
        return root

    def add_managed_packages(self, root: Path, names: tuple[str, ...]) -> None:
        for name in names:
            package = root / "openspec" / "changes" / name
            package.mkdir(parents=True, exist_ok=True)
            (package / ".managed-task.json").write_text(json.dumps({"change": name}), encoding="utf-8")

    def run_driver(self, root: Path, source: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", source], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )

    def test_downstream_archive_never_imports_coordinator_stack(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        result = self.run_driver(root, ARCHIVE_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ARCHIVE-OK", result.stdout)

    def test_portable_requirement_full_checks_without_coordinator(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        (root / "dev-platform").mkdir()
        command = ('python3 -c "import os; assert \'GH_TOKEN\' not in os.environ; '
                   'assert os.environ[\'GIT_TERMINAL_PROMPT\'] == \'0\'"')
        (root / "dev-platform/checks.toml").write_text(
            "[settings]\nfull_commands = " + json.dumps([command]) + "\n", encoding="utf-8",
        )
        source = BLOCKER + textwrap.dedent(
            """
            import os, sys
            from pathlib import Path
            sys.path.insert(0, "scripts")
            from requirement_integration import _run_full_checks
            os.environ["GH_TOKEN"] = "fixture-secret"
            _run_full_checks(Path.cwd())
            assert not any(name in sys.modules for name in BLOCKED)
            """
        )
        result = self.run_driver(root, source)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_finalize_rejects_invalid_contract_before_review_or_mutation(self) -> None:
        lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
        configs = [{}, *({"platform_version": "source", key: value}
                        for key, value in (("scm_provider", "gitlab"),
                                           ("publish_mode", "direct"), ("harness_mode", "project")))]
        for config in configs:
            for composition in ("", "owner/repo#1"):
                with self.subTest(config=config, composition=composition), \
                        mock.patch.object(lifecycle, "read_platform_config", return_value=config), \
                        mock.patch.dict("os.environ", {"DEV_PLATFORM_COMPOSITION_FINALIZATION": composition}), \
                        mock.patch.object(lifecycle, "require_archive_target") as target:
                    with self.assertRaises(common.PlatformConfigError):
                        lifecycle.archive_change(Path("/unused"), "work", finalize=True)
                    target.assert_called_once()

    def test_portable_composition_finalize_rejected_before_coordinator_import(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        source = BLOCKER + textwrap.dedent(
            """
            import os, sys
            from pathlib import Path
            sys.path.insert(0, "scripts")
            import openspec_lifecycle
            os.environ["DEV_PLATFORM_COMPOSITION_FINALIZATION"] = "owner/repo#1"
            try:
                openspec_lifecycle.archive_change(Path.cwd(), "work", finalize=True)
            except SystemExit as error:
                assert "coordinator source contract" in str(error), error
            else:
                raise AssertionError("portable composition finalization accepted")
            assert "requirement_composition" not in sys.modules
            assert not any(name in sys.modules for name in BLOCKED)
            """
        )
        result = self.run_driver(root, source)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_downstream_archive_ignores_ambiguous_managed_provenance(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        self.add_managed_packages(root, ("other", "third"))
        result = self.run_driver(root, ARCHIVE_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ARCHIVE-OK", result.stdout)

    def test_entrypoints_import_without_coordinator_stack(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        result = self.run_driver(root, IMPORT_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("IMPORT-OK", result.stdout)

    def test_managed_candidate_is_false_for_downstream_with_ambiguous_provenance(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        self.add_managed_packages(root, ("one", "two"))
        gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
        queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
        with mock.patch.object(queue, "enabled", side_effect=AssertionError("queue consulted")):
            self.assertFalse(gate.managed_candidate(root))

    def test_candidacy_imports_without_worker_or_queue_dependencies(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        self.add_managed_packages(root, ("one", "two"))
        source = BLOCKER.replace(repr(COORDINATOR_MODULES), repr(COORDINATOR_MODULES[1:])) + textwrap.dedent(
            """
            import sys
            from pathlib import Path
            sys.path.insert(0, "scripts")
            from pr_review_gate import managed_candidate
            assert managed_candidate(Path.cwd()) is False
            assert "publication_queue" not in sys.modules
            assert "lifecycle_workers" not in sys.modules
            """
        )
        result = self.run_driver(root, source)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_portable_archive_completes_real_checks_and_archive(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        for name in COORDINATOR_MODULES:
            (root / "scripts" / (name + ".py")).unlink()
        (root / "dev-platform").mkdir()
        shutil.copy(ROOT / "template/dev-platform/checks.toml", root / "dev-platform/checks.toml")
        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "test")
        git("add", "-A")
        git("commit", "-qm", "base")
        origin = root.parent / (root.name + "-origin.git")
        self.addCleanup(shutil.rmtree, origin, True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
        git("remote", "add", "origin", str(origin))
        git("push", "-q", "origin", "main")
        # This is a fixture receipt; selected-check evidence is generated by the real helper.
        (root / "openspec/changes/work/verification.md").write_text(
            "OpenSpec-Verify: PASS\nVerification-Method: fixture\n"
            "Automated-Checks-Evidence: automated-checks.json\n", encoding="utf-8",
        )
        git("add", "-A")
        git("commit", "-qm", "verified change")
        (root / "bin").mkdir()
        executable = root / "bin/openspec"
        executable.write_text(
            '#!/bin/sh\nif [ "$1" = archive ]; then\n'
            'mkdir -p openspec/changes/archive\n'
            'mv "openspec/changes/$2" "openspec/changes/archive/fixture-$2"\n'
            'fi\n', encoding="utf-8",
        )
        executable.chmod(0o755)
        source = BLOCKER + textwrap.dedent(
            """
            import os, sys
            from pathlib import Path
            sys.path.insert(0, "scripts")
            import openspec_lifecycle as lifecycle
            os.environ["PATH"] = str(Path.cwd() / "bin") + os.pathsep + os.environ["PATH"]
            sys.argv = ["openspec_lifecycle.py", "archive", "work"]
            assert lifecycle.main() == 0
            """
        )
        result = self.run_driver(root, source)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse((root / "openspec/changes/work").exists())
        archived = root / "openspec/changes/archive/fixture-work"
        evidence = json.loads((archived / "automated-checks.json").read_text())
        self.assertEqual("success", evidence["outcome"])
        self.assertTrue(evidence["executed_commands"])
        self.assertIn("python3 scripts/openspec_lifecycle.py check",
                      [item["command"] for item in evidence["executed_commands"]])

    def test_managed_candidate_still_raises_ambiguity_under_source_contract(self) -> None:
        root = self.make_checkout(contract("source"))
        self.add_managed_packages(root, ("one", "two"))
        gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
        managed_task = load_platform_module("managed_task", SCRIPTS / "managed_task.py")
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "ambiguous"):
            gate.managed_candidate(root)

    def test_managed_candidate_rejects_unsupported_source_combination(self) -> None:
        root = self.make_checkout(contract("source", scm_provider="gitlab"))
        gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
        with self.assertRaisesRegex(common.PlatformConfigError, "scm_provider"):
            gate.managed_candidate(root)


class RequirementLifecycleSelectionTests(unittest.TestCase):
    def test_portable_contribution_publication_is_unsupported(self) -> None:
        with mock.patch.object(common, "read_platform_config", return_value={"platform_version": "1.0.0"}):
            self.assertFalse(execution._contribution_publication_supported(Path("/unused")))

    def test_unsupported_source_combination_raises(self) -> None:
        for key, value in (("scm_provider", "gitlab"), ("publish_mode", "direct"), ("harness_mode", "project")):
            with self.subTest(key=key):
                config = {"platform_version": "source", key: value}
                with mock.patch.object(common, "read_platform_config", return_value=config):
                    with self.assertRaisesRegex(common.PlatformConfigError, key):
                        execution._contribution_publication_supported(Path("/unused"))

    def test_supported_source_delegates_to_publication_queue(self) -> None:
        queue = load_platform_module("publication_queue", SCRIPTS / "publication_queue.py")
        with mock.patch.object(common, "read_platform_config", return_value={"platform_version": "source"}), \
                mock.patch.object(queue, "enabled", return_value=True) as enabled:
            self.assertTrue(execution._contribution_publication_supported(Path("/unused")))
        enabled.assert_called_once()


class PublicationSelectionTests(unittest.TestCase):
    def test_publication_entrypoints_reject_unsupported_source_before_work(self) -> None:
        publication = load_platform_module("project_publish", SCRIPTS / "project_publish.py")
        finish = load_platform_module("finish_task", SCRIPTS / "finish_task.py")
        for key, value in (("scm_provider", "gitlab"), ("publish_mode", "direct"), ("harness_mode", "project")):
            config = {"platform_version": "source", key: value}
            with self.subTest(key=key), mock.patch.object(publication, "require_delivery_provenance") as delivery:
                with self.assertRaisesRegex(common.PlatformConfigError, key):
                    publication.publish_pr(Path("/unused"), "origin", "main", None, None, "manual", config=config)
                delivery.assert_not_called()
            for entrypoint in (publication, finish):
                with self.subTest(key=key, entrypoint=entrypoint.__name__), \
                        mock.patch.object(sys, "argv", [entrypoint.__name__]), \
                        mock.patch.object(entrypoint, "current_worktree_root", return_value=Path("/unused")), \
                        mock.patch.object(entrypoint, "main_root", return_value=Path("/unused")), \
                        mock.patch.object(entrypoint, "read_platform_config", return_value=config):
                    with self.assertRaisesRegex(common.PlatformConfigError, key):
                        entrypoint.main()

    def test_downstream_handoff_rejected_without_loading_coordinator(self) -> None:
        fixture = DownstreamCheckoutTests()
        root = fixture.make_checkout(contract("1.0.0"))
        self.addCleanup(fixture.doCleanups)
        source = BLOCKER + textwrap.dedent(
            """
            import sys
            from pathlib import Path
            sys.path.insert(0, "scripts")
            import project_publish
            from managed_task import ManagedTaskError
            try:
                project_publish.publish_pr(Path.cwd(), "origin", "main", None, None, "manual", developer_handoff=True)
            except ManagedTaskError as error:
                assert "coordinator source contract" in str(error)
            else:
                raise AssertionError("downstream handoff accepted")
            """
        )
        result = fixture.run_driver(root, source)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
