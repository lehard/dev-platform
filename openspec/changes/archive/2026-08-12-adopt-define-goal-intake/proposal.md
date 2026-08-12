# Proposal: Adopt optional define-goal intake

Source backlog issue: lehard/development-backlog#24

## Why

The platform already distinguishes discussion, managed authoring, quick execution and managed execution, but fuzzy non-trivial requests can still reach OpenSpec before the intended outcome and proof of success are sharp enough. OpenAI's curated `define-goal` skill provides a bounded way to improve that intake without creating durable planning state.

## What Changes

- Add an optional goal-definition refinement step for requests whose intended outcome or validator is materially unclear, and for explicit goal-backed requests.
- Define the minimum quality bar for that transient goal: outcome, evidence, success threshold, relevant scope bounds and stop/clarification condition.
- Preserve quick-task direct execution and the existing managed Issue/OpenSpec sources of truth.
- Keep model-specific Sol/Luna orchestration outside this change.

## Impact

- Affected specifications: `goal-definition` (new).
- Affected surfaces: reusable agent guidance/template and related contract tests; exact Codex skill/runtime integration is chosen during implementation preflight against current supported mechanisms.
- No new workflow status, backlog or durable implementation-plan artifact is introduced.
