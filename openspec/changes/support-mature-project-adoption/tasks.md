# Implementation Tasks

## 0. Baseline and contract freeze

- [x] 0.1 Read current `project-factory`, `platform-ci`, `platform-lifecycle`, `platform-config` and `completion-lifecycle` specs plus `docs/adoption.md`, `copier.yml`, `scripts/adopt_project.py`, generated CI and platform doctor.
- [x] 0.2 Add regression tests that capture current fresh adoption behavior before changing existing-project planning.
- [x] 0.3 Define the deterministic marker set and precedence for detecting project-owned lifecycle capabilities; explicitly separate repository-size/process detection from harness ownership detection.
- [x] 0.4 Define the exact ownership boundary for platform hygiene versus product/application checks in `harness_mode=project`.

**Commit boundary:** contract/tests only; no behavior change.

## 1. Adoption planning model

**Depends on:** 0

- [x] 1.1 Refactor adoption planning so `kind`, `workflow_profile`, `harness_mode` and `publish_mode` are derived independently rather than mapping every `existing` repository to one hard-coded tuple.
- [x] 1.2 Preserve existing fresh defaults and already-adopted behavior.
- [x] 1.3 Detect a coherent project-owned harness from deterministic repository-relative lifecycle markers; repository size alone must never select project harness ownership.
- [x] 1.4 Detect `multi-agent` only when existing worktree isolation plus agent/scope coordination are present; otherwise use a conservative compatible profile.
- [x] 1.5 Treat ambiguous ownership collisions as an explicit blocker/review state instead of silently overwriting files.
- [x] 1.6 Include the derived migration plan and detection reasons in the adoption result JSON, workflow summary and adoption PR description.
- [x] 1.7 Add unit tests for fresh, simple existing, mature standard/project-harness, mature multi-agent/project-harness, ambiguous collision and already-adopted cases.

**Commit boundary:** adoption planner and tests.

## 2. Copier ownership and mature migration safety

**Depends on:** 1

- [x] 2.1 Ensure `harness_mode=project` rendering preserves repository-owned lifecycle entrypoints instead of installing platform equivalents over them.
- [x] 2.2 Ensure reviewed project-required lifecycle files can be represented through `.dev-platform.toml project_required_files` without making platform doctor own their implementation.
- [x] 2.3 Audit all template paths that commonly collide with mature repositories, including engineering/OpenSpec guidance, and assign explicit project-owned versus platform-managed ownership.
- [x] 2.4 Eliminate normal mature-migration `.rej` failures caused only by an expected project-owned file; retain blocking behavior for true unresolved ownership conflicts.
- [x] 2.5 Do not destructively initialize existing OpenSpec state during first-time mature migration.
- [x] 2.6 Add Copier/adoption tests proving existing lifecycle files and project CI remain byte-for-byte preserved where ownership says they are project-owned.

**Commit boundary:** safe Copier migration for project-owned harnesses.

## 3. Adoption validation boundary

**Depends on:** 1, 2

- [x] 3.1 Split adoption validation into platform/OpenSpec validation and product/application validation.
- [x] 3.2 For `harness_mode=project`, stop invoking the target repository's selector with platform-only flags such as `--execute` or `--full`.
- [x] 3.3 For `harness_mode=project`, run only dependency-independent preparation checks: conflict hygiene, `git diff --check`, platform doctor/config health, OpenSpec lifecycle hygiene, strict structural OpenSpec validation and generated-platform-file validation.
- [x] 3.4 Preserve the existing platform-managed selected/full check path for `harness_mode=platform`.
- [x] 3.5 Ensure a mature existing adoption can prepare and push a reviewable PR without the onboarding runner installing arbitrary application dependencies.
- [x] 3.6 Update workflow summaries so they do not claim project checks passed when verification is intentionally delegated to repository CI.

**Commit boundary:** adoption validation ownership.

## 4. Downstream Dev Platform CI ownership

**Depends on:** 3

