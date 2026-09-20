from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_intent  # noqa: E402


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


class ReleaseIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "test")
        git(self.root, "config", "user.email", "test@example.invalid")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_version(self, value: str) -> None:
        (self.root / "VERSION").write_text(value + "\n", encoding="utf-8")

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message)

    def test_root_commit_with_version_has_no_release_intent(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial public snapshot")
        result = release_intent.determine_release_intent(self.root)
        self.assertFalse(result.intent)
        self.assertEqual(result.reason, "repository-bootstrap-root-commit")

    def test_unchanged_version_on_non_root_commit_has_no_release_intent(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial")
        (self.root / "README.md").write_text("hello\n", encoding="utf-8")
        self.commit("unrelated change")
        result = release_intent.determine_release_intent(self.root)
        self.assertFalse(result.intent)
        self.assertEqual(result.reason, "version-unchanged")
        self.assertEqual(result.version, "1.4.38")

    def test_genuine_version_bump_has_release_intent(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial")
        self.write_version("1.4.39")
        self.commit("bump version")
        result = release_intent.determine_release_intent(self.root)
        self.assertTrue(result.intent)
        self.assertEqual(result.reason, "version-bump")
        self.assertEqual(result.version, "1.4.39")

    def test_malformed_version_bump_fails_closed(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial")
        self.write_version("not-a-version")
        self.commit("bad bump")
        with self.assertRaises(release_intent.ReleaseIntentError):
            release_intent.determine_release_intent(self.root)

    def test_root_commit_never_has_release_intent_regardless_of_version_content(self) -> None:
        # Even a malformed VERSION on a root commit must not raise: there is
        # no parent to compare against, so the bootstrap short-circuit fires
        # before SemVer validation is ever reached.
        self.write_version("not-a-version")
        self.commit("initial public snapshot")
        result = release_intent.determine_release_intent(self.root)
        self.assertFalse(result.intent)
        self.assertEqual(result.reason, "repository-bootstrap-root-commit")

    def test_cli_prints_github_output_lines_and_exits_zero(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial")
        self.write_version("1.4.39")
        self.commit("bump version")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release_intent.py"), "--root", str(self.root)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("intent=true", result.stdout)
        self.assertIn("reason=version-bump", result.stdout)
        self.assertIn("version=1.4.39", result.stdout)

    def test_cli_exits_one_on_malformed_real_bump(self) -> None:
        self.write_version("1.4.38")
        self.commit("initial")
        self.write_version("not-a-version")
        self.commit("bad bump")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release_intent.py"), "--root", str(self.root)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("VERSION must be SemVer", result.stderr)


if __name__ == "__main__":
    unittest.main()
