# DEC-0005: Managed rollout on demand, not on every release

- **Status:** Current
- **Scope:** Platform releases and downstream managed-project updates
- **Decision date:** 2026-10-28
- **Authored against revision:** `e8392062178fa6b5e3ed7eabd66b8bfa54b2c70e`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

A published platform release does not open rollout PRs in managed projects. The repository variable
`DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED` on `lehard/dev-platform` is not `true`, so
`scripts/rollout_dispatch_gate.py` reports `dispatch=false` and `publish-version.yml` only publishes the
immutable tag. Automatic rollout was enabled on 2026-10-23 and switched off again on 2026-10-28 by owner
decision.

A project is updated when the owner starts working on it: dispatch **Roll Out Platform**
(`.github/workflows/rollout.yml`) with `version` and `repository=owner/name`. It opens one PR straight to
that version; it still does not auto-merge.

## Rejected and deferred alternatives

- Rollout on every release is rejected for now: the owner works on one or two projects at a time and does
  not want platform-update PRs to accumulate in projects that are not being worked on, some of which may not
  be resumed.
- Removing the rollout workflow is rejected: targeted rollout is the supported update path and the
  dispatch gate keeps fleet rollout an explicit operator opt-in.
- A warning at task start that a project lags behind the latest release is deferred:
  `rollout_preflight.py` only reconciles an already open rollout PR. Remaining rollout leftovers (the
  stale-rollout reconciliation schedule and descriptive text that still promises automatic rollout PRs)
  are tracked in BR-846.

## Evidence

- `scripts/rollout_dispatch_gate.py` reads `DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED` and skips dispatch unless
  it is exactly `true`; [release-policy.md](../release-policy.md) states that publishing a release never
  implies fleet rollout.
- Rollout PRs opened during the enabled window stay open; a later targeted rollout to a newer version
  supersedes them.

## Revisit triggers

- The owner again works on most managed projects in parallel, or asks for fleet-wide updates.
- A security or compatibility fix must reach every managed project promptly.
- A managed project starts work on a release older than the latest one without noticing (evidence for
  the deferred lag warning).
