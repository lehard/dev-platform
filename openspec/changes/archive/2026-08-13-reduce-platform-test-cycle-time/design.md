# Design: faster isolated platform validation

## Current constraint

The existing selector is safe but coarse in two independent ways. At command granularity, a Python selection executes the entire unittest suite, and broad platform control paths trigger the same full command set. Previous validation optimization intentionally stopped before partitioning because fixtures were not proven worker-safe. The result is that test runtime remains the dominant local cost and concurrent agents can amplify contention.

Separately, the selector classifies purely by path glob (`full_trigger_patterns` in `dev-platform/checks.toml`): `AGENTS.md`, `docs/**`, `openspec/**` and `template/AGENTS.md.jinja` are full triggers regardless of whether the change is a semantic-preserving wording refactor or an intentional behavior change. That conflates two different questions — "did runtime behavior change" and "is this file broadly classified as platform surface" — and pays full software-suite cost for the former even when the answer is no.

This change treats both problems as test/validation architecture, not as permission to weaken validation: make depth proportional to actual risk, and make genuine full-suite execution faster and safely concurrent.

## 0. Risk classes replace the single full-trigger/mapped/unknown split

Four canonical risk classes, evaluated in this fail-closed order:

1. `control-plane` — the changed path is unknown, ambiguously classified, or touches selector/check configuration (`dev-platform/checks.toml`, `select_checks.py`, `run_test_groups.py`), CI workflow, or OpenSpec/lifecycle control-plane code. Selects full validation. This subsumes and keeps the previously delivered "Local path is unknown or high impact" behavior.
2. `instruction-behavior-change` — an instruction/prompt surface (`AGENTS.md`, `template/AGENTS.md.jinja`, agent-facing prompt files) where the change is declared, by an explicit non-model-self-reported input to the selector invocation, to intentionally change agent behavior. Requires the configured targeted behavioral smoke command(s) for the affected runtime/provider to actually run and succeed as part of that validation invocation; a bare declaration with no executed evidence is treated as `control-plane` (full) instead of accepted.
3. `docs-semantic` — a documentation/instruction surface (`AGENTS.md`, `docs/**`, `openspec/**` prose, `template/AGENTS.md.jinja`) with no `instruction-behavior-change` declaration. Gets bounded structure/link/anchor/render checks; does not by itself select the full Python suite.
4. `executable` — harness/scripts/template runtime code with a maintained, tested path-to-group mapping. Selects only the mapped canonical test group(s); the previously delivered "Proven local affected change" behavior.

The declaration for class 2 is a selector-invocation input (an explicit flag plus which behavioral command(s) ran), never an unverified assertion embedded in agent output — the model cannot self-report "I checked, it's fine" in place of the command actually executing with a recorded outcome. Absence of a class-2 declaration on an instruction-surface path defaults to class 3 (`docs-semantic`); an ambiguous or unrecognized instruction surface defaults to class 1 (`control-plane`).

Class 3 and class 4 remain subject to the same "Local affected validation never replaces protected PR authority" and "Parallel validation preserves resource isolation and aggregate authority" requirements as before: a protected-main PR still runs the complete authoritative validation set for its actual risk class, and local success in any class is never accepted as protected-PR authority.

## 1. Profile before changing execution

Preflight SHALL capture current module/group timings and identify the slowest contributors under both an isolated run and at least two concurrent validation invocations in separate worktrees. The audit SHALL enumerate mutable resources used by tests: temporary repositories/directories, fixed paths, environment variables, process-global patches, locks, artifacts, ports, external state and long-lived subprocesses.

A test or group is classified as:

- `isolated`: all mutable resources are unique to the run/worker;
- `serial`: it has a legitimate shared boundary that cannot safely be isolated in this change;
- `unsafe/unknown`: it cannot participate in concurrent execution until repaired or explicitly kept behind the conservative full/serial path.

## 2. Make isolation a fixture contract

Prefer per-test/per-run generated temporary roots and explicit resource ownership over global fixed paths. Environment/process-global mutations must be restored within their test boundary. Locks, artifacts and helper repositories must be namespaced by run/worker where they are not intentionally shared.

