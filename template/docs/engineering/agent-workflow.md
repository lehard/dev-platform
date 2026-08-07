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

## Commands

```bash
python3 scripts/agent_doctor.py
python3 scripts/start_task.py my-task --task "OpenSpec add-x: 1-3" --scope "backend/..."
python3 scripts/select_checks.py --execute
python3 scripts/finish_task.py
```

The multi-agent profile may use `start_worktree.py` directly, but `start_task.py` is the preferred shared entrypoint.
