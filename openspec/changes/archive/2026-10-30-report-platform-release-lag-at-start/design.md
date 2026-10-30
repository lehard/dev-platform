## Context

`start_task` runs `reconcile_pending_rollout` (merge a green pending rollout PR) before creating the task. The project's installed release is `platform_version` in `.dev-platform.toml` (kept equal to `.copier-answers.yml` `_commit` by `platform_doctor`); the platform source is `_src_path` (`gh:owner/name`, `https://github.com/owner/name[.git]`, `git@github.com:owner/name.git`). Releases are published as immutable `vX.Y.Z` tags with a GitHub release (`publish-version.yml`). On-demand update is the Roll Out Platform workflow in the platform source repository with inputs `version` and `repository`.

## Decisions

- **Warn and continue.** A lagging project is reported and the task starts. Updating is a deliberate owner action on a project they work on (auto-rollout was disabled to avoid forced updates); stopping every start would force an update before any unrelated work. The report is printed before the task is created so it is the first thing the session sees. Rejected: stopping the start (forces updates the owner opted out of), a flag to choose (no second consumer).
- **Fail explicitly when undeterminable.** A non-SemVer `platform_version`, a missing/unrecognized `_src_path`, no GitHub environment, an unresolvable project repository, or a failed/invalid latest-release read raise `PlatformLagError` with the cause; `start_task` stops with it. No skip.
- **Latest = the source's latest GitHub release** (`gh api repos/<source>/releases/latest`, `tag_name` `vX.Y.Z`). A project version equal to or newer than it is `current`.
- **Not applicable** only for the platform source checkout (`platform_version = "source"`); `harness_mode=project` never reaches this code (`start_task` refuses it earlier).
- **After reconciliation.** The config is re-read after `reconcile_pending_rollout`, so a just-merged rollout is measured at its new version.

## Risks

- Task start now needs a reachable GitHub API for the release read; it already needs it for `gh repo view`/pending-rollout PRs, and an outage now stops start with the reason instead of passing silently.
