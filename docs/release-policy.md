# Platform release policy

Platform updates reach downstream repositories through reviewed Copier updates, never by executing mutable `dev-platform@main` logic.

## Release identity

Copier releases use immutable SemVer Git tags such as `v1.0.0` and `v1.0.1`. Published tags must never move or be reused; GitHub Immutable Releases should remain enabled.

### Choosing the version

The author of a release PR classifies every change since the previous tag and bumps the highest component any change requires. The point of view is an existing downstream project updating from the previous tag.

- **MAJOR** — an existing project cannot update without a manual action or breaks after the ordinary rollout PR: a removed or renamed command, subcommand, flag or template file it still uses; a Copier question whose answer must be given by hand (no safe default, or a changed meaning of a recorded answer); a persistent record, receipt or config that the new code no longer accepts; a new required config, environment variable or credential; a raised minimum Copier, Git or Python version; a CI behavior that turns a previously green project red.
- **MINOR** — new capability that existing projects absorb through the ordinary rollout PR without manual steps: a new command, subcommand or flag; a new Copier question with a default that preserves current behavior; a new optional config, environment variable or capability; a new persistent file or optional field; a new lifecycle state, gate or recovery path.
- **PATCH** — only repairs that restore behavior already established by an accepted spec or documented contract, plus documentation and test changes. A change that adds anything listed under MINOR is not a patch, even when it was delivered as a fix.

The release PR description lists the changes that determined the bump, and for MAJOR the manual action each affected project needs. When the classification is uncertain, choose the higher component.

## Downstream CI ownership

Starting with `v1.0.1`, generated project CI is self-contained: the Copier-managed workflow runs the Copier-managed `scripts/select_checks.py` from the downstream checkout using SHA-pinned GitHub Actions. It does not require private cross-repository reusable-workflow access.

GitHub Actions is the current control plane, not the default implementation
surface. Portable test, build, verification, release, and deploy behavior that
can run from a checked-out repository belongs behind a repository-owned
executable command or script, so developers and agents can invoke the same
behavior locally. The workflow orchestrates those entrypoints. GitHub-native
concerns -- events, permissions, concurrency, checkout/setup, secrets and
environment wiring, artifacts, and check/status integration -- remain in the
workflow. Do not introduce a generic provider abstraction merely to anticipate
another CI provider, and do not extract working inline workflow logic solely to
reduce YAML line count.

This keeps the same review boundary:

`dev-platform release -> exact-version Copier update PR -> downstream CI/review -> merge`

There is no silent remote workflow upgrade channel. `platform_ci_ref` remains in schema v2 for backward compatibility with v1.0.0 projects but is no longer required by the generated CI workflow.

## Managed rollout

An external operator-owned registry is the downstream project inventory and
cross-repository allowlist when managed rollout is enabled. Only entries in
state `managed` are eligible for central rollout. `candidate` means reviewed
first-time adoption is still expected; `excluded` records an intentional
non-adoption decision. The generic public core does not contain this registry.

After a version is published and the operator has enabled managed rollout (`DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED` repository variable), the release workflow dispatches the rollout workflow for that exact immutable tag. Rollout uses a least-privilege GitHub App with separate read-only platform-source and target-write tokens. The target token includes Workflows write because platform-managed updates can include `.github/workflows/*`. Rollout performs Copier update/doctor/project checks on a deterministic automation branch and opens a downstream PR. It does not auto-merge by default.

A blocked project does not stop other matrix entries. Conflicts, wrong/missing Copier ownership metadata, downgrade attempts, validation failures or unexpected branch collisions fail closed without changing the downstream default branch.

See `docs/managed-rollout.md` for registry ownership, one-time App setup and recovery.

## Upgrade safety

Platform CI and publication run `python3 scripts/validate_release_installation.py` before an immutable tag is created. It uses real Copier fresh renders and upgrades from the newest stable tag for GitHub platform/project harness modes plus the supported GitLab platform surface. Every disposable result receives the rollout-equivalent platform-only checks: reject detection, staged and unstaged diff hygiene, `platform_doctor.py` (including required files and selected capability surfaces). It deliberately does not call project selectors or application commands. Explicit local snapshot flags can skip a shallow checkout or upgrade cases when no baseline tag exists; CI and publication use neither flag and fail closed without complete history and a stable baseline.

Managed rollout must target an actually published immutable release tag using Copier `--vcs-ref`; it must never consume mutable `main` as the downstream upgrade source.

## Copier version

The platform tests Copier `9.18.2` exactly. Changing the tested version is an explicit platform change.

## Version publication

`VERSION` changes only in an explicit release PR. After merge, `.github/workflows/publish-version.yml` creates `v<VERSION>` at that exact commit, refuses to move an existing tag, and — only when the operator has opted in with the repository variable `DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED=true` (checked by `scripts/rollout_dispatch_gate.py`) — dispatches managed rollout for the exact published tag. Publishing a release never implies fleet rollout; without the variable the dispatch step is skipped.
