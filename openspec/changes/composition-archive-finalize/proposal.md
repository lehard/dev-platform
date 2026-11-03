## Why

Composition finalization archives children through its own archive mode, so the archive rules live in two places and can drift.

## What Changes

- `execute_composition_finalize` calls `finalize_change` per child in manifest order with composition review evidence as the review source.
- Preconditions of every child are evaluated before any child is archived; one error lists them per child.
- The separate composition archive branch in `openspec_lifecycle` is reduced to selecting the composition review evidence inside `finalize_change`.

## Impact

- `template/scripts/{requirement_composition,openspec_lifecycle}.py`, tests, manifest.
- Spec: platform-lifecycle (requirement added).
