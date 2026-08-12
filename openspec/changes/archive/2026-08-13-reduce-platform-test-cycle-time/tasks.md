## 1. Preflight and baseline

- [x] 1.1 Reconcile this package against current `platform-lifecycle`, `ci-safety`, the archived `optimize-platform-validation-feedback` change and any active changes touching validation/CI before implementation.
- [x] 1.2 Capture current isolated module/group timings for the mandatory unit suite and the complete protected validation path; retain machine-readable evidence.
- [x] 1.3 Run a controlled concurrent-worktree baseline and inventory every shared/fixed mutable resource, ordering dependency and long-lived subprocess that prevents safe concurrent execution.

## 2. Test isolation

- [x] 2.1 Refactor fixed/shared temporary repositories, paths, artifacts and locks to unique per-run/per-worker resources where isolation is feasible.
- [x] 2.2 Contain and reliably restore environment/process-global mutations within test boundaries; identify any tests that must remain serial.
- [x] 2.3 Add regression tests that reproduce the previous cross-run collision/contended behavior and prove independent worktrees no longer corrupt or block one another because of fixture state.

## 3. Granular local selection

- [x] 3.1 Define canonical named test groups and a maintained mapping for safely bounded implementation surfaces; deduplicate a group selected by multiple paths.
- [x] 3.2 Narrow current coarse full/Python triggers only where proof-backed mappings exist; preserve full fail-closed selection for unknown, ambiguous and high-impact control-plane paths.
- [x] 3.3 Add selector contract tests proving targeted local behavior, duplicate-group elimination and conservative full fallback.
- [x] 3.4 Implement the `docs-semantic` / `instruction-behavior-change` / `executable` / `control-plane` risk-class classification in the selector so `AGENTS.md`, `docs/**`, `openspec/**` prose and `template/AGENTS.md.jinja` are no longer unconditional full triggers.
- [x] 3.5 Add the bounded `docs-semantic` check group (anchors/links/destinations plus a Jinja render smoke for `template/AGENTS.md.jinja`) and prove it fails on a broken anchor/destination/render without running the full Python suite.
- [x] 3.6 Add the `instruction-behavior-change` declaration input plus its required targeted-behavioral-command evidence, and prove a declaration without an executed successful command falls back to `control-plane`.

## 4. Faster protected full execution

- [x] 4.1 Partition mandatory tests/checks only along proven isolation boundaries; keep genuinely shared-resource groups explicitly serial instead of serializing the whole suite.
- [x] 4.2 If CI uses parallel jobs/partitions, preserve one stable aggregate required result that fails on any mandatory partition failure and remains suitable for protected-main branch rules.
- [x] 4.3 Keep one canonical validation entrypoint/mode contract for agents and record group-level result/duration evidence without requiring manual command selection.

## 5. Benchmark, verification and delivery

- [x] 5.1 Repeat isolated and concurrent-worktree benchmarks after the change and compare like-for-like mandatory coverage with the baseline.
- [x] 5.2 Demonstrate that full protected validation still executes every mandatory test/check and that a controlled mandatory-partition failure blocks the aggregate gate.
- [x] 5.3 Run full relevant platform/OpenSpec/template/Copier regression validation; document remaining serial boundaries, performance gain and residual risks.
- [x] 5.4 Perform semantic OpenSpec verification, record truthful evidence, archive only after all acceptance criteria pass, and publish through the normal protected-main/immutable-release lifecycle when runtime/template artifacts changed.
