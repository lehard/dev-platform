# Proposal: Support exact-PR continuation and terminal recovery

## Why

A normal local CI-fix descendant of an open PR head cannot currently reconcile with newly advanced main, while a merged exact PR can be sent through a nonterminal task-branch path that risks republication.

## What Changes

- Safely fast-forward an exact open PR branch to a proven local descendant before main reconciliation.
- Preserve strict refusal for remote divergence or changed PR identity.
- Route an exact merged PR exclusively through terminal local-main reconciliation.
