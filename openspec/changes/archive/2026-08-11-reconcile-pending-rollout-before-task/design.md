## Context

The current release path is already correct and should remain intact:

`VERSION change -> immutable release -> automatic rollout dispatch -> exact Copier update/checks -> reviewed downstream PR -> stop`.

The current rollout implementation also has structured eligibility and supersession logic for bot-owned rollout PRs. The missing behavior is on the consumer side when a developer/agent later starts work in a repository that still has the latest rollout PR pending.

## Decisions

### 1. Reconcile at the next supported work boundary, not by creating backlog noise

A pending rollout is operational platform-delivery state. It is not represented as a Development Backlog issue. The supported task/readiness path is responsible for checking this state before new product work begins.

The exact shared helper/entrypoint placement should follow repository preflight during implementation, but the observable ordering is fixed:

`sync/observe repository -> reconcile eligible pending rollout -> synchronize merged base -> create task branch/worktree -> product work`.

No product task workspace may be created first and then retroactively updated underneath it.

### 2. Eligibility has one source of truth

The pre-task path must reuse or factor the same structured eligibility semantics already used by rollout pending detection/supersession. An authoritative rollout is identified by repository/base, reserved SemVer rollout branch contract, and expected automation identity. PR title/body text is never sufficient.

If multiple historical eligible rollout records exist, only the newest authoritative pending delivery may be considered for automatic adoption; superseded/older records are not merge candidates.

### 3. Green rollout adoption is ordinary GitHub reconciliation

A safe adoption may merge only after the exact current PR head and required downstream GitHub gates are confirmed. It uses normal repository merge policy and existing non-bypass/exact-head safeguards. It never force-pushes, uses admin bypass, or treats a stale observation as sufficient.

After GitHub confirms the rollout PR is merged, the local integration branch is synchronized before task creation. A process interruption after remote merge must be resumable using authoritative GitHub/Git state rather than creating a second merge attempt or asking the user to redo the update.

### 4. Ambiguity blocks new work instead of being hidden

Pending/failed required checks, merge conflicts, changed head, unexpected automation identity/base/version, or a repository policy that still requires an unsatisfied review produce an explicit pending/blocker result. Preflight does not repair application CI or rewrite rollout contents as a side effect.

The agent should not tell the user to perform routine Git courier work when the rollout is already unambiguous and green; human intervention is reserved for actual blockers/policy decisions.

### 5. Keep the rollout workflow reviewable for now

`publish-version.yml` continues to dispatch `rollout.yml` automatically after an immutable release. `rollout.yml` continues to stop at a reviewable downstream PR. Automatic adoption happens only at the later work boundary defined by this change. This preserves the current safety net while eliminating forgotten platform drift at the moment it matters.

### 6. Preserve harness ownership

For platform-owned lifecycle, reconciliation must be part of the supported pre-task path before branch/worktree creation. For project-owned harnesses, the platform should expose the same preflight contract without replacing the repository-owned task/worktree implementation. Agent guidance must make the prerequisite explicit in both cases.

No new daemon, scheduler, service, or credential is introduced; use existing GitHub authentication/resolution facilities.

## Relationship to active work

`adopt-gh-aw-process-automation` owns process-friction capture/triage and does not own rollout adoption. This change may produce friction evidence when reconciliation fails, but it must not merge the two feature contracts.
