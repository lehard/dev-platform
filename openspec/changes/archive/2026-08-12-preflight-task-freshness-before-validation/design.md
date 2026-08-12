## Context

The current lifecycle already has remote comparison at start/publication. The expensive rework in `dev-platform#178` happened because those boundaries do not protect the middle of the task, especially the point where a long full validation suite begins. A task can therefore spend significant compute/time validating a head that already needs reconciliation with main.

## Decisions

### Freshness is an ancestry fact, not a timer

Do not model freshness as task age or elapsed time. Refresh the configured remote main and determine the Git relationship between the exact task head and that authoritative ref.

### Fail before expensive evidence, not after it

The key guard belongs immediately before a validation path that is expensive and intended to support publication/OpenSpec verification. Cheap local development checks MAY still run earlier; this change does not turn every command into a network-gated operation.

### Reuse current Git/sync primitives

Use the existing remote/fetch/relation concepts rather than creating a second sync engine. Implementation preflight should identify all supported full/protected-validation entrypoints and place one reusable check so semantics do not drift between direct CLI, finish/archive, and central dogfood paths.

### Do not automate destructive reconciliation

When stale/diverged, report the exact relationship and recovery direction. Existing task workflow remains responsible for safe rebase/reconciliation; this change does not introduce force operations.

## Risks / Trade-offs

- A remote fetch adds small latency before expensive validation, intentionally trading a cheap network operation for avoiding repeated long suites.
- Offline/unavailable remote state can block authoritative full validation; this is preferable to producing delivery evidence from an unverified stale base.
- The guard must not accidentally apply project-owned product validation semantics when `harness_mode=project`; only platform-owned lifecycle boundaries are in scope.
