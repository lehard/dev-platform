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

`explorer/map.toml` owns structure only: element identity, title, hierarchy, order, relations, lifecycle stage order and element links, and source references. It has no prose fields; the loader rejects unknown keys, so explanatory text cannot be added there. Every explanation shown on a page is rendered from the referenced source file.

- `[site]` gives the site `title`.
- `[[element]]` declares `id`, `title`, `order`, and optionally `parent`, `sources` and `related`. An element with no children must have at least one source.
- `[[collection]]` enumerates tracked files by `glob` (`*` and `?` stay within one path segment; `**` is rejected) so new OpenSpec capabilities, optional engineering capability descriptors and decision records appear without editing the map. `title_from` is `heading`, `slug` or `toml:<key>`; `summary_from` is `first-paragraph`, `section:<Heading>` or `toml:<key>`; `slug_from` is `stem` or `parent`; optional `companions` name extra files per item through `{stem}` and `{slug}` templates.
- `[[stage]]` declares one step of the lifecycle journey (see below) with `id`, `title`, `order`, `elements` and `sources`, all required.

A source reference is `path` or `path#Heading`. The excerpt is the heading section up to the next heading of the same or higher level, or the whole file (without its level-1 heading) when no heading is given. A heading must match exactly once. Duplicate ids, parent cycles, dangling `parent` or `related` ids, a collection that matches nothing, and a source that is missing, untracked or excluded by the public-distribution policy all fail the build.

## Lifecycle journey

The ordered `[[stage]]` entries present how a change moves through the platform, from requirement and intent through specification, routing, isolated implementation, verification, publication and integration, release and rollout, to feedback and learning. A stage declares:

- `id`: lowercase kebab-case and unique among stages. Stage pages live under `lifecycle/`, so a stage id may equal an element id.
- `title` and `order`: `order` is a positive integer, unique, and the stages must run contiguously from 1 without gaps. The order in the file does not matter; `order` decides the sequence.
- `elements`: a non-empty list of existing element, collection or enumerated item ids that the stage involves, each listed at most once.
- `sources`: a non-empty list of source references with the same resolution rules as element sources.

A stage carries no prose and the loader rejects unknown keys, so explanations cannot be added to the map. Everything a stage page explains is the rendered excerpt of its sources, so the lifecycle description cannot drift from the canonical documents: renaming a referenced heading fails the build until the map is updated. At least one `[[stage]]` is required. A duplicate id, a duplicate or gapped order, an unknown element, a source that is missing, untracked, excluded by the public-distribution policy or has no matching heading, and an unsupported construct or dangling link in a stage excerpt all fail `check` and `build` with a message naming the stage, and nothing is written.

The generated pages are:

- `lifecycle/index.html`: the overview, an ordered list of every stage as numbered connected steps with a one-line summary taken from the first paragraph of the stage's first source. The home page shows the same flow.
- `lifecycle/<stage-id>/index.html`: the stage position, the rendered source excerpts, the component elements it involves with their titles and summaries, the source files at the built commit, and previous, next and "All stages" navigation. The first stage has no previous link and the last has no next link.

The navigation tree gains a "Lifecycle" branch that lists the numbered stages in order and marks the current page. Each component page lists the stages that name it under "Used in lifecycle stages"; that relation is derived from the stage `elements`, so it is authored once. The flow is an ordered list in semantic HTML and CSS with no diagram library or script: it is a grid of connected steps on wide screens and stacks vertically on narrow ones. Lifecycle pages use only relative links and are deterministic like all other pages.

## How sources are rendered

A small built-in renderer supports the constructs present in the sources: headings, paragraphs, ordered and unordered lists including task items, fenced code, tables, inline code, emphasis, links, block quotes and GitHub alert markers. It fails closed. An unsupported construct inside an included excerpt (raw HTML, images, setext headings, indented code blocks, reference-style links, strikethrough, character references, ragged tables and similar) fails the build with the file and line; it is never dropped or shown as raw text. Constructs outside the included excerpt do not matter. When a source legitimately needs a new construct, extend the renderer and its tests instead of rewording the source around the limit.

Relative links to repository files become links to the matching Explorer element when one shows that file (or that heading), otherwise to the file or directory at the built commit. A link to a missing, untracked or excluded path, or to a heading anchor that does not exist, fails the build.

## Pages, links and offline use

`index.html` shows the lifecycle flow and lists the top-level areas. Each element and enumerated item has one page at `e/<id>/index.html`; the lifecycle pages are described above. All internal links and assets are relative, so the site works from a project-site subpath or from the file system, and each page works without JavaScript; `assets/explorer.js` only keeps the selected navigation entry in view. Every page shows the navigation tree with the selected element marked, the parent chain, the rendered excerpts, related elements (declared relations and their back links), the lifecycle stages that involve it, links to the source files at the built commit, and the platform `VERSION` and short commit in the footer.

## Determinism and public safety

Output has no timestamps or absolute paths and uses declared order, then id, so identical inputs produce byte-identical output. The commit comes from `git rev-parse HEAD` and sources come from `git ls-files` minus the public-distribution exclusions; running outside a git checkout is an explicit error rather than a filesystem walk. Sources are read from the working tree, so when tracked files differ from `HEAD` every page footer says the commit is shown "with uncommitted changes"; build from a clean checkout when the stamped commit must describe the content exactly. `build --out` writes into a sibling staging directory and renames it into place, so a failed write leaves no partial site.

Before anything is written, every generated file is scanned with the owner-reference and secret rules of `scripts/public_distribution.py`. A finding aborts the build with the generated path and the reason, without echoing the matched value, and writes nothing.

## Ownership and downstream boundary

The Explorer is platform-owned and is not distributed. Its map, assets, build entrypoint and generated output live outside `template/`, so a rendered project receives none of them, and `tests/test_build_explorer.py` renders a project and fails if any Explorer artifact appears or if one is placed under `template/`. See [ownership.md](../ownership.md).

## Verification

`tests/test_build_explorer.py` covers map validation, stage validation and ordering, lifecycle pages and cross-links, collection discovery, determinism, unsupported constructs, prohibited-state rejection, relative links under a subpath, and the downstream boundary. It also builds the committed map against the committed sources, so renaming a heading the map uses fails CI until the map is updated.
