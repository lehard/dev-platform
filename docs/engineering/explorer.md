# Platform Explorer

The Explorer is a browsable static view of Dev Platform. It is generated at build time from canonical, git-tracked repository files; it is not a second documentation system. A reader gets a navigation tree beside the content, where each element sits in the platform, related elements, and links to the exact source files at the built commit.

## Commands

```bash
python3 scripts/build_explorer.py check
python3 scripts/build_explorer.py build --out build/explorer
```

`check` validates the map, every source reference, every link and the generated output without writing anything. `build` does the same and then writes the site. Both exit non-zero with a message naming the element and source that failed. `build --out` refuses a non-empty output directory and never deletes anything. `build/` is git-ignored.

The generator uses only the Python standard library and has no Node toolchain, framework or runtime dependency.

## What the map owns

`explorer/map.toml` owns structure only: element identity, title, hierarchy, order, relations and source references. It has no prose fields; the loader rejects unknown keys, so explanatory text cannot be added there. Every explanation shown on a page is rendered from the referenced source file.

- `[site]` gives the site `title`.
- `[[element]]` declares `id`, `title`, `order`, and optionally `parent`, `sources` and `related`. An element with no children must have at least one source.
- `[[collection]]` enumerates tracked files by `glob` (`*` and `?` stay within one path segment; `**` is rejected) so new OpenSpec capabilities, optional engineering capability descriptors and decision records appear without editing the map. `title_from` is `heading`, `slug` or `toml:<key>`; `summary_from` is `first-paragraph`, `section:<Heading>` or `toml:<key>`; `slug_from` is `stem` or `parent`; optional `companions` name extra files per item through `{stem}` and `{slug}` templates.

A source reference is `path` or `path#Heading`. The excerpt is the heading section up to the next heading of the same or higher level, or the whole file (without its level-1 heading) when no heading is given. A heading must match exactly once. Duplicate ids, parent cycles, dangling `parent` or `related` ids, a collection that matches nothing, and a source that is missing, untracked or excluded by the public-distribution policy all fail the build.

## How sources are rendered

A small built-in renderer supports the constructs present in the sources: headings, paragraphs, ordered and unordered lists including task items, fenced code, tables, inline code, emphasis, links, block quotes and GitHub alert markers. It fails closed. An unsupported construct inside an included excerpt (raw HTML, images, setext headings, indented code blocks, reference-style links, strikethrough, character references, ragged tables and similar) fails the build with the file and line; it is never dropped or shown as raw text. Constructs outside the included excerpt do not matter. When a source legitimately needs a new construct, extend the renderer and its tests instead of rewording the source around the limit.

Relative links to repository files become links to the matching Explorer element when one shows that file (or that heading), otherwise to the file or directory at the built commit. A link to a missing, untracked or excluded path, or to a heading anchor that does not exist, fails the build.

## Pages, links and offline use

`index.html` lists the top-level areas. Each element and enumerated item has one page at `e/<id>/index.html`. All internal links and assets are relative, so the site works from a project-site subpath or from the file system, and each page works without JavaScript; `assets/explorer.js` only keeps the selected navigation entry in view. Every page shows the navigation tree with the selected element marked, the parent chain, the rendered excerpts, related elements (declared relations and their back links), links to the source files at the built commit, and the platform `VERSION` and short commit in the footer.

## Determinism and public safety

Output has no timestamps or absolute paths and uses declared order, then id, so identical inputs produce byte-identical output. The commit comes from `git rev-parse HEAD` and sources come from `git ls-files` minus the public-distribution exclusions; running outside a git checkout is an explicit error rather than a filesystem walk. Sources are read from the working tree, so when tracked files differ from `HEAD` every page footer says the commit is shown "with uncommitted changes"; build from a clean checkout when the stamped commit must describe the content exactly. `build --out` writes into a sibling staging directory and renames it into place, so a failed write leaves no partial site.

Before anything is written, every generated file is scanned with the owner-reference and secret rules of `scripts/public_distribution.py`. A finding aborts the build with the generated path and the reason, without echoing the matched value, and writes nothing.

## Ownership and downstream boundary

The Explorer is platform-owned and is not distributed. Its map, assets, build entrypoint and generated output live outside `template/`, so a rendered project receives none of them, and `tests/test_build_explorer.py` renders a project and fails if any Explorer artifact appears or if one is placed under `template/`. See [ownership.md](../ownership.md).

## Verification

`tests/test_build_explorer.py` covers map validation, collection discovery, determinism, unsupported constructs, prohibited-state rejection, relative links under a subpath, and the downstream boundary. It also builds the committed map against the committed sources, so renaming a heading the map uses fails CI until the map is updated.
