## Why

The original version of this change was written before the v1.4.20-v1.4.22 lifecycle stabilization. The current platform already has independent GitHub credential fallback, structured required-check waiting, protected merge/auto-merge/queue negotiation, authoritative `MERGED` handling, concurrent local reconciliation locking, and recovery after a PR was already merged remotely.

The remaining publication gap is narrower: platform-owned PR delivery is still driven by one foreground process. If that process disappears before GitHub has been asked to complete the merge, the PR can remain open until a later lifecycle invocation notices it. The platform also lacks one concise read-only status view for an exact task head.

A machine-local phase journal and long-lived publisher lease would duplicate state that Git and GitHub already expose and introduce a second state system that can drift. The change therefore adopts a level-based reconciliation model: derive the current publication state from Git + GitHub on every invocation, make each transition idempotent, and let native GitHub auto-merge / merge-queue state provide durable remote waiting whenever repository policy supports it.

## What Changes

- Add a GitHub-backed publication reconciler for platform-owned PR tasks. It observes the exact branch/head SHA, matching PR, required checks, merge request/queue state, remote merge state, and remaining local reconciliation work instead of relying on a persisted phase cursor.
- Arm native GitHub auto-merge / merge-queue processing as early as possible for `pr_merge_mode=auto`, guarded by the exact validated head SHA. A caller may still wait for completion, but loss of the caller stream does not cancel an already-accepted GitHub merge request.
- Make normal `finish_task` idempotently resume an existing exact-head PR before stale-branch rejection, and add a read-only `finish_task --status` view derived from current Git/GitHub state.
- Preserve the existing bounded foreground fallback when native auto-merge is unavailable, while reporting that repository capability as degraded durability rather than inventing a local daemon or hidden repository-setting mutation.
- Use exact-head guards (`--match-head-commit` or equivalent API expected-head semantics) for every merge/auto-merge request so a changed branch cannot be merged under an earlier validation decision.
- Add restart/fault-injection and concurrent-resume regression coverage at remote boundaries: after push, after PR creation, after remote merge arming, after remote merge, and before local reconciliation.
- Keep current authentication fallback as baseline behavior; do not reimplement it in this change.
- Remove browser-QA discovery from this change. It is unrelated to publication recovery and should be handled separately only if it remains a demonstrated need.

## Capabilities

### New Capabilities

- `publication-recovery`: Authoritative Git/GitHub observation plus idempotent reconciliation for interrupted platform-owned PR publication.

### Modified Capabilities

- `platform-lifecycle`: Prefer durable native GitHub merge orchestration, exact-head merge guards, and restartable reconciliation for automatic PR delivery.
- `completion-lifecycle`: Expose unfinished automatic delivery as actionable incomplete work without requiring a human Git hand-off.

## Impact

This affects platform-managed publication scripts and guidance, primarily `finish_task.py`, `project_publish.py`, `agent_doctor.py`, generated AGENTS/engineering workflow documentation, and tests. It does not introduce a daemon, database, credential store, or mandatory machine-local publication journal.

`harness_mode=project` remains authoritative for project-owned publication. Manual-review PR mode remains manual. The platform SHALL NOT silently change repository settings; native auto-merge capability is detected and reported, and any repository-setting change is an explicit adoption/administrative action.
