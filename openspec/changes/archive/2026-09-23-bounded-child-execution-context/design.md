# Design: Bounded child execution context

## Boundary

A child handoff is a derived, disposable view keyed by its managed source Issue and imported OpenSpec change. It contains the active package path, exact source digest and repository revision, the parent Requirement reference, and only explicitly declared dependency receipts needed for execution. The handoff does not embed issue bodies, pre-authoring snapshots, transcripts, or sibling implementation details.

The parent reference is taken from the exact `Requirement: owner/repo#N` backlink already present in the fetched managed Issue body. Authored prose such as `Parent Requirement:` does not satisfy that link. The materialization adapter repairs this exact line idempotently and verifies it after writing, so a derived context cannot be silently based on substring-only linkage.

The supervisor can reconstruct this view from canonical managed state. It retains only parent identity, ordered child references and lifecycle states, and human decisions that cannot be derived. Dependency mismatches fail closed and require refresh from current canonical evidence.

## Integration

The existing start and resume path produces or validates this handoff before routing. Provider-local routing consumes the same bounded view; the view does not choose a model or grant write access. Existing containment and OpenSpec checks remain authoritative.

## Failure and recovery

Missing or ambiguous source provenance, a changed repository base, or stale dependency receipt blocks execution with an actionable diagnostic. Rebuilding the derived view is idempotent and does not mutate child Issues or copy old transcript content.
