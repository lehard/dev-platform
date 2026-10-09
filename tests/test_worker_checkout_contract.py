"""Disposable worker checkouts carry the committed platform contract, exactly as CI installs it."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

workers = load_platform_module("lifecycle_workers", SCRIPTS / "lifecycle_workers.py")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def seed_repository(root: Path, files: dict[str, str]) -> tuple[Path, str]:
    remote, seed = root / "remote.git", root / "seed"
    remote.mkdir(); seed.mkdir()
    git(remote, "init", "--bare", "-b", "main")
    git(seed, "init", "-b", "main")
    git(seed, "config", "user.name", "Test"); git(seed, "config", "user.email", "test@example.test")
    for name, text in files.items():
        (seed / name).parent.mkdir(parents=True, exist_ok=True)
        (seed / name).write_text(text, encoding="utf-8")
    git(seed, "add", "."); git(seed, "commit", "-m", "base")
    git(seed, "remote", "add", "origin", str(remote)); git(seed, "push", "origin", "main")
    return remote, git(seed, "rev-parse", "HEAD")


class InstallSourceContractTests(unittest.TestCase):
    def test_project_contract_is_left_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remote, head = seed_repository(Path(tmp), {".dev-platform.toml": 'platform_version = "1.0.0"\n'})
            checkout = workers.prepare_checkout(remote.as_uri(), tmp, "checkout", head)
            self.assertEqual((checkout / ".dev-platform.toml").read_text(), 'platform_version = "1.0.0"\n')
            self.assertEqual(git(checkout, "status", "--porcelain"), "")

    def test_source_repository_gets_the_committed_public_contract_excluded_from_git(self) -> None:
        public = 'platform_version = "source"\nharness_mode = "platform"\n'
        with tempfile.TemporaryDirectory() as tmp:
            remote, head = seed_repository(Path(tmp), {"dev-platform/source-contract.toml": public})
            checkout = workers.prepare_checkout(remote.as_uri(), tmp, "checkout", head)
            self.assertEqual((checkout / ".dev-platform.toml").read_text(), public)
            self.assertEqual(git(checkout, "status", "--porcelain", "--untracked-files=all"), "")

    def test_checkout_without_any_contract_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remote, head = seed_repository(Path(tmp), {"AGENTS.md": "test\n"})
            with self.assertRaisesRegex(workers.WorkerError, "neither .dev-platform.toml nor dev-platform/source-contract.toml"):
                workers.prepare_checkout(remote.as_uri(), tmp, "checkout", head)

    def test_this_repository_commits_the_public_source_contract(self) -> None:
        self.assertIn('platform_version = "source"', (ROOT / "dev-platform" / "source-contract.toml").read_text())


if __name__ == "__main__":
    unittest.main()
