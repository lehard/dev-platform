## Why
BR-441 requires that the main end-to-end Dev Platform lifecycle can be understood visually and in sequence. Component browsing alone answers "what exists" but not "how a change flows from intent to feedback". This change adds that ordered view on top of the Explorer foundation.

## What Changes
- Extend the Explorer map schema with ordered `[[stage]]` entries: id, title, order, the component elements it involves and canonical source references for its explanation.
- Generate a lifecycle overview page showing all stages as a visual ordered flow, plus one page per stage with its explanation, previous/next navigation and links to related component elements and sources.
- Give the overview and every stage a stable relative URL and a place in the navigation tree.
- Validate at build that stage order is contiguous, every stage references existing elements and resolvable sources, and no component element named by a stage is missing.
- Initial stages follow the platform lifecycle documented in the README and engineering documents: requirement and intent, specification, routing, isolated implementation, verification, publication and integration, release and rollout, feedback and learning.

## Current to Target
Currently (after the foundation change) the Explorer shows structure only. Target: a reader can start at the lifecycle page and walk the flow stage by stage, jumping to the components behind each stage.

## Success Evidence
- The lifecycle overview lists every declared stage in order and each stage page links to its previous and next stage and to at least one component element.
- A stage that references a missing element or unresolved source, or a stage list with duplicate or gapped order, fails the build naming the stage.
- Stage explanations are rendered from canonical sources; the map holds no stage prose.
- Lifecycle pages work without JavaScript and under a subpath, like all Explorer pages.

## Non-goals
Interactive simulation of a live run, per-task or per-agent status, queue or board views, new lifecycle behavior, animated diagrams requiring a third-party library, and Pages publication.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `platform-explorer`: adds the ordered lifecycle journey requirement.

## Impact
`explorer/map.toml` schema and content, the page generator in `scripts/build_explorer.py`, Explorer CSS, tests and `docs/engineering/explorer.md`. No change to `template/`; new projects and existing-project updates are unaffected.
