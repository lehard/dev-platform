"""The shipped lifecycle is one path: no script reaches the removed coordinator stack, source or downstream alike."""
from __future__ import annotations

import ast
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
from _platform_config import platform_config_text  # noqa: E402
from _platform_modules import isolate_machine_pool_environment, load_platform_module  # noqa: E402

common = load_platform_module("_platform_common", SCRIPTS / "_platform_common.py")

REMOVED_MODULES = (
    "candidate_lifecycle", "hosted_workers", "integration_contour", "lifecycle_workers", "parallel_lifecycle_acceptance",
    "post_merge_runner", "post_review_finalization", "pr_review_gate", "publication_queue", "requirement_composition",
    "requirement_contributions", "worker_preflight",
)

BLOCKER = textwrap.dedent(
    """
    import importlib.abc, sys
    BLOCKED = %r
    class Blocker(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in BLOCKED:
                raise ImportError("removed module requested: " + name)
            return None
    sys.meta_path.insert(0, Blocker())
    """
) % (REMOVED_MODULES,)

ARCHIVE_DRIVER = BLOCKER + textwrap.dedent(
    """
    import os, sys
    from pathlib import Path
    from unittest import mock
    sys.path.insert(0, "scripts")
    import openspec_lifecycle as lifecycle
    root = Path.cwd()
    with mock.patch.object(lifecycle, "static_archive_problems", return_value=[]), \\
            mock.patch.object(lifecycle, "require_applicable_committed_diff"), \\
            mock.patch.object(lifecycle, "require_committed_package"), \\
            mock.patch.object(lifecycle, "require_review_evidence") as review, \\
            mock.patch.object(lifecycle, "require_ready"), \\
            mock.patch.object(lifecycle, "rehearse_archive"), \\
            mock.patch.object(lifecycle, "archive_with_recovery"), \\
            mock.patch.object(lifecycle, "run_checked") as run, \\
            mock.patch.object(lifecycle.shutil, "which", return_value="openspec"):
        code = lifecycle.finalize_change(root, "work")
    review.assert_called_once()
    assert code == 0, code
    loaded = [name for name in %r if name in sys.modules]
    assert not loaded, loaded
    print("ARCHIVE-OK")
    """
) % (REMOVED_MODULES,)

IMPORT_DRIVER = BLOCKER + textwrap.dedent(
    """
    import sys
    sys.path.insert(0, "scripts")
    import openspec_lifecycle, execute_requirement, requirement_terminal, finish_task, project_publish
    loaded = [name for name in %r if name in sys.modules]
    assert not loaded, loaded
    print("IMPORT-OK")
    """
) % (REMOVED_MODULES,)


def setUpModule() -> None:
    isolate_machine_pool_environment()


def contract(version: str, **extra: str) -> str:
    return platform_config_text(platform_version=version, capabilities={"agent_board": False}, **extra)


class ShippedScriptsTests(unittest.TestCase):
    def test_removed_modules_are_gone_and_no_script_imports_one(self) -> None:
        sources = [*SCRIPTS.glob("*.py"), *(ROOT / "scripts").glob("*.py")]
        self.assertTrue(sources)
        for source in sources:
            self.assertNotIn(source.stem, REMOVED_MODULES)
            imported: set[str] = set()
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            with self.subTest(source=source.name):
                self.assertEqual(sorted(imported & set(REMOVED_MODULES)), [])


class RemovedDeepSeekConfigTests(unittest.TestCase):
    """BR-845: a leftover DeepSeek Harness section fails explicitly instead of being ignored."""

    def read(self, extra: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(platform_config_text(extra=extra), encoding="utf-8")
            return common.read_project_config(root)

    def test_leftover_deepseek_section_names_the_file_and_the_fix(self) -> None:
        with self.assertRaisesRegex(common.PlatformConfigError,
                                    r"\.dev-platform\.toml still has \[experimental_runtime\.deepseek_harness\].*delete that section"):
            self.read("[experimental_runtime.deepseek_harness]\nenabled = false\n")

    def test_configuration_without_the_section_is_read(self) -> None:
        self.assertEqual(self.read("")["harness_mode"], "platform")
        self.assertEqual(self.read("[experimental_runtime]\n")["experimental_runtime"], {})


class ShippedCheckoutTests(unittest.TestCase):
    def add_operator_overlay(self, root: Path, toml: str) -> None:
        with (root / ".dev-platform.toml").open("a", encoding="utf-8") as handle:
            handle.write('\n[operator]\nenabled = true\nconfig_path = "operator.toml"\n'
                         'config_env = "DOWNSTREAM_BOUNDARY_TEST_OPERATOR_CONFIG"\n')
        (root / "operator.toml").write_text(toml, encoding="utf-8")

    def test_operator_cannot_override_the_project_lifecycle_identity(self) -> None:
        root = self.make_checkout(contract("source", publish_mode="pr", scm_provider="github"))
        self.add_operator_overlay(root, 'platform_version = "1.0.0"\nharness_mode = "project"\n'
                                  'publish_mode = "direct"\nscm_provider = "gitlab"\n'
                                  '[promotion]\nrepo = "example/dev-platform"\n')
        config = common.read_platform_config(root)
        self.assertEqual(("source", "platform", "pr", "github"), (
            config["platform_version"], config["harness_mode"], config["publish_mode"], config["scm_provider"]))
        self.assertEqual("example/dev-platform", config["promotion"]["repo"])

    def test_operator_cannot_supply_missing_platform_version(self) -> None:
        root = self.make_checkout(platform_config_text(omit=("platform_version",)))
        self.add_operator_overlay(root, contract("source"))
        with self.assertRaisesRegex(common.PlatformConfigError, "platform_version"):
            common.read_platform_config(root)

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

    def test_archive_runs_without_the_removed_modules(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        result = self.run_driver(root, ARCHIVE_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ARCHIVE-OK", result.stdout)

    def test_requirement_full_checks_run_credential_free(self) -> None:
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

    def test_downstream_archive_ignores_ambiguous_managed_provenance(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        self.add_managed_packages(root, ("other", "third"))
        result = self.run_driver(root, ARCHIVE_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ARCHIVE-OK", result.stdout)

    def test_entrypoints_import_without_the_removed_modules(self) -> None:
        root = self.make_checkout(contract("1.0.0"))
        result = self.run_driver(root, IMPORT_DRIVER)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("IMPORT-OK", result.stdout)

    def test_archive_completes_real_checks_and_archive(self) -> None:
        root = self.make_checkout(contract("1.0.0", main_branch="main"))
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
            assert lifecycle.finalize_change(Path.cwd(), "work") == 0
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


if __name__ == "__main__":
    unittest.main()
