# Proposal: Managed project rollout

## Why

`dev-platform` can already publish immutable releases and individual downstream repositories can update themselves with Copier, but the human still has to remember which projects are managed and manually start each upgrade. That recreates the dispatcher role the platform is meant to remove.

The platform also still contains obsolete adoption guidance about private cross-repository reusable CI even though generated CI has been self-contained since v1.0.1.

## What changes

- Add an explicit allowlisted registry of repositories known to the platform, with only `managed` entries eligible for automatic rollout.
- Add a central rollout workflow that is dispatched automatically after a successful platform release and can also be run manually for recovery/retry.
- Use a least-privilege GitHub App installation token for cross-repository writes; the repository `GITHUB_TOKEN` remains insufficient by design.
- For every managed project, perform an exact-version Copier update in an isolated automation branch, fail closed on conflicts, run platform doctor/project checks, and open a reviewable PR.
- Never auto-merge rollout PRs in this version.
- Skip projects that already have an open rollout PR for the same target version rather than force-pushing or duplicating work.
- Keep non-adopted repositories out of automatic mutation until they are explicitly promoted to `managed` after reviewed adoption.
- Fix obsolete adoption documentation about cross-repository reusable CI access.

## Affected scope

This change affects existing-project updates and central release automation. It does not change application-domain behavior.

Affected central files include:

- managed-project registry and validation tooling;
- release/rollout GitHub Actions workflows;
- rollout scripts/tests;
- adoption/release/README guidance.

## Compatibility and safety

- Existing managed projects retain Copier ownership and project-local customizations.
- Rollout targets an exact immutable platform SemVer tag, never `main`.
- Conflicts, missing Copier metadata, wrong template source, failed doctor/checks, or an unexpected existing rollout branch block that project without mutating its default branch.
- GitHub App credentials are never stored in the repository; only a client ID variable and private-key secret are referenced by workflow configuration.
