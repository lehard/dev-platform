## Why

Source backlog issue: `lehard/development-backlog#7`  
Prepared against: `lehard/dev-platform@21a10c6dc41365fba80e1759dbfe89b3a99a67ea`

Dev Platform already publishes immutable releases and automatically dispatches a managed rollout for every new release. A clean rollout deliberately stops at a reviewed downstream PR. That safety boundary is useful while the platform is still stabilizing, but it leaves one ordinary operational gap: a healthy rollout PR can remain open indefinitely and the next coding session can start on the older platform version without noticing it.

Routine rollout delivery is not a product backlog item. Creating one Development Backlog issue per project per release would turn the backlog into an operations log. Instead, the next supported task start should treat an eligible pending rollout as platform maintenance that must be reconciled before new product work begins.

## What Changes

- Add a platform-owned pre-task/readiness reconciliation step for the current repository before a new task branch/worktree or product implementation starts.
- Detect pending rollout PRs using the existing structured rollout ownership contract: configured base branch, reserved `dev-platform/rollout-vX.Y.Z` branch/version semantics, and expected rollout automation identity. Human-readable PR titles/bodies are not ownership evidence.
- Reuse the existing rollout/supersession eligibility model so task-start reconciliation and rollout automation agree on which PR is authoritative.
- When the latest authoritative eligible rollout PR is safe to accept and required GitHub gates are satisfied, merge it through ordinary non-bypass GitHub policy, confirm the remote merge, synchronize local integration state, then continue task start.
- When the rollout is not safely adoptable, stop before new product work and surface a concrete resumable/blocker state rather than silently working on an older platform layer.
- Keep release-triggered rollout automatic and keep the rollout workflow itself reviewable: this change does not make `rollout.yml` unconditionally auto-merge downstream PRs.
- Keep routine rollout PRs out of Development Backlog.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: task start reconciles an authoritative pending platform rollout before new work begins.
- `platform-rollout`: reviewed rollout PRs remain the delivery boundary, but a later platform-owned task-start preflight may safely adopt the current authoritative PR.

## Non-goals

- Unconditional auto-merge inside the central rollout workflow.
- Creating managed backlog tasks for every downstream rollout.
- Automatically repairing failed CI or conflicted rollout changes during preflight.
- Changing Development Backlog dispatcher semantics.
