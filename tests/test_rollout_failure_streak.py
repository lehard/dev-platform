from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_failure_streak as rfs  # noqa: E402


class StreakStateTests(unittest.TestCase):
    def test_first_failure_opens_streak_at_one_without_alert(self) -> None:
        state, alert, unreadable = rfs.next_state_on_failure(
            None,
            repository="lehard/cuby",
            version="v1.4.13",
            category="copier_conflict",
            reason="Copier left unresolved .rej files: scripts/project_publish.py.rej",
            last_updated="2026-01-01T00:00:00Z",
            threshold=3,
        )
        self.assertEqual(state["consecutive_failures"], 1)
        self.assertEqual(state["first_failed_release"], "v1.4.13")
        self.assertEqual(state["last_failed_release"], "v1.4.13")
        self.assertFalse(alert)
        self.assertFalse(unreadable)

    def test_repeated_failure_increments_and_preserves_first_release(self) -> None:
        first, _, _ = rfs.next_state_on_failure(
            None,
            repository="lehard/cuby",
            version="v1.4.13",
            category="copier_conflict",
            reason="rej files",
            last_updated="2026-01-01T00:00:00Z",
            threshold=3,
        )
        body = rfs.render_body(first)
        second, alert, unreadable = rfs.next_state_on_failure(
            body,
            repository="lehard/cuby",
            version="v1.4.14",
            category="copier_conflict",
            reason="rej files still present",
            last_updated="2026-01-02T00:00:00Z",
            threshold=3,
        )
        self.assertEqual(second["consecutive_failures"], 2)
        self.assertEqual(second["first_failed_release"], "v1.4.13")
        self.assertEqual(second["last_failed_release"], "v1.4.14")
        self.assertEqual(second["last_reason"], "rej files still present")
        self.assertFalse(alert)
        self.assertFalse(unreadable)

    def test_third_consecutive_failure_crosses_default_threshold(self) -> None:
        body = None
        state = None
        for index, version in enumerate(["v1.4.13", "v1.4.14", "v1.4.15"], start=1):
            state, alert, unreadable = rfs.next_state_on_failure(
                body,
                repository="lehard/cuby",
                version=version,
                category="copier_conflict",
                reason="rej files",
                last_updated=f"2026-01-0{index}T00:00:00Z",
                threshold=3,
            )
            body = rfs.render_body(state)
            self.assertFalse(unreadable)
            if index < 3:
                self.assertFalse(alert, f"unexpected alert at failure {index}")
            else:
                self.assertTrue(alert)
        self.assertEqual(state["consecutive_failures"], 3)

    def test_unreadable_prior_state_escalates_instead_of_resetting(self) -> None:
        state, alert, unreadable = rfs.next_state_on_failure(
            "this issue body has no machine-readable state block",
            repository="lehard/cuby",
            version="v1.4.16",
            category="unknown",
            reason="unclear",
            last_updated="2026-01-05T00:00:00Z",
            threshold=3,
        )
        self.assertTrue(unreadable)
        self.assertTrue(alert)
        self.assertGreaterEqual(state["consecutive_failures"], 3)

    def test_different_repository_marker_does_not_leak_into_state(self) -> None:
        other_project, _, _ = rfs.next_state_on_failure(
            None,
            repository="lehard/other-project",
            version="v1.4.13",
            category="copier_conflict",
            reason="rej files",
            last_updated="2026-01-01T00:00:00Z",
            threshold=3,
        )
        other_body = rfs.render_body(other_project)
        # A body carrying a *different* repository's state must not be
        # mistaken for this repository's own prior streak.
        state, alert, unreadable = rfs.next_state_on_failure(
            other_body,
            repository="lehard/cuby",
            version="v1.4.13",
            category="copier_conflict",
            reason="rej files",
            last_updated="2026-01-01T00:00:00Z",
            threshold=3,
        )
        self.assertEqual(state["consecutive_failures"], 1)
        self.assertFalse(alert)
        self.assertFalse(unreadable)


class ParseAndRenderTests(unittest.TestCase):
    def test_parse_state_round_trips_through_render_body(self) -> None:
        state = {
            "schema_version": 1,
            "repository": "lehard/cuby",
            "consecutive_failures": 4,
            "first_failed_release": "v1.4.13",
            "last_failed_release": "v1.4.20",
            "last_category": "copier_conflict",
            "last_reason": "rej files",
            "last_updated": "2026-08-10T00:00:00Z",
        }
        body = rfs.render_body(state)
        parsed = rfs.parse_state(body)
        self.assertEqual(parsed, state)

    def test_parse_state_returns_none_for_body_without_marker(self) -> None:
        self.assertIsNone(rfs.parse_state("just a regular issue body"))

    def test_parse_state_returns_none_for_malformed_json(self) -> None:
        body = "<!-- rollout-failure-streak-state\n{not valid json\n-->"
        self.assertIsNone(rfs.parse_state(body))

    def test_parse_state_rejects_unknown_schema_version(self) -> None:
        body = (
            "<!-- rollout-failure-streak-state\n"
            '{"schema_version": 99, "repository": "lehard/cuby", "consecutive_failures": 1}\n'
            "-->"
        )
        self.assertIsNone(rfs.parse_state(body))


