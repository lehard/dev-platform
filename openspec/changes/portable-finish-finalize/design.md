## Decisions

- **Executor, not a new path.** finish calls the same `finalize_change` and the same review stage function the queue jobs use; there is no developer archive command.
- **Refusal.** `archive` without `--finalize` exits non-zero before any work, naming `finish` (no queue) or the queue finalize job (coordinator).
- **Evidence reuse.** Portable finalize keeps the finish rule for selected-check evidence reuse.

- **Shared review launch stage.** `independent_review_runner.run_review_stage` owns runtime preflight and both perspective launches for portable review and queue child review. Existing callers retain their containment checks and evidence writes; portable finish requires the stage even when the optional review setting is disabled.
