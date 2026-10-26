## 1. Routing policy
- [x] 1.1 Add the `balanced-parent` policy and the explicit `delegate` request to `_retention_policy_for`/`prepare`; `_retention_policy` never derives retention for a recorded delegated plan.
- [x] 1.2 Add `--delegate` to `prepare`, `dispatch-claude` and `dogfood_task.py route-claude`; `dispatch_codex` requests delegation; the retained Claude handoff output names `record-retained-execution` as the next step.

## 2. Write-time gate
- [x] 2.1 Add `check_task_write` and the `write-gate` PreToolUse hook command with explicit deny messages and next steps.
- [x] 2.2 Install the hook idempotently from `agent_doctor.py` into the integration checkout's `.claude/settings.local.json`; fail explicitly on malformed settings.

## 3. Docs and verification
- [x] 3.1 Update `docs/engineering/model-routing.md` and `template/docs/engineering/model-routing.md`.
- [x] 3.2 Regression tests: R2 write allowed without delegation; explicit delegation and first write denied with the next step; opened delegation allows the write with no extra step; no route denied; non-managed and lifecycle paths allowed; doctor installation idempotent and malformed settings fail.
- [x] 3.3 Update existing routing tests that assumed default delegation; run full validation and semantic OpenSpec verification.
