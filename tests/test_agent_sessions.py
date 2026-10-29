from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module  # noqa: E402

sessions = load_platform_module("agent_sessions", ROOT / "template" / "scripts" / "agent_sessions.py")

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
SESSION = "11111111-aaaa-bbbb-cccc-222222222222"


class RegistryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.cwd = self.dir / "work"
        self.cwd.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "agent/br-1-t1-x", str(self.cwd)], check=True)
        subprocess.run(["git", "-C", str(self.cwd), "-c", "user.email=t@example.test", "-c", "user.name=T", "commit",
                        "-q", "--allow-empty", "-m", "base"], check=True)

    def send(self, name, *, at=0, **fields):
        event = {"hook_event_name": name, "session_id": SESSION, "cwd": str(self.cwd), **fields}
        return sessions.ingest(self.dir, "claude", event, pid=os.getpid(), now=NOW + timedelta(seconds=at),
                               started=lambda pid: "start-1")

    def test_normal_turn_with_permission_wait(self):
        self.assertEqual(self.send("SessionStart")["state"], "idle")
        self.assertEqual(self.send("UserPromptSubmit", at=1)["state"], "working")
        self.assertEqual(self.send("PreToolUse", at=2, tool_name="Bash")["state"], "working")
        waiting = self.send("PermissionRequest", at=3, tool_name="Bash")
        self.assertEqual((waiting["state"], waiting["detail"]), ("waiting-permission", {"tool": "Bash"}))
        self.assertEqual(self.send("PostToolUse", at=4, tool_name="Bash")["state"], "working")
        self.assertEqual(self.send("Stop", at=5)["state"], "idle")
        self.assertEqual(self.send("SessionEnd", at=6, reason="logout")["state"], "ended")

    def test_permission_wait_survives_another_tools_events(self):
        self.send("SessionStart")
        self.send("PermissionRequest", at=1, tool_name="Edit")
        self.assertEqual(self.send("PostToolUse", at=2, tool_name="Read")["state"], "waiting-permission")
        self.assertEqual(self.send("PreToolUse", at=3, tool_name="Grep")["state"], "waiting-permission")
        record = self.send("PostToolUse", at=4, tool_name="Edit")
        self.assertEqual(record["state"], "working")
        self.assertEqual(record["state_since"], (NOW + timedelta(seconds=4)).isoformat(timespec="seconds").replace("+00:00", "Z"))

    def test_questions_notifications_and_limit(self):
        self.send("SessionStart")
        self.assertEqual(self.send("PreToolUse", at=1, tool_name="AskUserQuestion")["state"], "waiting-input")
        self.assertEqual(self.send("PostToolUse", at=2, tool_name="AskUserQuestion")["state"], "working")
        self.assertEqual(self.send("Notification", at=3, notification_type="idle_prompt")["state"], "waiting-input")
        self.assertEqual(self.send("Notification", at=4, notification_type="permission_prompt")["state"], "waiting-permission")
        failed = self.send("StopFailure", at=5, error="rate_limit")
        self.assertEqual((failed["state"], failed["detail"]), ("limit-or-error", {"error": "rate_limit"}))

    def test_context_is_recorded_and_unknown_event_is_an_error(self):
        record = self.send("SessionStart")
        self.assertEqual((record["branch"], record["pid"], record["pid_started"]), ("agent/br-1-t1-x", os.getpid(), "start-1"))
        self.assertEqual(record["task"], "work")
        with self.assertRaisesRegex(sessions.SessionError, "unknown Claude Code hook event 'Bogus'"):
            self.send("Bogus")

    def test_unsafe_session_id_and_missing_state_dir_fail(self):
        with self.assertRaisesRegex(sessions.SessionError, "not a safe file name"):
            sessions.ingest(self.dir, "claude", {"hook_event_name": "Stop", "session_id": "../x"}, pid=1)
        with self.assertRaisesRegex(sessions.SessionError, "does not exist"):
            sessions.ingest(self.dir / "none", "claude", {"hook_event_name": "Stop", "session_id": "a"}, pid=1)

    def test_start_time_is_refreshed_when_the_same_pid_now_has_another_start_time(self):
        self.send("SessionStart")
        event = {"hook_event_name": "Stop", "session_id": SESSION, "cwd": str(self.cwd)}
        record = sessions.ingest(self.dir, "claude", event, pid=os.getpid(), now=NOW + timedelta(seconds=1),
                                 started=lambda pid: "start-2")
        self.assertEqual((record["pid"], record["pid_started"]), (os.getpid(), "start-2"))
        same = sessions.ingest(self.dir, "claude", event, pid=os.getpid(), now=NOW + timedelta(seconds=2),
                               started=lambda pid: "start-2")
        self.assertEqual(same["pid_started"], "start-2")

    def test_codex_reports_only_turn_complete(self):
        record = sessions.ingest(self.dir, "codex", {"type": "agent-turn-complete", "thread-id": "t1", "cwd": str(self.cwd)},
                                 pid=os.getpid(), now=NOW, started=lambda pid: "s")
        self.assertEqual(record["state"], "idle")
        with self.assertRaisesRegex(sessions.SessionError, "only agent-turn-complete"):
            sessions.ingest(self.dir, "codex", {"type": "agent-turn-start", "thread-id": "t1"}, pid=1, now=NOW)

    def test_corrupt_record_raises_naming_the_file(self):
        self.send("SessionStart")
        (self.dir / f"claude-{SESSION}.json").write_text("{nope")
        with self.assertRaisesRegex(sessions.SessionError, "unreadable"):
            self.send("Stop", at=1)


class LivenessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def record(self, state="working", pid=os.getpid(), started="s1", updated=NOW):
        stamp = updated.isoformat(timespec="seconds").replace("+00:00", "Z")
        sessions._write(self.dir / "claude-a.json", {
            "version": 1, "provider": "claude", "session_id": "a", "pid": pid, "pid_started": started, "state": state,
            "state_since": stamp, "updated_at": stamp, "last_event": "x", "detail": {}, "branch": "b", "project": "p"})

    def listed(self, probe, now=NOW, stale=3600, keep=3600):
        return sessions.list_sessions(self.dir, now=now, stale_after=stale, ended_keep=keep, probe=probe)

    def test_killed_session_without_session_end_is_ended(self):
        self.record(pid=999999)
        with mock.patch.object(sessions.os, "kill", side_effect=ProcessLookupError):
            item = self.listed(lambda pid: "s1")[0]
        self.assertEqual((item["state"], item["detail"]), ("ended", {"reason": "process-gone"}))

    def test_reused_pid_is_ended_but_matching_start_is_alive(self):
        self.record()
        self.assertEqual(self.listed(lambda pid: "other")[0]["state"], "ended")
        self.assertEqual(self.listed(lambda pid: "s1")[0]["state"], "working")

    def test_failed_check_never_ends_a_live_session(self):
        self.record()

        def broken(pid):
            raise sessions.SessionError("ps unavailable")
        item = self.listed(broken)[0]
        self.assertEqual((item["state"], item["liveness"]), ("working", "unknown"))
        with mock.patch.object(sessions.os, "kill", side_effect=OSError("odd")):
            self.assertEqual(self.listed(lambda pid: "s1")[0]["liveness"], "unknown")

    def test_silent_session_is_unknown_not_working(self):
        self.record(updated=NOW - timedelta(hours=3))
        item = self.listed(lambda pid: "s1")[0]
        self.assertEqual(item["state"], "unknown")
        self.assertEqual(item["detail"]["last_state"], "working")
        self.assertIn("silent for 180 min", item["detail"]["reason"])

    def test_ended_sessions_are_hidden_after_retention_and_files_stay(self):
        self.record(state="ended", updated=NOW - timedelta(hours=2))
        self.assertEqual(self.listed(lambda pid: "s1"), [])
        self.assertTrue((self.dir / "claude-a.json").exists())


class HookCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_hook(self, payload, state_dir=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(sys, "stdin", io.StringIO(payload)):
            code = sessions.main(["hook", "--provider", "claude", "--state-dir", str(state_dir or self.dir)])
        return code, out.getvalue(), err.getvalue()

    def test_success_prints_nothing(self):
        code, out, err = self.run_hook(json.dumps({"hook_event_name": "Stop", "session_id": "a", "cwd": str(self.dir)}))
        self.assertEqual((code, out, err), (0, "", ""))

    def test_failures_are_non_blocking_and_explicit(self):
        for payload, state_dir in (("not json", None), (json.dumps({"hook_event_name": "Stop", "session_id": "a"}), self.dir / "gone")):
            code, out, err = self.run_hook(payload, state_dir)
            self.assertEqual((code, out), (1, ""))
            self.assertIn("agent sessions:", err)

    def test_broken_hook_arguments_do_not_use_the_blocking_exit_code(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sessions.main(["hook", "--provider", "claude"]), 1)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings = self.dir / "settings.json"
        self.script = Path("/x/agent_sessions.py")
        self.state = self.dir / "state"

    def test_install_is_idempotent_keeps_foreign_hooks_and_removes_cleanly(self):
        foreign = {"matcher": "Write", "hooks": [{"type": "command", "command": "other"}]}
        self.settings.write_text(json.dumps({"model": "x", "hooks": {"PreToolUse": [foreign]}}))
        self.assertEqual(sessions.edit_settings(self.settings, self.script, self.state, remove=False), "changed")
        self.assertEqual(sessions.edit_settings(self.settings, self.script, self.state, remove=False), "unchanged")
        data = json.loads(self.settings.read_text())
        self.assertEqual(set(data["hooks"]), set(sessions.CLAUDE_EVENTS))
        self.assertEqual(data["hooks"]["PreToolUse"][0], foreign)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)
        self.assertEqual(sessions.edit_settings(self.settings, self.script, self.state, remove=True), "changed")
        self.assertEqual(json.loads(self.settings.read_text()), {"model": "x", "hooks": {"PreToolUse": [foreign]}})

    def test_malformed_settings_and_conflicting_hooks_are_refused(self):
        self.settings.write_text("{bad")
        with self.assertRaisesRegex(sessions.SessionError, "not valid JSON"):
            sessions.edit_settings(self.settings, self.script, self.state, remove=False)
        self.settings.write_text("{}")
        sessions.edit_settings(self.settings, self.script, self.state, remove=False)
        with self.assertRaisesRegex(sessions.SessionError, "already has different session hooks"):
            sessions.edit_settings(self.settings, self.script, self.dir / "other-state", remove=False)

    def test_print_writes_nothing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sessions.main(["hooks", "--state-dir", str(self.state), "--print"]), 0)
        self.assertEqual(set(json.loads(out.getvalue())["hooks"]), set(sessions.CLAUDE_EVENTS))
        self.assertFalse(self.settings.exists())

    def test_install_needs_a_named_settings_file(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sessions.main(["hooks", "--state-dir", str(self.state), "--install"]), 2)


class SourceWrapperTests(unittest.TestCase):
    def test_source_checkout_wrapper_runs_the_template_script(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "agent_sessions.py"), "list", "--help"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: agent_sessions.py list", result.stdout)


if __name__ == "__main__":
    unittest.main()
