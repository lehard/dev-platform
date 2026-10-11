## Why

New blocking checks have repeatedly created dead ends: the routing gate stopped written code with no supported way to record the owner's decision until a later fix (#425), and an ownership check rejected a correct shared workspace until v1.9.1 (#427). The Requirement asks that an agent never has to choose between an unauthorized bypass and waiting indefinitely when a safe path exists, and that a genuine hard stop is explicit and justified rather than accidental.

## What Changes

- A platform-shipped gate catalog `dev-platform/blocking-gates.toml`: one entry per blocking platform check with id, owning script, failure class (`platform-defect`, `recoverable`, `hard-stop`), the recovery command or owner-recorded path (for `recoverable`), or a written justification (for `hard-stop`), and the acceptance test names for rejection and recovery.
- A small shared helper in `_platform_common.py` that blocking checks use to fail: it requires the gate id to be in the catalog, prints the class and the recovery or justification, and exits non-zero. A gate failure is never printed as success and no default is applied.
- Platform tests: every catalog entry has both acceptance tests present and passing; any blocking failure raised through the helper uses a cataloged id; a check added or changed without a catalog entry fails platform validation.
- An inventory of existing blocking gates, classified with their current recovery or hard-stop justification, including the gates named in the Requirement (routing early gate, merge-hook/reconcile, shared-workspace ownership, publication preflight, finalize freshness). Entries describe existing behavior; defects already tracked elsewhere are not re-fixed here.
- Negative tests for the protected surface: hotfix and recovery paths cannot disable independent review, protected publication, worktree isolation of other agents, credential limits, routing/provenance/evidence authenticity, Git-history protection or immutable releases; no universal `--force` exists.

## Capabilities

### New Capabilities

- `blocking-check-recovery`: failure classes, gate catalog, helper, inventory and negative tests.

## Impact

`template/dev-platform/blocking-gates.toml`, `template/scripts/_platform_common.py` and the call sites of cataloged gates (mechanical migration of the inventoried gates onto the helper), platform tests, `change-classes.md`. Delivered by release and Copier like the other contract files.

## Non-goals

Re-implementing the point fixes for BR-519, BR-522, #427 or other already-accounted defects; removing or weakening any gate; a new recovery service; automatic bypass of failures.
