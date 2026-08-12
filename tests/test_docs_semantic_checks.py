from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_ROOT / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_docs_links = _load("check_docs_links")
render_agents_md_smoke = _load("render_agents_md_smoke")


class DocsLinkCheckTests(unittest.TestCase):
    def test_repo_docs_have_no_broken_links_or_anchors(self) -> None:
        scanned = list(check_docs_links.iter_markdown_files(ROOT))
        # A task worktree commonly lives under .../.claude/worktrees/<slug>/;
        # this asserts the scan actually found a realistic number of files
        # rather than silently matching zero, which reads as "no problems"
        # for the wrong reason. See test_scan_is_not_fooled_by_a_dot_claude_ancestor.
        self.assertGreater(len(scanned), 100)
        cache: dict[Path, set[str]] = {}
        problems: list[str] = []
        for path in scanned:
            problems.extend(check_docs_links.check_file(ROOT, path, cache))
        self.assertEqual(problems, [])

    def test_scan_is_not_fooled_by_a_dot_claude_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Reproduces the real task-worktree layout: the repo root itself
            # sits under a path that contains .claude as an ancestor
            # component. Exclusion must be relative to root, not absolute.
            repo_root = Path(tmp) / ".claude" / "worktrees" / "some-task"
            (repo_root / "docs").mkdir(parents=True)
            (repo_root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            found = list(check_docs_links.iter_markdown_files(repo_root))
        self.assertEqual([path.name for path in found], ["guide.md"])

    def test_broken_destination_and_self_anchor_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "a.md"
            doc.write_text("# Title\n\nSee [broken](./nope.md) and [self](#missing-heading) and [good](#title).\n", encoding="utf-8")
            problems = check_docs_links.check_file(root, doc, {})
        self.assertIn("a.md: broken link destination './nope.md'", problems)
        self.assertIn("a.md: broken self anchor '#missing-heading'", problems)
        self.assertEqual(len(problems), 2)

    def test_valid_cross_file_anchor_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target.md").write_text("# Target Heading\n", encoding="utf-8")
            source = root / "source.md"
            source.write_text("[link](./target.md#target-heading)\n", encoding="utf-8")
            problems = check_docs_links.check_file(root, source, {})
        self.assertEqual(problems, [])

    def test_broken_cross_file_anchor_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target.md").write_text("# Target Heading\n", encoding="utf-8")
            source = root / "source.md"
            source.write_text("[link](./target.md#nope)\n", encoding="utf-8")
            problems = check_docs_links.check_file(root, source, {})
        self.assertEqual(problems, ["source.md: broken anchor './target.md#nope'"])


class AgentsMdRenderSmokeTests(unittest.TestCase):
    def test_current_template_renders_for_every_profile(self) -> None:
        for profile in render_agents_md_smoke.PROFILES:
            rendered = render_agents_md_smoke.render(profile)
            for heading in render_agents_md_smoke.REQUIRED_HEADINGS:
                self.assertIn(heading, rendered, f"profile={profile['workflow_profile']} missing {heading!r}")

    def test_undefined_variable_fails_closed(self) -> None:
        import jinja2

        with self.assertRaises(jinja2.exceptions.UndefinedError):
            render_agents_md_smoke.render({"workflow_profile": "light"})


if __name__ == "__main__":
    unittest.main()