- [x] 4.1 Make generated `.github/workflows/dev-platform.yml` conditional on `harness_mode` at render time or through an equally explicit stable contract.
- [x] 4.2 For `harness_mode=project`, run shared OpenSpec/platform hygiene only and never execute product checks through project-owned `select_checks.py`.
- [x] 4.3 For `harness_mode=platform`, retain current selected/full platform-managed check execution.
- [x] 4.4 Verify that project-owned CI files are not replaced, disabled or made redundant by adoption unless explicitly reviewed.
- [x] 4.5 Add generated-workflow tests covering both harness modes and asserting project mode has no dependency on `--execute`/`--full` selector flags.

**Commit boundary:** harness-aware downstream CI.

## 5. Mature multi-agent lifecycle composition

**Depends on:** 2, 4

- [x] 5.1 Verify platform doctor does not require platform-owned worktree/board files when `workflow_profile=multi-agent` and `harness_mode=project`.
- [x] 5.2 Verify shared start/finish helpers fail with clear instructions to use repository-owned lifecycle entrypoints rather than partially executing platform lifecycle.
- [x] 5.3 Add a synthetic project-owned multi-agent fixture with its own board/worktree/merge/check scripts and declare required project files through the reviewed platform config.
- [x] 5.4 Verify `python3 scripts/dev.py ready` remains safe/idempotent for project-owned harness mode and does not mutate the repository's lifecycle implementation.

**Commit boundary:** multi-agent project-harness compatibility.

## 6. Jara_Fin-like acceptance scenario

**Depends on:** 1–5

- [x] 6.1 Build a synthetic mature fixture representing the relevant Jara_Fin process surface: existing `AGENTS.md`, OpenSpec, project CI, project `select_checks.py` without `--execute`/`--full`, agent board/worktree coordination and repository-owned merge lifecycle.
- [x] 6.2 Run the adoption planner and assert `kind=existing`, `workflow_profile=multi-agent`, `harness_mode=project`, `publish_mode=pr` with auditable reasons.
- [x] 6.3 Run first-time adoption against the fixture and assert project-owned lifecycle files, project selector, project CI and existing OpenSpec state are preserved.
- [x] 6.4 Assert platform metadata, lifecycle hygiene and self-contained platform CI are installed successfully.
- [x] 6.5 Assert generated platform CI in project-harness mode does not call product checks or assume application dependencies are installed.
- [x] 6.6 Assert the resulting migration remains review-only and is not automatically promoted to `managed` until the adoption PR is merged and onboarding is rerun.

**Commit boundary:** mature-project acceptance tests.

## 7. Documentation, regression and release gate

**Depends on:** all implementation tasks

- [x] 7.1 Update `README.md` and `docs/adoption.md` to explain that one-command adoption automatically preserves coherent mature project harnesses.
- [x] 7.2 Document the CI ownership boundary: Dev Platform hygiene versus project-owned product CI.
- [x] 7.3 Document ambiguous-collision behavior and the advanced/manual fallback without making it part of normal onboarding.
- [x] 7.4 Run `python3 -m compileall -q template/scripts scripts`.
- [x] 7.5 Run `python3 scripts/managed_projects.py validate`.
- [x] 7.6 Run `python3 -m unittest discover -s tests -v` including fresh and mature adoption fixtures.
- [x] 7.7 Run `python3 template/scripts/openspec_lifecycle.py check` and strict OpenSpec validation.
- [ ] 7.8 Perform semantic OpenSpec verification across completeness, correctness and coherence; resolve material findings and record the verification receipt.
- [ ] 7.9 Archive this change through the platform lifecycle helper and only then prepare the next immutable platform release.

## Definition of Done

The change is complete when a Jara_Fin-like mature multi-agent repository can use the same one-command `Adopt Project` interface as a fresh repository, the platform derives a reviewed `multi-agent + project harness + PR` migration automatically, existing lifecycle/OpenSpec/CI assets are preserved, platform/OpenSpec hygiene is enforced, no project-owned selector compatibility shim is required, and fresh-project onboarding behavior remains unchanged.
