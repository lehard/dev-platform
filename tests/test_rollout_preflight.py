from __future__ import annotations

import io
import tomllib
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import rollout_preflight  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402
from _platform_config import platform_config_text  # noqa: E402
from publication_state import RequiredCheckState  # noqa: E402


BOT = "dev-platform-bot-lehard[bot]"
CONFIG_NO_BOT = tomllib.loads(platform_config_text())
CONFIG = {**CONFIG_NO_BOT, "tools": {"rollout": {"bot_login": BOT}}}
ROOT_PATH = Path("/tmp/integration")
ENV: dict[str, str] = {}


def pr(number: int, version: str, *, author: str = BOT, base: str = "main", branch: str | None = None, repository: str = "example-org/managed-project") -> dict[str, object]:
    branch = branch or f"dev-platform/rollout-{version}"
    return {
        "number": number,
        "html_url": f"https://example.invalid/pr/{number}",
        "user": {"login": author},
        "base": {"ref": base},
        "head": {"ref": branch, "repo": {"full_name": repository}, "sha": f"sha-{number}"},
    }


class ObservePendingRolloutTests(unittest.TestCase):
    def test_no_open_prs_is_none(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_no_matching_branch_pattern_is_none(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0", branch="feature/unrelated")]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_unresolvable_repository_fails_open_with_a_note(self) -> None:
        with patch.object(rollout_preflight, "github_repo_name", return_value=None):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)
        self.assertTrue(result.detail)

    def test_candidate_without_configured_bot_login_blocks_ambiguously(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG_NO_BOT, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("bot_login is not configured", result.detail)

    def test_similar_pr_from_wrong_author_is_not_treated_as_rollout(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0", author="human")]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("none match the expected automation identity", result.detail)

    def test_only_newest_eligible_pr_is_considered_authoritative(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0"), pr(2, "v1.2.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("passed")) as checks,
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.GREEN)
        self.assertEqual(result.pr.number, 2)
        self.assertEqual(checks.call_args.args[2], "2")

    def test_failed_required_checks_block(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("failed", "ci")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertEqual(result.pr.number, 1)

    def test_pending_required_checks_are_pending_checks_state(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("pending")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.PENDING_CHECKS)

    def test_unknown_required_check_state_blocks(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("unknown", "changed head", cause="head-mismatch")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)

    def test_green_pr_is_reported_green(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("passed")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.GREEN)
        self.assertEqual(result.pr.number, 1)


class EntrypointAndDoctorTests(unittest.TestCase):
    def test_no_start_entrypoint_exposes_a_rollout_deferral_flag(self) -> None:
        for script in ("start_task.py", "start_managed_task.py", "execute_managed_task.py", "execute_requirement.py"):
            with self.subTest(script=script):
                source = (ROOT / "template" / "scripts" / script).read_text(encoding="utf-8")
                self.assertNotIn("defer_rollout", source)

    def test_task_start_never_observes_or_merges_a_rollout(self) -> None:
        source = (ROOT / "template" / "scripts" / "start_task.py").read_text(encoding="utf-8")
        self.assertNotIn("pending_rollout", source)
        self.assertFalse(hasattr(rollout_preflight, "reconcile_pending_rollout"))

    def test_doctor_reports_a_pending_rollout_as_merged_only_by_an_explicit_rollout(self) -> None:
        doctor = load_platform_module("agent_doctor", ROOT / "template" / "scripts" / "agent_doctor.py")
        candidate = rollout_preflight.RolloutPR(48, "https://example.invalid/pr/48", "dev-platform/rollout-v1.2.3", "v1.2.3", "abc123")
        green = rollout_preflight.RolloutObservation(rollout_preflight.GREEN, detail="rollout PR #48 (v1.2.3) is green", pr=candidate)
        level, message = doctor.pending_rollout_report(green)
        self.assertEqual(level, "warn")
        self.assertIn("rollout PR #48 (v1.2.3) is green", message)
        self.assertIn("only an explicit rollout merges it", message)
        self.assertEqual(doctor.pending_rollout_report(rollout_preflight.RolloutObservation(rollout_preflight.NONE)), ("ok", "no pending Dev Platform rollout PR"))


class PlatformLagTests(unittest.TestCase):
    """Task start reports a project behind its platform source's latest release (BR-843)."""

    SOURCE = "example-org/dev-platform"
    PROJECT = "example-org/managed-project"

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.answers(f"gh:{self.SOURCE}")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def answers(self, source: str | None) -> None:
        lines = ["_commit: v2.0.0"] + ([f"_src_path: {source}"] if source is not None else [])
        (self.root / ".copier-answers.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def observe(self, installed: str = "2.0.0", *, release: object = None, env: dict[str, str] | None = ENV,
                project: str | None = PROJECT) -> rollout_preflight.PlatformLag:
        release = {"tag_name": "v3.0.0"} if release is None else release
        api = (patch.object(rollout_preflight, "gh_api", side_effect=release) if isinstance(release, Exception)
               else patch.object(rollout_preflight, "gh_api", return_value=release))
        with api as self.api, patch.object(rollout_preflight, "github_repo_name", return_value=project):
            return rollout_preflight.observe_platform_lag(self.root, {**CONFIG, "platform_version": installed}, env)

    def test_lagging_project_gets_both_versions_and_the_exact_update_command(self) -> None:
        lag = self.observe()
        self.api.assert_called_once_with([f"repos/{self.SOURCE}/releases/latest"], env=ENV)
        command = f"gh workflow run rollout.yml --repo {self.SOURCE} -f version=v3.0.0 -f repository={self.PROJECT}"
        self.assertEqual((lag.state, lag.project_version, lag.latest_version, lag.command),
                         (rollout_preflight.LAG_BEHIND, "v2.0.0", "v3.0.0", command))
        self.assertIn("v2.0.0", lag.detail)
        self.assertIn(command, lag.detail)

    def test_project_on_or_past_the_latest_release_is_current(self) -> None:
        for installed in ("3.0.0", "3.0.1"):
            with self.subTest(installed=installed):
                self.assertEqual(self.observe(installed).state, rollout_preflight.LAG_CURRENT)

    def test_platform_source_repository_is_not_applicable_without_any_read(self) -> None:
        lag = self.observe("source", env=None)
        self.assertEqual(lag.state, rollout_preflight.LAG_NOT_APPLICABLE)
        self.api.assert_not_called()

    def test_every_source_form_resolves_to_owner_and_name(self) -> None:
        for source in (f"gh:{self.SOURCE}", f"https://github.com/{self.SOURCE}", f"https://github.com/{self.SOURCE}.git",
                       f"git@github.com:{self.SOURCE}.git", f"'gh:{self.SOURCE}'"):
            with self.subTest(source=source):
                self.answers(source)
                self.assertEqual(rollout_preflight.platform_source_repository(self.root), self.SOURCE)

    def test_undeterminable_inputs_fail_with_their_cause(self) -> None:
        cases = [
            ("platform_version", lambda: self.observe("2.0"), "platform_version '2.0' is not a stable version"),
            ("no _src_path", lambda: (self.answers(None), self.observe())[1], "has no _src_path"),
            ("foreign source", lambda: (self.answers("https://gitlab.com/o/n"), self.observe())[1], "is not a GitHub repository"),
            ("no GitHub auth", lambda: self.observe(env=None), "GitHub CLI authentication is unavailable"),
            ("release read", lambda: self.observe(release=ValueError("GitHub API request failed: 404")),
             "cannot read the latest release of example-org/dev-platform: GitHub API request failed: 404"),
            ("no tag", lambda: self.observe(release={}), "has no tag_name"),
            ("prerelease tag", lambda: self.observe(release={"tag_name": "v3.1.0-rc.1"}), "is not a stable version"),
            ("project repo", lambda: self.observe(project=None), "cannot resolve this project's GitHub repository"),
        ]
        for name, run, message in cases:
            with self.subTest(name), self.assertRaisesRegex(rollout_preflight.PlatformLagError, message):
                run()
            self.answers(f"gh:{self.SOURCE}")
        (self.root / ".copier-answers.yml").unlink()
        with self.assertRaisesRegex(rollout_preflight.PlatformLagError, "is missing"):
            self.observe()
