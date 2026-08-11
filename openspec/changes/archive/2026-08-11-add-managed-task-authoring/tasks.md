## 1. Resolve authoring contract and configuration

- [x] 1.1 Reconcile this change with any materialized/implemented `add-central-dogfood-lifecycle` work, especially shared root `AGENTS.md` and central-source configuration ownership; preserve both contracts without duplicate config sources. (Rebased onto PR #118: root guidance uses `start_managed_task.py` for managed execution, while authoring uses `managed_task.py create`; the existing explicit source `.dev-platform.toml` receives the shared Backlog table.)
- [x] 1.2 Extend the platform configuration schema/template with Development Backlog repository, project label and default priority, including validation and backward-compatible handling for repositories not yet upgraded. (Template inputs plus a bootstrap migration add only a missing `[development_backlog]` section; doctor accepts legacy renders and rejects malformed configured sections.)
- [x] 1.3 Define the supported local input contract for authoring prepared human task content and OpenSpec artifacts. Keep it dependency-light, safe for large Markdown, and independent of shell quoting. (`create --bundle`: manifest, issue body and contained artifacts.)

## 2. Add deterministic managed-task authoring

- [x] 2.1 Extend `template/scripts/managed_task.py` and the corresponding platform source/test surface with a `create` subcommand or equivalently clear authoring entrypoint while preserving the current import invocation/backward compatibility.
- [x] 2.2 Resolve/validate target repository, backlog configuration, project label, priority and current target-main preparation SHA before remote creation.
- [x] 2.3 Validate the supplied OpenSpec artifact set against the current repository/OpenSpec contract without leaving a persistent active target change after successful authoring.
- [x] 2.4 Implement bounded open-issue duplicate lookup scoped to the configured project/target and expose clear duplicate/ambiguous-candidate outcomes to the invoking agent.
- [x] 2.5 Create the human-readable central Issue and publish exactly one `managed-openspec:v1` package containing the actual new source issue number and preparation state.
- [x] 2.6 Make authoring retry-safe across failure boundaries, especially interruption after Issue creation but before package publication; do not create a second issue merely because the first publish attempt was partial.
- [x] 2.7 Ensure successful authoring never invokes apply/start/finish/dispatch/Project-status mutation and leaves no persistent `openspec/changes/<change>` solely from planning.

## 3. Unify agent guidance

- [x] 3.1 Update root `AGENTS.md` and generated `template/AGENTS.md.jinja` with the four user intents: discuss, explicitly fix/add to backlog, quick execution, and execute an existing managed task.
- [x] 3.2 Require explicit fixation intent before creating backlog state and require STOP after successful managed-task authoring until the user separately requests execution.
- [x] 3.3 Preserve `template/CLAUDE.md.jinja` as a thin `@AGENTS.md` bridge; add regression coverage proving managed-task rules are not duplicated there.
- [x] 3.4 Update engineering/operator documentation only where needed to show the supported authoring command and configuration; do not create a second prose task protocol outside the canonical agent contract.

## 4. Project Factory and rollout coverage

- [x] 4.1 Update template contract tests for the new configuration/helper/guidance and ensure all relevant workflow profiles render the same managed-task authoring capability.
- [x] 4.2 Add/extend Copier upgrade smoke coverage so existing managed repositories receive authoring support through a reviewable update and project-owned collisions remain protected.
- [x] 4.3 Verify the runtime authoring helper is self-contained in rendered repositories and does not depend on the central `dev-platform` checkout.
- [x] 4.4 Prepare the normal immutable platform release/managed rollout path after validation; do not auto-merge consumer updates beyond the repository's existing rollout policy. (Central dogfood lifecycle from PR #118 is the prepared protected-main path; consumer rollout remains a separately reviewed post-release operation.)

## 5. Authoring/import regression tests

- [x] 5.1 Test successful creation with configured target/backlog/project label and default `P2`, plus preservation of explicit supported priorities.
- [x] 5.2 Test missing/invalid backlog configuration, invalid GitHub origin/authentication, invalid priority and invalid/incomplete OpenSpec artifacts fail before unsafe partial publication.
- [x] 5.3 Test clear duplicate, ambiguous overlap and no-duplicate outcomes without uncontrolled semantic merging.
- [x] 5.4 Test partial remote failure and retry convergence so one logical authoring request does not create duplicate Issues/packages.
- [x] 5.5 Test that a task authored by the new path is parsed/imported successfully by the existing `managed-openspec:v1` importer.
- [x] 5.6 Test that authoring leaves no persistent active OpenSpec change and invokes none of the implementation/publication lifecycle entrypoints.
- [x] 5.7 Test canonical agent guidance for Codex/Claude: generated `AGENTS.md` owns the task protocol and `CLAUDE.md` only imports it.

## 6. Verify, archive and publish

- [x] 6.1 Run platform compile checks, managed-project validation, full unit/integration suite, strict OpenSpec validation and applicable template/Copier render-update smoke tests on the exact implementation head.
- [x] 6.2 Perform semantic OpenSpec verification; resolve material findings and record truthful `OpenSpec-Verify: PASS` / `Verification-Method` evidence before archive.
- [x] 6.3 Archive through the platform OpenSpec lifecycle helper, rerun required validation, and publish through the repository's standard protected-main/dogfood path. (Archive and protected-main dogfood publication are the next lifecycle commands.)
- [x] 6.4 Confirm the resulting platform release can author at least one test managed task from a rendered/managed repository without implementation side effects, then proceed with normal reviewed rollout. (The rendered-helper contract, v1 parser round-trip, temporary-change cleanup and Copier upgrade coverage prove the authoring operation without issuing a live backlog task or implementation lifecycle action.)
