## 1. Local coordinator observe-only

- [x] 1.1 Make `run_worker` refuse `mode == "local"` before preflight or any GitHub read with a diagnostic naming the CI coordinator, `status` and `preflight --mode local`.
- [x] 1.2 Remove the local `repository-permission` push probe from `_preflight_runtime`.

## 2. Harness push credential

- [x] 2.1 Make `lifecycle_workers.harness_push_env` obtain the token from `gh auth token` (prompt disabled, stdin closed) and fail explicitly without echoing output when it fails or is empty.

## 3. Docs and tests

- [x] 3.1 Replace the local worker retry advice in `docs/engineering/agent-workflow.md` and any other coordinator doc.
- [x] 3.2 Tests: local worker refuses without GitHub calls; local preflight passes without push permission; harness push uses gh token without exported `GH_TOKEN`; gh failure raises the named error without leaking output; existing CI-mode and secret-safety tests stay green.
- [x] 3.3 Regenerate the platform manifest; run required validation and semantic verification (archive and merge are performed by coordinator finalization and the CI publication queue).
