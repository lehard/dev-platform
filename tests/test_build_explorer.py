"""Contract tests for the source-derived static Explorer build (scripts/build_explorer.py)."""
from __future__ import annotations

import contextlib
import html.parser
import io
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import urllib.parse
from pathlib import Path

from _platform_modules import load_platform_module

ROOT = Path(__file__).resolve().parents[1]

# build_explorer imports its sibling `public_distribution` by name. Expose
# scripts/ only while loading so later imports in the same process (for example
# the `openspec_lifecycle` adapter that would shadow template/scripts) are
# unaffected.
sys.path.insert(0, str(ROOT / "scripts"))
try:
    explorer = load_platform_module("build_explorer", ROOT / "scripts" / "build_explorer.py")
finally:
    sys.path.remove(str(ROOT / "scripts"))
ExplorerError = explorer.ExplorerError

README = textwrap.dedent(
    """\
    # Fixture

    ## Intro

    First paragraph of the intro.

    More intro with `code` and **bold** text.

    ## Other

    Read the [guide](docs/guide.md) and the [part](docs/guide.md#part).
    Also see [the notes](docs/notes.md) and [the tests folder](tests/).
    """
)
GUIDE = "# Guide\n\nGuide paragraph with *emphasis*.\n\n## Part\n\nPart text.\n"
NOTES = "# Notes\n\nNotes paragraph.\n"
SPEC = "# alpha Specification\n\n## Purpose\nAlpha purpose sentence.\n\n## Requirements\n\n### Requirement: A\nText.\n"
ELEMENT_MAP = textwrap.dedent(
    """\
    [site]
    title = "Fixture Explorer"

    [[element]]
    id = "home"
    title = "Home"
    order = 1
    sources = ["README.md#Intro"]
    related = ["guide"]

    [[element]]
    id = "guide"
    title = "Guide"
    parent = "home"
    order = 1
    sources = ["docs/guide.md"]

    [[element]]
    id = "other"
    title = "Other"
    parent = "home"
    order = 2
    sources = ["README.md#Other"]

    [[collection]]
    id = "specs"
    title = "Specs"
    parent = "home"
    order = 3
    glob = "openspec/specs/*/spec.md"
    title_from = "slug"
    summary_from = "section:Purpose"
    slug_from = "parent"
    """
)
STAGES = textwrap.dedent(
    """
    [[stage]]
    id = "start"
    title = "Start here"
    order = 1
    elements = ["home", "guide"]
    sources = ["README.md#Intro"]

    [[stage]]
    id = "middle"
    title = "Middle step"
    order = 2
    elements = ["guide"]
    sources = ["docs/guide.md#Part", "docs/notes.md"]

    [[stage]]
    id = "finish"
    title = "Finish"
    order = 3
    elements = ["other", "specs.alpha"]
    sources = ["README.md#Other"]
    """
)
MAP = ELEMENT_MAP + STAGES
BASE_FILES = {
    "VERSION": "9.9.9\n",
    "README.md": README,
    "docs/guide.md": GUIDE,
    "docs/notes.md": NOTES,
    "tests/keep.txt": "keep\n",
    "openspec/specs/alpha/spec.md": SPEC,
    "explorer/map.toml": MAP,
    "explorer/assets/explorer.css": "body { margin: 0; }\n",
    "explorer/assets/explorer.js": "// enhancement\n",
}

GIT_ENV = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "-c", "commit.gpgsign=false"]


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *GIT_ENV, *args], cwd=root, check=True, capture_output=True)


