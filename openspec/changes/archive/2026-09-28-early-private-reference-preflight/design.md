## Placement

Call the current `check_private_backlog_refs.py` from `observe_completion_blockers` or its immediate read-only preflight before `run_checks`. Keep the later call in `finish_task.py` and the `project_publish.py` check. The early call must be cheap and read-only. Use the same guard CLI and regex semantics for every gate.

## Diagnostics

Return a bounded surface-category summary (candidate file/path, branch, commit message, proposed PR text) and opaque file fingerprints. Never print private identifiers or raw offending text. Point to the existing `private_lineage.py` opaque handle process. Preserve fail-closed behavior when guard configuration or Git inspection fails.

## Verification

Regression tests create an isolated candidate with a private reference in verification evidence and a new commit message, assert preflight rejects before `run_checks`, then assert a clean candidate reaches normal validation and publication still rechecks.
