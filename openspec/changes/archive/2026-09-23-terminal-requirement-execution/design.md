# Design: Terminal Requirement execution

## Authority

The operation reads the Requirement Issue, current pre-authoring status and exact handoff envelopes, canonical linked child Issues/packages, local managed task state, ready-for-integration receipts, and the shared integration manifest. Its output is a recomputable plan/next action, not a persisted task queue. Any small local cache is disposable and must be validated against these authorities.

## Sequence

For each ready handoff in dependency order, reuse or materialize the exact managed child and prove both links. Start or resume one child in its isolated worktree, using the predecessor's exact ready receipt where declared. The agent performs bounded implementation and the existing verification/archive operation; the entrypoint then validates the child receipt. After all required children are ready, assemble/compose a single shared candidate and invoke the existing protected publication path. Reconcile local main and child terminal state before claiming completion.

The handoff materializer inserts the exact standalone `Requirement:` backlink into the initial Issue body even when authored prose already says `Parent Requirement:`. This prevents adapter-owned link repair from immediately invalidating the package's source-Issue revision evidence.

Before materializing a current handoff, the supervisor checks the parent Requirement's already linked children against their canonical managed change identities. A unique existing child wins even if an earlier handoff digest differs after pre-authoring refresh; duplicate change ownership fails closed. Only a genuinely absent change enters new handoff materialization and same-project distinctness review.

A verified ready child is no longer an active writer. After proving its clean worktree and branch still match the exact ready receipt, the supervisor releases only that child's board claim, preserving its worktree, Issue and receipt for shared publication. This removes false inherited-path conflicts for dependent children without acknowledging actual concurrent edits. A dirty or changed predecessor remains blocking; no sibling worktree contents are modified.

## Recovery

Each invocation rederives state. An existing exact Issue, worktree, receipt, candidate or PR is resumed rather than duplicated. Missing/stale dependencies, conflicting state, material contract decisions or external GitHub/CI blockers stop with a bounded diagnostic and an authorized recovery action. The operation never fabricates a verification receipt, merges an unverified change, or marks a Requirement Done on intent alone.
