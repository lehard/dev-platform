## Why

`model_routing.postcheck` (used by `record_claude_execution`) treats any integration `HEAD` movement as a containment violation. Codex has a narrow classification (`delegated_write_guard._classify_containment` with `verify_remote_fast_forward`) because native hard containment proves the child could not write the integration checkout. Claude delegations are detection-only: the child has a shell, so matching `origin/main` alone does not prove who moved `HEAD`. On a shared integration checkout sibling tasks merge routinely, so correct contained Claude work is stranded (lehard/development-backlog#510).

## What Changes

- Every platform code path that fast-forwards the integration checkout's main branch appends an integration-advance receipt (before, after, recorded `origin/<main>`, acting worktree, tool, pid, time) to an integration-owned log.
- A shared classifier decides whether a pure head move is a verified concurrent advance. Codex keeps its existing native-hard rule. Claude additionally requires an unbroken receipt chain from the pre-run head to the current head whose every receipt names an acting worktree other than the delegated one and an `after` equal to the `origin/<main>` it recorded.
- `record_claude_execution` records a verified advance next to the unchanged raw observation; any path change, non-fast-forward, ref mismatch or missing/broken chain stays a violation.
- `recover-external-advance` gains a bounded Claude form for a historical false violation recorded before receipts existed: bound to the exact friction event, the route's open delegation and recorded timing, and the `origin/<main>` reflog; it is not a generic override.

## Capabilities

### Modified Capabilities

- `model-routing`: detection-only writers accept a recorded integration advance.

## Impact

`template/scripts/delegation_containment.py`, `template/scripts/delegated_write_guard.py`, `template/scripts/model_routing.py`, the integration fast-forward sites (`finish_task.py`, `project_sync.py`, `publication_queue.py` when it advances the integration checkout), tests (`tests/test_model_routing.py`, `tests/test_delegated_write_guard.py`, new tests), `docs/engineering/model-routing.md`.

## Non-goals

Weakening Codex containment; hung-process handling (#376); routing tiers.
