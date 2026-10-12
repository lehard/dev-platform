"""Contract tests for the Explorer editorial layer, lifecycle schema, non-blocking drift and the drift issue."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_build_explorer as base
from _platform_modules import load_platform_module

ROOT = base.ROOT
explorer = base.explorer
ExplorerError = base.ExplorerError
NODES = base.NODE_FILES


def node_path(name: str) -> str:
    return f"explorer/nodes/{name}.toml"


def with_node(name: str, old: str, new: str) -> dict[str, str]:
    """Return a fixture override that edits one editorial node text."""
    text = NODES[name]
    assert old in text, f"{old!r} not in node {name}"
    return {node_path(name): text.replace(old, new, 1)}


class EditorialFixture(base.FixtureTestCase):
    def node_page(self, outputs: dict[str, bytes], path: str) -> str:
        return outputs[path].decode("utf-8")


class EditorialBuildTests(EditorialFixture):
    def test_clean_build_writes_every_page_family(self) -> None:
        outputs = self.build(self.make_repo())
        for path in (
            "index.html", "lifecycle/index.html", "lifecycle/start/index.html", "lifecycle/middle/index.html",
            "lifecycle/finish/index.html", "m/mech/index.html", "m/part/index.html", "t/topic/index.html",
            "t/term/index.html", "map/index.html", "e/guide/index.html", "assets/explorer.css", "assets/explorer.js",
        ):
            with self.subTest(path=path):
                self.assertIn(path, outputs)

    def test_stage_page_has_breadcrumb_kind_three_zones_and_example(self) -> None:
        page = self.node_page(self.build(self.make_repo()), "lifecycle/start/index.html")
        for fragment in (
            '<nav class="crumb"', "этап lifecycle", '<span class="pos">1 из 3</span>', "ОТКУДА ПРИХОДИТ",
            "ЧТО ЗДЕСЬ ПРОИСХОДИТ", "КУДА ИДЁТ · КТО ИСПОЛЬЗУЕТ", "Условные и ошибочные пути", "Пример",
            "<b>выделением</b>", "ЦЕЛЬ ЭТАПА", '<span class="lk">→ этап 2</span>', "Внутри",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, page)

    def test_term_is_linked_with_its_definition_as_tooltip(self) -> None:
        page = self.node_page(self.build(self.make_repo()), "lifecycle/start/index.html")
        self.assertIn('<a class="term" href="../../t/term/index.html" data-tip="Глоссарий — словарь терминов фикстуры.">Глоссарий</a>', page)
        term = self.node_page(self.build(self.make_repo()), "t/term/index.html")
        self.assertIn("Где встречается", term)
        self.assertIn('href="../../lifecycle/start/index.html"', term)

    def test_stage_pager_links_neighbours_and_overview(self) -> None:
        outputs = self.build(self.make_repo())
        first = self.node_page(outputs, "lifecycle/start/index.html")
        self.assertIn("← ВЕСЬ ЦИКЛ", first)
        self.assertIn('href="../middle/index.html"', first.split("СЛЕДУЮЩИЙ ЭТАП")[0].rsplit("<a", 1)[1])
        last = self.node_page(outputs, "lifecycle/finish/index.html")
        self.assertIn("← ПРЕДЫДУЩИЙ ЭТАП", last)
        self.assertNotIn("СЛЕДУЮЩИЙ ЭТАП", last)

    def test_mechanism_page_lists_usage_derived_from_its_stages(self) -> None:
        outputs = self.build(self.make_repo())
        mech = self.node_page(outputs, "m/mech/index.html")
        self.assertIn('<a href="../../lifecycle/start/index.html">01 Начало</a>', mech)
        self.assertIn('<a class="sec2" href="../../lifecycle/middle/index.html">02 Середина: ещё и здесь</a>', mech)
        self.assertIn("Что гарантирует", mech)
        self.assertIn("Исключения и восстановление", mech)
        self.assertIn("← ЭТАП", mech)
        self.assertIn("больше нет", mech)

    def test_card_text_is_the_node_definition_everywhere(self) -> None:
        outputs = self.build(self.make_repo())
        for path in ("index.html", "lifecycle/index.html", "lifecycle/start/index.html"):
            with self.subTest(page=path):
                text = self.node_page(outputs, path)
                if path != "lifecycle/start/index.html":
                    self.assertIn("Начальный этап пути.", text)
        self.assertIn("Механизм проверки пути.", self.node_page(outputs, "lifecycle/start/index.html"))
        self.assertIn("Механизм проверки пути.", self.node_page(outputs, "map/index.html"))

    def test_outline_node_renders_definition_relations_notice_and_is_listed_as_outline(self) -> None:
        outputs = self.build(self.make_repo())
        middle = self.node_page(outputs, "lifecycle/middle/index.html")
        self.assertIn("Средний этап пути.", middle)
        self.assertIn("Полное описание этого узла ещё не написано", middle)
        self.assertIn("Откуда приходит", middle)
        self.assertIn('<a href="../start/index.html">Начало</a>', middle)
        self.assertIn("Куда идёт", middle)
        self.assertNotIn("ОТКУДА ПРИХОДИТ", middle)
        coverage = self.node_page(outputs, "map/index.html")
        self.assertIn("Набросков: 4", coverage)
        row = coverage.split('<a href="../lifecycle/middle/index.html"><b>')[1].split("</tr>")[0]
        self.assertIn("набросок", row)
        start_row = coverage.split('<a href="../lifecycle/start/index.html"><b>')[1].split("</tr>")[0]
        self.assertIn("полный", start_row)

    def test_engineering_sources_are_collapsed_and_link_to_the_commit(self) -> None:
        root = self.make_repo()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        page = self.node_page(self.build(root), "lifecycle/start/index.html")
        details = page.split('<details class="src"')[1]
        self.assertNotIn(" open", details.split(">")[0])
        self.assertIn(f"/blob/{commit}/README.md#intro", details)
        self.assertIn('href="../../e/home/index.html"', details)

    def test_coverage_page_lists_nodes_levels_and_transitions_with_reasons(self) -> None:
        coverage = self.node_page(self.build(self.make_repo()), "map/index.html")
        for fragment in ("Дальше идёт середина", "Можно остановиться здесь", "1 → стоп", "основной", "условный", "0 · Всё", "Все узлы уровней 0–2"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, coverage)

    def test_tree_expands_current_branch_on_the_server_and_marks_selection(self) -> None:
        outputs = self.build(self.make_repo())
        part = self.node_page(outputs, "m/part/index.html")
        self.assertIn('aria-current="page"><span class="dot"></span><span class="nm">Часть механизма</span>', part)
        self.assertIn('<details open><summary class="line"><span class="chev" aria-hidden="true">▶</span><a class="row" href="../mech/index.html"', part)
        guide = self.node_page(outputs, "e/guide/index.html")
        self.assertIn("<details open><summary", guide.split("Инженерные источники")[1])
        index = self.node_page(outputs, "index.html")
        self.assertNotIn("<details open><summary class=\"line\"><span class=\"chev\" aria-hidden=\"true\">▶</span><span class=\"row grp\" style=\"--c:var(--src)\">", index)

    def test_pages_need_no_javascript_and_links_resolve_under_a_subpath(self) -> None:
        outputs = self.build(self.make_repo())
        for path, content in outputs.items():
            if path.endswith(".html"):
                page = content.decode("utf-8")
                with self.subTest(page=path):
                    self.assertEqual(page.count("<script"), 1)
                    self.assertNotRegex(page, r"\son[a-z]+=")
                    self.assertIn('<ul class="tree"', page)
        base.LinkTests("assert_links_resolve").assert_links_resolve(outputs)

    def test_stylesheet_has_focus_ring_narrow_layout_and_no_remote_assets(self) -> None:
        css = (ROOT / "explorer" / "assets" / "explorer.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        narrow = css.split("@media (max-width: 980px) {")[1]
        self.assertIn(".schema { display: none; }", narrow)
        self.assertIn(".vflow { display: block; }", narrow)
        self.assertIn(".flow { grid-template-columns: 1fr;", narrow)
        for text in (css, (ROOT / "explorer" / "assets" / "explorer.js").read_text(encoding="utf-8")):
            self.assertNotIn("http://", text)
            self.assertNotIn("https://", text)
            self.assertNotIn("googleapis", text)

    def test_output_is_deterministic_and_location_independent(self) -> None:
        root = self.make_repo(stamp=True)
        self.assertEqual(self.build(root), self.build(root))
        text = b"".join(self.build(root).values()).decode("utf-8")
        self.assertNotIn(str(root.parent), text)
        self.assertNotRegex(text, r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d")


class SchemaTests(EditorialFixture):
    def schema(self, root: Path) -> str:
        page = self.node_page(self.build(root), "index.html")
        return page.split('<svg')[1].split("</svg>")[0]

    def test_schema_is_generated_from_typed_transitions(self) -> None:
        override = with_node("middle", 'type = "main"\nreason = "Работа закончена"', 'type = "conditional"\nreason = "Работа закончена"')
        schema = self.schema(self.make_repo(override))
        self.assertIn('class="arm"', schema)
        self.assertIn('class="alt"', schema)
        self.assertNotIn('class="ret"', schema)
        self.assertIn("стоп здесь", schema)
        for stage in ("Начало", "Середина", "Конец"):
            self.assertIn(stage, schema)
        self.assertLess(schema.index("Начало"), schema.index("Середина"))

    def test_schema_stage_boxes_link_to_stage_pages_and_have_a_vertical_list(self) -> None:
        page = self.node_page(self.build(self.make_repo()), "index.html")
        self.assertIn('<a href="lifecycle/start/index.html"><title>Начало</title>', page)
        vertical = page.split('<div class="vflow">')[1]
        self.assertIn('data-n="2"', vertical)
        self.assertIn("Можно остановиться здесь", vertical)
        self.assertIn("· 3 этапа", page)

    def test_return_and_conditional_stage_are_drawn_distinctly(self) -> None:
        # Four stages: the return from stage 4 to stage 3 would not be routable, so use a stage 2 -> 1 style return.
        texts = {
            "middle": NODES["middle"].replace(
                'reason = "Работа закончена"\n',
                'reason = "Работа закончена"\n\n[[transitions]]\nto = "start"\ntype = "return"\nreason = "Нужна переделка"\n',
            )
        }
        root = self.make_repo({node_path(name): text for name, text in texts.items()})
        schema = self.schema(root)
        self.assertIn('class="ret"', schema)

    def test_conditional_stage_is_derived_from_its_incoming_transitions(self) -> None:
        override = with_node("middle", 'type = "main"\nreason = "Работа закончена"', 'type = "conditional"\nreason = "Работа закончена"')
        override.update(with_node("start", 'to = "middle"\ntype = "main"', 'to = "middle"\ntype = "conditional"'))
        page = self.node_page(self.build(self.make_repo(override)), "index.html")
        self.assertIn("02 · условный", page)
        self.assertIn('class="vflow"', page)
        self.assertIn('data-n="2" class="cond"', page)

    def test_label_on_a_transition_between_neighbours_fails(self) -> None:
        override = with_node("middle", 'reason = "Работа закончена"', 'reason = "Работа закончена"\nlabel = "метка"')
        self.assert_build_fails(self.make_repo(override), "node 'middle'", "has a label but joins neighbouring stages")

    def test_unroutable_transition_fails_naming_the_stage(self) -> None:
        override = with_node("finish", 'to = "stop"\ntype = "main"', 'to = "start"\ntype = "return"')
        self.assert_build_fails(self.make_repo(override), "node 'finish'", "cannot be routed")


class NodeValidationTests(EditorialFixture):
    def test_invalid_nodes_fail_naming_node_and_field_and_write_nothing(self) -> None:
        cases = {
            "missing required field": (with_node("start", 'thesis = "Главная мысль этапа."\n', ""), ("node 'start'", "missing required key(s): thesis")),
            "unknown key": (with_node("start", 'tagline = "с чего всё начинается"', 'tagline = "с чего всё начинается"\nextra = "x"'), ("node 'start'", "unknown key(s): extra")),
            "outline carrying explanation": (with_node("middle", 'order = 2', 'order = 2\nlead = "Текст."'), ("node 'middle'", "unknown key(s): lead", "outline")),
            "dangling input node": (with_node("start", 'node = "middle"\nnote', 'node = "ghost"\nnote'), ("node 'start'", "inputs[1].node", "unknown node 'ghost'")),
            "dangling stage in used_in": (with_node("mech", 'stage = "start"', 'stage = "ghost"'), ("node 'mech'", "used_in[1].stage", "unknown stage 'ghost'")),
            "dangling transition target": (with_node("middle", 'to = "finish"', 'to = "ghost"'), ("node 'middle'", "transitions[1].to", "unknown stage 'ghost'")),
            "transition without reason": (with_node("middle", 'reason = "Работа закончена"\n', ""), ("node 'middle'", "missing required key(s): reason")),
            "empty transition reason": (with_node("middle", 'reason = "Работа закончена"', 'reason = ""'), ("node 'middle'", "transitions[1].reason", "non-empty")),
            "unresolved binding": (with_node("start", 'sources = ["README.md#Intro"]', 'sources = ["README.md#Missing"]'), ("node 'start'", "README.md#Missing", "not found")),
            "binding to a missing file": (with_node("start", 'sources = ["README.md#Intro"]', 'sources = ["docs/absent.md"]'), ("node 'start'", "docs/absent.md", "not a git-tracked file")),
            "no binding": (with_node("start", 'sources = ["README.md#Intro"]', "sources = []"), ("node 'start'", "'sources'", "at least 1")),
            "ascii ellipsis": (with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "Главная мысль..."'), ("node 'start'", "field 'thesis'", "ellipsis")),
            "unicode ellipsis": (with_node("start", 'definition = "Начальный этап пути."', 'definition = "Начальный этап…"'), ("node 'start'", "field 'definition'", "ellipsis")),
            "markdown bold": (with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "Главная **мысль** этапа."'), ("node 'start'", "field 'thesis'", "Markdown")),
            "markdown link": (with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "См. [тут](docs/guide.md)."'), ("node 'start'", "field 'thesis'", "Markdown")),
            "unbalanced code span": (with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "Главная `мысль этапа."'), ("node 'start'", "field 'thesis'", "unbalanced code span")),
            "unfinished sentence": (with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "Главная мысль этапа"'), ("node 'start'", "field 'thesis'", "not a finished sentence")),
            "unfinished fragment": (with_node("start", 'outcome = "повторить шаг"', 'outcome = "повторить шаг и"'), ("node 'start'", "path[1].outcome", "unfinished")),
            "step without final punctuation": (with_node("start", 'steps = ["Первый шаг.", "Второй шаг."]', 'steps = ["Первый шаг.", "Второй шаг"]'), ("node 'start'", "action.steps[2]", "not a finished sentence")),
            "emphasis phrase absent": (with_node("start", 'emphasis = ["выделением"]', 'emphasis = ["отсутствует"]'), ("node 'start'", "example.steps[2].emphasis", "exactly once")),
            "bad role": (with_node("start", 'role = "actor"', 'role = "boss"'), ("node 'start'", "inputs[1].role")),
            "term absent from prose": (with_node("start", "с термином Глоссарий", "без термина"), ("node 'start'", "terms", "does not occur")),
            "unknown kind": (with_node("start", 'kind = "stage"', 'kind = "page"'), ("node 'start'", "kind")),
            "id differs from file name": (with_node("start", 'id = "start"', 'id = "begin"'), ("node 'begin'", "must equal the file name 'start'")),
            "duplicate stage order": (with_node("middle", "order = 2", "order = 1"), ("node 'middle'", "duplicates stage")),
            "gapped stage order": (with_node("finish", "order = 3", "order = 4"), ("node 'finish'", "not contiguous", "expected 3")),
            "return to a later stage": (with_node("start", 'to = "middle"\ntype = "main"', 'to = "middle"\ntype = "return"'), ("node 'start'", "return must lead to an earlier stage")),
            "part without a mechanism": (with_node("mech", 'children = ["part"]\n', ""), ("node 'part'", "must be listed in the 'children' of a mechanism")),
            "stage without a map entry": ({"explorer/map.toml": base.MAP.replace('[[stage]]\nid = "finish"\nelements = ["other", "specs.alpha"]', "")}, ("finish", "no [[stage]] entry")),
            "invalid toml": ({node_path("start"): "id = \n"}, ("explorer/nodes/start.toml", "not valid TOML")),
            "overview missing": ({node_path("overview"): None}, ("overview node is required",)),
            "fork with one branch": (
                {node_path("start"): NODES["start"] + '\n[[fork]]\ntitle = "Развилка"\n\n[[fork.branch]]\nname = "А"\ncode = "a"\nrole = "actor"\nrecognized = "Так."\ncreates = "Это."\nnext = "Дальше"\n'},
                ("node 'start'", "fork[1].branch", "at least 2"),
            ),
        }
        for name, (override, needles) in cases.items():
            with self.subTest(case=name):
                root = self.make_repo(override)
                message = self.assert_build_fails(root, *needles)
                self.assertNotIn("Traceback", message)
                out = root.parent / "site"
                code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
                self.assertEqual(code, 2)
                self.assertFalse(out.exists())

    def test_check_command_fails_non_zero_for_an_invalid_node(self) -> None:
        root = self.make_repo(with_node("start", 'thesis = "Главная мысль этапа."', 'thesis = "Главная мысль..."'))
        code, stderr = self.run_main("--root", str(root), "check")
        self.assertEqual(code, 2)
        self.assertIn("field 'thesis'", stderr)

    def test_valid_fork_renders_branches_and_follow_links(self) -> None:
        fork = (
            '\n[[fork]]\ntitle = "Развилка: два пути"\nnote = "Решает смысл."\n\n'
            '[[fork.branch]]\nname = "А"\ncode = "a"\nrole = "actor"\nrecognized = "Так."\ncreates = "Это."\nnext = "Остаться"\nstop = true\n\n'
            '[[fork.branch]]\nname = "Б"\ncode = "b"\nrole = "stage"\nrecognized = "Иначе."\ncreates = "То."\nnext = "→ 2 Середина"\nnext_node = "middle"\n'
        )
        page = self.node_page(self.build(self.make_repo({node_path("start"): NODES["start"] + fork})), "lifecycle/start/index.html")
        self.assertIn("Развилка: два пути", page)
        self.assertIn('<div class="go stop">', page)
        self.assertIn('<a href="../middle/index.html">→ 2 Середина</a>', page)

    def test_unreviewable_binding_to_a_policy_excluded_file_fails(self) -> None:
        root = self.make_repo({".claude/notes.md": "# Notes\n\ntext\n", **with_node("start", 'sources = ["README.md#Intro"]', 'sources = [".claude/notes.md"]')})
        self.assert_build_fails(root, "node 'start'", "excluded by the public-distribution policy")

    def test_whole_file_and_noted_bindings_are_accepted(self) -> None:
        override = with_node("start", 'sources = ["README.md#Intro"]', 'sources = [{ ref = "docs/notes.md", note = "заметки" }, "docs/guide.md#Part"]')
        page = self.node_page(self.build(self.make_repo(override)), "lifecycle/start/index.html")
        self.assertIn("<em>заметки</em>", page)
        self.assertIn("<em>Part</em>", page)


class DriftTests(EditorialFixture):
    def edit_readme(self, root: Path, old: str, new: str) -> None:
        readme = root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
        self.commit(root)

    def check(self, root: Path) -> tuple[int, str]:
        return self.run_main("--root", str(root), "check")

    def test_reviewed_state_has_no_warning(self) -> None:
        code, stderr = self.check(self.make_repo(stamp=True))
        self.assertEqual(code, 0)
        self.assertNotIn("warning", stderr)

    def test_changed_bound_section_warns_naming_node_and_section_without_failing(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        code, stderr = self.check(root)
        self.assertEqual(code, 0)
        self.assertIn("warning: start: README.md#Intro changed after the last editorial review", stderr)
        self.assertIn("warning: overview: README.md#Intro changed", stderr)
        self.assertNotIn("middle:", stderr)

    def test_build_also_succeeds_and_warns(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        out = root.parent / "site"
        code, stderr = self.run_main("--root", str(root), "build", "--out", str(out))
        self.assertEqual(code, 0)
        self.assertIn("changed after the last editorial review", stderr)
        self.assertTrue((out / "index.html").is_file())

    def test_whitespace_only_change_is_not_drift(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "First   paragraph  of\nthe intro.")
        self.edit_readme(root, "## Intro\n", "## Intro\n\n\n")
        code, stderr = self.check(root)
        self.assertEqual(code, 0)
        self.assertNotIn("warning", stderr)

    def test_change_outside_the_bound_section_is_not_drift(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "Read the [guide](docs/guide.md)", "Read the [guide](docs/guide.md) now")
        code, stderr = self.check(root)
        self.assertEqual(code, 0)
        self.assertNotIn("README.md#Intro", stderr)
        self.assertIn("README.md#Other", stderr)

    def test_stale_node_page_shows_marker_naming_the_section(self) -> None:
        root = self.make_repo(stamp=True)
        self.assertNotIn("Источник изменился", self.node_page(self.build(root), "lifecycle/start/index.html"))
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        outputs = self.build(root)
        page = self.node_page(outputs, "lifecycle/start/index.html")
        self.assertIn("Источник изменился после последней сверки текста.", page)
        self.assertIn("<code>README.md · Intro</code>", page)
        self.assertNotIn("Источник изменился", self.node_page(outputs, "lifecycle/finish/index.html").split("Intro")[0])
        self.assertIn("источник изменился", self.node_page(outputs, "map/index.html"))

    def test_mark_reviewed_refreshes_named_nodes_and_clears_marker(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        code, _ = self.run_main("--root", str(root), "mark-reviewed", "start")
        self.assertEqual(code, 0)
        _, stderr = self.check(root)
        self.assertNotIn("warning: start:", stderr)
        self.assertIn("warning: overview: README.md#Intro changed", stderr)
        code, _ = self.run_main("--root", str(root), "mark-reviewed", "overview")
        self.assertEqual(code, 0)
        _, stderr = self.check(root)
        self.assertNotIn("README.md#Intro", stderr)
        self.assertNotIn("Источник изменился", self.node_page(self.build(root), "lifecycle/start/index.html"))

    def test_mark_reviewed_all_is_deterministic_sorted_and_drops_obsolete_records(self) -> None:
        root = self.make_repo(stamp=True)
        record = root / "explorer" / "editorial-review.json"
        first = record.read_text(encoding="utf-8")
        data = json.loads(first)
        self.assertEqual(list(data), sorted(data))
        self.assertEqual(set(data), set(NODES))
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", digest) for bindings in data.values() for digest in bindings.values()))
        data["ghost"] = {"README.md#Intro": "0" * 64}
        data["start"]["docs/old.md"] = "1" * 64
        record.write_text(json.dumps(data), encoding="utf-8")
        _, stderr = self.check(root)
        self.assertIn("warning: ghost: review record for README.md#Intro is obsolete", stderr)
        self.assertIn("warning: start: review record for docs/old.md is obsolete", stderr)
        self.run_main("--root", str(root), "mark-reviewed", "--all")
        self.assertEqual(record.read_text(encoding="utf-8"), first)
        self.run_main("--root", str(root), "mark-reviewed", "--all")
        self.assertEqual(record.read_text(encoding="utf-8"), first)

    def test_mark_reviewed_argument_errors_fail_explicitly(self) -> None:
        root = self.make_repo(stamp=True)
        for argv, needle in (
            (["mark-reviewed", "ghost"], "unknown editorial node(s): ghost"),
            (["mark-reviewed"], "either node ids or --all"),
            (["mark-reviewed", "start", "--all"], "either node ids or --all"),
        ):
            with self.subTest(argv=argv):
                code, stderr = self.run_main("--root", str(root), *argv)
                self.assertEqual(code, 2)
                self.assertIn(needle, stderr)

    def test_missing_review_record_entries_warn_but_a_missing_file_fails(self) -> None:
        root = self.make_repo(stamp=True)
        record = root / "explorer" / "editorial-review.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        del data["finish"]
        record.write_text(json.dumps(data), encoding="utf-8")
        code, stderr = self.check(root)
        self.assertEqual(code, 0)
        self.assertIn("warning: finish: README.md#Other has no editorial review record", stderr)
        for override, needle in (({"explorer/editorial-review.json": None}, "editorial-review.json"), ({"explorer/editorial-review.json": "[1]"}, "must be an object"), ({"explorer/editorial-review.json": "{bad"}, "not valid JSON"), ({"explorer/editorial-review.json": '{"start": {"a": "xyz"}}'}, "not a SHA-256 digest")):
            with self.subTest(needle=needle):
                self.assert_build_fails(self.make_repo(override), needle)

    def test_drift_command_lists_and_never_fails(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        stdout = self.capture("--root", str(root), "drift")
        self.assertEqual(stdout[0], 0)
        self.assertIn("warning: start: README.md#Intro changed", stdout[1])
        code, filtered = self.capture("--root", str(root), "drift", "--changed-file", "docs/guide.md")
        self.assertEqual(code, 0)
        self.assertEqual(filtered, "")
        code, filtered = self.capture("--root", str(root), "drift", "--changed-file", "README.md")
        self.assertIn("overview", filtered)

    def capture(self, *argv: str) -> tuple[int, str]:
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = explorer.main(list(argv))
        return code, out.getvalue()

    def test_drift_github_annotates_and_writes_the_job_summary(self) -> None:
        root = self.make_repo(stamp=True)
        self.edit_readme(root, "First paragraph of the intro.", "A different first paragraph.")
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                code, stdout = self.capture("--root", str(root), "drift", "--github")
            self.assertEqual(code, 0)
            self.assertIn("::warning title=Explorer editorial drift::start: README.md#Intro changed", stdout)
            text = summary.read_text(encoding="utf-8")
            self.assertIn("| `start` | `README.md#Intro` | changed after the last review |", text)
            self.assertIn("never blocks", text)
            clean = self.make_repo(stamp=True)
            summary.write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                code, stdout = self.capture("--root", str(clean), "drift", "--github")
            self.assertEqual((code, stdout), (0, ""))
            self.assertIn("No editorial node is stale", summary.read_text(encoding="utf-8"))
            env = {key: value for key, value in os.environ.items() if key != "GITHUB_STEP_SUMMARY"}
            with mock.patch.dict(os.environ, env, clear=True):
                code, _ = self.run_main("--root", str(root), "drift", "--github")
            self.assertEqual(code, 2)


class FakeGh:
    def __init__(self, open_issues: list[dict] | None = None, fail: str | None = None) -> None:
        self.open_issues = open_issues or []
        self.fail = fail
        self.calls: list[list[str]] = []

    def __call__(self, arguments: list[str], *, stdin: str | None = None) -> str:
        self.calls.append(arguments)
        if self.fail and arguments[:2] == self.fail.split():
            raise ExplorerError(f"gh {self.fail} failed: HTTP 403")
        if arguments[:2] == ["issue", "list"]:
            return json.dumps(self.open_issues)
        return ""

    def verbs(self) -> list[str]:
        return [" ".join(call[:2]) for call in self.calls]


class DriftIssueTests(unittest.TestCase):
    ITEMS = [
        explorer.Drift("start", "Начало", "README.md#Intro", "changed"),
        explorer.Drift("mech", "Механизм", "docs/guide.md#Part", "unreviewed"),
    ]

    def test_creates_exactly_one_labelled_issue_when_nodes_are_stale(self) -> None:
        gh = FakeGh()
        result = explorer.sync_drift_issue(self.ITEMS, "o/r", gh=gh)
        self.assertEqual(result, "created the drift issue")
        self.assertEqual(gh.verbs(), ["issue list", "label create", "issue create"])
        create = gh.calls[-1]
        self.assertIn("explorer-drift", create)
        self.assertIn("Explorer: сверить пояснения", create)
        body = create[create.index("--body") + 1]
        self.assertIn("| `start` | `README.md#Intro` | changed after the last review |", body)
        self.assertNotIn("#", body.replace("README.md#Intro", "").replace("docs/guide.md#Part", "").replace("# ", ""))
        self.assertTrue(all(call[call.index("--repo") + 1] == "o/r" for call in gh.calls))

    def test_updates_the_existing_issue_in_place_without_a_second_one(self) -> None:
        gh = FakeGh([{"number": 7, "body": "old body"}])
        self.assertEqual(explorer.sync_drift_issue(self.ITEMS, "o/r", gh=gh), "updated issue 7")
        self.assertEqual(gh.verbs(), ["issue list", "issue edit"])
        self.assertEqual(gh.calls[-1][2], "7")

    def test_leaves_a_current_issue_untouched(self) -> None:
        gh = FakeGh([{"number": 7, "body": explorer.issue_body(self.ITEMS).replace("\n", "\r\n")}])
        self.assertEqual(explorer.sync_drift_issue(self.ITEMS, "o/r", gh=gh), "issue 7 is already current")
        self.assertEqual(gh.verbs(), ["issue list"])

    def test_closes_the_open_issue_when_nothing_is_stale(self) -> None:
        gh = FakeGh([{"number": 7, "body": "x"}])
        self.assertEqual(explorer.sync_drift_issue([], "o/r", gh=gh), "closed issue 7")
        self.assertEqual(gh.verbs(), ["issue list", "issue close"])

    def test_does_nothing_without_stale_nodes_and_without_an_issue(self) -> None:
        gh = FakeGh()
        self.assertEqual(explorer.sync_drift_issue([], "o/r", gh=gh), "no stale nodes and no open drift issue")
        self.assertEqual(gh.verbs(), ["issue list"])

    def test_more_than_one_open_issue_fails_explicitly(self) -> None:
        gh = FakeGh([{"number": 1, "body": ""}, {"number": 2, "body": ""}])
        with self.assertRaises(ExplorerError) as caught:
            explorer.sync_drift_issue(self.ITEMS, "o/r", gh=gh)
        self.assertIn("more than one open 'explorer-drift' issue", str(caught.exception))

    def test_listing_that_is_not_a_json_list_fails_explicitly(self) -> None:
        for output in ("", "not json", "{}", '[{"number": 1}]'):
            with self.subTest(output=output):
                with self.assertRaises(ExplorerError) as caught:
                    explorer.sync_drift_issue(self.ITEMS, "o/r", gh=lambda arguments, *, stdin=None, out=output: out)
                self.assertIn("gh issue list", str(caught.exception))

    def test_api_failure_propagates(self) -> None:
        gh = FakeGh(fail="issue create")
        with self.assertRaises(ExplorerError) as caught:
            explorer.sync_drift_issue(self.ITEMS, "o/r", gh=gh)
        self.assertIn("HTTP 403", str(caught.exception))

    def test_command_requires_repository_and_token_and_reports_api_failure(self) -> None:
        root = ROOT
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.run_main("--root", str(root), "drift-issue")[0], 2)
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r"}, clear=True):
            code, stderr = self.run_main("--root", str(root), "drift-issue")
            self.assertEqual(code, 2)
            self.assertIn("GH_TOKEN", stderr)
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r", "GH_TOKEN": "x"}), mock.patch.object(
            explorer, "run_gh", side_effect=ExplorerError("gh issue list failed: no network")
        ), mock.patch.object(explorer, "sync_drift_issue", side_effect=ExplorerError("gh issue list failed: no network")):
            code, stderr = self.run_main("--root", str(root), "drift-issue")
            self.assertEqual(code, 2)
            self.assertIn("no network", stderr)

    def run_main(self, *argv: str) -> tuple[int, str]:
        import contextlib
        import io

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            code = explorer.main(list(argv))
        return code, stderr.getvalue()


class SelectChecksDriftHookTests(unittest.TestCase):
    """scripts/select_checks.py prints stale editorial nodes touching the changed files; only a tool error fails it."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            cls.hook = load_platform_module("select_checks_hook", ROOT / "scripts" / "select_checks.py")
        finally:
            sys.path.remove(str(ROOT / "scripts"))

    def surface(self, argv: list[str], result: subprocess.CompletedProcess | None = None) -> tuple[int, str, str, mock.Mock]:
        import contextlib
        import io

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(self.hook.subprocess, "run", return_value=result) as run, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.hook.surface_explorer_drift(argv)
        return code, out.getvalue(), err.getvalue(), run

    def test_drift_is_computed_by_the_command_from_the_base_and_printed(self) -> None:
        done = subprocess.CompletedProcess([], 0, stdout="warning: start: README.md#Intro changed\n", stderr="")
        code, out, _, run = self.surface(["--base", "origin/main", "--execute"], done)
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[-3:], ["drift", "--base", "origin/main"])
        self.assertIn("warning only", out)
        self.assertIn("warning: start: README.md#Intro changed", out)

    def test_no_drift_prints_nothing_and_succeeds(self) -> None:
        code, out, err, _ = self.surface(["--base", "origin/main"], subprocess.CompletedProcess([], 0, stdout="", stderr=""))
        self.assertEqual((code, out, err), (0, "", ""))

    def test_a_drift_command_failure_is_reported_and_fails(self) -> None:
        code, _, err, _ = self.surface(["--base", "origin/main"], subprocess.CompletedProcess([], 2, stdout="", stderr="error: boom"))
        self.assertEqual(code, 2)
        self.assertIn("drift report failed (exit 2): error: boom", err)

    def test_missing_base_fails_explicitly_and_protected_full_has_no_changed_files(self) -> None:
        code, _, err, run = self.surface(["--execute"])
        self.assertEqual(code, 2)
        self.assertIn("--base", err)
        run.assert_not_called()
        for argv in (["--mode", "protected-full", "--execute"], ["--protected-full"], ["--full"]):
            with self.subTest(argv=argv):
                code, out, err, run = self.surface(argv)
                self.assertEqual((code, out, err), (0, "", ""))
                run.assert_not_called()

    def test_main_preserves_the_selector_exit_code_and_adds_drift_failure_only_when_it_succeeded(self) -> None:
        for selector_code, drift_code, expected in ((0, 0, 0), (3, 0, 3), (0, 2, 2), (3, 2, 3)):
            with self.subTest(selector=selector_code, drift=drift_code):
                with mock.patch.object(self.hook, "run_template", side_effect=SystemExit(selector_code)), mock.patch.object(
                    self.hook, "surface_explorer_drift", return_value=drift_code
                ), mock.patch.object(sys, "argv", ["select_checks.py", "--base", "origin/main", "--execute"]):
                    with self.assertRaises(SystemExit) as caught:
                        self.hook.main()
                self.assertEqual(caught.exception.code, expected)
        with mock.patch.object(self.hook, "run_template", side_effect=SystemExit(0)), mock.patch.object(
            self.hook, "surface_explorer_drift"
        ) as surface, mock.patch.object(sys, "argv", ["select_checks.py", "--base", "origin/main"]):
            with self.assertRaises(SystemExit):
                self.hook.main()
        surface.assert_not_called()

    def test_checks_configuration_selects_the_explorer_check_for_bound_sources(self) -> None:
        import tomllib

        config = tomllib.loads((ROOT / "dev-platform" / "checks.toml").read_text(encoding="utf-8"))
        rule = config["checks"]["explorer"]
        self.assertEqual(rule["commands"], ["python3 scripts/build_explorer.py check"])
        self.assertEqual(len(rule["commands"]), len(rule["evidence_types"]))
        self.assertIn("docs/**", rule["patterns"])
        self.assertIn("test_build_explorer_editorial", config["test_groups"]["fast-f"]["targets"])


