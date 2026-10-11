# Platform Explorer

The Explorer is a browsable static view of Dev Platform for a reader who does not know the repository. It has two layers. The **editorial layer** is one Russian explanation per semantic node (overview, lifecycle stage, mechanism, mechanism part, cross-cutting topic, glossary term), written for the reader and bound to the canonical sources it explains. The **engineering-source layer** is generated from allowlisted, git-tracked canonical files and is reachable from a node only through an explicit step. Neither layer is a second documentation system: the editorial layer is explanatory only and never defines a rule; normative rules stay in `AGENTS.md`, OpenSpec specifications and `docs/`.

## Commands

```bash
python3 scripts/build_explorer.py check
python3 scripts/build_explorer.py build --out build/explorer
python3 scripts/build_explorer.py drift [--changed-file PATH ...]
python3 scripts/build_explorer.py mark-reviewed <node-id> ...
python3 scripts/build_explorer.py mark-reviewed --all
python3 scripts/build_explorer.py drift-issue
```

`check` validates the map, every editorial node, every source reference, every link and the generated output without writing anything. `build` does the same and then writes the site. Both exit non-zero with a message naming the node (or element) and the field or source that failed. `build --out` refuses a non-empty output directory and never deletes anything. `build/` is git-ignored. `drift`, `mark-reviewed` and `drift-issue` are described under "Editorial drift". The generator uses only the Python standard library and has no Node toolchain, framework, CDN or remote font.

## Levels

- **Level 0, overview** (`index.html`): purpose, boundaries of responsibility, the lifecycle schema with main, conditional and return transitions, the entry "Пройти жизненный цикл", the stages and the cross-cutting topics.
- **Level 1, lifecycle stage** (`lifecycle/<stage-id>/`): the purpose, what comes in, what happens, what goes out and who uses it, forks, conditional and error paths, an example and the mechanisms inside.
- **Level 2, mechanism, part, topic, term** (`m/<id>/` for mechanisms and parts, `t/<id>/` for topics and terms): the stages that use it, what comes in and goes out, guarantees, a normal scenario, exceptions and its parts.
- **Level 3, engineering sources** (`e/<id>/`): the source-derived elements and collections described under "What the map owns". Rendered from the referenced files, opened from a node's collapsed "ИНЖЕНЕРНЫЕ ИСТОЧНИКИ" block or from the tree.
- **Coverage** (`map/`): generated from node data: every node of levels 0 to 2 with its definition, where it takes part, whether it is full or an outline and whether its source changed, plus the stage transitions with their reasons.

Previously published `lifecycle/index.html`, `lifecycle/<stage-id>/` and `e/<id>/` URLs keep resolving; `tests/test_build_explorer_editorial.py` asserts it.

## Editorial nodes

`explorer/nodes/<id>.toml` holds exactly one node; the file name is the node id (lowercase kebab-case). The loader is strict: it rejects unknown keys, missing required keys, a text that is not finished, and any dangling reference, naming the node and the field. Text is plain prose with inline code spans (backticks) only; links are structured fields, never inline Markdown. The validator fails on `...` or `…`, on Markdown syntax (emphasis markers, links, headings, list or quote markers), on unbalanced code spans, and on a sentence that does not end in terminal punctuation. A node is explanatory: it states how the platform works and links to where the rule lives, it does not restate or invent rules.

Every node has `id`, `kind`, `title`, `definition` and `sources`. The `definition` is the node's card text everywhere it is listed. `sources` is a non-empty list of bindings, each `path#Heading` (a Markdown section) or `path` (the whole file), optionally as `{ ref = "...", note = "..." }`. Bind the narrow canonical subsection the text explains; a binding must resolve to a tracked, publicly distributable file and, with a heading, to exactly one heading.

