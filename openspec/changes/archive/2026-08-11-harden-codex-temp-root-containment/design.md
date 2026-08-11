## Context

The current guarded delegation path already has two complementary protections: pre-write runtime enforcement when available and a content-aware integration snapshot/post-check. Codex on supported macOS/Linux runtimes is currently classified `HARD` when `codex exec --help` advertises `--sandbox workspace-write`. Live acceptance showed that this sandbox can still allow writes under system temp roots independent of `--cd`, so capability detection based only on the CLI flag is insufficient to support the stronger wording that the writable root is restricted exclusively to the assigned worktree.

## Decisions

### Define HARD around protected repository paths, not the entire filesystem

The platform does not need to prove that the child cannot write anywhere outside the assignment. It needs to prove that the child cannot pre-write mutate protected repository paths outside the assigned worktree. Runtime-added writable roots therefore matter when they overlap integration/managed repository topology.

### Normalize runtime writable roots and repository paths

The Codex adapter SHALL build a small set of proven extra writable roots from the runtime/OS contract (at minimum the observed system temp roots where applicable), normalize them with realpath semantics, and evaluate containment against normalized `integration_root`/`assigned_worktree`. This remains deliberately narrow; do not guess arbitrary writable locations without evidence.

### Fail closed for strict hard requirements

If the topology makes hard repository containment unprovable, `require_hard=True` fails before child launch. When hard is optional, the existing detection-only path is the fallback and inherits its clean-integration precondition.

### Keep the post-check

Even a `HARD` result retains the content-aware post-check. It protects against runtime regressions, capability-detection errors and future sandbox behavior changes.

## Risks / Trade-offs

- Runtime temp-root semantics may vary by Codex/OS version. Keep the modeled roots explicit and testable; do not claim support that was not proven.
- Over-conservative downgrade is acceptable; false `HARD` is not.
- Do not attempt to replace or patch the OS sandbox in this change.

## Non-Goals

- redesign Claude containment;
- add a new sandbox implementation;
- forbid system temp writes globally;
- change publication/rollout/managed-task behavior;
- turn this edge case into a broader filesystem policy engine.
