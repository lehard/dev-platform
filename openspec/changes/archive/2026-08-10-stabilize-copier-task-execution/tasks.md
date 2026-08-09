# Tasks

## 1. Managed rollout implementation

- [x] 1.1 Make exact-version Copier update and guarded recopy pass `--skip-tasks`.
- [x] 1.2 Invoke the rendered candidate platform bootstrap once only after a conflict-free render.
- [x] 1.3 Preserve existing project-owned snapshots, version coherence, strict validation and fail-closed behavior.

## 2. Regression coverage

- [x] 2.1 Add unit coverage for task skipping and candidate bootstrap ordering.
- [x] 2.2 Make root OpenSpec configuration parseable and cover it.
- [x] 2.3 Run the real project-harness recopy smoke with a supported OpenSpec CLI.

## 3. Verification and lifecycle

- [x] 3.1 Run compile, registry validation, unit tests, lifecycle check and strict OpenSpec validation.
- [x] 3.2 Perform semantic verification and record a truthful receipt.
- [x] 3.3 Archive through the lifecycle helper before publication.
