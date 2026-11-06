## Why

Worker code from main reads the candidate's contract. A new required key gives `PlatformConfigError` on a candidate from an older base, and three attempts burn. A trusted contract is installed only for composition post-merge checkouts.

## What Changes

- The job kind fixes the contract source in advance; the outcome of a schema check never picks it.
- Review and repair checkouts always receive the public contract of the worker's trusted revision.
- Finalize, including composition, always reads the candidate contract. An invalid or unreadable contract at the exact head is a refusal before claim, naming the key and the exit: reconcile with main, then `finish`, which re-admits the head from `finalize-pending`. No budget is spent.

## Impact

- `template/scripts/lifecycle_workers.py`, `pr_review_gate.py`, `post_review_finalization.py`; tests; `docs/engineering/chat-coordinator.md`; manifest.
- No queue state changes, and candidate content and identity stay the same.
