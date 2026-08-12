# Optimize agent context map

## Why

Source backlog issue: `lehard/development-backlog#28`  
Prepared against: `lehard/dev-platform@6d2629db8b5f4e6ed6dbdcdaa5dba8a0ddd14d8a`

Dev Platform already has the right durable knowledge layers: OpenSpec for accepted/current change contracts, `docs/` and `docs/engineering/` for architecture and workflow guidance, module-level `AGENTS.md` for scoped rules, executable scripts for lifecycle mechanics, and thin tool-specific adapters such as `CLAUDE.md`. However, the repository-wide `AGENTS.md` has accumulated detailed managed-task, OpenSpec, worktree, model-routing, publication, release, validation and friction instructions that are also represented in those more appropriate layers.

Because root agent guidance is loaded broadly, this turns reusable process knowledge into an always-on prompt cost and makes the platform more sensitive to context limits when agents or shells change. The generated downstream template has the same tendency. The platform should preserve all safety and lifecycle semantics while making `AGENTS.md` a compact vendor-neutral navigation and invariant layer that points agents to the canonical detailed contract they need for the current task.

The change must be semantic-preserving. It is not permission to delete difficult rules, weaken completion requirements, or hide workflow details. Every meaningful current directive must either remain always-on because it is needed for nearly every task or move to one clear canonical repository document with a discoverable route from the root map.

## What Changes

- Reclassify current root guidance into a small always-on set versus just-in-time detailed guidance.
- Reduce the central `AGENTS.md` and `template/AGENTS.md.jinja` to a bounded map containing source-of-truth relationships, task-intent boundaries, key safety/stop invariants, canonical lifecycle entrypoints, ownership/scope rules and links to detailed repository docs.
- Consolidate detailed workflow instructions into existing thematic docs where possible instead of creating another monolithic prompt file.
- Preserve `AGENTS.md` as the canonical cross-agent entrypoint; tool-specific files remain thin references/adapters and no Hermes-specific parallel contract is introduced.
- Add regression coverage that enforces a bounded root-guidance budget and required navigation anchors so the always-on context cannot silently grow back into a full handbook.
- Verify central dogfood and rendered downstream profiles preserve the same observable task, OpenSpec, worktree, routing, validation/publication and friction semantics.
- Verify this change risk-proportionally: focused structure, anchor, destination/link, render and semantic-preservation evidence rather than an unrelated full software regression suite run solely because instruction/documentation/template text changed. Any intentional directive behavior change is reconciled with OpenSpec first and carries targeted behavioral evidence.

## Impact

- Affected spec: `project-factory`.
- Likely implementation surfaces: central `AGENTS.md`, `template/AGENTS.md.jinja`, existing `docs/` and `template/docs/engineering/` guidance, thin tool adapters where references need adjustment, template/contract tests and possibly documentation-link validation.
- Active `adopt-gh-aw-process-automation` overlaps in generated completion/friction guidance. Implementation preflight must reconcile against its current state and preserve its retrospective/completion contract rather than moving an obsolete version of that guidance.
- Hermes integration, provider routing changes, test-cycle optimization and general doc-gardening automation are separate work. The risk-proportional validation selector itself is backlog issue `lehard/development-backlog#27` (`reduce-platform-test-cycle-time`), which is still open; this change only applies that principle to its own verification and does not implement the selector.
