## 1. Idle reason
- [x] 1.1 Add `idle_reason` to `lifecycle_overview.py` (ordered rules, hosted-class lookup, attempt limits) and expose it as `idle` on each assessed candidate.
- [x] 1.2 Render an `idle:` line in `render_candidate`; JSON carries the object.
- [x] 1.3 Update `docs/engineering/chat-coordinator.md`.

## 2. Verification
- [x] 2.1 Tests: unclaimed integration-repair (local macOS node), waiting for developer, waiting for queue, attempt limit exhausted, claimed -> no idle, unknown state explicit, every candidate state classified.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
