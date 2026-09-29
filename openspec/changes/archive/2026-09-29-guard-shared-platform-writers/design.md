# Design: Checked shared output boundary

## Ownership and guarantee

The guarantee applies to platform-owned files in paths already registered by shared_workspace, not to all files in the checkout. Reuse atomic_write_text and ensure_shared_path to publish and verify a specific output. A supported Process Health Review report command accepts content on stdin and a basename within the configured friction_reports directory; it rejects traversal/symlinks and reports a failure if the published inode lacks group write. It does not inspect or repair neighboring reports.

## Future writer guard

Document and test the contract at writer entrypoints. Add a focused regression fixture that runs the report publication with a restrictive umask and another fixture that deliberately creates 0644 to prove the nearest check fails before success. New supported platform-owned writers use the exact-output verification API. A CI source guard records the existing direct file-creation call sites by module/function/call count and fails when a new direct creation site appears without review. The guard recognizes common Python file creation APIs; it is review friction, not a sound static proof for every possible library or external editor. The read-only shared-workspace audit remains the broad completion backstop for registered paths. Avoid global automatic repair because ownership by OS user does not identify which agent created a file.

## Failure and compatibility

The report writer does not alter another agent's files or the Git common directory. Existing advisory reports remain machine-local and non-authoritative. The existing shared_workspace audit stays as the final backstop for registered paths. External editors cannot be prevented from creating a bad file; the documented post-review shared_workspace check catches that case before the report is declared finished.
