# Design: Exact-parent merge candidate

The entrypoint accepts ordered ready receipts and requires each preceding child head to be an ancestor of the next. It binds current authoritative main and final child head in a content-digested manifest. The candidate branch/worktree name includes the base and `merge` discriminator, never reusing a patch-replay or prior branch.

Preparation starts a no-commit merge of the exact last child into the candidate base and reports conflicts without publishing. A human/agent resolves only overlapping paths, records the resolution and finalizes a two-parent merge commit with exact parent SHA. Validation checks receipt/branch freshness, parents, manifest, clean tree and changed-path bounds; it cannot claim byte-identical patches after a reviewed merge. Full tests and semantic review establish resulting behavior.

The existing protected PR primitive and exact merged-PR reconciliation remain the only terminal authority. Any changed head/base, unexpected path, unresolved conflict, failed test or occupied candidate blocks without resetting other state.
