## Discriminator

Branch ancestry alone cannot separate "created from main, no commits" from "own commits merged into main". The registration head is the missing fact, so `cmd_start` records it as `base_head`.

For a branch that is an ancestor of `main`:

1. `base_head` absent: try the exact merged PR proof; without it the problem is `unproven-merge-no-base`.
2. `base_head` is not a commit in the repository: `unproven-merge-base-unknown`.
3. branch head equals `base_head`: no own commits, no merge problem.
4. `base_head` is an ancestor of the branch head and the head is not in `git rev-list --first-parent base_head..main`: the head entered main as a merge parent, so the task's own commits were merged; `merged-branch`. (Checking every commit of `base_head..branch` instead would misfire after a fast-forward over a `--no-ff` merge, whose second-parent commits also lie off the first-parent line.)
5. otherwise (the head lies on main's first-parent line, e.g. a fast-forward of a commitless task to a newer main or a fast-forward merge of the task, or the branch no longer descends from `base_head`): exact merged PR proof gives `merged-pr`; without it the problem is `unproven-merge-no-own-commits`.

Case 5 is deliberately not guessed: a fast-forward merge and a commitless task fast-forwarded by reconciliation have the same topology. Only the authoritative exact PR resolves it.

`unproven-merge-*` problems are not terminal, so `claim_eligibility` returns `degraded` (no blocking claim, diagnostic only) and `_safe_to_remove` returns false. A git failure other than "not a commit" still raises, as `_merged_into` does today.
