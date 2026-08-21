# Design: Profile contract and consumer canary

## Contract boundary

Managed intake depends on a small task-start interface rather than a CLI-only
wrapper: `StartedTask`, `start_task`, cleanup, and admission helpers. The
platform will own this interface at the common/template boundary and test that
each supported profile exposes the behavior expected by `start_managed_task`.

For `standard`, the supervisor works in a standalone isolated clone. Routing
therefore records that clone as the parent route root. The bypass applies only
to parent-only preflight; any actual child writer still passes existing assigned
worktree and containment checks. This preserves the current safety invariant.

## Test strategy

Build a deterministic profile matrix using temporary Git repositories and
mocked GitHub/package adapters. The standard canary must run through the public
managed-start composition sufficiently to prove package discovery, callable
task start, branch/clone semantics and routing record creation. It must fail if
the template removes a required import/API or reintroduces linked-worktree
assumptions.

Run the same suite for rendered template output or a small adopted-project
fixture, not only central module imports. Keep light and multi-agent cases as
compatibility controls; no test launches a model or needs secrets.

## Upgrade and rollback

The change is additive in a release. Existing downstream local patches remain
until their upgrade PR demonstrates the shared implementation and passes the
consumer canary. If rollout detects a failure, it stops before opening or
merging a downstream update under existing fail-closed rules.
