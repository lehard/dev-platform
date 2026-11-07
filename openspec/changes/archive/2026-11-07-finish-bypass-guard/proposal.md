## Why

A branch pushed by hand and opened with `gh pr create` merges when `validate` is green, with no checkpoint or review behind it. Check evidence of a quick task stays in the Git directory of its worktree, so CI cannot see it. `finish` has to leave a trace in the content of the pull request.

## What Changes

- With `delivery_trace = true` in `[settings]` of `dev-platform/checks.toml`, `finish` adds, right before publication and after all its gates, an empty commit carrying `Dev-Platform-Finish: <tree>`. A head that already carries a valid trace gets no new commit.
- An early step of `validate` checks the pull request head commit and refuses a head without a valid trace, naming the reason and the next command.
- `reconcile` adds the trace to its new head only when the published head carried one.
- The way out of a wrongly refusing guard is documented and needs no change to GitHub protection settings.
- A rendered project has no setting, so it neither writes nor checks a trace.

## Non-goals

Protection against deliberate forgery, signatures or services, exception labels or lists, changing GitHub protection settings, behavior change in downstream projects, release and rollout.
