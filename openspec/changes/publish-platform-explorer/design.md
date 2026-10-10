## Context
`AGENTS.md` requires portable build behavior to live behind a repository-owned entrypoint with providers only orchestrating, and `docs/release-policy.md` keeps GitHub Actions as the current control plane. The ADD resolved hosting as GitHub Pages via Actions because the repository is public and no extra infrastructure is needed.

## Decisions
1. **Workflow shape.** One workflow, two jobs. `build` runs on `pull_request`, `push` to the default branch and `workflow_dispatch`: checkout with full history needed for commit stamping, set up Python, run `python3 scripts/build_explorer.py build --out <dir>`, and on non-PR events upload the Pages artifact. `deploy` needs `build`, runs only for the default branch (push or dispatch on it), uses the `github-pages` environment and `actions/deploy-pages`.
2. **Thin provider.** The workflow contains no build logic: only checkout, interpreter setup, the single build command, artifact upload and deploy. All content and validation logic stays in `scripts/build_explorer.py`.
3. **Permissions.** Workflow default `contents: read`; the deploy job additionally `pages: write` and `id-token: write`. Actions are pinned by commit SHA like other platform workflows.
4. **Concurrency.** A `pages` concurrency group with `cancel-in-progress: false` so a deploy is never aborted midway; pull-request builds use a per-ref group that may cancel superseded runs.
5. **Pages not enabled.** `actions/configure-pages` is used without the `enablement` option, so a repository where Pages is not set to the GitHub Actions source fails with the action's explicit error. Enabling Pages is an operator repository setting documented as a one-time prerequisite; the workflow never changes repository settings.
6. **Reproducibility.** The same command builds locally and in CI; because the build is deterministic, a reviewer can rebuild a commit and compare to the published artifact. The artifact is also retained as the workflow artifact of the run.
7. **Path filtering.** Pull-request builds run when Explorer sources, canonical source roots it renders (docs, specs, capability descriptors, README), build script or the workflow change, so a source rename that breaks the map is caught before merge. Because a repository-wide check suite already treats workflow files as full-suite triggers, no check-selection change is required.

## Risks and Mitigations
- *Accidental public exposure:* the build already gates public safety (foundation); the workflow adds no extra sources and uploads only the build output directory.
- *Token over-privilege:* write permissions are confined to the deploy job.
- *Unpinned third-party actions:* SHA pinning is asserted by the workflow-contract test.
- *Pages not enabled yet:* explicit failure with documented remedy; no silent success.
- *Site reflecting unreleased main:* each page states VERSION and commit; the site is documentation, not a consumed release artifact.

## Ownership and Rollback
Platform-owned workflow, not rendered downstream. Rollback is deleting the workflow (and optionally unpublishing Pages in repository settings); no persisted data.

## Open Questions
None. Pages enablement is an operator action recorded as a prerequisite.