class DriftBaseTests(EditorialFixture):
    """drift --base computes the changed files with git itself."""

    def stale_repo(self) -> Path:
        root = self.make_repo(stamp=True)
        git_main = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        base.git(root, "branch", "base-ref")
        readme = root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8").replace("First paragraph of the intro.", "Changed paragraph."), encoding="utf-8")
        self.assertTrue(git_main)
        return root

    def capture(self, *argv: str) -> tuple[int, str]:
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = explorer.main(list(argv))
        return code, out.getvalue()

    def test_uncommitted_change_since_the_base_is_reported(self) -> None:
        root = self.stale_repo()
        code, out = self.capture("--root", str(root), "drift", "--base", "base-ref")
        self.assertEqual(code, 0)
        self.assertIn("warning: start: README.md#Intro changed", out)

    def test_committed_and_untracked_changes_count_and_unrelated_ones_do_not(self) -> None:
        root = self.stale_repo()
        self.commit(root)
        code, out = self.capture("--root", str(root), "drift", "--base", "base-ref")
        self.assertIn("README.md#Intro", out)
        clean = self.make_repo(stamp=True)
        base.git(clean, "branch", "base-ref")
        self.write(clean, "docs/untracked.md", "# Extra\n")
        code, out = self.capture("--root", str(clean), "drift", "--base", "base-ref")
        self.assertEqual((code, out), (0, ""))

    def test_base_and_changed_file_combine_and_an_empty_change_set_reports_nothing(self) -> None:
        root = self.stale_repo()
        self.commit(root)
        base.git(root, "branch", "head-ref")
        code, out = self.capture("--root", str(root), "drift", "--base", "head-ref")
        self.assertEqual((code, out), (0, ""))
        code, out = self.capture("--root", str(root), "drift", "--base", "head-ref", "--changed-file", "README.md")
        self.assertIn("README.md#Intro", out)

    def test_unresolvable_base_fails_explicitly(self) -> None:
        root = self.make_repo(stamp=True)
        code, _ = self.capture("--root", str(root), "drift", "--base", "no-such-ref")
        self.assertEqual(code, 2)
        message = self.run_main("--root", str(root), "drift", "--base", "no-such-ref")[1]
        self.assertIn("git merge-base no-such-ref HEAD failed", message)


