# Tasks

## 1. Specify the cloud execution surface

- [x] Add an ADDED Requirement to the architecture-health OpenSpec delta describing bounded cloud/scheduled execution, read-only tools, bounded safe outputs, and runtime/AI-credit guardrails, with scenarios for a scheduled run, a manually dispatched run, a guardrail-triggered stop, and central-pilot-first scope.

## 2. Implement the workflow

- [x] Author a new gh-aw workflow source (`.github/workflows/<name>.md`) that runs Architecture Health Review's existing instructions as a read-only Codex job with schedule and `workflow_dispatch` triggers.
- [x] Compile and commit the generated lock workflow with the repository's pinned `gh-aw` release.
- [x] Declare bounded runtime/AI-credit/turn guardrails consistent with the accepted agentic-maintenance pattern.

## 3. Verify and document

- [ ] Manually dispatch the workflow in `lehard/dev-platform` and confirm it completes within its guardrails with no code/PR/managed-task mutation.
- [x] Run `openspec validate --strict` for the change, full platform test groups, and semantic OpenSpec verification; record truthful evidence in `verification.md`.

## Logical commits

- [x] Commit the OpenSpec delta and the new workflow source/lock together, since they jointly define one observable capability: a working, bounded cloud execution surface for Architecture Health Review.