| Kind | Required beyond the common keys | Explanation (a full node) |
| --- | --- | --- |
| `overview` | `heading`, `kicker`, `headline`, `subhead`, `schema_note`, `cta`, `responsible`, `not_responsible`, `level`, `maintenance_auto`, `maintenance_editorial` | `lead`, `thesis` |
| `stage` | `order`, `short_title`, `tagline`, `transitions`, `children` | `lead`, `thesis`, `inputs`, `action`, `outputs`, `path`, `example`; optional `terms`, `fork` |
| `mechanism` | `order`, `role`, `used_in`; optional `children` (its parts) | the stage set plus `guarantees`; optional `cycle` |
| `part` | `role`, `used_in` | like a mechanism, `guarantees` optional |
| `topic` | `order`; optional `children` (terms) | `lead`, `thesis`, `points` |
| `term` | none | none: the `definition` is the tooltip and the page text |

- `transitions` (stages): each has `to` (a stage id, or `stop` for a path that ends), `type` (`main`, `conditional` or `return`), a `reason`, and optionally a `label` drawn on the schema. A return must lead to an earlier stage, a main or conditional transition to a later one. Stage `order` runs from 1 without gaps; the eight stage ids are exactly the `[[stage]]` entries of `explorer/map.toml`, so `lifecycle/<id>/` is stable. A stage is shown as conditional when every transition into it is conditional.
- `inputs` and `outputs`: each has `title`, `text` and a `role`; an output also has a `consumer`; either may link a node with `node`. `action` has `label`, `title` and ordered `steps`. `fork` (optional, repeatable) has `title`, optional `note` and at least two `branch` tables. `path` lists conditional and error paths (`title`, `tag`, `role`, `when`, `outcome`). `example` has a `title` and ordered `steps`, each a sentence or `{ text, emphasis = [...] }` where every emphasized phrase occurs exactly once in the text. `guarantees` and `points` are `title` and `text` pairs. `cycle` is an ordered state loop with notes.
- `role` is one of `stage`, `mechanism`, `artifact`, `actor`, `gate`, `external`, `source`, `neutral` and picks the colour from the legend shown on every page.
- `used_in` and `children` are the only places a relation is authored. Back-links ("where it is used", "comes from") are derived, never authored twice; a part belongs to exactly one mechanism and a term to exactly one topic.
- `terms` lists glossary terms whose title occurs in the node's `lead` or `thesis`; the first occurrence becomes a link with the term definition as tooltip.

### Outlines

A node may declare `outline = true`. It then carries its relation data (`order`, `role`, `used_in`, `children`, and for a stage `short_title`, `tagline`, `transitions`, so the tree and the lifecycle schema stay complete) plus `kind`, `title`, `definition` and `sources`, and no explanation text. It renders as an outline page with its definition, relations and a notice that the full explanation is pending, and the coverage page lists it as an outline. Writing an explanation into an outline fails the build; to promote an outline, remove `outline = true` and add the explanation. The overview, the stage `requirement-intent`, the mechanism `independent-review` and the term `business-requirement` are full today; every other node is an outline until the follow-up coverage change replaces it.

## What the map owns

`explorer/map.toml` owns the structure of the engineering-source level only: element identity, title, hierarchy, order, relations and source references. It has no prose fields; the loader rejects unknown keys, so explanatory text cannot be added there. Every explanation on a level-3 page is rendered from the referenced source file.

- `[site]` gives the site `title`.
- `[[element]]` declares `id`, `title`, `order`, and optionally `parent`, `sources` and `related`. An element with no children must have at least one source.
- `[[collection]]` enumerates tracked files by `glob` (`*` and `?` stay within one path segment; `**` is rejected) so new OpenSpec capabilities, optional engineering capability descriptors and decision records appear without editing the map or any node. `title_from` is `heading`, `slug` or `toml:<key>`; `summary_from` is `first-paragraph`, `section:<Heading>` or `toml:<key>`; `slug_from` is `stem` or `parent`; optional `companions` name extra files per item through `{stem}` and `{slug}` templates.
- `[[stage]]` links a lifecycle stage to the engineering-source elements it involves: `id` (the editorial stage node with the same id) and `elements`. Title, order, transitions and explanation belong to the node. A stage node without a `[[stage]]` entry, or an entry without a node, fails the build.

