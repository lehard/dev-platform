# Change: Alert on repeated managed rollout failures against the same project

## Why

`harden-rollout-diagnostics` gave every failed managed-rollout attempt a canonical, agent-consumable diagnostic envelope (`rollout-diagnostic.json`, stage/category/reason/exit_code). That closed the "what blocked this one run" gap.

It did not close a different gap: `lehard/cuby` failed the same managed rollout with the same `copier_conflict` blocker for **8 consecutive releases** (`v1.4.13` through `v1.4.20`) before a human noticed. Each attempt correctly failed closed per `allow-safe-reclaimed-rollout-recopy`'s guarded-recopy contract — the safety behavior was correct every time — but nothing accumulated that per-attempt state across releases, and a red `fail-fast: false` matrix job that nobody is watching is not an alert. The diagnostic envelope is regenerated from scratch on every attempt and is never compared against the project's own rollout history, so eight repeats looked, from the platform's point of view, identical to one.

This proposal is scoped narrowly to closing that detection gap: recording rollout outcome history per managed project and surfacing it once repetition itself becomes the signal. It does not change why any individual attempt blocks, and it does not touch `allow-safe-reclaimed-rollout-recopy`'s recopy/recovery eligibility, which remains a separate active change responsible for the underlying Cuby blocker.

## What changes

- Give each managed-rollout attempt a durable, cross-run place to record its terminal outcome (blocked or resolved) against a specific downstream project, keyed by `owner/repo`, independent of any single ephemeral Actions run.
- Track `consecutive_failures` per project: incremented on every terminal blocked attempt, reset to zero the next time that project's rollout preparation succeeds (Copier update completes without a `Managed rollout: BLOCKED:` guard or selected-check failure).
- When `consecutive_failures` reaches a fixed threshold (3), escalate beyond the existing per-run annotation: label the durable record so it is discoverable as an outstanding alert and emit a distinct `::warning::` workflow annotation naming the project and the streak length.
- Choose GitHub Issues on `lehard/dev-platform` as the durable store and human-visible surface: one issue per project streak, opened on first failure, updated with each additional failure's diagnostic category/reason, labeled once the alert threshold is reached, and closed with a resolution note the next time that project's rollout succeeds. This reuses existing GitHub notification/watch behavior instead of adding new infrastructure, and needs no new credentials because it operates on `dev-platform` itself (default `GITHUB_TOKEN`, not the cross-repository App).
- Make streak tracking best-effort and strictly additive: a failure to read, parse, or update the durable record must never change rollout's own pass/fail result, must never block/retry/push/merge anything, and must fail closed toward alerting (an unreadable prior streak state escalates rather than silently resetting to zero).
- Add regression tests for streak increment/reset/threshold-escalation logic and for the workflow wiring (permissions, best-effort step conditions, no interaction with existing safety gates).

## Scope

This only adds a repetition-detection and human-alerting layer on top of already-existing terminal rollout outcomes. It does not change:

- guarded-recopy or any other rollout safety guard, recovery, or conflict-resolution eligibility (owned by `allow-safe-reclaimed-rollout-recopy`);
- the `rollout-diagnostic.json` envelope schema or its per-attempt classification (owned by the already-archived `harden-rollout-diagnostics`);
- cross-repository rollout credentials, the App token model, or any target-project write scope;
- merge, retry, or push behavior — the streak tracker only reads terminal state that rollout already produced and writes to a `dev-platform`-local issue.

## Success criteria

After a managed project fails rollout preparation for the Nth consecutive release with the same or different blocker, and N reaches the threshold, a durable, labeled, human-visible record exists that says so explicitly — without requiring anyone to have watched the intervening Actions runs. The record self-resolves the next time that project's rollout preparation succeeds. No existing rollout safety, recovery, or credential behavior changes, and a failure inside the new tracking layer itself never masks, softens, or replaces the underlying rollout result.
