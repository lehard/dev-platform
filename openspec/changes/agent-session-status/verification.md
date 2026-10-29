OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-sessions and chat-coordinator deltas, proposal, design and tasks; 25 new unit tests plus the existing lifecycle-overview and shared-writer-guard tests; a scripted run of the real hook CLI over stdin with a stand-in session process; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (bounded evidence, no ADD). Executor choices left by the Requirement: one JSON file per session in an explicit state directory; hooks installed only into a settings file the owner names (user-level covers task worktrees, which do not load the integration checkout's local settings); the overview reads `[agent_sessions]` from the platform configuration and says "not configured" without it.
- Hook root PID is the hook's parent process; its start time is recorded so a reused PID can only produce `ended`/`unknown`.

## Completeness

- Transitions (working -> waiting-permission -> working -> idle -> ended), permission wait kept through another tool's PreToolUse/PostToolUse, AskUserQuestion, idle/permission notifications, StopFailure as `limit-or-error`, unknown events and unsafe ids as errors, Codex turn-complete only: `tests/test_agent_sessions.py`.
- Liveness: killed session without SessionEnd -> `ended (process-gone)`, reused PID -> `ended`, failed `ps` or `kill` -> liveness `unknown` with the state unchanged, silence beyond `stale_after` -> `unknown`, ended records hidden after retention with files kept.
- Hooks print nothing, exit 1 (never 2) on a bad payload, a missing state directory or broken arguments; settings merge is idempotent, keeps foreign hooks, refuses malformed JSON and conflicting hooks, `--remove` restores the file, `--print` writes nothing.
- Overview: attachment by branch (developer session after handoff), unattached list, not configured, partial configuration, unreadable registry, rendering: `tests/test_overview_agent_sessions.py`; the 45 existing overview tests pass.
- Docs: `docs/engineering/agent-sessions.md` (status table, liveness, Codex limits, configuration, owner install/rollback); pointer in `chat-coordinator.md`; manifest, protected-surface class (hotfixable), test groups and the shared-writer baseline entries updated.

## Correctness

- Only `agent_sessions.py` computes status; `lifecycle_overview.py` only reads and renders it and writes nothing to GitHub or to the registry.
- The scripted run drove the real CLI (`hook` over stdin, then `list`): waiting-permission -> working -> limit-or-error, and after the stand-in session process was killed `list` showed `ended`.

## Coherence

- Spec deltas, design, tasks and docs agree on the status vocabulary and rules.

## Not verified / limits

- Not run inside real Claude Code sessions: the hooks are not installed on this machine (owner step), so the real event payload field names (`notification_type`, `error` on StopFailure, `reason` on SessionEnd) follow the documented hook schema and are untested against a live session. Unknown values degrade to `unknown`/detail text, never to `working`.
- A Codex session can only be `idle` (turn complete); all other Codex states are unavailable by design.
- The root PID is the hook's parent; if Claude Code launches hooks through a wrapper shell the recorded PID is the wrapper's and can show `ended` early. Checking this needs one real installed session.
