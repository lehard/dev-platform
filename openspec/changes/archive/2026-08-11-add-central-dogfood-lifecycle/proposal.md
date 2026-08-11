## Why

Source backlog issue: `lehard/development-backlog#2`  
Source evidence: `lehard/dev-platform#113`  
Prepared against: `lehard/dev-platform@c3060546ea505e4246e27873db685246a029498a`

The central `dev-platform` repository defines the reusable zero-hand-off lifecycle used by generated projects, but the source repository itself cannot currently run that lifecycle end to end through a single supported start/finish path. The first managed-task dogfood run exposed the mismatch: downstream lifecycle components existed under `template/scripts/`, while the central checkout lacked the corresponding runnable source-repository entrypoints and root lifecycle wiring. PR #112 therefore needed a safeguarded fallback even though the platform contract intends routine agent work to reach terminal delivery without the human acting as Git courier.

This gap is now more visible because managed Development Backlog intake makes `dev-platform` itself a normal consumer of the task system. Central platform work needs to dogfood the same delivery guarantees it publishes: protected-main PR publication, exact-head safety, required checks, resumable remote state, confirmed merge, and local reconciliation.

## What Changes

- Add an explicit supported dogfood lifecycle for ordinary tasks performed in the central `lehard/dev-platform` source repository.
- Provide one normal start path that prepares an isolated task workspace/branch from synchronized central `main` without requiring an agent to assemble ad-hoc Git/worktree steps.
- Provide one normal finish/resume path and a read-only status path for central tasks. The path reuses the platform's existing GitHub-backed publication observation/reconciliation rather than introducing a second publication engine.
- Define central-source configuration/ownership explicitly instead of relying on downstream template defaults or the accidental absence/presence of `.dev-platform.toml`.
- Treat publication as a state machine with terminal completion only after GitHub confirms `MERGED` and required local reconciliation/cleanup succeeds or is explicitly classified as a non-blocking post-merge warning under existing policy.
- Ensure `branch pushed`, `draft PR`, `PR open`, or `checks passed` are observable intermediate states, never implicit completion.
- Keep automatic and manual-review policy distinct. Automatic policy continues toward merge without routine human intervention; manual-review policy stops intentionally and reports a nonterminal human-decision state.
- Add central-source integration tests with temporary remotes/repositories for start, PR delivery state, restart/resume, exact-head protection, and local reconciliation.
- Update root agent guidance so central tasks use the dogfood lifecycle and cannot report success before the lifecycle's terminal state.

## Capabilities

### New Capabilities

- `central-dogfood-lifecycle`: Runnable, tested zero-hand-off task lifecycle for the `dev-platform` source repository itself, built on the same publication semantics used by platform-managed downstream repositories.

### Modified Capabilities

None. The current `platform-lifecycle` publication contract remains authoritative. This change supplies the missing source-repository adapter/entrypoint needed for `dev-platform` to exercise that contract itself.

## Platform / rollout scope

This behavior is specific to the central platform source repository. It does not add a new workflow profile and does not change downstream runtime semantics. Any reusable bug fix discovered while implementing the adapter must remain within the existing platform-lifecycle contract unless a material cross-project behavior change is explicitly reconciled into OpenSpec first.

The root repository may gain source-owned scripts/configuration/guidance/tests. Downstream template files should change only when required to avoid duplication or to share a proven reusable primitive; normal Copier rollout is not an acceptance requirement for source-only wiring.

## Compatibility and active-change boundaries

`durable-publication-recovery` is currently active and already owns exact-head PR discovery, required-check state, resumable publication, remote merge arming/fallback, and local reconciliation behavior. This change MUST consume those primitives/semantics rather than redefine them, and must not claim completion of that change's remaining downstream live-acceptance tasks.

`adopt-gh-aw-process-automation` remains unrelated maintenance automation. The dogfood lifecycle must not use gh-aw as an executor or scheduler.

The implementation must preserve protected `main`, avoid force-push/admin bypass, avoid new secrets, and use existing GitHub authentication resolution. A central-source convenience wrapper is acceptable; a forked copy of publication logic is not.
