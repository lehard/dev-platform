## 1. Establish the central source contract

- [ ] 1.1 Inspect the current root/source layout, `template/scripts/` lifecycle modules, root AGENTS guidance, CI, and active `durable-publication-recovery` artifacts; identify the smallest source adapter boundary that does not duplicate publication semantics.
- [ ] 1.2 Define explicit central-source configuration for integration branch, protected-main expectation, task workspace/profile behavior, publication mode, merge policy, and required source-owned lifecycle paths; record the source-specific contract as an OpenSpec delta.
- [ ] 1.3 Add tests proving central configuration is explicit and does not silently inherit downstream fallback defaults.

## 2. Add supported central start/workspace entrypoint

- [ ] 2.1 Add the root source-repository start command/wrapper using existing synchronization/workspace primitives where possible.
- [ ] 2.2 Fail closed for dirty/diverged/unsafe central integration state; do not stash/reset/clean unrelated work.
- [ ] 2.3 Ensure ordinary implementation occurs in the supported isolated task workspace/branch and central `main` remains the integration copy.
- [ ] 2.4 Add temporary-repository tests for clean start, behind-main fast-forward, divergence failure, dirty integration failure, and repeat/conflict handling.

## 3. Add central status and finish/resume

- [ ] 3.1 Wire central read-only status to the existing authoritative GitHub-backed publication observation model; do not infer delivery from CLI prose.
- [ ] 3.2 Wire central finish/resume to existing exact-head PR publication/reconciliation behavior, including protected-main safety and required checks.
- [ ] 3.3 Ensure automatic policy does not stop routinely at draft/open PR and does not classify green CI as complete before merge.
- [ ] 3.4 Ensure manual-review policy returns an explicit nonterminal review-required state.
- [ ] 3.5 After confirmed remote merge, synchronize central local `main` and reconcile only lifecycle-owned task workspace/branch state.

## 4. Prove restart and terminal-state behavior

- [ ] 4.1 Add integration tests for branch-pushed/no-PR, PR-created/checks-pending, checks-passed/open-PR, and merged-awaiting-local-reconciliation states.
- [ ] 4.2 Add restart/resume tests showing repeated finish converges on the same exact task head/PR and does not duplicate delivery.
- [ ] 4.3 Add changed-head/TOCTOU regression coverage showing merge fails closed rather than acting on a different PR head.
- [ ] 4.4 Add the #112 dogfood regression: a draft/open PR with successful required CI must remain nonterminal and the automatic lifecycle must either advance it safely or report a concrete blocker.

## 5. Update source guidance and diagnostics

- [ ] 5.1 Update root `AGENTS.md` and relevant source developer documentation to make the central dogfood start/status/finish commands the normal path.
- [ ] 5.2 Explicitly forbid reporting ordinary central work as complete at `branch pushed`, `PR created`, `draft`, or `checks passed` states.
- [ ] 5.3 Ensure doctor/diagnostic output points to resumable publication state when unfinished central delivery exists instead of instructing ad-hoc Git/PR recovery.

## 6. Preserve shared/downstream boundaries

- [ ] 6.1 Verify the implementation reuses existing publication primitives and does not fork `durable-publication-recovery` logic.
- [ ] 6.2 If shared code must move to support source imports, keep generated repositories self-contained and update template/render/Copier tests only for real shared changes.
- [ ] 6.3 Do not mark or modify the remaining live-acceptance tasks of `durable-publication-recovery` except where this task supplies evidence that legitimately belongs there; keep completion ownership separate.

## 7. Verify and dogfood the fix

- [ ] 7.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -v`, `python3 template/scripts/openspec_lifecycle.py check`, strict OpenSpec validation, and any affected render/update smoke tests.
- [ ] 7.2 Run semantic OpenSpec verification and resolve material findings before archive.
- [ ] 7.3 Record truthful `OpenSpec-Verify: PASS` / `Verification-Method` evidence and archive through the central lifecycle helper required by current repository rules.
- [ ] 7.4 Publish this change using the newly implemented central dogfood finish path itself. This is the final acceptance: no generic draft-PR fallback and no manual Git courier unless a real blocker is recorded.
- [ ] 7.5 Confirm the associated Development Backlog task can be closed only after the exact PR is `MERGED` and local central `main` is reconciled.

## Logical commit boundaries

1. Central source configuration + start/workspace path + tests.
2. Status/finish/resume adapter + publication-state integration + tests.
3. Guidance/diagnostics + complete regression suite.
4. Verification/archive/spec synchronization and final dogfood publication.
