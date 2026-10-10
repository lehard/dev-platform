## Why
Dev Platform's architecture and process are spread over Markdown, TOML and OpenSpec files. A newcomer has to know the repository layout to understand the platform. BR-441 asks for a public interactive Explorer: navigation beside content, explanations of purpose, place in the process and related elements, and direct links per element, without a second hand-maintained copy of the documentation.

## What Changes
- Add a repository-owned build entrypoint `scripts/build_explorer.py` that generates a self-contained static site from canonical repository sources.
- Add one structure-only Explorer map (`explorer/map.toml`): element ids, titles, hierarchy, order, relations and source references. It carries no explanatory prose; prose is always rendered from the referenced source file and heading.
- Enumerate OpenSpec capabilities, optional engineering capabilities and decision records automatically by collection, so new ones appear without editing the map.
- Generate one page per element at a stable relative URL with a persistent navigation tree beside the content, working without JavaScript and under a project-site subpath.
- Fail the build explicitly on a missing source or heading, an untracked or excluded source, an unsupported Markdown construct in an included excerpt, a dangling relation, or prohibited operator state in the generated output (reusing the public-distribution rules).
- Make output deterministic and stamp every page with the platform `VERSION` and source commit.
- Keep all Explorer sources outside the Copier subdirectory and prove with a render test that new projects receive no Explorer artifact; record the ownership boundary in documentation.

## Current to Target
Currently there is no browsable presentation of the platform; understanding it requires reading raw files. Target: `python3 scripts/build_explorer.py build --out <dir>` produces a browsable site whose content is a view of the canonical sources.

## Success Evidence
- A clean build produces an index page and a page for every map element and every enumerated collection item; each page shows the navigation tree, the rendered source excerpts, related elements and links to the exact source files at the built commit.
- Identical inputs produce byte-identical output; changing a source heading used by the map makes the build fail naming the element and source.
- A fixture with a prohibited owner/project reference or secret pattern in an included source fails the build before output is written.
- A rendered new project contains no Explorer map, build script, assets or generated output.
- Existing repository checks (compile, ruff, full test groups, docs links) pass.

## Non-goals
Lifecycle journey view, Pages deployment workflow, search, theming system, CMS, database, backend, authentication, live agent or queue state (Agent Control Room), translation, a third-party Markdown or site-generator dependency, and copying documentation prose into Explorer-owned files.

## Capabilities
### New Capabilities
- `platform-explorer`: source-derived static Explorer build, navigation, deep links, public-safety gate, versioning and downstream boundary.
### Modified Capabilities
None.

## Impact
New files under `explorer/`, `scripts/build_explorer.py`, tests, `.gitignore` entry for build output, and `docs/engineering/explorer.md` plus an ownership note in `docs/ownership.md`. New projects: unchanged (nothing under `template/`). Existing-project updates: unchanged. Downstream managed files: none touched; compatibility risk is limited to accidentally placing Explorer files under `template/`, which a contract test guards.
