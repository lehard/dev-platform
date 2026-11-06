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
    def test_not_configured_is_said_explicitly(self):
        with mock.patch.object(overview, "read_platform_config", return_value={}):
            self.assertEqual(overview.read_sessions(Path("."), now=NOW), {"configured": False, "sessions": []})
        result = {"generated_at": "t", "backlog": "o/b", "requirements": [],
                  "agent_sessions": {"configured": False, "sessions": []},
                  "owner_needed": {"configured": False, "signals": []}}
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
        result = {"generated_at": "t", "backlog": "o/b", "requirements": [], "agent_sessions": registry,
                  "owner_needed": {"configured": False, "signals": []}}
        self.assertIn("registry unreadable", overview.render(result))

    def detail_view(self, registry_config):
        """Run show_requirement against a stubbed GitHub read and render the detail view."""
        requirement = {"requirement": "o/b#1", "stage": "in-development", "status": "In progress", "findings": []}
        with mock.patch.object(overview, "read_platform_config", return_value=registry_config), \
                mock.patch.object(overview, "_observe_requirement", return_value=requirement):
            return overview.render(overview.show_requirement(Path("."), "o/b#1", now=NOW))

    def test_detail_view_states_that_the_registry_is_not_configured(self):
        self.assertIn("Sessions: not configured", self.detail_view({}))

    def test_detail_view_states_that_the_registry_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            section = {"directory": str(Path(tmp) / "missing"), "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            text = self.detail_view({"agent_sessions": section})
        self.assertIn("Sessions: registry unreadable", text)
        self.assertIn("does not exist", text)

    def test_detail_view_shows_a_session_and_no_status_line_when_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_sessions.ingest(Path(tmp), "claude", {"hook_event_name": "SessionStart", "session_id": "abc", "cwd": tmp},
                                  pid=1, now=NOW, started=lambda pid: "s")
            section = {"directory": tmp, "stale_after_seconds": 3600, "ended_keep_seconds": 3600}
            with mock.patch.object(agent_sessions, "process_started", return_value="s"), mock.patch.object(agent_sessions.os, "kill"):
                text = self.detail_view({"agent_sessions": section})
        self.assertNotIn("Sessions: not configured", text)
        self.assertNotIn("Sessions: registry unreadable", text)
        self.assertIn("claude session abc", text)

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

    def test_session_rendering_shows_state_branch_and_project(self):
        text = overview.render({"generated_at": "t", "backlog": "o/b", "requirements": [],
                                "agent_sessions": {"configured": True, "sessions": [session("b", "waiting-permission")]},
                                "owner_needed": {"configured": False, "signals": []}})
        self.assertIn("claude session ssssssss pid 7 [waiting-permission]", text)
        self.assertIn("branch=b project=/p", text)


if __name__ == "__main__":
    unittest.main()
