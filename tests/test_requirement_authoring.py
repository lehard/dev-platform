"""Contract coverage for the canonical Business Requirement authoring standard."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _platform_modules import load_platform_module  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
# Insert at position 0 even if present: other test modules prepend the bare
# scripts/ directory, whose shims execute on import.
sys.path.insert(0, str(ROOT / "template" / "scripts"))
manager = load_platform_module("capability_manager", ROOT / "template" / "scripts" / "capability_manager.py")
import requirement_intake as intake  # noqa: E402

CAPABILITY = "dev-platform/capabilities/requirement-authoring.md"
MIRRORED = (
    CAPABILITY,
    "dev-platform/capabilities/requirement-authoring.toml",
    "dev-platform/evals/requirement-authoring-pilot.json",
)
SURFACES = (
    "AGENTS.md",
    "template/AGENTS.md.jinja",
    "docs/engineering/task-intake.md",
    "template/docs/engineering/task-intake.md.jinja",
    "docs/engineering/chatgpt-project-protocol.md",
    "template/docs/engineering/chatgpt-project-protocol.md",
    "docs/engineering/agent-instructions.md",
    "template/docs/engineering/agent-instructions.md",
    "docs/engineering/engineering-capabilities.md",
    "template/docs/engineering/engineering-capabilities.md",
)


def standard() -> str:
    return (ROOT / CAPABILITY).read_text(encoding="utf-8")


class RequirementAuthoringStandardTests(unittest.TestCase):
    def test_standard_carries_every_required_rule(self) -> None:
        text = standard()
        for required in (
            # whole context and classification
            "Use the whole relevant conversation",
            "Accepted and still in force",
            "Superseding refinements",
            "Examples and references",
            "Rejected or hypothetical",
            "Genuinely open",
            # supersession and no chronicle
            "Only explicit acceptance makes something a requirement.",
            "The last option mentioned, an agent's proposal, a quote or a hypothesis is not acceptance.",
            "Do not narrate",
            "active boundary or prohibition",
            # lossless detail
            "without loss",
            "never replaces an exact decision",
            # three levels
            "**Fixed**",
            "**Meaning fixed, execution variable**",
            "**Delegated**",
            "Silence is not blanket freedom",
            # references
            "reachable by the executing agent",
            "say it is unavailable",
            "never substitute a link to a changing site root",
            "Do not copy private conversations, secrets",
            # sections and acceptance
            "successful, failing and forbidden behavior",
            "Keep technical design, file plans and OpenSpec content out",
            # selective questions
            "normally one to three per pass",
            "Do not re-ask what was answered",
            "never write an invented decision or claim agreement",
            "Incubator contract",
            "does not replace the later evidence-first ADD/domain resolution",
            # self-check and whole-contract update
            "**Coverage**",
            "**Consistency**",
            "**Scope**",
            "**Autonomy**",
            "**Portability**",
            "**Truthfulness**",
            "rewrite the **entire current Requirement**",
            "Never hand-edit the children block",
            # scope restraint and proportionality
            "no new global policy",
            "Length follows content",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_standard_adds_no_ritual(self) -> None:
        text = standard()
        self.assertIn(
            "adds no stage, gate, status, validator, scorecard, approval, interview, storage or per-project setting",
            text,
        )
        self.assertIn("does not start implementation", text)
        descriptor = (ROOT / "dev-platform/capabilities/requirement-authoring.toml").read_text(encoding="utf-8")
        self.assertIn('kind = "instruction-only"', descriptor)
        self.assertIn("creates no storage, gate, status, validator, approval, interview or per-project setting", descriptor)
        self.assertIn("or run a mandatory interview", text)
        for banned in ("LLM judge", "scorecard required", "approval gate required"):
            self.assertNotIn(banned, text)

    def test_representative_cases_cover_the_acceptance_scenarios(self) -> None:
        text = standard()
        for case in (
            "**Long discussion.**",
            "**Superseded option.**",
            "**Reference.**",
            "**Local prohibition.**",
            "**Compact request.**",
            "**Unresolved fork.**",
        ):
            with self.subTest(case=case):
                self.assertIn(case, text)
        self.assertIn("quotes the text as *verbatim*", text)
        self.assertIn("no questionnaire, no empty sections", text)
        self.assertIn("instead of linking the site's home page", text)
        self.assertIn("It does not become a company-wide notification policy.", text)
        self.assertIn("no longer requires the earlier all-users export check", text)

    def test_canonical_source_is_mirrored_byte_for_byte(self) -> None:
        for relative in MIRRORED:
            with self.subTest(relative=relative):
                self.assertEqual(
                    (ROOT / relative).read_bytes(),
                    (ROOT / "template" / relative).read_bytes(),
                )

    def test_every_surface_points_to_the_one_source_without_restating_it(self) -> None:
        restated = ("Superseding refinements", "Meaning fixed, execution variable", "Truthfulness")
        for relative in SURFACES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("capabilities/requirement-authoring.md", text)
                for fragment in restated:
                    self.assertNotIn(fragment, text)

    def test_chatgpt_protocol_reads_the_same_file_and_adds_no_step(self) -> None:
        for relative in ("docs/engineering/chatgpt-project-protocol.md", "template/docs/engineering/chatgpt-project-protocol.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("same canonical authoring standard a repository agent uses", text)
                self.assertIn("adds no step for the user", text)

    def test_task_intake_states_the_boundary(self) -> None:
        for relative in ("docs/engineering/task-intake.md", "template/docs/engineering/task-intake.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("### Requirement content authoring", text)
                self.assertIn("it adds no gate, validator, status, approval, interview, storage or per-project\nsetting", text)
                self.assertIn("does not start implementation", text)
                self.assertIn("read without enabling it", text)

    def test_claude_and_codex_skills_carry_identical_standard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "dev-platform" / "capabilities").mkdir(parents=True)
            (root / "dev-platform" / "evals").mkdir()
            (root / "scripts").mkdir()
            (root / "scripts" / "capability_manager.py").write_text("# isolated adapter fixture\n", encoding="utf-8")
            (root / ".dev-platform.toml").write_text('agent_tools = "claude,codex"\n', encoding="utf-8")
            shutil.copyfile(ROOT / "dev-platform" / "capabilities.toml", root / "dev-platform" / "capabilities.toml")
            for relative in MIRRORED:
                shutil.copyfile(ROOT / relative, root / relative)
            capability = manager.load_registry(root)["requirement-authoring"]
            self.assertEqual(capability.kind, "instruction-only")
            self.assertEqual(capability.invocation, "auto+explicit")
            manager.write_selection(root, [capability.identifier])
            manager.sync(root, manager.load_registry(root), manager.load_selection(root))
            self.assertEqual(manager.audit(root, manager.load_registry(root), manager.load_selection(root))["status"], "ok")
            claude = (root / ".claude" / "skills" / "dev-platform-requirement-authoring" / "SKILL.md").read_text(encoding="utf-8")
            codex = (root / ".codex" / "skills" / "dev-platform-requirement-authoring" / "SKILL.md").read_text(encoding="utf-8")
            body = standard().strip()
            self.assertIn(body, claude)
            self.assertIn(body, codex)
            self.assertIn("dev-platform-capability:id=requirement-authoring", claude)
            self.assertIn("dev-platform-capability:id=requirement-authoring", codex)

    def test_capability_is_not_enabled_by_default_and_needs_no_project_edit(self) -> None:
        self.assertEqual(manager.load_selection(ROOT), [])
        self.assertIn("enabled = []", (ROOT / "template" / "dev-platform" / "capabilities.toml").read_text(encoding="utf-8"))

    def test_eval_fixture_is_bound_to_the_standard_and_passes(self) -> None:
        fixture_path = ROOT / "dev-platform" / "evals" / "requirement-authoring-pilot.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["content_sha256"], hashlib.sha256((ROOT / CAPABILITY).read_bytes()).hexdigest())
        descriptor = (ROOT / "dev-platform/capabilities/requirement-authoring.toml").read_text(encoding="utf-8")
        self.assertIn(f'content_sha256 = "{fixture["content_sha256"]}"', descriptor)
        negatives = [case for case in fixture["cases"] if case["expectation"] == "not-trigger"]
        self.assertGreaterEqual(len(negatives), 10)
        capability = manager.load_registry(ROOT)["requirement-authoring"]
        report = manager.evaluate_existing(capability, fixture_path, runtime="fixture", runs=3)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["incomplete"], 0)
        self.assertEqual(report["summary"]["case_count"], len(fixture["cases"]))
        self.assertTrue(all(item["improved"] for item in report["quality_comparisons"]))


class RequirementFormatCompatibilityTests(unittest.TestCase):
    """A Requirement written under the standard keeps the unchanged Issue format."""

    def test_compact_and_detailed_bodies_use_only_existing_sections(self) -> None:
        compact = intake.render_requirement_body(
            outcome='Rename the Export button to "Download CSV".',
            target_repository="acme/app",
            acceptance_evidence='The button reads exactly "Download CSV" and still exports the same file.',
        )
        detailed = intake.render_requirement_body(
            outcome="Managers export the filtered list; the empty state shows the agreed text verbatim.",
            context="Mockup: https://example.test/design/export-v2.png (header hierarchy and button wording mandatory).",
            acceptance_evidence="Success: manager exports. Failure: non-manager sees no export. Forbidden: any all-users export.",
            target_repository="acme/app",
            exclusions="No company-wide notification policy.",
        )
        for body, expected in (
            (compact, {"outcome", "acceptance evidence", "target repository"}),
            (detailed, {"outcome", "context", "acceptance evidence", "target repository", "exclusions"}),
        ):
            parsed = intake.parse_requirement_body(body)
            with self.subTest(sections=sorted(expected)):
                self.assertEqual(set(parsed["sections"]), expected)
                self.assertEqual(parsed["children"], [])
                self.assertIn(intake.CHILDREN_START, body)
                self.assertIn(intake.CHILDREN_END, body)

    def test_standard_defines_no_new_section_or_marker(self) -> None:
        text = standard()
        for section in ("## Outcome", "## Context", "## Acceptance evidence", "## Exclusions"):
            self.assertNotIn(f"\n{section}\n", text)
        self.assertNotIn("requirement-children:start", text)


class RenderedProjectTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("copier") is None, "copier is not installed")
    def test_managed_project_receives_the_standard_with_no_setup(self) -> None:
        link = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)")
        with tempfile.TemporaryDirectory() as shared:
            # Render the working tree, not the committed ref (see test_root_guidance_contract).
            source = Path(shared) / "template-source"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", ".venv", "node_modules", ".ruff_cache", ".pytest_cache"),
            )
            # The portable render has no Requirement flow, so its task-intake
            # carries no pointer; an operator-integrated render does.
            for profile, publish_mode, operator in (("light", "direct", False), ("multi-agent", "pr", True)):
                with self.subTest(profile=profile, operator=operator), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / "project"
                    subprocess.run(
                        [
                            "copier", "copy", "--trust", "--defaults",
                            "--data", f"project_name=Authoring {profile}",
                            "--data", f"project_slug=authoring-{profile}",
                            "--data", f"project_description=Requirement authoring render {profile}",
                            "--data", f"workflow_profile={profile}",
                            "--data", f"publish_mode={publish_mode}",
                            "--data", f"operator_integration={'true' if operator else 'false'}",
                            str(source), str(target),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    rendered = target / CAPABILITY
                    self.assertEqual(rendered.read_bytes(), (ROOT / CAPABILITY).read_bytes())
                    self.assertIn("enabled = []", (target / "dev-platform" / "capabilities.toml").read_text(encoding="utf-8"))
                    self.assertFalse((target / ".claude" / "skills" / "dev-platform-requirement-authoring").exists())
                    self.assertFalse((target / ".codex" / "skills" / "dev-platform-requirement-authoring").exists())
                    pointers = [
                        "AGENTS.md",
                        "docs/engineering/chatgpt-project-protocol.md",
                        "docs/engineering/agent-instructions.md",
                        "docs/engineering/engineering-capabilities.md",
                    ]
                    if operator:
                        pointers.append("docs/engineering/task-intake.md")
                    for relative in pointers:
                        text = (target / relative).read_text(encoding="utf-8")
                        self.assertIn("capabilities/requirement-authoring.md", text, relative)
                        for destination in link.findall(text):
                            if destination.endswith("requirement-authoring.md"):
                                self.assertTrue(
                                    ((target / relative).parent / destination).resolve().exists(),
                                    f"{profile}: {relative} links to missing {destination}",
                                )


if __name__ == "__main__":
    unittest.main()
