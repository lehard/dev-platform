## Context

`dev-platform` has two roles that currently do not line up mechanically:

1. It is the source/factory that owns reusable lifecycle code under `template/scripts/`.
2. It is itself an actively developed protected-main repository whose agents need the same zero-hand-off lifecycle.

The source checkout is intentionally not just another rendered Copier consumer. It has root administrative scripts and source files that downstream projects do not have, and it currently has no root `.dev-platform.toml`. Running template lifecycle scripts as if the source checkout were an ordinary generated project therefore relies on assumptions that are not part of an explicit contract. The #112 dogfood run demonstrated the failure mode when `finish_task.py` expected a root lifecycle helper that the source repository did not expose.

Meanwhile, the active `durable-publication-recovery` change has already implemented the hard publication mechanics in the platform template: exact-head observation, structured required-check state, resume of the same PR, safe merge requests and local reconciliation. The missing work is source-repository wiring and source ownership, not a new publishing design.

## Goals

- Make the central repository able to start and finish ordinary tasks through one supported lifecycle.
- Keep protected-main/PR/recovery semantics aligned with existing platform behavior.
- Make every delivery phase observable and prevent premature completion reports.
- Keep source-repository differences explicit rather than hidden behind downstream defaults.
- Ensure future platform changes dogfood the same primitives before they are promoted downstream.

## Non-goals

- Reimplementing publication observation/reconciliation.
- Changing the downstream `light`/`standard`/`multi-agent` contracts.
- Adding a dispatcher or monitoring daemon.
- Changing Development Backlog status automatically.
- Requiring GitHub Agentic Workflows for execution.
- Completing the remaining downstream live acceptance of `durable-publication-recovery` under this change.

## Decision 1: source adapter over publication fork

The central lifecycle will be a thin source-owned adapter around existing platform lifecycle/publication primitives. Implementation may expose root `scripts/start_task.py` / `scripts/finish_task.py`, a single root dogfood command with subcommands, or equivalently small wrappers, but the wrappers must delegate authoritative publication observation/reconciliation rather than copy it into a second implementation.

Before coding, the implementer must choose the smallest arrangement that keeps shared logic importable/testable without making `template/` runtime-dependent for downstream consumers. If code must be promoted into a shared reusable module to avoid duplication, preserve the existing self-contained downstream render contract.

## Decision 2: explicit central configuration

The source repository needs an explicit contract for the values that downstream projects normally obtain from `.dev-platform.toml`: integration branch, protected-main expectation, workspace/profile behavior, publication mode and PR merge policy, plus source-specific required paths.

The preferred implementation is a small committed source configuration or an equally explicit root-owned constant/config layer that is parsed by the central wrappers. It must not mutate the downstream template schema merely to make dogfooding work, and must not rely on the generic fallback defaults in `_platform_common.py` as the source of truth.

## Decision 3: source task workspace remains isolated

Normal non-trivial platform implementation should not occur directly on central `main`. The start path should create/reuse an isolated feature workspace consistent with the repository's current multi-task safety expectations. The exact choice between a managed worktree and a feature branch plus explicit source isolation can follow existing proven platform mechanics, but ad-hoc manual `git worktree add` outside the supported entrypoint is not the normal path.

The integration copy stays clean and is mutated only for safe synchronization/reconciliation owned by the lifecycle.

## Decision 4: one publication state model

Central status/finish must use the same structured GitHub-backed state used by the platform publication code. Human-readable CLI output may wrap that model, but terminal classification is derived from authoritative state, not text matching.

At minimum the user/agent must be able to distinguish:

- local task prepared;
- branch exists only locally;
- branch pushed / no PR;
- exact-head PR draft/open;
- required checks pending/failed/passed;
- remote merge/auto-merge armed or foreground fallback;
- merged, local reconciliation pending;
- complete;
- explicit manual-review/blocker.

A green draft/open PR is always nonterminal.

## Decision 5: finish is resumable and zero-hand-off by default

For the normal automatic source policy, `finish` should progress as far as safely possible in one invocation and can be rerun after interruption. It must preserve exact-head safeguards and never manufacture a new candidate merely because remote `main` advanced after the existing PR was established.

The human should not be asked to press Merge or manually synchronize local `main` unless GitHub policy/permissions produce a real blocker or the task explicitly uses manual-review policy.

## Decision 6: test the adapter at boundaries, not GitHub itself

Integration tests should use temporary Git repositories/bare remotes and controlled GitHub/publication adapters or fixtures. They need to prove central wrapper orchestration and terminal-state semantics without depending on the developer's live repository or network.

Required regression cases include:

- clean start and unsafe-start failure;
- successful automatic publication/reconciliation;
- green draft/open PR remains nonterminal;
- resume after branch push/PR creation;
- resume after remote merge before local reconciliation;
- changed-head/exact-head safety;
- manual-review stop;
- explicit configuration resolution when no downstream project config exists.

## Upgrade / rollback

This is source-repository behavior. Rollback is a normal revert of root wrappers/config/guidance/tests; it must not require reverting the already-shipped downstream publication recovery implementation. No new external service or persistent state migration is introduced.

If implementation evidence shows a required change to shared downstream publication semantics, stop and update OpenSpec scope/specs before modifying that contract.
