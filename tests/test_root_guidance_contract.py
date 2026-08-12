"""Bounded-context contract for platform-owned root agent guidance.

Root `AGENTS.md` is loaded into every agent task, so it is a navigation and
invariant layer rather than a copy of every workflow manual.  These tests fail
when it grows past the approved budget, loses a required navigation anchor,
re-absorbs relocated detail, or points at a document that does not exist.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Hard budget for platform-owned root guidance.  The operating target agreed in
# `optimize-agent-context-map` is ~80-120 meaningful lines; this ceiling leaves
# limited headroom so a future feature cannot casually append a whole workflow.
# Raising it is a deliberate contract change, not an incidental edit.
MAX_ROOT_GUIDANCE_LINES = 120

# Every always-on category the root map must keep exposing.  An agent that has
# read only this file must still know where the rest of the contract lives.
REQUIRED_ANCHORS = (
    "## Sources of truth",
    "## Task intents",
    "## Always-on invariants",
    "## Entrypoints",
    "## Where the detailed contract lives",
    "## Ownership",
)

# Signature phrases of guidance that now lives in the linked documents.  Their
# reappearance in root guidance means a workflow manual is being re-inlined.
RELOCATED_DETAIL = (
    "--confirm-distinct",
    "exact validated head",
    "workspace-write",
    "shared_workspace.py",
    "worktree_cleanup.py",
    "gh auth refresh -s project",
    "DEV_PLATFORM_SHARED_GROUP",
    "platform_ci_ref",
)

CONDITIONAL = re.compile(r"{%-?\s*(if|elif|else|endif)\b")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def worst_case_rendered_lines(text: str) -> int:
    """Largest line count any profile/publish-mode render can produce.

    Jinja tag lines disappear on render, and only one branch of each conditional
    survives, so counting raw template lines would overstate the always-on cost.
    """
    lines = text.splitlines()
    index = 0

    def block(depth: int) -> int:
        """Count lines until this block's `elif`/`else`/`endif` terminator."""
        nonlocal index
        total = 0
        while index < len(lines):
            match = CONDITIONAL.search(lines[index])
            if match is None:
                index += 1
                total += 1
                continue
            keyword = match.group(1)
            if keyword == "if":
                index += 1
                branches = [block(depth + 1)]
                while index < len(lines) and CONDITIONAL.search(lines[index]).group(1) != "endif":
                    index += 1
                    branches.append(block(depth + 1))
                index += 1  # consume `endif`
                total += max(branches)
                continue
            if depth == 0:
                raise AssertionError(f"unbalanced Jinja conditional near line {index + 1}")
            return total
        if depth:
            raise AssertionError("unterminated Jinja conditional")
        return total

    return block(0)


class RootGuidanceBudgetTests(unittest.TestCase):
    def test_central_root_guidance_is_within_budget(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        count = len(text.splitlines())
        self.assertLessEqual(
            count,
            MAX_ROOT_GUIDANCE_LINES,
            f"AGENTS.md is {count} lines; the always-on budget is {MAX_ROOT_GUIDANCE_LINES}. "
            "Move detailed workflow guidance into docs/engineering/ and link it instead.",
        )

    def test_generated_root_guidance_is_within_budget_for_every_profile(self) -> None:
        text = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        count = worst_case_rendered_lines(text)
        self.assertLessEqual(
            count,
            MAX_ROOT_GUIDANCE_LINES,
            f"template/AGENTS.md.jinja renders up to {count} lines; the always-on budget is "
            f"{MAX_ROOT_GUIDANCE_LINES}. Move detail into template/docs/engineering/ and link it instead.",
        )

    def test_root_guidance_keeps_required_navigation_anchors(self) -> None:
        for relative in ("AGENTS.md", "template/AGENTS.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for anchor in REQUIRED_ANCHORS:
                with self.subTest(relative=relative, anchor=anchor):
                    self.assertIn(
                        anchor,
                        text,
                        f"{relative} lost the required `{anchor}` category; an agent must not have to "
                        "infer it from undocumented convention.",
                    )

    def test_root_guidance_does_not_reabsorb_relocated_detail(self) -> None:
        for relative in ("AGENTS.md", "template/AGENTS.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in RELOCATED_DETAIL:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertNotIn(
                        phrase,
                        text,
                        f"{relative} re-inlines relocated detail ({phrase!r}); it belongs in the linked "
                        "canonical document.",
                    )

    def test_root_guidance_links_resolve(self) -> None:
        for relative, base in (("AGENTS.md", ROOT), ("template/AGENTS.md.jinja", ROOT / "template")):
            text = (ROOT / relative).read_text(encoding="utf-8")
            targets = [target for target in LINK.findall(text) if not target.startswith(("http", "#"))]
            self.assertTrue(targets, f"{relative} exposes no navigation links")
            for target in targets:
                with self.subTest(relative=relative, target=target):
                    self.assertTrue((base / target).exists(), f"{relative} links to missing {target}")

    def test_tool_specific_adapters_stay_thin_references(self) -> None:
        for relative in ("CLAUDE.md", "template/CLAUDE.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("AGENTS.md", text)
                self.assertLessEqual(
                    len(text.splitlines()),
                    12,
                    f"{relative} must stay a thin adapter that references AGENTS.md, not a parallel contract.",
                )


class RenderedRootGuidanceTests(unittest.TestCase):
    """Render the real template when Copier is available."""

    @unittest.skipIf(shutil.which("copier") is None, "copier is not installed")
    def test_every_supported_profile_renders_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as shared:
            # Copier resolves a Git source at a committed ref, which would test
            # HEAD instead of the working tree.  Render from a VCS-free copy so
            # this contract covers the guidance as it is actually written.
            source = Path(shared) / "template-source"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", ".venv", "node_modules"),
            )
            for profile, publish_mode in (("light", "direct"), ("standard", "pr"), ("multi-agent", "pr")):
                with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / "project"
                    subprocess.run(
                        [
                            "copier", "copy", "--trust", "--defaults",
                            "--data", f"project_name=Budget {profile}",
                            "--data", f"project_slug=budget-{profile}",
                            "--data", f"project_description=Root guidance budget {profile}",
                            "--data", f"workflow_profile={profile}",
                            "--data", f"publish_mode={publish_mode}",
                            str(source), str(target),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    self.check_rendered(profile, target)

    def check_rendered(self, profile: str, target: Path) -> None:
        agents = target / "AGENTS.md"
        self.assertTrue(agents.exists(), f"{profile} render produced no AGENTS.md")
        text = agents.read_text(encoding="utf-8")
        count = len(text.splitlines())
        self.assertLessEqual(count, MAX_ROOT_GUIDANCE_LINES, f"{profile} render is {count} lines")
        for anchor in REQUIRED_ANCHORS:
            self.assertIn(anchor, text, f"{profile} render lost `{anchor}`")
        for link in LINK.findall(text):
            if not link.startswith(("http", "#")):
                self.assertTrue((target / link).exists(), f"{profile} render links to missing {link}")


if __name__ == "__main__":
    unittest.main()