A source reference is `path` or `path#Heading`. The excerpt is the heading section up to the next heading of the same or higher level, or the whole file (without its level-1 heading) when no heading is given. A heading must match exactly once. Duplicate ids, parent cycles, dangling `parent` or `related` ids, a collection that matches nothing, and a source that is missing, untracked or excluded by the public-distribution policy all fail the build.

## How level-3 sources are rendered

A small built-in renderer supports the constructs present in the sources: headings, paragraphs, ordered and unordered lists including task items, fenced code, tables, inline code, emphasis, links, block quotes and GitHub alert markers. It fails closed. An unsupported construct inside an included excerpt (raw HTML, images, setext headings, indented code blocks, reference-style links, strikethrough, character references, ragged tables and similar) fails the build with the file and line; it is never dropped or shown as raw text. Constructs outside the included excerpt do not matter. When a source legitimately needs a new construct, extend the renderer and its tests instead of rewording the source around the limit.

Relative links to repository files become links to the matching level-3 page when one shows that file (or that heading), otherwise to the file or directory at the built commit. A link to a missing, untracked or excluded path, or to a heading anchor that does not exist, fails the build.

## Lifecycle schema

The overview and `lifecycle/index.html` draw the lifecycle as one inline SVG generated from the stage `transitions`: stages in two snake-ordered rows, main transitions as solid blue arrows, conditional ones dashed amber, returns red, labels where a transition has one, and a conditional stage with a dashed box. A transition the layout cannot route, or a label on a transition between neighbouring stages, fails the build. Below 980 px the SVG is replaced by a vertical list that states each non-obvious transition with its reason. Every box and list entry is a plain link to the stage page, so the schema works without scripting.

## Pages, links and offline use

`index.html` is the overview, `lifecycle/index.html` the schema page, `lifecycle/<stage-id>/` a stage, `m/<id>/` a mechanism or part, `t/<id>/` a topic or term, `e/<id>/` a level-3 element and `map/` the coverage page. All internal links and assets are relative, so the site works from a project-site subpath or from the file system. The tree is nested `details` lists with the current branch expanded in the HTML; `assets/explorer.js` only adds expand and collapse of the whole tree and keeps the selected entry in view. Every page shows the role legend, the tree, a breadcrumb, a kind tag, the node panel and the platform `VERSION` and short commit in the footer. Fonts are system stacks; the site has no remote font, script or stylesheet.

## Editorial drift

An explanation can fall behind its source. That is made visible and never blocks.

- `explorer/editorial-review.json` maps a node id to `{ binding: digest }`: the SHA-256 of each bound section at the last review, with whitespace runs normalized, so whitespace-only edits are not drift.
- `check`, `build` and `drift` report a bound section whose digest differs from the record, a binding with no record, and a record for a binding or node that no longer exists, as `warning:` lines. They exit 0 when drift is the only finding. Everything else in this document remains a hard failure.
- A built node page whose bound section changed shows the marker «Источник изменился после последней сверки текста» and names the section.
- After reading the changed section, update the node text if needed and run `python3 scripts/build_explorer.py mark-reviewed <node-id> ...` (or `--all`, which also drops obsolete records). The rewrite is deterministic.
- `python3 scripts/select_checks.py --execute` runs `check` for changes under the bound source surfaces (`[checks.explorer]`) and prints the drift that touches the changed files after the selector finishes; it never changes the selector's exit code.
- In pull requests the build job also runs `drift --github`: one `::warning::` annotation per stale node and the list in the job summary. It never fails the check.
- After a merge to `main`, the isolated `drift-issue` job runs `python3 scripts/build_explorer.py drift-issue`: it creates or updates exactly one open issue labelled `explorer-drift` in the same repository, titled «Explorer: сверить пояснения», listing the stale nodes and sections, and closes it when none remain. More than one open issue with that label is an explicit error. The command needs `GITHUB_REPOSITORY` and `GH_TOKEN` and uses the `gh` CLI; it fails visibly when the issue API cannot be reached, and nothing else depends on it.

