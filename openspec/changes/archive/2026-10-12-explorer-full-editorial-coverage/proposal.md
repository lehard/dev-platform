## Why
The editorial engine delivers the model and three approved screens. BR-573 is accepted only when every level 0–2 node has a complete Russian explanation traced to canonical sources and the four user scenarios work on the published UI. This change authors the remaining content in the same model without new design.

## What Changes
- Author full stage nodes for stages 2–8 (change design, routing, execution, verification and independent review, publication and integration, conditional release and rollout, feedback and improvement): purpose, inputs, action, outputs and consumers, transitions with reasons, forks, conditional and error paths, example, mechanisms, source bindings.
- Author full mechanism nodes and their parts: Requirement and intake, ADD and OpenSpec, executor routing, Codex and Claude Code executors, worktrees and parallel coordination, checks and verification receipt, PR/queue/integration, platform releases, Copier and managed rollout, friction and retrospectives (independent review already exists): where used, from whom and to whom, guarantees, normal scenario, exceptions, sources.
- Author cross-cutting topics: ownership boundaries, project adoption and workflow profiles, sources of truth, glossary of key terms.
- Generate the coverage page from node data: what each level shows, what is deliberately deeper, the source behind each node, and how nodes relate.
- Record review stamps for every authored node.

## Success Evidence
- Every node of the approved semantic map has a page that passes completeness validation with no warnings.
- On the built site, the four BR scenarios are walked through from the overview and recorded with screenshots: accepted request to work, independent-review finding, change reaching main, new platform version in an adopted project.
- Every factual statement checked against the bound canonical sections during semantic verification; mismatches fixed in the node, not in the source.

## Non-goals
Engine or visual changes beyond fixes discovered while authoring; changes to the engineering lifecycle; English translations.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `platform-explorer`: complete editorial coverage of levels 0–2 and the coverage page.

## Impact
`explorer/nodes/`, `explorer/editorial-review.json`, small renderer fixes in `scripts/build_explorer.py` if needed, tests and `docs/engineering/explorer.md`. No change under `template/`.
