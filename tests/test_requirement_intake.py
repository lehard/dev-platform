"""Coverage for the human-facing Business Requirement intake/linkage/aggregation surface.

gh CLI calls are mocked at the same seams tests/test_managed_task.py already
uses (managed_task.run / managed_task.github_cli_env), since
requirement_intake.py composes managed_task.py's own helpers rather than
reimplementing GitHub I/O.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
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
import managed_task  # noqa: E402
import requirement_intake as ri  # noqa: E402


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def init_repo() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "remote", "add", "origin", "https://github.com/acme/billing.git")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    (root / ".dev-platform.toml").write_text(
        'protected_main = true\npublish_mode = "pr"\nscm_provider = "github"\nharness_mode = "platform"\n'
        '\n[capabilities]\nopenspec = true\ngithub_sync = true\nfeature_branches = true\nplatform_git_lifecycle = true\n'
        '\n[development_backlog]\nrepository = "acme/development-backlog"\n'
        'project_label = "project:billing"\ndefault_priority = "P2"\n',
        encoding="utf-8",
    )
    for entrypoint in ri.requirement_target_lifecycle.REQUIRED_ENTRYPOINTS:
        path = root / entrypoint
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# managed lifecycle fixture\n", encoding="utf-8")
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


class MaterializeHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.handoff = self.root / "handoff.json"
        self.handoff.write_text(json.dumps({"digest": "a" * 64}), encoding="utf-8")
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.bundle_value = managed_task.AuthoringBundle(
            "Ship it", "Outcome", "ship-it", ("proposal.md",), {"proposal.md": "Proposal"},
        )
        self.parent_body = ri.render_requirement_body(outcome="Ship it", target_repository="acme/platform")
        self.child_body = ""
        self.marker = f"<!-- requirement-handoff:v1:acme/backlog#7:{'a' * 64} -->"
        self.candidates: list[dict] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fetch(self, root, repository, number):
        if number == 7:
            return {"body": self.parent_body, "labels": [{"name": ri.REQUIREMENT_LABEL}]}
        return {"body": self.child_body, "labels": [{"name": ri.CHILD_LABEL}]}

    def _link(self, root, *, requirement, child):
        self.parent_body = self.parent_body.replace(ri.CHILDREN_END, f"- [ ] {child}\n{ri.CHILDREN_END}")
        self.child_body += f"\nRequirement: {requirement}\n"

    def _run(self, *, candidates=None, create=None, link=None, status=None):
        report = status or {"current_stage": "complete", "target_repository": "acme/platform",
                            "handoffs": {"intent": str(self.handoff)}}
        config = managed_task.AuthoringConfig("acme/backlog", "managed", "P2")
        with (
            patch.object(ri.orchestrate_pre_authoring, "status", return_value=report),
            patch.object(ri, "fetch_issue", side_effect=self._fetch),
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri.managed_task, "origin_repository", return_value="acme/platform"),
            patch.object(ri.managed_task, "authoring_config", return_value=config),
            patch.object(ri.managed_task, "load_authoring_bundle", return_value=self.bundle_value),
            patch.object(ri.managed_task, "run_json", return_value=self.candidates if candidates is None else candidates),
            patch.object(ri.managed_task, "create_task", side_effect=create) as create_mock,
            patch.object(ri, "link_child", side_effect=link or self._link),
        ):
            result = ri.materialize_handoff(self.root, requirement="acme/backlog#7",
                handoff_file=self.handoff, bundle_path=self.bundle)
        return result, create_mock

    def test_create_then_link_and_retry_reuses_exact_child(self) -> None:
        package = type("Package", (), {"source_issue": "acme/backlog#8"})()
        result, create_mock = self._run(create=lambda *args, **kwargs: (package, False, False))
        self.assertEqual(result["child"], "acme/backlog#8")
        self.assertEqual(create_mock.call_args.kwargs["handoff_marker"], self.marker)
        self.candidates = [{"number": 8, "body": self.marker}]
        self.child_body = self.marker + self.child_body
        published = type("Package", (), {"change": "ship-it", "target_repository": "acme/platform",
                                          "artifacts": self.bundle_value.artifacts, "contents": self.bundle_value.contents})()
        with (
            patch.object(ri.managed_task, "issue_bodies", return_value=["package"]),
            patch.object(ri.managed_task, "parse_package", return_value=published),
        ):
            result, create_mock = self._run()
        self.assertEqual(result["child"], "acme/backlog#8")
        create_mock.assert_not_called()

    def test_interrupted_link_retries_without_another_issue(self) -> None:
        self.candidates = [{"number": 8, "body": self.marker}]
        self.child_body = self.marker
        published = type("Package", (), {"change": "ship-it", "target_repository": "acme/platform",
                                          "artifacts": self.bundle_value.artifacts, "contents": self.bundle_value.contents})()
        with (
            patch.object(ri.managed_task, "issue_bodies", return_value=["package"]),
            patch.object(ri.managed_task, "parse_package", return_value=published),
        ):
            with self.assertRaisesRegex(RuntimeError, "transport interruption"):
                self._run(link=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("transport interruption")))
            result, create_mock = self._run()
        self.assertEqual(result["child"], "acme/backlog#8")
        create_mock.assert_not_called()

    def test_authored_parent_prose_is_not_confirmed_backlink(self) -> None:
        package = type("Package", (), {"source_issue": "acme/backlog#8"})()
        self.parent_body = self.parent_body.replace(ri.CHILDREN_END, f"- [ ] acme/backlog#8\n{ri.CHILDREN_END}")
        self.child_body = "Parent Requirement: acme/backlog#7\n"
        with self.assertRaisesRegex(ri.RequirementIntakeError, "linkage incomplete"):
            self._run(create=lambda *args, **kwargs: (package, False, False), link=lambda *args, **kwargs: None)

    def test_invalid_or_ambiguous_handoff_does_not_create_issue(self) -> None:
        with self.assertRaises(ri.RequirementIntakeError):
            self._run(status={"current_stage": "snapshot", "blocker": {"state": "stale"}})
        with self.assertRaisesRegex(ri.RequirementIntakeError, "multiple children"):
            self._run(candidates=[{"number": 8, "body": self.marker}, {"number": 9, "body": self.marker}])

    def test_materialize_handoff_cli_serializes_confirmed_success_and_retry(self) -> None:
        """The CLI must not shadow its module-level JSON serializer on success."""
        results = [
            {"requirement": "acme/backlog#7", "child": "acme/backlog#8", "created": True},
            {"requirement": "acme/backlog#7", "child": "acme/backlog#8", "created": False},
        ]
        argv = [
            "requirement_intake.py", "materialize-handoff", "--requirement", "acme/backlog#7",
            "--handoff", "handoff.json", "--bundle", "bundle",
        ]
        with (
            patch.object(ri, "current_worktree_root", return_value=self.root),
            patch.object(ri, "materialize_handoff", side_effect=results) as materialize,
            patch.object(sys, "argv", argv),
        ):
            outputs = []
            for _ in results:
                stream = io.StringIO()
                with redirect_stdout(stream):
                    self.assertEqual(ri.main(), 0)
                outputs.append(json.loads(stream.getvalue()))

        self.assertEqual([payload["child"] for payload in outputs], ["acme/backlog#8", "acme/backlog#8"])
        self.assertEqual([payload["created"] for payload in outputs], [True, False])
        self.assertEqual(materialize.call_count, 2)


class CreateRequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.config = managed_task.AuthoringConfig("acme/development-backlog", "project:billing", "P2")
        self.issue_labels: set[str] = set()
        self.issue_body = ""

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fetch_issue(self, root, repository, number):
        return {"body": self.issue_body, "labels": [{"name": name} for name in self.issue_labels]}

    def _run_create(self, *, run_side_effect=None, priority=None, config=None, origin="acme/billing", validate_error=None,
                    existing_issues=None, ensure_side_effect=None):
        commands: list[list[str]] = []
        self.ensure_calls: list[str] = []

        def fake_ensure(root, *, source_issue, initial_status="Backlog"):
            self.ensure_calls.append(source_issue)
            if ensure_side_effect is not None:
                raise ensure_side_effect
            return managed_project_status.MembershipReceipt(
                source_issue, "lehard", 1, "item-1", "Backlog", True, True)

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
                self.issue_body = command[command.index("--body") + 1]
            if run_side_effect is not None:
                return run_side_effect(command)
            if command[:3] == ["gh", "issue", "create"]:
                self.issue_labels = {ri.REQUIREMENT_LABEL, (config or self.config).project_label,
                                      managed_task.priority_label(priority or (config or self.config).default_priority)}
                return type("Result", (), {"stdout": "https://github.com/acme/development-backlog/issues/42\n", "returncode": 0})()
            if command[:2] == ["gh", "api"] and "--method" in command:
                label = command[-1].split("=", 1)[1]
                self.issue_labels.add(label)
                return type("Result", (), {"stdout": "", "returncode": 0})()
            return type("Result", (), {"stdout": "", "returncode": 0})()

        def fake_validate(root, cfg, prio):
            if validate_error is not None:
                raise managed_task.ManagedTaskError(validate_error)

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "run", side_effect=fake_run),
            patch.object(ri, "fetch_issue", side_effect=self._fetch_issue),
            patch.object(ri.managed_task, "authoring_config", return_value=config or self.config),
            patch.object(ri.managed_task, "origin_repository", return_value=origin),
            patch.object(ri.managed_task, "validate_backlog_labels", side_effect=fake_validate),
            patch.object(ri.managed_task, "run_json", return_value=[existing_issues or []]),
            patch.object(ri.managed_project_status, "ensure_item", side_effect=fake_ensure),
        ):
            payload = ri.create_requirement(
                self.root, repository="acme/development-backlog", title="Make onboarding self-serve",
                outcome="Make onboarding self-serve.", target_repository="acme/billing", priority=priority,
            )
        return payload, commands

    def test_create_issues_gh_issue_create_with_all_expected_labels_for_default_priority(self) -> None:
        payload, commands = self._run_create()
        self.assertEqual(payload, {
            "repository": "acme/development-backlog", "number": 42, "slug": "requirement-42",
            "project_label": "project:billing", "priority": "priority:P2",
            "reused": False, "project_item": "item-1", "project_status": "Backlog",
        })
        self.assertEqual(self.ensure_calls, ["acme/development-backlog#42"])
        create_command = next(command for command in commands if command[:3] == ["gh", "issue", "create"])
        self.assertIn(ri.REQUIREMENT_LABEL, create_command)
        self.assertIn("project:billing", create_command)
        self.assertIn("priority:P2", create_command)
        label_command = next(command for command in commands if command[:3] == ["gh", "label", "create"])
        self.assertIn(ri.REQUIREMENT_LABEL, label_command)

    def test_create_fails_closed_naming_the_durable_issue_when_project_unavailable(self) -> None:
        error = managed_project_status.ManagedProjectStatusError("GitHub Project API request failed: down")
        with self.assertRaisesRegex(ri.RequirementIntakeError, r"acme/development-backlog#42 exists.*unconfirmed.*reconcile-board"):
            self._run_create(ensure_side_effect=error)

    def test_rerun_reuses_identical_open_requirement_instead_of_creating_another(self) -> None:
        body = ri.render_requirement_body(outcome="Make onboarding self-serve.", target_repository="acme/billing")
        # The platform appends its Work identity line after creation; it is not authored content.
        existing = [{"number": 42, "title": "Make onboarding self-serve", "body": body + "\nWork identity: BR-42\n"}]
        self.issue_labels = {ri.REQUIREMENT_LABEL, "project:billing", "priority:P2"}
        self.issue_body = body
        payload, commands = self._run_create(existing_issues=existing)
        self.assertTrue(payload["reused"])
        self.assertEqual(payload["number"], 42)
        self.assertFalse(any(command[:3] == ["gh", "issue", "create"] for command in commands))
        self.assertEqual(self.ensure_calls, ["acme/development-backlog#42"])

    def test_connected_fixation_outcome_requires_confirmed_membership(self) -> None:
        self.assertEqual(ri.connected_fixation_outcome(issue_created=True, project_membership_confirmed=True), "fixed")
        self.assertEqual(ri.connected_fixation_outcome(issue_created=True, project_membership_confirmed=False), "unconfirmed")
        self.assertEqual(ri.connected_fixation_outcome(issue_created=False, project_membership_confirmed=False), "not-created")

    def test_reconcile_board_ensures_each_open_requirement_idempotently(self) -> None:
        issues = [{"number": 5}, {"number": 3}, {"number": 9, "pull_request": {}}]
        seen: list[str] = []

        def fake_ensure(root, *, source_issue, initial_status="Backlog"):
            seen.append(source_issue)
            return managed_project_status.MembershipReceipt(source_issue, "lehard", 1, "i", "Backlog", False, False)

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri.managed_task, "authoring_config", return_value=self.config),
            patch.object(ri.managed_task, "run_json", return_value=[issues[:2], issues[2:]]),
            patch.object(ri.managed_project_status, "ensure_item", side_effect=fake_ensure),
        ):
            first = ri.reconcile_board(self.root)
            second = ri.reconcile_board(self.root)
        self.assertEqual(seen[:2], ["acme/development-backlog#3", "acme/development-backlog#5"])
        self.assertEqual(first, second)

    def test_reconcile_requirement_rejects_closed_or_non_requirement_targets(self) -> None:
        for issue, message in (
            ({"state": "closed", "labels": [{"name": ri.REQUIREMENT_LABEL}]}, "not open"),
            ({"state": "open", "labels": [{"name": ri.CHILD_LABEL}]}, "not labeled"),
        ):
            with self.subTest(message=message), \
                    patch.object(ri.managed_task, "authoring_config", return_value=self.config), \
                    patch.object(ri, "fetch_issue", return_value=issue), \
                    patch.object(ri.managed_project_status, "ensure_item") as ensure:
                with self.assertRaisesRegex(ri.RequirementIntakeError, message):
                    ri.reconcile_board(self.root, requirement="acme/development-backlog#7")
                ensure.assert_not_called()

    def test_create_honors_explicit_priority(self) -> None:
        payload, commands = self._run_create(priority="P0")
        self.assertEqual(payload["priority"], "priority:P0")
        create_command = next(command for command in commands if command[:3] == ["gh", "issue", "create"])
        self.assertIn("priority:P0", create_command)

    def test_create_rejects_blank_title(self) -> None:
        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri.managed_task, "authoring_config", return_value=self.config),
            patch.object(ri.managed_task, "origin_repository", return_value="acme/billing"),
        ):
            with self.assertRaises(ri.RequirementIntakeError):
                ri.create_requirement(
                    self.root, repository="acme/development-backlog", title="   ",
                    outcome="Ship X.", target_repository="acme/billing",
                )

    def test_create_fails_before_any_issue_when_target_repository_is_not_origin(self) -> None:
        with self.assertRaises(ri.RequirementIntakeError):
            self._run_create(origin="acme/other-service")

    def test_create_fails_when_repository_disagrees_with_backlog_config(self) -> None:
        other_config = managed_task.AuthoringConfig("acme/other-backlog", "project:billing", "P2")
        with self.assertRaises(ri.RequirementIntakeError):
            self._run_create(config=other_config)

    def test_create_fails_before_creation_when_configured_label_is_unavailable(self) -> None:
        created = []

        def fake_run(command):
            if command[:3] == ["gh", "issue", "create"]:
                created.append(command)
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with self.assertRaises(managed_task.ManagedTaskError):
            self._run_create(run_side_effect=fake_run, validate_error="configured Development Backlog label is unavailable: project:billing")
        self.assertEqual(created, [])

    def test_create_repairs_a_read_back_missing_label_then_succeeds(self) -> None:
        def fake_run(command):
            if command[:3] == ["gh", "issue", "create"]:
                # Simulate the created Issue coming back without the priority label.
                self.issue_labels = {ri.REQUIREMENT_LABEL, self.config.project_label}
                return type("Result", (), {"stdout": "https://github.com/acme/development-backlog/issues/42\n", "returncode": 0})()
            if command[:2] == ["gh", "api"] and "--method" in command:
                label = command[-1].split("=", 1)[1]
                self.issue_labels.add(label)
                return type("Result", (), {"stdout": "", "returncode": 0})()
            return type("Result", (), {"stdout": "", "returncode": 0})()

        payload, commands = self._run_create(run_side_effect=fake_run)
        self.assertEqual(payload["priority"], "priority:P2")
        self.assertIn("priority:P2", self.issue_labels)
        repair_command = next(command for command in commands if command[:2] == ["gh", "api"] and "--method" in command)
        self.assertIn("labels[]=priority:P2", repair_command)

    def test_create_fails_by_reference_when_read_back_has_a_conflicting_label(self) -> None:
        def fake_run(command):
            if command[:3] == ["gh", "issue", "create"]:
                self.issue_labels = {ri.REQUIREMENT_LABEL, "project:other-service", "priority:P2"}
                return type("Result", (), {"stdout": "https://github.com/acme/development-backlog/issues/42\n", "returncode": 0})()
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with self.assertRaisesRegex(ri.RequirementIntakeError, "acme/development-backlog#42"):
            self._run_create(run_side_effect=fake_run)


class StartPreAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.base_dir = self.root / ".claude" / "pre-authoring"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_repairs_legacy_parent_identity_and_refuses_conflicting_identity(self):
        issue = {"body": ri.render_requirement_body(outcome="Ship", target_repository="acme/billing")}
        def write(command, root, env):
            issue["body"] = command[command.index("--body") + 1]
        with (patch.object(ri, "fetch_issue", side_effect=lambda *args: dict(issue)),
              patch.object(ri, "github_cli_env", return_value={}),
              patch.object(ri, "run", side_effect=write) as edit):
            ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
            self.assertEqual(ri.work_identity.identity_in(issue["body"]), "BR-7")
            edit.assert_called_once()
            ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
            edit.assert_called_once()
            issue["body"] = issue["body"].replace("BR-7", "BR-99")
            with self.assertRaisesRegex(ri.RequirementIntakeError, "conflicting work identity"):
                ri.start_pre_authoring(self.root, requirement="acme/development-backlog#7", base_dir=self.base_dir)
            edit.assert_called_once()

    def test_start_bridges_a_requirement_issue_into_orchestrator_init(self) -> None:
        body = (
            "## Outcome\n\nMake onboarding self-serve.\n\n"
            "## Context\n\nSupport currently onboards every client by hand.\n\n"
            "## Acceptance evidence\n\nA new client can self-serve within one business day.\n\n"
            "## Target repository\n\n`acme/billing`\n\n"
            "## Exclusions\n\nDoes not cover enterprise SSO.\n\n"
            f"{ri.CHILDREN_START}\n{ri.CHILDREN_END}\n"
        )
        with patch.object(ri, "fetch_issue", return_value={"body": body + "\nWork identity: BR-7\n"}):
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
        with patch.object(ri, "fetch_issue", return_value={"body": initial + "\nWork identity: BR-7\n"}):
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
        with patch.object(ri, "fetch_issue", return_value={"body": reformatted + "\nWork identity: BR-7\n"}):
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
                git(self.root, "remote", "set-url", "origin", "https://github.com/acme/billing.git")
                base_dir = self.root / ".claude" / f"pre-authoring-{section.replace(' ', '-') }"
                with patch.object(ri, "fetch_issue", return_value={"body": initial + "\nWork identity: BR-7\n"}):
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
                if section == "Target repository":
                    git(self.root, "remote", "set-url", "origin", "https://github.com/acme/accounts.git")
                with patch.object(ri, "fetch_issue", return_value={"body": changed + "\nWork identity: BR-7\n"}):
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
        with patch.object(ri, "fetch_issue", return_value={"body": body + "\nWork identity: BR-7\n"}):
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
            if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
                fetched[f"{command[command.index('--repo') + 1]}#{command[3]}"] = command[command.index("--body") + 1]
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
            patch.object(ri, "_identity_siblings", return_value={}),
        ):
            payload = ri.link_child(self.root, requirement="acme/development-backlog#7", child="acme/development-backlog#20")

        self.assertEqual(payload["work_identity"], "BR-7/T1")
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
        child_body = "Some managed task body.\n\nRequirement: acme/development-backlog#7\nWork identity: BR-7/T1\n"
        parent_body += "Work identity: BR-7\n<!-- br-child:acme/development-backlog#20:1 -->\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
                fetched[f"{command[command.index('--repo') + 1]}#{command[3]}"] = command[command.index("--body") + 1]
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
            patch.object(ri, "_identity_siblings", return_value={}),
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

    def test_link_child_repairs_authored_parent_prose(self) -> None:
        parent_body = (
            f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n"
            f"- [ ] acme/development-backlog#20\n{ri.CHILDREN_END}\n"
        )
        child_body = "Parent Requirement: acme/development-backlog#7\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
                fetched[f"{command[command.index('--repo') + 1]}#{command[3]}"] = command[command.index("--body") + 1]
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
            patch.object(ri, "_identity_siblings", return_value={}),
        ):
            ri.link_child(self.root, requirement="acme/development-backlog#7", child="acme/development-backlog#20")

        child_edit = next(command for command in commands if command[:4] == ["gh", "issue", "edit", "20"])
        updated_body = child_edit[child_edit.index("--body") + 1]
        self.assertIn("\nRequirement: acme/development-backlog#7\n", updated_body)

    def test_link_child_is_idempotent_for_an_indented_existing_entry(self) -> None:
        """Regression: an existing child entry indented by a GitHub-UI hand
        edit must still be recognized, so re-linking does not duplicate it."""
        parent_body = (
            f"## Outcome\n\nShip X.\n\n{ri.CHILDREN_START}\n  - [ ] acme/development-backlog#20\n{ri.CHILDREN_END}\n"
        )
        child_body = "Some managed task body.\n\nRequirement: acme/development-backlog#7\nWork identity: BR-7/T1\n"
        parent_body += "Work identity: BR-7\n<!-- br-child:acme/development-backlog#20:1 -->\n"
        fetched = {"acme/development-backlog#7": parent_body, "acme/development-backlog#20": child_body}
        commands: list[list[str]] = []

        def fake_fetch_issue(root, repository, number):
            return {"body": fetched[f"{repository}#{number}"]}

        def fake_run(command, cwd, env=None, input_text=None):
            commands.append(command)
            if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
                fetched[f"{command[command.index('--repo') + 1]}#{command[3]}"] = command[command.index("--body") + 1]
            return type("Result", (), {"stdout": "", "returncode": 0})()

        with (
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=fake_fetch_issue),
            patch.object(ri, "run", side_effect=fake_run),
            patch.object(ri, "_identity_siblings", return_value={}),
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

    @staticmethod
    def _orchestrator_report(stage: str, state: str = "missing") -> dict[str, object]:
        if stage == "complete":
            return {"current_stage": "complete", "stages": {}, "blocker": None, "handoffs": {"direct": "handoff.json"}}
        return {
            "current_stage": stage,
            "stages": {stage: {"stage": stage, "state": state}},
            "blocker": {"stage": stage, "state": state},
        }

    def _projected_stage(self, *, children: list[str], report: dict[str, object], statuses: dict[str, str] | None = None) -> str:
        def fake_observe(root, *, source_issue):
            return managed_project_status.ProjectObservation(
                source_issue, "acme", 1, "Backlog", (statuses or {})[source_issue], None, False
            )

        with (
            patch.object(ri, "fetch_issue", return_value={"body": self._body_with_children(children)}),
            patch.object(ri.orchestrate_pre_authoring, "status", return_value=report),
            patch.object(managed_project_status, "observe", side_effect=fake_observe),
        ):
            return ri.aggregate(self.root, requirement="acme/development-backlog#7")["progress"]["stage"]

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

    def test_projection_distinguishes_pre_authoring_design_decision_and_ready(self) -> None:
        self.assertEqual(self._projected_stage(children=[], report=self._orchestrator_report("selection")), "pre-authoring")
        self.assertEqual(self._projected_stage(children=[], report=self._orchestrator_report("add", "needs-drafting")), "design")
        self.assertEqual(self._projected_stage(children=[], report=self._orchestrator_report("add", "needs-decision")), "human-decision")
        self.assertEqual(self._projected_stage(children=[], report=self._orchestrator_report("complete")), "ready")
        self.assertEqual(self._projected_stage(children=[], report=self._orchestrator_report("snapshot", "stale")), "unknown")

    def test_projection_uses_children_for_implementation_blocked_and_done(self) -> None:
        children = ["acme/development-backlog#20"]
        report = self._orchestrator_report("complete")
        self.assertEqual(self._projected_stage(children=children, report=report, statuses={children[0]: "In progress"}), "implementation")
        self.assertEqual(self._projected_stage(children=children, report=report, statuses={children[0]: "In review"}), "implementation")
        self.assertEqual(self._projected_stage(children=children, report=report, statuses={children[0]: "Blocked"}), "blocked")
        self.assertEqual(self._projected_stage(children=children, report=report, statuses={children[0]: "Done"}), "done")

    def test_linked_child_progress_does_not_require_machine_local_pre_authoring_state(self) -> None:
        child = "acme/development-backlog#20"
        with (
            patch.object(ri, "fetch_issue", return_value={"body": self._body_with_children([child])}),
            patch.object(ri.orchestrate_pre_authoring, "status", side_effect=AssertionError("must not read pre-authoring")),
            patch.object(managed_project_status, "observe", return_value=managed_project_status.ProjectObservation(
                child, "acme", 1, "Backlog", "Done", None, False,
            )),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["progress"]["stage"], "done")

    def test_projection_reports_orchestrator_escalation_as_blocked(self) -> None:
        self.assertEqual(
            self._projected_stage(children=[], report=self._orchestrator_report("snapshot", "needs-escalation")),
            "blocked",
        )

    def test_projection_fails_closed_for_unreadable_and_contradictory_sources(self) -> None:
        with (
            patch.object(ri, "fetch_issue", return_value={"body": self._body_with_children([])}),
            patch.object(ri.orchestrate_pre_authoring, "status", side_effect=ri.orchestrate_pre_authoring.OrchestratorError("missing state")),
        ):
            payload = ri.aggregate(self.root, requirement="acme/development-backlog#7")
        self.assertEqual(payload["progress"]["stage"], "unknown")
        self.assertIn("unreadable", payload["progress"]["diagnostics"][0]["reason"])

        self.assertEqual(
            self._projected_stage(children=[], report={"current_stage": "complete", "stages": {}, "blocker": "unexpected", "handoffs": {}}),
            "unknown",
        )


FIXTURES = ROOT / "tests" / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ConnectedRequirementRoutingTests(unittest.TestCase):
    """Coverage for the connected ChatGPT adapter's routing reference model.

    ``resolve_connected_routing``/``verify_connected_requirement`` are the
    pure functions the connected adapter must behave equivalently to when it
    cannot read a target's committed ``.dev-platform.toml`` -- for example an
    operator-managed target such as Dev Platform itself, which intentionally
    keeps that file untracked.
    """

    def setUp(self) -> None:
        self.fixture = _load_fixture("chatgpt_project_requirement_operator_routing.json")
        self.evidence = {
            "operator_integration": True,
            "managed_entrypoints": True,
            "protected_publication": True,
        }

    def test_resolve_connected_routing_uses_declared_parameters_when_uncommitted(self) -> None:
        self.assertIsNone(self.fixture["committed_config"])
        routing = ri.resolve_connected_routing(
            target_repository=self.fixture["target_repository"],
            backlog_repository=self.fixture["backlog_repository"],
            committed_config=self.fixture["committed_config"],
            project_parameters=self.fixture["project_parameters"],
            lifecycle_evidence=self.evidence,
        )
        self.assertEqual(routing, self.fixture["routing"])
        # The read-back issue in the fixture is exactly what a successful
        # connected fixation against this routing must find.
        ri.verify_connected_requirement(self.fixture["issue"], routing=routing)

    def test_connected_routing_rejects_parameters_without_lifecycle_evidence(self) -> None:
        with self.assertRaisesRegex(ri.RequirementIntakeError, "managed lifecycle support"):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=None,
                project_parameters=self.fixture["project_parameters"],
            )

    def test_routing_parameters_render_matches_what_the_fixture_declares(self) -> None:
        params = self.fixture["project_parameters"]
        config = managed_task.AuthoringConfig(
            self.fixture["backlog_repository"], params["PROJECT_LABEL"], params["DEFAULT_PRIORITY"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.object(ri.managed_task, "authoring_config", return_value=config),
                patch.object(ri.managed_task, "origin_repository", return_value=self.fixture["target_repository"]),
            ):
                rendered = ri.routing_parameters(root)
        self.assertEqual(rendered, params)

    def test_committed_configuration_conflicting_with_declared_project_label_stops(self) -> None:
        committed = {
            "repository": self.fixture["backlog_repository"],
            "project_label": "project:something-else",
            "default_priority": "P2",
        }
        with self.assertRaisesRegex(ri.RequirementIntakeError, "conflicts with committed"):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=committed,
                project_parameters=self.fixture["project_parameters"],
                lifecycle_evidence=self.evidence,
            )

    def test_committed_configuration_conflicting_with_declared_default_priority_stops(self) -> None:
        committed = {
            "repository": self.fixture["backlog_repository"],
            "project_label": self.fixture["project_parameters"]["PROJECT_LABEL"],
            "default_priority": "P0",
        }
        with self.assertRaisesRegex(ri.RequirementIntakeError, "conflicts with committed"):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=committed,
                project_parameters=self.fixture["project_parameters"],
                lifecycle_evidence=self.evidence,
            )

    def test_committed_configuration_is_used_when_declared_parameters_are_absent(self) -> None:
        committed = {
            "repository": self.fixture["backlog_repository"],
            "project_label": "project:committed-target",
            "default_priority": "P1",
        }
        routing = ri.resolve_connected_routing(
            target_repository=self.fixture["target_repository"],
            backlog_repository=self.fixture["backlog_repository"],
            committed_config=committed,
            project_parameters={},
            lifecycle_evidence=self.evidence,
        )
        self.assertEqual(routing, {"project_label": "project:committed-target", "priority": "priority:P1"})

    def test_missing_or_invalid_declared_parameters_fail_closed_when_uncommitted(self) -> None:
        base = dict(self.fixture["project_parameters"])
        for key in ("PROJECT_LABEL", "DEFAULT_PRIORITY", "BACKLOG_REPOSITORY", "TARGET_REPOSITORY"):
            declared = dict(base)
            del declared[key]
            with self.subTest(missing=key):
                with self.assertRaises(ri.RequirementIntakeError):
                    ri.resolve_connected_routing(
                        target_repository=self.fixture["target_repository"],
                        backlog_repository=self.fixture["backlog_repository"],
                        committed_config=None,
                        project_parameters=declared,
                        lifecycle_evidence=self.evidence,
                    )

    def test_wrong_declared_backlog_repository_fails_closed(self) -> None:
        declared = dict(self.fixture["project_parameters"])
        declared["BACKLOG_REPOSITORY"] = "some-other/backlog"
        with self.assertRaisesRegex(ri.RequirementIntakeError, "BACKLOG_REPOSITORY"):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=None,
                project_parameters=declared,
                lifecycle_evidence=self.evidence,
            )

    def test_invalid_owner_name_strings_raise_requirement_intake_error_not_managed_task_error(self) -> None:
        """Regression: a malformed owner/name string anywhere routing
        resolution touches (the function's own target/backlog repository, a
        declared Project parameter, or the committed config) must surface as
        RequirementIntakeError, not leak managed_task.repo's ManagedTaskError."""
        with self.assertRaises(ri.RequirementIntakeError):
            ri.resolve_connected_routing(
                target_repository="not-a-valid-repo",
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=None,
                project_parameters=self.fixture["project_parameters"],
                lifecycle_evidence=self.evidence,
            )
        declared = dict(self.fixture["project_parameters"])
        declared["TARGET_REPOSITORY"] = "###bad###"
        with self.assertRaises(ri.RequirementIntakeError):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=None,
                project_parameters=declared,
                lifecycle_evidence=self.evidence,
            )
        with self.assertRaises(ri.RequirementIntakeError):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config={"repository": "###bad###", "project_label": "project:x", "default_priority": "P2"},
                project_parameters={},
                lifecycle_evidence=self.evidence,
            )

    def test_wrong_declared_target_repository_fails_closed(self) -> None:
        declared = dict(self.fixture["project_parameters"])
        declared["TARGET_REPOSITORY"] = "some-other/target"
        with self.assertRaisesRegex(ri.RequirementIntakeError, "TARGET_REPOSITORY"):
            ri.resolve_connected_routing(
                target_repository=self.fixture["target_repository"],
                backlog_repository=self.fixture["backlog_repository"],
                committed_config=None,
                project_parameters=declared,
                lifecycle_evidence=self.evidence,
            )

    def test_explicit_priority_overrides_declared_default(self) -> None:
        routing = ri.resolve_connected_routing(
            target_repository=self.fixture["target_repository"],
            backlog_repository=self.fixture["backlog_repository"],
            committed_config=None,
            project_parameters=self.fixture["project_parameters"],
            priority="P0",
            lifecycle_evidence=self.evidence,
        )
        self.assertEqual(routing, {"project_label": self.fixture["routing"]["project_label"], "priority": "priority:P0"})

    def test_verify_connected_requirement_raises_on_missing_priority_label(self) -> None:
        routing = self.fixture["routing"]
        issue = {
            "state": "open",
            "labels": [{"name": "type:requirement"}, {"name": routing["project_label"]}],
        }
        with self.assertRaises(ri.RequirementIntakeError):
            ri.verify_connected_requirement(issue, routing=routing)

    def test_verify_connected_requirement_raises_on_extra_conflicting_project_label(self) -> None:
        routing = self.fixture["routing"]
        issue = {
            "state": "open",
            "labels": [
                {"name": "type:requirement"}, {"name": routing["project_label"]},
                {"name": "project:extra"}, {"name": routing["priority"]},
            ],
        }
        with self.assertRaises(ri.RequirementIntakeError):
            ri.verify_connected_requirement(issue, routing=routing)

    def test_verify_connected_requirement_rejects_closed_issue_and_pull_requests(self) -> None:
        routing = self.fixture["routing"]
        labels = [{"name": "type:requirement"}, {"name": routing["project_label"]}, {"name": routing["priority"]}]
        with self.assertRaises(ri.RequirementIntakeError):
            ri.verify_connected_requirement({"state": "closed", "labels": labels}, routing=routing)
        with self.assertRaises(ri.RequirementIntakeError):
            ri.verify_connected_requirement(
                {"state": "open", "labels": labels, "pull_request": {"url": "https://example.invalid/pr/1"}}, routing=routing,
            )

    def test_cli_routing_parameters_prints_name_equals_value_lines_in_order(self) -> None:
        params = self.fixture["project_parameters"]
        config = managed_task.AuthoringConfig(
            self.fixture["backlog_repository"], params["PROJECT_LABEL"], params["DEFAULT_PRIORITY"],
        )
        argv = ["requirement_intake.py", "routing-parameters"]
        with (
            patch.object(ri, "current_worktree_root", return_value=Path(".")),
            patch.object(ri.managed_task, "authoring_config", return_value=config),
            patch.object(ri.managed_task, "origin_repository", return_value=self.fixture["target_repository"]),
            patch.object(sys, "argv", argv),
        ):
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(ri.main(), 0)
        lines = stream.getvalue().strip("\n").splitlines()
        self.assertEqual(lines, [
            f"BACKLOG_REPOSITORY={params['BACKLOG_REPOSITORY']}",
            f"TARGET_REPOSITORY={params['TARGET_REPOSITORY']}",
            f"PROJECT_LABEL={params['PROJECT_LABEL']}",
            f"DEFAULT_PRIORITY={params['DEFAULT_PRIORITY']}",
        ])

    def test_protocol_docs_describe_routing_parameters_command_and_untracked_fallback(self) -> None:
        for relative in ("docs/engineering/chatgpt-project-protocol.md", "template/docs/engineering/chatgpt-project-protocol.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("routing-parameters", text)
                self.assertIn("DEFAULT_PRIORITY", text)
                self.assertIn("untracked", text)
                self.assertIn("operator-managed", text)


class RequirementTargetLifecycleTests(unittest.TestCase):
    def test_local_target_without_managed_entrypoints_fails_before_requirement_creation(self) -> None:
        temporary = init_repo()
        root = Path(temporary.name)
        try:
            (root / "scripts" / "execute_requirement.py").unlink()
            with patch.object(ri.managed_task, "authoring_config", return_value=managed_task.AuthoringConfig(
                "acme/development-backlog", "project:billing", "P2",
            )):
                with self.assertRaisesRegex(ri.RequirementIntakeError, "missing managed entrypoints"):
                    ri.create_requirement(
                        root, repository="acme/development-backlog", title="Guard lifecycle",
                        outcome="Only supported targets enter Requirements.", target_repository="acme/billing",
                    )
        finally:
            temporary.cleanup()

    def test_local_target_with_routing_but_disabled_lifecycle_capability_fails(self) -> None:
        temporary = init_repo()
        root = Path(temporary.name)
        try:
            path = root / ".dev-platform.toml"
            path.write_text(path.read_text(encoding="utf-8").replace("openspec = true", "openspec = false"), encoding="utf-8")
            with self.assertRaisesRegex(ri.requirement_target_lifecycle.RequirementTargetLifecycleError,
                                        "required managed capabilities are not enabled: openspec"):
                ri.requirement_target_lifecycle.require_local_target_support(root, target_repository="acme/billing")
        finally:
            temporary.cleanup()




class StableIdentityRegressionTests(unittest.TestCase):
    """Persisted synthetic Issues exercise the complete allocation transaction."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.parent = "example-org/private-backlog#42"
        self.records = {42: ri.render_requirement_body(outcome="Ship", target_repository="example-org/app"),
                        10: "Technical task\n", 11: "Technical task\n", 12: "Technical task\n"}
        self.interrupt = False
        self.race = False
        self.patches = [
            patch.object(ri, "github_cli_env", return_value={}),
            patch.object(ri, "fetch_issue", side_effect=self.fetch),
            patch.object(ri, "run", side_effect=self.write),
            patch.object(ri.managed_task, "run_json", side_effect=self.list_issues),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def fetch(self, root, repository, number):
        return {"body": self.records[number], "number": number}

    def list_issues(self, command, root, env):
        self.assertIn("state=all", command[-1])
        self.assertIn("--slurp", command)
        return [[{"number": number, "body": body} for number, body in self.records.items()]]

    def write(self, command, root, env=None):
        if command[:3] == ["gh", "issue", "edit"] and "--body" in command:
            number = int(command[3])
            if number == 42 and self.interrupt:
                self.interrupt = False
                raise ri.RequirementIntakeError("synthetic interruption")
            self.records[number] = command[command.index("--body") + 1]
            if number == 42 and self.race:
                self.records[12] = f"Requirement: {self.parent}\nWork identity: BR-42/T1\n"
        return type("Result", (), {"stdout": "", "returncode": 0})()

    def link(self, number):
        return ri.link_child(self.root, requirement=self.parent, child=f"example-org/private-backlog#{number}")

    def test_parent_recovery_serializes_with_child_link_and_preserves_reservation(self):
        initial = self.fetch(self.root, "example-org/private-backlog", 42)
        recovery_freshness = threading.Event()
        release_recovery = threading.Event()
        link_attempted_lock = threading.Event()
        link_fetched = threading.Event()
        original_fetch = self.fetch
        original_lock = ri.work_identity.allocation_lock

        @contextmanager
        def observed_lock(requirement):
            if threading.current_thread().name.startswith("link"):
                link_attempted_lock.set()
            with original_lock(requirement):
                yield

        def fetch(root, repository, number):
            if threading.current_thread().name.startswith("recovery") and not recovery_freshness.is_set():
                recovery_freshness.set()
                if not release_recovery.wait(5):
                    raise AssertionError("recovery release was not signaled")
            if threading.current_thread().name.startswith("link"):
                link_fetched.set()
            return original_fetch(root, repository, number)

        with (patch.object(ri.work_identity, "allocation_lock", side_effect=observed_lock),
              patch.object(ri, "fetch_issue", side_effect=fetch),
              ThreadPoolExecutor(max_workers=1, thread_name_prefix="recovery") as recovery_pool,
              ThreadPoolExecutor(max_workers=1, thread_name_prefix="link") as link_pool):
            recovery = recovery_pool.submit(ri.reconcile_requirement_identity, self.root, self.parent, initial)
            try:
                self.assertTrue(recovery_freshness.wait(5))
                link = link_pool.submit(self.link, 10)
                self.assertTrue(link_attempted_lock.wait(5))
                self.assertFalse(link_fetched.is_set(), "link must wait before reading/writing Issues")
            finally:
                release_recovery.set()
            self.assertEqual(ri.work_identity.identity_in(recovery.result()["body"]), "BR-42")
            self.assertEqual(link.result()["work_identity"], "BR-42/T1")
        self.assertIn("example-org/private-backlog#10", ri.parse_requirement_body(self.records[42])["children"])
        self.assertIn("<!-- br-child:example-org/private-backlog#10:1 -->", self.records[42])
        with self.assertRaisesRegex(ri.RequirementIntakeError, "Requirement changed"):
            ri.reconcile_requirement_identity(self.root, self.parent, initial)
        self.assertIn("<!-- br-child:example-org/private-backlog#10:1 -->", self.records[42])

    def test_sibling_scan_flattens_multiple_api_pages(self):
        pages = [[{"number": 10, "body": f"Requirement: {self.parent}\nWork identity: BR-42/T1\n"}],
                 [{"number": 11, "body": f"Requirement: {self.parent}\nWork identity: BR-42/T2\n"}]]
        with patch.object(ri.managed_task, "run_json", return_value=pages) as api:
            siblings = ri._identity_siblings(self.root, self.parent, {})
        self.assertEqual(set(siblings), {"example-org/private-backlog#10", "example-org/private-backlog#11"})
        self.assertIn("--slurp", api.call_args.args[0])

    def test_crlf_identity_is_preserved_on_retry(self):
        self.link(10)
        self.records = {number: body.replace("\n", "\r\n") for number, body in self.records.items()}
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")

    def test_observed_concurrent_requirement_prose_edit_stops_before_replacement(self):
        original = self.fetch
        calls = 0
        def fetch(root, repository, number):
            nonlocal calls
            if number == 42:
                calls += 1
                if calls == 2:
                    self.records[42] = self.records[42].replace("Ship", "Concurrent outcome")
            return original(root, repository, number)
        with patch.object(ri, "fetch_issue", side_effect=fetch):
            with self.assertRaisesRegex(ri.RequirementIntakeError, "Requirement changed"):
                self.link(10)
        self.assertIn("Concurrent outcome", self.records[42])
        self.assertIn("BR-42/T1", self.records[10])
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")

    def test_two_children_retry_removed_and_reordered_links(self):
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")
        self.assertEqual(self.link(11)["work_identity"], "BR-42/T2")
        before = dict(self.records)
        self.link(10)
        self.assertEqual(before, self.records)
        self.records[42] = self.records[42].replace("- [ ] example-org/private-backlog#10\n", "")
        self.assertEqual(self.link(12)["work_identity"], "BR-42/T3")
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")
        lines = self.records[42].splitlines()
        checklist = [line for line in lines if line.startswith("- [ ]")]
        self.records[42] = "\n".join([line for line in lines if not line.startswith("- [ ]")])
        self.records[42] = self.records[42].replace(ri.CHILDREN_END, "\n".join(reversed(checklist)) + "\n" + ri.CHILDREN_END)
        self.assertEqual(self.link(11)["work_identity"], "BR-42/T2")
        parsed = ri.parse_requirement_body(self.records[42])
        self.assertEqual(ri.canonical_requirement_context(parsed)["target_repository"], "example-org/app")

    def test_interruption_after_child_claim_preserves_assignment(self):
        self.interrupt = True
        with self.assertRaisesRegex(ri.RequirementIntakeError, "interruption"):
            self.link(10)
        self.assertIn("BR-42/T1", self.records[10])
        self.assertEqual(self.link(11)["work_identity"], "BR-42/T2")
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")

    def test_concurrent_duplicate_claim_fails_readback(self):
        self.race = True
        with self.assertRaisesRegex(ri.RequirementIntakeError, "duplicate child ordinal"):
            self.link(10)

    def test_lost_parent_write_fails_readback(self):
        original = self.write
        def lost(command, root, env=None):
            if command[:4] == ["gh", "issue", "edit", "42"]:
                return type("Result", (), {"stdout": "", "returncode": 0})()
            return original(command, root, env)
        with patch.object(ri, "run", side_effect=lost):
            with self.assertRaisesRegex(ri.RequirementIntakeError, "readback incomplete"):
                self.link(10)

    def test_conflicting_parent_and_duplicate_ordinals_do_not_write(self):
        self.records[10] = "Requirement: example-org/private-backlog#99\nWork identity: BR-99/T1\n"
        before = dict(self.records)
        with self.assertRaisesRegex(ri.RequirementIntakeError, "canonical parent"):
            self.link(10)
        self.assertEqual(before, self.records)
        self.records[10] = f"Requirement: {self.parent}\nWork identity: BR-42/T1\n"
        self.records[11] = f"Requirement: {self.parent}\nWork identity: BR-42/T1\n"
        with self.assertRaisesRegex(ri.RequirementIntakeError, "duplicate child ordinal"):
            self.link(12)

    def test_legacy_links_receive_stable_identities(self):
        self.records[42] = self.records[42].replace(ri.CHILDREN_END, "- [ ] example-org/private-backlog#10\n" + ri.CHILDREN_END)
        self.records[10] += f"\nRequirement: {self.parent}\n"
        self.assertEqual(self.link(10)["work_identity"], "BR-42/T1")
        self.assertEqual(self.link(11)["work_identity"], "BR-42/T2")

    def test_public_provenance_retains_opaque_handle_and_rejects_unsafe_identity(self):
        from dataclasses import replace
        package = managed_task.Package("example-org/private-backlog#10", "example-org/app", "synthetic", "a" * 40, (), {}, "b" * 64, work_identity="BR-42/T1")
        directory = self.root / "openspec" / "changes" / "synthetic"
        directory.mkdir(parents=True)
        with (patch.object(managed_task.private_lineage, "enabled", return_value=True),
              patch.object(managed_task.private_lineage, "handle_for_issue", return_value="opaque-synthetic-handle")):
            managed_task.write_provenance(directory, package)
            text = (directory / managed_task.PROVENANCE).read_text()
            self.assertNotIn("private-backlog", text)
            self.assertNotIn("source_issue", json.loads(text))
            self.assertEqual(json.loads(text)["work_identity"], "BR-42/T1")
            for unsafe in ("BR-0/T1", "BR-42/T0", "BR-42/T1 private content", "BR-042/T1", 42):
                with self.assertRaises(ri.work_identity.IdentityError):
                    managed_task.write_provenance(directory, replace(package, work_identity=unsafe))
        (directory / managed_task.PROVENANCE).write_text('{"version": 1}')
        self.assertNotIn("work_identity", managed_task.read_provenance(directory))

    def test_legacy_raw_revision_survives_identity_append_without_hiding_scope_edits(self):
        for ending in ["", "\n", "\n\n", "\r\n"]:
            with self.subTest(ending=repr(ending)):
                body = f"Scope\n\nRequirement: {self.parent}" + ending
                issue = {"title": "Synthetic", "body": body, "updated_at": "now"}
                recorded = managed_task.legacy_issue_revision_evidence(issue)["body_sha256"]
                issue["body"] = ri.work_identity.with_identity(body, "BR-42/T1")
                self.assertTrue(managed_task.source_issue_revision_matches(recorded, issue)[1])
                issue["body"] = issue["body"].replace("Scope", "Changed scope")
                self.assertFalse(managed_task.source_issue_revision_matches(recorded, issue)[1])

    def test_deleted_reserved_sibling_identity_or_parent_is_rejected_on_readback(self):
        for deleted in ["Work identity: BR-42/T1", f"Requirement: {self.parent}"]:
            with self.subTest(deleted=deleted):
                self.records = {42: ri.render_requirement_body(outcome="Ship", target_repository="example-org/app"),
                                10: "Technical task\n", 11: "Technical task\n", 12: "Technical task\n"}
                self.link(10)
                original = self.write
                def write(command, root, env=None):
                    result = original(command, root, env)
                    if command[:4] == ["gh", "issue", "edit", "42"] and "--body" in command:
                        self.records[10] = self.records[10].replace(deleted, "")
                    return result
                with patch.object(ri, "run", side_effect=write):
                    with self.assertRaisesRegex(ri.RequirementIntakeError, "claim missing"):
                        self.link(11)

    def test_reserved_child_parent_change_cannot_escape_filtered_readback(self):
        self.link(10)
        original = self.write
        def write(command, root, env=None):
            result = original(command, root, env)
            if command[:4] == ["gh", "issue", "edit", "42"] and "--body" in command:
                self.records[10] = self.records[10].replace(self.parent, "example-org/private-backlog#99")
            return result
        with patch.object(ri, "run", side_effect=write):
            with self.assertRaisesRegex(ri.RequirementIntakeError, "conflicting canonical parent"):
                self.link(11)

    def test_identity_metadata_does_not_create_source_scope_drift(self):
        issue = {"title": "Synthetic", "body": f"Scope\n\nRequirement: {self.parent}\n", "updated_at": "now"}
        recorded = managed_task.issue_revision_evidence(issue)["body_sha256"]
        issue["body"] = ri.work_identity.with_identity(issue["body"], "BR-42/T1")
        self.assertTrue(managed_task.source_issue_revision_matches(recorded, issue)[1])

    def test_import_and_resume_assign_legacy_identity_without_changing_package_revision(self):
        from dataclasses import replace
        self.records[10] += f"\nRequirement: {self.parent}\n"
        package = managed_task.Package("example-org/private-backlog#10", "example-org/app", "synthetic", "a" * 40, (), {}, "b" * 64, parent_requirement=self.parent)
        directory = self.root / "openspec" / "changes" / "synthetic"
        directory.mkdir(parents=True)
        managed_task.write_provenance(directory, replace(package, parent_requirement=None))
        with (patch.object(managed_task, "discover_task", return_value=package),
              patch.object(managed_task, "target_main", return_value="a" * 40),
              patch.object(managed_task, "check_schema"), patch.object(managed_task, "validate_change"),
              patch.object(managed_task, "write_task_state")):
            imported, _, reused = managed_task.import_task(self.root, package.source_issue)
            self.assertTrue(reused)
            self.assertEqual(imported.work_identity, "BR-42/T1")
            self.assertEqual(imported.revision, package.revision)
            self.assertEqual(managed_task.read_provenance(directory)["work_identity"], "BR-42/T1")
            again, _, _ = managed_task.import_task(self.root, package.source_issue)
            self.assertEqual(again.work_identity, imported.work_identity)
        lost = replace(package, parent_requirement=None, work_identity=None)
        with (patch.object(managed_task, "discover_task", return_value=lost),
              patch.object(managed_task, "target_main", return_value="a" * 40),
              patch.object(managed_task, "check_schema"), patch.object(managed_task, "validate_change"),
              patch.object(managed_task, "write_task_state")):
            with self.assertRaisesRegex(managed_task.ManagedTaskError, "conflicts with canonical"):
                managed_task.import_task(self.root, package.source_issue)

    def test_shared_helper_is_copier_managed_for_render_and_upgrade(self):
        source = ROOT / "template" / "scripts" / "managed_work_identity.py"
        self.assertTrue(source.is_file())
        import yaml
        config = yaml.safe_load((ROOT / "copier.yml").read_text())
        self.assertEqual(config["_subdirectory"], "template")
        for pattern in config.get("_exclude", []) + config.get("_skip_if_exists", []):
            self.assertNotEqual(pattern, "scripts/managed_work_identity.py")

    def test_allocation_lock_refuses_symlinks_and_hardlinks(self):
        import hashlib
        import os
        key = hashlib.sha256(self.parent.encode()).hexdigest()
        lock = self.root / f"dev-platform-br-{key}.lock"
        victim = self.root / "synthetic-victim"
        victim.write_text("preserve")
        with patch.object(ri.work_identity.tempfile, "gettempdir", return_value=str(self.root)):
            lock.symlink_to(victim)
            with self.assertRaisesRegex(ri.work_identity.IdentityError, "safe allocation lock"):
                with ri.work_identity.allocation_lock(self.parent):
                    self.fail("unsafe lock was acquired")
            lock.unlink()
            os.link(victim, lock)
            with self.assertRaisesRegex(ri.work_identity.IdentityError, "single-link"):
                with ri.work_identity.allocation_lock(self.parent):
                    self.fail("unsafe lock was acquired")
            self.assertEqual(victim.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
