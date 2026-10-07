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
    import openspec_lifecycle, execute_requirement, requirement_terminal
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
        with mock.patch.object(gate.queue, "enabled", side_effect=AssertionError("queue consulted")):
            self.assertFalse(gate.managed_candidate(root))

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


if __name__ == "__main__":
    unittest.main()
