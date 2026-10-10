## 1. Publication workflow
- [x] 1.1 Add the Explorer workflow with build and deploy jobs, least-privilege permissions, SHA-pinned actions, Pages concurrency and default-branch-only deployment, invoking `scripts/build_explorer.py` for all build logic.
- [x] 1.2 Add path-filtered pull-request build verification covering Explorer sources, the build script, the workflow and the canonical roots the Explorer renders.

## 2. Contract tests and documentation
- [x] 2.1 Add a workflow-contract test for triggers, permissions, pinning, deploy gating, absence of `enablement`, absence of inlined build logic, and absence from the rendered template.
- [x] 2.2 Document the one-time Pages enablement, explicit failure when disabled and local reproduction in `docs/engineering/explorer.md`.

## 3. Validation and delivery
- [ ] 3.1 Run compile, ruff, full test groups, docs link checks and the OpenSpec lifecycle check; run semantic OpenSpec verification and complete the authorized lifecycle handoff.
