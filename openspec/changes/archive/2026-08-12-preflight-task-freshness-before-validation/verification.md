# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic completeness/correctness/coherence review plus targeted freshness regressions and full local platform validation
Automated-Checks-Evidence: automated-checks.json

## Scope reviewed

Reviewed the managed proposal, design, delta requirement, task-start flow, the platform check selector, and the shared fetch/ancestry primitives.

- **Completeness:** task start now records a freshly fetched `origin/<main>` observation; every platform-mode selection that will execute the configured full/protected command set re-fetches and verifies exact `HEAD` ancestry before the first command.
- **Correctness:** equal/ahead task heads continue unchanged; behind/diverged heads stop with their observed relation and a resumable rebase/reconcile-first direction; fetch/ref failures are explicit blockers. The helper performs no reset, rebase, force-push, or other reconciliation.
- **Coherence:** `harness_mode=project` bypasses the new selector gate, while protected-main/exact-head publication behavior remains in the existing lifecycle. The change reuses `fetch_main` and `relation`; it does not create validation receipt reuse or a second sync system.

## Automated evidence

- `python3 -m unittest tests.test_task_freshness tests.test_managed_task tests.test_select_checks -v` — 53 tests passed.
- `python3 scripts/select_checks.py --mode protected-full --execute` — the real task worktree passed the new freshness gate; compile and registry checks succeeded before the suite was rerun as a single controlled process.
- `python3 -m unittest discover -s tests -v` — 421 tests passed in 208.253 seconds.
- `openspec validate preflight-task-freshness-before-validation --strict --no-interactive` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed before task completion/archive.

`copier` is not installed in this environment (`copier: command not found`), so a separate render/doctor smoke was not performed. Template/runtime coverage is included in the full local suite.
