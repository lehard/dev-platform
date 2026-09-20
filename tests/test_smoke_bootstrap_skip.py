from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


upgrade_smoke = load("upgrade_smoke_under_test", "tests/upgrade_smoke.py")
rollout_recopy_smoke = load("rollout_recopy_smoke_under_test", "tests/rollout_recopy_smoke.py")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


class HermeticRepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "file.txt").write_text("one\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "root commit")

    def tearDown(self) -> None:
        self.tmp.cleanup()


class ChooseBaseRefTests(HermeticRepoCase):
    def test_returns_latest_tag_when_present(self) -> None:
        git(self.root, "tag", "v1.0.0")
        (self.root / "file.txt").write_text("two\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "second")
        git(self.root, "tag", "v1.1.0")
        with mock.patch.object(upgrade_smoke, "ROOT", self.root):
            self.assertEqual(upgrade_smoke.choose_base_ref(), "v1.1.0")

    def test_falls_back_to_bootstrap_commit_when_resolvable(self) -> None:
        fallback = git(self.root, "rev-parse", "HEAD").stdout.strip()
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.object(upgrade_smoke, "FALLBACK_BASE_REF", fallback),
        ):
            self.assertEqual(upgrade_smoke.choose_base_ref(), fallback)

    def test_returns_none_when_no_tag_and_fallback_unresolvable(self) -> None:
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.object(upgrade_smoke, "FALLBACK_BASE_REF", "0" * 40),
        ):
            self.assertIsNone(upgrade_smoke.choose_base_ref())

    def test_explicit_env_override_always_wins(self) -> None:
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.dict("os.environ", {"UPGRADE_BASE_REF": "explicit-ref"}),
        ):
            self.assertEqual(upgrade_smoke.choose_base_ref(), "explicit-ref")

    def test_main_skips_cleanly_when_no_baseline_is_resolvable(self) -> None:
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.object(upgrade_smoke, "FALLBACK_BASE_REF", "0" * 40),
            mock.patch.object(sys, "argv", ["upgrade_smoke.py", "--profile", "light", "--publish-mode", "direct"]),
        ):
            self.assertEqual(upgrade_smoke.main(), 0)


class RolloutRecopySmokeSkipTests(HermeticRepoCase):
    def test_skips_cleanly_when_reproduction_tag_is_absent(self) -> None:
        with mock.patch.object(rollout_recopy_smoke, "ROOT", self.root):
            result = rollout_recopy_smoke.main()
        self.assertEqual(result, 0)
        tags = git(self.root, "tag", "--list").stdout.split()
        self.assertNotIn("v99.99.99", tags)

    def test_proceeds_past_the_check_when_reproduction_tag_is_present(self) -> None:
        git(self.root, "tag", "v1.2.3")
        with (
            mock.patch.object(rollout_recopy_smoke, "ROOT", self.root),
            mock.patch.object(
                rollout_recopy_smoke.tempfile,
                "TemporaryDirectory",
                side_effect=RuntimeError("reached real logic past the early-return guard"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                rollout_recopy_smoke.main()
        # The finally-block cleanup runs even though we raised inside the
        # try, so the smoke-test tag should not linger.
        tags = git(self.root, "tag", "--list").stdout.split()
        self.assertNotIn("v99.99.99", tags)


if __name__ == "__main__":
    unittest.main()
