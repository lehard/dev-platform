## 1. Registry
- [x] 1.1 `agent_sessions.py`: record model, locked atomic writes, Claude transition rules, Codex notification, explicit errors.
- [x] 1.2 `list` with liveness (pid + start time), stale and ended retention; `hooks --print|--install` for a named settings file.

## 2. Overview and docs
- [x] 2.1 `lifecycle_overview.py`: read the registry, attach sessions to candidates by branch, list the rest, explicit not-configured/unreadable.
- [x] 2.2 `docs/engineering/agent-sessions.md` (status table, Codex limits, owner install/rollback), pointer in `chat-coordinator.md`; manifest and test-group classification.

## 3. Verification
- [x] 3.1 Tests: transitions incl. permission not cleared by other tool, limit, killed session, failed check, silent session, hook never blocks, settings merge, Codex, overview attachment and not-configured.
- [x] 3.2 Run the hooks against a real recorded Claude Code event sequence; full validation and semantic verification.
