## Why

For a coordinator-managed candidate the developer-side fresh-base gate repeats work the queue already does. `select_checks.py --execute --evidence` and `finish` refuse a head that does not contain freshly fetched `origin/main`, so each main advance means `dogfood_task.py reconcile`, another full selected-check run (~10 min), a refreshed `verification.md`, a new friction checkpoint and re-admission. On 2026-10-10 BR-549 and BR-441 looped on this several times because main advanced during the full run. Meanwhile the queue merges current main into the admitted head (`_prepare`), waits for required checks on the integrated head and merges only when they pass (#480, #493), and the independent review already survives a clean irrelevant main merge.

## What Changes

- A shared helper classifies a task head against freshly fetched `origin/main` as `fresh` (contains main), `behind-disjoint` (does not contain main, the files main changed since `merge-base(HEAD, origin/main)` are disjoint from the files the task changed since that merge base, and `git merge-tree --write-tree` reports no conflict) or `reconcile-required` (overlapping files or conflict), naming the overlapping files or the conflict; a missing merge base fails explicitly.
- For a coordinator-managed candidate (the repository's publication contract is the coordinator queue), evidence-producing selected-check execution, `finish` developer handoff and admission accept `behind-disjoint` and record the observed main and merge base in the evidence/handoff output. `reconcile-required` blocks before any expensive command with the named files or conflict and the reconcile command.
- `dogfood_task.py status` reports `behind-disjoint` as not requiring reconcile.
- Outside the coordinator contract (quick or managed tasks published without the queue, downstream projects, protected CI) the fresh-base rule is unchanged.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: "Expensive validation requires a fresh task base" and "Freshness drift is visible before another expensive validation run" gain the bounded coordinator-candidate exception.

## Impact

`template/scripts/_platform_common.py`, `template/scripts/select_checks.py`, `template/scripts/project_publish.py`, `template/scripts/finish_task.py`, `template/scripts/task_reconciliation.py` and their tests. The queue (`publication_queue.py`) is unchanged: it already merges main and gates on integrated-head required checks. Downstream renders keep today's behavior because they do not use the coordinator contract.

## Non-goals

Reuse of checks between children of a multi-child Requirement (BR-483); reuse after OpenSpec archive (BR-468); the Requirement retrospective identity; queue or branch-protection changes.
