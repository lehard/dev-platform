# Proposal: Separate rollout Harness validation from product verification

## Why

Managed rollout currently invokes the rendered `select_checks.py` for `harness_mode=platform` after Copier update and `platform_doctor`. A control-plane update can select downstream full/product commands, causing a rollout preparation to execute costly application checks and then execute them again in the rollout pull request's ordinary CI. The platform release has already undergone central regression validation; this rollout step should prove that the Dev Platform Harness was applied safely, while the downstream repository's CI remains the single clean-environment product gate.

## Current to target

Today `run_project_validation()` runs diff hygiene and platform doctor for every update, then runs the platform selector for `harness_mode=platform`. Target behavior retains all installation, integrity, configuration, and platform-compatibility checks, but never executes `select_checks.py` or any repository product/full command during managed rollout preparation, regardless of harness mode. The downstream rollout PR must continue through its ordinary CI before merge.

## What changes

- Make managed rollout validation explicitly Harness-installation/compatibility-only for `harness_mode=platform`.
- Retain the existing `harness_mode=project` boundary: rollout does not assume or execute a project-owned selector.
- Amend the managed-rollout specification and rollout validation tests to state the single product-verification ownership boundary.

## Success evidence

- A focused test proves neither `harness_mode=platform` nor `harness_mode=project` invokes `select_checks.py` during rollout preparation, while both run `git diff --check` and `platform_doctor`.
- The accepted spec says that downstream rollout-PR CI, not preparation, validates product behavior before merge.
- Existing platform checks, rendered-template validation, and semantic OpenSpec verification pass.

## Constraints and non-goals

All existing fail-closed Copier/update integrity, `.rej` detection, config/version coherence, platform-owned invariants, and `platform_doctor` behavior are preserved. This does not alter downstream product test composition, downstream CI workflows, or the project-owned harness lifecycle.

## Delivery scope

The shared rollout engine and its accepted spec change for both new project renders and existing-project Copier updates. Existing projects receive the changed platform script only through a reviewed immutable-release rollout PR.
