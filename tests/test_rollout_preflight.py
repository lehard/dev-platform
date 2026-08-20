from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import rollout_preflight  # noqa: E402
from publication_state import RequiredCheckState  # noqa: E402


BOT = "dev-platform-bot-lehard[bot]"
CONFIG = {"main_branch": "main", "tools": {"rollout": {"bot_login": BOT}}}
CONFIG_NO_BOT = {"main_branch": "main"}
ROOT_PATH = Path("/tmp/integration")
ENV: dict[str, str] = {}


def pr(number: int, version: str, *, author: str = BOT, base: str = "main", branch: str | None = None, repository: str = "lehard/managed") -> dict[str, object]:
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
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_no_matching_branch_pattern_is_none(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
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
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG_NO_BOT, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("bot_login is not configured", result.detail)

    def test_similar_pr_from_wrong_author_is_not_treated_as_rollout(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0", author="human")]),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertIn("none match the expected automation identity", result.detail)

    def test_only_newest_eligible_pr_is_considered_authoritative(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0"), pr(2, "v1.2.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("passed")) as checks,
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.SAFE_TO_ADOPT)
        self.assertEqual(result.pr.number, 2)
        self.assertEqual(checks.call_args.args[2], "2")

    def test_failed_required_checks_block(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("failed", "ci")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)
        self.assertEqual(result.pr.number, 1)

    def test_pending_required_checks_are_pending_checks_state(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("pending")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.PENDING_CHECKS)

    def test_unknown_required_check_state_blocks(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("unknown", "changed head")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.BLOCKED)

    def test_green_pr_is_safe_to_adopt(self) -> None:
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[pr(1, "v1.0.0")]),
            patch.object(rollout_preflight, "required_check_state_for_ref", return_value=RequiredCheckState("passed")),
        ):
            result = rollout_preflight.observe_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.SAFE_TO_ADOPT)
        self.assertEqual(result.pr.number, 1)


class ReconcilePendingRolloutTests(unittest.TestCase):
    def test_none_state_is_returned_unchanged(self) -> None:
        with patch.object(rollout_preflight, "observe_pending_rollout", return_value=rollout_preflight.RolloutPreflightResult(rollout_preflight.NONE)):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)

    def test_pending_checks_state_is_returned_unchanged_without_merging(self) -> None:
        observed = rollout_preflight.RolloutPreflightResult(rollout_preflight.PENDING_CHECKS, pr=rollout_preflight.RolloutPR(1, "url", "dev-platform/rollout-v1.0.0", "v1.0.0"))
        with (
            patch.object(rollout_preflight, "observe_pending_rollout", return_value=observed),
            patch.object(rollout_preflight, "request_protected_merge") as merge,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
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
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
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
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
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
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
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
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.MERGED_NEEDS_LOCAL_SYNC)

    def test_retry_after_remote_merge_finds_no_open_pr_and_is_idempotently_none(self) -> None:
        """A retried reconciliation after a prior remote-confirmed merge sees no open eligible PR."""
        with (
            patch.object(rollout_preflight, "github_repo_name", return_value="lehard/managed"),
            patch.object(rollout_preflight, "list_open_prs", return_value=[]),
            patch.object(rollout_preflight, "request_protected_merge") as merge,
        ):
            result = rollout_preflight.reconcile_pending_rollout(ROOT_PATH, CONFIG, ENV)
        self.assertEqual(result.state, rollout_preflight.NONE)
        merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
