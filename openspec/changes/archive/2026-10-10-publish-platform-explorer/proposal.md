## Why
BR-441 requires a public, reproducible build and publication path that needs no manual site updates after platform changes. The repository is public and GitHub Actions is the existing control plane, so GitHub Pages deployed by a dedicated workflow fits without new infrastructure.

## What Changes
- Add a dedicated Explorer workflow that only orchestrates the repository-owned build entrypoint: on pull requests it builds the site (build verification, no deployment); on pushes to the default branch and manual dispatch it builds and deploys to GitHub Pages.
- Use least-privilege workflow permissions and SHA-pinned actions consistent with existing workflows; deployment jobs use a protected `github-pages` environment and concurrency that never cancels an in-progress deploy.
- Fail explicitly when Pages is not enabled for the repository; the workflow does not enable it and has no alternate publication path.
- Document the one-time operator step (Pages source set to GitHub Actions) and how to reproduce the published artifact locally from a commit.
- Keep the Explorer out of the downstream-consumed release surface; the site reflects the default branch and each page states its VERSION and commit.

## Current to Target
Currently no Explorer is published. Target: every merge to the default branch results in a refreshed public site produced by the same command a developer runs locally.

## Success Evidence
- A workflow-contract test verifies triggers, minimal permissions, SHA-pinned actions, that deployment happens only from the default branch, and that the workflow invokes the repository build entrypoint rather than inlining build logic.
- A pull request touching Explorer sources runs the build job and never the deploy job.
- With Pages disabled the deploy job fails with the platform's explicit error rather than succeeding silently.
- Documentation states the enablement step and the local reproduction command, and docs link checks pass.

## Non-goals
Custom domain, analytics, authentication or access control, preview deployments per pull request, hosting on any other provider, and changes to downstream reusable CI or release identity rules.

## Capabilities
### New Capabilities
- `explorer-publication`: automated build verification and Pages deployment of the Explorer.
### Modified Capabilities
None.

## Impact
New workflow under `.github/workflows/`, workflow-contract test, and operator documentation in `docs/engineering/explorer.md`. Nothing under `template/` changes; new projects and existing-project updates are unaffected, and downstream CI continues to avoid mutable `dev-platform@main` references.