class LabelBootstrapTests(unittest.TestCase):
    def test_ensure_label_uses_idempotent_force_create(self) -> None:
        with patch.object(rfs, "run_gh") as run_gh:
            run_gh.return_value = rfs.subprocess.CompletedProcess(["gh"], 0, "", "")
            rfs.ensure_label("lehard/dev-platform", rfs.TRACKING_LABEL)
        run_gh.assert_called_once()
        args = run_gh.call_args[0][0]
        self.assertEqual(args[:3], ["label", "create", rfs.TRACKING_LABEL])
        self.assertIn("--force", args)
        self.assertIn("lehard/dev-platform", args)

    def test_ensure_label_is_safe_to_call_repeatedly(self) -> None:
        with patch.object(rfs, "run_gh") as run_gh:
            run_gh.return_value = rfs.subprocess.CompletedProcess(["gh"], 0, "", "")
            rfs.ensure_label("lehard/dev-platform", rfs.TRACKING_LABEL)
            rfs.ensure_label("lehard/dev-platform", rfs.TRACKING_LABEL)
        self.assertEqual(run_gh.call_count, 2)

    def test_record_failure_bootstraps_both_labels_before_finding_the_issue(self) -> None:
        calls: list[str] = []

        def fake_run_gh(args: list[str]) -> "rfs.subprocess.CompletedProcess[str]":
            calls.append(args[0] if args[0] != "label" else f"label:{args[2]}")
            if args[:2] == ["issue", "create"]:
                return rfs.subprocess.CompletedProcess(["gh"], 0, "https://example.invalid/issues/1\n", "")
            return rfs.subprocess.CompletedProcess(["gh"], 0, "", "")

        with patch.object(rfs, "run_gh", side_effect=fake_run_gh), \
             patch.object(rfs, "find_tracking_issue", return_value=None) as find_issue:
            args = argparse.Namespace(
                repository="lehard/cuby", version="v1.4.21", category="unknown",
                reason="unsupported gh flag", last_updated="2026-08-11T00:00:00Z",
                threshold=3, tracker_repo="lehard/dev-platform", summary_output=None,
            )
            self.assertEqual(rfs.cmd_record_failure(args), 0)
        self.assertEqual(calls[0], f"label:{rfs.TRACKING_LABEL}")
        self.assertEqual(calls[1], f"label:{rfs.ALERT_LABEL}")
        self.assertLess(calls.index(f"label:{rfs.TRACKING_LABEL}"), calls.index("issue"))
        find_issue.assert_called_once()

    def test_missing_label_failure_does_not_crash_tracking_or_change_outcome(self) -> None:
        def fake_run_gh(args: list[str]) -> "rfs.subprocess.CompletedProcess[str]":
            if args[:2] == ["label", "create"]:
                raise rfs.TrackerError("gh label create failed: HTTP 403")
            raise AssertionError("should not reach further gh calls once label bootstrap fails")

        with patch.object(rfs, "run_gh", side_effect=fake_run_gh):
            args = argparse.Namespace(
                repository="lehard/cuby", version="v1.4.21", category="unknown",
                reason="unsupported gh flag", last_updated="2026-08-11T00:00:00Z",
                threshold=3, tracker_repo="lehard/dev-platform", summary_output=None,
            )
            # Must return 0 (tracking is best-effort) and must not raise.
            self.assertEqual(rfs.cmd_record_failure(args), 0)

    def test_record_success_also_bootstraps_tracking_label_before_lookup(self) -> None:
        with patch.object(rfs, "run_gh") as run_gh, patch.object(rfs, "find_tracking_issue", return_value=None) as find_issue:
            run_gh.return_value = rfs.subprocess.CompletedProcess(["gh"], 0, "", "")
            args = argparse.Namespace(repository="lehard/cuby", version="v1.4.21", tracker_repo="lehard/dev-platform")
            self.assertEqual(rfs.cmd_record_success(args), 0)
        run_gh.assert_called_once()
        self.assertEqual(run_gh.call_args[0][0][:3], ["label", "create", rfs.TRACKING_LABEL])
        find_issue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
