# DEC-0009: One stream, one writer: the platform takes the project path

- **Status:** Current
- **Scope:** The platform core: how this repository delivers its own changes, and what ships to projects
- **Decision date:** 2026-11-06
- **Authored against revision:** `8084afdd6befc5b0a3df6f1a2f536386478a63b9`
- **Supersedes:** [DEC-0008](0008-target-task-lifecycle.md)
- **Superseded by:** None
- **Amends:** [DEC-0004](0004-main-advance-revalidation.md): the `behind-mergeable` contract is removed, because nothing merges main into a head any more. A head behind main reconciles first. Evidence reuse for an unchanged own diff stays.

## Accepted current decision

The owner decided on 2026-11-06 to simplify the core sharply.

1. **One stream, one writer is mandatory.** The platform works one task at a time. Nothing serializes parallel writers any more, so the rule is a constraint on the coordinator, not a mechanism.
2. **The platform takes the project path.** There is no `coordinator` lifecycle mode. `finish` archives, publishes one PR and arms GitHub auto-merge, in this repository and in every project.
3. **The publication queue, hosted lifecycle workers and everything that lived only for them are deleted**: candidate records, developer handoff and re-handoff, Requirement contributions and composition, the post-merge runner and their specs.
4. **Merge is one action.** `gh pr merge --auto --squash --match-head-commit <head>`, refused when no required check gates it (lehard/dev-platform#278). The three-attempt chain and the foreground wait are gone.
5. **Independent review is optional**, as in the published releases: it runs in `finish` only with `[independent_review] enabled = true`, and `scripts/independent_review.py` runs it by hand.
6. **This change was delivered as one branch and one PR** without a Requirement, ADD, children or receipts, by direct owner decision.

## What was lost

- Parallel streams and any serialization of concurrent merges.
- Merging main into a head that is behind it: every advance of main now costs a reconcile and a validation rerun.
- Automatic review, repair and finalize after the developer stops, and automatic close of a Requirement after merge: a rerun of `finish` does this.
- Durable coordinator evidence on PRs, and PR-level delivery state in `lifecycle_overview.py`.
- Parallel Requirement children: children run in sequence or through the shared candidate.

## Rejected and deferred alternatives

- **Keep the queue for this repository only:** rejected. Its code was the largest part of the core, it served one repository and a sandbox, and projects never used it.
- **Remove the workflows and leave the code:** rejected. The `coordinator` mode would stay selected and `finish` would hand off to nobody.
- **Staged delivery through Requirements:** rejected by the owner for this change. The stages themselves depended on the machinery being removed.

## Evidence

Work saved before the removal, kept as the source for returning its scenarios and `worker_preflight`: branches `requirement/BR-993`, `agent/br-993-t3-live-requirement-scenarios` and `agent/br-995-t3-stale-candidate-contract`.

Lessons from running the queue that stay useful:

- A GitHub App token on a private repository needs Checks read and Actions read.
- `Empty reply from server` from `gh api` can be a one-off; it is not a reason for a retry loop.
- `gh pr checks --watch` can exit early; `gh run watch` is more reliable.

## Revisit triggers

- Two writers are needed at the same time for a sustained period, and sequential work is the proven bottleneck. Start from a plain GitHub merge queue if the repository moves to an organization, not from the removed code.
- Advances of main under a task start costing more than the reconcile they require.
- A project needs review or merge to continue after the developer session ends.
