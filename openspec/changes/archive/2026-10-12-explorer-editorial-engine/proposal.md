## Why
BR-573 requires the Explorer to explain how Dev Platform works to a reader who does not know the repository: a level-0 overview, eight lifecycle stages with inputs, outputs, forks and conditional paths, mechanisms, and engineering sources only on explicit request. The accepted `platform-explorer` contract forbids exactly that: the Explorer may own structure only and every explanation is a truncated source excerpt, which produced a flat English tree and identical cards. The owner approved a semantic map and three prototype screens (overview, stage 1, independent-review mechanism) as the model to replicate, and decided that stale explanations must never block development.

## What Changes
- Add one repository-owned editorial layer: one Russian description per semantic node (overview, stage, mechanism, mechanism part, cross-cutting topic, glossary term) with definition, thesis, purpose, inputs, action, outputs and their consumers, forks, conditional and error paths, example and exceptions, typed links to other nodes and bindings to canonical source subsections. It is explanatory only; normative rules stay in `AGENTS.md`, OpenSpec and `docs/`.
- Add the semantic model: levels 0–3, typed stage transitions (main, conditional, return) with a reason each, one node rendered everywhere it participates (schema, stage pages, mechanism pages, tree, coverage map). Level 3 is the existing source-derived map elements and collections.
- Validate completeness and finish of every node text (required fields per kind, no ellipsis, truncation or Markdown fragments, every link and source resolvable). Broken site inputs still fail the build.
- Replace templates and assets with the approved visual system: title zone, role legend, framed workspace with a collapsible tree and node panel, the three zones "Откуда приходит → Что здесь происходит → Куда идёт / кто использует", "Внутри · N", a lifecycle schema with conditional paths and a vertical narrow-screen variant, keyboard focus, content readable without JavaScript.
- Preserve `lifecycle/<stage-id>/` for the same eight stage ids and `e/<id>/` for level-3 elements; add stable addresses for mechanisms and topics.
- Add non-blocking editorial drift: committed review stamps with a digest per bound subsection (whitespace-only edits ignored), a warning from `build_explorer.py check` and `select_checks`, a non-red PR annotation, a site marker "источник изменился после последней сверки текста", a one-command `mark-reviewed`, and one auto-updated GitHub issue listing stale nodes after a merge to `main`.
- Author the approved texts for the overview, stage 1 and the review mechanism, and short definitions for every node of the semantic map.

## Current to Target
Current: map with structure only, explanation = first 240 characters or a heading excerpt of a source, English flat tree, identical lifecycle cards. Target: a Russian editorial explorer whose top levels are written for the reader and traced to canonical sources, with engineering sources one explicit step deeper.

## Success Evidence
- Built overview, `lifecycle/requirement-intent/` and the review mechanism page match the approved prototype structure and texts; screenshots at desktop and 390 px width show no horizontal overflow.
- A node with a missing required field, an ellipsis or a dangling link fails `check` naming the node; a changed bound subsection only produces a warning and the site marker, and the full test suite stays green.
- Every previously published `lifecycle/<id>/` and `e/<id>/` URL still resolves.
- Build stays deterministic, public-safety scanned and absent from rendered projects.

## Non-goals
Full screens for stages 2–8, the other mechanisms and topics; live agent or queue state; changes to the engineering lifecycle; JavaScript frameworks, CDNs, CMS or backend; making stale explanations block any check.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `platform-explorer`: editorial layer, semantic model, visual system, URL continuity, non-blocking drift.
- `explorer-publication`: a post-merge drift-issue job with the minimum issue permission.

## Impact
`explorer/` (new editorial node files, review stamps, assets), `scripts/build_explorer.py`, the selected-checks hook, `.github/workflows/explorer.yml`, tests and `docs/engineering/explorer.md`. Nothing under `template/`; downstream projects are unaffected. Every later PR that edits a bound canonical subsection only sees a warning.
