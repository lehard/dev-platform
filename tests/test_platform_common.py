from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _platform_common  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from _platform_config import platform_config_text, write_platform_config  # noqa: E402


class PlatformCommonTests(unittest.TestCase):
    def test_checked_git_failure_is_actionable_bounded_and_redacted(self) -> None:
        result = subprocess.CompletedProcess(
            ["git", "push"],
            23,
            stdout="server said token=stdout-secret\n",
            stderr=(
                "fatal: denied https://x-access-token:url-secret@example.invalid/repo; password=stderr-secret\n"
                + "x" * (_platform_common.GIT_DIAGNOSTIC_LIMIT + 50)
            ),
        )
        with mock.patch.object(_platform_common.subprocess, "run", return_value=result) as run:
            with self.assertRaises(_platform_common.GitCommandError) as raised:
                _platform_common.run_git(
                    ["push", "https://x-access-token:command-secret@example.invalid/repo"], cwd=Path("/tmp/platform-common")
                )

        message = str(raised.exception)
        self.assertIn("Git command failed: git push", message)
        self.assertIn("cwd: /tmp/platform-common", message)
        self.assertIn("exit code: 23", message)
        self.assertIn("stderr:", message)
        self.assertIn("stdout:", message)
        self.assertNotIn("CalledProcessError", message)
        for secret in ("command-secret", "url-secret", "stderr-secret", "stdout-secret"):
            self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)
        self.assertIn("[output truncated]", message)
        self.assertLess(len(message), _platform_common.GIT_DIAGNOSTIC_LIMIT + 1800)
        self.assertTrue(run.call_args.kwargs["check"] is False)

    def test_non_raising_git_call_keeps_the_completed_process(self) -> None:
        result = subprocess.CompletedProcess(["git", "merge-base"], 1, stdout="", stderr="not an ancestor\n")
        with mock.patch.object(_platform_common.subprocess, "run", return_value=result):
            observed = _platform_common.run_git(["merge-base", "--is-ancestor", "a", "b"], check=False)

        self.assertIs(observed, result)
        self.assertEqual(observed.returncode, 1)

    def test_missing_shared_workspace_module_is_an_import_error_not_a_noop_stand_in(self) -> None:
        driver = (
            "import sys; sys.path.insert(0, sys.argv[1]); sys.modules['shared_workspace'] = None\n"
            "import _platform_common\n"
        )
        done = subprocess.run([sys.executable, "-c", driver, str(SCRIPTS)], capture_output=True, text=True, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("shared_workspace", done.stderr)
        self.assertIn("ModuleNotFoundError", done.stderr)



class PlatformConfigSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def read(self) -> dict:
        return _platform_common.read_platform_config(self.root)

    def test_missing_file_is_an_explicit_error(self) -> None:
        with self.assertRaises(_platform_common.PlatformConfigError) as raised:
            self.read()
        self.assertIn(".dev-platform.toml is missing", str(raised.exception))

    def test_missing_required_key_names_key_file_and_line_to_add(self) -> None:
        path = write_platform_config(self.root, omit=("main_branch",))
        with self.assertRaises(_platform_common.PlatformConfigError) as raised:
            self.read()
        message = str(raised.exception)
        self.assertIn(str(path), message)
        self.assertIn("missing required key main_branch", message)
        self.assertIn('add `main_branch = "<value>"`', message)

    def test_missing_required_path_names_the_paths_table(self) -> None:
        write_platform_config(self.root, omit=("paths.friction_state",))
        with self.assertRaises(_platform_common.PlatformConfigError) as raised:
            self.read()
        self.assertIn("paths.friction_state", str(raised.exception))
        self.assertIn("under [paths]", str(raised.exception))

    def test_wrong_type_names_key_and_expected_type(self) -> None:
        write_platform_config(self.root, protected_main="yes")
        with self.assertRaises(_platform_common.PlatformConfigError) as raised:
            self.read()
        self.assertIn("protected_main must be a bool", str(raised.exception))

    def test_boolean_is_not_accepted_for_an_integer_key(self) -> None:
        write_platform_config(self.root, schema_version=True)
        with self.assertRaises(_platform_common.PlatformConfigError):
            self.read()

    def test_optional_path_uses_the_schema_default_only_when_absent(self) -> None:
        write_platform_config(self.root)
        self.assertEqual(
            self.read()["paths"]["pending_completed_worktree_cleanup"],
            ".claude/pending-completed-worktree-cleanup.json",
        )
        write_platform_config(self.root, paths={"pending_completed_worktree_cleanup": ".claude/custom.json"})
        self.assertEqual(self.read()["paths"]["pending_completed_worktree_cleanup"], ".claude/custom.json")

    def test_accessors_return_validated_values_without_substitutes(self) -> None:
        write_platform_config(self.root, protected_main=False, pr_merge_mode="manual", scm_provider="GitLab")
        config = self.read()
        self.assertIs(_platform_common.protected_main(config), False)
        self.assertEqual(_platform_common.pr_merge_mode(config), "manual")
        self.assertEqual(_platform_common.scm_provider(config), "gitlab")
        with self.assertRaises(KeyError):
            _platform_common.pr_merge_mode({})

    def test_source_and_template_configurations_satisfy_the_schema(self) -> None:
        import re
        import tomllib

        # The committed public source contract is what CI and hosted workers install.
        source = ROOT / "dev-platform" / "source-contract.toml"
        _platform_common.validate_platform_config(tomllib.loads(source.read_text(encoding="utf-8")), source)
        # The template renders every required key, so a fresh project always validates.
        template = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        sections: dict[str, set[str]] = {"": set()}
        current = ""
        for line in template.splitlines():
            header = re.fullmatch(r"\[([\w.]+)\]", line.strip())
            if header:
                current = header.group(1)
                sections.setdefault(current, set())
                continue
            assignment = re.match(r"(\w+) = ", line)
            if assignment:
                sections[current].add(assignment.group(1))
        self.assertLessEqual(set(_platform_common.PLATFORM_CONFIG_REQUIRED), sections[""])
        for section, fields in _platform_common.PLATFORM_CONFIG_REQUIRED_TABLES.items():
            self.assertLessEqual(set(fields), sections[section], section)
        self.assertLessEqual(set(_platform_common.PLATFORM_CONFIG_OPTIONAL_DEFAULTS["paths"]), sections["paths"])

    def test_entry_point_reports_a_configuration_error_in_one_line(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        write_platform_config(self.root, omit=("main_branch",))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "select_checks.py")], cwd=self.root, capture_output=True, text=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertIn("platform configuration error:", result.stderr)
        self.assertIn("missing required key main_branch", result.stderr)

    def test_import_keeps_a_host_installed_exception_hook(self) -> None:
        code = (
            "import sys\n"
            "def host_hook(*args):\n    pass\n"
            "sys.excepthook = host_hook\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import _platform_common\n"
            "print(sys.excepthook is host_hook)\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "True")

    def test_fixture_text_is_complete(self) -> None:
        import tomllib

        _platform_common.validate_platform_config(tomllib.loads(platform_config_text()), self.root / "fixture.toml")


if __name__ == "__main__":
    unittest.main()
