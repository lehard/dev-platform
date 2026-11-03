## Decisions

- **Same function.** `finalize_change(..., context="composition")` selects `requirement_composition.require_archive_evidence` as the review evidence source; every other precondition is identical to the queue finalize job.
- **All children first.** Composition collects every child's unmet preconditions before archiving the first child, so a partial composition archive never starts.
- **Shared preflight.** `finalize_change_problems` exposes the same read-only preconditions used by `finalize_change`. Composition evaluates it for every active child before calling `finalize_change(..., context="composition", requirement=...)` in manifest order. The Requirement identity is explicit and required for this context; no environment variable selects an archive mode. Already archived children remain resumable.
- **Commit and paths.** The composition commit message and path validation are unchanged.
