## 1. Runtime and containment preflight

- [x] 1.1 Inspect the current supported Codex VS Code/CLI native subagent configuration, per-child model/reasoning controls, inherited sandbox behavior, writable roots and working-directory semantics.
- [x] 1.2 Inspect the current supported Claude Code Desktop/CLI native subagent configuration, per-child model/effort controls, sandbox/worktree isolation, permissions/hooks and shell write boundaries.
- [x] 1.3 Inventory the current `delegated_write_guard` and containment tests by supported scenario; identify which layers are still required, which are now duplicated by native enforcement, and which are only legacy compatibility behavior.
- [x] 1.4 Reconcile the updated `platform-delegation` delta with current accepted specs/active changes. Stop for user resolution only on a material product-level safety conflict, not implementation-detail differences.

## 2. Simplify delegation containment without a rewrite

- [x] 2.1 Change platform-owned delegation guidance/adapters from mandatory custom-guard wording to the stable assigned-worktree + proven-boundary + post-check invariant.
- [x] 2.2 For current supported Codex modes, use proven native sandbox containment as the primary prevention path where it satisfies the invariant.
- [x] 2.3 For current supported Claude modes, use proven native sandbox/worktree isolation as the primary prevention path where it satisfies the invariant.
- [x] 2.4 Preserve a minimal custom guarded/detection fallback only for supported modes that lack sufficient native containment; remove or simplify redundant provider-specific hook/wrapper code only after tests prove coverage.
- [x] 2.5 Preserve the lightweight content-aware integration post-check and fail-closed reporting for detected protected-path mutation.

## 3. Routing policy and reusable agent profiles

- [x] 3.1 Add reusable routing guidance that makes the strong parent perform bounded semantic classification after task materialization and before implementation.
- [x] 3.2 Define versioned provider-local `routine`, `standard` and `complex` executor mappings using the smallest supported project-level Codex/Claude configuration surface; keep concrete model/reasoning settings outside durable task artifacts.
- [x] 3.3 Ensure downstream projects receive routing and containment guidance/profiles through the normal template/Copier lifecycle.

## 4. Delegated execution and escalation

- [x] 4.1 Implement bounded context handoff from parent to executor and back, including canonical OpenSpec, task worktree state and relevant verification evidence without creating a second implementation plan.
- [x] 4.2 Implement explicit escalation for material contract conflict, unexpected cross-cutting/scope growth, low confidence and bounded substantive verification failures; preserve useful worktree/diff state across escalation.
- [x] 4.3 Implement truthful fallback when the preferred cheap executor/native child capability is unavailable: use configured fallback/parent or return an actionable diagnostic.

## 5. Verification and cleanup

- [x] 5.1 Add/update deterministic containment tests for native Codex and Claude paths, invalid assigned worktree, native-boundary failure, fallback mode, integration mutation, dirty/pre-existing integration state and child failure/cancellation.
- [x] 5.2 Add routing contract tests for routine/standard delegation, complex/no-cheap-trial, standard-to-complex escalation and unavailable-executor fallback.
- [x] 5.3 Remove dead/redundant containment code only after the supported native/fallback matrix is covered; do not perform unrelated delegation refactors.
- [x] 5.4 Run relevant template/OpenSpec lifecycle tests and Copier/render smoke validation, then perform semantic OpenSpec verification before archive. (Copier is unavailable on this host; the verification receipt records the unexecuted render smoke and structural delivery coverage.)
