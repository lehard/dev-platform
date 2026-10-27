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

    def test_github_unavailable_fails_open_with_a_note(self) -> None:
        result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, None)
        self.assertEqual(result.state, rollout_preflight.NONE)
        self.assertTrue(result.detail)

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
        self.assertEqual(result.state, rollout_preflight.SAFE_TO_ADOPT)
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

    def test_green_pr_is_safe_to_adopt(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("passed")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.SAFE_TO_ADOPT)
        self.assertEqual(result.pr.number, 1)


class ReconcilePendingRolloutTests(unittest.TestCase):
    def test_none_state_is_returned_unchanged(self) -> None:
        with patch.object(rollout_preflight, "observe_pending_rollout", return_value=rollout_preflight.RolloutPreflightResult(rollout_preflight.NONE)):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_pending_checks_state_is_returned_unchanged_without_merging(self) -> None:
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.PENDING_CHECKS, pr=rollout_preflight.RolloutPR(1, "url", "dev-platform/rollout-v1.0.0", "v1.0.0"))
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge") as merge,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.PENDING_CHECKS)
        merge.assert_not_called()

    def test_safe_pr_is_merged_and_synced_to_reconciled(self) -> None:
        candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, pr=candidate)
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge", return_value="merged") as merge,
            patch.object(rollout_preflight, "serialized_integration") as lock,
            patch.object(rollout_preflight, "sync_after_remote_pr_merge") as sync,
        ):
            lock.return_value.__enter__ = lambda self: None
            lock.return_value.__exit__ = lambda self, *a: False
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.RECONCILED)
        merge.assert_called_once()
        sync.assert_called_once()

    def test_conflicting_or_changed_head_blocks_without_partial_progress(self) -> None:
        candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, pr=candidate)
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge", return_value="unavailable"),
            patch.object(rollout_preflight, "sync_after_remote_pr_merge") as sync,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        sync.assert_not_called()

    def test_merge_accepted_but_head_changed_raises_system_exit_is_translated_to_blocked(self) -> None:
        candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, pr=candidate)

        def raise_exit(*_args, **_kwargs):
            raise SystemExit("PR head changed from validated abc123 to def456")

        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge", side_effect=raise_exit),
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("head changed", result.detail)

    def test_merged_but_local_sync_fails_is_resumable_merged_needs_local_sync(self) -> None:
        candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, pr=candidate)
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge", return_value="merged"),
            patch.object(rollout_preflight, "serialized_integration") as lock,
            patch.object(rollout_preflight, "sync_after_remote_pr_merge", side_effect=SystemExit("diverged")),
        ):
            lock.return_value.__enter__ = lambda self: None
            lock.return_value.__exit__ = lambda self, *a: False
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.MERGED_NEEDS_LOCAL_SYNC)

    def test_retry_after_remote_merge_finds_no_open_pr_and_is_idempotently_none(self) -> None:
        """A retried reconciliation after a prior remote-confirmed merge sees no open eligible PR."""
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="example-org/managed-project"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[]),
            patch.object(rollout_preflight, "request_protected_merge") as merge,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.NONE)
        merge.assert_not_called()


PROJECT_CONFIG = {**CONFIG, "harness_mode": "project"}


