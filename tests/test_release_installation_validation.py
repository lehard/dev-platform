from __future__ import annotations

import inspect
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_project  # noqa: E402
import validate_release_installation as validation  # noqa: E402


class ReleaseInstallationValidationTests(unittest.TestCase):
    def make_git_installation(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        doctor = root / "scripts" / "platform_doctor.py"
        doctor.parent.mkdir()
        doctor.write_text(
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "required = [root / 'dev-platform/checks.toml', "
            "root / '.codex/skills/dev-platform-capability/SKILL.md']\n"
            "raise SystemExit(0 if all(path.is_file() for path in required) else 1)\n",
            encoding="utf-8",
        )
        for relative in ("dev-platform/checks.toml", ".codex/skills/dev-platform-capability/SKILL.md"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")

    def test_matrix_covers_supported_harness_and_scm_boundaries(self) -> None:
        fresh = {(case.scm_provider, case.harness_mode) for case in validation.FRESH_CASES}
        upgrade = {(case.scm_provider, case.harness_mode) for case in validation.UPGRADE_CASES}
        self.assertTrue({("github", "platform"), ("github", "project"), ("gitlab", "platform")} <= fresh)
        self.assertTrue({("github", "platform"), ("github", "project"), ("gitlab", "platform")} <= upgrade)

    def test_shared_validator_checks_staged_and_unstaged_hygiene_before_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doctor = root / "scripts" / "platform_doctor.py"
            doctor.parent.mkdir()
            doctor.write_text("# synthetic doctor\n", encoding="utf-8")
            with patch.object(rollout_project, "find_reject_files", return_value=[]), patch.object(rollout_project, "run") as run:
                rollout_project.validate_platform_installation(root)
        self.assertEqual(
            run.call_args_list,
            [
                call(["git", "diff", "--check", "--"], root),
                call(["git", "diff", "--cached", "--check", "--"], root),
                call(["python3", str(doctor)], root),
            ],
        )

    def test_negative_reject_fixture_fails_before_doctor(self) -> None:
        with patch.object(rollout_project, "find_reject_files", return_value=["conflicted-file.rej"]), patch.object(rollout_project, "run") as run:
            with self.assertRaisesRegex(ValueError, "unresolved .rej files: conflicted-file.rej"):
                rollout_project.validate_platform_installation(ROOT)
        run.assert_not_called()

    def test_negative_missing_required_surface_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(rollout_project, "find_reject_files", return_value=[]), patch.object(rollout_project, "run"):
            with self.assertRaisesRegex(ValueError, "missing scripts/platform_doctor.py"):
                rollout_project.validate_platform_installation(Path(tmp))

    def test_negative_staged_whitespace_fails_before_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_git_installation(root)
            (root / "bad.txt").write_text("bad trailing space \n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            with self.assertRaisesRegex(ValueError, "git diff --cached --check"):
                rollout_project.validate_platform_installation(root)

    def test_negative_required_input_and_capability_surface_fail_doctor(self) -> None:
        for missing in ("dev-platform/checks.toml", ".codex/skills/dev-platform-capability/SKILL.md"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make_git_installation(root)
                (root / missing).unlink()
                with self.assertRaisesRegex(ValueError, "platform_doctor.py"):
                    rollout_project.validate_platform_installation(root)

    def test_missing_baseline_fails_closed_unless_explicit_snapshot_skip(self) -> None:
        with patch.object(validation, "shallow_repository", return_value=False), patch.object(validation, "stable_baseline_ref", return_value=None), patch.object(sys, "argv", ["validate_release_installation.py"]):
            with self.assertRaisesRegex(SystemExit, "requires a stable baseline"):
                validation.main()

    def test_shallow_snapshot_requires_explicit_skip(self) -> None:
        with patch.object(validation, "shallow_repository", return_value=True), patch.object(sys, "argv", ["validate_release_installation.py"]):
            with self.assertRaisesRegex(SystemExit, "requires complete Git history"):
                validation.main()
        with patch.object(validation, "shallow_repository", return_value=True), patch.object(sys, "argv", ["validate_release_installation.py", "--allow-shallow-snapshot"]):
            self.assertEqual(validation.main(), 0)

    def test_entrypoint_never_invokes_downstream_selector(self) -> None:
        source = (ROOT / "scripts" / "validate_release_installation.py").read_text(encoding="utf-8")
        self.assertNotIn('run(["python3", "scripts/select_checks.py"', source)
        self.assertNotIn('run(["python3", "scripts/select_checks.py"', inspect.getsource(rollout_project.validate_platform_installation))

    def test_pr_and_publication_workflows_use_the_same_entrypoint(self) -> None:
        for relative in (".github/workflows/ci.yml", ".github/workflows/publish-version.yml"):
            with self.subTest(relative=relative):
                self.assertIn(
                    "python3 scripts/validate_release_installation.py",
                    (ROOT / relative).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
