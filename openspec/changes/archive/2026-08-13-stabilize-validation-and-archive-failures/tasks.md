## 1. Stabilize shared-workspace validation

- [x] 1.1 Reproduce the managed-task/shared-workspace scenario under controlled test-group parallelism.
- [x] 1.2 Confirm current fixture setup remains deterministic; do not serialize a group without a reproduced unsafe boundary.
- [x] 1.3 Verify the existing regression coverage preserves real permission-failure detection.

## 2. Preserve validation failure signal

- [x] 2.1 Expose bounded selected-check/group failure context from selector/runner paths.
- [x] 2.2 Record sanitized failure class/context in lifecycle friction instead of one generic validation issue signal.
- [x] 2.3 Keep raw detailed evidence bounded to its existing local/run surface.

## 3. Preflight OpenSpec archive

- [x] 3.1 Validate semantic receipt/static automated-evidence prerequisites before expensive checks.
- [x] 3.2 Fail before checks/evidence mutation when no applicable committed diff/state exists.
- [x] 3.3 Ensure a failed preflight cannot leave a stale authoritative `automated-checks.json`.

## 4. Verify

- [x] 4.1 Cover concurrent success and controlled real shared-workspace failure.
- [x] 4.2 Cover actionable validation failure classification.
- [x] 4.3 Cover archive fail-fast ordering and ready single-pass archive.
- [x] 4.4 Run relevant platform-ci/completion/OpenSpec checks and strict OpenSpec validation.
