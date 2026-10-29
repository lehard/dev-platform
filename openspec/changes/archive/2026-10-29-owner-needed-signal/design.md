# Design: Owner-needed signal

## Command and identity

A portable template script, exposed in the source repository through the usual thin wrapper, offers `raise` (question text) and `resolve` (signal id, resolver name). `raise` finds the caller's board entry by the caller's own worktree; there is no default task and no task argument that can name another worktree's task. A missing board capability, a missing board file, no active entry for the worktree, or an empty question stops with an error that names the cause.

## Storage and lifecycle

Signals are kept in an optional `signals` list on the board entry, written under the board's existing lock through the board's own writer, so the shared-writer guard stays valid. Each signal holds an id (derived from the task and the normalised question), the question, project, task, branch, `raised_at`, `last_raised_at`, a raise count and, once resolved, `resolved_at` and `resolved_by`. The entry's removal when the task finishes ends its signals; no separate store, configuration key or operator path is introduced.

## De-duplication and resolution

The normalised question (trimmed, whitespace collapsed, case preserved) plus the task gives the identity. Raising an open signal again updates `last_raised_at` and the count and prints the existing id. Resolving marks it resolved; a resolved signal is not shown, and raising the same text again opens a new signal. Resolving an unknown or already resolved id is an explicit error.

## Visibility

`lifecycle_overview.py` reads open signals read-only from the board and prints an "Owner needed" section (question, project, task, age) in the default text and in `--json`. An unconfigured or unreadable board is printed as such, not omitted, like the session registry. The coordinator guide names the section as part of the overview it already starts from.

## Out of scope

Notifications and rendering (board application), automatic answers, new configuration. New scripts are classified in the protected surface and the manifest as the platform requires.
