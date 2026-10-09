from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

containment = load_platform_module("delegation_containment", SCRIPTS / "delegation_containment.py")
guard = load_platform_module("delegated_write_guard", SCRIPTS / "delegated_write_guard.py")
routing = load_platform_module("model_routing", SCRIPTS / "model_routing.py")
agent_friction = load_platform_module("agent_friction", SCRIPTS / "agent_friction.py")

import test_model_routing as routing_fixtures  # noqa: E402  (module only: its TestCase classes must not be re-collected here)

git = routing_fixtures.git
DETECTION_ONLY = guard.EnforcementDecision(
    guard.EnforcementTier.DETECTION_ONLY, "detection-only:claude-shell-capable", "no proven sandbox"
)
FRICTION_EVIDENCE = "new_changes=[] disappeared_changes=[] head_moved=True enforcement_tier='native-worktree'"


def rev(repo: Path, ref: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


def utc(delta_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=delta_seconds)).isoformat()


class ReceiptSchemaTests(unittest.TestCase):
    def test_single_remote_schema_is_required(self) -> None:
        good = {"before": "a", "after": "b", "remote": "origin", "remote_main": "b",
                "origin_main": "b", "actor_worktree": "/actor", "tool": "test", "pid": 1, "at": utc()}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = containment.integration_advance_log(root)
            log.parent.mkdir()
            for key in good:
                with self.subTest(missing=key):
                    log.write_text(json.dumps({k: v for k, v in good.items() if k != key}) + "\n")
                    with self.assertRaises(containment.ContainmentError):
                        containment.read_integration_advances(root)
            log.write_text(json.dumps(good) + "\n")
            self.assertEqual(containment.read_integration_advances(root), [good])
            upstream = {k: v for k, v in good.items() if k != "origin_main"}
            upstream["remote"] = "upstream"
            log.write_text(json.dumps(upstream) + "\n")
            self.assertEqual(containment.read_integration_advances(root), [upstream])
            log.write_text(json.dumps({**upstream, "origin_main": "b"}) + "\n")
            with self.assertRaisesRegex(containment.ContainmentError, "only valid"):
                containment.read_integration_advances(root)

    def test_noop_receipt_is_rejected(self) -> None:
        with self.assertRaisesRegex(containment.ContainmentError, "actually moved"):
            containment.record_integration_advance(Path("/integration"), "a", "a",
                tool="test", actor_worktree=Path("/actor"), remote="origin")

    def test_receipt_without_posix_locking_fails_explicitly(self) -> None:
        with mock.patch.object(containment, "fcntl", None):
            with self.assertRaisesRegex(containment.ContainmentError, "POSIX fcntl locking"):
                containment.record_integration_advance(Path("/integration"), "a", "b",
                    tool="test", actor_worktree=Path("/actor"), remote="origin")

    def test_remote_argument_is_required(self) -> None:
        with self.assertRaises(TypeError):
            containment.record_integration_advance(Path("/integration"), "a", "b",
                tool="test", actor_worktree=Path("/actor"))


OWNER_APPROVAL = "Owner accepts the bounded risk of this one historical recovery"


