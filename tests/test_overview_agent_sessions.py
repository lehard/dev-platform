from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template/scripts"
sys.path.insert(0, str(SCRIPTS))
from _platform_modules import load_platform_module  # noqa: E402

overview = load_platform_module("lifecycle_overview", SCRIPTS / "lifecycle_overview.py")
agent_sessions = load_platform_module("agent_sessions", SCRIPTS / "agent_sessions.py")



def setUpModule() -> None:
    # Other test modules put the source-checkout scripts/ wrappers ahead of template/scripts on sys.path.
    sys.path.insert(0, str(SCRIPTS))


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
STAMP = "2026-10-29T11:59:00Z"


def session(branch, state="working", sid="s" * 8, **extra):
    return {"provider": "claude", "session_id": sid, "pid": 7, "branch": branch, "project": "/p", "state": state,
            "state_since": STAMP, "detail": {}, "liveness": "alive", **extra}


class OverviewSessionTests(unittest.TestCase):
    def test_developer_session_after_handoff_attaches_to_the_candidate_by_branch(self):
        mine, other = session("agent/br-1-t1-x"), session("agent/other", sid="o" * 8)
        candidates = [{"number": 5, "branch": "agent/br-1-t1-x"}, {"number": 6, "branch": "agent/br-2"}]
        unattached = overview.attach_sessions({"sessions": [mine, other]}, candidates)
        self.assertEqual(candidates[0]["sessions"], [mine])
        self.assertEqual(candidates[1]["sessions"], [])
        self.assertEqual(unattached, [other])

    def test_not_configured_is_said_explicitly(self):
        with mock.patch.object(overview, "read_platform_config", return_value={}):
            self.assertEqual(overview.read_sessions(Path("."), now=NOW), {"configured": False, "sessions": []})
        result = {"bounds": {"note": "n", "merged_discovery_page": 50, "prs_without_lifecycle_record": 0},
                  "generated_at": "t", "repository": "o/r", "requirements": [], "candidates": [],
                  "agent_sessions": {"configured": False, "unattached": []}}
        self.assertIn("Sessions: not configured", overview.render(result))

    def test_partial_configuration_names_the_missing_key(self):
        with mock.patch.object(overview, "read_platform_config", return_value={"agent_sessions": {"directory": "/x"}}):
            with self.assertRaisesRegex(overview.OverviewError, "stale_after_seconds"):
                overview.read_sessions(Path("."), now=NOW)

    def test_unreadable_registry_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            section = {"directory": str(Path(tmp) / "missing"), "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            with mock.patch.object(overview, "read_platform_config", return_value={"agent_sessions": section}):
                registry = overview.read_sessions(Path("."), now=NOW)
        self.assertTrue(registry["configured"])
        self.assertIn("does not exist", registry["error"])
        result = {"bounds": {"note": "n", "merged_discovery_page": 50, "prs_without_lifecycle_record": 0},
                  "generated_at": "t", "repository": "o/r", "requirements": [], "candidates": [],
                  "agent_sessions": {**registry, "unattached": []}}
        self.assertIn("registry unreadable", overview.render(result))

    def detail_views(self, registry_config):
        """Run show_pr and show_requirement against stubbed GitHub reads and render both detail views."""
        import publication_queue as queue
        candidate = {"number": 5, "stage": "handed-off", "state": "review-pending", "head": "a" * 40, "url": "u",
                     "executor": {"activity": "not confirmed"}, "findings": [], "branch": "agent/br-1-t1-x", "chain": [],
                     "attempts": {}, "actions": []}
        requirement = {"requirement": "o/b#1", "stage": "in-development", "status": "In progress", "findings": [],
                       "candidates": [5]}
        with mock.patch.object(overview, "read_platform_config", return_value=registry_config), \
                mock.patch.object(overview, "unclaimed_threshold_minutes", return_value=30), \
                mock.patch.object(overview, "observe_candidate", return_value=dict(candidate)), \
                mock.patch.object(overview, "_observe_requirement", return_value=requirement), \
                mock.patch.object(queue, "_repo", return_value="o/r"), mock.patch.object(queue, "_pr", return_value={}), \
                mock.patch.object(queue, "_requirement_candidate_numbers", return_value=([5], None)):
            return (overview.render(overview.show_pr(Path("."), 5, now=NOW)),
                    overview.render(overview.show_requirement(Path("."), "o/b#1", now=NOW)))

    def test_detail_views_state_that_the_registry_is_not_configured(self):
        for text in self.detail_views({}):
            self.assertIn("Sessions: not configured", text)

    def test_detail_views_state_that_the_registry_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            section = {"directory": str(Path(tmp) / "missing"), "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            for text in self.detail_views({"agent_sessions": section}):
                self.assertIn("Sessions: registry unreadable", text)
                self.assertIn("does not exist", text)

    def test_detail_views_show_an_attached_session_and_no_status_line_when_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_sessions.ingest(Path(tmp), "claude", {"hook_event_name": "SessionStart", "session_id": "abc", "cwd": tmp},
                                  pid=1, now=NOW, started=lambda pid: "s")
            section = {"directory": tmp, "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            with mock.patch.object(agent_sessions, "process_started", return_value="s"), mock.patch.object(agent_sessions.os, "kill"):
                texts = self.detail_views({"agent_sessions": section})
        for text in texts:
            self.assertNotIn("Sessions:", text)

    def test_registry_sessions_are_read_through_the_platform_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            agent_sessions.ingest(state_dir, "claude", {"hook_event_name": "SessionStart", "session_id": "abc", "cwd": tmp},
                                  pid=1, now=NOW, started=lambda pid: "s")
            section = {"directory": tmp, "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            with mock.patch.object(overview, "read_platform_config", return_value={"agent_sessions": section}), \
                    mock.patch.object(agent_sessions, "process_started", return_value="s"), \
                    mock.patch.object(agent_sessions.os, "kill"):
                registry = overview.read_sessions(Path("."), now=NOW)
        self.assertEqual([s["session_id"] for s in registry["sessions"]], ["abc"])

    def test_candidate_rendering_shows_the_attached_session(self):
        item = {"number": 5, "stage": "handed-off", "state": "review-pending", "head": "a" * 40, "url": "u",
                "executor": {"activity": "not confirmed"}, "findings": [], "sessions": [session("b", "waiting-permission")]}
        text = overview.render_candidate(item, detail=False)
        self.assertIn("claude session ssssssss pid 7 [waiting-permission]", text)


if __name__ == "__main__":
    unittest.main()
