"""Coverage for the human-facing Business Requirement intake/linkage/aggregation surface.

gh CLI calls are mocked at the same seams tests/test_managed_task.py already
uses (managed_task.run / managed_task.github_cli_env), since
requirement_intake.py composes managed_task.py's own helpers rather than
reimplementing GitHub I/O.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"
# Always insert at position 0, even if already present elsewhere on
# sys.path: several test modules prepend the bare scripts/ directory (whose
# shims execute unconditionally on import), and a merely-conditional insert
# here can leave template/scripts shadowed behind it depending on discovery
# order.
sys.path.insert(0, str(TEMPLATE_SCRIPTS))

import managed_project_status  # noqa: E402
import requirement_intake as ri  # noqa: E402


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def init_repo() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")
    return temporary


class RenderParseTests(unittest.TestCase):
    def test_round_trip_recovers_every_section_and_empty_children(self) -> None:
        body = ri.render_requirement_body(
            outcome="Make onboarding self-serve.",
            target_repository="acme/billing",
            context="Support currently onboards every client by hand.",
            acceptance_evidence="A new client can self-serve within one business day.",
            exclusions="Does not cover enterprise SSO.",
        )
        parsed = ri.parse_requirement_body(body)
        self.assertEqual(parsed["sections"]["outcome"], "Make onboarding self-serve.")
        self.assertEqual(parsed["sections"]["context"], "Support currently onboards every client by hand.")
        self.assertEqual(parsed["sections"]["target repository"], "`acme/billing`")
        self.assertEqual(parsed["sections"]["exclusions"], "Does not cover enterprise SSO.")
        self.assertEqual(parsed["children"], [])

    def test_optional_sections_may_be_omitted(self) -> None:
        body = ri.render_requirement_body(outcome="Ship X.", target_repository="acme/billing")
        parsed = ri.parse_requirement_body(body)
        self.assertEqual(set(parsed["sections"]), {"outcome", "target repository"})

    def test_parse_recognizes_indented_children(self) -> None:
        """Regression: a GitHub-UI hand-edit can indent a checklist item;
        parsing must still recognize it as an existing child so link_child
        does not append a duplicate entry for it."""
        body = (
            "## Outcome\n\nShip X.\n\n"
            f"{ri.CHILDREN_START}\n  - [ ] acme/repo#20\n{ri.CHILDREN_END}\n"
        )
        parsed = ri.parse_requirement_body(body)
        self.assertEqual(parsed["children"], ["acme/repo#20"])

    def test_parse_recognizes_sections_placed_after_the_children_block(self) -> None:
        """Regression: the children block's HTML-comment markers are
        invisible in the rendered Issue, so a human may add or move a
        section after it; that section must still be recognized."""
        body = (
            "## Outcome\n\nShip X.\n\n"
            f"{ri.CHILDREN_START}\n- [ ] acme/repo#20\n{ri.CHILDREN_END}\n\n"
            "## Exclusions\n\nDoes not cover enterprise SSO.\n"
        )
        parsed = ri.parse_requirement_body(body)
        self.assertEqual(parsed["sections"]["exclusions"], "Does not cover enterprise SSO.")
        self.assertEqual(parsed["children"], ["acme/repo#20"])

    def test_render_rejects_empty_outcome(self) -> None:
        with self.assertRaises(ri.RequirementIntakeError):
            ri.render_requirement_body(outcome="   ", target_repository="acme/billing")

    def test_parse_reads_existing_children(self) -> None:
        body = (
            "## Outcome\n\nShip X.\n\n"
            f"{ri.CHILDREN_START}\n- [ ] acme/billing#12\n- [x] acme/billing#13\n{ri.CHILDREN_END}\n"
        )
        parsed = ri.parse_requirement_body(body)
        self.assertEqual(parsed["children"], ["acme/billing#12", "acme/billing#13"])

    def test_parse_tolerates_a_body_with_no_children_block(self) -> None:
        parsed = ri.parse_requirement_body("## Outcome\n\nShip X.\n")
        self.assertEqual(parsed["children"], [])


class CreateRequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_issues_gh_issue_create_with_the_requirement_label(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            if command[:3] == ["gh", "issue", "create"]:
                return type("Result", (), {"stdout": "https://github.com/acme/development-backlog/issues/42\n", "returncode": 0})()
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "run", side_effect=fake_run),
        ):
            payload = ri.create_requirement(
                self.root, repository="acme/development-backlog", title="Make onboarding self-serve",
                outcome="Make onboarding self-serve.", target_repository="acme/billing",
            )
        self.assertEqual(payload, {"repository": "acme/development-backlog", "number": 42, "slug": "requirement-42"})
        create_command = next(command for command in commands if command[:3] == ["gh", "issue", "create"])
        self.assertIn(ri.REQUIREMENT_LABEL, create_command)
        label_command = next(command for command in commands if command[:3] == ["gh", "label", "create"])
        self.assertIn(ri.REQUIREMENT_LABEL, label_command)

    def test_create_rejects_blank_title(self) -> None:
        with patch.object(ri, "github_cli_env", return_value={}):
            with self.assertRaises(ri.RequirementIntakeError):
                ri.create_requirement(
                    self.root, repository="acme/development-backlog", title="   ",
                    outcome="Ship X.", target_repository="acme/billing",
                )


class StartPreAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.base_dir = self.root / ".claude" / "pre-authoring"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_bridges_a_requirement_issue_into_orchestrator_init(self) -> None:
        body = (
            "## Outcome\n\nMake onboarding self-serve.\n\n"
            "## Context\n\nSupport currently onboards every client by hand.\n\n"
            "## Acceptance evidence\n\nA new client can self-serve within one business day.\n\n"
            "## Target repository\n\n`acme/billing`\n\n"
            "## Exclusions\n\nDoes not cover enterprise SSO.\n\n"
            f"{ri.CHILDREN_START}\n{ri.CHILDREN_END}\n"
        )
        with patch.object(ri, "fetch_issue", return_value={"body": body}):
            payload = ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
        self.assertEqual(payload["slug"], "requirement-7")
        directory = ri.orchestrate_pre_authoring.requirement_dir(self.base_dir, "requirement-7")
        self.assertFalse(ri.orchestrate_pre_authoring.add_path(directory).exists())
        self.assertEqual(payload["state"]["target_repository"], "acme/billing")
        context = json.loads((directory / "requirement.json").read_text(encoding="utf-8"))
        self.assertEqual(context, {
            "version": ri.REQUIREMENT_CONTEXT_VERSION,
            "outcome": "Make onboarding self-serve.",
            "context": "Support currently onboards every client by hand.",
            "acceptance_evidence": "A new client can self-serve within one business day.",
            "exclusions": "Does not cover enterprise SSO.",
            "target_repository": "acme/billing",
        })
        self.assertEqual(payload["state"]["business_context_file"], str(directory / "requirement.json"))

    def test_start_normalizes_formatting_only_edits_without_rebuilding(self) -> None:
        initial = (
            "## Outcome\n\nMake onboarding self-serve.\n\n"
            "## Context\n\nSupport onboards every client by hand.\n\n"
            "## Acceptance evidence\n\nA client self-serves in one business day.\n\n"
            "## Target repository\n\n`acme/billing`\n\n"
            "## Exclusions\n\nNo enterprise SSO.\n"
        )
        reformatted = (
            "## Outcome\n\n Make   onboarding\n self-serve. \n\n"
            "## Context\n\nSupport   onboards every\nclient by hand.\n\n"
            "## Acceptance evidence\n\nA client self-serves in one business day.\n\n"
            "## Target repository\n\n acme/billing \n\n"
            "## Exclusions\n\nNo enterprise SSO.\n"
        )
        with patch.object(ri, "fetch_issue", return_value={"body": initial}):
            first = ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
        directory = ri.orchestrate_pre_authoring.requirement_dir(self.base_dir, "requirement-7")
        add_file = ri.orchestrate_pre_authoring.add_path(directory)
        add_file.write_text('{"preserved": true}\n', encoding="utf-8")
        snapshot_file = ri.orchestrate_pre_authoring.snapshot_path(directory)
        snapshot_file.write_text('{"preserved": "snapshot"}\n', encoding="utf-8")
        intents_file = ri.orchestrate_pre_authoring.intents_path(directory)
        intents_file.write_text('{"preserved": "intents"}\n', encoding="utf-8")
        handoff_file = ri.orchestrate_pre_authoring.handoff_dir(directory) / "intent.json"
        handoff_file.parent.mkdir()
        handoff_file.write_text('{"preserved": "handoff"}\n', encoding="utf-8")
        with patch.object(ri, "fetch_issue", return_value={"body": reformatted}):
            second = ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
        self.assertEqual(first["state"], second["state"])
        self.assertEqual(add_file.read_text(encoding="utf-8"), '{"preserved": true}\n')
        self.assertEqual(snapshot_file.read_text(encoding="utf-8"), '{"preserved": "snapshot"}\n')
        self.assertEqual(intents_file.read_text(encoding="utf-8"), '{"preserved": "intents"}\n')
        self.assertEqual(handoff_file.read_text(encoding="utf-8"), '{"preserved": "handoff"}\n')

    def test_start_rebuilds_add_and_later_artifacts_for_each_changed_business_value(self) -> None:
        initial = (
            "## Outcome\n\nMake onboarding self-serve.\n\n"
            "## Context\n\nSupport onboards every client by hand.\n\n"
            "## Acceptance evidence\n\nA client self-serves in one business day.\n\n"
            "## Target repository\n\n`acme/billing`\n\n"
            "## Exclusions\n\nNo enterprise SSO.\n"
        )
        replacements = {
            "Outcome": "Launch guided onboarding.",
            "Context": "Sales onboards every client by hand.",
            "Acceptance evidence": "A client self-serves within one hour.",
            "Target repository": "`acme/accounts`",
            "Exclusions": "No enterprise SCIM.",
        }
        for section, replacement in replacements.items():
            with self.subTest(section=section):
                base_dir = self.root / ".claude" / f"pre-authoring-{section.replace(' ', '-') }"
                with patch.object(ri, "fetch_issue", return_value={"body": initial}):
                    ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=base_dir)
                directory = ri.orchestrate_pre_authoring.requirement_dir(base_dir, "requirement-7")
                snapshot = ri.orchestrate_pre_authoring.snapshot_path(directory)
                snapshot.write_text('{"snapshot": "retained"}\n', encoding="utf-8")
                add_file = ri.orchestrate_pre_authoring.add_path(directory)
                add_file.write_text('{"stale": "add"}\n', encoding="utf-8")
                ri.orchestrate_pre_authoring.intents_path(directory).write_text('{"stale": "intents"}\n', encoding="utf-8")
                handoff = ri.orchestrate_pre_authoring.handoff_dir(directory) / "intent.json"
                handoff.parent.mkdir()
                handoff.write_text('{"stale": "handoff"}\n', encoding="utf-8")
                ri.orchestrate_pre_authoring.receipt_path(directory).write_text('{"stale": "receipt"}\n', encoding="utf-8")
                changed = initial.replace(f"## {section}\n\n" + {
                    "Outcome": "Make onboarding self-serve.",
                    "Context": "Support onboards every client by hand.",
                    "Acceptance evidence": "A client self-serves in one business day.",
                    "Target repository": "`acme/billing`",
                    "Exclusions": "No enterprise SSO.",
                }[section], f"## {section}\n\n{replacement}")
                with patch.object(ri, "fetch_issue", return_value={"body": changed}):
                    ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=base_dir)
                self.assertEqual(snapshot.read_text(encoding="utf-8"), '{"snapshot": "retained"}\n')
                self.assertFalse(add_file.exists())
                self.assertFalse(ri.orchestrate_pre_authoring.intents_path(directory).exists())
                self.assertFalse(ri.orchestrate_pre_authoring.handoff_dir(directory).exists())
                self.assertFalse(ri.orchestrate_pre_authoring.receipt_path(directory).exists())

    def test_start_rebuilds_legacy_outcome_only_state(self) -> None:
        body = "## Outcome\n\nShip X.\n\n## Target repository\n\n`acme/billing`\n"
        directory = ri.orchestrate_pre_authoring.requirement_dir(self.base_dir, "requirement-7")
        directory.mkdir(parents=True)
        legacy_file = directory / "requirement.md"
        legacy_file.write_text("Ship X.\n", encoding="utf-8")
        state_path = ri.orchestrate_pre_authoring.state_path(directory)
        state_path.write_text(json.dumps({
            "version": 1,
            "id": "requirement-7",
            "requirement_file": str(legacy_file),
            "requirement_digest": ri.orchestrate_pre_authoring._digest("Ship X.\n"),
            "target_repository": "acme/billing",
            "created_at": "2024-01-01T00:00:00Z",
        }), encoding="utf-8")
        ri.orchestrate_pre_authoring.add_path(directory).write_text('{"legacy": true}\n', encoding="utf-8")
        with patch.object(ri, "fetch_issue", return_value={"body": body}):
            ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["version"], ri.orchestrate_pre_authoring.STATE_VERSION)
        self.assertFalse(ri.orchestrate_pre_authoring.add_path(directory).exists())

    def test_start_requires_an_outcome_section(self) -> None:
        with patch.object(ri, "fetch_issue", return_value={"body": "## Target repository\n\n`acme/billing`\n"}):
            with self.assertRaises(ri.RequirementIntakeError):
                ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)

    def test_start_requires_a_target_repository_section(self) -> None:
        with patch.object(ri, "fetch_issue", return_value={"body": "## Outcome\n\nShip X.\n"}):
            with self.assertRaises(ri.RequirementIntakeError):
                ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)


class LinkChildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_link_child_inserts_reference_and_labels_and_back_references(self) -> None:
        parent_body = f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n{ri.CHILDREN_END}\n"
        child_body = "Some managed task body.\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
        ):
            payload = ri.link_child(self.root, requirement="acme/development-backlog#7", child="acme/development-backlog#20")

        self.assertEqual(payload, {"requirement": "acme/development-backlog#7", "child": "acme/development-backlog#20"})
        edit_commands = [command for command in commands if command[:3] == ["gh", "issue", "edit"]]
        parent_edit = next(command for command in edit_commands if command[3] == "7")
        self.assertIn("acme/development-backlog#20", parent_edit[parent_edit.index("--body") + 1])
        child_edit = next(command for command in edit_commands if command[3] == "20")
        self.assertIn("Requirement: acme/development-backlog#7", child_edit[child_edit.index("--body") + 1])
        self.assertIn(ri.CHILD_LABEL, child_edit)
        label_commands = [command for command in commands if command[:3] == ["gh", "label", "create"]]
        self.assertTrue(any(ri.CHILD_LABEL in command for command in label_commands))

    def test_link_child_is_idempotent(self) -> None:
        parent_body = (
            f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n- [ ] acme/development-backlog#20\n{ri.CHILDREN_END}\n"
        )
        child_body = "Some managed task body.\n\nRequirement: acme/development-backlog#7\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
        ):
            ri.link_child(self.root, requirement="acme/development-backlog#7", child="acme/development-backlog#20")

        # The parent body already contained the reference, so no --body edit
        # is issued for the parent; only the child's label is (re-)applied.
        parent_body_edits = [
            command for command in commands
            if command[:3] == ["gh", "issue", "edit"] and command[3] == "7" and "--body" in command
        ]
        self.assertEqual(parent_body_edits, [])
        child_body_edits = [
            command for command in commands
            if command[:3] == ["gh", "issue", "edit"] and command[3] == "20" and "--body" in command
        ]
        self.assertEqual(child_body_edits, [])

    def test_link_child_is_idempotent_for_an_indented_existing_entry(self) -> None:
        """Regression: an existing child entry indented by a GitHub-UI hand
        edit must still be recognized, so re-linking does not duplicate it."""
        parent_body = (
            f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n  - [ ] acme/development-backlog#20\n{ri.CHILDREN_END}\n"
        )
        child_body = "Some managed task body.\n\nRequirement: acme/development-backlog#7\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
        ):
            ri.link_child(self.root, requirement="acme/development-backlog#7", child="acme/development-backlog#20")

        parent_body_edits = [
            command for command in commands
            if command[:3] == ["gh", "issue", "edit"] and command[3] == "7" and "--body" in command
        ]
        self.assertEqual(parent_body_edits, [])


class AggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _body_with_children(self, refs: list[str]) -> str:
        items = "\n".join(f"- [ ] {ref}" for ref in refs)
        return f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n{items}\n{ri.CHILDREN_END}\n"

    def test_no_children_reports_pre_authoring(self) -> None:
        with patch.object(ri, "fetch_issue", return_value={"body": self._body_with_children([])}):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["status"], "pre-authoring")
        self.assertEqual(payload["children"], [])

    def test_all_done_children_report_done(self) -> None:
        body = self._body_with_children(["acme/development-backlog#20", "acme/development-backlog#21"])

        def fake_observe(root, *, source_issue):
            return managed_project_status.ProjectObservation(source_issue, "acme", 1, "Backlog", "Done", None, False)

        with (
            patch.object(ri, "fetch_issue", return_value={"body": body}),
            patch.object(managed_project_status, "observe", side_effect=fake_observe),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["status"], "Done")

    def test_any_blocked_child_reports_blocked(self) -> None:
        body = self._body_with_children(["acme/development-backlog#20", "acme/development-backlog#21"])
        statuses = {"acme/development-backlog#20": "Done", "acme/development-backlog#21": "Blocked"}

        def fake_observe(root, *, source_issue):
            return managed_project_status.ProjectObservation(source_issue, "acme", 1, "Backlog", statuses[source_issue], None, False)

        with (
            patch.object(ri, "fetch_issue", return_value={"body": body}),
            patch.object(managed_project_status, "observe", side_effect=fake_observe),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["status"], "Blocked")

    def test_mixed_in_progress_children_report_in_progress(self) -> None:
        body = self._body_with_children(["acme/development-backlog#20", "acme/development-backlog#21"])
        statuses = {"acme/development-backlog#20": "Done", "acme/development-backlog#21": "In progress"}

        def fake_observe(root, *, source_issue):
            return managed_project_status.ProjectObservation(source_issue, "acme", 1, "Backlog", statuses[source_issue], None, False)

        with (
            patch.object(ri, "fetch_issue", return_value={"body": body}),
            patch.object(managed_project_status, "observe", side_effect=fake_observe),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["status"], "In progress")

    def test_unreadable_child_status_fails_closed_to_unknown(self) -> None:
        body = self._body_with_children(["acme/development-backlog#20", "acme/development-backlog#21"])

        def fake_observe(root, *, source_issue):
            if source_issue.endswith("21"):
                raise managed_project_status.ManagedProjectStatusError("boom")
            return managed_project_status.ProjectObservation(source_issue, "acme", 1, "Backlog", "Done", None, False)

        with (
            patch.object(ri, "fetch_issue", return_value={"body": body}),
            patch.object(managed_project_status, "observe", side_effect=fake_observe),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["status"], "unknown")
        by_child = {entry["child"]: entry["status"] for entry in payload["children"]}
        self.assertIsNone(by_child["acme/development-backlog#21"])
        self.assertEqual(by_child["acme/development-backlog#20"], "Done")


if __name__ == "__main__":
    unittest.main()
