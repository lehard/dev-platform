# Change: Harden protected-PR reconciliation under concurrency and transient GitHub state

## Why

The protected-main PR lifecycle is now resumable and GitHub-aware, but one local race remains in the platform-owned multi-agent path. `finish_task.py` serializes direct integration through the shared `main_merge_lock`, while PR-mode post-merge reconciliation (`sync local main -> board cleanup -> optional worktree cleanup`) currently runs outside that lock. Two task PRs can therefore merge safely on GitHub and then concurrently mutate the same integration checkout, creating avoidable local Git/index lock failures and breaking the intended zero-hand-off experience.

The same lifecycle still distinguishes "required checks have not registered yet" partly from human-readable `gh` CLI output. That is fragile across GitHub CLI wording/version changes. Bounded waits are necessary, but when a registration or merge-queue wait expires the lifecycle should expose a structured, resumable pending state rather than an ambiguous failure that invites unsafe manual repair.

## What changes

- Serialize the local mutation phase of PR-mode reconciliation with the existing integration/main lock. Remote PR/check waiting stays outside the lock; acquire it only after GitHub confirms the task PR is merged (or an already-merged recovery is detected), then re-fetch and reconcile local state under the lock.
- Keep the lock scope narrow: local main synchronization, board reconciliation, and optional local worktree/branch cleanup. Do not hold the shared integration lock while waiting minutes for cloud CI or merge queue progress.
- Re-check `origin/<main>` and local integration state after acquiring the lock so a second completed task can safely reconcile after a first one advanced local main.
- Replace check-registration classification based on human-readable `gh` messages with structured GitHub PR/check state. Human-readable output may still be displayed, but must not be the source of truth for `not_registered`, `pending`, `passed`, or `failed`.
- Make bounded registration/merge waits explicitly resumable. On timeout, leave the PR/feature branch intact and local main untouched; a rerun must query authoritative remote state and continue without duplicate PRs, rebases, or branch-protection bypass.
- Add regression coverage for two near-simultaneous PR completions, already-merged recovery under the integration lock, structured check registration, and timeout/resume behavior.

## Scope

This affects both new projects and existing projects using `harness_mode=platform`, `publish_mode=pr`, especially `workflow_profile=multi-agent`. Project-owned harnesses remain responsible for their own integration serialization. Managed template files and lifecycle tests change and must be validated through Project Factory rendering and downstream Copier update behavior.

## Compatibility risks

- Incorrect lock scope could serialize long-running cloud waits and reduce concurrency; the design explicitly forbids that.
- Structured GitHub state queries must tolerate supported GitHub/`gh` response variation without falling back to arbitrary log-text parsing.
- Recovery must remain idempotent when another task advanced local main while this task was waiting remotely.

## Success criteria

Two agents may finish separate protected task PRs at nearly the same time without racing the shared integration checkout. Required-check registration is classified from structured remote state. Registration/merge timeouts remain fail-closed but resumable, and rerunning the same finish command completes remaining reconciliation without human Git surgery.