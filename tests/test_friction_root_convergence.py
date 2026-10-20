from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

agent_friction = load_platform_module("agent_friction_convergence_under_test", SCRIPT_ROOT / "agent_friction.py")

REPO = "acme/platform"
SHA = "b" * 40


def marker(seed: str) -> str:
    return agent_friction.marker_for(seed * 24)


class FakeGitHub:
    """Minimal in-memory GitHub issues/pulls API behind the `gh` seam."""

    def __init__(self) -> None:
        self.issues: dict[int, dict] = {}
        self.comments: dict[int, list[str]] = {}
        self.pulls: dict[int, dict] = {}
        self.files: dict[int, list[dict]] = {}
        self.contents: dict[str, str] = {}
        self.next_number = 100
        self.calls: list[list[str]] = []

    def add_issue(self, number: int, *, body: str, title: str | None = None, state: str = "open", labels: tuple = ("process",)) -> None:
        self.issues[number] = {
            "number": number, "state": state, "body": body, "labels": [{"name": name} for name in labels],
            "title": agent_friction.GENERATED_FRICTION_TITLE_PREFIX + "x" if title is None else title,
        }
        self.comments.setdefault(number, [])

    def friction(self, number: int, seed: str, **kwargs) -> None:
        self.add_issue(number, body=f"{marker(seed)}\n## Sanitized process friction", **kwargs)

    @staticmethod
    def fields(command: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for index, item in enumerate(command):
            if item == "-f":
                key, _, value = command[index + 1].partition("=")
                out[key] = value
        return out

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        if command[:2] == ["auth", "status"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        method = command[command.index("--method") + 1] if "--method" in command else "GET"
        endpoint = next((c for c in command[1:] if c.startswith("repos/")), "")
        path, _, query = endpoint.partition("?")
        fields = self.fields(command)
        page = int(re.search(r"(?:^|&)page=(\d+)", query).group(1)) if "&page=" in query else 1
        ok = lambda payload: subprocess.CompletedProcess(command, 0, json.dumps(payload), "")  # noqa: E731
        m = re.fullmatch(rf"repos/{REPO}/issues/(\d+)/comments", path)
        if m:
            number = int(m.group(1))
            if method == "POST":
                self.comments[number].append(fields["body"])
                return ok({})
            items = [{"body": body} for body in self.comments[number]]
            return ok(items[(page - 1) * 100:page * 100])
        m = re.fullmatch(rf"repos/{REPO}/issues/(\d+)/labels", path)
        if m:
            labels = self.issues[int(m.group(1))]["labels"]
            if not any(label["name"] == fields["labels[]"] for label in labels):
                labels.append({"name": fields["labels[]"]})
            return ok([])
        m = re.fullmatch(rf"repos/{REPO}/issues/(\d+)", path)
        if m:
            number = int(m.group(1))
            if number not in self.issues:
                return subprocess.CompletedProcess(command, 1, "", "Not Found")
            if method == "PATCH":
                if "body" in fields:
                    self.issues[number]["body"] = fields["body"]
                if "state" in fields:
                    self.issues[number]["state"] = fields["state"]
                    self.issues[number]["state_reason"] = fields.get("state_reason")
                return ok(self.issues[number])
            return ok(self.issues[number])
        if path == f"repos/{REPO}/issues" and method == "POST":
            self.next_number += 1
            self.friction(self.next_number, "c", labels=())
            self.issues[self.next_number]["title"] = fields["title"]
            self.issues[self.next_number]["body"] = fields["body"]
            self.issues[self.next_number]["labels"] = [{"name": fields["labels[]"]}]
            return ok({"number": self.next_number})
        if path == f"repos/{REPO}/issues":
            open_items = [i for i in self.issues.values() if i["state"] == "open"]
            return ok(open_items[(page - 1) * 100:page * 100])
        m = re.fullmatch(rf"repos/{REPO}/pulls/(\d+)", path)
        if m:
            return ok(self.pulls[int(m.group(1))])
        m = re.fullmatch(rf"repos/{REPO}/pulls/(\d+)/files", path)
        if m:
            items = self.files[int(m.group(1))]
            return ok(items[(page - 1) * 100:page * 100])
        m = re.fullmatch(rf"repos/{REPO}/contents/(.+)", path)
        if m:
            text = self.contents[m.group(1)]
            assert query == f"ref={SHA}", query
            return ok({"encoding": "base64", "content": base64.b64encode(text.encode()).decode()})
        raise AssertionError(f"unexpected gh call: {command}")


def make_event(event_id: str = "ev1", category: str = "later-name") -> dict:
    return {
        "id": event_id, "at": "2026-10-20T10:00:00+00:00", "scope": "project", "category": category,
        "severity": "high", "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "proposal": "prop",
    }


class ConvergenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude" / "agent-friction.jsonl"
        self.state = self.root / ".claude" / "agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        self.gh = FakeGitHub()
        for name, value in {
            "main_root": lambda: self.root,
            "log_path": lambda: self.log,
            "state_path": lambda: self.state,
            "current_worktree_root": lambda: self.root,
            "destination_for": lambda event: REPO,
            "process_label": lambda: "process",
            "gh": self.gh,
        }.items():
            patcher = mock.patch.object(agent_friction, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        which = mock.patch.object(agent_friction.shutil, "which", return_value="/usr/bin/gh")
        which.start()
        self.addCleanup(which.stop)

    def write_events(self, *events: dict) -> None:
        self.log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

    def set_route(self, event_id: str, status: str) -> None:
        self.state.write_text(json.dumps({"version": 2, "reviewed_count": 0, "checkpoints": {}, "routes": {event_id: {"status": status}}}))

    def route_of(self, event_id: str) -> dict:
        return agent_friction.read_state()["routes"][event_id]

    def mutations(self) -> list[list[str]]:
        return [c for c in self.gh.calls if "--method" in c]


class ResolveCandidateTests(ConvergenceTestCase):
    def test_same_root_attaches_marker_and_later_event_routes_directly(self) -> None:
        self.gh.friction(10, "a")
        event = make_event()
        self.write_events(event)
        self.set_route("ev1", "candidate")
        result = agent_friction.resolve_candidate("ev1", same_root=f"{REPO}#10", new_root=False, reason="same cause")
        fingerprint = agent_friction.fingerprint_for(event, REPO)
        self.assertEqual(result["issue_number"], 10)
        self.assertEqual(result["resolved_by"], "same-root")
        self.assertIn(agent_friction.marker_for(fingerprint), self.gh.issues[10]["body"])
        self.assertIn("Decision reason: same cause", self.gh.comments[10][0])
        self.assertEqual(self.route_of("ev1")["status"], "routed")
        # A later event of the same category now goes straight to issue 10.
        later = make_event("ev2")
        before = len(self.gh.issues)
        routed = agent_friction.route_event(later)
        self.assertEqual((routed["status"], routed["issue_number"]), ("routed", 10))
        self.assertEqual(len(self.gh.issues), before)
        self.assertEqual(len(self.gh.comments[10]), 2)

    def test_alias_marker_in_body_routes_event_without_new_issue(self) -> None:
        event = make_event("ev3", "alias-category")
        fingerprint = agent_friction.fingerprint_for(event, REPO)
        self.gh.add_issue(
            11, body=f"{marker('a')}\n{agent_friction.marker_for(fingerprint)}",
            title=agent_friction.GENERATED_FRICTION_TITLE_PREFIX + "root",
        )
        routed = agent_friction.route_event(event)
        self.assertEqual(routed["issue_number"], 11)
        self.assertEqual(len(self.gh.issues), 1)

    def test_same_root_rerun_after_comment_failure_posts_one_comment(self) -> None:
        self.gh.friction(10, "a")
        event = make_event()
        self.write_events(event)
        self.set_route("ev1", "candidate")
        real = self.gh.__call__
        failing = {"on": True}

        def flaky(command: list[str]):
            if failing["on"] and command[-2:-1] == ["-f"] and any(str(c).startswith("body=<!-- dev-platform-friction-resolved") for c in command) and "comments" in " ".join(command):
                self.gh.calls.append(command)
                return subprocess.CompletedProcess(command, 1, "", "boom")
            return real(command)

        with mock.patch.object(agent_friction, "gh", flaky):
            with self.assertRaisesRegex(SystemExit, "commenting on"):
                agent_friction.resolve_candidate("ev1", same_root=f"{REPO}#10", new_root=False, reason="r")
        self.assertEqual(self.route_of("ev1")["status"], "candidate")
        self.assertIn(agent_friction.marker_for(agent_friction.fingerprint_for(event, REPO)), self.gh.issues[10]["body"])
        self.assertEqual(self.gh.comments[10], [])
        failing["on"] = False
        agent_friction.resolve_candidate("ev1", same_root=f"{REPO}#10", new_root=False, reason="r")
        self.assertEqual(len(self.gh.comments[10]), 1)
        self.assertIn("dev-platform-friction-resolved:ev1", self.gh.comments[10][0])
        self.assertEqual(self.route_of("ev1")["status"], "routed")

    def test_new_root_creates_issue(self) -> None:
        event = make_event()
        self.write_events(event)
        self.set_route("ev1", "candidate")
        result = agent_friction.resolve_candidate("ev1", same_root=None, new_root=True, reason="distinct")
        self.assertEqual(result["resolved_by"], "new-root")
        created = self.gh.issues[result["issue_number"]]
        self.assertTrue(created["title"].startswith(agent_friction.GENERATED_FRICTION_TITLE_PREFIX))
        self.assertEqual(self.route_of("ev1")["issue_number"], result["issue_number"])

    def assert_refused(self, pattern: str, **kwargs) -> None:
        with self.assertRaisesRegex(SystemExit, pattern):
            agent_friction.resolve_candidate("ev1", reason="r", new_root=False, **kwargs)
        self.assertEqual(self.mutations(), [])

    def test_refuses_event_not_in_candidate_state(self) -> None:
        self.gh.friction(10, "a")
        self.write_events(make_event())
        self.set_route("ev1", "routed")
        self.assert_refused("ev1.*not in candidate", same_root=f"{REPO}#10")

    def test_refuses_unknown_event(self) -> None:
        self.write_events(make_event())
        self.assert_refused("ev1.*not in candidate", same_root=f"{REPO}#10")

    def test_refuses_closed_target(self) -> None:
        self.gh.friction(10, "a", state="closed")
        self.write_events(make_event())
        self.set_route("ev1", "candidate")
        self.assert_refused(r"acme/platform#10 is not open", same_root=f"{REPO}#10")

    def test_refuses_non_generated_target(self) -> None:
        self.gh.add_issue(10, body="plain", title="Something else")
        self.write_events(make_event())
        self.set_route("ev1", "candidate")
        self.assert_refused(r"acme/platform#10 is not a router-generated", same_root=f"{REPO}#10")

    def test_refuses_repository_mismatch(self) -> None:
        self.write_events(make_event())
        self.set_route("ev1", "candidate")
        self.assert_refused("destination repository", same_root="acme/other#10")


class MergeRootsTests(ConvergenceTestCase):
    def test_merge_moves_markers_closes_duplicates_and_rerun_is_noop(self) -> None:
        self.gh.friction(1, "a")
        self.gh.friction(2, "b")
        self.gh.friction(3, "c")
        result = agent_friction.merge_roots(f"{REPO}#1", [f"{REPO}#2", f"{REPO}#3"], "same root")
        self.assertEqual(result["closed"], [2, 3])
        for seed in "bc":
            self.assertIn(marker(seed), self.gh.issues[1]["body"])
        self.assertEqual(len(self.gh.comments[1]), 1)
        self.assertIn("#2, #3", self.gh.comments[1][0])
        for number in (2, 3):
            self.assertEqual(self.gh.issues[number]["state"], "closed")
            self.assertEqual(self.gh.issues[number]["state_reason"], "not_planned")
            self.assertIn("Duplicate of #1", self.gh.comments[number][0])
        self.gh.calls.clear()
        again = agent_friction.merge_roots(f"{REPO}#1", [f"{REPO}#2", f"{REPO}#3"], "same root")
        self.assertEqual((again["closed"], again["markers_added"], again["listed_on_target"]), ([], [], []))
        self.assertEqual(self.mutations(), [])

    def test_interrupted_run_is_completed_by_rerun(self) -> None:
        self.gh.friction(1, "a")
        self.gh.friction(2, "b")
        agent_friction.merge_roots(f"{REPO}#1", [f"{REPO}#2"], "r")
        self.gh.issues[2]["state"] = "open"  # simulate the close failing after the comment
        result = agent_friction.merge_roots(f"{REPO}#1", [f"{REPO}#2"], "r")
        self.assertEqual(result["closed"], [2])
        self.assertEqual(len(self.gh.comments[2]), 1)

    def test_invalid_targets_fail_without_changes(self) -> None:
        self.gh.friction(1, "a")
        self.gh.friction(2, "b")
        self.gh.friction(4, "d", state="closed")
        self.gh.add_issue(5, body="plain", title="Other")
        cases = [
            (f"{REPO}#4", [f"{REPO}#2"], "not open"),
            (f"{REPO}#5", [f"{REPO}#2"], "not a router-generated"),
            (f"{REPO}#1", [f"{REPO}#1"], "must not be among"),
            (f"{REPO}#1", [f"{REPO}#5"], "not a router-generated"),
            (f"{REPO}#1", [f"{REPO}#4"], "closed and was not merged"),
            (f"{REPO}#1", ["acme/other#2"], "target repository"),
            (f"{REPO}#1", [], "at least one"),
            ("bad", [f"{REPO}#2"], "valid owner/repo#N"),
        ]
        for into, dups, pattern in cases:
            with self.subTest(into=into, dups=dups):
                with self.assertRaisesRegex(SystemExit, pattern):
                    agent_friction.merge_roots(into, dups, "r")
        self.assertEqual(self.mutations(), [])


class CloseFixedTests(ConvergenceTestCase):
    def pull(self, number: int = 7, *, body: str | None = "", merged: bool = True) -> None:
        self.gh.pulls[number] = {"number": number, "merged": merged, "merge_commit_sha": SHA, "body": body}
        self.gh.files[number] = []

    def add_proposal(self, number: int, path: str, text: str, status: str = "added") -> None:
        self.gh.files[number].append({"filename": path, "status": status})
        self.gh.contents[path] = text

    def run_close(self, number: int = 7) -> dict:
        return agent_friction.close_fixed(number, REPO)

    def test_body_reference_closes_issue_with_pr_and_commit(self) -> None:
        self.gh.friction(20, "a")
        self.pull(body=f"Summary\nFixes-Friction: {REPO}#20\n")
        result = self.run_close()
        self.assertEqual(result["closed"], [20])
        self.assertEqual(self.gh.issues[20]["state"], "closed")
        self.assertEqual(self.gh.issues[20]["state_reason"], "completed")
        self.assertIn(f"PR #7 (merge commit {SHA})", self.gh.comments[20][0])

    def test_proposal_reference_and_rerun_do_not_duplicate_comment(self) -> None:
        self.gh.friction(20, "a")
        self.gh.friction(21, "b")
        self.pull()
        self.add_proposal(7, "openspec/changes/fix-it/proposal.md", f"## Why\nFixes-Friction: {REPO}#20, {REPO}#21\n")
        self.add_proposal(7, "openspec/changes/fix-it/design.md", f"Fixes-Friction: {REPO}#99\n")
        self.assertEqual(self.run_close()["closed"], [20, 21])
        self.gh.calls.clear()
        again = self.run_close()
        self.assertEqual(again["closed"], [])
        self.assertEqual(self.mutations(), [])
        self.assertEqual(len(self.gh.comments[20]), 1)

    def test_archived_proposal_is_read_and_removed_proposal_skipped(self) -> None:
        self.gh.friction(20, "a")
        self.pull()
        self.add_proposal(7, "openspec/changes/archive/2026-10-20-fix/proposal.md", f"Fixes-Friction: {REPO}#20\n")
        self.gh.files[7].append({"filename": "openspec/changes/gone/proposal.md", "status": "removed"})
        self.assertEqual(self.run_close()["closed"], [20])

    def test_no_references_closes_nothing(self) -> None:
        self.gh.friction(20, "a")
        self.pull(body=None)
        self.add_proposal(7, "openspec/changes/fix-it/proposal.md", "No refs; mid-line `Fixes-Friction: acme/platform#20` text\n")
        result = self.run_close()
        self.assertEqual((result["referenced"], result["closed"]), ([], []))
        self.assertEqual(self.gh.issues[20]["state"], "open")
        self.assertEqual(self.mutations(), [])

    def test_non_friction_reference_fails_and_closes_nothing(self) -> None:
        self.gh.friction(20, "a")
        self.gh.add_issue(30, body="plain", title="A feature request")
        self.pull(body=f"Fixes-Friction: {REPO}#20 {REPO}#30")
        with self.assertRaisesRegex(SystemExit, r"acme/platform#30 is not a router-generated"):
            self.run_close()
        self.assertEqual(self.gh.issues[20]["state"], "open")
        self.assertEqual(self.mutations(), [])

    def test_cross_repository_reference_fails(self) -> None:
        self.pull(body="Fixes-Friction: acme/other#5")
        with self.assertRaisesRegex(SystemExit, r"'acme/other#5'.*not in the pull request repository"):
            self.run_close()

    def test_malformed_reference_fails(self) -> None:
        for token in ("#20", "acme/platform#", "20", "acme/platform/20"):
            with self.subTest(token=token):
                self.pull(body=f"Fixes-Friction: {token}")
                with self.assertRaisesRegex(SystemExit, "valid owner/repo#N"):
                    self.run_close()

    def test_not_merged_pr_fails(self) -> None:
        self.pull(merged=False)
        with self.assertRaisesRegex(SystemExit, "PR #7 is not merged"):
            self.run_close()

    def test_already_closed_issue_is_untouched(self) -> None:
        self.gh.friction(20, "a", state="closed")
        self.pull(body=f"Fixes-Friction: {REPO}#20")
        self.assertEqual(self.run_close()["closed"], [])
        self.assertEqual(self.mutations(), [])
        self.assertEqual(self.gh.comments[20], [])

    def test_interrupted_close_reuses_existing_comment(self) -> None:
        self.gh.friction(20, "a")
        self.gh.comments[20].append("<!-- dev-platform-friction-closed-by:7 -->\nClosed")
        self.pull(body=f"Fixes-Friction: {REPO}#20")
        self.assertEqual(self.run_close()["closed"], [20])
        self.assertEqual(len(self.gh.comments[20]), 1)

    def test_cli_does_not_read_operator_configuration(self) -> None:
        self.gh.friction(20, "a")
        self.pull(body=f"Fixes-Friction: {REPO}#20")
        argv = ["agent_friction.py", "close-fixed", "--pr", "7", "--repo", REPO]
        out = StringIO()
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(agent_friction, "read_operator_config", side_effect=AssertionError("operator config read")),
            redirect_stdout(out),
        ):
            self.assertEqual(agent_friction.main(), 0)
        self.assertEqual(json.loads(out.getvalue())["closed"], [20])


if __name__ == "__main__":
    unittest.main()
