## 1. Preflight and shared rollout identity

- [x] 1.1 Inspect the current task/readiness entrypoints and factor/reuse the existing rollout pending/supersession eligibility rules without title/body matching.
- [x] 1.2 Define a structured pre-task rollout state for at least: none, pending checks, blocked/failed, safe-to-adopt, merged-needs-local-sync, and reconciled.

## 2. Reconcile before task creation

- [x] 2.1 Integrate rollout observation before a platform-owned task branch/worktree is created.
- [x] 2.2 For an exact authoritative green rollout, perform ordinary exact-head GitHub merge and confirm remote merge without bypass or force-push.
- [x] 2.3 Synchronize the local integration branch after confirmed merge and make interrupted/retried reconciliation idempotent.
- [x] 2.4 Expose the same prerequisite to project-owned harness guidance/readiness without replacing its repository-owned task implementation.
- [x] 2.5 Stop with an actionable resumable/blocker state when CI/review/conflict/provenance safety conditions are not satisfied.

## 3. Preserve rollout/backlog boundaries

- [x] 3.1 Keep `publish-version.yml -> rollout.yml` automatic release dispatch unchanged in semantics.
- [x] 3.2 Keep ordinary `rollout.yml` delivery reviewable and non-auto-merged by default.
- [x] 3.3 Ensure routine rollout delivery does not create Development Backlog issues.

## 4. Verify and deliver

- [x] 4.1 Add regression/integration coverage for no pending rollout, green pending rollout, checks pending, checks failed, conflict/changed head, unexpected ownership, superseded older PR, remote-merged retry, and local-main reconciliation.
- [x] 4.2 Run relevant lifecycle/rollout/unit tests plus template render and upgrade smoke for supported profiles/harness boundaries.
- [x] 4.3 Run strict OpenSpec validation and semantic verification, archive the change, and publish through the normal protected-main/release lifecycle if template/runtime code changes.
