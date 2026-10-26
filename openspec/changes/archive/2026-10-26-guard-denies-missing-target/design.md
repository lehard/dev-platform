## Context

The structured-write fallback guard is an ephemeral PreToolUse hook script rendered by `render_pretooluse_guard_script` and matched on `Write|Edit|NotebookEdit`. It already denies unreadable and malformed payloads; only the "no recognized target key" branch answers `allow`.

## Decisions

- Deny, never allow, a payload without `file_path`, `path` or `notebook_path`; the reason names the expected keys and the tool name when present. No other branch changes.
- No configuration switch: the guard has no legitimate case of a target-less structured write.

## Risks

- A future Claude Code tool matched by the hook with a different target key would be denied until the key list is extended. That is the intended fail-closed behavior.
