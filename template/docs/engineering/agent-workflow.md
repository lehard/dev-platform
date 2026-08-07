# Agent workflow

## Start

```bash
python3 scripts/agent_board.py doctor
python3 scripts/start_worktree.py <slug> --task "<task>" --scope "<scope>"
```

Work only in the created worktree.

## During work

- keep the board scope accurate if ownership changes;
- use OpenSpec as the task contract for non-trivial work;
- do not treat the board as a backlog;
- do not touch another active agent's scope without resolving the overlap.

## Validate

```bash
python3 scripts/select_checks.py
python3 scripts/select_checks.py --execute
```

Project-specific command mappings live in `dev-platform/checks.toml`.

## Merge

Commit the worktree, then:

```bash
python3 scripts/merge_to_main.py
```

Only a clean fast-forward merge is performed. No automatic conflict resolution.

## Learn

When a session exposes meaningful process friction:

```bash
python3 scripts/agent_friction.py record --help
```

Review periodically with:

```bash
python3 scripts/agent_friction.py review --days 7
```

Promote only reusable findings to the central platform.
