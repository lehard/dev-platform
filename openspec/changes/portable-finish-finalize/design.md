## Decisions

- **Executor, not a new path.** finish calls the same `finalize_change` and the same review stage function the queue jobs use; there is no developer archive command.
- **Refusal.** `archive` without `--finalize` exits non-zero before any work, naming `finish` (no queue) or the queue finalize job (coordinator).
- **Evidence reuse.** Portable finalize keeps the finish rule for selected-check evidence reuse.
- **Advance refusal boundary.** The ready-receipt adapter translates a portable finalizer refusal into `RequirementExecutionError`; no ready receipt is written after a refusal. It preserves the finalizer's exact diagnostic and cause.
- **Shipped guidance.** Central and rendered OpenSpec config and explorer instructions point developers to finish or Requirement advance. Template contract tests assert the new instructions and the explicit refusal of manual archive.

- **Shared review launch stage.** `independent_review_runner.run_review_stage` owns runtime preflight and both perspective launches for portable review and queue child review. Existing callers retain their containment checks and evidence writes; portable finish requires the stage even when the optional review setting is disabled.

- **Managed-only boundary.** Finish resolves canonical provenance before entering the new finalization preflight. Only an active managed change enters that path; quick tasks and archived delivery recovery keep the established publication gates. The finalizer imports required review machinery only after proving an active managed change.
