# Agent workflow

The platform exposes one lifecycle with profile-specific capabilities:

`doctor -> sync origin -> start -> OpenSpec/implementation -> checks -> fetch origin again -> publish -> verify/archive`

## Profiles

- `light`: single-agent, synchronized integration branch, no mandatory feature branch/worktree/board.
- `standard`: feature branches + GitHub PR/direct publication; no mandatory worktrees/board.
- `multi-agent`: feature branches inside isolated worktrees + machine-local agent board and scope ownership.

Profiles select capabilities; they are not separate forks of the platform.

## Publishing

`publish_mode=pr` is the safe default for standard and multi-agent profiles. It pushes the task branch and creates a PR via authenticated GitHub CLI. It does not auto-merge.

`publish_mode=direct` is an explicit simplification. It re-fetches immediately before push and only pushes when remote main is an ancestor of local main. Force push is never used.

## Local-heavy, cloud-final verification

Required selected and full checks run locally before publication. The self-contained cloud workflow is the final clean-environment merge gate for `publish_mode=pr`; for `publish_mode=direct`, it validates the published main state as a health signal. It deliberately has one automatic trigger path for the selected publish mode, plus manual dispatch, and cancels superseded runs for the same PR/ref. Do not skip local verification because cloud CI is narrower, and do not automatically duplicate expensive full/browser suites after a successful PR without a reviewed repository-specific reason.

## Commands

```bash
python3 scripts/agent_doctor.py
python3 scripts/start_task.py my-task --task "OpenSpec add-x: 1-3" --scope "backend/..."
python3 scripts/select_checks.py --execute
python3 scripts/finish_task.py
```

The multi-agent profile may use `start_worktree.py` directly, but `start_task.py` is the preferred shared entrypoint.
