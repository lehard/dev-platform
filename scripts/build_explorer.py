#!/usr/bin/env python3
"""Build the static Dev Platform Explorer from canonical repository sources.

The Explorer has two layers. The *engineering sources* layer is a build-time
view of git-tracked repository files: ``explorer/map.toml`` owns structure only
(ids, titles, hierarchy, order, relations and source references) and every
explanation on those pages is rendered from the referenced source file and
heading. The *editorial* layer is one explanatory Russian description per
semantic node (overview, lifecycle stage, mechanism, mechanism part,
cross-cutting topic, glossary term) in ``explorer/nodes/<id>.toml``. It is
explanatory only: normative rules stay in ``AGENTS.md``, OpenSpec and
``docs/``, and every node binds the canonical source sections it explains.
Contract: docs/engineering/explorer.md.

Failure model: there are no defaults that mask a missing input and no degraded
rendering mode. A missing or untracked source, a missing heading, an
incomplete or unfinished editorial node (missing field, ellipsis, Markdown
fragment, unfinished sentence), a dangling node, stage or source reference, an
unsupported Markdown construct in an included excerpt, prohibited operator
state in the generated output, or running outside a git checkout aborts with a
message naming what failed, and nothing is written.

Editorial drift is the one deliberately non-blocking condition. A committed
review record (``explorer/editorial-review.json``) stores a digest of every
bound source section at its last review. A section that changed since then is
reported as a warning by ``check``, ``build`` and ``drift``, marked on the
published node, and collected into one issue after a merge (``drift-issue``);
``mark-reviewed`` refreshes the record. Drift never fails a command.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import html
import json
import math
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import public_distribution

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = "explorer/map.toml"
ASSETS_DIR = "explorer/assets"
ASSET_SUFFIXES = (".css", ".js")
SUMMARY_LIMIT = 240
REPOSITORY_URL = f"https://github.com/{public_distribution.CANONICAL_PRODUCT_REPOSITORY}"

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
LIFECYCLE_INDEX = "lifecycle/index.html"


class ExplorerError(Exception):
    """The Explorer map, a source, or the generated output is not acceptable."""


# ---------------------------------------------------------------------------
# Repository access (git-tracked, publicly distributable files only)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Repo:
    root: Path
    tracked: frozenset[str]
    allowed: frozenset[str]
    directories: frozenset[str]
    commit: str
    version: str
    dirty: bool


def open_repo(root: Path) -> Repo:
    root = root.resolve()
    try:
        tracked = frozenset(public_distribution.tracked_files(root))
        allowed = frozenset(path.relative_to(root).as_posix() for path in public_distribution.public_files(root))
    except public_distribution.GitSourceError as exc:
        raise ExplorerError(str(exc)) from exc
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ExplorerError(f"git is required to determine the source commit: {exc}") from exc
    commit = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ExplorerError(f"cannot determine the source commit at {root}: {result.stderr.strip() or 'git rev-parse HEAD failed'}")
    try:
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ExplorerError(f"git is required to determine the working tree state: {exc}") from exc
    if status.returncode != 0:
        raise ExplorerError(f"cannot determine the working tree state at {root}: {status.stderr.strip() or 'git status failed'}")
    version_file = root / "VERSION"
    if not version_file.is_file():
        raise ExplorerError(f"VERSION file is missing at {root}")
    version = version_file.read_text(encoding="utf-8").strip()
    if not version:
        raise ExplorerError("VERSION file is empty")
    directories: set[str] = set()
    for path in allowed:
        parent = posixpath.dirname(path)
        while parent:
            directories.add(parent)
            parent = posixpath.dirname(parent)
    return Repo(root, tracked, allowed, frozenset(directories), commit, version, bool(status.stdout.strip()))


def require_source(repo: Repo, path: str, context: str) -> None:
    if path in repo.allowed:
        return
    if path in repo.tracked:
        reason = (
            "excluded by the public-distribution policy"
            if (repo.root / path).is_file()
            else "tracked but missing from the working tree"
        )
    else:
        reason = "not a git-tracked file"
    raise ExplorerError(f"{context}: source '{path}' is {reason}")


def read_text(repo: Repo, path: str, context: str) -> str:
    require_source(repo, path, context)
    try:
        return (repo.root / path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExplorerError(f"{context}: source '{path}' is not valid UTF-8") from exc


# ---------------------------------------------------------------------------
# Markdown model and parser (fail-closed: unsupported constructs are recorded
# as blocks and raise only when they are part of an included excerpt)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Heading:
    line: int
    level: int
    text: str
    slug: str = ""


@dataclasses.dataclass
class Para:
    line: int
    text: str


@dataclasses.dataclass
class Code:
    line: int
    info: str
    text: str


@dataclasses.dataclass
class Quote:
    line: int
    blocks: list
    alert: str | None


@dataclasses.dataclass
class Item:
    blocks: list
    checked: bool | None


@dataclasses.dataclass
class ListBlock:
    line: int
    ordered: bool
    start: int
    items: list[Item]


@dataclasses.dataclass
class Table:
    line: int
    header: list[str]
    align: list[str]
    rows: list[list[str]]
    row_lines: list[int]


@dataclasses.dataclass
class Rule:
    line: int


@dataclasses.dataclass
class Unsupported:
    line: int
    reason: str


Line = tuple[int, str]
FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*([^`]*?)[ \t]*$")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
RULE_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
QUOTE_RE = re.compile(r"^ {0,3}>")
LIST_RE = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])( +|$)(.*)$")
REFERENCE_DEFINITION_RE = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*\S")
HTML_BLOCK_RE = re.compile(r"^ {0,3}<(?:/?[A-Za-z][A-Za-z0-9-]*(?:[ \t/>]|$)|!--|\?|![A-Za-z])")
TABLE_DELIMITER_RE = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
ALERT_RE = re.compile(r"^\[!([A-Za-z]+)\][ \t]*$")
ALERT_KINDS = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def _blank(text: str) -> bool:
    return not text.strip()


def _interrupts_paragraph(text: str) -> bool:
    if FENCE_RE.match(text) or HEADING_RE.match(text) or QUOTE_RE.match(text) or RULE_RE.match(text):
        return True
    match = LIST_RE.match(text)
    return bool(match and match.group(4).strip() and (not match.group(2)[0].isdigit() or match.group(2)[:-1] == "1"))


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(stripped):
        char = stripped[index]
        if char == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _is_table_start(lines: list[Line], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header, delimiter = lines[index][1], lines[index + 1][1]
    if "|" not in header or "|" not in delimiter or not TABLE_DELIMITER_RE.match(delimiter):
        return False
    return len(_split_row(header)) == len(_split_row(delimiter))


def parse_blocks(lines: list[Line]) -> list:
    blocks: list = []
    index = 0
    count = len(lines)
    while index < count:
        number, text = lines[index]
        if _blank(text):
            index += 1
            continue
        if _indent(text) >= 4:
            end = index
            while end < count and (_blank(lines[end][1]) or _indent(lines[end][1]) >= 4):
                end += 1
            blocks.append(Unsupported(number, "indented code block"))
            index = end
            continue
        fence = FENCE_RE.match(text)
        if fence:
            marker, fence_indent = fence.group(2), len(fence.group(1))
            closing = re.compile(rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*$")
            body: list[str] = []
            end = index + 1
            while end < count and not closing.match(lines[end][1]):
                body.append(lines[end][1][min(fence_indent, _indent(lines[end][1])):])
                end += 1
            if end >= count:
                blocks.append(Unsupported(number, "unterminated fenced code block"))
                index = count
                continue
            blocks.append(Code(number, fence.group(3), "\n".join(body)))
            index = end + 1
            continue
        heading = HEADING_RE.match(text)
        if heading:
            blocks.append(Heading(number, len(heading.group(1)), (heading.group(2) or "").strip()))
            index += 1
            continue
        if RULE_RE.match(text):
            blocks.append(Rule(number))
            index += 1
            continue
        if QUOTE_RE.match(text):
            index = _parse_quote(lines, index, blocks)
            continue
        if LIST_RE.match(text):
            index = _parse_list(lines, index, blocks)
            continue
        if REFERENCE_DEFINITION_RE.match(text):
            blocks.append(Unsupported(number, "link reference definition"))
            index += 1
            continue
        if HTML_BLOCK_RE.match(text):
            end = index
            while end < count and not _blank(lines[end][1]):
                end += 1
            blocks.append(Unsupported(number, "raw HTML block"))
            index = end
            continue
        if _is_table_start(lines, index):
            index = _parse_table(lines, index, blocks)
            continue
        paragraph = [text.lstrip()]
        end = index + 1
        unsupported: Unsupported | None = None
        while end < count:
            following = lines[end][1]
            if _blank(following):
                break
            if SETEXT_RE.match(following):
                unsupported = Unsupported(number, "setext heading")
                end += 1
                break
            if _interrupts_paragraph(following):
                break
            paragraph.append(following.lstrip())
            end += 1
        if unsupported is not None:
            blocks.append(unsupported)
        else:
            paragraph[-1] = paragraph[-1].rstrip()
            blocks.append(Para(number, "\n".join(paragraph)))
        index = end
    return blocks


def _parse_quote(lines: list[Line], index: int, blocks: list) -> int:
    number = lines[index][0]
    inner: list[Line] = []
    count = len(lines)
    while index < count and QUOTE_RE.match(lines[index][1]):
        stripped = re.sub(r"^ {0,3}> ?", "", lines[index][1], count=1)
        inner.append((lines[index][0], stripped))
        index += 1
    lazy = False
    if index < count and not _blank(lines[index][1]) and not _interrupts_paragraph(lines[index][1]) and not _blank(inner[-1][1]):
        lazy = True
    parsed = parse_blocks(inner)
    alert = None
    if parsed and isinstance(parsed[0], Para):
        first_line, _, rest = parsed[0].text.partition("\n")
        match = ALERT_RE.match(first_line)
        if match:
            kind = match.group(1).upper()
            if kind not in ALERT_KINDS or match.group(1) != kind:
                parsed[0] = Unsupported(parsed[0].line, f"unknown alert marker [!{match.group(1)}]")
            else:
                alert = kind
                if rest.strip():
                    parsed[0] = Para(parsed[0].line + 1, rest)
                else:
                    parsed.pop(0)
    blocks.append(Quote(number, parsed, alert))
    if lazy:
        blocks.append(Unsupported(lines[index][0], "lazy blockquote continuation line"))
        index += 1
    return index


def _same_list(match: re.Match[str], ordered: bool, kind: str) -> bool:
    marker = match.group(2)
    if marker[0].isdigit() != ordered:
        return False
    return (marker[-1] if ordered else marker) == kind


def _parse_list(lines: list[Line], index: int, blocks: list) -> int:
    count = len(lines)
    first = LIST_RE.match(lines[index][1])
    assert first is not None
    ordered = first.group(2)[0].isdigit()
    kind = first.group(2)[-1] if ordered else first.group(2)
    start = int(first.group(2)[:-1]) if ordered else 1
    number = lines[index][0]
    items: list[Item] = []
    while index < count:
        match = LIST_RE.match(lines[index][1])
        if match is None or RULE_RE.match(lines[index][1]) or not _same_list(match, ordered, kind):
            break
        marker, spaces, rest = match.group(2), match.group(3), match.group(4)
        if not rest.strip():
            content_col = len(match.group(1)) + len(marker) + 1
            first_content = ""
        elif len(spaces) > 4:
            content_col = len(match.group(1)) + len(marker) + 1
            first_content = lines[index][1][content_col:]
        else:
            content_col = len(match.group(1)) + len(marker) + len(spaces)
            first_content = rest
        item_lines: list[Line] = [(lines[index][0], first_content)]
        index += 1
        while index < count:
            text = lines[index][1]
            if _blank(text):
                lookahead = index
                while lookahead < count and _blank(lines[lookahead][1]):
                    lookahead += 1
                if lookahead < count and _indent(lines[lookahead][1]) >= content_col:
                    item_lines.extend((lines[position][0], "") for position in range(index, lookahead))
                    index = lookahead
                    continue
                break
            if _indent(text) >= content_col:
                item_lines.append((lines[index][0], text[content_col:]))
                index += 1
                continue
            previous = item_lines[-1][1]
            if (
                not _blank(previous)
                and not FENCE_RE.match(previous)
                and not LIST_RE.match(text)
                and not _interrupts_paragraph(text)
                and not _is_table_start(lines, index)
            ):
                item_lines.append((lines[index][0], text.lstrip()))
                index += 1
                continue
            break
        item_blocks = parse_blocks(item_lines)
        checked: bool | None = None
        if item_blocks and isinstance(item_blocks[0], Para):
            task = re.match(r"^\[([ xX])\] +", item_blocks[0].text)
            if task:
                checked = task.group(1) != " "
                item_blocks[0] = Para(item_blocks[0].line, item_blocks[0].text[task.end():])
        items.append(Item(item_blocks, checked))
        lookahead = index
        while lookahead < count and _blank(lines[lookahead][1]):
            lookahead += 1
        if lookahead < count:
            following = LIST_RE.match(lines[lookahead][1])
            if following and not RULE_RE.match(lines[lookahead][1]) and _same_list(following, ordered, kind):
                index = lookahead
                continue
        break
    blocks.append(ListBlock(number, ordered, start, items))
    return index


def _parse_table(lines: list[Line], index: int, blocks: list) -> int:
    count = len(lines)
    number = lines[index][0]
    header = _split_row(lines[index][1])
    align: list[str] = []
    for cell in _split_row(lines[index + 1][1]):
        left, right = cell.startswith(":"), cell.endswith(":")
        align.append("center" if left and right else "left" if left else "right" if right else "")
    index += 2
    rows: list[list[str]] = []
    row_lines: list[int] = []
    bad_row: int | None = None
    while index < count and not _blank(lines[index][1]) and "|" in lines[index][1]:
        if (
            FENCE_RE.match(lines[index][1]) or HEADING_RE.match(lines[index][1]) or QUOTE_RE.match(lines[index][1])
        ):
            break
        cells = _split_row(lines[index][1])
        if len(cells) != len(header) and bad_row is None:
            bad_row = lines[index][0]
        rows.append(cells)
        row_lines.append(lines[index][0])
        index += 1
    if bad_row is not None:
        blocks.append(Unsupported(bad_row, "table row whose cell count differs from the header"))
    else:
        blocks.append(Table(number, header, align, rows, row_lines))
    return index


def github_slug(text: str) -> str:
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    plain = plain.replace("`", "").replace("*", "").lower()
    plain = re.sub(r"[^\w\- ]", "", plain)
    return plain.strip().replace(" ", "-")


@dataclasses.dataclass
class MdDoc:
    path: str
    blocks: list
    slugs: frozenset[str]


def parse_markdown(text: str, path: str) -> MdDoc:
    lines: list[Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        lines.append((number, re.sub(r"^\t+", lambda match: "    " * len(match.group()), raw)))
    blocks = parse_blocks(lines)
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    for block in blocks:
        if isinstance(block, Heading):
            base = github_slug(block.text)
            occurrence = seen.get(base, 0)
            seen[base] = occurrence + 1
            block.slug = base if occurrence == 0 else f"{base}-{occurrence}"
            slugs.add(block.slug)
    return MdDoc(path, blocks, frozenset(slugs))


# ---------------------------------------------------------------------------
# Inline parsing and rendering
# ---------------------------------------------------------------------------

AUTOLINK_RE = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*)>")
INLINE_HTML_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|<!--.*?-->|<\?.*?\?>", re.DOTALL)
CHARACTER_REFERENCE_RE = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
BARE_URL_RE = re.compile(r"https?://[^\s<>]+")
LINK_DESTINATION_RE = re.compile(r"""^\s*(<[^<>\s]*>|[^\s<>]*)\s*$""")
ESCAPABLE = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
EXTERNAL_RE = re.compile(r"^(?:https?://|mailto:)", re.IGNORECASE)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class InlineError(Exception):
    def __init__(self, reason: str, offset: int):
        super().__init__(reason)
        self.reason = reason
        self.offset = offset


def _skip_code_span(text: str, index: int) -> int | None:
    """Return the index just past a code span opening at ``index``, or None."""
    run = 0
    while index + run < len(text) and text[index + run] == "`":
        run += 1
    cursor = index + run
    while cursor < len(text):
        if text[cursor] == "`":
            end = cursor
            while end < len(text) and text[end] == "`":
                end += 1
            if end - cursor == run:
                return end
            cursor = end
        else:
            cursor += 1
    return None


def _matching_bracket(text: str, index: int) -> int | None:
    depth = 0
    cursor = index
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "`":
            skipped = _skip_code_span(text, cursor)
            if skipped is not None:
                cursor = skipped
                continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return None


def _matching_paren(text: str, index: int) -> int | None:
    depth = 0
    cursor = index
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return None


def _find_emphasis_closer(text: str, start: int, char: str, run: int) -> int | None:
    cursor = start
    while cursor < len(text):
        current = text[cursor]
        if current == "\\":
            cursor += 2
            continue
        if current == "`":
            skipped = _skip_code_span(text, cursor)
            if skipped is not None:
                cursor = skipped
                continue
        if current == char:
            end = cursor
            while end < len(text) and text[end] == char:
                end += 1
            length = end - cursor
            previous = text[cursor - 1]
            following = text[end] if end < len(text) else ""
            valid = (
                length == run
                and cursor > start
                and not previous.isspace()
                and (char == "*" or not (following.isalnum() or following == "_"))
            )
            if valid:
                return cursor
            cursor = end
            continue
        cursor += 1
    return None


def parse_inline(text: str, offset: int = 0, in_link: bool = False) -> list:
    """Parse inline Markdown into nodes; raise InlineError for unsupported syntax."""
    nodes: list = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            nodes.append(("text", "".join(buffer)))
            buffer.clear()

    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            following = text[index + 1] if index + 1 < len(text) else ""
            if following == "\n":
                flush()
                nodes.append(("br",))
                index += 2
            elif following and following in ESCAPABLE:
                buffer.append(following)
                index += 2
            else:
                buffer.append("\\")
                index += 1
        elif char == "`":
            end = _skip_code_span(text, index)
            if end is None:
                run = 0
                while index + run < len(text) and text[index + run] == "`":
                    run += 1
                buffer.append("`" * run)
                index += run
            else:
                run = 0
                while text[index + run] == "`":
                    run += 1
                content = text[index + run:end - run].replace("\n", " ")
                if len(content) >= 2 and content[0] == " " and content[-1] == " " and content.strip():
                    content = content[1:-1]
                flush()
                nodes.append(("code", content))
                index = end
        elif char == "<":
            autolink = AUTOLINK_RE.match(text, index)
            if autolink:
                flush()
                nodes.append(("link", autolink.group(1), [("text", autolink.group(1))]))
                index = autolink.end()
            elif INLINE_HTML_RE.match(text, index):
                raise InlineError("inline raw HTML", offset + index)
            else:
                buffer.append("<")
                index += 1
        elif char == "!" and text.startswith("![", index):
            raise InlineError("image", offset + index)
        elif char == "[":
            close = _matching_bracket(text, index)
            if close is None:
                buffer.append("[")
                index += 1
                continue
            following = text[close + 1] if close + 1 < len(text) else ""
            if following == "(":
                paren = _matching_paren(text, close + 1)
                if paren is None:
                    raise InlineError("unterminated link destination", offset + index)
                parsed = LINK_DESTINATION_RE.match(text[close + 2:paren])
                if not parsed or not parsed.group(1):
                    raise InlineError("unsupported link destination", offset + index)
                destination = parsed.group(1)
                if destination.startswith("<"):
                    destination = destination[1:-1]
                if in_link:
                    raise InlineError("nested link", offset + index)
                flush()
                children = parse_inline(text[index + 1:close], offset + index + 1, in_link=True)
                nodes.append(("link", destination, children))
                index = paren + 1
            elif following == "[":
                raise InlineError("reference-style link", offset + index)
            else:
                buffer.append("[")
                index += 1
        elif char in "*_":
            run = 0
            while index + run < len(text) and text[index + run] == char:
                run += 1
            following = text[index + run] if index + run < len(text) else ""
            previous = text[index - 1] if index > 0 else ""
            opener = bool(following) and not following.isspace() and (
                char == "*" or not (previous.isalnum() or previous == "_")
            )
            if not opener:
                buffer.append(char * run)
                index += run
                continue
            if run > 3:
                raise InlineError(f"emphasis delimiter run of length {run}", offset + index)
            closer = _find_emphasis_closer(text, index + run, char, run)
            if closer is None:
                buffer.append(char * run)
                index += run
                continue
            flush()
            children = parse_inline(text[index + run:closer], offset + index + run, in_link=in_link)
            node: tuple = ("em", children) if run == 1 else ("strong", children)
            if run == 3:
                node = ("em", [("strong", children)])
            nodes.append(node)
            index = closer + run
        elif char == "~" and text.startswith("~~", index):
            raise InlineError("strikethrough", offset + index)
        elif char == "&":
            reference = CHARACTER_REFERENCE_RE.match(text, index)
            if reference:
                raise InlineError("character reference", offset + index)
            buffer.append("&")
            index += 1
        elif char == "\n":
            joined = "".join(buffer)
            stripped = joined.rstrip(" ")
            hard = len(joined) - len(stripped) >= 2
            buffer.clear()
            if stripped:
                buffer.append(stripped)
            flush()
            nodes.append(("br",) if hard else ("text", "\n"))
            index += 1
        elif not in_link and char == "h" and BARE_URL_RE.match(text, index) and (index == 0 or not text[index - 1].isalnum()):
            trimmed = BARE_URL_RE.match(text, index).group().rstrip(".,;:!?*_\"'")  # type: ignore[union-attr]
            while trimmed.endswith(")") and trimmed.count(")") > trimmed.count("("):
                trimmed = trimmed[:-1].rstrip(".,;:!?*_\"'")
            flush()
            nodes.append(("link", trimmed, [("text", trimmed)]))
            index += len(trimmed)
        else:
            buffer.append(char)
            index += 1
    flush()
    return nodes


def plain_text(nodes: list) -> str:
    parts: list[str] = []
    for node in nodes:
        kind = node[0]
        if kind in ("text", "code"):
            parts.append(node[1])
        elif kind == "br":
            parts.append(" ")
        elif kind == "link":
            parts.append(plain_text(node[2]))
        else:
            parts.append(plain_text(node[1]))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def summarize(text: str) -> str:
    if len(text) <= SUMMARY_LIMIT:
        return text
    cut = text[:SUMMARY_LIMIT].rsplit(" ", 1)[0].rstrip(",;:.-")
    return f"{cut}…"


# ---------------------------------------------------------------------------
# Map model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SourceRef:
    path: str
    heading: str | None

    @property
    def label(self) -> str:
        return self.path if self.heading is None else f"{self.path}#{self.heading}"


@dataclasses.dataclass
class Node:
    id: str
    title: str
    kind: str  # element | collection | item
    parent: str | None
    order: int
    sources: list[SourceRef]
    related: list[str]
    children: list[str] = dataclasses.field(default_factory=list)
    summary: str | None = None
    collection: dict | None = None


@dataclasses.dataclass
class MapStage:
    """Level-3 links of one lifecycle stage; every explanation lives in the stage's editorial node."""

    id: str
    elements: list[str]


