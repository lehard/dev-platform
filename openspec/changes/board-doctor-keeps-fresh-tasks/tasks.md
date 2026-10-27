## 1. Board classification
- [x] 1.1 Record `base_head` (registered branch head) in `agent_board.py start` entries.
- [x] 1.2 In `_status`, classify an ancestor-of-main branch as merged only with own-commit or exact-PR proof; otherwise add a named `unproven-merge-*` problem.
- [x] 1.3 Name the reason for each `unproven-merge-*` problem in `doctor` text and JSON output.

## 2. Verification
- [x] 2.1 Regression tests: a fresh registered task at the main tip survives `doctor --fix`; a merged and abandoned task is removed; legacy, unknown-base and fast-forward-without-proof entries are kept with named reasons; existing tests updated to register `base_head`.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
