from __future__ import annotations

import argparse
import contextlib
import io
import fcntl
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import post_merge_runner as runner  # noqa: E402


def done(out="", err="", code=0):
    return subprocess.CompletedProcess([], code, out, err)


class FakeRun:
    """Dispatches on argv: gh auth token, gh api rate_limit, work-next."""

    def __init__(self, work, remaining=5000, on_rate=None):
        self.work, self.remaining, self.calls, self.timeouts, self.on_rate = list(work), remaining, [], [], on_rate

    def __call__(self, argv, *, env, cwd, timeout):
        self.calls.append(argv)
        self.timeouts.append(timeout)
        if argv[1:3] == ["auth", "token"]:
            return done("tok\n")
        if argv[1:3] == ["api", "rate_limit"]:
            if self.on_rate:
                self.on_rate()
            value = self.remaining.pop(0) if isinstance(self.remaining, list) else self.remaining
            return done(json.dumps({"resources": {"core": {"remaining": value, "reset": 1}}}))
        item = self.work.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def job(status, number=1, kind="retrospective", outcome="done"):
    return done(json.dumps({"status": status, "job": {"number": number, "kind": kind},
                            "execution": {"status": "done", "outcome": outcome}}))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        (base / "co/scripts").mkdir(parents=True)
        (base / "co/scripts/lifecycle_workers.py").write_text("")
        (base / "journal").mkdir()
        self.args = argparse.Namespace(repo="o/r", checkout=base / "co", journal_dir=base / "journal", gh="gh",
                                       min_rest_remaining=1000, max_jobs=5, max_seconds=100, claim_ttl=900)

    def events(self):
        return runner.read_records(self.args.journal_dir)

    def round(self, fake):
        with mock.patch.object(runner.shutil, "which", return_value="/usr/bin/gh"):
            return runner.run_round(self.args, run=fake)

    def test_chain_runs_until_idle_and_is_journaled(self):
        fake = FakeRun([job("claimed", 7, "retrospective"), job("claimed", 7, "terminal-reconciliation"),
                        job("claimed", 7, "cleanup"), done(json.dumps({"status": "idle", "job": None}))])
        self.assertEqual(self.round(fake), 0)
        events = self.events()
        self.assertEqual([e["event"] for e in events], ["round-start"] + ["work-next"] * 4 + ["round-end"])
        self.assertEqual([e["kind"] for e in events[1:4]], ["retrospective", "terminal-reconciliation", "cleanup"])
        self.assertEqual(events[-1]["jobs"], 3)
        self.assertEqual(events[-1]["outcome"], "idle")
        work = [c for c in fake.calls if "work-next" in c][0]
        self.assertIn("--run", work)
        self.assertEqual(work[work.index("--kinds") + 1], runner.KINDS)

    def test_max_jobs_bounds_the_round(self):
        self.args.max_jobs = 2
        self.assertEqual(self.round(FakeRun([job("claimed")] * 3)), 0)
        self.assertEqual(self.events()[-1]["outcome"], "max-jobs")

    def test_low_remainder_skips_at_start_and_between_runs(self):
        self.assertEqual(self.round(FakeRun([], remaining=10)), 0)
        low = [e for e in self.events() if e["event"] == "rest-low"]
        self.assertEqual((low[0]["remaining"], low[0]["threshold"]), (10, 1000))
        self.assertEqual(self.events()[-1]["outcome"], "skipped-low-rest")
        fake = FakeRun([job("claimed")], remaining=[5000, 10])
        self.assertEqual(self.round(fake), 0)
        self.assertEqual(sum(1 for e in self.events() if e["event"] == "work-next"), 1)

    def test_first_failure_stops_and_fails(self):
        fake = FakeRun([done(err="boom", code=2), job("claimed")])
        self.assertEqual(self.round(fake), 1)
        end = self.events()[-1]
        self.assertEqual(end["outcome"], "failed")
        self.assertIn("boom", end["error"])
        self.assertEqual(len(fake.work), 1)

    def test_unparsable_result_and_timeout_fail(self):
        self.assertEqual(self.round(FakeRun([done("not json")])), 1)
        self.assertEqual(self.round(FakeRun([runner.RunnerError("work-next exceeded 900s and was killed")])), 1)

    def test_overlapping_round_is_skipped(self):
        with open(self.args.journal_dir / runner.LOCK_NAME, "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            fake = FakeRun([])
            self.assertEqual(self.round(fake), 0)
        self.assertEqual(self.events()[0]["reason"], "previous round still running")
        self.assertEqual(fake.calls, [])

    def test_interrupted_previous_round_is_journaled(self):
        runner.append_record(self.args.journal_dir, {"event": "round-start", "round": "dead"})
        self.assertEqual(self.round(FakeRun([done(json.dumps({"status": "idle", "job": None}))])), 0)
        self.assertEqual(self.events()[1]["event"], "interrupted-previous-round")
        self.assertEqual(self.events()[1]["interrupted"], "dead")

    def test_missing_configuration_fails_before_running(self):
        for field, value in (("repo", "bad"), ("journal_dir", self.args.journal_dir / "none"), ("max_jobs", 0),
                             ("checkout", self.args.checkout / "none")):
            args = argparse.Namespace(**{**vars(self.args), field: value})
            with self.assertRaises(runner.RunnerError):
                runner.validate(args)

    def test_relative_paths_are_rejected_naming_the_argument(self):
        for field in ("checkout", "journal_dir"):
            args = argparse.Namespace(**{**vars(self.args), field: Path("relative")})
            with self.assertRaisesRegex(runner.RunnerError, f"--{field.replace('_', '-')} must be an absolute path"):
                runner.validate(args)

    def test_run_timeout_is_bounded_by_the_round_deadline(self):
        clock = [0.0]
        self.args.max_seconds, self.args.claim_ttl = 100, 900
        fake = FakeRun([job("claimed"), done(json.dumps({"status": "idle", "job": None}))],
                       on_rate=lambda: clock.__setitem__(0, clock[0] + 40))
        with mock.patch.object(runner.shutil, "which", return_value="/usr/bin/gh"):
            runner.run_round(self.args, run=fake, monotonic=lambda: clock[0])
        work_timeouts = [t for c, t in zip(fake.calls, fake.timeouts) if "work-next" in c]
        self.assertEqual(work_timeouts[0], 60)

    def test_no_time_left_ends_the_round_without_a_run(self):
        clock = [0.0]
        self.args.max_seconds = 100
        fake = FakeRun([], on_rate=lambda: clock.__setitem__(0, clock[0] + 200))
        with mock.patch.object(runner.shutil, "which", return_value="/usr/bin/gh"):
            self.assertEqual(runner.run_round(self.args, run=fake, monotonic=lambda: clock[0]), 0)
        self.assertEqual(self.events()[-1]["outcome"], "max-seconds")
        self.assertFalse(any("work-next" in c for c in fake.calls))

    def test_unwritable_lock_is_an_explicit_error(self):
        self.args.journal_dir = self.args.journal_dir / "gone"
        self.args.journal_dir.mkdir()
        (self.args.journal_dir / runner.LOCK_NAME).mkdir()  # a directory cannot be opened as the lock file
        with mock.patch.object(runner.shutil, "which", return_value="/usr/bin/gh"):
            with self.assertRaisesRegex(runner.RunnerError, "lock file"):
                runner.run_round(self.args, run=FakeRun([]))

    def test_missing_token_fails_explicitly(self):
        def bad(argv, *, env, cwd, timeout):
            return done(err="not logged in", code=1)
        self.assertEqual(self.round(bad), 1)
        self.assertIn("gh auth token failed", self.events()[-1]["error"])

    def test_corrupt_journal_raises_with_line(self):
        (self.args.journal_dir / runner.JOURNAL_NAME).write_text("{}\nnope\n")
        with self.assertRaisesRegex(runner.RunnerError, "line 2"):
            runner.read_records(self.args.journal_dir)

    def test_plist_is_explicit_and_in_interval(self):
        with mock.patch.object(runner.shutil, "which", side_effect=lambda n: f"/opt/bin/{n}"):
            data = plistlib.loads(runner.render_plist(self.args))
        self.assertEqual(data["Label"], runner.LABEL)
        self.assertTrue(600 <= data["StartInterval"] <= 900)
        self.assertTrue(data["RunAtLoad"])
        arguments = data["ProgramArguments"]
        self.assertEqual(arguments[arguments.index("--gh") + 1], "/opt/bin/gh")
        self.assertIn("--min-rest-remaining", arguments)
        self.assertTrue(data["EnvironmentVariables"]["PATH"].startswith("/opt/bin"))

    def test_plist_path_has_sbin_dirs_for_lsof_without_duplicates(self):
        with mock.patch.object(runner.shutil, "which", side_effect=lambda n: f"/usr/sbin/{n}"):
            data = plistlib.loads(runner.render_plist(self.args))
        entries = data["EnvironmentVariables"]["PATH"].split(":")
        self.assertEqual(entries, ["/usr/sbin", "/usr/bin", "/bin", "/sbin"])
        with mock.patch.object(runner.shutil, "which", side_effect=lambda n: f"/opt/bin/{n}"):
            entries = plistlib.loads(runner.render_plist(self.args))["EnvironmentVariables"]["PATH"].split(":")
        self.assertEqual(entries, ["/opt/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"])

    def test_render_without_gh_fails(self):
        with mock.patch.object(runner.shutil, "which", return_value=None):
            self.args.gh = str(self.args.checkout / "missing-gh")
            with self.assertRaises(runner.RunnerError):
                runner.render_plist(self.args)


class LaunchAgentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        (base / "co/scripts").mkdir(parents=True)
        (base / "co/scripts/lifecycle_workers.py").write_text("")
        (base / "journal").mkdir()
        self.plist = base / "LaunchAgents" / f"{runner.LABEL}.plist"
        self.argv = ["--repo", "o/r", "--checkout", str(base / "co"), "--journal-dir", str(base / "journal"),
                     "--gh", "/usr/bin/gh", "--min-rest-remaining", "1000", "--max-jobs", "5",
                     "--max-seconds", "100", "--claim-ttl", "900"]
        for patcher in (mock.patch.object(runner, "agent_path", return_value=self.plist),
                        mock.patch.object(runner.sys, "platform", "darwin"),
                        mock.patch.object(runner.shutil, "which", side_effect=lambda n: f"/opt/bin/{n}")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def launchctl(self, loaded=True, bootout=0, bootstrap=0):
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv[:2])
            if argv[1] == "print":
                return subprocess.CompletedProcess(argv, 0 if loaded else 1, "", "")
            if argv[1] == "bootout":
                return subprocess.CompletedProcess(argv, bootout, "", "Boot-out failed: 5")
            if bootstrap:
                raise subprocess.CalledProcessError(bootstrap, argv, "", "Bootstrap failed: 5")
            return subprocess.CompletedProcess(argv, 0, "", "")
        return calls, fake

    def test_print_writes_and_loads_nothing(self):
        calls, fake = self.launchctl()
        with mock.patch.object(runner.subprocess, "run", fake):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(runner.main(["launchagent", "--print", *self.argv]), 0)
        self.assertIn(runner.LABEL, out.getvalue())
        self.assertEqual(calls, [])
        self.assertFalse(self.plist.exists())

    def test_removal_keeps_the_plist_when_unload_fails(self):
        self.plist.parent.mkdir()
        self.plist.write_bytes(b"agent")
        calls, fake = self.launchctl(loaded=True, bootout=5)
        with mock.patch.object(runner.subprocess, "run", fake):
            with self.assertRaisesRegex(runner.RunnerError, "unload failed, plist kept: Boot-out failed: 5"):
                runner.remove_agent()
        self.assertTrue(self.plist.exists())

    def test_removal_unloads_then_deletes(self):
        self.plist.parent.mkdir()
        self.plist.write_bytes(b"agent")
        calls, fake = self.launchctl(loaded=True)
        with mock.patch.object(runner.subprocess, "run", fake):
            runner.remove_agent()
        self.assertEqual(calls, [["launchctl", "print"], ["launchctl", "bootout"]])
        self.assertFalse(self.plist.exists())

    def test_bootstrap_failure_names_the_unloaded_agent_and_plist(self):
        calls, fake = self.launchctl(loaded=True, bootstrap=5)
        with mock.patch.object(runner.subprocess, "run", fake):
            with self.assertRaises(runner.RunnerError) as caught:
                runner.install_agent(argparse.Namespace(
                    repo="o/r", checkout=Path(self.argv[3]), journal_dir=Path(self.argv[5]), gh="/usr/bin/gh",
                    min_rest_remaining=1000, max_jobs=5, max_seconds=100, claim_ttl=900))
        message = str(caught.exception)
        self.assertIn("Bootstrap failed: 5", message)
        self.assertIn("already unloaded", message)
        self.assertIn(str(self.plist), message)
        self.assertTrue(self.plist.exists())


if __name__ == "__main__":
    unittest.main()