class HarnessModeGateTests(unittest.TestCase):
    def test_project_harness_skips_platform_reconciliation_without_observing(self) -> None:
        with (
            patch.object(rollout_preflight, "observe_pending_rollout") as observe,
            patch.object(rollout_preflight, "request_protected_merge") as merge,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, PROJECT_CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.NONE)
        self.assertIn("harness_mode=project", result.detail)
        observe.assert_not_called()
        merge.assert_not_called()

    def test_platform_harness_missing_publication_helper_fails_closed_before_merge(self) -> None:
        candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, pr=candidate)
        unavailable = rollout_preflight.PlatformPublicationUnavailable(
            "platform-owned pending-rollout reconciliation cannot run: scripts/project_publish.py:request_protected_merge (No module named ...)"
        )
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "_load_platform_reconciliation_helpers", side_effect=unavailable),
            patch.object(rollout_preflight, "_merge_rollout_pr") as merge,
            patch.object(rollout_preflight, "_synchronize_local_main") as sync,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("project_publish.py", result.detail)
        self.assertEqual(result.pr, candidate)
        merge.assert_not_called()
        sync.assert_not_called()

    def test_loader_reports_every_missing_platform_dependency(self) -> None:
        real_import = __import__

        def deny(name, *args, **kwargs):
            if name in {"project_publish", "finish_task"}:
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        with (
            patch.object(rollout_preflight, "request_protected_merge", None),
            patch.object(rollout_preflight, "sync_after_remote_pr_merge", None),
            patch("builtins.__import__", side_effect=deny),
        ):
            with self.assertRaises(rollout_preflight.PlatformPublicationUnavailable) as caught:
                rollout_preflight._load_platform_reconciliation_helpers()
        message = str(caught.exception)
        self.assertIn("scripts/project_publish.py:request_protected_merge", message)
        self.assertIn("scripts/finish_task.py:sync_after_remote_pr_merge", message)

    def test_loader_populates_real_helpers_when_platform_modules_are_present(self) -> None:
        # Another test module may have put the source-adapter wrappers in scripts/
        # ahead of template/scripts on sys.path; importing such a wrapper (even
        # transitively) runs its CLI. Resolve the platform modules as a platform
        # harness would: from template/scripts only.
        template = str(ROOT / "template" / "scripts")
        wrappers = str(ROOT / "scripts")
        resolved = [template, *(entry for entry in sys.path if entry not in {template, wrappers})]
        with (
            patch.object(sys, "path", resolved),
            patch.object(rollout_preflight, "request_protected_merge", None),
            patch.object(rollout_preflight, "sync_after_remote_pr_merge", None),
        ):
            rollout_preflight._load_platform_reconciliation_helpers()
            self.assertTrue(callable(rollout_preflight.request_protected_merge))
            self.assertTrue(callable(rollout_preflight.sync_after_remote_pr_merge))



def safe_candidate() -> tuple[rollout_preflight.RolloutPR, rollout_preflight.RolloutPreflightResult]:
    candidate = rollout_preflight.RolloutPR(1, "https://example.invalid/pr/1", "dev-platform/rollout-v1.0.0", "v1.0.0", "abc123")
    return candidate, rollout_preflight.RolloutPreflightResult(rollout_preflight.SAFE_TO_ADOPT, detail="green", pr=candidate)


class SessionDeferralTests(unittest.TestCase):
    def test_deferred_green_rollout_is_observed_but_never_merged_or_synced(self) -> None:
        candidate, observed = safe_candidate()
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "_load_platform_reconciliation_helpers") as load,
            patch.object(rollout_preflight, "_merge_rollout_pr") as merge,
            patch.object(rollout_preflight, "_synchronize_local_main") as sync,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=True)
        self.assertEqual(result.state, rollout_preflight.DEFERRED)
        self.assertEqual(result.pr, candidate)
        self.assertIn("#1", result.detail)
        self.assertIn(rollout_preflight.DEFER_ROLLOUT_ENV, result.detail)
        load.assert_not_called()
        merge.assert_not_called()
        sync.assert_not_called()

    def test_deferred_non_green_rollout_is_reported_as_skipped_not_blocked(self) -> None:
        for state in (rollout_preflight.PENDING_CHECKS, rollout_preflight.BLOCKED):
            with self.subTest(state=state):
                observed = rollout_preflight.RolloutPreflightResult(state, detail="not mergeable yet")
                with patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed):
                    result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=True)
                self.assertEqual(result.state, rollout_preflight.DEFERRED)
                self.assertIn(state, result.detail)

    def test_deferral_with_nothing_pending_is_none(self) -> None:
        with patch.object(rollout_preflight, "observe_pending_rollout", return_value=rollout_preflight.RolloutPreflightResult(rollout_preflight.NONE)):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=True)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_project_harness_is_unchanged_by_deferral(self) -> None:
        with patch.object(rollout_preflight, "observe_pending_rollout") as observe:
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, PROJECT_CONFIG, ENV, defer=True)
        self.assertEqual(result.state, rollout_preflight.NONE)
        observe.assert_not_called()

    def test_merge_is_announced_before_it_runs_when_not_deferred(self) -> None:
        _, observed = safe_candidate()
        out = io.StringIO()
        seen_at_merge: list[str] = []

        def fake_merge(*_args, **_kwargs):
            seen_at_merge.append(out.getvalue())
            return "merged"

        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge", side_effect=fake_merge),
            patch.object(rollout_preflight, "serialized_integration") as lock,
            patch.object(rollout_preflight, "sync_after_remote_pr_merge"),
            redirect_stdout(out),
        ):
            lock.return_value.__enter__ = lambda self: None
            lock.return_value.__exit__ = lambda self, *a: False
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV, defer=False)
        self.assertEqual(result.state, rollout_preflight.RECONCILED)
        self.assertEqual(len(seen_at_merge), 1)
        self.assertIn("Preflight: merging pending Dev Platform rollout PR #1 (v1.0.0)", seen_at_merge[0])
        self.assertIn(rollout_preflight.DEFER_ROLLOUT_FLAG, seen_at_merge[0])


