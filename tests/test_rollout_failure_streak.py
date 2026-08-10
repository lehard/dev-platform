from __future__ import annotations

import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
