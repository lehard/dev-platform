# OpenSpec workflow

OpenSpec is the canonical planning layer for non-trivial product and architecture work. It does not replace repository engineering rules, runtime coordination, test selection, merge safety, operational runbooks or durable architecture documentation.

## Ownership

- `AGENTS.md` — how agents work.
- `openspec/specs/` — current durable expected behavior.
- `openspec/changes/<change>/` — active implementation contract.
- `.claude/agents-board.json` — active local concurrency coordination only.
- `docs/` — durable architecture/runbooks/project context outside active feature specs.

## Change lifecycle

1. Explore current code/specs/active changes.
2. Create or update one named OpenSpec change.
3. Put requirements/acceptance in specs, cross-cutting decisions in design, and execution/dependencies/verification in tasks.
4. Do not duplicate the plan elsewhere.
5. Implement in isolated worktrees using the agent board.
6. Mark tasks complete only after implementation and required verification.
7. Validate/synchronize/archive the change so durable behavior reaches `openspec/specs/`.

Small fixes may use the normal repository workflow without a ceremonial change.

## Parallel agents

Parallelize only task groups whose shared contracts are already fixed. Each agent uses its own worktree and board entry. Overlapping files or contracts must be serialized or explicitly split.

## Definition of done

A change is ready to archive when implementation is complete, selected checks pass (or deviations are explicit), migrations/compatibility are addressed where relevant, task checkboxes match reality, and durable behavior is synchronized through OpenSpec.
