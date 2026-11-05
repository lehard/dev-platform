## Why

Only the sandboxed writer reads `[independent_review.login.claude] token_file`. A reviewer needs an exported `CLAUDE_CODE_OAUTH_TOKEN`: without it the readiness probe reports "Not logged in". The exported value is also inherited by project checks, because the credential-free environment does not drop it. The coordinator guide and the overview hint still ask for manual exports.

## What Changes

- One resolver gives every job kind its credentials. GitHub stays the active `gh` credential.
- On the operator node the Claude credential comes only from `token_file`, and the ambient token is removed at worker start. On a hosted runner, which has no enabled `[operator]`, it comes only from the job's secret. Placement picks the source; a value being present never does.
- The value reaches only the LLM process and the readiness probe, never Git, push, project checks, argv or logs.
- The coordinator guide and the overview hint drop the manual exports.

## Impact

- New `template/scripts/worker_credentials.py`; `template/scripts/sandboxed_writer.py`, `lifecycle_workers.py`, `pr_review_gate.py`, `lifecycle_overview.py`; tests; `docs/engineering/chat-coordinator.md`, `docs/engineering/model-routing.md`; manifest.
- A command that still exports the token keeps working: the ambient value is removed and the file value used.
