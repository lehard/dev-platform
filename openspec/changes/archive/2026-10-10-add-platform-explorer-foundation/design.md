## Context
The approved Architecture Design Delta for BR-441 fixes these choices (evidence: repository is public, tooling is Python 3.11+ without a Node toolchain, `AGENTS.md` requires thin CI providers, `copier.yml` renders only `template/`):
- Python standard-library generator emitting static HTML/CSS; no framework or runtime dependency.
- Pre-rendered page per element for real deep links; no client routing.
- Prose is rendered from canonical sources; only structure and relations are Explorer-owned.
- Sources, build entrypoint and output live outside `template/`.

## Decisions
1. **Location.** `scripts/build_explorer.py` (platform-only; not in `template/scripts`), `explorer/map.toml`, `explorer/assets/` (CSS and an optional small enhancement script), build output default-ignored (`build/`). Nothing is added under `template/`.
2. **Map model.** `explorer/map.toml` declares `[[element]]` entries (`id`, `title`, `parent`, `order`, `sources = ["path#Heading", ...]`, `related = [ids]`) and `[[collection]]` entries (`id`, `title`, `parent`, `glob`, `title_from`, `summary_from`) that enumerate OpenSpec specs, capability descriptors and decision records. Unknown keys, duplicate ids, cycles, dangling `related` or `parent`, and empty `sources` on a non-container element are errors.
3. **Source rendering.** A source reference is `path` or `path#Heading`. The excerpt is the heading section up to the next heading of the same or higher level (whole file when no heading). A reference must resolve to a git-tracked file not matched by the public-distribution exclusions. A small built-in renderer supports the constructs present in the sources (headings, paragraphs, ordered/unordered lists, fenced code, tables, inline code, emphasis, links, block quotes including GitHub alert markers). An unsupported construct inside an included excerpt fails the build naming file and line; it is never silently dropped or rendered as raw text. Relative links to other repository files become links to the matching Explorer element when one exists, otherwise to the file at the built commit.
4. **Pages.** `<out>/index.html` and `<out>/e/<id>/index.html`. All internal links are relative so the site works under a project-site subpath. The navigation tree is rendered into every page (nested `details` for collapsing, `aria-current` on the selected element), so pages work without JavaScript. Each page shows: title, purpose excerpt, "where it fits" (parent chain), related elements, sources with links to the exact file at the built commit, and the platform VERSION and short commit in the footer.
5. **Determinism.** Stable ordering (declared `order`, then id), no timestamps, no absolute paths. The commit comes from `git rev-parse HEAD`; running outside a git checkout is an explicit error.
6. **Public-safety gate.** Source reading is restricted to `git ls-files` minus the public-distribution exclusions. After rendering and before writing, the generated text is scanned with the existing public-distribution owner-reference and secret rules; any finding aborts the build with the bounded path and reason, writing nothing. This reuses `scripts/public_distribution.py` functions rather than a second pattern set.
7. **Downstream boundary.** Because Copier renders only `template/`, the boundary holds by location. A contract test renders a project with the existing render test helpers and asserts absence of `explorer/`, `build_explorer.py` and generated output, so a future accidental move into `template/` fails. `docs/ownership.md` records that the Explorer is platform-owned and not distributed.
8. **Entrypoints.** `python3 scripts/build_explorer.py build --out DIR` and `python3 scripts/build_explorer.py check` (validate map and sources without writing). Failures exit non-zero with a message naming the element and source; there are no defaults that mask a missing input and no degraded rendering mode.

## Risks and Mitigations
- *Drift between map and sources:* every reference is validated each build; collections are globbed so additions need no map edit; removal or rename of a referenced heading fails CI.
- *Public exposure of operator state:* output scan plus tracked-file restriction; DEC-0002 limits public work identity to BR tokens, and Backlog repository references are rejected by the owner-reference rule.
- *Minimal renderer incompleteness:* fail-closed on unsupported constructs; extend the renderer when a source legitimately needs a new construct.
- *Test-suite coupling:* root `scripts/` may be mirrored or compared with `template/scripts` by existing contract tests; the implementation must confirm Explorer files are correctly classified as platform-only and keep those tests green.
- *Scope growth into a second documentation system:* map has no prose fields by schema.

## Ownership and Rollback
Platform-owned, versioned with the platform, never rendered downstream. Rollback is removal of `explorer/`, the script and the doc/test additions; no data or downstream state is involved.

## Open Questions
None. Hosting and publication are handled by the sibling publication change; the lifecycle journey by the sibling lifecycle change, which extends this map schema with ordered stages after this change lands.
