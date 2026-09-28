# Design: Derived terminal obligations

The publication observation remains authoritative for exact PR merge and local main synchronization. A read-only terminal evaluator overlays required obligations from the managed task's existing provenance: linked process evidence resolution and required cleanup. Status emits a separate remote merge fact and downgrades full `complete` while an obligation is pending or unknown. Finish uses the same evidence policy before announcing terminal success.

Process evidence normally resolves by reading the linked Issue, adding the existing resolution marker, and closing an open process Issue. A new explicit operator command may record a disposition only after GitHub returns a definite 404 for an exact linked reference. It writes a bounded marker, reference, reason, source task identity, and observed 404 to the durable managed source Issue comment. The command must read back the exact marker before success. The evaluator accepts only an exact, source-bound disposition marker. Authentication failure, 403, timeout, or malformed responses cannot authorize disposition. Closed evidence remains fulfilled without mutation.

The source Issue comment is an audit record, not a second status ledger. It records an exceptional human decision about a missing external artifact; terminal state is still derived on each observation. Ordinary retries are idempotent.

Risks: GitHub permissions may make 404 ambiguous in a private repository. Disposition requires explicit operator invocation and reason and is never automatic. GitHub read failures leave status unknown/pending. Cleanup eligibility remains governed by exact worktree identity and existing safety checks.