@dataclasses.dataclass
class Excerpt:
    ref: SourceRef
    kind: str  # markdown | toml
    blocks: list
    base: int
    code: str
    heading_ids: dict[str, str]


ELEMENT_REQUIRED = {"id", "title", "order"}
ELEMENT_OPTIONAL = {"parent", "sources", "related"}
COLLECTION_REQUIRED = {"id", "title", "order", "glob", "title_from", "summary_from", "slug_from"}
COLLECTION_OPTIONAL = {"parent", "companions"}
STAGE_REQUIRED = {"id", "elements"}
SITE_REQUIRED = {"title"}
TOP_LEVEL = {"site", "element", "collection", "stage"}
TITLE_FROM_RE = re.compile(r"^(?:heading|slug|toml:[A-Za-z0-9_.-]+)$")
SUMMARY_FROM_RE = re.compile(r"^(?:first-paragraph|section:.+|toml:[A-Za-z0-9_.-]+)$")


def _check_keys(table: dict, required: set[str], optional: set[str], context: str) -> None:
    unknown = sorted(set(table) - required - optional)
    if unknown:
        raise ExplorerError(f"{context}: unknown key(s): {', '.join(unknown)}")
    missing = sorted(required - set(table))
    if missing:
        raise ExplorerError(f"{context}: missing required key(s): {', '.join(missing)}")


def _string(table: dict, key: str, context: str) -> str:
    value = table[key]
    if not isinstance(value, str) or not value.strip():
        raise ExplorerError(f"{context}: '{key}' must be a non-empty string")
    return value