Do not introduce broad repository-wide locking merely to make tests pass concurrently. If a small subset really requires serialization, isolate that subset into an explicit serial group so unrelated tests remain parallelizable.

Flakiness caused by ordering or concurrent state is a defect to repair or isolate, not something to hide with retries.

## 3. Add stable test groups below the current all-Python command

The selector should operate on canonical named groups rather than ad-hoc commands chosen by an agent. A maintained mapping MAY associate a bounded implementation surface with one or more relevant groups only when the dependency is defensible and covered by selector contract tests. This mapping applies within the `executable` risk class from §0.

Multiple changed paths selecting the same group execute it once per validation run. A broad language/file-type match alone is not sufficient reason to run the entire suite when a narrower proven mapping exists. Conversely, selector/check configuration, workflow, OpenSpec/lifecycle control-plane code, unknown paths and ambiguous mappings remain full-suite triggers (`control-plane`).

The exact grouping mechanism is a preflight implementation choice. Preserve the existing unittest framework unless migration is independently justified; do not introduce a new test framework solely to obtain parallelism.

## 3a. `docs-semantic` and `instruction-behavior-change` checks

`docs-semantic` gets its own bounded, fast check group — not the Python suite: a required-anchor/reference-integrity check (existing `tests/test_project_harness_doc_ownership.py`, `tests/test_ci_trigger_compatibility.py` and an added link/anchor/destination check), plus, for `template/AGENTS.md.jinja`, a Jinja render smoke so a broken template fails even though it is `docs-semantic`.

`instruction-behavior-change` reuses the `docs-semantic` checks and additionally runs the configured targeted behavioral smoke command(s) for the declared affected runtime/provider (for example, an existing `dev.py`/entrypoint smoke or a provider-specific harness invocation already present in the platform). The selector records which command ran and its outcome as evidence; a declaration without a recorded successful command outcome is rejected and the selection falls back to `control-plane`.

## 4. Keep protected full authoritative while reducing wall-clock

`protected-full` continues to mean complete mandatory coverage for the current head. It may dispatch mandatory groups concurrently only after their isolation contract is proven. Serial groups run behind an explicit boundary. If GitHub Actions uses multiple jobs, one stable aggregate required result must fail whenever any mandatory partition fails.

A local selected run never substitutes for protected-full. No cached receipt, prior head result or similarity heuristic is accepted as merge authority for a changed head.

Within one validation invocation, the runner should not execute the same expensive mandatory group twice merely because multiple selector rules chose it. Selection evidence records group identity, execution result and duration.

## 5. Validate concurrent-agent behavior explicitly

Acceptance must include concurrent validation from separate task worktrees, because that is the operational scenario that motivated the change. Both runs must complete without fixed-path collisions, shared artifact corruption, hidden cross-run state or indefinite blocking caused by test fixtures. CPU contention may increase elapsed time and must be reported honestly; correctness and resource isolation are the invariant.

## 6. Performance evidence and rollback boundary

Record comparable before/after timings for the same mandatory coverage. The optimized path is accepted only if it demonstrates lower full-validation wall-clock without reducing mandatory tests or branch-protection authority. If a proposed partition provides no meaningful improvement or creates instability, keep it sequential and document the blocker rather than landing unsafe concurrency.

The change must remain reversible at the execution-policy level: canonical group definitions and conservative full mode remain available even if a parallel execution strategy later needs to be disabled.

## Non-goals

- merge queue, Hermes or coding-agent orchestration;
- weakening required checks or branch protection;
- cross-head validation reuse/caching as proof of safety;
- deleting tests to improve timings;
- changing downstream product behavior;
- building a general-purpose multi-provider behavioral test harness from scratch — `instruction-behavior-change` reuses whatever targeted smoke command(s) already exist for the affected runtime/provider and fails closed if none exist for it;
- letting an agent's own narrative report ("I verified this is safe") stand in for an executed, recorded behavioral command outcome.