class FixtureTestCase(unittest.TestCase):
    def make_repo(self, overrides: dict[str, str | None] | None = None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "repo"
        root.mkdir()
        files = dict(BASE_FILES)
        files.update(overrides or {})
        for relative, text in files.items():
            if text is not None:
                self.write(root, relative, text)
        git(root, "init", "-q")
        self.commit(root)
        return root

    def write(self, root: Path, relative: str, text: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, root: Path) -> None:
        git(root, "add", "-A")
        git(root, "commit", "-q", "--allow-empty", "-m", "fixture")

    def build(self, root: Path) -> dict[str, bytes]:
        return explorer.build_site(root)[1]

    def page(self, outputs: dict[str, bytes], identifier: str) -> str:
        return outputs[f"e/{identifier}/index.html"].decode("utf-8")

    def assert_build_fails(self, root: Path, *needles: str) -> str:
        with self.assertRaises(ExplorerError) as caught:
            self.build(root)
        message = str(caught.exception)
        for needle in needles:
            self.assertIn(needle, message)
        return message

    def run_main(self, *argv: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            code = explorer.main(list(argv))
        return code, stderr.getvalue()


class CleanBuildTests(FixtureTestCase):
    def test_clean_build_writes_index_element_and_collection_item_pages(self) -> None:
        outputs = self.build(self.make_repo())
        for path in (
            "index.html", "e/home/index.html", "e/guide/index.html", "e/other/index.html",
            "e/specs/index.html", "e/specs.alpha/index.html", "assets/explorer.css", "assets/explorer.js",
        ):
            with self.subTest(path=path):
                self.assertIn(path, outputs)

    def test_page_shows_navigation_excerpt_related_parents_sources_and_stamp(self) -> None:
        root = self.make_repo()
        outputs = self.build(root)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        guide = self.page(outputs, "guide")
        self.assertIn('<nav class="tree"', guide)
        self.assertIn('aria-current="page">Guide</a>', guide)
        self.assertIn("Guide paragraph with <em>emphasis</em>.", guide)
        self.assertIn('aria-label="Where it fits"', guide)
        self.assertIn('<a href="../home/index.html">Home</a>', guide)
        self.assertIn(f"/blob/{commit}/docs/guide.md", guide)
        self.assertIn("Dev Platform 9.9.9", guide)
        self.assertIn(commit[:7], guide)
        # Declared relation is visible on the source page and as a back link on the target.
        self.assertIn('<h2>Related</h2>', self.page(outputs, "home"))
        self.assertIn('<a href="../home/index.html">Home</a>', guide.split('id="related"')[1])

    def test_heading_section_excerpt_stops_at_next_heading_of_same_level(self) -> None:
        home = self.page(self.build(self.make_repo()), "home")
        self.assertIn("First paragraph of the intro.", home)
        self.assertIn("<code>code</code>", home)
        self.assertNotIn("Read the", home.split('id="in-this-area"')[0])

    def test_collection_items_take_title_summary_and_source_from_the_file(self) -> None:
        outputs = self.build(self.make_repo())
        listing = self.page(outputs, "specs")
        self.assertIn(">alpha</a>", listing)
        self.assertIn("Alpha purpose sentence.", listing)
        self.assertIn("<h2 id=\"s-purpose\">Purpose</h2>", self.page(outputs, "specs.alpha"))

    def test_pages_work_without_javascript(self) -> None:
        outputs = self.build(self.make_repo())
        page = self.page(outputs, "guide")
        self.assertIn('<script defer src="../../assets/explorer.js">', page)
        self.assertIn('<details open><summary><a href="../home/index.html">Home</a>', page)

    def test_cli_check_and_build_succeed_and_build_writes_files(self) -> None:
        root = self.make_repo()
        code, _ = self.run_main("--root", str(root), "check")
        self.assertEqual(code, 0)
        out = root.parent / "site"
        code, _ = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 0)
        self.assertTrue((out / "e" / "guide" / "index.html").is_file())
        code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("not empty", stderr)

    def test_clean_tree_footer_has_no_uncommitted_marker_and_dirty_tree_is_labelled(self) -> None:
        root = self.make_repo()
        self.assertNotIn("uncommitted", self.page(self.build(root), "guide"))
        guide = root / "docs" / "guide.md"
        guide.write_text(guide.read_text(encoding="utf-8") + "\nchanged but not committed\n", encoding="utf-8")
        self.assertIn("with uncommitted changes", self.page(self.build(root), "guide"))

    def test_failed_write_leaves_no_partial_output(self) -> None:
        root = self.make_repo()
        outputs = self.build(root)
        out = root.parent / "partial"
        outputs = dict(outputs)
        outputs["e/blocked/index.html"] = "not bytes"  # type: ignore[assignment]
        with self.assertRaises(Exception):
            explorer.write_outputs(out, outputs)
        self.assertFalse(out.exists())
        self.assertEqual([p.name for p in root.parent.iterdir() if "staging" in p.name], [])

    def test_script_runs_as_a_command_from_another_directory(self) -> None:
        root = self.make_repo()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_explorer.py"), "--root", str(root), "check"],
            cwd=root.parent, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("explorer checked", result.stdout)


class MapValidationTests(FixtureTestCase):
    def test_invalid_maps_fail_naming_the_problem(self) -> None:
        cases = {
            "unknown element key": (MAP.replace('order = 2\nsources = ["README.md#Other"]', 'order = 2\nsources = ["README.md#Other"]\nprose = "x"'), "unknown key"),
            "unknown top-level key": (MAP + '\n[extra]\nkey = 1\n', "unknown top-level"),
            "missing site": (MAP.replace('[site]\ntitle = "Fixture Explorer"\n', ""), "[site]"),
            "duplicate id": (MAP.replace('id = "other"', 'id = "guide"'), "duplicate id 'guide'"),
            "dangling parent": (MAP.replace('parent = "home"\norder = 2', 'parent = "nope"\norder = 2'), "dangling parent 'nope'"),
            "dangling related": (MAP.replace('related = ["guide"]', 'related = ["nope"]'), "unknown id 'nope'"),
            "self related": (MAP.replace('related = ["guide"]', 'related = ["home"]'), "relates to itself"),
            "empty sources on leaf": (MAP.replace('sources = ["README.md#Other"]', "sources = []", 1), "no sources and no children"),
            "bad id": (MAP.replace('id = "other"', 'id = "Other_One"'), "kebab-case"),
            "non-integer order": (MAP.replace('order = 2\nsources', 'order = "2"\nsources'), "'order' must be an integer"),
            "absolute source": (MAP.replace('sources = ["docs/guide.md"]', 'sources = ["/docs/guide.md"]'), "normalized repository-relative"),
            "empty heading": (MAP.replace('"README.md#Other"', '"README.md#"'), "empty heading"),
            "duplicate source": (MAP.replace('sources = ["docs/guide.md"]', 'sources = ["docs/guide.md", "docs/guide.md"]'), "duplicate source"),
            "bad title_from": (MAP.replace('title_from = "slug"', 'title_from = "magic"'), "title_from"),
            "bad glob": (MAP.replace('openspec/specs/*/spec.md', 'openspec/**/spec.md'), "'**'"),
            "empty glob": (MAP.replace('openspec/specs/*/spec.md', 'openspec/specs/*/missing.md'), "matches no"),
            "invalid toml": ("[site\n", "not valid TOML"),
        }
        for name, (text, needle) in cases.items():
            with self.subTest(case=name):
                root = self.make_repo({"explorer/map.toml": text})
                self.assert_build_fails(root, needle)

    def test_parent_cycle_is_rejected(self) -> None:
        text = MAP.replace('id = "home"\ntitle = "Home"', 'id = "home"\nparent = "guide"\ntitle = "Home"')
        self.assert_build_fails(self.make_repo({"explorer/map.toml": text}), "cycle")

    def test_element_cannot_be_placed_under_a_collection(self) -> None:
        text = MAP.replace('parent = "home"\norder = 2', 'parent = "specs"\norder = 2')
        self.assert_build_fails(self.make_repo({"explorer/map.toml": text}), "cannot be placed under collection")


class SourceResolutionTests(FixtureTestCase):
    def test_missing_file_names_element_and_source(self) -> None:
        text = MAP.replace('"docs/guide.md"', '"docs/absent.md"')
        self.assert_build_fails(self.make_repo({"explorer/map.toml": text}), "element 'guide'", "docs/absent.md", "not a git-tracked file")

    def test_missing_heading_names_element_and_source(self) -> None:
        text = MAP.replace('"docs/guide.md"', '"docs/guide.md#Renamed"')
        self.assert_build_fails(self.make_repo({"explorer/map.toml": text}), "element 'guide'", "docs/guide.md#Renamed", "heading 'Renamed' not found")

    def test_changing_a_heading_used_by_the_map_fails_the_build(self) -> None:
        root = self.make_repo()
        self.build(root)
        self.write(root, "README.md", README.replace("## Intro", "## Introduction"))
        self.commit(root)
        self.assert_build_fails(root, "element 'home'", "README.md#Intro")

    def test_ambiguous_heading_is_rejected(self) -> None:
        root = self.make_repo({"docs/guide.md": GUIDE + "\n## Part\n\nAgain.\n"})
        text = MAP.replace('"docs/guide.md"', '"docs/guide.md#Part"')
        self.write(root, "explorer/map.toml", text)
        self.commit(root)
        self.assert_build_fails(root, "ambiguous")

    def test_untracked_source_is_rejected(self) -> None:
        root = self.make_repo()
        self.write(root, "docs/draft.md", "# Draft\n\ntext\n")
        self.write(root, "explorer/map.toml", MAP.replace('"docs/guide.md"', '"docs/draft.md"'))
        git(root, "add", "explorer/map.toml")
        git(root, "commit", "-q", "-m", "map")
        self.assert_build_fails(root, "docs/draft.md", "not a git-tracked file")

    def test_source_excluded_by_public_distribution_policy_is_rejected(self) -> None:
        root = self.make_repo({".claude/notes.md": "# Notes\n\nlocal agent state\n"})
        self.write(root, "explorer/map.toml", MAP.replace('"docs/guide.md"', '".claude/notes.md"'))
        self.commit(root)
        self.assert_build_fails(root, "element 'guide'", ".claude/notes.md", "excluded by the public-distribution policy")

    def test_failure_leaves_no_output_directory(self) -> None:
        root = self.make_repo({"explorer/map.toml": MAP.replace('"docs/guide.md"', '"docs/absent.md"')})
        out = root.parent / "site"
        code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("docs/absent.md", stderr)
        self.assertFalse(out.exists())

    def test_running_outside_git_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, text in BASE_FILES.items():
                self.write(root, relative, text)
            with self.assertRaises(ExplorerError) as caught:
                self.build(root)
            self.assertIn("Git checkout", str(caught.exception))

    def test_repository_without_a_commit_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, text in BASE_FILES.items():
                self.write(root, relative, text)
            git(root, "init", "-q")
            git(root, "add", "-A")
            with self.assertRaises(ExplorerError) as caught:
                self.build(root)
            self.assertIn("source commit", str(caught.exception))

    def test_missing_version_file_fails_explicitly(self) -> None:
        root = self.make_repo({"VERSION": None})
        self.assert_build_fails(root, "VERSION")


class CollectionTests(FixtureTestCase):
    def test_new_collection_item_appears_without_editing_the_map(self) -> None:
        root = self.make_repo()
        self.assertNotIn("e/specs.beta/index.html", self.build(root))
        self.write(root, "openspec/specs/beta/spec.md", SPEC.replace("alpha", "beta").replace("Alpha purpose", "Beta purpose"))
        self.commit(root)
        outputs = self.build(root)
        self.assertIn("e/specs.beta/index.html", outputs)
        self.assertIn("Beta purpose sentence.", self.page(outputs, "specs"))

    def test_collection_item_without_required_summary_section_fails(self) -> None:
        root = self.make_repo({"openspec/specs/beta/spec.md": "# beta\n\nNo purpose section.\n"})
        self.assert_build_fails(root, "openspec/specs/beta/spec.md", "section:Purpose")

    def test_toml_descriptor_collection_renders_the_descriptor_and_companion(self) -> None:
        collection = textwrap.dedent(
            """
            [[collection]]
            id = "caps"
            title = "Caps"
            parent = "home"
            order = 4
            glob = "caps/*.toml"
            title_from = "toml:capability.name"
            summary_from = "toml:capability.description"
            slug_from = "stem"
            companions = ["caps/{stem}.md"]
            """
        )
        root = self.make_repo({
            "explorer/map.toml": MAP + collection,
            "caps/one.toml": '[capability]\nname = "One cap"\ndescription = "Does one thing."\n',
            "caps/one.md": "Companion guidance paragraph.\n",
        })
        outputs = self.build(root)
        page = self.page(outputs, "caps.one")
        self.assertIn("One cap", page)
        self.assertIn("Companion guidance paragraph.", page)
        self.assertIn("Does one thing.", self.page(outputs, "caps"))

    def test_missing_companion_fails(self) -> None:
        collection = MAP + textwrap.dedent(
            """
            [[collection]]
            id = "caps"
            title = "Caps"
            order = 4
            glob = "caps/*.toml"
            title_from = "toml:capability.name"
            summary_from = "toml:capability.description"
            slug_from = "stem"
            companions = ["caps/{stem}.md"]
            """
        )
        root = self.make_repo({"explorer/map.toml": collection, "caps/one.toml": '[capability]\nname = "One"\ndescription = "d"\n'})
        self.assert_build_fails(root, "caps/one.md", "not a git-tracked file")


def stage_block(identifier: str) -> str:
    """Return the fixture ``[[stage]]`` table text for ``identifier``."""
    for block in STAGES.strip().split("\n\n"):
        if f'id = "{identifier}"' in block:
            return block
    raise AssertionError(identifier)


class LifecycleTests(FixtureTestCase):
    def lifecycle(self, outputs: dict[str, bytes]) -> str:
        return outputs["lifecycle/index.html"].decode("utf-8")

    def flow(self, outputs: dict[str, bytes]) -> str:
        return self.lifecycle(outputs).split('<ol class="flow">')[1].split("</ol>")[0]

    def stage_page(self, outputs: dict[str, bytes], identifier: str) -> str:
        return outputs[f"lifecycle/{identifier}/index.html"].decode("utf-8")

    def hrefs(self, page: str) -> list[str]:
        collector = LinkCollector()
        collector.feed(page)
        return collector.links

    # -- success scenarios -----------------------------------------------------

    def test_overview_and_every_stage_page_are_generated(self) -> None:
        outputs = self.build(self.make_repo())
        for path in ("lifecycle/index.html", "lifecycle/start/index.html", "lifecycle/middle/index.html", "lifecycle/finish/index.html"):
            with self.subTest(path=path):
                self.assertIn(path, outputs)

    def test_overview_lists_every_stage_in_order_with_stable_relative_links(self) -> None:
        page = self.lifecycle(self.build(self.make_repo()))
        flow = page.split('<ol class="flow">')[1].split("</ol>")[0]
        positions = [flow.index(f'href="{target}"') for target in ("start/index.html", "middle/index.html", "finish/index.html")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('<a href="start/index.html">Start here</a>', flow)
        self.assertIn('<a href="middle/index.html">Middle step</a>', flow)
        self.assertIn('<span class="flow-number" aria-hidden="true">3</span>', flow)
        # The first paragraph of the source heading is the summary: rendered from the source, not the map.
        self.assertIn("First paragraph of the intro.", flow)

    def test_home_page_shows_the_same_ordered_flow(self) -> None:
        home = self.build(self.make_repo())["index.html"].decode("utf-8")
        self.assertIn('<a href="lifecycle/start/index.html">Start here</a>', home)
        self.assertLess(home.index("lifecycle/start/index.html"), home.index("lifecycle/finish/index.html"))

    def test_stage_page_renders_source_excerpts_and_links_to_sources(self) -> None:
        root = self.make_repo()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        middle = self.stage_page(self.build(root), "middle")
        self.assertIn("<h1>Middle step</h1>", middle)
        self.assertIn("Stage 2 of 3", middle)
        self.assertIn("Part text.", middle)
        self.assertIn("Notes paragraph.", middle)
        self.assertIn(f'href="https://github.com/lehard/dev-platform/blob/{commit}/docs/guide.md" rel="noopener noreferrer"><code>docs/guide.md#Part</code>', middle)
        self.assertIn(f"/blob/{commit}/docs/notes.md", middle)

    def test_stage_page_links_to_previous_and_next_stage(self) -> None:
        outputs = self.build(self.make_repo())
        middle = self.stage_page(outputs, "middle")
        self.assertIn('<a rel="prev" href="../start/index.html">Previous: Start here</a>', middle)
        self.assertIn('<a rel="next" href="../finish/index.html">Next: Finish</a>', middle)
        self.assertIn('<a href="../index.html">All stages</a>', middle)

    def test_first_and_last_stage_omit_the_missing_neighbour(self) -> None:
        outputs = self.build(self.make_repo())
        first, last = self.stage_page(outputs, "start"), self.stage_page(outputs, "finish")
        self.assertNotIn('rel="prev"', first)
        self.assertIn('rel="next" href="../middle/index.html"', first)
        self.assertNotIn('rel="next"', last)
        self.assertIn('rel="prev" href="../middle/index.html"', last)

    def test_stage_page_links_to_component_elements_with_titles_and_at_least_one(self) -> None:
        outputs = self.build(self.make_repo())
        start = self.stage_page(outputs, "start").split('id="components"')[1]
        self.assertIn('<a href="../../e/home/index.html">Home</a>', start)
        self.assertIn('<a href="../../e/guide/index.html">Guide</a>', start)
        self.assertIn("Guide paragraph with", start)
        finish = self.stage_page(outputs, "finish").split('id="components"')[1]
        self.assertIn('href="../../e/specs.alpha/index.html"', finish)

    def test_links_inside_stage_excerpts_resolve_to_element_pages(self) -> None:
        finish = self.stage_page(self.build(self.make_repo()), "finish")
        self.assertIn('<a href="../../e/guide/index.html">guide</a>', finish)
        self.assertIn('<a href="../../e/guide/index.html#s-part">part</a>', finish)

    def test_stage_order_not_file_order_decides_the_sequence(self) -> None:
        reordered = ELEMENT_MAP + "\n\n".join(stage_block(name) for name in ("finish", "start", "middle")) + "\n"
        root = self.make_repo({"explorer/map.toml": reordered})
        outputs = self.build(root)
        baseline = self.build(self.make_repo())
        self.assertEqual(self.flow(outputs), self.flow(baseline))
        self.assertIn('rel="next" href="../middle/index.html"', self.stage_page(outputs, "start"))

    def test_stage_may_share_an_id_with_an_element(self) -> None:
        text = MAP.replace('id = "middle"', 'id = "guide"')
        outputs = self.build(self.make_repo({"explorer/map.toml": text}))
        self.assertIn("lifecycle/guide/index.html", outputs)
        self.assertIn("e/guide/index.html", outputs)

    # -- navigation and cross-links ---------------------------------------------

    def test_navigation_tree_has_a_lifecycle_branch_listing_stages_in_order(self) -> None:
        outputs = self.build(self.make_repo())
        for path in ("index.html", "e/guide/index.html", "lifecycle/index.html", "lifecycle/middle/index.html"):
            with self.subTest(page=path):
                tree = outputs[path].decode("utf-8").split('<nav class="tree"')[1].split("</nav>")[0]
                self.assertIn(">Lifecycle</a></summary>", tree)
                positions = [tree.index(f"{number}. ") for number in (1, 2, 3)]
                self.assertEqual(positions, sorted(positions))
        tree = self.stage_page(outputs, "middle").split('<nav class="tree"')[1].split("</nav>")[0]
        self.assertIn('<details open><summary><a href="../index.html">Lifecycle</a>', tree)
        self.assertIn('<a href="index.html" aria-current="page">2. Middle step</a>', tree)
        self.assertEqual(tree.count('aria-current="page"'), 1)

    def test_lifecycle_branch_is_collapsed_on_unrelated_pages_and_current_on_overview(self) -> None:
        outputs = self.build(self.make_repo())
        guide_tree = outputs["e/guide/index.html"].decode("utf-8").split('<nav class="tree"')[1]
        self.assertIn("<li><details><summary><a href=\"../../lifecycle/index.html\">Lifecycle</a>", guide_tree)
        overview_tree = self.lifecycle(outputs).split('<nav class="tree"')[1]
        self.assertIn('<a href="index.html" aria-current="page">Lifecycle</a>', overview_tree)

    def test_component_page_lists_the_stages_that_use_it(self) -> None:
        outputs = self.build(self.make_repo())
        guide = self.page(outputs, "guide")
        section = guide.split('id="lifecycle-usage"')[1].split("</section>")[0]
        self.assertIn("<h2>Used in lifecycle stages</h2>", section)
        self.assertIn('<a href="../../lifecycle/start/index.html">Stage 1: Start here</a>', section)
        self.assertIn('<a href="../../lifecycle/middle/index.html">Stage 2: Middle step</a>', section)
        self.assertNotIn("Finish", section)
        self.assertIn('Stage 3: Finish', self.page(outputs, "specs.alpha"))

    def test_component_without_a_stage_has_no_usage_section(self) -> None:
        outputs = self.build(self.make_repo())
        self.assertNotIn("lifecycle-usage", self.page(outputs, "specs"))

    # -- invalid stage definitions -------------------------------------------------

    def test_invalid_stage_definitions_fail_naming_the_stage(self) -> None:
        cases = {
            "duplicate order": (MAP.replace('title = "Finish"\norder = 3', 'title = "Finish"\norder = 2'), ("stage 'finish'", "order 2 duplicates stage 'middle'")),
            "gapped order": (MAP.replace('title = "Finish"\norder = 3', 'title = "Finish"\norder = 4'), ("stage 'finish'", "order 4 is not contiguous", "expected 3")),
            "order not starting at 1": (
                MAP.replace('title = "Start here"\norder = 1', 'title = "Start here"\norder = 0'),
                ("stage 'start'", "positive integer"),
            ),
            "order starting above 1": (
                MAP.replace('order = 1\nelements = ["home", "guide"]', 'order = 5\nelements = ["home", "guide"]'),
                ("stage 'middle'", "order 2 is not contiguous", "expected 1"),
            ),
            "non-integer order": (MAP.replace('title = "Finish"\norder = 3', 'title = "Finish"\norder = "3"'), ("stage 'finish'", "'order' must be an integer")),
            "duplicate id": (MAP.replace('id = "finish"', 'id = "middle"'), ("duplicate stage id 'middle'",)),
            "bad id": (MAP.replace('id = "finish"', 'id = "Finish_Line"'), ("stage 'Finish_Line'", "kebab-case")),
            "missing element": (MAP.replace('elements = ["other", "specs.alpha"]', 'elements = ["other", "ghost"]'), ("stage 'finish'", "unknown element 'ghost'")),
            "repeated element": (MAP.replace('elements = ["guide"]', 'elements = ["guide", "guide"]'), ("stage 'middle'", "more than once")),
            "empty elements": (MAP.replace('elements = ["guide"]', "elements = []"), ("stage 'middle'", "'elements' must not be empty")),
            "empty sources": (MAP.replace('title = "Finish"\norder = 3\nelements = ["other", "specs.alpha"]\nsources = ["README.md#Other"]', 'title = "Finish"\norder = 3\nelements = ["other", "specs.alpha"]\nsources = []'), ("stage 'finish'", "'sources' must not be empty")),
            "missing sources key": (MAP.replace('elements = ["guide"]\nsources = ["docs/guide.md#Part", "docs/notes.md"]', 'elements = ["guide"]'), ("stage 'middle'", "missing required key(s): sources")),
            "unknown key": (MAP.replace('title = "Finish"', 'title = "Finish"\nprose = "Stage text lives in sources"'), ("stage 'finish'", "unknown key(s): prose")),
            "duplicate source": (MAP.replace('"docs/guide.md#Part", "docs/notes.md"', '"docs/notes.md", "docs/notes.md"'), ("stage 'middle'", "duplicate source")),
            "absolute source": (MAP.replace('"docs/notes.md"]', '"/docs/notes.md"]'), ("stage 'middle'", "normalized repository-relative")),
            "no stages": (ELEMENT_MAP, ("at least one [[stage]]",)),
        }
        for name, (text, needles) in cases.items():
            with self.subTest(case=name):
                self.assert_build_fails(self.make_repo({"explorer/map.toml": text}), *needles)

    def test_unresolved_stage_sources_fail_naming_stage_and_source(self) -> None:
        cases = {
            "missing file": ("docs/notes.md", "docs/absent.md", "not a git-tracked file"),
            "missing heading": ("docs/guide.md#Part", "docs/guide.md#Renamed", "heading 'Renamed' not found"),
        }
        for name, (old, new, reason) in cases.items():
            with self.subTest(case=name):
                root = self.make_repo({"explorer/map.toml": MAP.replace(f'"{old}"', f'"{new}"')})
                self.assert_build_fails(root, "stage 'middle'", new, reason)

    def test_renaming_a_heading_used_only_by_a_stage_fails_the_build(self) -> None:
        text = ELEMENT_MAP + STAGES.replace('sources = ["README.md#Other"]', 'sources = ["docs/notes.md#Details"]')
        root = self.make_repo({"explorer/map.toml": text, "docs/notes.md": NOTES + "\n## Details\n\nDetail text.\n"})
        self.build(root)
        self.write(root, "docs/notes.md", NOTES + "\n## Specifics\n\nDetail text.\n")
        self.commit(root)
        self.assert_build_fails(root, "stage 'finish'", "docs/notes.md#Details")

    def test_untracked_and_policy_excluded_stage_sources_fail(self) -> None:
        root = self.make_repo({".claude/notes.md": "# Notes\n\nlocal agent state\n"})
        self.write(root, "explorer/map.toml", MAP.replace('"docs/notes.md"', '".claude/notes.md"'))
        self.commit(root)
        self.assert_build_fails(root, "stage 'middle'", ".claude/notes.md", "excluded by the public-distribution policy")

    def test_unsupported_construct_in_a_stage_excerpt_names_stage_file_and_line(self) -> None:
        root = self.make_repo({"docs/bad.md": "# Bad\n\nok\n\n<div>\nx\n</div>\n"})
        self.write(root, "explorer/map.toml", MAP.replace('"docs/notes.md"', '"docs/bad.md"'))
        self.commit(root)
        self.assert_build_fails(root, "docs/bad.md:5:", "raw HTML block", "stage 'middle'")

    def test_dangling_link_in_a_stage_excerpt_names_stage(self) -> None:
        root = self.make_repo({"README.md": README.replace("Read the [guide](docs/guide.md)", "Read the [x](docs/nowhere.md)")})
        self.write(root, "explorer/map.toml", ELEMENT_MAP + STAGES.replace('sources = ["README.md#Intro"]', 'sources = ["README.md#Other"]'))
        self.commit(root)
        self.assert_build_fails(root, "README.md:", "not a tracked")

    def test_invalid_stage_writes_no_output_and_exits_non_zero(self) -> None:
        root = self.make_repo({"explorer/map.toml": MAP.replace('elements = ["guide"]', 'elements = ["ghost"]')})
        for command in ("build", "check"):
            with self.subTest(command=command):
                out = root.parent / f"site-{command}"
                argv = ["--root", str(root), command] + (["--out", str(out)] if command == "build" else [])
                code, stderr = self.run_main(*argv)
                self.assertEqual(code, 2)
                self.assertIn("stage 'middle'", stderr)
                self.assertFalse(out.exists())

    # -- no JavaScript, subpath, determinism ----------------------------------------

    def test_lifecycle_pages_need_no_javascript(self) -> None:
        outputs = self.build(self.make_repo())
        for path in ("lifecycle/index.html", "lifecycle/start/index.html", "lifecycle/finish/index.html"):
            with self.subTest(page=path):
                page = outputs[path].decode("utf-8")
                self.assertEqual(page.count("<script"), 1)
                self.assertRegex(page, r'<script defer src="(?:\.\./)+assets/explorer\.js"></script>')
                self.assertNotRegex(page, r"\son[a-z]+=")
                # Flow, stage navigation and the tree are plain anchors and lists.
                self.assertIn('<nav class="tree"', page)
                self.assertIn("<li><a ", page)

    def test_lifecycle_links_are_relative_and_resolve_under_a_subpath(self) -> None:
        outputs = self.build(self.make_repo())
        LinkTests("assert_links_resolve").assert_links_resolve(outputs)
        for path in ("lifecycle/index.html", "lifecycle/start/index.html"):
            with self.subTest(page=path):
                hrefs = self.hrefs(outputs[path].decode("utf-8"))
                self.assertTrue(hrefs)
                self.assertFalse([href for href in hrefs if href.startswith("/")])
        self.assertIn("../assets/explorer.css", self.hrefs(self.lifecycle(outputs)))
        self.assertIn("../../assets/explorer.css", self.hrefs(self.stage_page(outputs, "start")))

    def test_lifecycle_output_is_deterministic_and_location_independent(self) -> None:
        root = self.make_repo()
        copy = root.parent / "elsewhere" / "clone"
        shutil.copytree(root, copy)
        first, second = self.build(root), self.build(copy)
        self.assertEqual(first, second)
        self.assertEqual(first, self.build(root))
        for path, content in first.items():
            if path.startswith("lifecycle/"):
                self.assertNotIn(str(root.parent).encode(), content, path)

    def test_stylesheet_stacks_the_flow_vertically_on_narrow_screens(self) -> None:
        css = (ROOT / "explorer" / "assets" / "explorer.css").read_text(encoding="utf-8")
        narrow = css.split("@media (max-width: 52rem) {")[1]
        self.assertIn(".flow { display: block; }", narrow)
        self.assertIn(".stage-pager ul { flex-direction: column; }", narrow)


class DeterminismTests(FixtureTestCase):
    def test_identical_inputs_produce_byte_identical_output(self) -> None:
        root = self.make_repo()
        self.assertEqual(self.build(root), self.build(root))

    def test_output_does_not_depend_on_checkout_location(self) -> None:
        root = self.make_repo()
        copy = root.parent / "elsewhere" / "clone"
        shutil.copytree(root, copy)
        first, second = self.build(root), self.build(copy)
        self.assertEqual(first, second)
        for path, content in first.items():
            self.assertNotIn(str(root.parent).encode(), content, path)

    def test_output_has_no_timestamp_markers(self) -> None:
        text = b"".join(self.build(self.make_repo()).values()).decode("utf-8")
        self.assertNotRegex(text, r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d")

    def test_commit_change_changes_only_the_stamp(self) -> None:
        root = self.make_repo()
        before = self.build(root)
        git(root, "commit", "-q", "--allow-empty", "-m", "again")
        after = self.build(root)
        self.assertNotEqual(before["e/guide/index.html"], after["e/guide/index.html"])
        self.assertEqual(before["assets/explorer.css"], after["assets/explorer.css"])


class UnsupportedConstructTests(FixtureTestCase):
    CASES = {
        "raw html block": ("# Bad\n\nok\n\n<div>\nx\n</div>\n", 5, "raw HTML block"),
        "inline raw html": ("# Bad\n\nok\n\ntext <span>x</span> more\n", 5, "inline raw HTML"),
        "image": ("# Bad\n\nok\n\n![alt](x.png)\n", 5, "image"),
        "setext heading": ("# Bad\n\nok\n\nTitle\n=====\n", 5, "setext heading"),
        "indented code": ("# Bad\n\nok\n\n    code\n", 5, "indented code block"),
        "reference link": ("# Bad\n\nok\n\nsee [a][b]\n", 5, "reference-style link"),
        "link definition": ("# Bad\n\nok\n\n[b]: https://example.test\n", 5, "link reference definition"),
        "strikethrough": ("# Bad\n\nok\n\n~~gone~~\n", 5, "strikethrough"),
        "link title": ('# Bad\n\nok\n\nsee [a](b.md "Title")\n', 5, "unsupported link destination"),
        "character reference": ("# Bad\n\nok\n\nfish &amp; chips\n", 5, "character reference"),
        "lazy blockquote": ("# Bad\n\nok\n\n> quote\nlazy\n", 6, "lazy blockquote"),
        "unterminated fence": ("# Bad\n\nok\n\n```\ncode\n", 5, "unterminated fenced code block"),
        "ragged table": ("# Bad\n\nok\n\n| a | b |\n|---|---|\n| 1 |\n", 7, "cell count"),
        "unknown alert": ("# Bad\n\nok\n\n> [!FOO]\n> x\n", 5, "unknown alert marker"),
        "unsupported scheme": ("# Bad\n\nok\n\n[x](javascript:alert)\n", 5, "unsupported scheme"),
        "multi-line inline": ("# Bad\n\nline one\nline two ![img](x.png)\n", 4, "image"),
    }

    def element_map(self, source: str) -> str:
        return MAP.replace('"docs/guide.md"', f'"{source}"')

    def test_unsupported_constructs_fail_naming_file_and_line(self) -> None:
        for name, (text, line, reason) in self.CASES.items():
            with self.subTest(construct=name):
                root = self.make_repo({"docs/bad.md": text, "explorer/map.toml": self.element_map("docs/bad.md")})
                self.assert_build_fails(root, f"docs/bad.md:{line}:", reason, "element 'guide'")

    def test_unsupported_construct_outside_the_included_excerpt_is_not_an_error(self) -> None:
        text = "# T\n\n## Good\n\nfine text\n\n## Bad\n\n<div>x</div>\n"
        root = self.make_repo({"docs/x.md": text, "explorer/map.toml": self.element_map("docs/x.md#Good")})
        self.assertIn("fine text", self.page(self.build(root), "guide"))

    def test_included_excerpt_with_unsupported_construct_fails_for_whole_file_reference(self) -> None:
        text = "# T\n\n## Good\n\nfine text\n\n## Bad\n\n<div>x</div>\n"
        root = self.make_repo({"docs/x.md": text, "explorer/map.toml": self.element_map("docs/x.md")})
        self.assert_build_fails(root, "docs/x.md:9:", "raw HTML block")

    def test_supported_constructs_render(self) -> None:
        text = textwrap.dedent(
            """\
            # Rich

            Intro with `a_b_c` words, snake_case_name, **strong**, *em*, and [ext](https://example.test/a_b).

            > [!NOTE]
            > Alert body.

            > Plain quote.

            1. one
            2. two
               - nested **item**
            - [x] done
            - [ ] todo

            | Name | Value |
            | :--- | ---: |
            | a \\| b | `c` |

            ```bash
            echo "<tag>" && ls
            ```

            ## Second

            Visit https://example.test/path. Trailing.\\
            Hard break above.
            """
        )
        root = self.make_repo({"docs/rich.md": text, "explorer/map.toml": self.element_map("docs/rich.md")})
        page = self.page(self.build(root), "guide")
        for fragment in (
            "<code>a_b_c</code>", "snake_case_name", "<strong>strong</strong>", "<em>em</em>",
            '<a href="https://example.test/a_b" rel="noopener noreferrer">ext</a>',
            'class="alert alert-note"', "<blockquote>", '<ol>', "<strong>item</strong>",
            '<input type="checkbox" disabled checked>', '<input type="checkbox" disabled>',
            '<th style="text-align:left">Name</th>', '<td style="text-align:right"><code>c</code></td>', "a | b",
            '<code class="language-bash">echo &quot;&lt;tag&gt;&quot; &amp;&amp; ls</code>',
            '<h2 id="s-second">Second</h2>',
            '<a href="https://example.test/path" rel="noopener noreferrer">https://example.test/path</a>.', "<br>",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, page)

    def test_inline_parser_keeps_unmatched_delimiters_literal(self) -> None:
        nodes = explorer.parse_inline("2 * 3 and a_b and `unclosed")
        self.assertEqual(explorer.plain_text(nodes), "2 * 3 and a_b and `unclosed")


class LinkTests(FixtureTestCase):
    def test_links_to_mapped_files_become_relative_element_links(self) -> None:
        other = self.page(self.build(self.make_repo()), "other")
        self.assertIn('<a href="../guide/index.html">guide</a>', other)
        self.assertIn('<a href="../guide/index.html#s-part">part</a>', other)

    def test_links_to_unmapped_files_and_directories_point_at_the_built_commit(self) -> None:
        root = self.make_repo()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        other = self.page(self.build(root), "other")
        base = "https://github.com/lehard/dev-platform"
        self.assertIn(f'href="{base}/blob/{commit}/docs/notes.md"', other)
        self.assertIn(f'href="{base}/tree/{commit}/tests"', other)

    def test_dangling_links_fail_naming_the_source_line(self) -> None:
        cases = {
            "missing file": ("[x](docs/nowhere.md)", "not a tracked"),
            "missing anchor": ("[x](docs/guide.md#nope)", "heading anchor that does not exist"),
            "escapes repo": ("[x](../../outside.md)", "escapes the repository"),
            "absolute": ("[x](/docs/guide.md)", "absolute"),
            "query": ("[x](docs/guide.md?x=1)", "query string"),
        }
        for name, (link, needle) in cases.items():
            with self.subTest(case=name):
                root = self.make_repo({"README.md": README.replace("Read the [guide](docs/guide.md)", f"Read the {link}")})
                self.assert_build_fails(root, "README.md:", needle, "element 'other'")

    def test_link_to_policy_excluded_file_fails(self) -> None:
        root = self.make_repo({".claude/notes.md": "# n\n", "README.md": README.replace("docs/notes.md", ".claude/notes.md")})
        self.assert_build_fails(root, "excluded by the public-distribution policy")

    def test_generated_links_are_relative_and_resolve_under_a_subpath(self) -> None:
        outputs = self.build(self.make_repo())
        self.assert_links_resolve(outputs)

    def assert_links_resolve(self, outputs: dict[str, bytes]) -> int:
        prefix = "/projects/explorer/"
        ids: dict[str, set[str]] = {}
        links: dict[str, list[str]] = {}
        for path, content in outputs.items():
            if not path.endswith(".html"):
                continue
            collector = LinkCollector()
            collector.feed(content.decode("utf-8"))
            ids[path] = collector.ids
            links[path] = collector.links
        checked = 0
        for page, hrefs in links.items():
            for href in hrefs:
                if href.startswith(("https://", "mailto:")):
                    continue
                self.assertFalse(href.startswith("/"), f"{page}: absolute internal link {href}")
                self.assertNotIn("://", href, f"{page}: {href}")
                resolved = urllib.parse.urlsplit(urllib.parse.urljoin(f"https://host{prefix}{page}", href))
                self.assertTrue(resolved.path.startswith(prefix), f"{page}: {href} leaves the subpath")
                target = resolved.path[len(prefix):]
                self.assertIn(target, outputs, f"{page}: {href} does not resolve")
                if resolved.fragment:
                    self.assertIn(resolved.fragment, ids.get(target, set()), f"{page}: {href} anchor missing")
                checked += 1
        self.assertGreater(checked, 0)
        return checked


class LinkCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)
            if name in ("href", "src") and value:
                self.links.append(value)


class PublicSafetyTests(FixtureTestCase):
    OPERATOR_REFERENCE = "lehard" + "/" + "operator-backlog"
    TOKEN = "ghp_" + "a" * 36

    def poisoned(self, text: str) -> Path:
        return self.make_repo({"docs/guide.md": GUIDE + f"\n{text}\n"})

    def test_non_canonical_owner_reference_in_an_included_source_aborts_without_output(self) -> None:
        root = self.poisoned(f"See {self.OPERATOR_REFERENCE} for details.")
        out = root.parent / "site"
        code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("e/guide/index.html: non-canonical owner/project reference", stderr)
        self.assertNotIn(self.OPERATOR_REFERENCE, stderr)
        self.assertFalse(out.exists())

    def test_secret_pattern_in_an_included_source_aborts_without_output_or_echo(self) -> None:
        root = self.poisoned(f"token {self.TOKEN}")
        out = root.parent / "site"
        code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("possible github_pat credential", stderr)
        self.assertNotIn(self.TOKEN, stderr)
        self.assertFalse(out.exists())

    def test_check_applies_the_same_scan(self) -> None:
        code, stderr = self.run_main("--root", str(self.poisoned(f"x {self.OPERATOR_REFERENCE}")), "check")
        self.assertEqual(code, 2)
        self.assertIn("nothing was written", stderr)

    def test_canonical_product_repository_reference_is_allowed(self) -> None:
        root = self.poisoned("Canonical lehard/dev-platform is public.")
        self.assertIn("lehard/dev-platform", self.page(self.build(root), "guide"))

    def test_scan_reuses_the_public_distribution_rules(self) -> None:
        self.assertEqual(Path(explorer.public_distribution.__file__).resolve(), ROOT / "scripts" / "public_distribution.py")
        with self.assertRaises(ExplorerError):
            explorer.scan_outputs({"x.html": f"<p>{self.OPERATOR_REFERENCE}</p>".encode()})
        explorer.scan_outputs({"x.html": b"<p>lehard/dev-platform and lehard/dev-platform.git</p>"})


def explorer_artifacts(root: Path) -> list[str]:
    """Return repository-relative paths that are Explorer artifacts under ``root``."""
    found = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if any(part == "explorer" or part == "build_explorer.py" or part.startswith("explorer.") for part in relative.parts):
            found.append(relative.as_posix())
    return found


class DownstreamBoundaryTests(unittest.TestCase):
    def test_artifact_detector_flags_an_explorer_file_moved_under_the_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "template" / "explorer").mkdir(parents=True)
            (root / "template" / "explorer" / "map.toml").write_text("x\n", encoding="utf-8")
            (root / "template" / "scripts").mkdir()
            (root / "template" / "scripts" / "build_explorer.py").write_text("x\n", encoding="utf-8")
            self.assertEqual(
                explorer_artifacts(root),
                ["template/explorer", "template/explorer/map.toml", "template/scripts/build_explorer.py"],
            )

    def test_template_subdirectory_contains_no_explorer_artifact(self) -> None:
        self.assertEqual(explorer_artifacts(ROOT / "template"), [])

    def test_explorer_sources_are_platform_only_and_outside_the_template(self) -> None:
        self.assertTrue((ROOT / "scripts" / "build_explorer.py").is_file())
        self.assertTrue((ROOT / "explorer" / "map.toml").is_file())
        self.assertFalse((ROOT / "template" / "scripts" / "build_explorer.py").exists())
        self.assertFalse((ROOT / "template" / "explorer").exists())

    def test_build_output_is_ignored_by_git(self) -> None:
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/build/", patterns)

    def test_rendered_new_project_contains_no_explorer_artifact(self) -> None:
        self.assertIsNotNone(shutil.which("copier"), "copier is required to prove the downstream boundary")
        with tempfile.TemporaryDirectory() as shared:
            # Render from a VCS-free copy so the working tree (not HEAD) is covered.
            source = Path(shared) / "template-source"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", ".venv", "node_modules"))
            self.assertTrue((source / "explorer" / "map.toml").is_file(), "fixture copy must contain the Explorer sources")
            target = Path(shared) / "project"
            subprocess.run(
                [
                    "copier", "copy", "--trust", "--defaults", "--skip-tasks",
                    "--data", "project_name=Explorer Boundary",
                    "--data", "project_slug=explorer-boundary",
                    "--data", "project_description=Explorer boundary render",
                    "--data", "workflow_profile=standard",
                    "--data", "publish_mode=pr",
                    str(source), str(target),
                ],
                check=True, capture_output=True, text=True,
            )
            self.assertTrue((target / "AGENTS.md").is_file(), "render must have produced the project")
            self.assertEqual(explorer_artifacts(target), [])


class RealRepositoryTests(unittest.TestCase):
    """The committed map must describe the committed sources."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.site, cls.outputs = explorer.build_site(ROOT)

    def test_every_node_has_a_page(self) -> None:
        for identifier in self.site.nodes:
            with self.subTest(identifier=identifier):
                self.assertIn(f"e/{identifier}/index.html", self.outputs)

    def test_collections_enumerate_every_matching_source(self) -> None:
        specs = sorted(path.parent.name for path in (ROOT / "openspec" / "specs").glob("*/spec.md"))
        capabilities = sorted(path.stem for path in (ROOT / "dev-platform" / "capabilities").glob("*.toml"))
        decisions = sorted(path.stem for path in (ROOT / "docs" / "decisions").glob("????-*.md"))
        for prefix, expected in (("specs", specs), ("capabilities", capabilities), ("decisions", decisions)):
            with self.subTest(collection=prefix):
                actual = sorted(identifier.split(".", 1)[1] for identifier in self.site.nodes if identifier.startswith(f"{prefix}."))
                self.assertEqual(actual, expected)

    def test_map_carries_structure_only(self) -> None:
        text = (ROOT / "explorer" / "map.toml").read_text(encoding="utf-8")
        for key in ("description", "summary", "body", "text", "content", "prose"):
            self.assertNotRegex(text, rf"(?m)^{key}\s*=", f"map must not carry a '{key}' prose field")

    def test_generated_site_has_only_relative_internal_links(self) -> None:
        checker = LinkTests("assert_links_resolve")
        self.assertGreater(checker.assert_links_resolve(self.outputs), 100)

    def test_lifecycle_stages_follow_the_documented_journey_in_order(self) -> None:
        self.assertEqual(
            [stage.id for stage in self.site.stages],
            [
                "requirement-intent", "specification", "routing", "isolated-implementation",
                "verification", "publication-integration", "release-rollout", "feedback-learning",
            ],
        )
        self.assertEqual([stage.order for stage in self.site.stages], list(range(1, len(self.site.stages) + 1)))

    def test_every_real_stage_has_pages_neighbours_components_and_source_prose(self) -> None:
        self.assertIn("lifecycle/index.html", self.outputs)
        overview = self.outputs["lifecycle/index.html"].decode("utf-8")
        count = len(self.site.stages)
        for index, stage in enumerate(self.site.stages):
            with self.subTest(stage=stage.id):
                self.assertIn(f'href="{stage.id}/index.html"', overview)
                page = self.outputs[f"lifecycle/{stage.id}/index.html"].decode("utf-8")
                self.assertEqual('rel="prev"' in page, index > 0)
                self.assertEqual('rel="next"' in page, index < count - 1)
                components = page.split('id="components"')[1].split("</section>")[0]
                self.assertIn('href="../../e/', components)
                self.assertIn('class="excerpt"', page)
                for target in stage.elements:
                    self.assertIn(f'href="../../e/{target}/index.html"', components)

    def test_component_pages_list_every_stage_that_names_them(self) -> None:
        for stage in self.site.stages:
            for target in stage.elements:
                with self.subTest(stage=stage.id, element=target):
                    page = self.outputs[f"e/{target}/index.html"].decode("utf-8")
                    self.assertIn(f'<a href="../../lifecycle/{stage.id}/index.html">Stage {stage.order}: ', page)

    def test_stage_entries_carry_structure_only(self) -> None:
        text = (ROOT / "explorer" / "map.toml").read_text(encoding="utf-8")
        stage_keys = {
            line.split("=", 1)[0].strip()
            for chunk in text.split("[[stage]]")[1:]
            for line in chunk.split("[[", 1)[0].splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
        self.assertEqual(stage_keys, {"id", "title", "order", "elements", "sources"})

    def test_real_build_is_deterministic(self) -> None:
        self.assertEqual(self.outputs, explorer.build_site(ROOT)[1])


if __name__ == "__main__":
    unittest.main()
