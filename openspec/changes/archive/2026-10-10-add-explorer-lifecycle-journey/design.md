## Context
Builds on the foundation change: map loader, source-excerpt rendering, tree navigation, relative-link pages and public-safety gate. The lifecycle view reuses all of them; only the stage entity and its pages are new. Stage prose is never stored in the map.

## Decisions
1. **Stage entity.** `[[stage]]` with `id`, `title`, `order` (positive integers, contiguous from 1), `elements = [element ids]` (non-empty) and `sources = ["path#Heading", ...]` (non-empty, same resolution rules as elements). Strict key validation as for elements.
2. **Pages.** `<out>/lifecycle/index.html` shows the ordered flow as semantic HTML/CSS (an ordered list rendered as connected steps; no external diagram library, readable without JavaScript and in narrow viewports). `<out>/lifecycle/<stage-id>/index.html` shows the stage excerpt, previous/next stage links, and the linked component elements with their one-line titles. The navigation tree gains a "Lifecycle" branch listing the stages in order.
3. **Cross-linking.** Component element pages list the stages that involve them ("used in lifecycle stages"), derived from stage `elements`, so no relation is authored twice.
4. **Validation.** Contiguous order, unique ids, existing elements, resolvable sources and non-empty stage list are checked by `check` and `build`; failures name the stage. A stage id may not collide with another element id namespace because stage pages live under `lifecycle/`.
5. **Initial content.** Stages cover requirement/intent intake, specification (OpenSpec), routing, isolated implementation, verification, publication/integration, release/rollout and feedback/learning, each pointing at the existing README, task-intake, workflow, OpenSpec, model-routing, release-policy, managed-rollout and friction documentation sections. Wording about behavior always comes from those sources.

## Risks and Mitigations
- *Lifecycle description drifting from real behavior:* explanations are source excerpts and the stage list is validated against existing elements; renaming a referenced heading breaks the build.
- *Over-claiming completeness:* the initial stage set is bounded to the documented lifecycle; adding a stage is a map edit validated by the same rules.
- *Narrow-screen legibility:* the flow is an ordered list that stacks vertically on small viewports.

## Ownership and Rollback
Platform-owned and not distributed downstream. Rollback removes the `[[stage]]` support and lifecycle pages; component browsing from the foundation is unaffected.

## Open Questions
None. Depends on the foundation change being archived or on the same shared candidate.
