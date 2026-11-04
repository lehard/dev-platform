## Decisions

- **Order in `merge_reviewed_contribution`.** Content gates first, then ownership, then `merge_conflicts` against the target, then required checks immediately before merge. A missing check on a conflict-free head stays an explicit refusal naming the wait.
- **Base is identity.** `contribution_base` remains the single identity field. It changes only to a head of the target that descends from the previous base. Reconcile updates the child context; integration repair rebinds the identity to the merged target head before refreshing task content.
- **Gate reuse.** `reusable` no longer needs an equal base when `equivalent_proofs` proves the move. A proven target-only merge keeps gates bound to the moved base. Any other content change returns to review on the new base.
- **Re-admission.** `_SAME_TASK_KEYS` drops the base; re-admission requires the new base to descend from the recorded base and be contained in the target, otherwise it refuses naming `dogfood_task.py reconcile`.
- **Freshness.** One helper resolves the freshness target: the contribution target or main. Behind-mergeable keeps its meaning relative to that target. A contribution is not compared with main; composition validates main.
- **absorb-main.** Runs in a disposable checkout, merges origin/main, pushes fast-forward with the exact expected head. It reuses `push_fast_forward`. Open contributions need no action: their base stays an ancestor of the target, and the moved-target re-offer already covers them. The manifest is unchanged; the merge history stays in git.
- **Composition.** Identity checks keep using the child's recorded base, now the moved base. The child record is the stored binding of base, identity, head and integration history.
