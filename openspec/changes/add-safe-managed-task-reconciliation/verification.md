# Verification: Add safe managed-task reconciliation

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, task checklist, current specifications and active deltas, plus structural OpenSpec validation and focused/full lifecycle regression tests.

## Semantic review

- Completeness: the active delta covers early freshness status, explicit non-rewriting reconciliation, published exact-PR ancestry, dirty/conflict/changed-head blockers, validation invalidation, same-PR continuation, idempotence and central dogfood delegation.
- Correctness: `task_reconciliation.py` fetches authoritative main only for mutation, uses a normal Git merge, never stashes/resets/rebases/force-pushes, and preserves an open exact PR through an ordinary fast-forward push after exact base/head/owner checks. `finish_task.py` stops before expensive validation when freshness requires reconciliation; its read-only status uses `ls-remote` without updating local tracking refs.
- Coherence: the `publication-recovery` delta explicitly replaces the former behavior that allowed an old exact PR to continue after base advancement, so current specs plus this active delta match the implementation. The central adapter delegates instead of introducing a second delivery state machine.

## Executed evidence

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate` — passed (`3 managed, 7 candidate, 3 excluded`).
- `python3 scripts/run_test_groups.py --all` — passed; coverage proved 550 discovered/declared tests with no gaps or duplicates.
- `openspec validate add-safe-managed-task-reconciliation --strict` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- Targeted regression tests cover issues #190 and #219 plus unpublished, exact-open-PR, dirty, merge-conflict/resume, changed-remote-head and already-current paths.
