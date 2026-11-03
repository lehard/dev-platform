## Why

A managed package exceeding GitHub's comment limit can fail only after its Issue has already been created, leaving an incomplete task.

## What Changes

Before the first GitHub write in managed creation, estimate the complete serialized package comment against the coordinator-selected limit of 65,536 Python characters. Include a proven upper bound for the unknown Issue number, and explicitly reject estimates over the limit. Preserve successful publication, package format and Issue layout. No splitting or recovery of existing Issues.

## Impact

Managed task creation, its regression tests and the managed-task-intake specification.
