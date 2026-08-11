## Why

Managed-task intake currently materializes its OpenSpec package in whichever
checkout invokes the importer. When an agent begins in the integration copy,
this leaves `main` dirty before the normal task-start synchronization runs;
that synchronization correctly refuses a dirty integration copy. The result
breaks the intended isolation invariant and can leave duplicate uncommitted
planning contracts in `main` and a task worktree.

## What Changes

- Add a platform-owned managed-task start entrypoint that performs read-only
  package discovery, starts the configured task branch/worktree, and
  materializes the package only in that task checkout.
- Make direct materialization from the platform-owned integration checkout
  fail closed for feature-capable (`standard` and `multi-agent`) profiles,
  while retaining direct materialization for the `light` profile.
- Document the managed-task flow as task-start-before-materialization and add
  regression coverage that the integration copy remains clean.
- Preserve project-owned harness routing: platform wrappers must direct those
  repositories to their documented task/worktree lifecycle rather than impose
  a platform worktree implementation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `platform-lifecycle`: managed backlog intake must preserve integration-copy
  isolation while creating task work.

## Impact

The change affects the generated task-start/import scripts, generated agent
instructions and their tests. It applies to newly rendered projects and to
existing managed projects after a reviewed Copier update; no external API or
backlog package format changes are required.
