## Why

The board showed "nothing is happening" while a developer was finishing a PR (2026-10-28): after handoff the developer's claim is released and nothing records that the session is alive, busy or waiting for a person (BR-887). The platform needs one honest source for "which sessions are alive and what each does", read by `lifecycle_overview.py`, the coordinator and the board.

## What Changes

- New `template/scripts/agent_sessions.py`: a hook ingester (`hook`), a registry reader (`list`) and a settings renderer/installer (`hooks --print|--install`). One JSON file per session in an explicit state directory; the platform computes status; viewers only read.
- Status model: `working`, `idle`, `waiting-input`, `waiting-permission`, `limit-or-error`, `ended`, plus `unknown` where a source is unavailable. Transitions follow the hook events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, Notification, Stop, StopFailure, SessionEnd). `waiting-permission` is cleared only by the matching tool's PostToolUse, a new prompt, Stop, StopFailure or SessionEnd, never by another tool's event.
- Liveness: the session's root PID and its start time are recorded; a session whose process is verifiably gone (or whose PID was reused) is `ended`; a failed check leaves liveness `unknown` and never ends the session; a live-looking session with no events for the retention time is reported `unknown`, not `working`.
- Hooks change nothing in the session: no stdout, no input, exit 0 on success, a non-blocking non-zero exit with a message on failure (never exit 2).
- `lifecycle_overview.py` reads the registry (directory from the external operator configuration) and shows each session next to the candidate whose PR head ref equals its branch, and the rest under "Sessions"; an unconfigured or unreadable registry is shown as such.
- Codex: only the turn-complete notification exists; it maps to `idle`. Working, permission and limit states are reported as unavailable for Codex.
- Docs: `docs/engineering/agent-sessions.md` with the status table, the owner install and rollback commands.

## Impact

- `template/scripts/agent_sessions.py` (new), `lifecycle_overview.py`, `docs/engineering/chat-coordinator.md` (short pointer), `docs/engineering/agent-sessions.md` (new), tests, platform manifest and test-group classification.
- Specs: agent-sessions (new capability), chat-coordinator (added requirement).
