## Why

A candidate whose only integration problem is a failed derived merge with a clean plain merge (PR #730) waits for a writer-capable worker, although the worker's integration-repair harness merges such a candidate without calling the writer. No hosted executor may run `integration-repair` (it can hold a writer and the provider token), so this deterministic case still waits for an operator. The owner decided on 2026-10-26 that this LLM-free case runs in hosted CI as its own kind.

## What Changes

- New job kind `integration-merge` (`lifecycle_workers.JOB_KINDS`), not a writer kind: no provider, no route, no `--llm-command`.
- `publication_queue._integration_repair` offers it when the red gate is `integration` and `merge_conflicts(head, main)` is empty; the state stays `integration-repair-pending` (same bound and lifecycle), the red gate carries `merge_only: true`, so the interrupted-job republish and the validated-push recovery keep the kind, and the T1 "Repair needed" comment is not posted for it.
- `integration_contour`: `run_claimed_integration_repair` and `execute_integration_repair` accept the kind; a conflict or a `required-checks` red gate fails it by name without starting a writer; the existing failure path then offers `integration-repair` in the next attempt.
- `work-next --run --kinds integration-merge` needs no `--llm-command`; `--writer` does not apply to it.
- `hosted_workers`: a new `integrate` class (`integration-merge`, no provider, no tools, contents and pull-requests write); `integrated` is a resulted hosted outcome. The workflow needs no change beyond the class table (it installs the Claude CLI only for `review`).
- Docs: `docs/engineering/hosted-lifecycle-workers.md` class and placement tables.

## Impact

- `template/scripts/lifecycle_workers.py`, `template/scripts/integration_contour.py`, `template/scripts/publication_queue.py`, `template/scripts/candidate_lifecycle.py`, `template/scripts/hosted_workers.py`.
- Specs: lifecycle-workers (two hosted requirements modified), publication-queue (one added, one modified).
- Tests: hosted workers, lifecycle workers / integration contour, publication queue, candidate lifecycle recovery.
