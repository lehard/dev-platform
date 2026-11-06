## 1. Credentials
- [x] 1.1 `worker_credentials` module with placement-selected Claude source; `sandboxed_writer` uses it; GitHub stays the active `gh` credential.
- [x] 1.2 Remove the ambient token at worker start on the operator node; add the resolved value only to the LLM environment of the probe and the reviewer.
- [x] 1.3 Project checks and harness Git never see the value.

## 2. Tests and docs
- [x] 2.1 Unit tests for every scenario, including an exported token on the operator node, a missing file with an export, hosted absence and value containment.
- [x] 2.2 `docs/engineering/chat-coordinator.md`, `docs/engineering/model-routing.md`, overview hint, manifest.
- [x] 2.3 Full validation, strict `openspec validate` and semantic OpenSpec verification.
