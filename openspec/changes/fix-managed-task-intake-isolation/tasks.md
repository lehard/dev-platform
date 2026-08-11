## 1. Managed task startup

- [ ] 1.1 Extract read-only managed-package discovery and implement the platform-owned managed-task start entrypoint.
- [ ] 1.2 Start standard and multi-agent task state before materialization, and reconcile only invocation-created state when materialization fails.
- [ ] 1.3 Guard standalone importer materialization from a platform-owned feature-capable integration branch while retaining supported task-branch and light-profile use.

## 2. Regression coverage

- [ ] 2.1 Add unit tests for discovery, integration-branch refusal and light/feature-branch compatibility.
- [ ] 2.2 Add lifecycle tests proving successful managed start materializes only in the task checkout and leaves integration `main` clean.
- [ ] 2.3 Add failure-path tests proving invalid packages create no task state and materialization failures do not modify integration state or remove unrelated work.

## 3. Rendered workflow guidance

- [ ] 3.1 Update central and generated agent instructions to use managed-task start before materialization, including project-harness routing.
- [ ] 3.2 Update template contract/render validation for the new entrypoint and verify Copier-update compatibility for existing managed projects.

## 4. Verification and delivery

- [ ] 4.1 Run focused tests plus the required platform validation suite, including template render/doctor checks when Copier is available.
- [ ] 4.2 Perform semantic OpenSpec verification, record the actual PASS method and findings in `verification.md`, then archive through the lifecycle helper before publication.
