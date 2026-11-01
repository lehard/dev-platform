## Decisions

- **Collected gates.** Each existing gate becomes a check returning problems instead of raising; `finalize_change` runs them all, then raises one `SystemExit` naming every problem and its fix. Gates that need an earlier one (for example committed-diff checks after package presence) report the dependency explicitly instead of being skipped silently.
- **No review from archive.** The non-finalize branch that called `ensure_review_evidence` calls `require_review_evidence`; a missing or stale review is one listed problem naming the review command.
- **Executor.** The finalize job keeps its disposable checkout, commit message and path validation; only the archive call changes. Composition and portable callers move in later children.
