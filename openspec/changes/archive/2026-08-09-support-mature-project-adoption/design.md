# Design: mature project adoption

## Context

The platform currently has three repository states (`fresh`, `existing`, `adopted`) and two harness ownership modes (`platform`, `project`), but first-time adoption collapses those concerns: every `existing` repository receives `standard + platform + pr`. This is safe only when the existing repository does not already own lifecycle entrypoints that collide with the platform harness.

A mature repository may already own:

- branch/worktree creation and cleanup;
- agent-board coordination;
- serialized merge/publish behavior;
- test selection and dependency-aware CI;
- repository-specific OpenSpec/source-of-truth rules.

Those are engineering-process assets, not migration debt. Adoption should wrap them with shared platform policy where possible rather than replace them.

## Decision 1: classify repository state and harness ownership independently

Adoption planning will produce at least these dimensions:

- `kind`: `fresh | existing | adopted`;
- `workflow_profile`: `light | standard | multi-agent`;
- `harness_mode`: `platform | project`;
- `publish_mode`: `pr | direct`.

Fresh defaults remain unchanged.

For an existing repository, the planner SHALL inspect deterministic repository-relative lifecycle markers before rendering. A project-owned harness is selected when the repository already owns platform-colliding lifecycle entrypoints or an equivalent coherent lifecycle surface. Example markers include project-owned check selection, agent-board/worktree coordination, merge/publish helpers and Git hooks.

`multi-agent` is selected only when existing coordination clearly includes isolated worktrees plus active agent/scope coordination. Otherwise the planner uses `standard` unless another explicit existing platform configuration already defines the profile.

The detection algorithm must be conservative and testable. It SHALL NOT infer project ownership from repository size alone. Ambiguous collisions SHALL fail closed or remain review-only rather than silently overwrite existing process files.

## Decision 2: project-owned harness means project-owned lifecycle entrypoints stay authoritative

When `harness_mode=project`:

- existing project lifecycle files are preserved;
- platform task/worktree/merge/publish wrappers must not become mandatory execution paths;
- platform helpers that already guard on `harness_mode=project` keep directing agents to repository-owned instructions;
- project-required lifecycle files may be declared in `.dev-platform.toml` so `platform_doctor.py` can verify the reviewed project contract without owning its implementation.

This mode does not exempt the project from shared OpenSpec lifecycle policy, platform metadata health, release pinning or managed rollout safety.

## Decision 3: split platform validation from product validation

The adoption workflow must not assume that a project-owned `scripts/select_checks.py` implements the platform selector CLI.

For an existing repository with `harness_mode=project`, pre-PR adoption validation is limited to checks the platform can execute without understanding application dependencies:

- unresolved Copier/Git conflicts;
- `git diff --check`;
- platform doctor/config health;
- OpenSpec lifecycle hygiene;
- strict OpenSpec structural validation when the CLI is available in onboarding;
- deterministic validation of the generated platform files.

Application/product checks remain owned by the repository's existing CI and repository instructions. The adoption PR is the integration point where that CI validates the migration in the project's real dependency environment.

For `harness_mode=platform`, the existing platform-managed selected/full check execution contract remains available.

## Decision 4: downstream Dev Platform CI respects harness ownership

The generated `.github/workflows/dev-platform.yml` remains self-contained and versioned, but its responsibilities differ by harness ownership.

For `harness_mode=platform`, it may run platform-selected project checks through the platform `select_checks.py` contract.

For `harness_mode=project`, it SHALL run only platform-owned hygiene that is dependency-independent, such as OpenSpec lifecycle/validation and platform contract checks. It SHALL NOT execute product tests through a project-owned selector and SHALL NOT duplicate the repository's dependency-aware CI.

The project's existing CI remains untouched unless the reviewed migration explicitly changes it.

## Decision 5: path collisions are ownership decisions, not automatic overwrites

Existing-project adoption SHALL distinguish:

1. project-owned files that the platform intentionally preserves;
2. platform-managed files that are new and non-colliding;
3. true ownership collisions requiring review.

A normal mature migration should not fail merely because an existing repository already has project-specific guidance at a path used by a generic platform document. Where reusable platform guidance needs a stable managed location, prefer a non-colliding platform-owned path or explicitly make the existing path project-owned. Do not attempt semantic auto-merging of arbitrary Markdown.

Any unresolved ownership ambiguity must remain visible in the adoption PR or block preparation before mutation; it must never be silently resolved.

## Decision 6: keep the human onboarding interface simple

`GitHub Actions -> Adopt Project` continues to require only `owner/name` in the normal path. We do not add routine `workflow_profile`, `harness_mode` or `publish_mode` questions for the human.

The workflow summary and adoption PR SHALL report the derived migration plan and the evidence/reasons that caused project-harness or multi-agent selection so the decision is auditable.

An advanced/manual Copier path remains available for exceptional migrations.

## Decision 7: Jara_Fin is an acceptance case, not a template source

Tests will include a synthetic mature-repository fixture with the process characteristics discovered in Jara_Fin: existing OpenSpec, project CI, project selector, multi-agent worktrees/board and repository-owned merge lifecycle.

Acceptance requires that planning chooses `existing + multi-agent + project + pr`, preserves the existing lifecycle/CI, installs platform metadata/hygiene safely, and produces a reviewable migration without requiring the project selector to support `--execute` or `--full`.

The test fixture must not copy business/domain code or depend on Jara_Fin itself.

## Compatibility and rollout

- Fresh onboarding behavior must remain regression-tested.
- Existing simple repositories without a coherent project harness may continue to use `harness_mode=platform`.
- Already-adopted repositories keep their reviewed `.dev-platform.toml` values.
- Ordinary managed rollout remains PR-based and does not auto-merge.
- Release only after both fresh and mature adoption fixtures pass and the platform's own full validation suite is green.