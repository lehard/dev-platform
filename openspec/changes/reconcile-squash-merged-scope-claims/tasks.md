## 1. Reconcile claim completion from publication authority

- [ ] 1.1 Reuse exact managed-task/publication identity to observe the sibling task's PR merge state.
- [ ] 1.2 Treat proven exact squash-merged sibling tasks as completed for scope-claim gating.
- [ ] 1.3 Keep ambiguous/unavailable publication state fail-closed.

## 2. Preserve worktree safety

- [ ] 2.1 Restrict reconciliation to coordination metadata; never clean/reset/delete/take over the sibling worktree.
- [ ] 2.2 Make repeated reconciliation idempotent.

## 3. Verify

- [ ] 3.1 Add regression for exact squash-merged sibling with no branch ancestry.
- [ ] 3.2 Add controls for genuinely active sibling and unavailable/ambiguous GitHub state.
- [ ] 3.3 Run relevant worktree/publication/lifecycle tests and strict OpenSpec validation.
