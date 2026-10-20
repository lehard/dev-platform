from __future__ import annotations

import json
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

agent_friction = load_platform_module("agent_friction_strict_under_test", SCRIPT_ROOT / "agent_friction.py")


def event(event_id: str | None = "e1", *, scope: str = "platform", at: str = "2026-08-11T10:00:00+00:00") -> dict:
    record = {
        "at": at, "scope": scope, "category": "repeated-error", "severity": "high", "triggers": ["repeated-error"],
        "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "proposal": "prop",
    }
    if event_id is not None:
        record["id"] = event_id
    return record


class StrictFrictionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude" / "agent-friction.jsonl"
        self.state = self.root / ".claude" / "agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        for name, value in {
            "main_root": lambda: self.root,
            "log_path": lambda: self.log,
            "state_path": lambda: self.state,
            "current_branch": lambda: "test-branch",
            "current_worktree_root": lambda: self.root,
            "current_head": lambda root: "a" * 40,
            "current_task_content": lambda root: None,
        }.items():
            patcher = mock.patch.object(agent_friction, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_lines(self, *lines: str) -> None:
        self.log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- routing destination -------------------------------------------------

    def test_platform_event_without_promotion_repo_stays_pending_and_never_hits_origin(self) -> None:
        calls: list[list[str]] = []

        def fake_gh(command: list[str]):
            calls.append(command)
            return mock.Mock(returncode=0, stdout="[]", stderr="")

        with (
            mock.patch.object(agent_friction.shutil, "which", return_value="/usr/bin/gh"),
            mock.patch.object(agent_friction, "gh", fake_gh),
            mock.patch.object(agent_friction, "read_operator_config", return_value={}),
            mock.patch.object(agent_friction, "origin_repository", side_effect=AssertionError("origin must not be used")),
        ):
            result = agent_friction.route_event(event("route-me"))
        self.assertEqual(result["status"], "pending")
        self.assertIn("[promotion].repo", result["detail"])
        self.assertEqual([c for c in calls if c[:1] == ["api"]], [])
        self.assertEqual(agent_friction.read_state()["routes"]["route-me"]["status"], "pending")

    def test_platform_repository_requires_promotion_repo(self) -> None:
        with mock.patch.object(agent_friction, "read_operator_config", return_value={"promotion": {"repo": "  "}}):
            with self.assertRaisesRegex(RuntimeError, r"\[promotion\]\.repo"):
                agent_friction.platform_repository()
        with mock.patch.object(agent_friction, "read_operator_config", side_effect=RuntimeError("operator configuration is not enabled")):
            with self.assertRaisesRegex(RuntimeError, "not enabled"):
                agent_friction.platform_repository()
        with mock.patch.object(agent_friction, "read_operator_config", return_value={"promotion": {"repo": "Ops/Friction"}}):
            self.assertEqual(agent_friction.platform_repository(), "ops/friction")
            self.assertEqual(agent_friction.destination_for(event()), "ops/friction")

    def test_process_label_propagates_read_errors_and_rejects_invalid_values(self) -> None:
        with mock.patch.object(agent_friction, "read_platform_config", side_effect=ValueError("bad toml")):
            with self.assertRaisesRegex(ValueError, "bad toml"):
                agent_friction.process_label()
        for bad in ("", "   ", 7):
            with mock.patch.object(agent_friction, "read_platform_config", return_value={"process_health": {"process_label": bad}}):
                with self.assertRaisesRegex(RuntimeError, r"process_health\.process_label"):
                    agent_friction.process_label()
        with mock.patch.object(agent_friction, "read_platform_config", return_value={}):
            self.assertEqual(agent_friction.process_label(), "process")
        with mock.patch.object(agent_friction, "read_platform_config", return_value={"process_health": {"process_label": " a  b "}}):
            self.assertEqual(agent_friction.process_label(), "a b")

    # --- strict log ------------------------------------------------------------

    def test_malformed_lines_raise_with_path_and_line(self) -> None:
        good = json.dumps(event("ok"))
        for bad, text in ((  "{not json", "invalid JSON"), ("[1]", "not a JSON object"),
                          (json.dumps({"id": "x"}), "'at'"), (json.dumps({"id": "x", "at": "nope"}), "'at'")):
            self.write_lines(good, bad)
            with self.assertRaises(agent_friction.FrictionLogError) as ctx:
                agent_friction.read_events()
            self.assertIn(f"{self.log}:2", str(ctx.exception))
            self.assertIn(text, str(ctx.exception))
            self.assertEqual(agent_friction.evidence_source_status()["friction-log"], "partial")

    def test_unreadable_log_raises_naming_path(self) -> None:
        self.log.write_bytes(b"\xff\xfe\x00bad")
        with self.assertRaises(agent_friction.FrictionLogError) as ctx:
            agent_friction.read_events()
        self.assertIn(str(self.log), str(ctx.exception))
        self.assertEqual(agent_friction.evidence_source_status()["friction-log"], "unreadable")
        with agent_friction.tolerate_local_gap():
            self.assertEqual(agent_friction.read_events(), [])

    def test_status_checks_the_whole_log(self) -> None:
        self.write_lines("{broken", *[json.dumps(event(f"e{i}")) for i in range(600)])
        self.assertEqual(agent_friction.evidence_source_status()["friction-log"], "partial")

    def test_tolerant_context_skips_only_invalid_lines(self) -> None:
        self.write_lines(json.dumps(event("a")), "{broken", json.dumps(event("b")))
        with self.assertRaises(agent_friction.FrictionLogError):
            agent_friction.read_events()
        with agent_friction.tolerate_local_gap():
            self.assertEqual([e["id"] for e in agent_friction.read_events()], ["a", "b"])

    def test_checkpoint_needs_accepted_friction_log_gap(self) -> None:
        self.write_lines(json.dumps(event("a")), "{broken")
        kwargs = dict(event_ids=[], review_note="Reviewed the actual path.", bind_content=False)
        with self.assertRaises(agent_friction.FrictionLogError):
            agent_friction.record_checkpoint("test-branch", self.root, **kwargs)
        recorded = agent_friction.record_checkpoint("test-branch", self.root, accepted_gaps=["friction-log"], **kwargs)
        self.assertEqual(recorded["accepted_gaps"], ["friction-log"])
        # the same acceptance covers later completion validation, a missing one does not
        agent_friction.require_checkpoint("test-branch", self.root)
        state = agent_friction.read_state()
        state["checkpoints"]["test-branch"]["accepted_gaps"] = []
        agent_friction.atomic_write_json(self.state, state)
        with self.assertRaises(agent_friction.FrictionLogError):
            agent_friction.require_checkpoint("test-branch", self.root)

    def test_review_path_reports_the_gap_instead_of_failing(self) -> None:
        self.write_lines(json.dumps(event("a")), "{broken")
        out = StringIO()
        with (
            mock.patch.object(agent_friction, "changed_paths", return_value=[]),
            mock.patch.object(agent_friction, "review_guidance", return_value={}),
            redirect_stdout(out),
        ):
            self.assertEqual(agent_friction.cmd_review_path(type("Args", (), {"task": "test-branch"})()), 0)
        self.assertEqual(json.loads(out.getvalue())["evidence_sources"], {"friction-log": "partial"})

    # --- legacy identities -----------------------------------------------------

    def test_legacy_id_is_content_derived_and_stable_across_appends(self) -> None:
        legacy = json.dumps(event(None))
        self.write_lines(legacy)
        first = agent_friction.read_events()[0]["id"]
        self.assertRegex(first, r"^legacy-[0-9a-f]{16}$")
        self.write_lines(json.dumps(event("new", at="2026-08-12T10:00:00+00:00")), "", legacy)
        ids = [e["id"] for e in agent_friction.read_events()]
        self.assertEqual(ids, ["new", first])

    def test_positional_references_resolve_to_content_id(self) -> None:
        legacy = json.dumps(event(None))
        self.write_lines(json.dumps(event("own")), "", legacy)  # legacy is physical line 3 (blank line counts)
        content_id = agent_friction.read_events()[1]["id"]
        self.state.write_text(json.dumps({"version": 2, "reviewed_count": 0, "routes": {"legacy-3": {"status": "routed"}},
                                          "checkpoints": {}}), encoding="utf-8")
        self.assertEqual(list(agent_friction.read_state()["routes"]), [content_id])
        attributions = agent_friction.attributions_path()
        attributions.write_text(json.dumps({"id": "legacy-3", "task": "o/r#5", "reason": "x", "at": "t"}) + "\n", encoding="utf-8")
        self.assertEqual(list(agent_friction.read_attributions()), [content_id])
        # the append-only file is not rewritten and the CLI accepts the content id
        self.assertIn('"legacy-3"', attributions.read_text(encoding="utf-8"))
        self.assertEqual(agent_friction.attribute_event(content_id, "o/r#5", "same")["task"], "o/r#5")

    def test_unresolved_positional_reference_is_a_named_error(self) -> None:
        self.write_lines(json.dumps(event("own")), json.dumps(event(None)))
        for position in ("legacy-1", "legacy-9"):  # line with its own id; missing line
            self.state.write_text(json.dumps({"version": 2, "reviewed_count": 0, "routes": {position: {}},
                                              "checkpoints": {}}), encoding="utf-8")
            with self.assertRaises(agent_friction.FrictionLogError) as ctx:
                agent_friction.read_state()
            self.assertIn(position, str(ctx.exception))
            self.assertIn(str(self.log), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
