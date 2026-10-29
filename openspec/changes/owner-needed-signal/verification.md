OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the two spec deltas, proposal, design and tasks; targeted unit tests (test_agent_signal, test_lifecycle_overview, test_overview_agent_sessions, test_shared_writer_guard, test_platform_module_identity); repository-owned selected checks recorded in automated-checks.json
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Storage on the task's agent-board entry (no new configuration key or operator path); the signal ends with the entry. Decided in the ADD, no open choice.
- Material path with one intent: the command and the overview section ship together.

## Completeness

- `agent_signal.py raise|resolve` stores, collapses and resolves signals; task identity comes from the caller's own worktree and its active board entry; missing capability, board file, entry, question or signal fail with a named error (`test_agent_signal`).
- `lifecycle_overview.py` prints an "Owner needed" section and `owner_needed` in `--json`, with explicit lines for a disabled or unreadable board.
- The source wrapper, the hotfixable classification, the test group entry, the manifest and the coordinator guide are updated.

## Correctness

- An exception inside the board lock leaves the board unwritten (the writer persists only after the block completes), so a rejected signal stores nothing; the test covers a worktree without an entry.
- The identity is task plus whitespace-normalised question; the same text on another task is a separate signal; the same text after resolution opens a new one.

## Coherence

- Spec deltas, design, docs and tests state the same contract: report a question only, no decisions, no notifications, no new configuration.

## Not verified / limits

- Not exercised from a real agent session against the live board; covered by tests over a temporary git repository with worktrees and a temporary board file.
- The age is computed from the first raise time; clock skew between machines is not handled (single operator machine).
