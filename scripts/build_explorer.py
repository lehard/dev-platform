#!/usr/bin/env python3
"""Build the static Dev Platform Explorer from canonical repository sources.

The Explorer is a build-time *view* of git-tracked repository files, not a
second documentation system. ``explorer/map.toml`` owns structure only (ids,
titles, hierarchy, order, relations and source references); every explanation
is rendered from the referenced source file and heading. Contract:
docs/engineering/explorer.md.

Failure model: there are no defaults that mask a missing input and no degraded
rendering mode. A missing or untracked source, a missing heading, an
unsupported Markdown construct in an included excerpt, a dangling link or
relation, prohibited operator state in the generated output, or running
outside a git checkout aborts with a message naming what failed, and nothing
is written.
"""
from __future__ import annotations

import argparse
import dataclasses
import html
import posixpath
import re
import subprocess
import sys
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
    return Repo(root, tracked, allowed, frozenset(directories), commit, version)


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
LINK_DESTINATION_RE = re.compile(r"""^\s*(<[^<>\s]*>|[^\s<>]*)(?:\s+(?:"[^"]*"|'[^']*'))?\s*$""")
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
SITE_REQUIRED = {"title"}
TOP_LEVEL = {"site", "element", "collection"}
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


def parse_source_ref(raw: str, context: str) -> SourceRef:
    path, separator, heading = raw.partition("#")
    if not path or path.startswith("/") or posixpath.normpath(path) != path or path.startswith("../") or path == "..":
        raise ExplorerError(f"{context}: source reference '{raw}' must be a normalized repository-relative path")
    if separator and not heading.strip():
        raise ExplorerError(f"{context}: source reference '{raw}' has an empty heading")
    return SourceRef(path, heading if separator else None)


def load_map(repo: Repo) -> tuple[str, list[Node], list[Node]]:
    """Load and strictly validate the structure-only map; return (title, elements, collections)."""
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
    return title, elements, collections


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


