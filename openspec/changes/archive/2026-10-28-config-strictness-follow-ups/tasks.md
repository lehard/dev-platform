## 1. Configuration readers

- [x] 1.1 `github_retry_attempts`: explicit error for an invalid or below-one value; unset keeps 4; update `tests/test_github_retry.py`.
- [x] 1.2 Configuration error hook installed only over the interpreter default; test.
- [x] 1.3 `capability_manager` reads `agent_tools` and `platform_version` through the validated configuration; test.
- [x] 1.4 Sandboxed writer probe fixture carries the real source contract.
- [x] 1.5 `_project_topology` named-key test.

## 2. Documentation

- [x] 2.1 `AGENTS.md` and `docs/engineering/agent-workflow.md`: committed contract is `dev-platform/source-contract.toml`; minimum validation adds ruff and the manifest check; retry setting documents the error.

## 3. Verification

- [x] 3.1 Run full validation, the public distribution snapshot smoke and semantic OpenSpec verification.
