from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_distribution_test", ROOT / "scripts" / "public_distribution.py")
assert SPEC and SPEC.loader
public_distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(public_distribution)


class PublicDistributionTests(unittest.TestCase):
    def test_audit_and_snapshot_use_the_same_candidate_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "private.txt").write_text("lehard/private-project\n", encoding="utf-8")
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))
            result = public_distribution.snapshot(root, root / "snapshot.tar")
            self.assertEqual(result["audit"]["candidate_files"], receipt["candidate_files"])

    def test_installation_state_and_nested_cache_are_not_product_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / ".dev-platform.toml").write_text("lehard/private-operator\n", encoding="utf-8")
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "helper.cpython-313.pyc").write_bytes(b"machine-local")
            receipt = public_distribution.audit_tree(root)
            self.assertFalse(public_distribution.has_findings(receipt))
            self.assertEqual(receipt["candidate_files"], ["README.md"])

    def test_packaged_owner_reference_blocks_audit_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "operator.md").write_text("lehard/private-project\n", encoding="utf-8")
            receipt = public_distribution.audit_tree(root)
            self.assertTrue(public_distribution.has_findings(receipt))
            with self.assertRaises(ValueError):
                public_distribution.snapshot(root, root / "snapshot.tar")

    def test_history_audit_reports_fake_secret_without_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "credential.txt").write_text("ghp_" + "a" * 30, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "synthetic credential"], cwd=root, check=True)
            receipt = public_distribution.history_audit(root)
            self.assertEqual(receipt["findings"][0]["pattern"], "github_pat")
            self.assertNotIn("ghp_", str(receipt["findings"]))

    def test_history_audit_reads_blobs_in_bounded_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "safe.txt").write_text("safe\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "safe"], cwd=root, check=True)
            with mock.patch.object(public_distribution.subprocess, "run", wraps=subprocess.run) as run:
                receipt = public_distribution.history_audit(root)
            self.assertFalse(receipt["findings"])
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(["git", "cat-file", "--batch"], commands)
            self.assertLessEqual(len(commands), 5)
