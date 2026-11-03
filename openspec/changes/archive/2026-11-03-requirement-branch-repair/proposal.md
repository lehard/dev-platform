## Why

An assembled `requirement/BR-N` branch has no repair entry outside queue jobs, so composition fixes (manifest regeneration, a guard fix, a spec wording, a restored child receipt) were made as one-off manual fast-forward commits, and a manual repair once broke a child receipt.

## What Changes

- A repository command requests repair of a composition: it enqueues the existing `repair` job kind on the composition PR with a stated reason.
- The repair writer keeps its guards: child `verification.md`, `automated-checks.json` and independent-review files are not editable; declared generated files are regenerated after the edit.
- Before the repaired head is pushed or admitted, `validate_children` checks every child receipt byte-for-byte; a mismatch fails explicitly.

## Impact

- `template/scripts/{lifecycle_workers,requirement_composition,execute_requirement}.py`, tests, manifest, chat-coordinator docs.
- Spec: platform-lifecycle (added).
