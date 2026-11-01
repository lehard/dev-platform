## 1. Behaviour
- [x] 1.1 `execute_requirement.py`: archive a delivered child's task state before starting the next child; explicit refusals otherwise.
- [x] 1.2 `requirement_retrospective.py`: `RetrospectivePending` for missing or stale receipts; `advance` returns `await-requirement-retrospective` with the command.

## 2. Docs and tests
- [x] 2.1 Docs: task-intake; platform manifest.
- [x] 2.2 Tests: archive on Done child with equal main; refusal on non-Done child and on diverged main; pending status for missing and stale receipts; malformed receipt still fails.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification.
