from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    return load_platform_module(name, path)


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
    def commit(self, text: str) -> None:
        (self.root / "file.txt").write_text(text, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", text)

    def test_returns_latest_tag_when_present(self) -> None:
        git(self.root, "tag", "v1.0.0")
        self.commit("two\n")
        git(self.root, "tag", "v1.1.0")
        with mock.patch.object(upgrade_smoke, "ROOT", self.root):
            self.assertEqual(upgrade_smoke.choose_base_ref(), "v1.1.0")

    def test_branch_older_than_latest_release_uses_its_own_ancestor_tag(self) -> None:
        git(self.root, "tag", "v1.0.0")
        git(self.root, "branch", "older")
        self.commit("two\n")
        git(self.root, "tag", "v1.1.0")
        git(self.root, "checkout", "-q", "older")
        self.commit("older work\n")
        git(self.root, "tag", "v1.2.0-rc.1")
        with mock.patch.object(upgrade_smoke, "ROOT", self.root):
            self.assertEqual(upgrade_smoke.choose_base_ref(), "v1.0.0")

    def test_missing_stable_tag_fails_explicitly(self) -> None:
        git(self.root, "tag", "v1.0.0-rc.1")
        with mock.patch.object(upgrade_smoke, "ROOT", self.root):
            with self.assertRaisesRegex(SystemExit, "requires a stable vX.Y.Z tag"):
                upgrade_smoke.choose_base_ref()

    def test_explicit_env_override_always_wins(self) -> None:
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.dict("os.environ", {"UPGRADE_BASE_REF": "explicit-ref"}),
        ):
            self.assertEqual(upgrade_smoke.choose_base_ref(), "explicit-ref")

    def test_main_fails_without_a_baseline(self) -> None:
        with (
            mock.patch.object(upgrade_smoke, "ROOT", self.root),
            mock.patch.object(sys, "argv", ["upgrade_smoke.py", "--profile", "light", "--publish-mode", "direct"]),
        ):
            with self.assertRaisesRegex(SystemExit, "requires a stable vX.Y.Z tag"):
                upgrade_smoke.main()


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
