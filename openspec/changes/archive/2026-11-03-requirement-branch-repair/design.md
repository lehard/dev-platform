## Decisions

- **Reuse the repair job.** No new writer path: the command records a repair request for the composition and the queue runs the `repair` job (same provider routing, writer scope = the PR's changed paths, `_forbidden` receipts).
- **Regenerate, then validate.** After the writer finishes, `regenerate_declared_files` runs, then `validate_children`; any receipt digest mismatch fails the job explicitly, nothing is restored silently.
- **Gates afterwards.** A repaired head is a changed identity: composition review, finalize and full checks follow the normal path.
- The command refuses a branch that is not an assembled composition with a complete manifest.