class IntegrationRepoMixin:
    """A temporary integration repo with a registered sibling worktree and helpers to advance main."""

    def make_repo(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.integration = Path(self.tmp.name) / "integration"
        self.integration.mkdir()
        git(self.integration, "init", "-q", "-b", "main")
        git(self.integration, "config", "user.email", "advance@example.test")
        git(self.integration, "config", "user.name", "Advance Test")
        (self.integration / "README.md").write_text("base\n", encoding="utf-8")
        git(self.integration, "add", "README.md")
        git(self.integration, "commit", "-qm", "base")
        routing_fixtures.route_ready(self.integration)
        self.sibling = Path(self.tmp.name) / "sibling"
        git(self.integration, "worktree", "add", "-qb", "agent/sibling", str(self.sibling), "main")
        self.counter = 0

    def advance(self, *, remote: bool = True) -> tuple[str, str]:
        """Commit on integration main (a fast-forward as a sibling merge would be) and move origin/main with it."""
        before = rev(self.integration)
        self.counter += 1
        name = f"advance-{self.counter}.txt"
        (self.integration / name).write_text("advance\n", encoding="utf-8")
        git(self.integration, "add", name)
        git(self.integration, "commit", "-qm", f"advance {self.counter}")
        after = rev(self.integration)
        if remote:
            git(self.integration, "update-ref", "refs/remotes/origin/main", after)
        return before, after

    def receipt(self, before: str, after: str, *, actor: Path | None = None) -> dict:
        return containment.record_integration_advance(
            self.integration, before, after, tool="test", actor_worktree=actor or self.sibling, remote="origin"
        )

    def write_raw_receipts(self, *receipts: dict | str) -> None:
        log = containment.integration_advance_log(self.integration)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            for item in receipts:
                handle.write((item if isinstance(item, str) else json.dumps(item)) + "\n")


class ReceiptAndClassifierTests(IntegrationRepoMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.make_repo()
        self.delegated = Path(self.tmp.name) / "delegated"
        git(self.integration, "worktree", "add", "-qb", "agent/delegated", str(self.delegated), "main")
        self.start = rev(self.integration)
        self.window_start = utc(-5)

    def classify(self, tier: str = "detection-only", *, window_start: str | None = None, delegated: Path | None = None):
        before = containment.snapshot(self.integration)
        # The integration checkout was clean at the pre-run head.
        pre = containment.GitSnapshot(head=self.start, paths={})
        result = containment.check_containment(pre, before)
        return containment.assess_head_move(
            self.integration,
            self.start,
            before.head,
            containment=result,
            tier=tier,
            delegated_worktree=delegated or self.delegated,
            window_start=window_start or self.window_start,
        )

    def test_record_writes_a_complete_receipt_line(self) -> None:
        before, after = self.advance()
        written = self.receipt(before, after)
        lines = containment.integration_advance_log(self.integration).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        stored = json.loads(lines[0])
        self.assertEqual(stored, written)
        self.assertEqual(stored["before"], before)
        self.assertEqual(stored["after"], after)
        self.assertEqual(stored["origin_main"], after)
        self.assertEqual(stored["actor_worktree"], str(self.sibling.resolve()))
        self.assertEqual(stored["tool"], "test")
        self.assertIsInstance(stored["pid"], int)
        self.assertIsNotNone(datetime.fromisoformat(stored["at"]).tzinfo)

    def test_non_origin_receipt_is_unverified_even_when_origin_matches(self) -> None:
        before, after = self.advance()
        git(self.integration, "update-ref", "refs/remotes/upstream/main", after)
        receipt = containment.record_integration_advance(
            self.integration, before, after, tool="test", actor_worktree=self.sibling, remote="upstream"
        )
        self.assertEqual((receipt["remote"], receipt["remote_main"]), ("upstream", after))
        self.assertNotIn("origin_main", receipt)
        self.assertFalse(self.classify().verified)

    def test_record_records_the_origin_main_as_read_at_that_moment(self) -> None:
        before, after = self.advance(remote=False)
        git(self.integration, "update-ref", "refs/remotes/origin/main", before)
        self.assertEqual(self.receipt(before, after)["origin_main"], before)

    def test_record_fails_explicitly_without_origin_main(self) -> None:
        before = rev(self.integration)
        git(self.integration, "update-ref", "-d", "refs/remotes/origin/main")
        (self.integration / "x.txt").write_text("x\n", encoding="utf-8")
        git(self.integration, "add", "x.txt")
        git(self.integration, "commit", "-qm", "x")
        with self.assertRaises(containment.ContainmentError):
            self.receipt(before, rev(self.integration))
        self.assertFalse(containment.integration_advance_log(self.integration).exists())

    def test_record_fails_explicitly_when_the_log_cannot_be_written(self) -> None:
        before, after = self.advance()
        (self.integration / ".claude").mkdir(exist_ok=True)
        containment.integration_advance_log(self.integration).mkdir()  # a directory where the log file must go
        with self.assertRaisesRegex(containment.ContainmentError, "receipt could not be written"):
            self.receipt(before, after)

    def test_record_refuses_a_non_move(self) -> None:
        head = rev(self.integration)
        with self.assertRaisesRegex(containment.ContainmentError, "actually moved"):
            self.receipt(head, head)

    def test_sibling_chain_is_verified_for_detection_only(self) -> None:
        first = self.advance()
        self.receipt(*first)
        second = self.advance()
        self.receipt(*second)
        assessment = self.classify()
        self.assertTrue(assessment.verified, assessment.reason)
        self.assertEqual([r["after"] for r in assessment.evidence["receipts"]], [first[1], second[1]])
        pure = containment.check_containment(
            containment.GitSnapshot(self.start, {}), containment.GitSnapshot(second[1], {})
        )
        evidence = containment.classify_head_move(
            self.integration, self.start, second[1], containment=pure,
            tier="detection-only", delegated_worktree=self.delegated, window_start=self.window_start,
        )
        self.assertEqual(evidence["after"], second[1])

    def test_detection_only_without_a_receipt_is_a_violation(self) -> None:
        self.advance()
        assessment = self.classify()
        self.assertFalse(assessment.verified)
        self.assertIn("no verified receipt chain", assessment.reason)

    def test_hard_tier_needs_no_receipt(self) -> None:
        self.advance()
        self.assertTrue(self.classify("hard").verified)

    def test_broken_chain_is_a_violation(self) -> None:
        self.advance()  # head moved once with no receipt
        second = self.advance()
        self.receipt(*second)
        self.assertFalse(self.classify().verified)

    def test_chain_ending_short_of_the_current_head_is_a_violation(self) -> None:
        first = self.advance()
        self.receipt(*first)
        self.advance()
        self.assertFalse(self.classify().verified)

    def test_receipt_from_the_delegated_worktree_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after, actor=self.delegated)
        self.assertIn("delegated worktree", self.classify().reason)

    def test_receipt_from_inside_the_delegated_worktree_is_a_violation(self) -> None:
        before, after = self.advance()
        inner = self.delegated / "nested"
        inner.mkdir()
        self.receipt(before, after, actor=inner)
        self.assertFalse(self.classify().verified)

    def test_receipt_older_than_the_delegation_window_is_ignored(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        self.assertFalse(self.classify(window_start=utc(+60)).verified)

    def test_receipt_that_did_not_land_on_its_recorded_origin_main_is_a_violation(self) -> None:
        before, after = self.advance()
        self.write_raw_receipts(
            {"before": before, "after": after, "origin_main": before, "remote": "origin", "remote_main": before, "actor_worktree": str(self.sibling), "tool": "t", "pid": 1, "at": utc()}
        )
        self.assertFalse(self.classify().verified)

    def test_head_that_differs_from_origin_main_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        git(self.integration, "update-ref", "refs/remotes/origin/main", before)
        self.assertFalse(self.classify().verified)
        self.assertFalse(self.classify("hard").verified)

    def test_non_fast_forward_is_a_violation(self) -> None:
        tree = git_output(self.integration, "write-tree")
        unrelated = git_output(self.integration, "commit-tree", tree, "-m", "unrelated")
        git(self.integration, "reset", "-q", "--hard", unrelated)
        git(self.integration, "update-ref", "refs/remotes/origin/main", unrelated)
        self.receipt(self.start, unrelated)
        self.assertFalse(self.classify().verified)

    def test_path_change_with_head_move_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        (self.integration / "escape.txt").write_text("escaped\n", encoding="utf-8")
        assessment = self.classify()
        self.assertFalse(assessment.verified)
        self.assertIn("paths", assessment.reason)

    def test_malformed_receipt_logs_are_violations(self) -> None:
        before, after = self.advance()
        good = self.receipt(before, after)
        for bad in ("not json", json.dumps([1]), json.dumps({**good, "pid": "x"}), json.dumps({**good, "at": "nope"}),
                    json.dumps({k: v for k, v in good.items() if k != "tool"}),
                    json.dumps({**good, "at": "2026-01-01T00:00:00"})):
            with self.subTest(bad=bad):
                self.write_raw_receipts(bad)
                assessment = self.classify()
                self.assertFalse(assessment.verified)
                log = containment.integration_advance_log(self.integration)
                log.write_text(json.dumps(good) + "\n", encoding="utf-8")

    def test_unknown_tier_is_an_explicit_error(self) -> None:
        self.advance()
        with self.assertRaises(containment.ContainmentError):
            self.classify("whatever")

    def test_detection_only_requires_window_and_worktree(self) -> None:
        self.advance()
        result = containment.check_containment(
            containment.GitSnapshot(self.start, {}), containment.GitSnapshot(rev(self.integration), {})
        )
        with self.assertRaises(containment.ContainmentError):
            containment.assess_head_move(self.integration, self.start, rev(self.integration), containment=result, tier="detection-only")

    def test_guard_classification_constants_agree(self) -> None:
        self.assertEqual(guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE, containment.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)

    def test_codex_classification_is_unchanged(self) -> None:
        before, after = self.advance()
        pre = containment.GitSnapshot(self.start, {})
        result = containment.check_containment(pre, containment.GitSnapshot(after, {}))
        classify = guard._classify_containment
        self.assertEqual(classify(result, guard.EnforcementTier.HARD, self.integration, before, after), guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        self.assertEqual(classify(result, guard.EnforcementTier.DETECTION_ONLY, self.integration, before, after), guard.CLASSIFICATION_VIOLATION)
        git(self.integration, "update-ref", "refs/remotes/origin/main", before)
        self.assertEqual(classify(result, guard.EnforcementTier.HARD, self.integration, before, after), guard.CLASSIFICATION_VIOLATION)
        paths = containment.GitSnapshot(after, {"x.txt": containment.PathState("??", "f")})
        mutated = containment.check_containment(pre, paths)
        git(self.integration, "update-ref", "refs/remotes/origin/main", after)
        self.assertEqual(classify(mutated, guard.EnforcementTier.HARD, self.integration, before, after), guard.CLASSIFICATION_VIOLATION)


def git_output(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


class ClaudeRoutingFixture(IntegrationRepoMixin):
    """The Claude routing record on top of the shared integration repo."""

    def setUp(self) -> None:
        self.make_repo()
        # Same task worktree layout as the routing test fixtures, built on this integration repo.
        self.task = Path(self.tmp.name) / "task"
        git(self.integration, "worktree", "add", "-qb", "agent/routing", str(self.task), "main")
        change = self.task / "openspec" / "changes" / "routing-change"
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(
            json.dumps({"source_issue": "owner/backlog#7", "change": "routing-change"}), encoding="utf-8"
        )
        (self.task / ".dev-platform.toml").write_text('main_branch = "main"\n', encoding="utf-8")
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(
            routing, "determine_claude_tier", return_value=DETECTION_ONLY
        ):
            routing.prepare_claude_handoff(
                self.task, profile="standard", rationale="bounded current-spec preflight",
                evidence=["openspec/changes/routing-change"],
            )
        self.pre_head = rev(self.integration)
        routing.begin_claude_delegation(self.task)

    def record_path(self) -> Path:
        return self.task / ".claude" / "model-routing" / "routing-change.json"

    def saved(self) -> dict:
        return json.loads(self.record_path().read_text(encoding="utf-8"))

    def record(self):
        with patch.object(routing, "main_root", return_value=self.integration), patch.object(
            routing, "determine_claude_tier", return_value=DETECTION_ONLY
        ):
            return routing.record_claude_execution(self.task, agent_id="agent-1", summary="child work")

    def record_expecting_violation(self, pattern: str = "containment violation") -> None:
        with patch.object(routing, "record_containment_friction") as friction:
            with self.assertRaisesRegex(routing.RoutingError, pattern):
                self.record()
        friction.assert_called_once()
        saved = self.saved()
        self.assertIsNone(saved["execution"])
        self.assertEqual(saved["execution_plan"]["delegation"]["state"], "open")


class ClaudeRecordingTests(ClaudeRoutingFixture, unittest.TestCase):
    def test_sibling_merge_with_receipt_is_recorded_as_a_verified_advance(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        execution = self.record()
        self.assertEqual(execution["postcheck"]["containment"], "clean")
        advance = execution["postcheck"]["integration_advance"]
        self.assertEqual(advance["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        self.assertEqual((advance["before"], advance["after"]), (before, after))
        self.assertEqual(advance["receipts"][0]["actor_worktree"], str(self.sibling.resolve()))
        self.assertTrue(advance["raw_observation"]["head_moved"])
        self.assertEqual(self.saved()["execution_plan"]["delegation"]["state"], "closed")
        # The terminal gate accepts the recorded execution.
        with patch.object(routing, "main_root", return_value=self.integration):
            routing.require_routing_gate(self.task, "owner/backlog#7", "routing-change")

    def test_normal_parallel_merge_needs_no_owner_input(self) -> None:
        # A sibling lifecycle fast-forwards integration main while the Claude delegation is open: the platform
        # verifies it from receipts alone, with no recovery, owner approval or friction event.
        before, after = self.advance()
        self.receipt(before, after)
        with patch.object(routing, "record_containment_friction") as friction:
            execution = self.record()
        friction.assert_not_called()
        self.assertEqual(execution["postcheck"]["integration_advance"]["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        self.assertNotIn("historical_recovery", execution)
        self.assertNotIn("owner_approval", json.dumps(self.saved()))

    def test_several_sibling_merges_form_a_verified_chain(self) -> None:
        first = self.advance()
        self.receipt(*first)
        second = self.advance()
        self.receipt(*second)
        advance = self.record()["postcheck"]["integration_advance"]
        self.assertEqual((advance["before"], advance["after"]), (first[0], second[1]))
        self.assertEqual(len(advance["receipts"]), 2)

    def test_no_head_movement_records_no_advance(self) -> None:
        self.assertNotIn("integration_advance", self.record()["postcheck"])

    def test_missing_receipt_is_a_violation(self) -> None:
        self.advance()
        self.record_expecting_violation("not accepted as a verified concurrent advance")

    def test_integration_path_change_is_a_violation_even_with_a_receipt(self) -> None:
        self.receipt(*self.advance())
        (self.integration / "escape.txt").write_text("escaped\n", encoding="utf-8")
        self.record_expecting_violation("escape.txt")

    def test_non_fast_forward_is_a_violation(self) -> None:
        tree = git_output(self.integration, "write-tree")
        unrelated = git_output(self.integration, "commit-tree", tree, "-m", "unrelated")
        git(self.integration, "reset", "-q", "--hard", unrelated)
        git(self.integration, "update-ref", "refs/remotes/origin/main", unrelated)
        self.receipt(self.pre_head, unrelated)
        self.record_expecting_violation()

    def test_head_that_differs_from_origin_main_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        git(self.integration, "update-ref", "refs/remotes/origin/main", before)
        self.record_expecting_violation()

    def test_broken_chain_is_a_violation(self) -> None:
        self.advance()
        self.receipt(*self.advance())
        self.record_expecting_violation()

    def test_receipt_from_the_delegated_worktree_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after, actor=self.task)
        self.record_expecting_violation("names the delegated worktree")

    def test_malformed_receipt_log_is_a_violation(self) -> None:
        before, after = self.advance()
        self.receipt(before, after)
        self.write_raw_receipts("{broken")
        self.record_expecting_violation("malformed")

    def test_receipt_older_than_the_delegation_is_a_violation(self) -> None:
        before, after = self.advance()
        self.write_raw_receipts(
            {"before": before, "after": after, "origin_main": after, "remote": "origin", "remote_main": after, "actor_worktree": str(self.sibling), "tool": "t", "pid": 1,
             "at": utc(-3600)}
        )
        self.record_expecting_violation()


class ClaudeRecoveryTests(ClaudeRoutingFixture, unittest.TestCase):
    """Bounded Claude form of `recover-external-advance` for a violation recorded before receipts existed."""

    def setUp(self) -> None:
        super().setUp()
        self.opened_at = self.saved()["execution_plan"]["delegation"]["opened_at"]
        self.worktree = self.saved()["task_worktree"]
        time.sleep(1.1)  # the reflog window starts at the whole-second delegation opening
        self.first = self.advance()  # the historical false violation: no receipt was written for it

    def friction(self, **overrides) -> str:
        entry = {
            "id": "claude-event-1",
            "at": utc(),
            "category": "delegated-write-containment-violation",
            "task": "owner/backlog#7",
            "observation": f"Delegated write containment violation: changes appeared outside assigned worktree {self.worktree}. "
            "Integration HEAD moved during delegation (something was committed there).",
            "evidence": FRICTION_EVIDENCE,
        }
        entry.update(overrides)
        log = self.integration / ".claude" / "agent-friction.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        return entry["id"]

    def recover(self, **kwargs):
        arguments = {"friction_event": "claude-event-1", "before_head": self.pre_head, "after_head": rev(self.integration),
                     "owner_approval": OWNER_APPROVAL}
        arguments.update(kwargs)
        with patch.object(agent_friction, "main_root", return_value=self.integration):
            return routing.recover_external_advance(self.task, **arguments)

    def assert_refused(self, pattern: str, **kwargs) -> None:
        before = self.record_path().read_bytes()
        with self.assertRaisesRegex(routing.RoutingError, pattern):
            self.recover(**kwargs)
        self.assertEqual(self.record_path().read_bytes(), before)

    def test_recovery_stores_a_record_on_the_open_delegation_without_an_execution(self) -> None:
        self.friction()
        recovery = self.recover()
        # An owner risk acceptance, never recorded as a machine-verified advance.
        self.assertEqual(recovery["classification"], routing.CLASSIFICATION_OWNER_AUTHORIZED_RECOVERY)
        self.assertNotEqual(recovery["classification"], guard.CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE)
        self.assertIs(recovery["verified"], False)
        self.assertEqual(recovery["owner_approval"]["approval"], OWNER_APPROVAL)
        saved = self.saved()
        self.assertIsNone(saved["execution"])
        delegation = saved["execution_plan"]["delegation"]
        self.assertEqual(delegation["state"], "open")
        self.assertEqual(delegation["recovery"]["after_head"], self.first[1])
        self.assertEqual(delegation["recovery"]["before_head"], self.pre_head)
        self.assertEqual(delegation["recovery"]["friction_event"], "claude-event-1")
        self.assertFalse((self.integration / ".claude" / "model-routing" / "routing-change.json").exists())

    def test_recovery_to_the_current_head_after_several_later_unreceipted_advances(self) -> None:
        self.friction()
        self.advance()
        self.advance()
        current = rev(self.integration)
        recovery = self.recover(after_head=current)
        self.assertEqual(recovery["after_head"], current)
        execution = self.record()
        self.assertEqual(execution["postcheck"]["containment"], "clean")
        self.assertNotIn("integration_advance", execution["postcheck"])

    def test_recovery_without_owner_approval_refuses_without_writing(self) -> None:
        self.friction()
        for approval in (None, "", "   "):
            with self.subTest(approval=approval):
                self.assert_refused("requires --owner-approval", owner_approval=approval)

    def test_owner_approval_is_refused_for_codex_recovery(self) -> None:
        self.friction()
        with patch.object(routing, "_read_route", return_value=(routing.Route(**{**self.saved(), "provider": "codex"}), self.record_path())):
            with self.assertRaisesRegex(routing.RoutingError, "applies only to the Claude historical recovery"):
                self.recover()

    def test_execution_after_recovery_keeps_the_owner_authorized_base_apart(self) -> None:
        self.friction()
        self.recover()
        execution = self.record()
        self.assertEqual(execution["historical_recovery"]["classification"], routing.CLASSIFICATION_OWNER_AUTHORIZED_RECOVERY)
        self.assertNotIn("integration_advance", execution["postcheck"])

    def test_recording_after_recovery_starts_from_the_recovered_head(self) -> None:
        self.friction()
        self.recover()
        # Further movement after the recovery is classified only through receipts.
        later = self.advance()
        self.record_expecting_violation()
        self.receipt(*later)
        advance = self.record()["postcheck"]["integration_advance"]
        self.assertEqual((advance["before"], advance["after"]), later)

    def test_receipts_at_or_before_friction_refuse_without_writing(self) -> None:
        event_time = datetime.fromisoformat(utc())
        self.friction(at=event_time.isoformat())
        receipt = self.receipt(*self.first)
        log = containment.integration_advance_log(self.integration)
        for at in ((event_time - timedelta(hours=1)).isoformat(), event_time.isoformat()):
            with self.subTest(at=at):
                log.write_text(json.dumps({**receipt, "at": at}) + "\n", encoding="utf-8")
                self.assert_refused("does not predate integration advance receipts")

    def test_self_attributed_receipts_after_friction_refuse_without_writing(self) -> None:
        event_time = datetime.fromisoformat(utc())
        self.friction(at=event_time.isoformat())
        recovery_time = (event_time + timedelta(seconds=10)).isoformat()
        log = containment.integration_advance_log(self.integration)
        for actor in (self.task, self.task / "nested"):
            for seconds in (1, 10):
                with self.subTest(actor=actor, seconds=seconds):
                    receipt = self.receipt(*self.first, actor=actor)
                    log.write_text(json.dumps({**receipt, "at": (event_time + timedelta(seconds=seconds)).isoformat()}) + "\n", encoding="utf-8")
                    with patch.object(routing, "utc_now", return_value=recovery_time):
                        self.assert_refused("names the delegated worktree")

    def test_later_sibling_receipt_allows_historical_recovery(self) -> None:
        event_time = datetime.fromisoformat(utc())
        self.friction(at=event_time.isoformat())
        receipt = self.receipt(*self.first)
        log = containment.integration_advance_log(self.integration)
        log.write_text(json.dumps({**receipt, "at": (event_time + timedelta(seconds=1)).isoformat()}) + "\n", encoding="utf-8")
        with patch.object(routing, "utc_now", return_value=(event_time + timedelta(seconds=10)).isoformat()):
            self.recover()

    def test_malformed_receipts_refuse_recovery_without_writing(self) -> None:
        self.friction()
        self.write_raw_receipts("{broken")
        self.assert_refused("invalid integration advance receipts")

    def test_recovery_is_not_repeatable(self) -> None:
        self.friction()
        self.recover()
        self.assert_refused("already has a recorded recovery")

    def test_path_change_refuses(self) -> None:
        self.friction()
        (self.integration / "escape.txt").write_text("escaped\n", encoding="utf-8")
        self.assert_refused("integration paths changed")

    def test_unknown_friction_event_refuses(self) -> None:
        self.assert_refused("no machine-local friction event")

    def test_friction_for_another_task_refuses(self) -> None:
        self.friction(task="owner/backlog#99")
        self.assert_refused("does not identify this exact managed task")

    def test_friction_with_another_category_refuses(self) -> None:
        self.friction(category="something-else")
        self.assert_refused("not a delegated-write-containment-violation")

    def test_friction_for_another_worktree_refuses(self) -> None:
        self.friction(observation="unrelated worktree")
        self.assert_refused("exact assigned worktree")

    def test_friction_with_prose_evidence_refuses(self) -> None:
        self.friction(evidence="the head moved, trust me")
        self.assert_refused("structured containment format")

    def test_friction_with_path_changes_refuses(self) -> None:
        self.friction(evidence="new_changes=['x'] disappeared_changes=[] head_moved=True enforcement_tier='native-worktree'")
        self.assert_refused("pure integration-head move")

    def test_friction_without_head_move_refuses(self) -> None:
        self.friction(evidence="new_changes=[] disappeared_changes=[] head_moved=False enforcement_tier='native-worktree'")
        self.assert_refused("pure integration-head move")

    def test_friction_before_the_delegation_opened_refuses(self) -> None:
        self.friction(at="2000-01-01T00:00:00+00:00")
        self.assert_refused("predates the open delegation")

    def test_friction_without_a_timestamp_refuses(self) -> None:
        self.friction(at=None)
        self.assert_refused("no timezone-aware time")

    def test_wrong_before_head_refuses(self) -> None:
        self.friction()
        self.assert_refused("does not match this route's recorded pre-execution head", before_head="0" * 40)

    def test_after_head_that_is_not_the_current_head_refuses(self) -> None:
        self.friction()
        self.advance()
        self.assert_refused("not the current integration head", after_head=self.first[1])

    def test_after_head_equal_to_before_head_refuses(self) -> None:
        self.friction()
        self.assert_refused("no head movement", after_head=self.pre_head)

    def test_after_head_that_is_not_the_remote_tracking_main_refuses(self) -> None:
        self.friction()
        git(self.integration, "update-ref", "refs/remotes/origin/main", self.pre_head)
        self.assert_refused("remote-tracking main")

    def test_after_head_missing_from_the_reflog_window_refuses(self) -> None:
        self.friction(at=utc(+7200))
        # origin/main is moved without ever passing through the window start: force the window to exclude it.
        payload = self.saved()
        payload["execution_plan"]["delegation"]["opened_at"] = utc(+3600)
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        self.assert_refused("cannot prove")

    def test_closed_delegation_refuses(self) -> None:
        self.friction()
        payload = self.saved()
        payload["execution_plan"]["delegation"].update(
            {"state": "closed", "closed_at": utc(), "task_content_post": payload["execution_plan"]["task_content_pre"]}
        )
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        self.assert_refused("open Claude delegation")

    def test_existing_execution_refuses(self) -> None:
        self.friction()
        payload = self.saved()
        payload["execution"] = {"outcome": "claimed"}
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")
        self.assert_refused("already has execution evidence")


if __name__ == "__main__":
    unittest.main()
