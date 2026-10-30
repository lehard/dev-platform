## Why

On PR #809 (2026-10-30) the coordinator finalize job at the reviewed head pushed its archive commit and was then released with a worker error, so the newest coordinator record stayed `finalize-pending` at the reviewed head. After `main` moved, the developer reconciled (merge only, task content unchanged) and pushed a descendant head. No supported path could re-admit it: `publication_queue._supersession` accepts a new developer head only from `READMISSION_STATES`, which lacks `finalize-pending`, and the archived change is not re-opened for a handoff because `DEVELOPER_FIX_STATES` lacks it too. Friction: lehard/dev-platform#810.

## What Changes

- `finalize-pending` joins `READMISSION_STATES` and `DEVELOPER_FIX_STATES` in `template/scripts/publication_queue.py`. A finalize job is bound to its head, so once the PR head moved it can never run; the developer handoff of a descendant head supersedes it, exactly as for an unclaimed review, repair or integration-repair job.
- Unchanged guards refuse by name: a live claim on the finalize job, a handoff for another task, a head that does not descend from the proven head.

## Impact

- `template/scripts/publication_queue.py`, `tests/test_queue_archived_readmission.py`, `tests/test_publication_queue.py`, platform manifest.
- Spec: publication-queue (new requirement for finalize-pending re-admission).
