## Why

Friction lehard/dev-platform#838: PR #836 and PR #837 returned to the developer for fresh semantic verification after a coordinator integration merge that only brought main content. Gate reuse after integration relies on `equivalent_proofs`, which needs an identical digest and no task path changed by main between the bases, so any path shared with main (`dev-platform/checks.toml`, the generated manifest) resets the receipt although the candidate's own diff is unchanged.

## What Changes

- A main-only-integration proof: the tree of the new head equals, byte for byte, `git merge-tree --write-tree <old head> <new base>`, and that merge conflicts only in generated files declared by the default-branch checkout.
- The old head is read only from a trusted queue record (proven writer or coordinator App) of the transition on which the gates passed; a missing or malformed record resets the receipt explicitly with a reason.
- After an integration repair, `advance_after_repair` keeps review, selected-check and semantic gates, rebound to the fresh identity, when either `equivalent_proofs` or this proof holds. Finalize then reuses the rebound gates unchanged. Otherwise the candidate returns to review as today, and the reason is logged.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: gate evidence survives a main-only integration.

## Impact

`template/scripts/task_content_identity.py`, `integration_contour.py`, tests. Coordinator decision D1=B with conditions, 2026-11-01.
