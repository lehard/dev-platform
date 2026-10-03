# Design: Reliable short task retrospective

## Attribution

`record` keeps `--task` as the explicit override. Without it, the task is the current branch unless the branch is unknown or the configured main branch (an integration checkout is not a task). The event gains `attribution`: `explicit`, `branch` or `unattributed`. Old events are never rewritten.

One read-side helper, `events_for_task(task, aliases)`, returns events whose `task` equals the task, plus legacy events with `task == null` whose `branch` or `run.source_issue` equals the task or one of its aliases (the managed task's source issue). Those are reported as `inferred`. All existing selections (lifecycle failures, retrospective signals) use it, so the signal the #284 browser event carried is found. Events with `task == null` that carry no usable branch or source issue, recorded within a bounded recent window, are listed as `ambiguous` in review output and checkpoint output. They are never attributed to the task being reviewed.

## Mandatory signals and dispositions

Mandatory signals are high/critical `lifecycle-*` failures and events carrying a workaround, override, recurrence or drift trigger. Each must be linked with `--event` (new finding) or classified with `--disposition <id>=resolved-in-task|already-recorded|expected-behavior` (`--lifecycle-disposition` stays accepted). The recorded event is the supporting evidence, so no second store is introduced. An event with the `known-recurrence` trigger accepts only a link, because a new occurrence of an open problem must stay visible. Stored checkpoints keep the `lifecycle_dispositions` field; it now holds dispositions for any mandatory signal, so receipts written earlier remain valid.

A failing regression test that is the intended red step is not an event and costs nothing; if a lifecycle failure event was recorded for an expected failure, `expected-behavior` explains it.

## Evidence source availability

The friction log read reports `available`, `partial` (malformed lines skipped) or `unreadable`. A non-available source must be named with `--accept-gap friction-log` for a checkpoint to be recorded, and the accepted gaps are stored in the receipt. A missing log file is a normal clean state. Only the most recent 500 log lines are checked for malformed content, so one old bad line does not become permanent ceremony. Pre-authoring state is deliberately not an evidence source (it is machine-local and may legitimately be gone).

## Requirement retrospective

`requirement_retrospective.py` uses the same helper with the Requirement as the task: events with `task == requirement` (pre-authoring and between-children work recorded with `--task`) plus inferred legacy events, with the same dispositions, gaps and ambiguous list. Child-attributed events stay with child retrospectives. Linked findings may be recorded-or-inferred events of the Requirement.

## Shared template and project questions

`review-path` outputs `template`: what happened and its basis; confirmed cause kept apart from hypothesis (unknown cause allowed); fix kept apart from workaround; recurrences and remaining problems; the action with a verifiable result or the reason for none. The template lives in code so a Copier script update reaches existing projects, and in both workflow docs.

Projects add up to five questions in the project-owned `dev-platform/retrospective.toml` (`[[question]]` with `text` and optional `paths` globs). A question applies when `paths` is absent or a changed file of the task matches (the Requirement review applies only path-less questions). Questions beyond five are ignored and reported; a missing or invalid file leaves the shared path working and an invalid file is reported as a gap line, not a block. The file is added to Copier `_skip_if_exists` with an empty commented example.

## Non-goals

No model gate, transcript or shell-history capture, new database, signed evidence, policy language, or fixes to the #284 archive, browser-runner or stale-receipt defects.
