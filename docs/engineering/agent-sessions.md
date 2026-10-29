# Agent session status (BR-887)

The platform knows which Claude Code and Codex sessions are alive on the operator Mac and what each is doing. `template/scripts/agent_sessions.py` computes the status from hook events and keeps one JSON file per session in a state directory; `lifecycle_overview.py`, the coordinator and the board only read it. Hooks change nothing in a session: they print nothing, take no permission or stop decision, and a failure is a non-blocking exit code 1 with one stderr line (never the blocking code 2).

## Status

| Status | Claude Code event that sets it | Cleared by |
| --- | --- | --- |
| `idle` | SessionStart, Stop | UserPromptSubmit and tool events |
| `working` | UserPromptSubmit, PreToolUse, PostToolUse | Stop, a wait or SessionEnd |
| `waiting-permission` | PermissionRequest, Notification `permission_prompt` | PostToolUse of the same tool, a new prompt, Stop, StopFailure, SessionEnd. Another tool's events do not clear it |
| `waiting-input` | PreToolUse of AskUserQuestion, Notification `idle_prompt` / `elicitation_dialog` | PostToolUse of AskUserQuestion, a new prompt, Stop, SessionEnd |
| `limit-or-error` | StopFailure (the error type is kept) | a new prompt or SessionStart |
| `ended` | SessionEnd, or a verifiably gone process | resume with SessionStart |
| `unknown` | no event for `stale_after_seconds`, or a state that cannot be established | the next event |

Each record also holds provider, session id, root PID and its start time, working directory, project (git top level), branch, task (worktree name), `state_since`, `updated_at` and the last event.

## Liveness

`list` checks the root PID and its recorded start time. A process that is gone, or whose PID now has another start time, is `ended` (`process-gone`) although no SessionEnd arrived. A failed check (`ps` error, timeout, unexpected `kill` error) leaves the liveness `unknown` and the state unchanged: a temporary failure never turns a live session into a dead one. A session with no event for `stale_after_seconds` is shown `unknown (silent for N min)`, never `working`. Ended records are listed for `ended_keep_seconds`; readers never delete files.

## Codex

Codex reports only its turn-complete notification (`agent-turn-complete`, passed as the last argument of the configured `notify` program). It is recorded as `idle`. Working, waiting-for-permission, waiting-for-input and limit states are not available for Codex and are not inferred.

## Configuration and the overview

The overview reads `[agent_sessions]` from the (external operator) platform configuration; with no section it prints `Sessions: not configured`:

```toml
[agent_sessions]
directory = "~/.local/state/dev-platform/agent-sessions"
stale_after_seconds = 21600
ended_keep_seconds = 86400
```

Sessions appear on the candidate whose PR head ref equals the session's branch (including a developer session after handoff); the rest are listed under "Sessions not attached to a candidate PR". An unreadable registry is printed as such.

## Owner steps (nothing installs automatically)

Hooks must be in a settings file that sessions load. Task worktrees do not load the integration checkout's `.claude/settings.local.json`, so the user-level file covers every worktree. Review the block, then install it into the file you choose:

```bash
python3 scripts/agent_sessions.py hooks --state-dir ~/.local/state/dev-platform/agent-sessions --print
mkdir -p ~/.local/state/dev-platform/agent-sessions
python3 scripts/agent_sessions.py hooks --state-dir ~/.local/state/dev-platform/agent-sessions --install --settings ~/.claude/settings.json
```

Rollback removes exactly those entries and leaves other hooks alone:

```bash
python3 scripts/agent_sessions.py hooks --state-dir ~/.local/state/dev-platform/agent-sessions --remove --settings ~/.claude/settings.json
```

Running sessions pick up hook changes after a restart. Read the registry with `python3 scripts/agent_sessions.py list --state-dir <dir> --stale-after 21600 --ended-keep 86400`.
