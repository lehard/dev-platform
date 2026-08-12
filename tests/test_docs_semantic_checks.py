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
        cache: dict[Path, set[str]] = {}
        problems: list[str] = []
        for path in check_docs_links.iter_markdown_files(ROOT):
            problems.extend(check_docs_links.check_file(ROOT, path, cache))
        self.assertEqual(problems, [])

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
