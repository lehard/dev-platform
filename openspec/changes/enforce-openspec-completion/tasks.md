# Tasks

## 1. Lifecycle enforcement

- [ ] 1.1 Add platform-managed lifecycle checker/archive entrypoint.
- [ ] 1.2 Make `finish_task.py` block completed-but-active OpenSpec changes.
- [ ] 1.3 Add generated check/CI coverage for OpenSpec lifecycle hygiene.

## 2. Agent contract

- [ ] 2.1 Update generated `AGENTS.md` completion policy to require verification receipt, archive, then publication.
- [ ] 2.2 Update generated OpenSpec config/archive guidance consistently.
- [ ] 2.3 Update durable OpenSpec workflow documentation and README lifecycle wording.

## 3. Tests

- [ ] 3.1 Add unit tests for incomplete, complete-stale, missing-verification, and verified-ready states.
- [ ] 3.2 Add template contract assertions for the lifecycle gate.

## 4. Historical cleanup

- [ ] 4.1 Reconcile stale task text with already-published releases/implemented behavior.
- [ ] 4.2 Archive completed/superseded historical dev-platform changes without fabricating verification claims.
- [ ] 4.3 Confirm accepted current behavior is represented under `openspec/specs/` after cleanup.

## 5. Verification

- [ ] 5.1 Run Python compile/unit checks and strict structural validation where available.
- [ ] 5.2 Perform semantic verification against this change and record `OpenSpec-Verify: PASS` only if findings are resolved.
