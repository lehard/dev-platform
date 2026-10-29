## Why

The owner decided on 2026-10-22 to extend the BR-748 behind-mergeable rule to quick tasks: a full validation run takes about 35 minutes, `main` moves meanwhile, and `finish` refused the stale quick task (lehard/dev-platform#683). Quick PRs lehard/dev-platform#718 and #726 delivered the behavior: `queue_integrated` treats a quick task without canonical managed provenance under the enabled coordinator queue like a coordinator-managed candidate, and the validation gate, `finish`, the publish step and reconcile read that one predicate and the one BR-748 classifier. The accepted spec still grants the exception only to coordinator-managed candidates, so the code is wider than the contract.

## What Changes

- `platform-lifecycle` "Expensive validation requires a fresh task base": the second bounded exception covers a task the publication queue integrates, a coordinator-managed candidate or a quick task under the enabled coordinator queue, with the unchanged BR-748 conditions.
- New scenarios: a quick task behind a cleanly mergeable main is handed off without reconcile; a quick task with a real conflict must reconcile. The non-coordinator scenario keeps its name and now names the tasks the queue does not integrate.
- No behavior change; no managed-candidate rule changes.

## Impact

- `openspec/specs/platform-lifecycle/spec.md` only; existing tests (`tests/test_task_base_matrix.py`, `tests/test_select_checks.py`, `tests/test_task_freshness.py`) are the acceptance evidence, extended only if they fall short.