## Determinism and public safety

Output has no timestamps or absolute paths and uses declared order, then id, so identical inputs produce byte-identical output. The commit comes from `git rev-parse HEAD` and sources come from `git ls-files` minus the public-distribution exclusions; running outside a git checkout is an explicit error rather than a filesystem walk. Sources are read from the working tree, so when tracked files differ from `HEAD` every page footer says the commit is shown "с незафиксированными изменениями"; build from a clean checkout when the stamped commit must describe the content exactly. `build --out` writes into a sibling staging directory and renames it into place, so a failed write leaves no partial site.

Before anything is written, every generated file is scanned with the owner-reference and secret rules of `scripts/public_distribution.py`. A finding aborts the build with the generated path and the reason, without echoing the matched value, and writes nothing.

## Ownership and downstream boundary

The Explorer is platform-owned and is not distributed. Its map, nodes, review record, assets, build entrypoint and generated output live outside `template/`, so a rendered project receives none of them, and `tests/test_build_explorer.py` renders a project and fails if any Explorer artifact appears or if one is placed under `template/`. See [ownership.md](../ownership.md).

## Publication

`.github/workflows/explorer.yml` publishes the Explorer to GitHub Pages. It only orchestrates: checkout, Python 3.11 and repository commands. No build or validation logic lives in the workflow.

- **Pull requests** that change `explorer/`, the build script, `scripts/public_distribution.py`, `AGENTS.md`, `README.md`, `docs/`, `openspec/specs/`, `dev-platform/capabilities/`, `VERSION` or the workflow run the `build` job only: `python3 scripts/build_explorer.py build --out build/explorer` (a failing build fails the check; nothing is uploaded or deployed) and `drift --github` (annotations and summary only).
- **Pushes to `main` and manual dispatch on `main`** build, upload the Pages artifact (retained as the run's workflow artifact) and run the `deploy` job in the `github-pages` environment. Deployments share one `pages` concurrency group that never cancels a run in progress.
- **Pushes to `main`** also run the `drift-issue` job, which has no dependency in either direction with `build` and `deploy`, so its failure changes neither.
- Workflow permissions are `contents: read`; only `deploy` adds `pages: write` and `id-token: write`, and only `drift-issue` adds `issues: write`. Third-party actions are pinned by commit SHA.

### One-time operator step

An operator must enable Pages once: repository **Settings -> Pages -> Build and deployment -> Source: GitHub Actions**. The workflow never changes repository settings and has no other publication path. Before `actions/configure-pages` (used without its `enablement` input), the `deploy` job reads the repository's Pages source and fails with an explicit error unless it is GitHub Actions, including when Pages is not enabled at all; nothing is published. Enable the setting and re-run the job.

### Reproducing the published site

Check out the published commit (the footer of every page shows the short commit) and run the same command:

```bash
python3 scripts/build_explorer.py build --out build/explorer
```

The build is deterministic, so the output matches the published artifact for that commit. Build from a clean checkout so the footer does not report uncommitted changes.

`tests/test_explorer_workflow.py` checks the workflow contract: triggers, per-job permissions, SHA pinning, default-branch-only deployment and drift reporting, the absence of `enablement`, that every step runs a repository command, and that nothing under `template/` publishes the Explorer.

## Verification

`tests/test_build_explorer.py` covers map validation, source resolution, collection discovery, determinism, unsupported constructs, prohibited-state rejection, relative links under a subpath, the downstream boundary and the committed map against the committed sources. `tests/test_build_explorer_editorial.py` covers node validation failures (missing field, unknown key, dangling reference, transition without reason, unresolved binding, ellipsis, Markdown, unfinished sentence), outlines, derived back-links, the lifecycle schema, URL preservation, drift warnings that do not fail, whitespace-insensitive digests, the page marker, `mark-reviewed` and the drift issue.
