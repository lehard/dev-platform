## Context

`publish_pr` in `project_publish.py` runs after every `finish` gate and reads the head it publishes. `reconcile` in `task_reconciliation.py` pushes a merged head to a published PR. On `pull_request`, `actions/checkout` checks out the merge commit, so the guard must read `github.event.pull_request.head.sha`, never `HEAD`; `fetch-depth: 0` makes that commit available. The workflow and scripts of that event come from the tree of the PR itself.

## Decisions

**Carrier.** A commit trailer on the head. The commit hash covers the message, so the trace is bound to the head with no store, no token right and no API call at check time. The trailer value is the tree of that commit, which catches an amend or rebase that keeps the message. A PR body was rejected: editing it does not rerun the check. A separate ref was rejected: it is not in the PR and needs cleanup.

**One module.** `delivery_trace.py` holds `enabled`, `valid`, `ensure` and the `check` entrypoint. `ensure` commits with `--allow-empty` and the subject of the current head, because the default PR title is the head subject. It does nothing for a head that is already valid. A non-boolean setting stops with an error naming it.

**Publication.** `publish_pr` calls `ensure` before it reads `expected_head`, so the lookup, the push and `--match-head-commit` all use the traced head.

**Head-bound gates.** The checkpoint, selected-check evidence and review bind task content, not the head hash. An empty commit keeps that content, so a repeated `finish` reuses them. A test pins this.

**Reconcile.** In the merge path, when the published head was valid, `reconcile` calls `ensure` before its push. A local descendant pushed by `reconcile` gets no trace, because `finish` has not checked its content; `validate` stays red until the next `finish`.

**Guard.** `python3 scripts/delivery_trace.py check --head <sha>` reads Git only and runs early in `validate`, on `pull_request` only. Exactly one trailer whose value equals the tree of that commit passes. Otherwise it prints the reason and the next command and exits non-zero. The exception list is empty: PR history shows no bot or other legitimate source.

**Recovery.** The fix of a wrongly refusing guard takes effect on its own PR. If `finish` is broken too, a PR that removes the step from `ci.yml`, opened with `gh pr create` and merged with `gh pr merge --auto --squash`, leaves the state; the next delivery through `finish` restores the step. GitHub protection settings do not change.

## Risks

A guard error blocks every PR; the recovery above is proven before merge. The setting being absent means off, which is how projects stay unchanged; in this repository its loss shows as a red `validate`.
