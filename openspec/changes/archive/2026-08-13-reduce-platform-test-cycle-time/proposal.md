# Reduce platform test cycle time

## Why

Source backlog issue: `lehard/development-backlog#27`  
Prepared against: `lehard/dev-platform@64055d86eed7a90f3561a0dd300dfa3459b0dde5`  
Backlog issue #27 was materially expanded after this change started; this revision reconciles the local canonical OpenSpec artifacts with the current issue body (observed 2026-08-12T19:30:30Z) per the platform's no-silent-divergence rule.

The completed `optimize-platform-validation-feedback` change established timing evidence, `local-affected` versus `protected-full`, concise diagnostics and fail-closed selection. It also deliberately retained a sequential full unit suite because the isolation audit found fixed/shared temporary state and process-global state; a contended experiment with two full suites was still blocked after eight minutes.

That conservative decision left two costs in place. First, validation depth is still driven by broad file-type/directory classification rather than by the actual risk of the change: `AGENTS.md`, `docs/**`, OpenSpec prose and `template/AGENTS.md.jinja` are `full_trigger_patterns` in `dev-platform/checks.toml`, so a semantic-preserving instruction/documentation refactor pays the same full unittest cost as an executable change even when no runtime behavior changes. Second, for changes that do need full software validation, the archived benchmark measured `python3 -m unittest discover -s tests -v` at 217.776 seconds and the most recent completed platform task measured 253.246 seconds, while compile/configuration checks took only fractions of a second.

The next change should therefore address both costs together: make validation depth proportional to the risk class of the change (docs/instruction-refactor, intended-agent-behavior-change, or executable/control-plane), and, independently, isolate mutable fixtures, create maintainable test groups, and reduce genuine full-suite wall-clock through evidence-backed partitioning. The protected merge gate must keep complete mandatory coverage for whichever risk class applies.

## What Changes

- Classify a changed path into one of a small number of canonical risk classes instead of the current single full-trigger/mapped/unknown split: `docs-semantic` (documentation/instruction content with no intended agent-behavior change), `instruction-behavior-change` (an instruction/prompt change that intentionally changes agent behavior), `executable` (harness/scripts/template runtime code), and `control-plane` (selector/CI/lifecycle/OpenSpec-policy code, plus anything unknown or ambiguous).
- `docs-semantic` paths (`AGENTS.md`, `docs/**`, `openspec/**` prose, `template/AGENTS.md.jinja`) no longer trigger the full Python suite by default; they get bounded structure/link/anchor/render checks that still fail on a broken destination, a dropped required anchor, or a template render defect.
- An `instruction-behavior-change` requires an explicit, non-model-self-reported declaration plus the targeted behavioral smoke command(s) for the affected runtime/provider actually executing successfully; absent that evidence the change fails closed to `control-plane` (full).
- `executable` and `control-plane` classification, and the underlying mapped-group/full-fallback selection logic for executable surfaces, keep the previously delivered dependency-mapping and fail-closed behavior; this change makes the mapping more granular where it can be proven and test-covered.
- Profile the current suite at module/group level and identify slow tests plus all resources that prevent concurrent execution.
- Remove or contain fixed/shared fixture state so independent validation runs in separate task worktrees do not interfere.
- Introduce canonical test-group identities and proof-backed code-path-to-test-group mappings for bounded routine executable changes; unknown, ambiguous and control-plane changes continue to select full validation.
- Restructure the mandatory full test path so isolation-safe groups can execute concurrently or otherwise reduce wall-clock, while genuinely shared-resource tests are narrowly serialized.
- Preserve one canonical platform validation entrypoint across all risk classes, deduplicate selected mandatory groups within one run, and keep machine-readable selection-rationale/timing evidence.
- Benchmark before/after in isolated and concurrent-worktree conditions and accept the test-execution optimization only with unchanged mandatory protected coverage and a demonstrated wall-clock reduction.

## Impact

- Affected spec: `platform-lifecycle`.
- Likely implementation surfaces: test fixtures/helpers, `dev-platform/checks.toml`, `select_checks.py`, protected CI orchestration, generated validation workflow/contracts and regression tests.
- This change builds on Development Backlog #9 and #19; it does not reopen their already delivered timing/freshness work.
- Active `adopt-gh-aw-process-automation` remains separate process-friction/completion work and must not be folded into this change.
- Development Backlog #28 (`optimize-agent-context-map`) is the first representative consumer of the `docs-semantic` risk class: it shrank/restructured `AGENTS.md` and `template/AGENTS.md.jinja` as a semantic-preserving instruction refactor. It merged upstream while this change was in progress, requiring a mid-implementation rebase; see verification.md for how that rebase exercised (and validated) the new docs-semantic checks against real drift.
