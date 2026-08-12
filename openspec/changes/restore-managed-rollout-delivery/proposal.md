## Why

Source backlog issue: `lehard/development-backlog#13`
Prepared against: `lehard/dev-platform@3c970b815b92f0711d85957a263330b8ecd9d439`

Release `v1.4.25` was published successfully, but managed rollout preparation failed for every current managed consumer: Cuby reported an unresolved Copier conflict in `.github/workflows/dev-platform.yml`, while Jara_Fin and planner-agent-lab terminated with `exit 2` and an `unknown` diagnostic category. A platform release that cannot reach its managed inventory leaves central fixes stranded upstream.

## What Changes

- Root-cause the current rollout failures per repository using the existing structured diagnostics and bounded workflow evidence.
- Repair platform-owned delivery defects without weakening exact-version, Copier-conflict, protected-main or reviewed-PR safeguards.
- Improve classification only where current `unknown` results hide a deterministically knowable blocker.
- Perform a controlled retry across all current managed repositories and require normal tracker closure through a successful preparation.
- Compose with `lehard/development-backlog#12`: diagnose permission-related failures now, but do not implement a second shared-permission subsystem. If a failure is owned by #12, record that dependency and use the finished #12 result for acceptance.

## Capabilities

### Modified Capabilities

- `platform-rollout`: restore reliable, diagnosable delivery of immutable platform releases across the managed inventory after a blocked rollout attempt.
