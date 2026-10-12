## Context
Builds on the editorial engine: node schema, validation, drift stamps, visual system and addresses are fixed there. The approved prototype provides the semantic map (node list, definitions, transitions) and the three reference screens whose density and tone the remaining screens follow.

## Decisions
1. **Source of facts.** Each node is written from its bound canonical sections only (`AGENTS.md`, `docs/engineering/*.md`, `docs/release-policy.md`, `docs/managed-rollout.md`, `docs/promotion-loop.md`, `docs/ownership.md`, `docs/adoption.md`, accepted specs). Where a source is ambiguous, the node states less rather than guessing.
2. **Bindings are narrow.** Bind the deepest heading that carries the fact, to keep later drift reports precise.
3. **One explanation per mechanism.** Stages link to mechanisms instead of repeating their explanation; the stage text states only what the stage needs from the mechanism.
4. **Glossary terms** are short nodes reused as hover hints wherever a term appears in node text.
5. **Coverage page** is generated from node data and stage/mechanism relations, not authored by hand.

## Risks and Mitigations
- *Factual drift during authoring:* semantic verification checks each node against its bindings; review stamps are written only after that check.
- *Inconsistent tone across screens:* the three approved screens are the reference; each new screen keeps the same blocks and sentence-length limits enforced by validation.

## Ownership and Rollback
Platform-owned content; rollback removes the added node files and the engine still builds with definitions only.

## Open Questions
None.
