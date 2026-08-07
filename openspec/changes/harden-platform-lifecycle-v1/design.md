# Design

## Lifecycle

The shared lifecycle becomes `doctor -> fetch/sync -> start -> implement -> checks -> fetch again -> publish`. GitHub publication is a platform responsibility, not a user hand-off.

`project_sync.py` only fast-forwards a clean local integration branch from `origin/main`; ahead/diverged states abort. `project_publish.py` re-fetches immediately before publication. Direct mode pushes only when remote main is an ancestor of local main. PR mode pushes the feature branch and creates/reuses a PR through authenticated `gh`; it never merges the PR.

`start_task.py` and `finish_task.py` are profile-aware orchestration entrypoints. Legacy `merge_to_main.py` remains a compatibility wrapper.

## Profiles as capabilities

- light: core planning/check/sync/publish, no mandatory feature branch/worktree/board;
- standard: adds feature branches;
- multi-agent: adds worktrees, board and scope ownership.

One template implements all profiles; profile flags live in `.dev-platform.toml` so later capabilities can be added without template forks.

## OpenSpec contract

`AGENTS.md` describes sources by ownership instead of a false total order: process constraints, accepted current specs, approved active delta, implementation. If implementation changes direction, artifacts are updated before code knowingly diverges. Non-trivial archive requires project checks and `/opsx:verify`.

OpenSpec remains external. The platform records minimum/tested versions and diagnoses compatibility. Since expanded workflow selection is user/global-profile driven, bootstrap initializes core non-interactively and clearly requires enabling `verify` with `openspec config profile` + `openspec update`; generated verify skills are never vendored.

## Release pinning

Generated CI references `platform_ci_ref`, default `release-v1.0.0`, never `main`. The v1 release ref is append-only: once created it must never move. Future release refs are changed downstream only through reviewed Copier updates.

## Promotion inbox

Friction stays machine-local. `agent_friction.py promote <id>` is deliberate, requires authenticated `gh`, rejects project-scoped events, omits raw evidence, sanitizes obvious credential-like values, and creates a central issue. Dry-run is supported for review before upload.

## Compatibility and rollback

Existing downstream repositories have not yet adopted the platform, so schema v2 can be introduced before dogfood. Copier remains the migration mechanism. All Git mutation paths fail closed on dirty/diverged states. A project can roll back by pinning its previous platform release ref and reverting the reviewed Copier update.