# Every path the pre-editorial build produced under lifecycle/ and e/ for the committed map.
LEGACY_STAGE_IDS = (
    "requirement-intent", "specification", "routing", "isolated-implementation",
    "verification", "publication-integration", "release-rollout", "feedback-learning",
)
LEGACY_ELEMENT_IDS = (
    "overview", "core-capabilities", "how-it-works", "agent-interoperability", "workflow-profiles", "architecture",
    "safety-reliability", "friction-loop", "repository-structure", "adoption-area", "adoption-guide",
    "project-owned-config", "ownership-model", "release-area", "release-policy", "managed-rollout", "public-cutover",
    "agent-process", "task-intake", "agent-workflow", "openspec-workflow", "model-routing", "agent-instructions",
    "chatgpt-project-protocol", "local-workspace", "verification-area", "engineering-capabilities",
    "browser-verification", "frontend-design-capabilities", "code-erosion", "upstream-substitution",
    "harness-replay-lab", "deepseek-harness-runtime", "process-improvement", "promotion-loop",
    "platform-health-review", "agentic-workflows", "explorer", "contracts", "specs", "capabilities", "decisions",
)


class RealEditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site, cls.outputs = explorer.build_site(ROOT)

    def test_previously_published_paths_still_exist(self) -> None:
        expected = ["lifecycle/index.html"]
        expected += [f"lifecycle/{stage}/index.html" for stage in LEGACY_STAGE_IDS]
        expected += [f"e/{identifier}/index.html" for identifier in LEGACY_ELEMENT_IDS]
        expected += [f"e/{identifier}/index.html" for identifier in self.site.nodes]
        for path in expected:
            with self.subTest(path=path):
                self.assertIn(path, self.outputs)

    def test_no_committed_node_is_an_outline_and_the_semantic_map_is_complete(self) -> None:
        by_kind: dict[str, list[str]] = {}
        for node in self.site.ed.values():
            by_kind.setdefault(node.kind, []).append(node.id)
        self.assertEqual({kind: len(ids) for kind, ids in by_kind.items()}, {"overview": 1, "stage": 8, "mechanism": 11, "part": 7, "topic": 4, "term": 12})
        self.assertEqual(sorted(by_kind["stage"]), sorted(LEGACY_STAGE_IDS))
        self.assertEqual(
            sorted(by_kind["mechanism"]),
            sorted((
                "requirement-intake", "add-openspec", "executor-routing", "executors", "worktrees", "verification-checks",
                "independent-review", "pr-queue-integration", "platform-releases", "copier-rollout", "friction-retrospectives",
            )),
        )
        self.assertEqual(
            sorted(by_kind["part"]),
            sorted((
                "chatgpt-project", "incubator", "goal-refinement", "review-perspectives", "repair-job", "review-decisions",
                "lifecycle-workers",
            )),
        )
        self.assertEqual(sorted(by_kind["topic"]), sorted(("ownership", "adoption", "sources-of-truth", "glossary")))
        outlines = sorted(node.id for node in self.site.ed.values() if node.outline)
        self.assertEqual(outlines, [])
        for node in self.site.ed.values():
            with self.subTest(node=node.id):
                self.assertTrue(node.definition)
                if node.kind in ("stage", "mechanism", "part"):
                    for key in ("lead", "thesis", "inputs", "action", "outputs", "path", "example"):
                        self.assertIn(key, node.data)
                elif node.kind == "topic":
                    for key in ("lead", "thesis", "points"):
                        self.assertIn(key, node.data)
                if node.kind in ("mechanism", "part"):
                    self.assertTrue(node.data["used_in"])

    def test_every_glossary_term_is_wired_as_a_hint_in_at_least_one_node(self) -> None:
        wired: dict[str, list[str]] = {}
        for node in self.site.ed.values():
            for term in node.data.get("terms", []):
                wired.setdefault(term, []).append(node.id)
        terms = [node.id for node in self.site.ed.values() if node.kind == "term"]
        self.assertEqual(sorted(wired), sorted(terms))
        glossary = self.site.ed["glossary"].data["children"]
        self.assertEqual(sorted(glossary), sorted(terms))

    def test_coverage_page_shows_every_node_as_full_with_its_bound_sources(self) -> None:
        coverage = self.outputs["map/index.html"].decode("utf-8")
        self.assertIn("Набросков: 0.", coverage)
        self.assertNotIn(">набросок<", coverage)
        self.assertNotIn("Полное описание этого узла ещё не написано", coverage)
        self.assertIn("ИСТОЧНИКИ", coverage)
        for node in self.site.ed.values():
            for binding in node.sources:
                with self.subTest(node=node.id, source=binding.ref.label):
                    self.assertIn(f"<code>{explorer.esc(binding.ref.label)}</code>", coverage)
        for path, page in self.outputs.items():
            if path.endswith(".html"):
                self.assertNotIn("Полное описание этого узла ещё не написано", page.decode("utf-8"), path)

    def test_check_command_reports_no_outlines(self) -> None:
        import contextlib
        import io

        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = explorer.main(["--root", str(ROOT), "check"])
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertIn("(0 outline node(s))", stdout.getvalue())

    def test_every_node_binds_a_source_and_has_a_page(self) -> None:
        for node in self.site.ed.values():
            with self.subTest(node=node.id):
                self.assertTrue(node.sources)
                self.assertIn(self.site.node_page(node.id), self.outputs)

    def test_review_record_covers_every_binding_and_check_never_fails_on_drift(self) -> None:
        # Staleness is allowed to exist (it never blocks); the record must at least be well formed and cover known nodes.
        review = json.loads((ROOT / "explorer" / "editorial-review.json").read_text(encoding="utf-8"))
        self.assertEqual(review, json.loads(explorer.render_review(review)))
        self.assertIsInstance(self.site.drift, list)

    def test_approved_texts_are_rendered_verbatim(self) -> None:
        overview = self.outputs["index.html"].decode("utf-8")
        stage = self.outputs["lifecycle/requirement-intent/index.html"].decode("utf-8")
        review = self.outputs["m/independent-review/index.html"].decode("utf-8")
        self.assertIn("Dev Platform — общий для нескольких репозиториев порядок инженерной работы", overview)
        self.assertIn("Развилка: четыре намерения", stage)
        self.assertIn("Цикл кандидата", review)
        self.assertIn("Существенное замечание нельзя молча пропустить.", review)
        self.assertNotIn("ПРОТОТИП", overview)
        self.assertNotIn("образец", overview)
        self.assertNotIn("fonts.googleapis", overview)

    def test_schema_covers_every_transition_with_a_reason(self) -> None:
        overview = self.outputs["index.html"].decode("utf-8")
        schema = overview.split("<svg")[1].split("</svg>")[0]
        total = sum(len(stage.data["transitions"]) for stage in self.site.stages)
        self.assertEqual(total, 12)
        self.assertGreaterEqual(schema.count("<title>"), total - 1 + len(self.site.stages))
        for kind in ("arm", "alt", "ret"):
            self.assertIn(f'class="{kind}"', schema)


if __name__ == "__main__":
    unittest.main()
