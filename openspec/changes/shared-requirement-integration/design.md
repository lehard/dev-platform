# Design: Shared Requirement integration

## Boundary

Each child retains its own managed Issue, exact OpenSpec package, isolated worktree, source commit and truthful verification receipt. A new ready-for-integration receipt is nonterminal: it binds the child Issue, change, exact committed head, and the archived contract and verification receipt at that head. A digest of a local JSON file alone is not verification: the handoff must check the tracked archive content and the managed task identity, and assembly must recheck the live child branch head. It does not close the Issue or set Project Done.

The requirement-level integration worktree is created through the existing worktree coordination rules. It records an exact ordered list of child heads and the main base, composes them without history rewriting or force push, and runs interaction checks plus the protected full validation set. It needs an explicit publication identity that the existing PR primitive can validate without pretending the candidate is one child; the integration manifest is the provenance source for that mode. The existing PR publication primitive owns the single final merge and exact-head reconciliation. Only after that merge may the contributing children and parent be projected as terminal.

## Failure and recovery

Stale child heads, changed main, overlapping edits, missing receipts, or a failed combined check stop before publication with actionable evidence. An interrupted run reobserves the exact integration branch and PR; it never deletes, resets or takes over another agent's worktree. A separately deliverable child may use the old publication route only with an explicit recorded reason.

## Risks

The existing child finish path assumes one Issue maps to one PR. Introduce the nonterminal handoff and combined finalization behind a separate mode while preserving the old route. Tests must cover squash-merge provenance and remote-merged/local-pending recovery before using this path for real work.