class Site:
    def __init__(self, repo: Repo):
        self.repo = repo
        self.corpus = Corpus(repo)
        self.title, elements, collections = load_map(repo)
        self.nodes: dict[str, Node] = {}
        self._register(elements, collections)
        self._link_tree()
        self.order: list[str] = []
        self._depth_first(self.roots)
        self.excerpts: dict[str, list[Excerpt]] = {}
        self._assemble()
        self._index_links()

    # -- structure ---------------------------------------------------------

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

    def _assemble(self) -> None:
        for identifier in self.order:
            node = self.nodes[identifier]
            context = f"{node.kind} '{node.id}'"
            excerpts: list[Excerpt] = []
            used: dict[str, int] = {}
            for position, ref in enumerate(node.sources):
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
                if position == 0 and node.kind == "element":
                    paragraph = first_paragraph(blocks)
                    if paragraph is not None:
                        node.summary = summarize(inline_plain(paragraph.text, ref.path, paragraph.line, source_context))
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

    # -- link resolution -----------------------------------------------------

    def page_path(self, identifier: str | None) -> str:
        return "index.html" if identifier is None else f"e/{identifier}/index.html"

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

    # -- rendering -----------------------------------------------------------

    def render(self) -> dict[str, bytes]:
        pages: dict[str, str] = {"index.html": self._render_index()}
        for identifier in self.order:
            pages[self.page_path(identifier)] = self._render_node(identifier)
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

    def _asset_tags(self, page_dir: str) -> tuple[str, str]:
        styles = self.relative("assets/explorer.css", page_dir)
        scripts = self.relative("assets/explorer.js", page_dir)
        return styles, scripts

    def _layout(self, title: str, page_dir: str, identifier: str | None, body: str, description: str | None) -> str:
        styles, scripts = self._asset_tags(page_dir)
        home = self.relative("index.html", page_dir)
        short = self.repo.commit[:7]
        description_tag = f'<meta name="description" content="{html.escape(description, quote=True)}">\n' if description else ""
        return (
            "<!doctype html>\n"
            '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)} | {html.escape(self.title)}</title>\n"
            f"{description_tag}"
            f'<link rel="stylesheet" href="{html.escape(styles)}">\n'
            f'<script defer src="{html.escape(scripts)}"></script>\n'
            "</head>\n<body>\n"
            '<a class="skip" href="#content">Skip to content</a>\n'
            f'<header class="site-header"><a href="{html.escape(home)}">{html.escape(self.title)}</a></header>\n'
            '<div class="layout">\n'
            f'<nav class="tree" aria-label="Platform map">\n{self._nav(identifier, page_dir)}</nav>\n'
            f'<main id="content">\n{body}</main>\n'
            "</div>\n"
            '<footer class="site-footer">'
            f"Dev Platform {html.escape(self.repo.version)} &middot; built from commit "
            f'<a href="{REPOSITORY_URL}/commit/{self.repo.commit}">{short}</a>'
            "</footer>\n</body>\n</html>\n"
        )

    def _nav(self, current: str | None, page_dir: str) -> str:
        ancestors: set[str] = set()
        cursor = current
        while cursor is not None:
            ancestors.add(cursor)
            cursor = self.nodes[cursor].parent

        def branch(identifiers: list[str], depth: int) -> str:
            pad = "  " * depth
            lines = [f"{pad}<ul>"]
            for identifier in identifiers:
                node = self.nodes[identifier]
                href = html.escape(self.relative(self.page_path(identifier), page_dir))
                aria = ' aria-current="page"' if identifier == current else ""
                link = f'<a href="{href}"{aria}>{html.escape(node.title)}</a>'
                if node.children:
                    opened = " open" if identifier in ancestors else ""
                    lines.append(f"{pad}  <li><details{opened}><summary>{link}</summary>")
                    lines.append(branch(node.children, depth + 2))
                    lines.append(f"{pad}  </details></li>")
                else:
                    lines.append(f"{pad}  <li>{link}</li>")
            lines.append(f"{pad}</ul>")
            return "\n".join(lines)

        return branch(self.roots, 1) + "\n"

    def _child_list(self, identifiers: list[str], page_dir: str) -> str:
        entries = []
        for identifier in identifiers:
            node = self.nodes[identifier]
            href = html.escape(self.relative(self.page_path(identifier), page_dir))
            summary = f" <span class=\"summary\">{html.escape(node.summary)}</span>" if node.summary else ""
            entries.append(f'<li><a href="{href}">{html.escape(node.title)}</a>{summary}</li>')
        return '<ul class="cards">\n' + "\n".join(entries) + "\n</ul>\n"

    def _render_index(self) -> str:
        body = (
            f"<h1>{html.escape(self.title)}</h1>\n"
            '<section id="in-this-area">\n<h2>Platform areas</h2>\n'
            f"{self._child_list(self.roots, '')}</section>\n"
        )
        return self._layout("Overview", "", None, body, None)

    def incoming(self, identifier: str) -> list[str]:
        return [
            other for other in self.order
            if identifier in self.nodes[other].related and other not in self.nodes[identifier].related
        ]

    def _render_node(self, identifier: str) -> str:
        node = self.nodes[identifier]
        page_dir = f"e/{identifier}"
        parts = [f"{self._breadcrumb(identifier, page_dir)}<h1>{html.escape(node.title)}</h1>\n"]
        for excerpt in self.excerpts[identifier]:
            parts.append(self._render_excerpt(node, excerpt, page_dir))
        if node.children:
            parts.append(
                '<section id="in-this-area">\n<h2>In this area</h2>\n'
                f"{self._child_list(node.children, page_dir)}</section>\n"
            )
        related = node.related + self.incoming(identifier)
        if related:
            parts.append(f'<section id="related">\n<h2>Related</h2>\n{self._child_list(related, page_dir)}</section>\n')
        if node.sources:
            entries = []
            for ref in node.sources:
                url = f"{REPOSITORY_URL}/blob/{self.repo.commit}/{ref.path}"
                entries.append(f'<li><a href="{html.escape(url)}" rel="noopener noreferrer"><code>{html.escape(ref.label)}</code></a></li>')
            parts.append(
                '<section id="sources">\n<h2>Sources</h2>\n<ul>\n' + "\n".join(entries) + "\n</ul>\n</section>\n"
            )
        description = node.summary
        return self._layout(node.title, page_dir, identifier, "".join(parts), description)

    def _breadcrumb(self, identifier: str, page_dir: str) -> str:
        chain: list[str] = []
        cursor: str | None = identifier
        while cursor is not None:
            chain.append(cursor)
            cursor = self.nodes[cursor].parent
        chain.reverse()
        items = [f'<li><a href="{html.escape(self.relative("index.html", page_dir))}">{html.escape(self.title)}</a></li>']
        for position, ancestor in enumerate(chain):
            title = html.escape(self.nodes[ancestor].title)
            if position == len(chain) - 1:
                items.append(f'<li aria-current="page">{title}</li>')
            else:
                href = html.escape(self.relative(self.page_path(ancestor), page_dir))
                items.append(f'<li><a href="{href}">{title}</a></li>')
        return '<nav class="breadcrumb" aria-label="Where it fits"><ol>' + "".join(items) + "</ol></nav>\n"

    def _render_excerpt(self, node: Node, excerpt: Excerpt, page_dir: str) -> str:
        label = html.escape(excerpt.ref.label)
        if excerpt.kind == "toml":
            return (
                f'<section class="excerpt"><p class="excerpt-source">From <code>{label}</code></p>\n'
                f'<pre><code class="language-toml">{html.escape(excerpt.code)}</code></pre></section>\n'
            )
        context = f"{node.kind} '{node.id}' source '{excerpt.ref.label}'"
        renderer = Renderer(self, excerpt, page_dir, context)
        return (
            f'<section class="excerpt"><p class="excerpt-source">From <code>{label}</code></p>\n'
            f'<div class="prose">\n{renderer.blocks(excerpt.blocks)}</div></section>\n'
        )


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
            level = block.level - self.excerpt.base + 1
            if level < 2 or level > 6:
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
# Output scan, build and CLI
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
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(outputs):
        destination = out / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(outputs[path])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check the static Dev Platform Explorer.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository checkout to read (default: this checkout).")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Generate the static site.")
    build.add_argument("--out", type=Path, required=True, help="Output directory (must not exist or be empty).")
    commands.add_parser("check", help="Validate the map, sources and generated output without writing.")
    args = parser.parse_args(argv)
    try:
        site, outputs = build_site(args.root)
        if args.command == "build":
            write_outputs(args.out, outputs)
    except ExplorerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    pages = sum(1 for path in outputs if path.endswith(".html"))
    verb = "built" if args.command == "build" else "checked"
    print(f"explorer {verb}: {pages} pages, {len(site.nodes)} elements at commit {site.repo.commit[:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
