# Proposal: Self-contained Harness documentation for agents

## Why

The downstream template ships `AGENTS.md` and detailed engineering documents but no map tying them together, and its OpenSpec guidance assumes the agent already knows OpenSpec. Agents may pick the wrong source of truth, miss the concern document, or fall back to upstream OpenSpec docs for rules that are part of the Dev Platform workflow. This must be fixed before Harness is installed for a client.

## What changes

- New platform-owned `template/docs/README.md`: a documentation map explaining the roles of `AGENTS.md`, `docs/`, accepted `openspec/specs/`, active `openspec/changes/` and code, with a "which document for which task" table.
- `template/docs/engineering/openspec-workflow.md` gains an "OpenSpec model used by Dev Platform" section: purpose of `proposal.md`, delta `specs/`, `design.md`, `tasks.md`, `verification.md`; accepted specs vs active delta; Requirements/Scenarios; contract changes during implementation; semantic verification; archive; and the boundary between upstream OpenSpec and Dev Platform entrypoints.
- Rendered `AGENTS.md` adds one pointer row to the docs map; it stays a bounded map.
- Regression tests: rendered docs links resolve, required sections and pointers exist, AGENTS.md remains bounded.

## Success evidence

A fresh render has the path AGENTS.md -> docs/README.md -> concern document with all links resolving; the OpenSpec section contains each required topic and names only entrypoints that exist in the template; tests and full validation pass.

## Constraints and non-goals

No change to OpenSpec/task lifecycle, scripts or CLI behavior. No documentation-governance runtime, portal, RAG, skills conversion, or rewrite of other docs. The central repository's own docs are not restructured.
