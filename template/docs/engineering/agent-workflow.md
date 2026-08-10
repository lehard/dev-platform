# Agent workflow

The platform exposes one lifecycle with profile-specific capabilities:

`doctor -> sync origin -> start -> OpenSpec/implementation -> checks -> fetch origin again -> publish -> verify/archive`

## Profiles

- `light`: single-agent, synchronized integration branch, no mandatory feature branch/worktree/board.
- `standard`: feature branches + GitHub PR/direct publication; no mandatory worktrees/board.
- `multi-agent`: feature branches inside isolated worktrees + machine-local agent board and scope ownership.

Profiles select capabilities; they are not separate forks of the platform.

## Publishing

Protected main and zero-hand-off are compatible. The safe normal configuration for feature-capable projects is:

```toml
protected_main = true
publish_mode = "pr"
pr_merge_mode = "auto"
```

With that configuration, `finish_task.py` pushes the validated feature branch, creates or reuses a PR, waits for GitHub checks, merges through GitHub, and only then fast-forwards local `main` to the merged remote state. Required status checks remain authoritative; the platform never uses branch-protection bypass.

PR merge completion is reconciled from GitHub's PR state rather than from client-side branch-cleanup convenience. The merge command does not use `--delete-branch`; after GitHub confirms `MERGED`, the remote task branch is deleted separately, then local `main`/board state is reconciled. If `--cleanup` is requested in a multi-agent worktree, the running process first moves to the integration checkout and removes the completed task worktree/local branch from there.

`pr_merge_mode=manual` keeps an explicit review stop after PR creation. Cross-repository Dev Platform rollout PRs remain reviewed and are not auto-merged by this task-publication policy.

`publish_mode=direct` is only valid for an intentionally unprotected integration branch. It re-fetches immediately before push and only pushes when remote main is an ancestor of local main. `protected_main=true` plus `publish_mode=direct` is an invalid configuration and doctor/finish preflight must reject it before local integration.

Platform-owned PR publication requires authenticated GitHub CLI/API access. Run `gh auth login` once on the agent host (or provide a supported `GH_TOKEN`/`GITHUB_TOKEN`). Doctor checks this before a protected-main task reaches publication. Git branch push and PR API operations are kept separate so validated work is not lost if `project_publish.py` is invoked directly in a partially configured environment.

## Local-heavy, cloud-final verification

Required selected and full checks run locally before publication. The self-contained cloud workflow is the final clean-environment merge gate for `publish_mode=pr`. Protected PR publication waits for that gate before merging. Superseded validation runs for the same PR/ref are cancelled. Manual workflow dispatch remains the explicit cloud path for a full platform-managed run when that is useful.

For intentionally unprotected `publish_mode=direct` repositories, the published main state receives an automatic run that is deliberately lightweight: it validates platform/OpenSpec health without repeating the full project check set. Direct-mode repositories also retain the stable pull-request `platform-ci` gate for explicitly reviewed maintenance or rollout PRs so existing required-status protection can be satisfied if such a PR is used.

Do not skip local verification because cloud CI is narrower, and do not use the compatibility PR gate as a reason to duplicate expensive full/browser suites without a reviewed repository-specific need.

## Commands

```bash
python3 scripts/agent_doctor.py
python3 scripts/start_task.py my-task --task "OpenSpec add-x: 1-3" --scope "backend/..."
python3 scripts/select_checks.py --execute
python3 scripts/finish_task.py
```

The multi-agent profile may use `start_worktree.py` directly, but `start_task.py` is the preferred shared entrypoint.