class DeferralValueTests(unittest.TestCase):
    def test_unset_and_empty_mean_no_deferral(self) -> None:
        self.assertFalse(rollout_preflight.rollout_deferred({}))
        self.assertFalse(rollout_preflight.rollout_deferred({rollout_preflight.DEFER_ROLLOUT_ENV: ""}))

    def test_one_means_deferral(self) -> None:
        self.assertTrue(rollout_preflight.rollout_deferred({rollout_preflight.DEFER_ROLLOUT_ENV: "1"}))

    def test_any_other_value_is_an_explicit_error_naming_the_variable(self) -> None:
        for value in ("0", "true", "yes", " 1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(rollout_preflight.RolloutDeferralError, rollout_preflight.DEFER_ROLLOUT_ENV):
                    rollout_preflight.rollout_deferred({rollout_preflight.DEFER_ROLLOUT_ENV: value})

    def test_flag_sets_the_variable_for_the_process_only_when_given(self) -> None:
        import argparse

        parser = argparse.ArgumentParser()
        rollout_preflight.add_defer_rollout_argument(parser)
        with patch.dict(os.environ):
            os.environ.pop(rollout_preflight.DEFER_ROLLOUT_ENV, None)
            rollout_preflight.apply_defer_rollout(parser.parse_args([]))
            self.assertNotIn(rollout_preflight.DEFER_ROLLOUT_ENV, os.environ)
            rollout_preflight.apply_defer_rollout(parser.parse_args([rollout_preflight.DEFER_ROLLOUT_FLAG]))
            self.assertEqual(os.environ[rollout_preflight.DEFER_ROLLOUT_ENV], "1")


class EntrypointAndDoctorTests(unittest.TestCase):
    def test_every_managed_start_entrypoint_exposes_the_deferral_flag(self) -> None:
        scripts = ROOT / "template" / "scripts"
        for name, extra in (("start_task.py", []), ("start_managed_task.py", []), ("execute_managed_task.py", []), ("execute_requirement.py", ["advance"])):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(scripts / name), *extra, "--help"], cwd=scripts, capture_output=True, text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(rollout_preflight.DEFER_ROLLOUT_FLAG, result.stdout)

    def test_doctor_announces_green_rollout_merge_and_the_deferral(self) -> None:
        agent_doctor = load_platform_module("agent_doctor", ROOT / "template" / "scripts" / "agent_doctor.py")

        _, green = safe_candidate()
        level, message = agent_doctor.pending_rollout_report(green, "main", False)
        self.assertEqual(level, "warn")
        self.assertIn("next task start will merge it", message)
        self.assertIn(rollout_preflight.DEFER_ROLLOUT_FLAG, message)
        level, message = agent_doctor.pending_rollout_report(green, "main", True)
        self.assertIn("will be left unmerged", message)
        self.assertNotIn("next task start will merge", message)
        blocked = rollout_preflight.RolloutPreflightResult(rollout_preflight.BLOCKED, detail="checks failed")
        self.assertNotIn("will merge", agent_doctor.pending_rollout_report(blocked, "main", False)[1])
        self.assertEqual(agent_doctor.pending_rollout_report(rollout_preflight.RolloutPreflightResult(rollout_preflight.NONE), "main", False), ("ok", "no pending Dev Platform rollout PR"))


if __name__ == "__main__":
    unittest.main()
