## 1. Preflight and contract alignment

- [x] 1.1 Inspect the current official `define-goal` skill and the Codex/runtime mechanism actually supported at implementation time.
- [x] 1.2 Reconcile the new goal-definition contract with current task-intake, OpenSpec and downstream template guidance; stop for user resolution on a material product-contract conflict.

## 2. Reusable integration

- [x] 2.1 Add the smallest reusable platform/template guidance or adapter needed to invoke goal refinement selectively.
- [x] 2.2 Preserve direct quick-task execution and existing managed-task authoring/source-of-truth boundaries.
- [x] 2.3 Implement truthful fallback/diagnostics for environments without supported native goal state; do not vendor a competing durable goal system.

## 3. Verification

- [x] 3.1 Add or update contract tests for a fuzzy request that requires goal refinement and a concrete request that must not require it.
- [x] 3.2 Verify managed authoring consumes the refined outcome without creating a second durable implementation-plan artifact.
- [x] 3.3 Verify unsupported-runtime behavior cannot fabricate native goal creation/state.
- [x] 3.4 Run relevant template/OpenSpec lifecycle tests and Copier/render smoke validation, then perform semantic OpenSpec verification before archive.
