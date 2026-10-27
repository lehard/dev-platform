## Context

- `_cleanup_target` returns `"completed" if errors else (...)`, so recorded errors read as success.
- `_cleanup_all` already says `completed-with-errors`; `main` exits 1 only for a refused target.
- The post-merge `cleanup` job (`integration_contour.local_cleanup`) reads `errors` directly and blocks; it is unaffected.

## Decisions

- **Status names stay, the lie goes.** `failed` is new only for the targeted cleanup with errors; `completed-with-errors` for `--all` is kept because it names partial removal truthfully. The exit code is the signal callers rely on, so any error or refusal is non-zero.
- **No change to what is removed.** Eligibility, the deferred-target contract and the pending report are unchanged.
