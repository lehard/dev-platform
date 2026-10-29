from __future__ import annotations

import argparse
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

    def __init__(self, work, remaining=5000):
        self.work, self.remaining, self.calls = list(work), remaining, []

    def __call__(self, argv, *, env, cwd, timeout):
        self.calls.append(argv)
        if argv[1:3] == ["auth", "token"]:
            return done("tok\n")
        if argv[1:3] == ["api", "rate_limit"]:
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

    def test_render_without_gh_fails(self):
        with mock.patch.object(runner.shutil, "which", return_value=None):
            self.args.gh = str(self.args.checkout / "missing-gh")
            with self.assertRaises(runner.RunnerError):
                runner.render_plist(self.args)


if __name__ == "__main__":
    unittest.main()
