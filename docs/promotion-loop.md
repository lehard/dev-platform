# Improvement promotion loop

The platform is intended to learn from real project work without automatically turning every local annoyance into global policy.

## 1. Observe in the project

Record friction only when there is useful signal: a user correction, repeated failure, safety near-miss, important undocumented invariant, or excessive retries.

Use:

```bash
python3 scripts/agent_friction.py record \
  --category workflow \
  --observation "..." \
  --evidence "..." \
  --hypothesis "..." \
  --scope platform \
  --proposal "..."
```

The log is machine-local under `.claude/` and must not contain secrets or sensitive data.

## 2. Review periodically

```bash
python3 scripts/agent_friction.py review --days 7
```

Classify each useful finding as:

- `project` — fix only the owning repository;
- `platform` — candidate for `dev-platform`.

One incident is evidence, not automatic authorization to rewrite shared rules.

## 3. Promote through OpenSpec

For a platform candidate:

1. inspect current platform behavior and affected downstream files;
2. create an OpenSpec change in `dev-platform`;
3. define compatibility/update behavior;
4. implement and validate the template plus platform CI;
5. merge a reviewed platform change.

## 4. Propagate

Existing projects receive the change through a reviewed Copier update, ideally in a dedicated PR/worktree.

New projects automatically start from the latest accepted platform state.

The goal is controlled learning: improvements spread, but project-specific exceptions and local experiments do not silently become global policy.
