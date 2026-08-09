# Tasks

## 1. Managed rollout implementation

- [ ] 1.1 Make exact-version Copier update and guarded recopy pass `--skip-tasks`.
- [ ] 1.2 Invoke the rendered candidate platform bootstrap once only after a conflict-free render.
- [ ] 1.3 Preserve existing project-owned snapshots, version coherence, strict validation and fail-closed behavior.

## 2. Regression coverage

- [ ] 2.1 Add unit coverage for task skipping and candidate bootstrap ordering.
- [ ] 2.2 Make root OpenSpec configuration parseable and cover it.
- [ ] 2.3 Run the real project-harness recopy smoke with a supported OpenSpec CLI.

## 3. Verification and lifecycle

- [ ] 3.1 Run compile, registry validation, unit tests, lifecycle check and strict OpenSpec validation.
- [ ] 3.2 Perform semantic verification and record a truthful receipt.
- [ ] 3.3 Archive through the lifecycle helper before publication.