def _string_list(table: dict, key: str, context: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ExplorerError(f"{context}: '{key}' must be a list of non-empty strings")
    return value


def _integer(table: dict, key: str, context: str) -> int:
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExplorerError(f"{context}: '{key}' must be an integer")
    return value


def _nonempty_string_list(table: dict, key: str, context: str) -> list[str]:
    value = _string_list(table, key, context)
    if not value:
        raise ExplorerError(f"{context}: '{key}' must not be empty")
    return value


def parse_source_ref(raw: str, context: str) -> SourceRef:
    path, separator, heading = raw.partition("#")
    if not path or path.startswith("/") or posixpath.normpath(path) != path or path.startswith("../") or path == "..":
        raise ExplorerError(f"{context}: source reference '{raw}' must be a normalized repository-relative path")
    if separator and not heading.strip():
        raise ExplorerError(f"{context}: source reference '{raw}' has an empty heading")
    return SourceRef(path, heading if separator else None)


def load_stages(raw_stages: object) -> list[MapStage]:
    """Validate the ``[[stage]]`` entries that link lifecycle stages to engineering-source elements."""
    if not isinstance(raw_stages, list) or not raw_stages:
        raise ExplorerError(f"{MAP_PATH}: at least one [[stage]] is required")
    stages: list[MapStage] = []
    for position, table in enumerate(raw_stages, start=1):
        label = f"{MAP_PATH} stage #{position}"
        if not isinstance(table, dict):
            raise ExplorerError(f"{label}: must be a table")
        if isinstance(table.get("id"), str) and table["id"].strip():
            label = f"{MAP_PATH} stage '{table['id']}'"
        _check_keys(table, STAGE_REQUIRED, set(), label)
        identifier = _string(table, "id", label)
        label = f"{MAP_PATH} stage '{identifier}'"
        if not ID_RE.match(identifier):
            raise ExplorerError(f"{label}: id must be lowercase kebab-case")
        if any(stage.id == identifier for stage in stages):
            raise ExplorerError(f"{MAP_PATH}: duplicate stage id '{identifier}'")
        elements = _nonempty_string_list(table, "elements", label)
        if len(set(elements)) != len(elements):
            raise ExplorerError(f"{label}: lists an element id more than once")
        stages.append(MapStage(identifier, elements))
    return stages


def load_map(repo: Repo) -> tuple[str, list[Node], list[Node], list[MapStage]]:
    """Load and strictly validate the structure-only map; return (title, elements, collections, stage links)."""
    require_source(repo, MAP_PATH, "Explorer map")
    try:
        data = tomllib.loads((repo.root / MAP_PATH).read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ExplorerError(f"{MAP_PATH} is not valid TOML: {exc}") from exc
    unknown = sorted(set(data) - TOP_LEVEL)
    if unknown:
        raise ExplorerError(f"{MAP_PATH}: unknown top-level key(s): {', '.join(unknown)}")
    site = data.get("site")
    if not isinstance(site, dict):
        raise ExplorerError(f"{MAP_PATH}: [site] table is required")
    _check_keys(site, SITE_REQUIRED, set(), f"{MAP_PATH} [site]")
    title = _string(site, "title", f"{MAP_PATH} [site]")
    raw_elements = data.get("element")
    if not isinstance(raw_elements, list) or not raw_elements:
        raise ExplorerError(f"{MAP_PATH}: at least one [[element]] is required")
    raw_collections = data.get("collection", [])
    if not isinstance(raw_collections, list):
        raise ExplorerError(f"{MAP_PATH}: [[collection]] must be an array of tables")
    elements: list[Node] = []
    for position, table in enumerate(raw_elements, start=1):
        label = f"{MAP_PATH} element #{position}"
        if not isinstance(table, dict):
            raise ExplorerError(f"{label}: must be a table")
        _check_keys(table, ELEMENT_REQUIRED, ELEMENT_OPTIONAL, label)
        identifier = _string(table, "id", label)
        label = f"{MAP_PATH} element '{identifier}'"
        if not ID_RE.match(identifier):
            raise ExplorerError(f"{label}: id must be lowercase kebab-case")
        refs = [parse_source_ref(raw, label) for raw in _string_list(table, "sources", label)]
        if len({ref.label for ref in refs}) != len(refs):
            raise ExplorerError(f"{label}: duplicate source reference")
        elements.append(Node(
            id=identifier,
            title=_string(table, "title", label),
            kind="element",
            parent=_string(table, "parent", label) if "parent" in table else None,
            order=_integer(table, "order", label),
            sources=refs,
            related=_string_list(table, "related", label),
        ))
    collections: list[Node] = []
    for position, table in enumerate(raw_collections, start=1):
        label = f"{MAP_PATH} collection #{position}"
        if not isinstance(table, dict):
            raise ExplorerError(f"{label}: must be a table")
        _check_keys(table, COLLECTION_REQUIRED, COLLECTION_OPTIONAL, label)
        identifier = _string(table, "id", label)
        label = f"{MAP_PATH} collection '{identifier}'"
        if not ID_RE.match(identifier):
            raise ExplorerError(f"{label}: id must be lowercase kebab-case")
        glob = _string(table, "glob", label)
        if "**" in glob:
            raise ExplorerError(f"{label}: '**' is not supported in glob; use '*' within one path segment")
        title_from = _string(table, "title_from", label)
        summary_from = _string(table, "summary_from", label)
        slug_from = _string(table, "slug_from", label)
        if not TITLE_FROM_RE.match(title_from):
            raise ExplorerError(f"{label}: title_from must be 'heading', 'slug' or 'toml:<key>'")
        if not SUMMARY_FROM_RE.match(summary_from):
            raise ExplorerError(f"{label}: summary_from must be 'first-paragraph', 'section:<Heading>' or 'toml:<key>'")
        if slug_from not in ("stem", "parent"):
            raise ExplorerError(f"{label}: slug_from must be 'stem' or 'parent'")
        companions = _string_list(table, "companions", label)
        for companion in companions:
            if "{stem}" not in companion and "{slug}" not in companion:
                raise ExplorerError(f"{label}: companion template '{companion}' must contain {{stem}} or {{slug}}")
        collections.append(Node(
            id=identifier,
            title=_string(table, "title", label),
            kind="collection",
            parent=_string(table, "parent", label) if "parent" in table else None,
            order=_integer(table, "order", label),
            sources=[],
            related=[],
            collection={
                "glob": glob,
                "title_from": title_from,
                "summary_from": summary_from,
                "slug_from": slug_from,
                "companions": companions,
            },
        ))
    return title, elements, collections, load_stages(data.get("stage"))


def _glob_regex(glob: str) -> re.Pattern[str]:
    pattern = ""
    for char in glob:
        pattern += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
    return re.compile(f"^{pattern}$")


# ---------------------------------------------------------------------------
# Site assembly (pass 1) and rendering (pass 2)
# ---------------------------------------------------------------------------


class Corpus:
    def __init__(self, repo: Repo):
        self.repo = repo
        self.docs: dict[str, MdDoc] = {}
        self.tomls: dict[str, dict] = {}

    def markdown(self, path: str, context: str) -> MdDoc:
        if path not in self.docs:
            if not path.endswith(".md"):
                raise ExplorerError(f"{context}: source '{path}' is not a Markdown file")
            self.docs[path] = parse_markdown(read_text(self.repo, path, context), path)
        return self.docs[path]

    def toml(self, path: str, context: str) -> dict:
        if path not in self.tomls:
            try:
                self.tomls[path] = tomllib.loads(read_text(self.repo, path, context))
            except tomllib.TOMLDecodeError as exc:
                raise ExplorerError(f"{context}: source '{path}' is not valid TOML: {exc}") from exc
        return self.tomls[path]

    def excerpt(self, ref: SourceRef, context: str) -> tuple[list, int]:
        doc = self.markdown(ref.path, context)
        blocks = doc.blocks
        if ref.heading is None:
            if blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1:
                blocks = blocks[1:]
            for block in blocks:
                if isinstance(block, Heading) and block.level == 1:
                    raise ExplorerError(
                        f"{context}: source '{ref.path}' has more than one level-1 heading; reference a heading section instead"
                    )
            base = 1
        else:
            matches = [position for position, block in enumerate(blocks) if isinstance(block, Heading) and block.text == ref.heading]
            if not matches:
                raise ExplorerError(f"{context}: heading '{ref.heading}' not found in '{ref.path}'")
            if len(matches) > 1:
                raise ExplorerError(f"{context}: heading '{ref.heading}' is ambiguous in '{ref.path}' ({len(matches)} matches)")
            start = matches[0]
            base = blocks[start].level
            end = len(blocks)
            for position in range(start + 1, len(blocks)):
                block = blocks[position]
                if isinstance(block, Heading) and block.level <= base:
                    end = position
                    break
            blocks = blocks[start + 1:end]
        if not blocks:
            raise ExplorerError(f"{context}: excerpt of '{ref.label}' is empty")
        return blocks, base

    def section_text(self, ref: SourceRef, context: str) -> str:
        """Raw text of a bound section (heading line excluded) or of the whole file; input of the review digest."""
        text = read_text(self.repo, ref.path, context)
        if ref.heading is None:
            return text
        if not ref.path.endswith(".md"):
            raise ExplorerError(f"{context}: source '{ref.label}' names a heading but '{ref.path}' is not a Markdown file")
        blocks = self.markdown(ref.path, context).blocks
        matches = [block for block in blocks if isinstance(block, Heading) and block.text == ref.heading]
        if not matches:
            raise ExplorerError(f"{context}: heading '{ref.heading}' not found in '{ref.path}'")
        if len(matches) > 1:
            raise ExplorerError(f"{context}: heading '{ref.heading}' is ambiguous in '{ref.path}' ({len(matches)} matches)")
        start = matches[0]
        end_line = len(text.splitlines()) + 1
        for block in blocks:
            if isinstance(block, Heading) and block.line > start.line and block.level <= start.level:
                end_line = block.line
                break
        body = "\n".join(text.splitlines()[start.line:end_line - 1])
        if not body.strip():
            raise ExplorerError(f"{context}: section '{ref.label}' is empty")
        return body


def section_paragraph(doc: MdDoc, name: str) -> Para | None:
    matches = [position for position, block in enumerate(doc.blocks) if isinstance(block, Heading) and block.text == name]
    if len(matches) != 1:
        return None
    start = matches[0]
    level = doc.blocks[start].level
    for block in doc.blocks[start + 1:]:
        if isinstance(block, Heading) and block.level <= level:
            return None
        if isinstance(block, Para):
            return block
    return None


def first_paragraph(blocks: list) -> Para | None:
    for block in blocks:
        if isinstance(block, Para):
            return block
    return None


def inline_plain(raw: str, path: str, line: int, context: str) -> str:
    try:
        return plain_text(parse_inline(raw))
    except InlineError as exc:
        raise ExplorerError(f"{path}:{line + raw.count(chr(10), 0, exc.offset)}: unsupported Markdown construct ({exc.reason}) in {context}") from exc


def dotted(data: dict, key: str, path: str, context: str) -> str:
    value: object = data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ExplorerError(f"{context}: key '{key}' not found in '{path}'")
        value = value[part]
    if not isinstance(value, str) or not value.strip():
        raise ExplorerError(f"{context}: key '{key}' in '{path}' must be a non-empty string")
    return value


# ---------------------------------------------------------------------------
# Editorial layer: one explanatory node per semantic concept
# ---------------------------------------------------------------------------

NODES_DIR = "explorer/nodes"
REVIEW_PATH = "explorer/editorial-review.json"
STOP = "stop"

# role -> (legend label, stylesheet variable)
ROLES: dict[str, tuple[str, str]] = {
    "stage": ("этап", "--stage"),
    "mechanism": ("механизм", "--mech"),
    "artifact": ("артефакт", "--artifact"),
    "actor": ("участник", "--actor"),
    "gate": ("проверка и возврат", "--gate"),
    "external": ("внешняя система", "--ext"),
    "source": ("источник", "--src"),
    "neutral": ("нейтрально", "--muted"),
}
LEGEND_ROLES = ("stage", "mechanism", "artifact", "actor", "gate", "external", "source")
TRANSITION_TYPES = {"main": "основной", "conditional": "условный", "return": "возврат"}
KINDS = ("overview", "stage", "mechanism", "part", "topic", "term")
OUTLINE_KINDS = ("stage", "mechanism", "part", "topic")

COMMON_KEYS = {"id", "kind", "title", "definition", "sources"}
# Structure is relation data (hierarchy, order, schema, usage); an outline keeps it so the tree, the lifecycle
# schema and the coverage page stay complete. Content is the explanation itself and is absent from an outline.
STRUCTURE_KEYS = {
    "overview": (set(), set()),
    "stage": ({"order", "short_title", "tagline", "transitions", "children"}, set()),
    "mechanism": ({"order", "role", "used_in"}, {"children"}),
    "part": ({"role", "used_in"}, set()),
    "topic": ({"order"}, {"children"}),
    "term": (set(), set()),
}
OVERVIEW_KEYS = {
    "heading", "kicker", "headline", "subhead", "lead", "thesis", "responsible", "not_responsible",
    "schema_note", "cta", "level", "maintenance_auto", "maintenance_editorial",
}
FLOW_REQUIRED = {"lead", "thesis", "inputs", "action", "outputs", "path", "example"}
CONTENT_KEYS = {
    "stage": (FLOW_REQUIRED, {"terms", "fork"}),
    "mechanism": (FLOW_REQUIRED | {"guarantees"}, {"terms", "fork", "cycle"}),
    "part": (FLOW_REQUIRED, {"terms", "fork", "guarantees", "cycle"}),
    "topic": ({"lead", "thesis", "points"}, set()),
}

CONJUNCTIONS = frozenset({
    "и", "или", "а", "но", "что", "чтобы", "который", "которая", "которые", "в", "на", "с", "со", "к", "по", "для",
    "от", "из", "не", "же", "как", "когда", "если", "то", "при", "без", "до", "за", "у", "о", "об",
})
MARKDOWN_PATTERNS = (
    (re.compile(r"\*\*|__|~~"), "emphasis or strikethrough markers"),
    (re.compile(r"!?\[[^\]]*\]\([^)]*\)"), "an inline link or image"),
    (re.compile(r"(?m)^\s{0,3}#{1,6}\s"), "a heading marker"),
    (re.compile(r"(?m)^\s*[-*+]\s"), "a list marker"),
    (re.compile(r"(?m)^\s*\d{1,3}[.)]\s"), "a numbered list marker"),
    (re.compile(r"(?m)^\s*>"), "a block quote marker"),
)
CLOSERS = "»)\"'”"


@dataclasses.dataclass(frozen=True)
class Binding:
    ref: SourceRef
    note: str | None


@dataclasses.dataclass
class EdNode:
    id: str
    kind: str
    title: str
    definition: str
    outline: bool
    sources: list[Binding]
    data: dict
    file: str
    parent: str | None = None  # tree parent: the owning mechanism of a part, the owning topic of a term

    @property
    def label(self) -> str:
        return f"{self.file} node '{self.id}'"

    @property
    def role(self) -> str:
        if self.kind in ("mechanism", "part"):
            return self.data["role"]
        return "artifact" if self.kind in ("topic", "term") else "stage"

    @property
    def level(self) -> int:
        return {"overview": 0, "stage": 1}.get(self.kind, 2)


def _fail(ctx: str, field: str, reason: str) -> ExplorerError:
    return ExplorerError(f"{ctx}: field '{field}' {reason}")


def check_text(value: object, ctx: str, field: str, mode: str) -> str:
    """Validate one authored text. ``mode``: ``label`` (short caption), ``fragment`` or ``sentence``."""
    if not isinstance(value, str) or not value.strip():
        raise _fail(ctx, field, "must be a non-empty string")
    if value != value.strip() or "\n" in value:
        raise _fail(ctx, field, "must be a single line without leading or trailing whitespace")
    if "..." in value or "…" in value:
        raise _fail(ctx, field, "contains an ellipsis; write the full text")
    if "```" in value:
        raise _fail(ctx, field, "contains a fenced code block marker")
    if value.count("`") % 2:
        raise _fail(ctx, field, "has an unbalanced code span")
    outside = re.sub(r"`[^`]*`", "", value)
    for pattern, reason in MARKDOWN_PATTERNS:
        if pattern.search(outside):
            raise _fail(ctx, field, f"contains Markdown syntax ({reason}); text is plain prose with inline code spans only")
    if mode == "sentence":
        trimmed = value.rstrip(CLOSERS)
        if not trimmed or trimmed[-1] not in ".!?":
            raise _fail(ctx, field, "is not a finished sentence: it must end with terminal punctuation")
    elif mode == "fragment":
        words = re.findall(r"[\w'-]+", value.lower())
        if value[-1] in ",;:-–—(" or (words and words[-1] in CONJUNCTIONS):
            raise _fail(ctx, field, "is unfinished: it ends with a connective or a separator")
    return value


def _strict(table: dict, required: set[str], optional: set[str], ctx: str, where: str | None = None) -> None:
    prefix = f"{where}: " if where else ""
    unknown = sorted(set(table) - required - optional)
    if unknown:
        raise ExplorerError(f"{ctx}: {prefix}unknown key(s): {', '.join(unknown)}")
    missing = sorted(required - set(table))
    if missing:
        raise ExplorerError(f"{ctx}: {prefix}missing required key(s): {', '.join(missing)}")


def _list_of(table: dict, key: str, ctx: str, *, minimum: int = 1, path: str | None = None) -> list:
    value = table[key]
    name = path or key
    if not isinstance(value, list):
        raise _fail(ctx, name, "must be a list")
    if len(value) < minimum:
        raise _fail(ctx, name, f"must have at least {minimum} item(s)")
    return value


def _table_items(
    table: dict, key: str, ctx: str, required: set[str], optional: set[str], *, minimum: int = 1, path: str | None = None
) -> list[dict]:
    name = path or key
    items = _list_of(table, key, ctx, minimum=minimum, path=name)
    for position, item in enumerate(items, start=1):
        where = f"{name}[{position}]"
        if not isinstance(item, dict):
            raise _fail(ctx, where, "must be a table")
        _strict(item, required, optional, ctx, where)
    return items


def _role(value: object, ctx: str, field: str) -> str:
    if value not in ROLES:
        raise _fail(ctx, field, f"must be one of: {', '.join(ROLES)}")
    return value  # type: ignore[return-value]


def _id_list(table: dict, key: str, ctx: str, *, minimum: int = 0) -> list[str]:
    value = _list_of(table, key, ctx, minimum=minimum)
    for item in value:
        if not isinstance(item, str) or not ID_RE.match(item):
            raise _fail(ctx, key, "must be a list of lowercase kebab-case node ids")
    if len(set(value)) != len(value):
        raise _fail(ctx, key, "lists a node more than once")
    return value


def _optional_id(table: dict, key: str, ctx: str, where: str) -> None:
    if key in table and (not isinstance(table[key], str) or not ID_RE.match(table[key])):
        raise _fail(ctx, where, "must be a lowercase kebab-case node id")


def _validate_flow_item(item: dict, ctx: str, where: str, *, consumer: bool) -> None:
    check_text(item["title"], ctx, f"{where}.title", "label")
    check_text(item["text"], ctx, f"{where}.text", "sentence")
    _role(item["role"], ctx, f"{where}.role")
    _optional_id(item, "node", ctx, f"{where}.node")
    key = "consumer" if consumer else "note"
    if key in item:
        check_text(item[key], ctx, f"{where}.{key}", "label")


def _validate_steps(steps: list, ctx: str, field: str, *, emphasis: bool) -> None:
    for position, step in enumerate(steps, start=1):
        where = f"{field}[{position}]"
        if isinstance(step, str):
            check_text(step, ctx, where, "sentence")
            continue
        if not emphasis or not isinstance(step, dict):
            raise _fail(ctx, where, "must be a sentence")
        _strict(step, {"text"}, {"emphasis"}, ctx, where)
        text = check_text(step["text"], ctx, f"{where}.text", "sentence")
        phrases = step.get("emphasis", [])
        if not isinstance(phrases, list) or ("emphasis" in step and not phrases):
            raise _fail(ctx, f"{where}.emphasis", "must be a non-empty list of phrases")
        for phrase in phrases:
            check_text(phrase, ctx, f"{where}.emphasis", "label")
            if text.count(phrase) != 1:
                raise _fail(ctx, f"{where}.emphasis", f"phrase '{phrase}' must occur exactly once in the step text")


def _validate_content(node: EdNode, table: dict) -> None:
    ctx = node.label
    kind = node.kind
    check_text(table["lead"], ctx, "lead", "sentence")
    check_text(table["thesis"], ctx, "thesis", "sentence")
    if kind == "topic":
        for position, point in enumerate(_table_items(table, "points", ctx, {"title", "text"}, set()), start=1):
            check_text(point["title"], ctx, f"points[{position}].title", "label")
            check_text(point["text"], ctx, f"points[{position}].text", "sentence")
        return
    if "terms" in table:
        _id_list(table, "terms", ctx, minimum=1)
    for position, item in enumerate(_table_items(table, "inputs", ctx, {"title", "text", "role"}, {"node", "note"}), start=1):
        _validate_flow_item(item, ctx, f"inputs[{position}]", consumer=False)
    action = table["action"]
    if not isinstance(action, dict):
        raise _fail(ctx, "action", "must be a table")
    _strict(action, {"label", "title", "steps"}, set(), ctx, "action")
    check_text(action["label"], ctx, "action.label", "label")
    check_text(action["title"], ctx, "action.title", "label")
    steps = _list_of(action, "steps", ctx, path="action.steps")
    _validate_steps(steps, ctx, "action.steps", emphasis=False)
    for position, item in enumerate(_table_items(table, "outputs", ctx, {"title", "text", "role", "consumer"}, {"node"}), start=1):
        _validate_flow_item(item, ctx, f"outputs[{position}]", consumer=True)
    for position, fork in enumerate(_table_items(table, "fork", ctx, {"title", "branch"}, {"note"}, minimum=0) if "fork" in table else [], start=1):
        where = f"fork[{position}]"
        check_text(fork["title"], ctx, f"{where}.title", "label")
        if "note" in fork:
            check_text(fork["note"], ctx, f"{where}.note", "sentence")
        branches = _table_items(
            fork, "branch", ctx, {"name", "code", "role", "recognized", "creates", "next"}, {"next_node", "stop"}, minimum=2, path=f"{where}.branch"
        )
        for index, branch in enumerate(branches, start=1):
            at = f"{where}.branch[{index}]"
            for name in ("name", "code"):
                check_text(branch[name], ctx, f"{at}.{name}", "label")
            for name in ("recognized", "creates"):
                check_text(branch[name], ctx, f"{at}.{name}", "sentence")
            check_text(branch["next"], ctx, f"{at}.next", "label")
            _role(branch["role"], ctx, f"{at}.role")
            _optional_id(branch, "next_node", ctx, f"{at}.next_node")
            if "stop" in branch and branch["stop"] is not True:
                raise _fail(ctx, f"{at}.stop", "must be true when present")
    for position, item in enumerate(_table_items(table, "path", ctx, {"title", "tag", "role", "when", "outcome"}, set()), start=1):
        where = f"path[{position}]"
        check_text(item["title"], ctx, f"{where}.title", "label")
        check_text(item["tag"], ctx, f"{where}.tag", "label")
        check_text(item["when"], ctx, f"{where}.when", "sentence")
        check_text(item["outcome"], ctx, f"{where}.outcome", "fragment")
        _role(item["role"], ctx, f"{where}.role")
    example = table["example"]
    if not isinstance(example, dict):
        raise _fail(ctx, "example", "must be a table")
    _strict(example, {"title", "steps"}, set(), ctx, "example")
    check_text(example["title"], ctx, "example.title", "label")
    _validate_steps(_list_of(example, "steps", ctx, path="example.steps"), ctx, "example.steps", emphasis=True)
    if "guarantees" in table:
        for position, item in enumerate(_table_items(table, "guarantees", ctx, {"title", "text"}, set()), start=1):
            check_text(item["title"], ctx, f"guarantees[{position}].title", "label")
            check_text(item["text"], ctx, f"guarantees[{position}].text", "sentence")
    if "cycle" in table:
        cycle = table["cycle"]
        if not isinstance(cycle, dict):
            raise _fail(ctx, "cycle", "must be a table")
        _strict(cycle, {"title", "step"}, {"note"}, ctx, "cycle")
        check_text(cycle["title"], ctx, "cycle.title", "label")
        steps = _table_items(cycle, "step", ctx, {"state", "text"}, {"arrow", "emphasis"}, minimum=2, path="cycle.step")
        for index, step in enumerate(steps, start=1):
            at = f"cycle.step[{index}]"
            check_text(step["state"], ctx, f"{at}.state", "label")
            check_text(step["text"], ctx, f"{at}.text", "fragment")
            last = index == len(steps)
            if last and "arrow" in step:
                raise _fail(ctx, f"{at}.arrow", "is not allowed on the last step")
            if not last:
                if "arrow" not in step:
                    raise _fail(ctx, f"{at}.arrow", "is required on every step except the last")
                check_text(step["arrow"], ctx, f"{at}.arrow", "label")
            if "emphasis" in step:
                _role(step["emphasis"], ctx, f"{at}.emphasis")
        if "note" in cycle:
            for index, note in enumerate(_table_items(cycle, "note", ctx, {"tag", "text", "role"}, set(), path="cycle.note"), start=1):
                at = f"cycle.note[{index}]"
                check_text(note["tag"], ctx, f"{at}.tag", "label")
                check_text(note["text"], ctx, f"{at}.text", "sentence")
                _role(note["role"], ctx, f"{at}.role")


def _validate_structure(node: EdNode, table: dict) -> None:
    ctx = node.label
    kind = node.kind
    if kind == "stage":
        order = table["order"]
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise _fail(ctx, "order", "must be a positive integer")
        check_text(table["short_title"], ctx, "short_title", "label")
        check_text(table["tagline"], ctx, "tagline", "label")
        _id_list(table, "children", ctx, minimum=1)
        seen: set[str] = set()
        for position, item in enumerate(_table_items(table, "transitions", ctx, {"to", "type", "reason"}, {"label"}), start=1):
            where = f"transitions[{position}]"
            if not isinstance(item["to"], str) or not (ID_RE.match(item["to"]) or item["to"] == STOP):
                raise _fail(ctx, f"{where}.to", f"must be a stage id or '{STOP}'")
            if item["to"] in seen:
                raise _fail(ctx, f"{where}.to", f"repeats the transition to '{item['to']}'")
            seen.add(item["to"])
            if item["type"] not in TRANSITION_TYPES:
                raise _fail(ctx, f"{where}.type", f"must be one of: {', '.join(TRANSITION_TYPES)}")
            check_text(item["reason"], ctx, f"{where}.reason", "fragment")
            if "label" in item:
                check_text(item["label"], ctx, f"{where}.label", "label")
        return
    if kind in ("mechanism", "part"):
        _role(table["role"], ctx, "role")
        seen_stages: set[str] = set()
        for position, item in enumerate(_table_items(table, "used_in", ctx, {"stage"}, {"note"}), start=1):
            where = f"used_in[{position}]"
            if not isinstance(item["stage"], str) or not ID_RE.match(item["stage"]):
                raise _fail(ctx, f"{where}.stage", "must be a stage id")
            if item["stage"] in seen_stages:
                raise _fail(ctx, f"{where}.stage", f"repeats stage '{item['stage']}'")
            seen_stages.add(item["stage"])
            if "note" in item:
                check_text(item["note"], ctx, f"{where}.note", "label")
    if kind in ("mechanism", "topic"):
        order = table["order"]
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise _fail(ctx, "order", "must be a positive integer")
        if "children" in table:
            _id_list(table, "children", ctx, minimum=1)


def _validate_overview(node: EdNode, table: dict) -> None:
    ctx = node.label
    for key in ("heading", "kicker", "headline", "cta"):
        check_text(table[key], ctx, key, "label")
    for key in ("subhead", "lead", "thesis", "schema_note"):
        check_text(table[key], ctx, key, "sentence")
    for key in ("responsible", "not_responsible", "maintenance_auto", "maintenance_editorial"):
        for position, item in enumerate(_list_of(table, key, ctx), start=1):
            check_text(item, ctx, f"{key}[{position}]", "sentence")
    for position, row in enumerate(_table_items(table, "level", ctx, {"name", "what", "visible", "hidden"}, set()), start=1):
        for key in ("name", "what", "visible", "hidden"):
            check_text(row[key], ctx, f"level[{position}].{key}", "fragment")


def parse_binding(raw: object, ctx: str, position: int) -> Binding:
    where = f"sources[{position}]"
    note = None
    if isinstance(raw, dict):
        _strict(raw, {"ref"}, {"note"}, ctx, where)
        if "note" in raw:
            note = check_text(raw["note"], ctx, f"{where}.note", "label")
        raw = raw["ref"]
    if not isinstance(raw, str) or not raw.strip():
        raise _fail(ctx, where, "must be a 'path' or 'path#Heading' string")
    return Binding(parse_source_ref(raw, f"{ctx} {where}"), note)


def load_node(path: str, data: dict) -> EdNode:
    stem = posixpath.splitext(posixpath.basename(path))[0]
    label = f"{path} node '{data['id']}'" if isinstance(data.get("id"), str) else path
    kind = data.get("kind")
    if kind not in KINDS:
        raise _fail(label, "kind", f"must be one of: {', '.join(KINDS)}")
    outline = data.get("outline", False)
    if outline is not False and outline is not True:
        raise _fail(label, "outline", "must be a boolean")
    if outline and kind not in OUTLINE_KINDS:
        raise _fail(label, "outline", f"is not allowed for kind '{kind}'")
    structure_required, structure_optional = STRUCTURE_KEYS[kind]
    if kind == "overview":
        content_required, content_optional = OVERVIEW_KEYS, set()
    elif kind == "term":
        content_required, content_optional = set(), set()
    else:
        content_required, content_optional = CONTENT_KEYS[kind]
    if outline:
        content_required, content_optional = set(), set()
    required = COMMON_KEYS | structure_required | content_required
    optional = structure_optional | content_optional | {"outline"}
    unknown = sorted(set(data) - required - optional)
    if unknown:
        hint = " (an outline carries no explanation text)" if outline and set(unknown) & (
            FLOW_REQUIRED | {"terms", "fork", "cycle", "guarantees", "points"}
        ) else ""
        raise ExplorerError(f"{label}: unknown key(s): {', '.join(unknown)}{hint}")
    missing = sorted(required - set(data))
    if missing:
        raise ExplorerError(f"{label}: missing required key(s): {', '.join(missing)}")
    identifier = data["id"]
    if not isinstance(identifier, str) or not ID_RE.match(identifier):
        raise _fail(label, "id", "must be lowercase kebab-case")
    if identifier != stem:
        raise _fail(label, "id", f"must equal the file name '{stem}'")
    if kind == "overview" and identifier != "overview":
        raise _fail(label, "id", "of the overview node must be 'overview'")
    title = check_text(data["title"], label, "title", "label")
    definition = check_text(data["definition"], label, "definition", "sentence")
    raw_sources = _list_of(data, "sources", label)
    bindings = [parse_binding(raw, label, position) for position, raw in enumerate(raw_sources, start=1)]
    if len({binding.ref.label for binding in bindings}) != len(bindings):
        raise _fail(label, "sources", "binds the same source section more than once")
    node = EdNode(identifier, kind, title, definition, bool(outline), bindings, data, path)
    if kind == "overview":
        _validate_overview(node, data)
    else:
        _validate_structure(node, data)
        if not outline and kind not in ("term",):
            _validate_content(node, data)
    return node


def load_editorial(repo: Repo) -> dict[str, EdNode]:
    prefix = f"{NODES_DIR}/"
    paths = sorted(path for path in repo.allowed if path.startswith(prefix))
    if not paths:
        raise ExplorerError(f"no editorial nodes under {NODES_DIR}/")
    nodes: dict[str, EdNode] = {}
    for path in paths:
        if "/" in path[len(prefix):] or not path.endswith(".toml"):
            raise ExplorerError(f"{path}: editorial nodes must be .toml files directly under {NODES_DIR}/")
        try:
            data = tomllib.loads((repo.root / path).read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise ExplorerError(f"{path} is not valid TOML: {exc}") from exc
        node = load_node(path, data)
        if node.id in nodes:
            raise ExplorerError(f"{path}: duplicate editorial node id '{node.id}'")
        nodes[node.id] = node
    if "overview" not in nodes:
        raise ExplorerError(f"{NODES_DIR}/overview.toml: the overview node is required")
    return nodes


def link_editorial(nodes: dict[str, EdNode], map_stage_ids: list[str]) -> list[EdNode]:
    """Check cross-references between nodes, assign tree parents and return the stages in lifecycle order."""
    stages = sorted((node for node in nodes.values() if node.kind == "stage"), key=lambda node: (node.data["order"], node.id))
    stage_ids = {node.id for node in stages}
    for expected, stage in enumerate(stages, start=1):
        order = stage.data["order"]
        if any(other is not stage and other.data["order"] == order for other in stages):
            other = next(other for other in stages if other is not stage and other.data["order"] == order)
            raise _fail(stage.label, "order", f"{order} duplicates stage '{other.id}'")
        if order != expected:
            raise _fail(
                stage.label, "order",
                f"{order} is not contiguous; expected {expected} (stage orders must run from 1 to the number of stages without gaps)",
            )
    unmapped = sorted(stage_ids - set(map_stage_ids))
    if unmapped:
        raise ExplorerError(f"{NODES_DIR}: stage node(s) {', '.join(unmapped)} have no [[stage]] entry in {MAP_PATH}")
    unknown_stage = sorted(set(map_stage_ids) - stage_ids)
    if unknown_stage:
        raise ExplorerError(f"{MAP_PATH}: [[stage]] entry(ies) {', '.join(unknown_stage)} have no editorial stage node in {NODES_DIR}/")

    def require(node: EdNode, field: str, target: str, kinds: tuple[str, ...] | None = None) -> EdNode:
        other = nodes.get(target)
        if other is None:
            raise _fail(node.label, field, f"references unknown node '{target}'")
        if other is node:
            raise _fail(node.label, field, "references the node itself")
        if kinds is not None and other.kind not in kinds:
            raise _fail(node.label, field, f"references '{target}' of kind '{other.kind}'; expected {' or '.join(kinds)}")
        return other

    by_order = {stage.id: stage.data["order"] for stage in stages}
    for stage in stages:
        for position, item in enumerate(stage.data["transitions"], start=1):
            where = f"transitions[{position}].to"
            if item["to"] == STOP:
                if item["type"] == "return":
                    raise _fail(stage.label, f"transitions[{position}].type", "a transition to 'stop' cannot be a return")
                continue
            if item["to"] not in stage_ids:
                raise _fail(stage.label, where, f"references unknown stage '{item['to']}'")
            if item["to"] == stage.id:
                raise _fail(stage.label, where, "references the stage itself")
            backward = by_order[item["to"]] < by_order[stage.id]
            if (item["type"] == "return") != backward:
                raise _fail(
                    stage.label, f"transitions[{position}].type",
                    "a return must lead to an earlier stage and a main or conditional transition to a later one",
                )
        for target in stage.data["children"]:
            require(stage, "children", target, ("mechanism", "part"))

    owners: dict[str, str] = {}
    for node in sorted(nodes.values(), key=lambda item: item.id):
        if node.kind in ("mechanism", "topic"):
            expected_kind = "part" if node.kind == "mechanism" else "term"
            for target in node.data.get("children", []):
                child = require(node, "children", target, (expected_kind,))
                if target in owners:
                    raise _fail(node.label, "children", f"'{target}' already belongs to '{owners[target]}'")
                owners[target] = node.id
                child.parent = node.id
        if node.kind in ("mechanism", "part"):
            for position, item in enumerate(node.data["used_in"], start=1):
                if item["stage"] not in stage_ids:
                    raise _fail(node.label, f"used_in[{position}].stage", f"references unknown stage '{item['stage']}'")
    for node in nodes.values():
        if node.kind in ("part", "term") and node.parent is None:
            owner = "mechanism" if node.kind == "part" else "topic"
            raise ExplorerError(f"{node.label}: a {node.kind} must be listed in the 'children' of a {owner}")
    for kind in ("mechanism", "topic"):
        seen: dict[int, str] = {}
        for node in sorted((item for item in nodes.values() if item.kind == kind), key=lambda item: item.id):
            order = node.data["order"]
            if order in seen:
                raise _fail(node.label, "order", f"{order} duplicates {kind} '{seen[order]}'")
            seen[order] = node.id

    for node in nodes.values():
        if node.outline or node.kind in ("overview", "term"):
            continue
        content = node.data
        for field in ("inputs", "outputs"):
            for position, item in enumerate(content.get(field, []), start=1):
                if "node" in item:
                    require(node, f"{field}[{position}].node", item["node"])
        for fork_index, fork in enumerate(content.get("fork", []), start=1):
            for index, branch in enumerate(fork["branch"], start=1):
                if "next_node" in branch:
                    require(node, f"fork[{fork_index}].branch[{index}].next_node", branch["next_node"])
        prose = " ".join(content.get(key, "") for key in ("lead", "thesis"))
        for target in content.get("terms", []):
            term = require(node, "terms", target, ("term",))
            if term.title not in prose:
                raise _fail(node.label, "terms", f"term '{target}' ('{term.title}') does not occur in 'lead' or 'thesis'")
    return stages


def plural(count: int, forms: tuple[str, str, str]) -> str:
    tail = count % 100
    if 11 <= tail <= 19:
        return forms[2]
    return forms[0] if count % 10 == 1 else forms[1] if 2 <= count % 10 <= 4 else forms[2]


# ---------------------------------------------------------------------------
# Review record and drift
# ---------------------------------------------------------------------------

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ISSUE_TITLE = "Explorer: сверить пояснения"
ISSUE_LABEL = "explorer-drift"
ISSUE_LABEL_DESCRIPTION = "Editorial Explorer nodes whose bound sources changed since the last review"


def section_digest(text: str) -> str:
    """SHA-256 of a bound section with whitespace runs normalized, so whitespace-only edits never count as drift."""
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class Drift:
    node: str
    title: str
    binding: str
    reason: str  # changed | unreviewed | obsolete

    def message(self) -> str:
        if self.reason == "changed":
            return f"{self.node}: {self.binding} changed after the last editorial review"
        if self.reason == "unreviewed":
            return f"{self.node}: {self.binding} has no editorial review record"
        return f"{self.node}: review record for {self.binding} is obsolete"


def load_review(repo: Repo) -> dict[str, dict[str, str]]:
    require_source(repo, REVIEW_PATH, "Explorer editorial review record")
    try:
        data = json.loads((repo.root / REVIEW_PATH).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ExplorerError(f"{REVIEW_PATH} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExplorerError(f"{REVIEW_PATH}: must be an object mapping node ids to binding digests")
    for node, bindings in data.items():
        if not isinstance(bindings, dict):
            raise ExplorerError(f"{REVIEW_PATH}: entry '{node}' must map source bindings to digests")
        for binding, digest in bindings.items():
            if not isinstance(digest, str) or not SHA256_RE.match(digest):
                raise ExplorerError(f"{REVIEW_PATH}: entry '{node}' binding '{binding}' is not a SHA-256 digest")
    return data


def render_review(review: dict[str, dict[str, str]]) -> str:
    ordered = {node: {binding: review[node][binding] for binding in sorted(review[node])} for node in sorted(review)}
    return json.dumps(ordered, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def drift_markdown(items: list[Drift]) -> str:
    if not items:
        return "No editorial node is stale: every bound source section matches its last review.\n"
    lines = ["| Node | Source section | State |", "| --- | --- | --- |"]
    states = {"changed": "changed after the last review", "unreviewed": "no review record", "obsolete": "obsolete review record"}
    for item in items:
        lines.append(f"| `{item.node}` | `{item.binding}` | {states[item.reason]} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Lifecycle schema (inline SVG generated from stage transitions)
# ---------------------------------------------------------------------------

BOX_W, BOX_H = 194, 76
COL_X, COL_PITCH = 28, 240
ROW_Y = (94, 260)
EDGE_CLASS = {"main": "arm", "conditional": "alt", "return": "ret"}
MARKER_ID = {"main": "mS", "conditional": "mA", "return": "mR"}


def _schema_geometry(count: int) -> tuple[int, dict[int, tuple[int, int, int, int]]]:
    columns = math.ceil(count / 2)
    placed: dict[int, tuple[int, int, int, int]] = {}
    for order in range(1, count + 1):
        row, column = (0, order - 1) if order <= columns else (1, 2 * columns - order)
        placed[order] = (COL_X + column * COL_PITCH, ROW_Y[row], row, column)
    return columns, placed


def _edge(stage: EdNode, target: EdNode, item: dict, columns: int, placed: dict[int, tuple[int, int, int, int]]):
    """Return (path data, label placement) for one transition; fail when the layout cannot route it."""
    ax, ay, arow, acol = placed[stage.data["order"]]
    bx, by, brow, bcol = placed[target.data["order"]]
    kind = item["type"]
    where = f"{stage.label}: transition to '{target.id}'"
    if arow == brow and abs(acol - bcol) == 1:
        if bx > ax:
            return f"M{ax + BOX_W} {ay + BOX_H // 2} H{bx}", None
        return f"M{ax} {ay + BOX_H // 2} H{bx + BOX_W}", None
    if acol == bcol and arow == 0 and brow == 1 and kind != "return":
        return f"M{ax + BOX_W // 2} {ay + BOX_H} V{by - 2}", None
    if acol == bcol and arow == 1 and brow == 0 and kind == "return":
        if acol == columns - 1:
            path = f"M{ax + BOX_W - 7} {ay + 8} C{ax + BOX_W + 33} {ay - 12}, {ax + BOX_W + 33} {by + 66}, {ax + BOX_W + 3} {by + 51}"
            return path, (ax + BOX_W + 26, (ay + by + BOX_H) // 2, "vertical-end")
        if acol == 0:
            return f"M{ax + 30} {ay - 2} V{by + BOX_H + 2}", (ax + 18, (ay + by + BOX_H) // 2, "vertical-middle")
    if arow == brow and abs(acol - bcol) > 1:
        mid = (ax + bx) // 2 + BOX_W // 2
        if arow == 0:
            path = f"M{ax + BOX_W // 2} {ay - 2} C{ax + BOX_W // 2} {ay - 64}, {bx + BOX_W // 2} {ay - 64}, {bx + BOX_W // 2} {by - 2}"
            return path, (mid, ay - 56, "horizontal")
        path = f"M{ax + BOX_W // 2} {ay + BOX_H} C{ax + BOX_W // 2} {ay + 140}, {bx + BOX_W // 2} {ay + 140}, {bx + BOX_W // 2} {by + BOX_H + 4}"
        return path, (mid, ay + 148, "horizontal")
    raise ExplorerError(f"{where} ({kind}) cannot be routed by the lifecycle schema layout")


def render_schema(stages: list[EdNode], href_for, conditional: set[str]) -> str:
    count = len(stages)
    columns, placed = _schema_geometry(count)
    width = COL_X * 2 + (columns - 1) * COL_PITCH + BOX_W + 10
    height = 420
    by_id = {stage.id: stage for stage in stages}
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" focusable="false">',
        "<defs>",
    ]
    for kind, marker in MARKER_ID.items():
        parts.append(
            f'<marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path class="mk-{EDGE_CLASS[kind]}" d="M0 0L10 5L0 10z"/></marker>'
        )
    parts.append("</defs>")
    stop_index: dict[str, int] = {}
    for stage in stages:
        for item in stage.data["transitions"]:
            label = item.get("label")
            reason = esc(item["reason"])
            if item["to"] == STOP:
                ax, ay, _, _ = placed[stage.data["order"]]
                if label:
                    slot = stop_index.get(stage.id, 0)
                    stop_index[stage.id] = slot + 1
                    parts.append(f'<text class="lbl" x="{ax + 44}" y="{ay + BOX_H + 20 + 16 * slot}"><title>{reason}</title>{esc(label)}</text>')
                continue
            path, label_at = _edge(stage, by_id[item["to"]], item, columns, placed)
            kind = item["type"]
            parts.append(
                f'<path class="{EDGE_CLASS[kind]}" d="{path}" marker-end="url(#{MARKER_ID[kind]})"><title>{reason}</title></path>'
            )
            if label:
                if label_at is None:
                    raise ExplorerError(f"{stage.label}: transition to '{item['to']}' has a label but joins neighbouring stages; labels are drawn on arcs and returns only")
                x, y, mode = label_at
                tone = {"main": "main", "conditional": "alt", "return": "ret"}[kind]
                if mode == "horizontal":
                    parts.append(f'<text class="lbl {tone}" x="{x}" y="{y}" text-anchor="middle">{esc(label)}</text>')
                else:
                    anchor = "end" if mode == "vertical-end" else "middle"
                    parts.append(
                        f'<text class="lbl {tone}" x="{x}" y="{y}" text-anchor="{anchor}" transform="rotate(-90 {x} {y})">{esc(label)}</text>'
                    )
    for stage in stages:
        x, y, _, _ = placed[stage.data["order"]]
        cond = stage.id in conditional
        number = f"{stage.data['order']:02d}" + (" · условный" if cond else "")
        parts.append(
            f'<a href="{esc(href_for(stage.id))}"><title>{esc(stage.title)}</title>'
            f'<g class="stagebox{" cond" if cond else ""}"><rect class="bx bxs" x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="11"/>'
            f'<text class="n" x="{x + 16}" y="{y + 24}">{number}</text>'
            f'<text class="t" x="{x + 16}" y="{y + 45}">{esc(stage.data["short_title"])}</text>'
            f'<text class="s" x="{x + 16}" y="{y + 63}">{esc(stage.data["tagline"])}</text></g></a>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def inline_code(text: str) -> str:
    """Escape plain editorial text and turn its (validated, balanced) backtick spans into code elements."""
    return "".join(f"<code>{esc(part)}</code>" if index % 2 else esc(part) for index, part in enumerate(text.split("`")))




@dataclasses.dataclass
class TreeItem:
    key: tuple
    label: str
    href: str | None
    role: str
    num: str = ""
    hint: str = ""
    group: bool = False
    default_open: bool = False
    children: list["TreeItem"] = dataclasses.field(default_factory=list)


def role_style(role: str) -> str:
    return f' style="--c:var({ROLES[role][1]})"'


class Site:
    def __init__(self, repo: Repo):
        self.repo = repo
        self.corpus = Corpus(repo)
        self.title, elements, collections, self.map_stages = load_map(repo)
        self.nodes: dict[str, Node] = {}
        self._register(elements, collections)
        self.ed = load_editorial(repo)
        self.stages = link_editorial(self.ed, [stage.id for stage in self.map_stages])
        self.stage_by_id = {stage.id: stage for stage in self.stages}
        self._register_stages()
        self._link_tree()
        self.order: list[str] = []
        self._depth_first(self.roots)
        self.excerpts: dict[str, list[Excerpt]] = {}
        self._assemble()
        self._index_links()
        self.overview = self.ed["overview"]
        self.review = load_review(repo)
        self.digests = self._bind_editorial()
        self.drift = compute_drift(self.ed, self.digests, self.review)
        self.stale: dict[str, list[Drift]] = {}
        for item in self.drift:
            if item.reason != "obsolete":
                self.stale.setdefault(item.node, []).append(item)
        # A stage is conditional when every transition into it is conditional (only the release stage today).
        self.conditional: set[str] = set()
        for stage in self.stages:
            incoming = [item["type"] for other in self.stages for item in other.data["transitions"] if item["to"] == stage.id]
            if incoming and all(kind == "conditional" for kind in incoming):
                self.conditional.add(stage.id)
        self.mechanisms = sorted((n for n in self.ed.values() if n.kind == "mechanism"), key=lambda n: n.data["order"])
        self.topics = sorted((n for n in self.ed.values() if n.kind == "topic"), key=lambda n: n.data["order"])
        self.tree = self._build_tree()

    # -- level 3 structure (engineering sources) ---------------------------

    def _add(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ExplorerError(f"{MAP_PATH}: duplicate id '{node.id}'")
        self.nodes[node.id] = node

    def _register(self, elements: list[Node], collections: list[Node]) -> None:
        for node in elements + collections:
            self._add(node)
        for node in collections:
            self._enumerate(node)
        for node in list(self.nodes.values()):
            if node.parent is not None and node.parent not in self.nodes:
                raise ExplorerError(f"{MAP_PATH}: '{node.id}' has dangling parent '{node.parent}'")
            if node.parent is not None and self.nodes[node.parent].kind == "item":
                raise ExplorerError(f"{MAP_PATH}: '{node.id}' cannot have an enumerated item as parent")
            if node.parent is not None and self.nodes[node.parent].kind == "collection" and node.kind != "item":
                raise ExplorerError(f"{MAP_PATH}: '{node.id}' cannot be placed under collection '{node.parent}'")
            for target in node.related:
                if target not in self.nodes:
                    raise ExplorerError(f"{MAP_PATH}: '{node.id}' relates to unknown id '{target}'")
                if target == node.id:
                    raise ExplorerError(f"{MAP_PATH}: '{node.id}' relates to itself")
            if len(set(node.related)) != len(node.related):
                raise ExplorerError(f"{MAP_PATH}: '{node.id}' lists a related id more than once")

    def _register_stages(self) -> None:
        self.stage_usage: dict[str, list[EdNode]] = {}
        for entry in self.map_stages:
            for target in entry.elements:
                if target not in self.nodes:
                    raise ExplorerError(f"{MAP_PATH} stage '{entry.id}': references unknown element '{target}'")
                self.stage_usage.setdefault(target, []).append(self.stage_by_id[entry.id])
        for usage in self.stage_usage.values():
            usage.sort(key=lambda stage: stage.data["order"])

    def _enumerate(self, collection: Node) -> None:
        spec = collection.collection
        assert spec is not None
        context = f"collection '{collection.id}'"
        pattern = _glob_regex(spec["glob"])
        paths = sorted(path for path in self.repo.allowed if pattern.match(path))
        if not paths:
            raise ExplorerError(f"{MAP_PATH}: {context} glob '{spec['glob']}' matches no publicly distributable tracked file")
        for position, path in enumerate(paths, start=1):
            slug = Path(path).stem if spec["slug_from"] == "stem" else posixpath.basename(posixpath.dirname(path))
            if not SLUG_RE.match(slug):
                raise ExplorerError(f"{MAP_PATH}: {context} item '{path}' yields invalid slug '{slug}'")
            item_context = f"{context} item '{path}'"
            title, summary = self._item_title_summary(spec, path, slug, item_context)
            sources = [SourceRef(path, None)]
            for template in spec["companions"]:
                companion = template.replace("{stem}", Path(path).stem).replace("{slug}", slug)
                require_source(self.repo, companion, item_context)
                sources.append(SourceRef(companion, None))
            self._add(Node(
                id=f"{collection.id}.{slug}",
                title=title,
                kind="item",
                parent=collection.id,
                order=position,
                sources=sources,
                related=[],
                summary=summary,
            ))

    def _item_title_summary(self, spec: dict, path: str, slug: str, context: str) -> tuple[str, str]:
        title_from, summary_from = spec["title_from"], spec["summary_from"]
        is_toml = path.endswith(".toml")
        data = self.corpus.toml(path, context) if is_toml else None
        doc = None if is_toml else self.corpus.markdown(path, context)
        if title_from == "slug":
            title = slug
        elif title_from == "heading":
            if doc is None:
                raise ExplorerError(f"{context}: title_from 'heading' requires a Markdown file")
            headings = [block for block in doc.blocks if isinstance(block, Heading) and block.level == 1]
            if not headings or not headings[0].text:
                raise ExplorerError(f"{context}: no level-1 heading to use as the title")
            title = inline_plain(headings[0].text, path, headings[0].line, context)
        else:
            if data is None:
                raise ExplorerError(f"{context}: title_from '{title_from}' requires a TOML file")
            title = dotted(data, title_from[len("toml:"):], path, context)
        if summary_from.startswith("toml:"):
            if data is None:
                raise ExplorerError(f"{context}: summary_from '{summary_from}' requires a TOML file")
            summary = summarize(dotted(data, summary_from[len("toml:"):], path, context))
        else:
            if doc is None:
                raise ExplorerError(f"{context}: summary_from '{summary_from}' requires a Markdown file")
            if summary_from == "first-paragraph":
                paragraph = first_paragraph(doc.blocks)
            else:
                paragraph = section_paragraph(doc, summary_from[len("section:"):])
            if paragraph is None:
                raise ExplorerError(f"{context}: summary_from '{summary_from}' found no paragraph in '{path}'")
            summary = summarize(inline_plain(paragraph.text, path, paragraph.line, context))
        return title, summary

    def _link_tree(self) -> None:
        for node in self.nodes.values():
            if node.parent is not None:
                self.nodes[node.parent].children.append(node.id)
        for node in self.nodes.values():
            node.children.sort(key=lambda child: (self.nodes[child].order, child))
            seen: set[str] = set()
            current: str | None = node.id
            while current is not None:
                if current in seen:
                    raise ExplorerError(f"{MAP_PATH}: parent cycle through '{node.id}'")
                seen.add(current)
                current = self.nodes[current].parent
        for node in self.nodes.values():
            if node.kind == "element" and not node.sources and not node.children:
                raise ExplorerError(f"{MAP_PATH} element '{node.id}': has no sources and no children")
        self.roots = sorted(
            (node.id for node in self.nodes.values() if node.parent is None),
            key=lambda identifier: (self.nodes[identifier].order, identifier),
        )

    def _depth_first(self, identifiers: list[str]) -> None:
        for identifier in identifiers:
            self.order.append(identifier)
            self._depth_first(self.nodes[identifier].children)

    # -- pass 1: excerpts, summaries, heading ids ----------------------------

    def _excerpts_for(self, context: str, sources: list[SourceRef]) -> tuple[list[Excerpt], str | None]:
        """Resolve sources into excerpts; the summary is the first paragraph of a leading Markdown source."""
        excerpts: list[Excerpt] = []
        summary: str | None = None
        used: dict[str, int] = {}
        for position, ref in enumerate(sources):
            source_context = f"{context} source '{ref.label}'"
            if ref.path.endswith(".toml"):
                self.corpus.toml(ref.path, source_context)
                text = read_text(self.repo, ref.path, source_context)
                excerpts.append(Excerpt(ref, "toml", [], 1, text.rstrip("\n"), {}))
                continue
            blocks, base = self.corpus.excerpt(ref, source_context)
            heading_ids: dict[str, str] = {}
            for block in blocks:
                if isinstance(block, Heading):
                    stem = f"s-{block.slug or 'section'}"
                    count = used.get(stem, 0)
                    used[stem] = count + 1
                    heading_ids[block.slug] = stem if count == 0 else f"{stem}-{count + 1}"
            excerpts.append(Excerpt(ref, "markdown", blocks, base, "", heading_ids))
            if position == 0:
                paragraph = first_paragraph(blocks)
                if paragraph is not None:
                    summary = summarize(inline_plain(paragraph.text, ref.path, paragraph.line, source_context))
        return excerpts, summary

    def _assemble(self) -> None:
        for identifier in self.order:
            node = self.nodes[identifier]
            excerpts, summary = self._excerpts_for(f"{node.kind} '{node.id}'", node.sources)
            if node.kind == "element" and summary is not None:
                node.summary = summary
            self.excerpts[identifier] = excerpts

    def _index_links(self) -> None:
        self.whole_file: dict[str, str] = {}
        self.heading_target: dict[tuple[str, str], tuple[str, str]] = {}
        for identifier in self.order:
            for excerpt in self.excerpts[identifier]:
                path = excerpt.ref.path
                if excerpt.kind != "markdown":
                    continue
                if excerpt.ref.heading is None:
                    self.whole_file.setdefault(path, identifier)
                for slug, anchor in excerpt.heading_ids.items():
                    self.heading_target.setdefault((path, slug), (identifier, anchor))

    def _bind_editorial(self) -> dict[str, dict[str, str]]:
        """Resolve every editorial source binding and return its current section digest."""
        digests: dict[str, dict[str, str]] = {}
        for node in sorted(self.ed.values(), key=lambda item: item.id):
            digests[node.id] = {}
            for binding in node.sources:
                digests[node.id][binding.ref.label] = section_digest(
                    self.corpus.section_text(binding.ref, f"{node.label} source '{binding.ref.label}'")
                )
        return digests

    # -- link resolution -----------------------------------------------------

    def page_path(self, identifier: str | None) -> str:
        return "index.html" if identifier is None else f"e/{identifier}/index.html"

    def stage_path(self, identifier: str) -> str:
        return f"lifecycle/{identifier}/index.html"

    def node_page(self, identifier: str) -> str:
        node = self.ed[identifier]
        if node.kind == "overview":
            return "index.html"
        if node.kind == "stage":
            return self.stage_path(identifier)
        if node.kind in ("mechanism", "part"):
            return f"m/{identifier}/index.html"
        return f"t/{identifier}/index.html"

    def relative(self, target: str, page_dir: str) -> str:
        return posixpath.relpath(target, page_dir or ".")

    def resolve(self, source_path: str, destination: str, page_dir: str, where: str) -> tuple[str, bool]:
        if EXTERNAL_RE.match(destination):
            return destination, True
        if SCHEME_RE.match(destination):
            raise ExplorerError(f"{where}: link '{destination}' uses an unsupported scheme")
        path_part, _, fragment = destination.partition("#")
        if "?" in path_part:
            raise ExplorerError(f"{where}: link '{destination}' carries a query string")
        if path_part.startswith("/"):
            raise ExplorerError(f"{where}: link '{destination}' is absolute; use a relative repository path")
        target = source_path if not path_part else posixpath.normpath(posixpath.join(posixpath.dirname(source_path), path_part))
        if target == ".." or target.startswith("../"):
            raise ExplorerError(f"{where}: link '{destination}' escapes the repository")
        if target in self.repo.tracked:
            if target not in self.repo.allowed:
                raise ExplorerError(f"{where}: link '{destination}' targets '{target}', excluded by the public-distribution policy")
            kind = "blob"
        elif target == "." or target in self.repo.directories:
            kind = "tree"
        else:
            raise ExplorerError(
                f"{where}: link '{destination}' targets '{target}', which is not a tracked, publicly distributable file or directory"
            )
        if fragment and kind == "blob" and target.endswith(".md"):
            if fragment not in self.corpus.markdown(target, where).slugs:
                raise ExplorerError(f"{where}: link '{destination}' targets a heading anchor that does not exist in '{target}'")
        if kind == "blob" and target.endswith(".md"):
            if fragment and (target, fragment) in self.heading_target:
                identifier, anchor = self.heading_target[(target, fragment)]
                return f"{self.relative(self.page_path(identifier), page_dir)}#{anchor}", False
            if target in self.whole_file:
                return self.relative(self.page_path(self.whole_file[target]), page_dir), False
        elif kind == "blob" and target in self.whole_file:
            return self.relative(self.page_path(self.whole_file[target]), page_dir), False
        suffix = f"#{fragment}" if fragment else ""
        return f"{REPOSITORY_URL}/{kind}/{self.repo.commit}/{'' if target == '.' else target}{suffix}", True

    # -- navigation tree -------------------------------------------------------

    def _stage_item(self, stage: EdNode) -> TreeItem:
        return TreeItem(
            ("ed", stage.id), stage.title, self.stage_path(stage.id), "stage",
            num=f"{stage.data['order']:02d}", hint="условный" if stage.id in self.conditional else "",
        )

    def _mechanism_item(self, node: EdNode) -> TreeItem:
        item = TreeItem(("ed", node.id), node.title, self.node_page(node.id), node.role)
        item.children = [self._mechanism_item(self.ed[child]) for child in node.data.get("children", [])]
        return item

    def _topic_item(self, node: EdNode) -> TreeItem:
        item = TreeItem(("ed", node.id), node.title, self.node_page(node.id), "artifact")
        item.children = [TreeItem(("ed", child), self.ed[child].title, self.node_page(child), "artifact") for child in node.data.get("children", [])]
        return item

    def _element_item(self, identifier: str) -> TreeItem:
        node = self.nodes[identifier]
        item = TreeItem(("el", identifier), node.title, self.page_path(identifier), "source")
        item.children = [self._element_item(child) for child in node.children]
        return item

    def _build_tree(self) -> TreeItem:
        root = TreeItem(("ed", "overview"), self.overview.title, "index.html", "stage", default_open=True)
        lifecycle = TreeItem(("lifecycle",), "Жизненный цикл", LIFECYCLE_INDEX, "stage", group=True, default_open=True)
        lifecycle.children = [self._stage_item(stage) for stage in self.stages]
        mechanisms = TreeItem(("group", "mechanisms"), "Механизмы", None, "mechanism", group=True, default_open=True)
        mechanisms.children = [self._mechanism_item(node) for node in self.mechanisms]
        topics = TreeItem(("group", "topics"), "Сквозные темы", None, "artifact", group=True)
        topics.children = [self._topic_item(node) for node in self.topics]
        sources = TreeItem(("group", "sources"), "Инженерные источники", None, "source", group=True)
        sources.children = [self._element_item(identifier) for identifier in self.roots]
        coverage = TreeItem(("map",), "Карта покрытия", "map/index.html", "artifact")
        root.children = [lifecycle, mechanisms, topics, sources, coverage]
        return root

    def _tree_html(self, current: tuple, page_dir: str) -> str:
        def path_to(item: TreeItem) -> list[TreeItem] | None:
            if item.key == current:
                return [item]
            for child in item.children:
                found = path_to(child)
                if found is not None:
                    return [item] + found
            return None

        on_path = {item.key for item in (path_to(self.tree) or [])}

        def render(item: TreeItem, depth: int) -> str:
            pad = "  " * depth
            selected = item.key == current
            classes = ["row"] + (["grp"] if item.group else []) + (["sel"] if selected else [])
            inner = ""
            if not item.group:
                inner += '<span class="dot"></span>'
            if item.num:
                inner += f'<span class="num">{esc(item.num)}</span>'
            inner += f'<span class="nm">{esc(item.label)}</span>'
            if item.hint:
                inner += f'<span class="hint">{esc(item.hint)}</span>'
            if item.href is None:
                row = f'<span class="{" ".join(classes)}"{role_style(item.role)}>{inner}</span>'
            else:
                aria = ' aria-current="page"' if selected else ""
                href = esc(self.relative(item.href, page_dir))
                row = f'<a class="{" ".join(classes)}" href="{href}"{role_style(item.role)}{aria}>{inner}</a>'
            if not item.children:
                return f'{pad}<li><div class="line"><span class="chev none" aria-hidden="true"></span>{row}</div></li>'
            opened = " open" if item.key in on_path or item.default_open else ""
            children = "\n".join(render(child, depth + 2) for child in item.children)
            return (
                f'{pad}<li><details{opened}><summary class="line"><span class="chev" aria-hidden="true">▶</span>{row}</summary>\n'
                f"{pad}  <ul>\n{children}\n{pad}  </ul>\n{pad}</details></li>"
            )

        return render(self.tree, 1) + "\n"

    # -- layout ----------------------------------------------------------------

    def _asset_tags(self, page_dir: str) -> tuple[str, str]:
        return self.relative("assets/explorer.css", page_dir), self.relative("assets/explorer.js", page_dir)

    def _legend(self) -> str:
        items = "".join(f'<span{role_style(role)}><i></i>{esc(ROLES[role][0])}</span>' for role in LEGEND_ROLES)
        return f'<div class="legend" role="group" aria-label="Легенда категорий"><span class="lt">ЦВЕТ = РОЛЬ В ПЛАТФОРМЕ</span>{items}</div>'

    def _crumb(self, items: list[tuple[str, str | None]], page_dir: str) -> str:
        parts = []
        for position, (label, target) in enumerate(items):
            last = position == len(items) - 1
            if last:
                parts.append(f'<b aria-current="page">{esc(label)}</b>')
            elif target is None:
                parts.append(f"<span>{esc(label)}</span>")
            else:
                parts.append(f'<a href="{esc(self.relative(target, page_dir))}">{esc(label)}</a>')
        return '<nav class="crumb" aria-label="Где это находится">' + '<span class="sep">/</span>'.join(parts) + "</nav>"

    def _layout(
        self,
        title: str,
        page_dir: str,
        current: tuple,
        crumb: list[tuple[str, str | None]],
        tag: tuple[str, str],
        body: str,
        description: str | None,
    ) -> str:
        styles, scripts = self._asset_tags(page_dir)
        short = self.repo.commit[:7]
        description_tag = f'<meta name="description" content="{esc(description)}">\n' if description else ""
        head = self.overview.data
        dirty = " · с незафиксированными изменениями" if self.repo.dirty else ""
        return (
            "<!doctype html>\n"
            '<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{esc(title)} | {esc(self.title)}</title>\n"
            f"{description_tag}"
            f'<link rel="stylesheet" href="{esc(styles)}">\n'
            f'<script defer src="{esc(scripts)}"></script>\n'
            "</head>\n<body>\n"
            '<a class="skip" href="#content">К содержимому</a>\n'
            '<div class="wrap">\n'
            '<header class="top">\n<div>'
            f'<div class="kicker">{esc(head["kicker"])}</div>'
            f'<h1><a href="{esc(self.relative("index.html", page_dir))}">{esc(head["headline"])}</a></h1>'
            f'<p class="sub">{esc(head["subhead"])}</p></div>\n'
            f"{self._legend()}\n</header>\n"
            '<div class="ide">\n'
            '<nav class="explorer" aria-label="Проводник">'
            '<div class="ex-h"><span>ПРОВОДНИК</span><span data-tree-tools></span></div>'
            f'<div class="tree-scroll"><ul class="tree" id="tree">\n{self._tree_html(current, page_dir)}</ul></div></nav>\n'
            '<main class="view" id="content">\n'
            f'<div class="tabbar">{self._crumb(crumb, page_dir)}<span class="ktag"{role_style(tag[1])}>{esc(tag[0])}</span></div>\n'
            f'<div class="body">\n{body}</div>\n'
            "</main>\n</div>\n"
            f'<footer class="foot"><span>Dev Platform {esc(self.repo.version)} · собрано из коммита '
            f'<a href="{REPOSITORY_URL}/commit/{self.repo.commit}">{short}</a>{dirty}</span>'
            "<span>источники ведут на точный коммит</span></footer>\n"
            "</div>\n</body>\n</html>\n"
        )

    # -- editorial components --------------------------------------------------

    def _prose(self, text: str, *, emphasis: list[str] | None = None, terms: list[EdNode] | None = None, page_dir: str, ctx: str) -> str:
        marks: list[tuple[int, int, str, EdNode | None]] = []
        for phrase in emphasis or []:
            start = text.find(phrase)
            marks.append((start, start + len(phrase), "b", None))
        for term in terms or []:
            start = text.find(term.title)
            marks.append((start, start + len(term.title), "term", term))
        marks.sort(key=lambda mark: mark[0])
        out: list[str] = []
        cursor = 0
        for start, end, kind, term in marks:
            if start < cursor:
                raise ExplorerError(f"{ctx}: emphasis and term markers overlap in '{text[:40]}'")
            if text[:start].count("`") % 2 or text[start:end].count("`"):
                raise ExplorerError(f"{ctx}: a marker cuts through a code span in '{text[:40]}'")
            out.append(inline_code(text[cursor:start]))
            segment = inline_code(text[start:end])
            if kind == "b":
                out.append(f"<b>{segment}</b>")
            else:
                assert term is not None
                href = esc(self.relative(self.node_page(term.id), page_dir))
                tip = esc(term.definition.replace("`", ""))
                out.append(f'<a class="term" href="{href}" data-tip="{tip}">{segment}</a>')
            cursor = end
        out.append(inline_code(text[cursor:]))
        return "".join(out)

    def _node_link(self, identifier: str, page_dir: str) -> str:
        return esc(self.relative(self.node_page(identifier), page_dir))

    def _stale_marker(self, node: EdNode) -> str:
        items = self.stale.get(node.id)
        if not items:
            return ""
        changed = [item.binding.replace("#", " · ", 1) for item in items if item.reason == "changed"]
        unreviewed = [item.binding.replace("#", " · ", 1) for item in items if item.reason == "unreviewed"]
        sentences = []
        if changed:
            noun = "Раздел" if len(changed) == 1 else "Разделы"
            verb = "менялся" if len(changed) == 1 else "менялись"
            listing = ", ".join(f"<code>{esc(name)}</code>" for name in changed)
            sentences.append(f"{noun} {listing} {verb} после последней сверки; пояснение может отставать.")
        if unreviewed:
            listing = ", ".join(f"<code>{esc(name)}</code>" for name in unreviewed)
            sentences.append(f"Ещё не сверено: {listing}.")
        return (
            '<div class="stale" role="note"><span aria-hidden="true">◷</span><span>'
            f'<b>Источник изменился после последней сверки текста.</b> {" ".join(sentences)}</span></div>\n'
        )

    def _tag_label(self, node: EdNode) -> tuple[str, str]:
        if node.kind == "stage":
            return ("условный этап" if node.id in self.conditional else "этап"), ("actor" if node.id in self.conditional else "stage")
        if node.kind == "overview":
            return "обзор", "stage"
        if node.kind == "topic":
            return "сквозная тема", "artifact"
        if node.kind == "term":
            return "термин", "artifact"
        return ROLES[node.role][0], node.role

    def _kind_line(self, node: EdNode) -> str:
        if node.kind == "overview":
            return "обзор · уровень 0"
        if node.kind == "stage":
            return "этап lifecycle"
        if node.kind == "topic":
            return "сквозная тема · уровень 2"
        if node.kind == "term":
            return "термин · уровень 2"
        if node.kind == "mechanism":
            return "механизм · уровень 2"
        return f"{ROLES[node.role][0]} · уровень 2"

    def _card(self, node: EdNode, page_dir: str, *, tag: str | None = None) -> str:
        cond = node.id in self.conditional
        number = f'<span class="num">{node.data["order"]:02d}</span>' if node.kind == "stage" else ""
        label = tag if tag is not None else ""
        badge = f'<span class="s">{esc(label)}</span>' if label else ""
        role = node.role
        return (
            f'<a class="kid{" cond" if cond else ""}" href="{self._node_link(node.id, page_dir)}"{role_style(role)}>'
            f'<div class="n">{number}{esc(node.title)}</div><div class="d">{inline_code(node.definition)}</div>{badge}</a>'
        )

    def _cards(self, nodes: list[EdNode], page_dir: str, *, tags: bool) -> str:
        cards = []
        for node in nodes:
            if tags:
                tag = "УСЛОВНЫЙ ЭТАП" if node.id in self.conditional else (
                    "" if node.kind == "stage" else ROLES[node.role][0].upper() if node.kind in ("mechanism", "part") else ""
                )
            else:
                tag = "УСЛОВНЫЙ ЭТАП" if node.id in self.conditional else ""
            cards.append(self._card(node, page_dir, tag=tag))
        return '<div class="kids">\n' + "\n".join(cards) + "\n</div>\n"

    def _section(self, title: str, count: int | None = None) -> str:
        counter = f' <span class="cnt">· {count}</span>' if count is not None else ""
        return f'<div class="sec">{esc(title)}{counter}</div>\n'

    def _flow_item(self, item: dict, page_dir: str, *, consumer: bool, ctx: str) -> str:
        marker = item.get("consumer" if consumer else "note")
        extra = f'<span class="lk">{esc(marker)}</span>' if marker else ""
        inner = f'<span class="k"></span><span><b>{esc(item["title"])}</b>{inline_code(item["text"])}{extra}</span>'
        style = role_style(item["role"])
        if "node" in item:
            return f'<a class="fitem" href="{self._node_link(item["node"], page_dir)}"{style}>{inner}</a>\n'
        return f'<div class="fitem"{style}>{inner}</div>\n'

    def _three_zones(self, node: EdNode, page_dir: str) -> str:
        data = node.data
        ctx = node.label
        inputs = "".join(self._flow_item(item, page_dir, consumer=False, ctx=ctx) for item in data["inputs"])
        outputs = "".join(self._flow_item(item, page_dir, consumer=True, ctx=ctx) for item in data["outputs"])
        action = data["action"]
        steps = "".join(f"<li>{inline_code(step)}</li>" for step in action["steps"])
        return (
            '<div class="flow">\n'
            f'<div class="fcol"><h4>ОТКУДА ПРИХОДИТ</h4>\n{inputs}</div>\n'
            '<div class="arrow" aria-hidden="true"></div>\n'
            '<div class="fmid"><h4>ЧТО ЗДЕСЬ ПРОИСХОДИТ</h4>\n'
            f'<div class="center"><div class="p">{esc(action["label"])}</div><div class="t">{esc(action["title"])}</div>'
            f"<ol>{steps}</ol></div></div>\n"
            '<div class="arrow" aria-hidden="true"></div>\n'
            f'<div class="fcol"><h4>КУДА ИДЁТ · КТО ИСПОЛЬЗУЕТ</h4>\n{outputs}</div>\n'
            "</div>\n"
        )

    def _forks(self, node: EdNode, page_dir: str) -> str:
        out = []
        for fork in node.data.get("fork", []):
            rows = [
                '<div class="fr fh"><div>НАМЕРЕНИЕ</div><div>КАК РАСПОЗНАЁТСЯ</div><div>ЧТО СОЗДАЁТСЯ</div><div>ЧТО ДАЛЬШЕ</div></div>'
            ]
            for branch in fork["branch"]:
                if "next_node" in branch:
                    follow = f'<a href="{self._node_link(branch["next_node"], page_dir)}">{esc(branch["next"])}</a>'
                else:
                    follow = esc(branch["next"])
                stop = " stop" if branch.get("stop") else ""
                rows.append(
                    f'<div class="fr"{role_style(branch["role"])}>'
                    f'<div class="who"><b>{esc(branch["name"])}</b><code>{esc(branch["code"])}</code></div>'
                    f'<div><span class="fl">КАК РАСПОЗНАЁТСЯ</span>{inline_code(branch["recognized"])}</div>'
                    f'<div><span class="fl">ЧТО СОЗДАЁТСЯ</span>{inline_code(branch["creates"])}</div>'
                    f'<div class="go{stop}"><span class="fl">ЧТО ДАЛЬШЕ</span>{follow}</div></div>'
                )
            note = f'<p class="note">{inline_code(fork["note"])}</p>\n' if "note" in fork else ""
            out.append(self._section(fork["title"]) + '<div class="fork">\n' + "\n".join(rows) + f"\n</div>\n{note}")
        return "".join(out)

    def _paths(self, node: EdNode) -> str:
        title = "Условные и ошибочные пути" if node.kind == "stage" else "Исключения и восстановление"
        cards = "".join(
            f'<div class="path"{role_style(item["role"])}><div class="w">{esc(item["title"])} <span class="tg">{esc(item["tag"])}</span></div>'
            f'{inline_code(item["when"])}<span class="then">{inline_code(item["outcome"])}</span></div>\n'
            for item in node.data["path"]
        )
        return self._section(title) + f'<div class="paths">\n{cards}</div>\n'

    def _example(self, node: EdNode, page_dir: str) -> str:
        example = node.data["example"]
        items = []
        for position, step in enumerate(example["steps"], start=1):
            text, phrases = (step, []) if isinstance(step, str) else (step["text"], step.get("emphasis", []))
            items.append(f"<li>{self._prose(text, emphasis=phrases, page_dir=page_dir, ctx=f'{node.label} example.steps[{position}]')}</li>")
        return self._section(example["title"]) + '<ol class="story">\n' + "\n".join(items) + "\n</ol>\n"

    def _guarantees(self, node: EdNode) -> str:
        if "guarantees" not in node.data:
            return ""
        cards = "".join(f'<div><b>{esc(item["title"])}</b>{inline_code(item["text"])}</div>\n' for item in node.data["guarantees"])
        return self._section("Что гарантирует") + f'<div class="guar">\n{cards}</div>\n'

    def _cycle(self, node: EdNode) -> str:
        if "cycle" not in node.data:
            return ""
        cycle = node.data["cycle"]
        parts = []
        for step in cycle["step"]:
            emphasis = step.get("emphasis")
            state = esc(step["state"])
            classes = "st hl" if emphasis else "st"
            style = role_style(emphasis) if emphasis and emphasis != node.role else ""
            parts.append(f'<div class="{classes}"{style}><code>{state}</code><span>{esc(step["text"])}</span></div>')
            if "arrow" in step:
                parts.append(f'<div class="sa" aria-hidden="true">{esc(step["arrow"])}</div>')
        notes = ""
        if "note" in cycle:
            cards = "".join(
                f'<div{role_style(note["role"])}><b>{esc(note["tag"])}</b>{inline_code(note["text"])}</div>' for note in cycle["note"]
            )
            notes = f'<div class="loopnote">{cards}</div>\n'
        return self._section(cycle["title"]) + f'<div class="loop"{role_style(node.role)}>{"".join(parts)}</div>\n{notes}'

    def _source_url(self, ref: SourceRef) -> str:
        url = f"{REPOSITORY_URL}/blob/{self.repo.commit}/{ref.path}"
        if ref.heading is not None:
            url += f"#{github_slug(ref.heading)}"
        return url

    def _sources_details(self, node: EdNode, page_dir: str) -> str:
        entries = []
        for binding in node.sources:
            caption = binding.ref.heading if binding.ref.heading is not None else ""
            if binding.note:
                caption = f"{caption} · {binding.note}" if caption else binding.note
            note = f"<em>{esc(caption)}</em>" if caption else ""
            entries.append(
                f'<li><a href="{esc(self._source_url(binding.ref))}" target="_blank" rel="noopener noreferrer">'
                f"<code>{esc(binding.ref.path)}</code>{note}</a></li>"
            )
        elements = []
        if node.kind == "stage":
            for target in next(entry for entry in self.map_stages if entry.id == node.id).elements:
                href = esc(self.relative(self.page_path(target), page_dir))
                elements.append(f'<li><a href="{href}"><code>{esc(self.nodes[target].title)}</code><em>страница инженерных источников</em></a></li>')
        total = len(entries) + len(elements)
        return (
            '<details class="src" id="sources"><summary>ИНЖЕНЕРНЫЕ ИСТОЧНИКИ · '
            f'{total} <span>открыть точные правила</span></summary>\n<ul class="srcl">\n' + "\n".join(entries + elements) + "\n</ul></details>\n"
        )

    def _usedin(self, node: EdNode, page_dir: str) -> str:
        if node.kind not in ("mechanism", "part"):
            return ""
        chips = []
        for position, item in enumerate(node.data["used_in"]):
            stage = self.stage_by_id[item["stage"]]
            number = f"{stage.data['order']:02d}"
            label = f"{number} {stage.data['short_title']}: {item['note']}" if "note" in item else f"{number} {stage.title}"
            klass = "" if position == 0 else ' class="sec2"'
            chips.append(f'<a{klass} href="{self._node_link(stage.id, page_dir)}">{esc(label)}</a>')
        return f'<div class="usedin" aria-label="Где используется">{"".join(chips)}</div>\n'

    def _pager(self, node: EdNode, page_dir: str) -> str:
        def link(target: EdNode, caption: str, label: str, css: str = "") -> str:
            klass = f' class="{css}"' if css else ""
            return f'<a{klass} href="{self._node_link(target.id, page_dir)}"><small>{esc(caption)}</small>{esc(label)}</a>'

        placeholder = '<span class="nx" aria-hidden="true"><small>—</small>больше нет</span>'
        if node.kind == "stage":
            order = node.data["order"]
            previous = self.stages[order - 2] if order > 1 else self.overview
            prev_html = (
                link(previous, "← ПРЕДЫДУЩИЙ ЭТАП", f'{previous.data["order"]}. {previous.title}')
                if previous.kind == "stage" else link(previous, "← ВЕСЬ ЦИКЛ", "Обзор Dev Platform")
            )
            following = self.stages[order] if order < len(self.stages) else None
            next_html = (
                link(following, "СЛЕДУЮЩИЙ ЭТАП →", f'{following.data["order"]}. {following.title}', "nx") if following else placeholder
            )
            return f'<nav class="pn" aria-label="Соседние этапы">{prev_html}{next_html}</nav>\n'
        if node.kind in ("mechanism", "part"):
            owner = self.ed[node.parent] if node.parent else None
            if owner is not None:
                prev_html = link(owner, "← МЕХАНИЗМ", owner.title)
                siblings = owner.data["children"]
                index = siblings.index(node.id)
                following = self.ed[siblings[index + 1]] if index + 1 < len(siblings) else None
                next_html = link(following, "СЛЕДУЮЩАЯ ЧАСТЬ →", following.title, "nx") if following else placeholder
            else:
                first = self.stage_by_id[node.data["used_in"][0]["stage"]]
                prev_html = link(first, "← ЭТАП", f'{first.data["order"]}. {first.title}')
                index = self.mechanisms.index(node)
                following = self.mechanisms[index + 1] if index + 1 < len(self.mechanisms) else None
                next_html = link(following, "СЛЕДУЮЩИЙ МЕХАНИЗМ →", following.title, "nx") if following else placeholder
            return f'<nav class="pn" aria-label="Навигация">{prev_html}{next_html}</nav>\n'
        if node.kind in ("topic", "term"):
            if node.kind == "term":
                owner = self.ed[node.parent] if node.parent else None
                prev_html = link(owner, "← ТЕМА", owner.title) if owner else link(self.overview, "← ОБЗОР", "Обзор Dev Platform")
                return f'<nav class="pn" aria-label="Навигация">{prev_html}{placeholder}</nav>\n'
            index = self.topics.index(node)
            previous = self.topics[index - 1] if index > 0 else None
            following = self.topics[index + 1] if index + 1 < len(self.topics) else None
            prev_html = link(previous, "← ПРЕДЫДУЩАЯ ТЕМА", previous.title) if previous else link(self.overview, "← ОБЗОР", "Обзор Dev Platform")
            next_html = link(following, "СЛЕДУЮЩАЯ ТЕМА →", following.title, "nx") if following else placeholder
            return f'<nav class="pn" aria-label="Навигация">{prev_html}{next_html}</nav>\n'
        return ""

    # -- derived relations (never authored twice) -------------------------------

    def _incoming(self, node: EdNode) -> list[tuple[EdNode, str, str]]:
        """Nodes that lead here: (source node, kind of link, explanation)."""
        found: list[tuple[EdNode, str, str]] = []
        for other in sorted(self.ed.values(), key=lambda item: (item.level, item.data.get("order", 0), item.id)):
            if other is node:
                continue
            if other.kind == "stage":
                for item in other.data["transitions"]:
                    if item["to"] == node.id:
                        found.append((other, TRANSITION_TYPES[item["type"]], item["reason"]))
            if other.outline or other.kind in ("overview", "term"):
                continue
            for field in ("outputs", "inputs"):
                for item in other.data.get(field, []):
                    if item.get("node") == node.id and field == "outputs":
                        found.append((other, "выход", item["title"]))
        return found

    def _relations(self, node: EdNode, page_dir: str) -> str:
        """Relations of an outline page: incoming and outgoing transitions, usage and parent."""
        blocks = []
        incoming = self._incoming(node)
        if incoming:
            rows = "".join(
                f'<li><a href="{self._node_link(source.id, page_dir)}">{esc(source.title)}</a> '
                f'<span class="rel">{esc(kind)}</span> {inline_code(why)}</li>\n'
                for source, kind, why in incoming
            )
            blocks.append(self._section("Откуда приходит") + f'<ul class="rels">\n{rows}</ul>\n')
        if node.kind == "stage":
            rows = []
            for item in node.data["transitions"]:
                kind = TRANSITION_TYPES[item["type"]]
                if item["to"] == STOP:
                    target = "стоп"
                else:
                    stage = self.stage_by_id[item["to"]]
                    target = f'<a href="{self._node_link(stage.id, page_dir)}">{stage.data["order"]}. {esc(stage.title)}</a>'
                rows.append(f'<li>{target} <span class="rel">{esc(kind)}</span> {inline_code(item["reason"])}</li>\n')
            blocks.append(self._section("Куда идёт") + f'<ul class="rels">\n{"".join(rows)}</ul>\n')
        return "".join(blocks)

    def _children_section(self, node: EdNode, page_dir: str) -> str:
        ids = node.data.get("children", []) if node.kind in ("stage", "mechanism", "topic") else []
        if not ids:
            return ""
        nodes = [self.ed[identifier] for identifier in ids]
        return self._section("Внутри", len(nodes)) + self._cards(nodes, page_dir, tags=True)

    # -- editorial pages ---------------------------------------------------------

    def _crumb_for(self, node: EdNode) -> list[tuple[str, str | None]]:
        items: list[tuple[str, str | None]] = [(self.overview.title, "index.html")]
        if node.kind == "stage":
            items.append(("Жизненный цикл", LIFECYCLE_INDEX))
            items.append((f"{node.data['order']:02d} · {node.title}", None))
        elif node.kind in ("mechanism", "part"):
            items.append(("Механизмы", None))
            if node.parent:
                owner = self.ed[node.parent]
                items.append((owner.title, self.node_page(owner.id)))
            items.append((node.title, None))
        else:
            items.append(("Сквозные темы", None))
            if node.parent:
                owner = self.ed[node.parent]
                items.append((owner.title, self.node_page(owner.id)))
            items.append((node.title, None))
        return items

    def _title_block(self, node: EdNode) -> str:
        pos = ""
        if node.kind == "stage":
            pos = f'<span class="pos">{node.data["order"]} из {len(self.stages)}</span>'
        return f'<div class="title"><h2>{esc(node.title)}</h2><span class="kind">{esc(self._kind_line(node))}</span>{pos}</div>\n'

    def _page_node(self, node: EdNode) -> tuple[str, str]:
        path = self.node_page(node.id)
        page_dir = posixpath.dirname(path)
        role = node.role
        parts = [f'<section class="node"{role_style(role)}>\n', self._title_block(node), self._stale_marker(node), self._usedin(node, page_dir)]
        if node.outline:
            parts.append(f'<p class="lead">{inline_code(node.definition)}</p>\n')
            parts.append(
                '<div class="stubnote" role="note">Полное описание этого узла ещё не написано: входы, что происходит, выходы, '
                "развилки, пример и исключения появятся, когда узел будет расписан по той же модели. Здесь показаны его определение, "
                "связи и точные источники.</div>\n"
            )
            parts.append(self._relations(node, page_dir))
            parts.append(self._children_section(node, page_dir))
        elif node.kind == "term":
            parts.append(f'<p class="lead">{inline_code(node.definition)}</p>\n')
            users = sorted(
                (other for other in self.ed.values() if node.id in other.data.get("terms", [])),
                key=lambda other: (other.level, other.id),
            )
            if users:
                chips = "".join(f'<a href="{self._node_link(other.id, page_dir)}">{esc(other.title)}</a>' for other in users)
                parts.append(self._section("Где встречается") + f'<div class="usedin">{chips}</div>\n')
        elif node.kind == "topic":
            terms = [self.ed[child] for child in node.data.get("children", [])]
            parts.append(f'<p class="lead">{self._prose(node.data["lead"], page_dir=page_dir, ctx=node.label)}</p>\n')
            parts.append(f'<div class="thesis"><small>ГЛАВНОЕ</small>{self._prose(node.data["thesis"], page_dir=page_dir, ctx=node.label)}</div>\n')
            cards = "".join(f'<div><b>{esc(point["title"])}</b>{inline_code(point["text"])}</div>\n' for point in node.data["points"])
            parts.append(f'<div class="guar">\n{cards}</div>\n')
            if terms:
                parts.append(self._section("Внутри", len(terms)) + self._cards(terms, page_dir, tags=False))
        else:
            terms = [self.ed[identifier] for identifier in node.data.get("terms", [])]
            label = "ЦЕЛЬ ЭТАПА" if node.kind == "stage" else "ГЛАВНОЕ"
            lead = self._prose(node.data["lead"], terms=[t for t in terms if t.title in node.data["lead"]], page_dir=page_dir, ctx=node.label)
            in_thesis = [t for t in terms if t.title not in node.data["lead"]]
            thesis = self._prose(node.data["thesis"], terms=in_thesis, page_dir=page_dir, ctx=node.label)
            parts.append(f'<p class="lead">{lead}</p>\n')
            parts.append(f'<div class="thesis"><small>{label}</small>{thesis}</div>\n')
            parts.append(self._three_zones(node, page_dir))
            parts.append(self._guarantees(node))
            parts.append(self._cycle(node))
            parts.append(self._forks(node, page_dir))
            if node.kind == "stage":
                parts.append(self._paths(node))
                parts.append(self._example(node, page_dir))
            else:
                parts.append(self._example(node, page_dir))
                parts.append(self._paths(node))
            parts.append(self._children_section(node, page_dir))
        parts.append(self._sources_details(node, page_dir))
        parts.append(self._pager(node, page_dir))
        parts.append("</section>\n")
        tag_label, tag_role = self._tag_label(node)
        page = self._layout(
            node.title, page_dir, ("ed", node.id), self._crumb_for(node), (tag_label, tag_role), "".join(parts), node.definition.replace("`", ""),
        )
        return path, page

    def _schema_block(self, page_dir: str) -> str:
        def href_for(identifier: str) -> str:
            return self.relative(self.stage_path(identifier), page_dir)

        svg = render_schema(self.stages, href_for, self.conditional)
        keys = (
            '<div class="keys"><span style="--c:var(--stage)"><i></i>основной путь</span>'
            '<span style="--c:var(--actor)"><i class="d"></i>условный путь</span>'
            '<span style="--c:var(--gate)"><i></i>возврат</span></div>'
        )
        rows = []
        for stage in self.stages:
            notes = []
            for item in stage.data["transitions"]:
                if item["type"] == "main" and item["to"] != STOP and self.stage_by_id[item["to"]].data["order"] == stage.data["order"] + 1:
                    continue
                tone = {"main": "", "conditional": " a", "return": " r"}[item["type"]]
                where = "" if item["to"] == STOP else f' → шаг {self.stage_by_id[item["to"]].data["order"]}'
                notes.append(f'<span class="br{tone}">{inline_code(item["reason"])}{where}</span>')
            cond = " cond" if stage.id in self.conditional else ""
            rows.append(
                f'<li data-n="{stage.data["order"]}" class="{cond.strip()}"><a href="{esc(href_for(stage.id))}">{esc(stage.title)}</a>{"".join(notes)}</li>'
            )
        vertical = '<div class="vflow"><ol>\n' + "\n".join(rows) + "\n</ol></div>\n"
        count = len(self.stages)
        return (
            f'<div class="sec">Жизненный цикл изменения <span class="cnt">· {count} {plural(count, ("этап", "этапа", "этапов"))}</span></div>\n'
            + '<div class="schema" role="group" aria-label="Схема жизненного цикла с условными переходами">\n'
            + svg + "\n" + keys + "</div>\n" + vertical
        )

    def _page_overview(self) -> tuple[str, str]:
        node = self.overview
        data = node.data
        page_dir = ""
        first = self.stages[0]
        scope = (
            '<div class="scope">\n<div class="in"><h4>ЗА ЧТО ОТВЕЧАЕТ</h4><ul>\n'
            + "".join(f"<li>{inline_code(item)}</li>\n" for item in data["responsible"])
            + '</ul></div>\n<div class="out"><h4>ЗА ЧТО НЕ ОТВЕЧАЕТ</h4><ul>\n'
            + "".join(f"<li>{inline_code(item)}</li>\n" for item in data["not_responsible"])
            + "</ul></div>\n</div>\n"
        )
        topics_cards = self._cards(self.topics, page_dir, tags=False)
        stages_cards = self._cards(self.stages, page_dir, tags=False)
        body = (
            f'<section class="node" style="--c:var(--stage)">\n'
            f'<div class="title"><h2>{esc(data["heading"])}</h2><span class="kind">{esc(self._kind_line(node))}</span></div>\n'
            f'{self._stale_marker(node)}'
            f'<p class="lead">{inline_code(data["lead"])}</p>\n'
            f'<div class="thesis"><small>ГЛАВНОЕ</small>{inline_code(data["thesis"])}</div>\n'
            f"{scope}{self._schema_block(page_dir)}"
            f'<p class="note">{inline_code(data["schema_note"])}</p>\n'
            f'<a class="cta" href="{self._node_link(first.id, page_dir)}">{esc(data["cta"])}</a>\n'
            f'{self._section("Этапы", len(self.stages))}{stages_cards}'
            f'{self._section("Сквозные темы", len(self.topics))}{topics_cards}'
            f'{self._sources_details(node, page_dir)}'
            f'<nav class="pn" aria-label="Карта"><a class="nx" href="{esc(self.relative("map/index.html", page_dir))}">'
            "<small>КАРТА ПОКРЫТИЯ →</small>Все узлы, переходы и что обновляется автоматически</a></nav>\n"
            "</section>\n"
        )
        page = self._layout(
            node.title, page_dir, ("ed", "overview"), [(node.title, None)], ("обзор", "stage"), body, node.definition,
        )
        return "index.html", page

    def _page_lifecycle(self) -> tuple[str, str]:
        page_dir = "lifecycle"
        data = self.overview.data
        body = (
            '<section class="node" style="--c:var(--stage)">\n'
            '<div class="title"><h2>Жизненный цикл изменения</h2><span class="kind">схема · уровень 0</span></div>\n'
            f"{self._schema_block(page_dir)}"
            f'<p class="note">{inline_code(data["schema_note"])}</p>\n'
            f'{self._section("Этапы", len(self.stages))}{self._cards(self.stages, page_dir, tags=False)}'
            "</section>\n"
        )
        page = self._layout(
            "Жизненный цикл изменения", page_dir, ("lifecycle",),
            [(self.overview.title, "index.html"), ("Жизненный цикл", None)], ("схема", "stage"), body, data["schema_note"],
        )
        return LIFECYCLE_INDEX, page

    def _where_used(self, node: EdNode) -> str:
        if node.kind == "stage":
            return f"этап {node.data['order']}"
        if node.kind in ("mechanism", "part"):
            numbers = sorted(self.stage_by_id[item["stage"]].data["order"] for item in node.data["used_in"])
            word = "этап" if len(numbers) == 1 else "этапы"
            return f"{word} {', '.join(str(number) for number in numbers)}"
        return "—"

    def _coverage_rows(self) -> list[EdNode]:
        rows: list[EdNode] = [self.overview, *self.stages]
        for mechanism in self.mechanisms:
            rows.append(mechanism)
            rows.extend(self.ed[child] for child in mechanism.data.get("children", []))
        for topic in self.topics:
            rows.append(topic)
            rows.extend(self.ed[child] for child in topic.data.get("children", []))
        return rows

    def _page_map(self) -> tuple[str, str]:
        page_dir = "map"
        data = self.overview.data
        rows = self._coverage_rows()
        outlines = sum(1 for node in rows if node.outline)
        levels = "".join(
            f'<tr><td><b>{esc(row["name"])}</b></td><td>{esc(row["what"])}</td><td>{esc(row["visible"])}</td><td>{esc(row["hidden"])}</td></tr>\n'
            for row in data["level"]
        )
        body_rows = []
        for node in rows:
            kind_label, kind_role = self._tag_label(node)
            status = (
                '<span class="kd" style="--c:var(--actor)">набросок</span>' if node.outline
                else '<span class="kd" style="--c:var(--mech)">полный</span>'
            )
            stale = ' <span class="kd" style="--c:var(--gate)">источник изменился</span>' if node.id in self.stale else ""
            body_rows.append(
                f'<tr><td><a href="{self._node_link(node.id, page_dir)}"><b>{esc(node.title)}</b></a>{stale}</td>'
                f'<td class="kd"{role_style(kind_role)}>{esc(kind_label)} · {node.level}</td>'
                f"<td>{status}</td><td>{inline_code(node.definition)}</td><td>{esc(self._where_used(node))}</td></tr>"
            )
        transitions = []
        for stage in self.stages:
            for item in stage.data["transitions"]:
                if item["to"] == STOP:
                    target = "стоп"
                else:
                    target = str(self.stage_by_id[item["to"]].data["order"])
                tone = {"main": "stage", "conditional": "actor", "return": "gate"}[item["type"]]
                transitions.append(
                    f'<tr><td>{stage.data["order"]} → {esc(target)}</td><td class="kd"{role_style(tone)}>{TRANSITION_TYPES[item["type"]]}</td>'
                    f'<td>{inline_code(item["reason"])}</td></tr>'
                )
        body = (
            '<section class="node" style="--c:var(--artifact)">\n'
            '<div class="title"><h2>Смысловая карта и покрытие</h2><span class="kind">карта · уровни 0–3</span></div>\n'
            '<p class="lead">Карта всех уровней Explorer: что видно с порога, что после одного перехода и что спрятано в технической глубине. '
            "Каждый узел описан один раз и показывается везде, где он участвует: на схеме, на экранах этапов и механизмов.</p>\n"
            f'{self._section("Уровни")}<div class="tw"><table class="tb">\n'
            "<tr><th>УРОВЕНЬ</th><th>ЧТО ЭТО</th><th>ЧТО ВИДНО</th><th>ЧТО СПРЯТАНО ГЛУБЖЕ</th></tr>\n"
            f"{levels}</table></div>\n"
            f'{self._section("Все узлы уровней 0–2", len(rows))}'
            f'<p class="note">Полных узлов: {len(rows) - outlines}. Набросков: {outlines}. '
            "Набросок показывает определение, связи и источники; полное описание появляется по той же модели.</p>\n"
            '<div class="tw"><table class="tb">\n'
            "<tr><th>УЗЕЛ</th><th>ТИП · УРОВЕНЬ</th><th>ГОТОВНОСТЬ</th><th>ОПРЕДЕЛЕНИЕ</th><th>ГДЕ УЧАСТВУЕТ</th></tr>\n"
            + "\n".join(body_rows) + "\n</table></div>\n"
            f'{self._section("Переходы между этапами и их причины")}<div class="tw"><table class="tb">\n'
            "<tr><th>ПЕРЕХОД</th><th>ТИП</th><th>ПОЧЕМУ</th></tr>\n" + "\n".join(transitions) + "\n</table></div>\n"
            f'{self._section("Что обновляется автоматически, а что редакционно")}'
            '<div class="scope">\n<div class="in"><h4>АВТОМАТИЧЕСКИ ИЗ РЕПОЗИТОРИЯ</h4><ul>\n'
            + "".join(f"<li>{inline_code(item)}</li>\n" for item in data["maintenance_auto"])
            + '</ul></div>\n<div class="out" style="--c:var(--actor)"><h4 style="color:var(--actor)">РЕДАКЦИОННО, ТОЧЕЧНО В PR</h4><ul>\n'
            + "".join(f"<li>{inline_code(item)}</li>\n" for item in data["maintenance_editorial"])
            + "</ul></div>\n</div>\n"
            "</section>\n"
        )
        page = self._layout(
            "Смысловая карта и покрытие", page_dir, ("map",),
            [(self.overview.title, "index.html"), ("Смысловая карта", None)], ("карта", "artifact"), body,
            "Все узлы Explorer, их готовность, переходы между этапами и правила обновления.",
        )
        return "map/index.html", page

    # -- engineering-source pages (level 3) ---------------------------------------------

    def incoming(self, identifier: str) -> list[str]:
        return [
            other for other in self.order
            if identifier in self.nodes[other].related and other not in self.nodes[identifier].related
        ]

    def _element_cards(self, identifiers: list[str], page_dir: str) -> str:
        entries = []
        for identifier in identifiers:
            node = self.nodes[identifier]
            href = esc(self.relative(self.page_path(identifier), page_dir))
            summary = f'<div class="d">{esc(node.summary)}</div>' if node.summary else ""
            entries.append(f'<a class="kid" href="{href}" style="--c:var(--src)"><div class="n">{esc(node.title)}</div>{summary}</a>')
        return '<div class="kids">\n' + "\n".join(entries) + "\n</div>\n"

    def _render_element(self, identifier: str) -> tuple[str, str]:
        node = self.nodes[identifier]
        page_dir = f"e/{identifier}"
        parts = [
            '<section class="node" style="--c:var(--src)">\n'
            f'<div class="title"><h2>{esc(node.title)}</h2><span class="kind">инженерный источник · уровень 3</span></div>\n'
        ]
        for excerpt in self.excerpts[identifier]:
            parts.append(self._render_excerpt(f"{node.kind} '{node.id}'", excerpt, page_dir))
        if node.children:
            parts.append(f'<div id="in-this-area">{self._section("В этой области", len(node.children))}{self._element_cards(node.children, page_dir)}</div>\n')
        related = node.related + self.incoming(identifier)
        if related:
            parts.append(f'<div id="related">{self._section("Связанные")}{self._element_cards(related, page_dir)}</div>\n')
        used_in = self.stage_usage.get(identifier, [])
        if used_in:
            entries = []
            for stage in used_in:
                href = esc(self.relative(self.stage_path(stage.id), page_dir))
                entries.append(f'<a href="{href}">Этап {stage.data["order"]}: {esc(stage.title)}</a>')
            parts.append(f'<div id="lifecycle-usage">{self._section("Участвует в этапах жизненного цикла")}<div class="usedin">{"".join(entries)}</div></div>\n')
        if node.sources:
            entries = []
            for ref in node.sources:
                url = f"{REPOSITORY_URL}/blob/{self.repo.commit}/{ref.path}"
                entries.append(f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer"><code>{esc(ref.label)}</code></a></li>')
            parts.append(
                '<details class="src" id="sources" open><summary>ФАЙЛЫ НА ТОЧНОМ КОММИТЕ · '
                f'{len(entries)}</summary>\n<ul class="srcl">\n' + "\n".join(entries) + "\n</ul></details>\n"
            )
        parts.append("</section>\n")
        chain: list[tuple[str, str | None]] = []
        cursor: str | None = identifier
        while cursor is not None:
            chain.append((self.nodes[cursor].title, self.page_path(cursor)))
            cursor = self.nodes[cursor].parent
        chain.reverse()
        crumb = [(self.overview.title, "index.html"), ("Инженерные источники", None), *chain]
        page = self._layout(node.title, page_dir, ("el", identifier), crumb, ("источник", "source"), "".join(parts), node.summary)
        return self.page_path(identifier), page

    def _render_excerpt(self, owner: str, excerpt: Excerpt, page_dir: str) -> str:
        label = esc(excerpt.ref.label)
        if excerpt.kind == "toml":
            return (
                f'<section class="excerpt"><p class="excerpt-source">Из <code>{label}</code></p>\n'
                f'<pre><code class="language-toml">{esc(excerpt.code)}</code></pre></section>\n'
            )
        context = f"{owner} source '{excerpt.ref.label}'"
        renderer = Renderer(self, excerpt, page_dir, context)
        return (
            f'<section class="excerpt"><p class="excerpt-source">Из <code>{label}</code></p>\n'
            f'<div class="prose">\n{renderer.blocks(excerpt.blocks)}</div></section>\n'
        )

    # -- build -----------------------------------------------------------------------------

    def render(self) -> dict[str, bytes]:
        pages: dict[str, str] = {}
        for path, page in (self._page_overview(), self._page_lifecycle(), self._page_map()):
            pages[path] = page
        for node in sorted(self.ed.values(), key=lambda item: item.id):
            if node.kind == "overview":
                continue
            path, page = self._page_node(node)
            pages[path] = page
        for identifier in self.order:
            path, page = self._render_element(identifier)
            pages[path] = page
        outputs = {path: text.encode("utf-8") for path, text in pages.items()}
        outputs.update(self._assets())
        return outputs

    def _assets(self) -> dict[str, bytes]:
        prefix = f"{ASSETS_DIR}/"
        names = sorted(path for path in self.repo.allowed if path.startswith(prefix))
        if not names:
            raise ExplorerError(f"no tracked assets under {ASSETS_DIR}/")
        assets: dict[str, bytes] = {}
        for name in names:
            relative = name[len(prefix):]
            if "/" in relative or not name.endswith(ASSET_SUFFIXES):
                raise ExplorerError(f"asset '{name}' must be a .css or .js file directly under {ASSETS_DIR}/")
            assets[f"assets/{relative}"] = read_text(self.repo, name, "Explorer assets").encode("utf-8")
        for required in ("assets/explorer.css", "assets/explorer.js"):
            if required not in assets:
                raise ExplorerError(f"required asset {ASSETS_DIR}/{required[len('assets/'):]} is missing")
        return assets


def compute_drift(nodes: dict[str, EdNode], digests: dict[str, dict[str, str]], review: dict[str, dict[str, str]]) -> list[Drift]:
    """Compare current section digests with the review record; the result is advisory and never an error."""
    found: list[Drift] = []
    for node in sorted(nodes.values(), key=lambda item: item.id):
        stamps = review.get(node.id, {})
        for binding in node.sources:
            label = binding.ref.label
            if label not in stamps:
                found.append(Drift(node.id, node.title, label, "unreviewed"))
            elif stamps[label] != digests[node.id][label]:
                found.append(Drift(node.id, node.title, label, "changed"))
    for identifier in sorted(review):
        if identifier not in nodes:
            found.extend(Drift(identifier, identifier, label, "obsolete") for label in sorted(review[identifier]))
            continue
        current = {binding.ref.label for binding in nodes[identifier].sources}
        found.extend(Drift(identifier, nodes[identifier].title, label, "obsolete") for label in sorted(set(review[identifier]) - current))
    return found


class Renderer:
    def __init__(self, site: Site, excerpt: Excerpt, page_dir: str, context: str):
        self.site = site
        self.excerpt = excerpt
        self.page_dir = page_dir
        self.context = context
        self.path = excerpt.ref.path

    def fail(self, line: int, reason: str) -> ExplorerError:
        return ExplorerError(f"{self.path}:{line}: unsupported Markdown construct ({reason}) in {self.context}")

    def blocks(self, blocks: list) -> str:
        return "".join(self.block(block) for block in blocks)

    def block(self, block) -> str:
        if isinstance(block, Unsupported):
            raise self.fail(block.line, block.reason)
        if isinstance(block, Heading):
            level = block.level - self.excerpt.base + 2
            if level < 3 or level > 6:
                raise self.fail(block.line, f"heading depth {block.level} cannot be placed beneath the page title")
            anchor = self.excerpt.heading_ids.get(block.slug)
            ident = f' id="{html.escape(anchor)}"' if anchor else ""
            return f"<h{level}{ident}>{self.inline(block.text, block.line)}</h{level}>\n"
        if isinstance(block, Para):
            return f"<p>{self.inline(block.text, block.line)}</p>\n"
        if isinstance(block, Code):
            language = block.info.split()[0] if block.info.strip() else ""
            cls = f' class="language-{html.escape(language, quote=True)}"' if language else ""
            return f"<pre><code{cls}>{html.escape(block.text)}</code></pre>\n"
        if isinstance(block, Rule):
            return "<hr>\n"
        if isinstance(block, Quote):
            inner = self.blocks(block.blocks)
            if block.alert:
                kind = block.alert.lower()
                return (
                    f'<aside class="alert alert-{kind}" role="note"><p class="alert-title">{block.alert.title()}</p>\n'
                    f"{inner}</aside>\n"
                )
            return f"<blockquote>\n{inner}</blockquote>\n"
        if isinstance(block, ListBlock):
            tag = "ol" if block.ordered else "ul"
            start = f' start="{block.start}"' if block.ordered and block.start != 1 else ""
            items = []
            for item in block.items:
                box = ""
                if item.checked is not None:
                    box = f'<input type="checkbox" disabled{" checked" if item.checked else ""}> '
                items.append(f"<li>{box}{self.blocks(item.blocks)}</li>\n")
            return f"<{tag}{start}>\n{''.join(items)}</{tag}>\n"
        if isinstance(block, Table):
            head = "".join(self.cell("th", cell, block.align[index], block.line) for index, cell in enumerate(block.header))
            body = ""
            for row, line in zip(block.rows, block.row_lines, strict=True):
                body += "<tr>" + "".join(self.cell("td", cell, block.align[index], line) for index, cell in enumerate(row)) + "</tr>\n"
            return f"<table>\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}</tbody>\n</table>\n"
        raise AssertionError(f"unhandled block type {type(block).__name__}")

    def cell(self, tag: str, text: str, align: str, line: int) -> str:
        style = f' style="text-align:{align}"' if align else ""
        return f"<{tag}{style}>{self.inline(text, line)}</{tag}>"

    def inline(self, text: str, line: int) -> str:
        try:
            nodes = parse_inline(text)
        except InlineError as exc:
            raise self.fail(line + text.count("\n", 0, exc.offset), exc.reason) from exc
        return self.nodes(nodes, line)

    def nodes(self, nodes: list, line: int) -> str:
        out: list[str] = []
        for node in nodes:
            kind = node[0]
            if kind == "text":
                out.append(html.escape(node[1]))
            elif kind == "code":
                out.append(f"<code>{html.escape(node[1])}</code>")
            elif kind == "br":
                out.append("<br>\n")
            elif kind == "em":
                out.append(f"<em>{self.nodes(node[1], line)}</em>")
            elif kind == "strong":
                out.append(f"<strong>{self.nodes(node[1], line)}</strong>")
            elif kind == "link":
                where = f"{self.path}:{line}: in {self.context}"
                href, external = self.site.resolve(self.path, node[1], self.page_dir, where)
                rel = ' rel="noopener noreferrer"' if external else ""
                out.append(f'<a href="{html.escape(href, quote=True)}"{rel}>{self.nodes(node[2], line)}</a>')
            else:
                raise AssertionError(f"unhandled inline node {kind}")
        return "".join(out)


# ---------------------------------------------------------------------------
# Output scan, build, drift reporting and CLI
# ---------------------------------------------------------------------------


def scan_outputs(outputs: dict[str, bytes]) -> None:
    """Apply the public-distribution owner-reference and secret rules to generated text."""
    findings: list[str] = []
    for path in sorted(outputs):
        try:
            text = outputs[path].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExplorerError(f"generated output '{path}' is not valid UTF-8") from exc
        for match in public_distribution.OWNER_REFERENCE.finditer(text):
            if match.group(0).removesuffix(".git") not in public_distribution.CANONICAL_PRODUCT_REPOSITORIES:
                findings.append(f"{path}: non-canonical owner/project reference")
                break
        for name, pattern in public_distribution.SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path}: possible {name} credential")
    if findings:
        raise ExplorerError(
            "prohibited operator state in generated output; nothing was written:\n  " + "\n  ".join(findings)
        )


def build_site(root: Path) -> tuple[Site, dict[str, bytes]]:
    repo = open_repo(root)
    site = Site(repo)
    outputs = site.render()
    scan_outputs(outputs)
    return site, outputs


def write_outputs(out: Path, outputs: dict[str, bytes]) -> None:
    if out.exists():
        if not out.is_dir():
            raise ExplorerError(f"output path '{out}' exists and is not a directory")
        if any(out.iterdir()):
            raise ExplorerError(f"output directory '{out}' is not empty; remove it or choose a new directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-staging-", dir=out.parent))
    try:
        for path in sorted(outputs):
            destination = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(outputs[path])
        if out.exists():
            out.rmdir()
        staging.rename(out)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def mark_reviewed(site: Site, identifiers: list[str], everything: bool) -> int:
    """Refresh the review record for the named nodes (or all) and return how many nodes were refreshed."""
    if everything == bool(identifiers):
        raise ExplorerError("mark-reviewed needs either node ids or --all, not both and not neither")
    unknown = sorted(set(identifiers) - set(site.ed))
    if unknown:
        raise ExplorerError(f"mark-reviewed: unknown editorial node(s): {', '.join(unknown)}")
    if everything:
        review = {identifier: dict(digests) for identifier, digests in site.digests.items()}
        count = len(review)
    else:
        review = {identifier: dict(bindings) for identifier, bindings in site.review.items()}
        for identifier in identifiers:
            review[identifier] = dict(site.digests[identifier])
        count = len(set(identifiers))
    (site.repo.root / REVIEW_PATH).write_text(render_review(review), encoding="utf-8")
    return count


def git_changed_files(root: Path, base: str) -> list[str]:
    """Files changed since the merge base with ``base``: committed, uncommitted tracked and untracked."""

    def git(*arguments: str) -> str:
        try:
            result = subprocess.run(["git", *arguments], cwd=root, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise ExplorerError(f"git is required to compute the changed files: {exc}") from exc
        if result.returncode != 0:
            raise ExplorerError(f"git {' '.join(arguments)} failed: {result.stderr.strip() or 'no error output'}")
        return result.stdout

    merge_base = git("merge-base", base, "HEAD").strip()
    if not merge_base:
        raise ExplorerError(f"cannot resolve a merge base between '{base}' and HEAD")
    changed = set(git("diff", "--name-only", merge_base).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(path for path in changed if path)


def filter_drift(items: list[Drift], changed_files: list[str] | None) -> list[Drift]:
    """Keep drift for bindings in ``changed_files``; ``None`` means no filter."""
    if changed_files is None:
        return items
    wanted = set(changed_files)
    return [item for item in items if item.binding.partition("#")[0] in wanted]


def github_escape(text: str, *, prop: bool = False) -> str:
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def report_drift_github(items: list[Drift]) -> None:
    """Emit non-failing workflow annotations and a job summary for the drift list."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        raise ExplorerError("drift --github requires the GITHUB_STEP_SUMMARY environment variable")
    for item in items:
        print(f"::warning title={github_escape('Explorer editorial drift', prop=True)}::{github_escape(item.message())}")
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("### Explorer editorial drift\n\n" + drift_markdown(items) + "\n")
        if items:
            handle.write(
                "Update the explanation if needed, then run "
                "`python3 scripts/build_explorer.py mark-reviewed <node-id>`. This never blocks the pull request.\n"
            )


def issue_body(items: list[Drift]) -> str:
    lines = [
        "Эти узлы Explorer ссылаются на канонические разделы, которые изменились после последней сверки текста.",
        "Проверьте пояснение, при необходимости поправьте узел в `explorer/nodes/` и выполните "
        "`python3 scripts/build_explorer.py mark-reviewed <узел>`. Задача открывается и закрывается автоматически и ничего не блокирует.",
        "",
        drift_markdown(items).rstrip(),
        "",
    ]
    return "\n".join(lines)


def run_gh(arguments: list[str], *, stdin: str | None = None) -> str:
    try:
        result = subprocess.run(["gh", *arguments], capture_output=True, text=True, check=False, input=stdin)
    except OSError as exc:
        raise ExplorerError(f"the GitHub CLI 'gh' is required for drift-issue: {exc}") from exc
    if result.returncode != 0:
        raise ExplorerError(f"gh {' '.join(arguments[:2])} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def sync_drift_issue(items: list[Drift], repository: str, gh=run_gh) -> str:
    """Create, update or close the single open drift issue; return what was done."""
    raw = gh([
        "issue", "list", "--repo", repository, "--label", ISSUE_LABEL, "--state", "open",
        "--json", "number,body", "--limit", "100",
    ])
    try:
        listing = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExplorerError(f"gh issue list returned output that is not JSON: {exc}") from exc
    if not isinstance(listing, list) or not all(isinstance(entry, dict) and "number" in entry and "body" in entry for entry in listing):
        raise ExplorerError("gh issue list did not return a JSON list of issues with 'number' and 'body'")
    if len(listing) > 1:
        numbers = ", ".join(str(entry["number"]) for entry in listing)
        raise ExplorerError(f"more than one open '{ISSUE_LABEL}' issue exists ({numbers}); close the extras so exactly one remains")
    if not items:
        if not listing:
            return "no stale nodes and no open drift issue"
        number = str(listing[0]["number"])
        gh(["issue", "close", number, "--repo", repository, "--comment", "Все узлы Explorer сверены с источниками; задача закрыта автоматически."])
        return f"closed issue {number}"
    body = issue_body(items)
    if listing:
        number = str(listing[0]["number"])
        if listing[0]["body"].replace("\r\n", "\n").strip() == body.strip():
            return f"issue {number} is already current"
        gh(["issue", "edit", number, "--repo", repository, "--title", ISSUE_TITLE, "--body", body])
        return f"updated issue {number}"
    gh(["label", "create", ISSUE_LABEL, "--repo", repository, "--description", ISSUE_LABEL_DESCRIPTION, "--color", "FBCA04", "--force"])
    gh(["issue", "create", "--repo", repository, "--title", ISSUE_TITLE, "--label", ISSUE_LABEL, "--body", body])
    return "created the drift issue"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check the static Dev Platform Explorer.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository checkout to read (default: this checkout).")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Generate the static site.")
    build.add_argument("--out", type=Path, required=True, help="Output directory (must not exist or be empty).")
    commands.add_parser("check", help="Validate the map, editorial nodes, sources and generated output without writing.")
    drift = commands.add_parser("drift", help="List editorial nodes whose bound sources changed since their last review (never fails).")
    drift.add_argument("--github", action="store_true", help="Emit ::warning:: annotations and append a job summary.")
    drift.add_argument("--changed-file", action="append", default=[], help="Only report drift for bindings in these files.")
    drift.add_argument("--base", help="Only report drift for bindings in files changed since the merge base with this git ref.")
    marker = commands.add_parser("mark-reviewed", help="Record that the named nodes were reviewed against their current sources.")
    marker.add_argument("nodes", nargs="*", help="Editorial node ids.")
    marker.add_argument("--all", action="store_true", dest="everything", help="Refresh every node and drop obsolete records.")
    commands.add_parser("drift-issue", help="Create, update or close the single GitHub issue that lists stale nodes (needs gh).")
    args = parser.parse_args(argv)
    try:
        site, outputs = build_site(args.root)
        if args.command == "build":
            write_outputs(args.out, outputs)
        elif args.command == "mark-reviewed":
            count = mark_reviewed(site, args.nodes, args.everything)
            print(f"explorer marked {count} editorial node(s) reviewed")
            return 0
        elif args.command == "drift":
            changed = None
            if args.changed_file or args.base is not None:
                changed = list(args.changed_file)
                if args.base is not None:
                    changed += git_changed_files(site.repo.root, args.base)
            items = filter_drift(site.drift, changed)
            if args.github:
                report_drift_github(items)
            for item in items:
                print(f"warning: {item.message()}")
            return 0
        elif args.command == "drift-issue":
            repository = os.environ.get("GITHUB_REPOSITORY")
            if not repository:
                raise ExplorerError("drift-issue requires the GITHUB_REPOSITORY environment variable")
            if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
                raise ExplorerError("drift-issue requires GH_TOKEN (or GITHUB_TOKEN) for the GitHub CLI")
            print(f"explorer drift issue: {sync_drift_issue(site.drift, repository)}")
            return 0
    except ExplorerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for item in site.drift:
        print(f"warning: {item.message()}", file=sys.stderr)
    pages = sum(1 for path in outputs if path.endswith(".html"))
    verb = "built" if args.command == "build" else "checked"
    print(
        f"explorer {verb}: {pages} pages, {len(site.nodes)} elements, {len(site.ed)} editorial nodes, "
        f"{len(site.stages)} lifecycle stages at commit {site.repo.commit[:7]}"
        + (f"; {len(site.drift)} editorial drift warning(s)" if site.drift else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
